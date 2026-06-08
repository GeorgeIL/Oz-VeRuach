import io
import json
import re
from datetime import datetime, timezone

import boto3
import markdown as md_lib  # type: ignore
from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    jsonify,
    url_for,
)
from werkzeug.utils import secure_filename
from pypdf import PdfReader

from auth_utils import get_current_user, login_required
from config import Config
from db import get_db
from rag import engine as rag
from services import s3_recipes

recipes_bp = Blueprint("recipes", __name__, url_prefix="/recipes")
PAGE_SIZE = 20


# ── Helpers ───────────────────────────────────────────────────────────────────


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def _recipe_to_md(title, description, ingredients, steps, notes, tags) -> str:
    lines = [f"# {title}\n"]
    if description:
        lines += [f"## Description\n\n{description}\n"]
    if tags:
        lines += [f"**Tags:** {', '.join(t for t in tags if t)}\n"]
    if ingredients:
        lines += ["## Ingredients\n"]
        lines += [f"- {i}" for i in ingredients if i]
        lines += [""]
    if steps:
        lines += ["## Steps\n"]
        lines += [f"{n}. {s}" for n, s in enumerate(steps, 1) if s]
        lines += [""]
    if notes:
        lines += [f"## Notes\n\n{notes}\n"]
    return "\n".join(lines)


def _render_md(text: str) -> str:
    return md_lib.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br", "toc"],
    )


def _s3():
    return boto3.client("s3", region_name=Config.AWS_REGION)


def _s3_key(slug: str) -> str:
    return s3_recipes.catalog_s3_key(slug)


def _upload_to_s3(slug: str, md_content: str) -> str:
    key = _s3_key(slug)
    _s3().put_object(
        Bucket=Config.S3_BUCKET,
        Key=key,
        Body=md_content.encode("utf-8"),
        ContentType="text/markdown",
    )
    return key


def _delete_from_s3(s3_key: str) -> None:
    try:
        _s3().delete_object(Bucket=Config.S3_BUCKET, Key=s3_key)
    except Exception:
        pass


def _unique_slug(conn, base_slug: str) -> str:
    slug, counter = base_slug, 1
    with conn.cursor() as cur:
        while True:
            cur.execute("SELECT id FROM recipes WHERE slug = %s", (slug,))
            if not cur.fetchone():
                return slug
            slug = f"{base_slug}-{counter}"
            counter += 1


def _row_to_recipe(row) -> dict:
    r = dict(row)
    r["_id"] = r.get("id", "")  # template compat
    return r


# ── Routes ────────────────────────────────────────────────────────────────────


@recipes_bp.route("/")
@login_required
def list_recipes():
    user = get_current_user()
    conn = get_db()

    sort = request.args.get("sort", "az")
    if sort not in ("latest", "oldest", "az", "za"):
        sort = "az"

    query = (request.args.get("q") or "").strip()
    select_mode = request.args.get("select") == "1"
    return_url = request.args.get("return") or url_for("buddies.buddies_page")

    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1

    offset = (page - 1) * PAGE_SIZE
    items, total = s3_recipes.search_recipes(
        conn, query, PAGE_SIZE, offset, sort=sort
    )
    total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    if page > total_pages:
        page = total_pages
        offset = (page - 1) * PAGE_SIZE
        items, total = s3_recipes.search_recipes(
            conn, query, PAGE_SIZE, offset, sort=sort
        )

    recipes = [_row_to_recipe(item) for item in items]

    with conn.cursor() as cur:
        cur.execute(
            "SELECT recipe_slug FROM favorites WHERE user_id = %s", (user["sub"],)
        )
        favorites = {r["recipe_slug"] for r in cur.fetchall()}

    return render_template(
        "recipes/list.html",
        recipes=recipes,
        favorites=favorites,
        current_sort=sort,
        current_query=query,
        page=page,
        total=total,
        total_pages=total_pages,
        page_size=PAGE_SIZE,
        select_mode=select_mode,
        return_url=return_url,
    )


@recipes_bp.route("/new")
@login_required
def new_recipe():
    return render_template("recipes/form.html", recipe=None, action="create")


@recipes_bp.route("/", methods=["POST"])
@login_required
def create_recipe():
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    ingredients = [i.strip() for i in (data.get("ingredients") or []) if str(i).strip()]
    steps = [s.strip() for s in (data.get("steps") or []) if str(s).strip()]
    notes = (data.get("notes") or "").strip()
    tags = [t.strip().lower() for t in (data.get("tags") or []) if str(t).strip()]

    if not title:
        return jsonify({"error": "Recipe title is required"}), 400
    if not ingredients:
        return jsonify({"error": "At least one ingredient is required"}), 400
    if not steps:
        return jsonify({"error": "At least one step is required"}), 400

    conn = get_db()
    slug = _unique_slug(conn, _slugify(title))
    md_content = _recipe_to_md(title, description, ingredients, steps, notes, tags)
    s3_key = _upload_to_s3(slug, md_content)

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO recipes
               (slug, title, description, ingredients, steps, notes, tags,
                author_id, author_username, s3_key)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                slug,
                title,
                description,
                json.dumps(ingredients),
                json.dumps(steps),
                notes,
                json.dumps(tags),
                user["sub"],
                user["username"],
                s3_key,
            ),
        )
    conn.commit()
    s3_recipes.invalidate_index_cache()
    rag.sync_knowledge_base()

    return (
        jsonify(
            {
                "message": "Recipe created",
                "redirect": url_for("recipes.view_recipe", slug=slug),
            }
        ),
        201,
    )


