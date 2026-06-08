"""Exact recipe lookup for Chef AI — manifest + RDS titles, full S3 markdown."""

from __future__ import annotations

import re

from services import s3_recipes

_FOLLOWUP_RE = re.compile(
    r"\b(this|that|the)\s+recipe\b|"
    r"tags?\s+of\b|"
    r"last\s+(question|recipe)\b|"
    r"what\s+was\s+my\b|"
    r"my\s+last\s+question\b",
    re.IGNORECASE,
)


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", str(title).strip().lower())


def _title_pattern(title: str) -> re.Pattern[str]:
    words = re.escape(_normalize_title(title))
    return re.compile(rf"\b{words}\b", re.IGNORECASE)


def build_title_index(conn) -> list[tuple[str, str, str]]:
    """Return (title, slug, s3_key) sorted by title length descending."""
    manifest = s3_recipes._load_catalog_manifest()
    entries: dict[str, tuple[str, str, str]] = {}

    for slug, item in manifest.items():
        title = (item.get("title") or s3_recipes._title_from_slug(slug)).strip()
        s3_key = item.get("s3_key") or s3_recipes.catalog_s3_key(slug)
        if title:
            entries[slug] = (title, slug, s3_key)

    with conn.cursor() as cur:
        cur.execute("SELECT slug, title, s3_key FROM recipes")
        for row in cur.fetchall():
            slug = row["slug"]
            title = (row["title"] or "").strip()
            s3_key = row.get("s3_key") or s3_recipes.catalog_s3_key(slug)
            if title:
                entries[slug] = (title, slug, s3_key)

    return sorted(entries.values(), key=lambda item: len(item[0]), reverse=True)


def detect_recipe_slugs(text: str, conn, max_results: int = 2) -> list[str]:
    """Find cookbook slugs whose titles appear in text (longest match wins)."""
    if not (text or "").strip():
        return []

    index = build_title_index(conn)
    matches: list[tuple[int, str]] = []

    for title, slug, _s3_key in index:
        if _title_pattern(title).search(text):
            matches.append((len(title), slug))

    if not matches:
        return []

    matches.sort(key=lambda item: item[0], reverse=True)
    slugs: list[str] = []
    for _length, slug in matches:
        if slug not in slugs:
            slugs.append(slug)
        if len(slugs) >= max_results:
            break
    return slugs


def is_followup_about_recipe(question: str) -> bool:
    return bool(_FOLLOWUP_RE.search(question or ""))


def last_user_message(history: list[dict]) -> str:
    for msg in reversed(history):
        if msg.get("role") == "user":
            return str(msg.get("content") or "")
    return ""


def resolve_active_recipe_slugs(
    question: str, history: list[dict], conn, max_results: int = 2
) -> list[str]:
    """Resolve which recipe(s) the user is asking about (current or follow-up)."""
    slugs = detect_recipe_slugs(question, conn, max_results=max_results)
    if slugs:
        return slugs

    if not is_followup_about_recipe(question):
        return []

    combined = " ".join(
        str(msg.get("content") or "")
        for msg in reversed(history)
        if msg.get("role") in ("user", "assistant")
    )
    return detect_recipe_slugs(combined, conn, max_results=max_results)


def load_recipe_context(slug: str, conn) -> str | None:
    """Load full recipe markdown as an authoritative context block."""
    index = build_title_index(conn)
    title = slug.replace("-", " ").title()
    s3_key = s3_recipes.catalog_s3_key(slug)

    for entry_title, entry_slug, entry_key in index:
        if entry_slug == slug:
            title = entry_title
            s3_key = entry_key
            break

    try:
        md = s3_recipes.get_recipe_content(s3_key)
    except Exception:
        return None

    parsed_title = s3_recipes.parse_title(md) or title
    return (
        f"[Authoritative cookbook entry — {parsed_title} (slug: {slug})]\n"
        f"{md.strip()}"
    )


def build_authoritative_context(slugs: list[str], conn) -> list[str]:
    blocks: list[str] = []
    for slug in slugs:
        block = load_recipe_context(slug, conn)
        if block:
            blocks.append(block)
    return blocks


def build_retrieval_query(question: str, history: list[dict], conn) -> str:
    """Expand KB retrieval query with recipe names and recent user context."""
    parts = [question.strip()]
    slugs = resolve_active_recipe_slugs(question, history, conn)
    index = build_title_index(conn)
    slug_to_title = {slug: title for title, slug, _key in index}

    for slug in slugs:
        title = slug_to_title.get(slug)
        if title:
            parts.append(title)

    prev_user = last_user_message(history)
    if prev_user and prev_user.strip() != question.strip():
        parts.append(prev_user.strip())

    return " ".join(part for part in parts if part)
