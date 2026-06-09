"""Build saveable recipe JSON from Chef AI answers (fences, tags, markdown, or S3 catalog).

Chef AI (the Bedrock agent) is inconsistent about how it returns a brand-new recipe:
  * ```recipe-json ... ```           (the documented fence)
  * <recipe-json> ... </recipe-json> (XML-style tags it actually emits)
  * key "name" instead of "title"
  * all steps crammed into a single string ("1. ... 2. ...")
Catalog recipes come back as readable markdown with plain "Ingredients:" / "Steps:"
labels (no JSON at all) and are matched via the resolved S3 slug.

This module normalizes every shape into the dict that /recipes/from-chat expects and
renders clean markdown for display so the user never sees raw JSON.
"""

from __future__ import annotations

import json
import re

from services import recipe_lookup, s3_recipes

# Matches ```recipe-json ...```, ```json ...```, or <recipe-json>...</recipe-json>.
_RECIPE_BLOCK_RE = re.compile(
    r"```(?:recipe-json|json)\s*\n?([\s\S]*?)```"
    r"|<recipe-json>\s*([\s\S]*?)</recipe-json>",
    re.IGNORECASE,
)
_AUTHORITY_PREFIX_RE = re.compile(
    r"^\[Authoritative cookbook entry[^\]]*\]\s*\n?", re.IGNORECASE
)
# Section headings: "## Ingredients", "**Ingredients:**", or plain "Ingredients:".
_SECTION_HEADING_RE = re.compile(
    r"^\s*(?:#{1,3}\s+)?\*{0,2}\s*"
    r"(Ingredients|Steps|Instructions|Directions|Description|Notes)"
    r"\s*:?\s*\*{0,2}\s*:?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
# Derive a recipe name from intro prose when there is no explicit title heading.
# Articles must be whole words (a|an|the|new + whitespace) so we never eat the
# leading letter of a real name (e.g. the "A" in "Avocado").
_INTRO_TITLE_RES = (
    re.compile(r"recipe\s+for\s+(?:(?:a|an|the)\s+)?([^\n:.,!?]{2,60})", re.IGNORECASE),
    re.compile(
        r"here(?:'s| is)\s+(?:a\s+)?(?:new\s+)?([^\n:.,!?]{2,60}?)\s+recipe",
        re.IGNORECASE,
    ),
)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+)$", re.MULTILINE)
_NUMBERED_STEP_RE = re.compile(r"^\s*\d+[.)]\s+(.+)$", re.MULTILINE)
_INLINE_STEP_SPLIT_RE = re.compile(r"(?:(?<=[.!?])\s+|\s+)(?=\d+[.)]\s)")
_SECTION_ALIASES = {
    "instructions": "steps",
    "directions": "steps",
}


def _is_valid_recipe_data(data: dict | None) -> bool:
    if not data or not isinstance(data, dict):
        return False
    title = str(data.get("title") or "").strip()
    ingredients = data.get("ingredients") or []
    steps = data.get("steps") or []
    return (
        bool(title)
        and isinstance(ingredients, list)
        and len(ingredients) > 0
        and isinstance(steps, list)
        and len(steps) > 0
    )


def _normalize_steps(raw) -> list[str]:
    """Accept a list or string of steps; split single crammed strings into items."""
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, list):
        items = [str(item) for item in raw]
    else:
        return []

    steps: list[str] = []
    for item in items:
        item = str(item).strip()
        if not item:
            continue
        # A single element like "1. Do this. 2. Do that. 3. Done." -> split it.
        if len(re.findall(r"\b\d+[.)]\s", item)) >= 2:
            for part in _INLINE_STEP_SPLIT_RE.split(item):
                part = re.sub(r"^\s*\d+[.)]\s*", "", part.strip())
                if part:
                    steps.append(part)
        else:
            steps.append(re.sub(r"^\s*\d+[.)]\s*", "", item))
    return steps


