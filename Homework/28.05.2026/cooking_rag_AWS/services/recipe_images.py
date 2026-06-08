"""Recipe image generation (Gemini), S3 storage, and URL resolution."""

from __future__ import annotations

import logging
import re
import threading
from typing import TypedDict

import boto3
from google import genai

from config import Config
from db import _checkout, _get_pool
from services import s3_recipes

logger = logging.getLogger(__name__)

_IMAGE_PREFIX = "catalog/images/"
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)

_s3_client = None


class ImageState(TypedDict):
    image_url: str | None
    status: str
    cleared: bool


def _s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=Config.AWS_REGION)
    return _s3_client


def image_s3_key(slug: str, ext: str = "png") -> str:
    return f"{Config.S3_RECIPES_PREFIX}{_IMAGE_PREFIX}{slug}.{ext}"


def public_url(s3_key: str) -> str:
    return f"https://{Config.S3_BUCKET}.s3.{Config.AWS_REGION}.amazonaws.com/{s3_key}"


def _load_all_image_rows(conn) -> dict[str, dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT slug, image_url, image_s3_key, status, cleared
            FROM recipe_images
            """
        )
        return {row["slug"]: dict(row) for row in cur.fetchall()}


def _load_image_row(conn, slug: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT slug, image_url, image_s3_key, status, cleared
            FROM recipe_images WHERE slug = %s
            """,
            (slug,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def resolve_image(
    slug: str,
    manifest_item: dict | None = None,
    image_row: dict | None = None,
) -> ImageState:
    row = image_row or {}
    if row.get("cleared"):
        return {"image_url": None, "status": "", "cleared": True}

    url = (row.get("image_url") or "").strip()
    status = (row.get("status") or "").strip()
    if url and not row.get("cleared"):
        return {"image_url": url, "status": status or "ready", "cleared": False}

    if status == "pending":
        return {"image_url": None, "status": "pending", "cleared": False}

    manifest = manifest_item or {}
    manifest_url = (manifest.get("image_url") or "").strip()
    if manifest_url:
        return {"image_url": manifest_url, "status": "ready", "cleared": False}

    return {"image_url": None, "status": status, "cleared": False}


def resolve_image_url(slug: str, conn, manifest: dict | None = None) -> str | None:
    manifest_lookup = manifest if manifest is not None else s3_recipes._load_catalog_manifest()
    row = _load_image_row(conn, slug)
    state = resolve_image(slug, manifest_lookup.get(slug), row)
    return state["image_url"]


def resolve_image_state(slug: str, conn) -> ImageState:
    manifest = s3_recipes._load_catalog_manifest()
    row = _load_image_row(conn, slug)
    return resolve_image(slug, manifest.get(slug), row)


def load_image_rows(conn) -> dict[str, dict]:
    return _load_all_image_rows(conn)


def set_pending(conn, slug: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO recipe_images (slug, image_url, image_s3_key, status, cleared, updated_at)
            VALUES (%s, '', '', 'pending', FALSE, NOW())
            ON CONFLICT (slug) DO UPDATE SET
                status = 'pending',
                cleared = FALSE,
                updated_at = NOW()
            """,
            (slug,),
        )
    conn.commit()


def save_image(
    conn,
    slug: str,
    image_url: str,
    image_s3_key: str = "",
    status: str = "ready",
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO recipe_images (slug, image_url, image_s3_key, status, cleared, updated_at)
            VALUES (%s, %s, %s, %s, FALSE, NOW())
            ON CONFLICT (slug) DO UPDATE SET
                image_url = EXCLUDED.image_url,
                image_s3_key = EXCLUDED.image_s3_key,
                status = EXCLUDED.status,
                cleared = FALSE,
                updated_at = NOW()
            """,
            (slug, image_url, image_s3_key, status),
        )
    conn.commit()


def mark_failed(conn, slug: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO recipe_images (slug, image_url, image_s3_key, status, cleared, updated_at)
            VALUES (%s, '', '', 'failed', FALSE, NOW())
            ON CONFLICT (slug) DO UPDATE SET
                status = 'failed',
                updated_at = NOW()
            """,
            (slug,),
        )
    conn.commit()


def _delete_s3_key(s3_key: str) -> None:
    if not s3_key or not Config.S3_BUCKET:
        return
    try:
        _s3().delete_object(Bucket=Config.S3_BUCKET, Key=s3_key)
    except Exception as exc:
        logger.warning("Failed to delete S3 image %s: %s", s3_key, exc)


def clear_image(conn, slug: str) -> None:
    row = _load_image_row(conn, slug)
    if row and row.get("image_s3_key"):
        _delete_s3_key(row["image_s3_key"])

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO recipe_images (slug, image_url, image_s3_key, status, cleared, updated_at)
            VALUES (%s, '', '', '', TRUE, NOW())
            ON CONFLICT (slug) DO UPDATE SET
                image_url = '',
                image_s3_key = '',
                status = '',
                cleared = TRUE,
                updated_at = NOW()
            """,
            (slug,),
        )
    conn.commit()
    s3_recipes.invalidate_index_cache()


def validate_image_url(url: str) -> str | None:
    url = (url or "").strip()
    if not url or not _URL_RE.match(url):
        return None
    if len(url) > 1000:
        return None
    return url


def upload_image_bytes(slug: str, data: bytes, content_type: str, ext: str) -> tuple[str, str]:
    key = image_s3_key(slug, ext)
    put_args = {
        "Bucket": Config.S3_BUCKET,
        "Key": key,
        "Body": data,
        "ContentType": content_type,
        "CacheControl": "public, max-age=31536000",
    }
    try:
        _s3().put_object(**put_args, ACL="public-read")
    except Exception:
        _s3().put_object(**put_args)
    return key, public_url(key)


def generate_image(title: str, instructions: str = "") -> tuple[bytes, str, str]:
    """Return (image_bytes, content_type, file_extension)."""
    if not Config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=Config.GEMINI_API_KEY)
    prompt = (
        f"A relaxed, realistic food photograph of {title}. "
        "Natural lighting, appetizing presentation on a simple plate or bowl, "
        "shallow depth of field, no text, no watermarks, no people."
    )
    extra = (instructions or "").strip()
    if extra:
        prompt = f"{prompt} Additional styling notes from the cook: {extra}"
    response = client.models.generate_content(
        model=Config.GEMINI_MODEL,
        contents=[prompt],
    )

    for part in response.parts:
        inline = part.inline_data
        if inline is not None and inline.data:
            mime = inline.mime_type or "image/png"
            ext = "jpg" if "jpeg" in mime else "png"
            return inline.data, mime, ext

    raise RuntimeError("Gemini returned no image data")


def _run_generation(slug: str, title: str, instructions: str = "") -> None:
    conn = _checkout()
    try:
        image_bytes, content_type, ext = generate_image(title, instructions)
        s3_key, url = upload_image_bytes(slug, image_bytes, content_type, ext)
        save_image(conn, slug, url, s3_key, "ready")
        s3_recipes.invalidate_index_cache()
        logger.info("Generated recipe image for %s", slug)
    except Exception as exc:
        logger.exception("Recipe image generation failed for %s: %s", slug, exc)
        try:
            mark_failed(conn, slug)
        except Exception:
            pass
    finally:
        _get_pool().putconn(conn)


def schedule_generation(slug: str, title: str, instructions: str = "") -> None:
    if not Config.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — skipping image generation for %s", slug)
        return

    thread = threading.Thread(
        target=_run_generation,
        args=(slug, title, instructions),
        daemon=True,
        name=f"recipe-image-{slug}",
    )
    thread.start()


def trigger_generation_after_create(conn, slug: str, title: str) -> None:
    if not Config.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — skipping image generation for %s", slug)
        return
    set_pending(conn, slug)
    schedule_generation(slug, title)


def trigger_manual_generation(
    conn, slug: str, title: str, instructions: str = ""
) -> None:
    if not Config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    row = _load_image_row(conn, slug)
    if row and row.get("image_s3_key"):
        _delete_s3_key(row["image_s3_key"])

    set_pending(conn, slug)
    schedule_generation(slug, title, instructions.strip())


def set_external_url(conn, slug: str, url: str) -> None:
    row = _load_image_row(conn, slug)
    if row and row.get("image_s3_key"):
        _delete_s3_key(row["image_s3_key"])
    save_image(conn, slug, url, "", "ready")
    s3_recipes.invalidate_index_cache()


def upload_user_image(conn, slug: str, file_bytes: bytes, content_type: str, ext: str) -> str:
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise ValueError("Image is too large (max 5 MB)")

    row = _load_image_row(conn, slug)
    if row and row.get("image_s3_key"):
        _delete_s3_key(row["image_s3_key"])

    s3_key, url = upload_image_bytes(slug, file_bytes, content_type, ext)
    save_image(conn, slug, url, s3_key, "ready")
    s3_recipes.invalidate_index_cache()
    return url


def delete_recipe_image(conn, slug: str) -> None:
    clear_image(conn, slug)


def cleanup_on_recipe_delete(conn, slug: str) -> None:
    row = _load_image_row(conn, slug)
    if row and row.get("image_s3_key"):
        _delete_s3_key(row["image_s3_key"])
    with conn.cursor() as cur:
        cur.execute("DELETE FROM recipe_images WHERE slug = %s", (slug,))
    conn.commit()
    s3_recipes.invalidate_index_cache()