@recipes_bp.route("/<slug>")
@login_required
def view_recipe(slug):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id::text AS id, slug, title, description, ingredients, steps, notes, tags, "
            "author_id::text AS author_id, author_username, created_at, s3_key "
            "FROM recipes WHERE slug = %s",
            (slug,),
        )
        recipe = cur.fetchone()

    if recipe:
        recipe = _row_to_recipe(recipe)
        md_content = _recipe_to_md(
            recipe["title"],
            recipe["description"],
            recipe["ingredients"],
            recipe["steps"],
            recipe["notes"],
            recipe["tags"],
        )
        html_content = _render_md(md_content)
        user = get_current_user()
        is_author = user and user["sub"] == recipe["author_id"]
        return render_template(
            "recipes/detail.html",
            recipe=recipe,
            html_content=html_content,
            is_author=is_author,
        )

    catalog_key = s3_recipes.catalog_s3_key(slug)
    try:
        md_content = s3_recipes.get_recipe_content(catalog_key)
    except Exception:
        abort(404)

    title = s3_recipes.title_for_key(catalog_key, md_content)
    tags = s3_recipes.parse_tags(md_content)
    html_content = _render_md(md_content)
    recipe = {
        "id": "",
        "slug": slug,
        "title": title,
        "description": "",
        "tags": tags,
        "author_username": None,
        "author_id": None,
        "created_at": None,
        "s3_key": catalog_key,
    }
    return render_template(
        "recipes/detail.html",
        recipe=recipe,
        html_content=html_content,
        is_author=False,
    )


@recipes_bp.route("/<slug>/edit")
@login_required
def edit_recipe(slug):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id::text AS id, slug, title, description, ingredients, steps, notes, tags, "
            "author_id::text AS author_id, author_username FROM recipes WHERE slug = %s",
            (slug,),
        )
        recipe = cur.fetchone()
    if not recipe:
        abort(404)
    return render_template(
        "recipes/form.html", recipe=_row_to_recipe(recipe), action="edit"
    )


@recipes_bp.route("/<slug>", methods=["PUT"])
@login_required
def update_recipe(slug):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT id, s3_key FROM recipes WHERE slug = %s", (slug,))
        recipe = cur.fetchone()
    if not recipe:
        return jsonify({"error": "Recipe not found"}), 404

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    ingredients = [i.strip() for i in (data.get("ingredients") or []) if str(i).strip()]
    steps = [s.strip() for s in (data.get("steps") or []) if str(s).strip()]
    notes = (data.get("notes") or "").strip()
    tags = [t.strip().lower() for t in (data.get("tags") or []) if str(t).strip()]

    if not title:
        return jsonify({"error": "Title is required"}), 400

    md_content = _recipe_to_md(title, description, ingredients, steps, notes, tags)
    s3_key = _upload_to_s3(slug, md_content)

    with conn.cursor() as cur:
        cur.execute(
            """UPDATE recipes SET title=%s, description=%s, ingredients=%s,
               steps=%s, notes=%s, tags=%s, s3_key=%s, updated_at=%s WHERE slug=%s""",
            (
                title,
                description,
                json.dumps(ingredients),
                json.dumps(steps),
                notes,
                json.dumps(tags),
                s3_key,
                datetime.now(timezone.utc),
                slug,
            ),
        )
    conn.commit()
    s3_recipes.invalidate_index_cache()
    rag.sync_knowledge_base()
    return jsonify(
        {
            "message": "Recipe updated",
            "redirect": url_for("recipes.view_recipe", slug=slug),
        }
    )


@recipes_bp.route("/<slug>", methods=["DELETE"])
@login_required
def delete_recipe(slug):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT s3_key FROM recipes WHERE slug = %s", (slug,))
        recipe = cur.fetchone()
    if not recipe:
        return jsonify({"error": "Recipe not found"}), 404

    _delete_from_s3(recipe["s3_key"])
    with conn.cursor() as cur:
        cur.execute("DELETE FROM recipes WHERE slug = %s", (slug,))
    conn.commit()
    s3_recipes.invalidate_index_cache()
    rag.sync_knowledge_base()
    return jsonify(
        {"message": "Recipe deleted", "redirect": url_for("recipes.list_recipes")}
    )


# ── API: list recipes (for chat quick-picks) ──────────────────────────────────


@recipes_bp.route("/api/list")
@login_required
def api_list():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id::text AS id, title, slug, tags, ingredients FROM recipes ORDER BY title"
        )
        rows = [dict(r) for r in cur.fetchall()]
    return jsonify(rows)


# ── Save AI-generated recipe from chat ───────────────────────────────────────