def _normalize_list(raw) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _normalize_recipe_data(data: dict) -> dict:
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    title = data.get("title") or data.get("name") or ""
    return {
        "title": str(title).strip(),
        "description": str(data.get("description") or "").strip(),
        "ingredients": _normalize_list(data.get("ingredients")),
        "steps": _normalize_steps(data.get("steps")),
        "notes": str(data.get("notes") or "").strip(),
        "tags": [str(tag).strip().lower() for tag in tags if str(tag).strip()],
    }


def _find_recipe_block(text: str) -> tuple[dict, int, int] | None:
    """Return (recipe_data, start, end) for the first valid embedded JSON block."""
    for match in _RECIPE_BLOCK_RE.finditer(text or ""):
        raw = (match.group(1) or match.group(2) or "").strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        data = _normalize_recipe_data(parsed)
        if _is_valid_recipe_data(data):
            return data, match.start(), match.end()
    return None


def _split_markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(_SECTION_HEADING_RE.finditer(text))
    for idx, match in enumerate(matches):
        name = match.group(1).lower()
        name = _SECTION_ALIASES.get(name, name)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip()
    return sections


def _parse_bullet_items(section: str) -> list[str]:
    items = [m.group(1).strip() for m in _BULLET_RE.finditer(section)]
    if items:
        return items
    inline = section.strip()
    if " - " in inline:
        return [part.strip() for part in re.split(r"\s+-\s+", inline) if part.strip()]
    return [line.strip() for line in inline.splitlines() if line.strip()]


def _parse_numbered_steps(section: str) -> list[str]:
    return _normalize_steps(
        [m.group(1).strip() for m in _NUMBERED_STEP_RE.finditer(section)]
        or [section.strip()]
    )


_SECTION_WORDS = {
    "ingredients", "steps", "instructions", "directions", "description", "notes",
}


def _parse_title(text: str) -> str:
    cleaned = _AUTHORITY_PREFIX_RE.sub("", text or "").strip()
    title = s3_recipes.parse_title(cleaned)
    if title and not title.isdigit() and "**Tags:**" not in title:
        return title
    for match in re.finditer(r"^#{1,3}\s+(.+?)\s*$", cleaned, re.MULTILINE):
        candidate = match.group(1).strip()
        if candidate.lower() not in _SECTION_WORDS:
            return candidate

    # No heading — derive the name from intro prose ("...recipe for a Burger:").
    intro = cleaned.split("\n", 1)[0]
    for pattern in _INTRO_TITLE_RES:
        m = pattern.search(intro)
        if m:
            candidate = re.sub(r"^(?:a|an|the|new)\s+", "", m.group(1).strip(), flags=re.I)
            candidate = candidate.strip(" .:-")
            if candidate and candidate.lower() not in _SECTION_WORDS:
                return candidate.title()
    return ""


def markdown_to_recipe_data(text: str) -> dict | None:
    """Parse a Chef AI markdown recipe (## or plain-label sections) into recipe JSON."""
    cleaned = _AUTHORITY_PREFIX_RE.sub("", text or "").strip()
    if not cleaned:
        return None

    title = _parse_title(cleaned)
    sections = _split_markdown_sections(cleaned)
    ingredients = _parse_bullet_items(sections.get("ingredients", ""))
    steps = _parse_numbered_steps(sections.get("steps", ""))

    if not title or not ingredients or not steps:
        return None

    data = {
        "title": title,
        "description": sections.get("description", "").strip(),
        "ingredients": ingredients,
        "steps": steps,
        "notes": sections.get("notes", "").strip(),
        "tags": s3_recipes.parse_tags(cleaned),
    }
    return _normalize_recipe_data(data) if _is_valid_recipe_data(data) else None


def recipe_data_from_slug(slug: str, conn) -> dict | None:
    block = recipe_lookup.load_recipe_context(slug, conn)
    if not block:
        return None
    return markdown_to_recipe_data(block)


