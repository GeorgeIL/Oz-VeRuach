import re
import io
from datetime import datetime, timezone
from pathlib import Path

import markdown as md_lib  # type: ignore
from bson import ObjectId  # type: ignore
from flask import (
    Blueprint,
    abort,
    flash,
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

recipes_bp = Blueprint("recipes", __name__, url_prefix="/recipes")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def _safe_path(filename: str) -> Path:
    """Resolve path and ensure it stays inside DATA_FOLDER."""
    resolved = (Config.DATA_FOLDER / filename).resolve()
    if not str(resolved).startswith(str(Config.DATA_FOLDER.resolve())):
        abort(400, "Invalid filename")
    return resolved


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


# ── Routes ────────────────────────────────────────────────────────────────────


@recipes_bp.route("/")
@login_required
def list_recipes():
    user = get_current_user()
    db = get_db()

    sort = request.args.get("sort", "latest")
    sort_map = {
        "latest": ("created_at", -1),
        "oldest": ("created_at", 1),
        "az": ("title", 1),
        "za": ("title", -1),
    }
    sort_field, sort_dir = sort_map.get(sort, ("created_at", -1))

    recipes = list(
        db.recipes.find(
            {},
            {
                "title": 1,
                "slug": 1,
                "description": 1,
                "tags": 1,
                "author_username": 1,
                "created_at": 1,
            },
        ).sort(sort_field, sort_dir)
    )
    for r in recipes:
        r["_id"] = str(r["_id"])

    user_doc = db.users.find_one({"_id": ObjectId(user["sub"])}, {"favorites": 1})
    favorites = set(user_doc.get("favorites") or [])

    return render_template(
        "recipes/list.html",
        recipes=recipes,
        favorites=favorites,
        current_sort=sort,
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

    slug = _slugify(title)
    db = get_db()

    # Unique slug
    base_slug, counter = slug, 1
    while db.recipes.find_one({"slug": slug}):
        slug = f"{base_slug}-{counter}"
        counter += 1

    filename = f"{slug}.md"
    md_content = _recipe_to_md(title, description, ingredients, steps, notes, tags)
    _safe_path(filename).write_text(md_content, encoding="utf-8")

    recipe_doc = {
        "title": title,
        "slug": slug,
        "description": description,
        "ingredients": ingredients,
        "steps": steps,
        "notes": notes,
        "tags": tags,
        "author_id": ObjectId(user["sub"]),
        "author_username": user["username"],
        "filename": filename,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    db.recipes.insert_one(recipe_doc)

    # Rebuild RAG index so the new recipe is searchable immediately
    rag.rebuild_index()

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
    db = get_db()
    recipe = db.recipes.find_one({"slug": slug})
    if not recipe:
        abort(404)
    md_path = _safe_path(recipe["filename"])
    raw_md = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    html_content = _render_md(raw_md)
    recipe["_id"] = str(recipe["_id"])
    recipe["author_id"] = str(recipe["author_id"])
    user = get_current_user()
    is_author = user and user["sub"] == recipe["author_id"]
    return render_template(
        "recipes/detail.html",
        recipe=recipe,
        html_content=html_content,
        is_author=is_author,
    )


@recipes_bp.route("/<slug>/edit")
@login_required
def edit_recipe(slug):
    db = get_db()
    recipe = db.recipes.find_one({"slug": slug})
    if not recipe:
        abort(404)
    recipe["_id"] = str(recipe["_id"])
    recipe["author_id"] = str(recipe["author_id"])
    return render_template("recipes/form.html", recipe=recipe, action="edit")


@recipes_bp.route("/<slug>", methods=["PUT"])
@login_required
def update_recipe(slug):
    db = get_db()
    recipe = db.recipes.find_one({"slug": slug})
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
    _safe_path(recipe["filename"]).write_text(md_content, encoding="utf-8")

    db.recipes.update_one(
        {"slug": slug},
        {
            "$set": {
                "title": title,
                "description": description,
                "ingredients": ingredients,
                "steps": steps,
                "notes": notes,
                "tags": tags,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    rag.rebuild_index()
    return jsonify(
        {
            "message": "Recipe updated",
            "redirect": url_for("recipes.view_recipe", slug=slug),
        }
    )


@recipes_bp.route("/<slug>", methods=["DELETE"])
@login_required
def delete_recipe(slug):
    db = get_db()
    recipe = db.recipes.find_one({"slug": slug})
    if not recipe:
        return jsonify({"error": "Recipe not found"}), 404

    md_path = _safe_path(recipe["filename"])
    if md_path.exists():
        md_path.unlink()

    db.recipes.delete_one({"slug": slug})
    rag.rebuild_index()
    return jsonify(
        {"message": "Recipe deleted", "redirect": url_for("recipes.list_recipes")}
    )


# ── API: list recipes (for chat quick-picks) ──────────────────────────────────


@recipes_bp.route("/api/list")
@login_required
def api_list():
    db = get_db()
    recipes = list(
        db.recipes.find({}, {"title": 1, "slug": 1, "tags": 1, "ingredients": 1}).sort(
            "title", 1
        )
    )
    for r in recipes:
        r["_id"] = str(r["_id"])
    return jsonify(recipes)


# ── Save AI-generated recipe from chat ────────────────────────────────────────


@recipes_bp.route("/from-chat", methods=["POST"])
@login_required
def recipe_from_chat():
    """
    Save a recipe generated by Chef AI directly from the chat interface.
    The recipe is attributed to 'Chef AI' as author, but owned by the current user
    for edit/delete permission purposes.
    """
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

    slug = _slugify(title)
    db = get_db()
    base_slug, counter = slug, 1
    while db.recipes.find_one({"slug": slug}):
        slug = f"{base_slug}-{counter}"
        counter += 1

    md_filename = f"{slug}.md"
    md_content = _recipe_to_md(title, description, ingredients, steps, notes, tags)
    _safe_path(md_filename).write_text(md_content, encoding="utf-8")

    recipe_doc = {
        "title": title,
        "slug": slug,
        "description": description,
        "ingredients": ingredients,
        "steps": steps,
        "notes": notes,
        "tags": tags,
        # Owned by the user who clicked Save, but displayed as Chef AI
        "author_id": ObjectId(user["sub"]),
        "author_username": "Chef AI",
        "filename": md_filename,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    db.recipes.insert_one(recipe_doc)
    rag.rebuild_index()

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
    db = get_db()
    user_oid = ObjectId(user["sub"])
    user_doc = db.users.find_one({"_id": user_oid}, {"favorites": 1})
    favorites = set(user_doc.get("favorites") or [])
    if slug in favorites:
        db.users.update_one({"_id": user_oid}, {"$pull": {"favorites": slug}})
        return jsonify({"favorited": False})
    db.users.update_one({"_id": user_oid}, {"$addToSet": {"favorites": slug}})
    return jsonify({"favorited": True})


# ── Upload recipe from PDF / TXT ──────────────────────────────────────────────

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
    ext = Path(filename).suffix.lower()

    if ext not in _ALLOWED_EXTENSIONS:
        return render_template(
            "recipes/upload.html", error="Only .pdf and .txt files are supported."
        )

    file_bytes = file.read()
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        return render_template(
            "recipes/upload.html", error="File is too large (max 10 MB)."
        )

    # ── Extract raw text ──────────────────────────────────────────────────────
    if ext == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return render_template(
                "recipes/upload.html",
                error="Could not read the PDF. Make sure it contains selectable text (not a scanned image).",
            )
    else:
        raw_text = file_bytes.decode("utf-8", errors="replace")

    if not raw_text.strip():
        return render_template(
            "recipes/upload.html", error="No text could be extracted from the file."
        )

    # ── Ask Gemini to structure the recipe ───────────────────────────────────
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

    # ── Save (same flow as create_recipe) ────────────────────────────────────
    slug = _slugify(title)
    db = get_db()
    base_slug, counter = slug, 1
    while db.recipes.find_one({"slug": slug}):
        slug = f"{base_slug}-{counter}"
        counter += 1

    md_filename = f"{slug}.md"
    md_content = _recipe_to_md(title, description, ingredients, steps, notes, tags)
    _safe_path(md_filename).write_text(md_content, encoding="utf-8")

    recipe_doc = {
        "title": title,
        "slug": slug,
        "description": description,
        "ingredients": ingredients,
        "steps": steps,
        "notes": notes,
        "tags": tags,
        "author_id": ObjectId(user["sub"]),
        "author_username": user["username"],
        "filename": md_filename,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    db.recipes.insert_one(recipe_doc)
    rag.rebuild_index()

    return redirect(url_for("recipes.view_recipe", slug=slug))