@recipes_bp.route("/from-chat", methods=["POST"])
@login_required
def recipe_from_chat():
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    ingredients = [i.strip() for i in (data.get("ingredients") or []) if str(i).strip()]
    steps = [s.strip() for s in (data.get("steps") or []) if str(s).strip()]
    notes = (data.get("notes") or "").strip()
    tags = [t.strip().lower() for t in (data.get("tags") or []) if str(t).strip()]

    if not title:
        return jsonify({"error": "Recipe title is missing"}), 400
    if not ingredients or not steps:
        return jsonify({"error": "Recipe must have ingredients and steps"}), 400

    conn = get_db()
    slug = _unique_slug(conn, _slugify(title))
    md_content = _recipe_to_md(title, description, ingredients, steps, notes, tags)
    s3_key = _upload_to_s3(slug, md_content)

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO recipes
               (slug, title, description, ingredients, steps, notes, tags,
                author_id, author_username, s3_key)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                slug,
                title,
                description,
                json.dumps(ingredients),
                json.dumps(steps),
                notes,
                json.dumps(tags),
                user["sub"],
                "Chef AI",
                s3_key,
            ),
        )
    conn.commit()
    s3_recipes.invalidate_index_cache()
    rag.sync_knowledge_base()

    return (
        jsonify(
            {
                "message": "Recipe saved",
                "redirect": url_for("recipes.view_recipe", slug=slug),
            }
        ),
        201,
    )


# ── Favourite toggle ──────────────────────────────────────────────────────────


@recipes_bp.route("/<slug>/favorite", methods=["POST"])
@login_required
def toggle_favorite(slug):
    user = get_current_user()
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM favorites WHERE user_id = %s AND recipe_slug = %s",
            (user["sub"], slug),
        )
        if cur.fetchone():
            cur.execute(
                "DELETE FROM favorites WHERE user_id = %s AND recipe_slug = %s",
                (user["sub"], slug),
            )
            conn.commit()
            return jsonify({"favorited": False})
        cur.execute(
            "INSERT INTO favorites (user_id, recipe_slug) VALUES (%s, %s)",
            (user["sub"], slug),
        )
    conn.commit()
    return jsonify({"favorited": True})


# ── Upload recipe from PDF / TXT ─────────────────────────────────────────────

_ALLOWED_EXTENSIONS = {".pdf", ".txt"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@recipes_bp.route("/upload", methods=["GET"])
@login_required
def upload_recipe_page():
    return render_template("recipes/upload.html", error=None)


@recipes_bp.route("/upload", methods=["POST"])
@login_required
def upload_recipe():
    user = get_current_user()

    if "file" not in request.files or not request.files["file"].filename:
        return render_template(
            "recipes/upload.html", error="Please select a file to upload."
        )

    file = request.files["file"]
    filename = secure_filename(file.filename)
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in _ALLOWED_EXTENSIONS:
        return render_template(
            "recipes/upload.html", error="Only .pdf and .txt files are supported."
        )

    file_bytes = file.read()
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        return render_template(
            "recipes/upload.html", error="File is too large (max 10 MB)."
        )

    # Extract raw text
    if ext == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return render_template(
                "recipes/upload.html",
                error="Could not read the PDF. Make sure it contains selectable text.",
            )
    else:
        raw_text = file_bytes.decode("utf-8", errors="replace")

    if not raw_text.strip():
        return render_template(
            "recipes/upload.html", error="No text could be extracted from the file."
        )

    # Parse with Nova Lite
    try:
        parsed = rag.parse_recipe_from_text(raw_text)
    except Exception as exc:
        return render_template("recipes/upload.html", error=f"AI parsing failed: {exc}")

    title = (parsed.get("title") or "").strip()
    if not title:
        return render_template(
            "recipes/upload.html",
            error="Chef AI could not detect a recipe title. Try a cleaner file.",
        )
    description = (parsed.get("description") or "").strip()
    ingredients = [
        i.strip() for i in (parsed.get("ingredients") or []) if str(i).strip()
    ]
    steps = [s.strip() for s in (parsed.get("steps") or []) if str(s).strip()]
    notes = (parsed.get("notes") or "").strip()
    tags = [t.strip().lower() for t in (parsed.get("tags") or []) if str(t).strip()]

    if not ingredients or not steps:
        return render_template(
            "recipes/upload.html",
            error="Chef AI could not extract ingredients or steps from the file.",
        )

    conn = get_db()
    slug = _unique_slug(conn, _slugify(title))
    md_content = _recipe_to_md(title, description, ingredients, steps, notes, tags)
    s3_key = _upload_to_s3(slug, md_content)

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO recipes
               (slug, title, description, ingredients, steps, notes, tags,
                author_id, author_username, s3_key)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                slug,
                title,
                description,
                json.dumps(ingredients),
                json.dumps(steps),
                notes,
                json.dumps(tags),
                user["sub"],
                user["username"],
                s3_key,
            ),
        )
    conn.commit()
    s3_recipes.invalidate_index_cache()
    rag.sync_knowledge_base()

    return redirect(url_for("recipes.view_recipe", slug=slug))