def render_recipe_markdown(data: dict) -> str:
    """Render a recipe dict into clean, displayable markdown."""
    lines = [f"## {data['title']}"]
    if data.get("description"):
        lines += ["", data["description"]]
    if data.get("tags"):
        lines += ["", f"**Tags:** {', '.join(data['tags'])}"]
    lines += ["", "## Ingredients", ""]
    lines += [f"- {item}" for item in data["ingredients"]]
    lines += ["", "## Steps", ""]
    lines += [f"{num}. {step}" for num, step in enumerate(data["steps"], 1)]
    if data.get("notes"):
        lines += ["", "## Notes", "", data["notes"]]
    return "\n".join(lines)


def looks_like_full_recipe_answer(text: str) -> bool:
    lower = (text or "").lower()
    if "ingredient" not in lower:
        return False
    if "step" in lower or "instruction" in lower or "direction" in lower:
        return True
    return bool(_NUMBERED_STEP_RE.search(text))


def _title_in_text(title: str, text: str) -> bool:
    if not title:
        return False
    norm_title = re.sub(r"[\s\-]+", " ", title.lower()).strip()
    norm_text = re.sub(r"[\s\-]+", " ", (text or "").lower())
    return norm_title in norm_text


def _slug_for_answer(answer: str, active_slugs: list[str], conn) -> str | None:
    """
    Pick the catalog slug that matches the recipe actually shown in the answer.

    Critical: never blindly trust active_slugs (derived from the question), because
    "the first one" can resolve to the wrong suggestion. The added recipe must be the
    one the user is reading, so we match against the answer text first.
    """
    detected = recipe_lookup.detect_recipe_slugs(answer, conn, max_results=5)

    # Prefer a slug the question pointed at *only if* it also appears in the answer.
    for slug in active_slugs or []:
        if slug in detected:
            return slug

    if detected:
        return detected[0]

    # Hyphen/space-insensitive scan: the displayed title may use spaces where the
    # catalog title uses hyphens (e.g. "Ceviche Estillo" vs "Ceviche-Estillo").
    # build_title_index is sorted longest-title-first, so the first hit is the best.
    norm_answer = re.sub(r"[\s\-]+", " ", (answer or "").lower())
    for title, slug, _key in recipe_lookup.build_title_index(conn):
        norm_title = re.sub(r"[\s\-]+", " ", title.lower()).strip()
        if len(norm_title) >= 6 and norm_title in norm_answer:
            return slug

    # Last resort: an active slug whose title literally appears in the answer.
    for slug in active_slugs or []:
        data = recipe_data_from_slug(slug, conn)
        if data and _title_in_text(data["title"], answer):
            return slug
    return None


def process_answer(answer: str, active_slugs: list[str], conn) -> tuple[str, dict | None]:
    """
    Return (display_answer, recipe_or_None).

    * If the agent embedded a recipe-json block (fence or <recipe-json> tag), replace
      that raw block with rendered markdown so the user sees a clean recipe.
    * Otherwise resolve the recipe from the answer's own content (catalog match or
      parsed markdown), so the saved recipe always matches what is displayed.
    """
    answer = answer or ""

    block = _find_recipe_block(answer)
    if block:
        data, start, end = block
        rendered = render_recipe_markdown(data)
        display = (answer[:start].rstrip() + "\n\n" + rendered + "\n" + answer[end:].lstrip()).strip()
        return display, data

    if not looks_like_full_recipe_answer(answer):
        return answer, None

    # Identity comes from the answer, not the question-derived active_slugs.
    slug = _slug_for_answer(answer, active_slugs, conn)
    if slug:
        data = recipe_data_from_slug(slug, conn)
        if data and _title_in_text(data["title"], answer):
            return answer, data

    parsed = markdown_to_recipe_data(answer)
    if parsed:
        return answer, parsed

    return answer, None


def resolve_saveable_recipe(answer: str, active_slugs: list[str], conn) -> dict | None:
    """Backwards-compatible helper returning only the recipe dict."""
    _display, recipe = process_answer(answer, active_slugs, conn)
    return recipe
