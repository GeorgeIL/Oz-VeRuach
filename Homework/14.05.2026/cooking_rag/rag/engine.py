"""
RAG engine for the Smart Cookbook.

Responsibilities:
- Load recipe .md (and .txt) files from the data folder
- Embed texts via HuggingFace Inference API
- Build / query a FAISS index for recipe retrieval
- Maintain a module-level index so it persists across requests
- Call Gemini with recipe context + conversation history
- Provide helpers for per-message embedding (MongoDB vector store)
"""

import re
import time
import faiss
import numpy as np
import nltk
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
from huggingface_hub import InferenceClient

from config import Config

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Chef AI, a knowledgeable and warm culinary assistant for a smart cookbook app.

Your capabilities:
- Help users find recipes based on ingredients they currently have at home
- Suggest practical ingredient substitutions when something is missing
- Explain cooking techniques, methods, and food science
- Recommend recipes based on dietary needs, cuisine type, or occasion
- Answer questions about food storage, nutrition, and kitchen tips

Guidelines:
- Be encouraging and enthusiastic about cooking
- Reference specific recipes from the cookbook when relevant
- Always suggest substitutions when asked - be creative and practical
- If a user lists their pantry items, tailor recommendations to those ingredients
- Format lists and steps clearly using markdown (bold headings, bullet points, numbered steps)
- Mention estimated cooking times and difficulty when helpful
- Be concise but thorough; avoid unnecessary filler

New Recipe Format:
When you create a BRAND NEW recipe from scratch (not referencing an existing cookbook recipe),
always append the following data block at the very end of your response.
Replace all values with the actual recipe content.

```recipe-json
{"title": "Recipe Name", "description": "One sentence description", "ingredients": ["quantity ingredient", "quantity ingredient"], "steps": ["First instruction", "Second instruction"], "notes": "Optional tips, or empty string", "tags": ["tag1", "tag2"]}
```

Rules for the recipe-json block:
- Include it ONLY when you are providing a complete recipe with a title, ingredients list, and numbered steps.
- Do NOT include it for substitution tips, general cooking advice, or when referencing an existing cookbook recipe.
- The JSON must be on a single line with no line breaks inside.
- All array values must be plain strings (no nested objects)."""


# ── Lazy clients ──────────────────────────────────────────────────────────────

_gemini_client: Optional[genai.Client] = None
_hf_client: Optional[InferenceClient] = None


def _get_clients() -> tuple[genai.Client, InferenceClient]:
    """
    Return the shared Gemini and HuggingFace clients, creating them on first call.
    Raises RuntimeError if required API keys are missing from the environment.
    """
    global _gemini_client, _hf_client
    if _gemini_client is None:
        if not Config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set in the environment.")
        if not Config.HF_TOKEN:
            raise RuntimeError("HF_TOKEN is not set in the environment.")
        _gemini_client = genai.Client(api_key=Config.GEMINI_API_KEY)
        _hf_client = InferenceClient(provider="hf-inference", api_key=Config.HF_TOKEN)
    return _gemini_client, _hf_client


# ── Module-level FAISS index (rebuilt on demand) ──────────────────────────────

_chunks: list[str] = []
_index: Optional[faiss.Index] = None
_index_error: Optional[str] = None


def get_index_state() -> tuple[list[str], Optional[faiss.Index], Optional[str]]:
    """Return the current FAISS index state as (chunks list, index object, error string)."""
    return _chunks, _index, _index_error


def rebuild_index(folder: Optional[Path] = None) -> int:
    """Load recipe files, embed them, build FAISS index. Returns chunk count."""
    global _chunks, _index, _index_error
    try:
        _chunks = load_recipe_documents(folder)
        if not _chunks:
            _index = None
            _index_error = "No recipe files found in the data folder."
            return 0
        embeddings = embed_texts(_chunks)
        _index = build_faiss_index(embeddings)
        _index_error = None
        return len(_chunks)
    except Exception as exc:
        _index_error = str(exc)
        _index = None
        return 0


# ── Document loading ──────────────────────────────────────────────────────────


def _ensure_nltk():
    """Download required NLTK tokenizer data packages if not already present on disk."""
    for pkg in ("punkt", "punkt_tab"):
        nltk.download(pkg, quiet=True)


def load_recipe_documents(folder: Optional[Path] = None) -> list[str]:
    """
    Load .md and .txt recipe files and split into meaningful chunks.
    Markdown files are split by section (## headings).
    Text files are split into sentences.
    """
    folder = Path(folder or Config.DATA_FOLDER)
    _ensure_nltk()

    chunks: list[str] = []

    for file_path in sorted(folder.glob("*.md")):
        text = file_path.read_text(encoding="utf-8")
        # Include filename as context prefix for the first chunk
        file_label = f"[Recipe: {file_path.stem.replace('-', ' ').title()}]\n"
        # Split the file at every line that begins with a markdown heading (# / ## / ###).
        # The lookahead (?=#{1,3}\s) finds the position just before the '#' without consuming it,
        # so each heading character stays at the start of its own chunk.
        sections = re.split(r"\n(?=#{1,3}\s)", text)
        for i, section in enumerate(sections):
            section = section.strip()
            if section:
                prefix = file_label if i == 0 else ""
                chunks.append(prefix + section)

    for file_path in sorted(folder.glob("*.txt")):
        from nltk.tokenize import sent_tokenize

        text = file_path.read_text(encoding="utf-8")
        for sent in sent_tokenize(text):
            sent = sent.strip()
            if sent:
                chunks.append(sent)

    return chunks


# ── Embedding ─────────────────────────────────────────────────────────────────


def _normalize_embedding(output) -> np.ndarray:
    """
    Convert raw HuggingFace API output into a 2-D float32 array of shape (num_texts, embedding_dim).
    The API can return 1-D, 2-D, or 3-D tensors depending on model and batch size - this normalizes all cases.
    """
    arr = np.array(output, dtype="float32")
    if arr.ndim == 1:
        # Single embedding returned as a flat vector - wrap it into a (1, dim) matrix
        arr = arr[np.newaxis, :]
    elif arr.ndim == 3:
        # Token-level embeddings (batch, tokens, dim) - average across the token axis to get sentence embeddings
        arr = arr.mean(axis=1)
    return arr.astype("float32")


def embed_texts(texts: list[str], batch_size: Optional[int] = None) -> np.ndarray:
    """Embed a list of texts using HuggingFace Inference API."""
    _, hf = _get_clients()
    batch_size = batch_size or Config.BATCH_SIZE
    all_embeddings: list[np.ndarray] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        result = hf.feature_extraction(batch, model=Config.HF_EMBEDDING_MODEL)
        embeddings = _normalize_embedding(result)

        if embeddings.shape[0] != len(batch):
            # The API returned fewer vectors than texts - fall back to embedding one at a time
            fixed: list[np.ndarray] = []
            for text in batch:
                r = hf.feature_extraction(text, model=Config.HF_EMBEDDING_MODEL)
                e = _normalize_embedding(r)
                if e.ndim == 2 and e.shape[0] > 1:
                    # If multiple rows were returned for a single text, average them into one vector
                    e = e.mean(axis=0, keepdims=True)
                fixed.append(e)
                # Small pause to avoid hitting the HuggingFace rate limit
                time.sleep(0.05)
            embeddings = np.vstack(fixed)

        all_embeddings.append(embeddings)

    return np.vstack(all_embeddings).astype("float32")


def embed_single(text: str) -> list[float]:
    """Embed one text and return as a plain Python list (for MongoDB storage)."""
    arr = embed_texts([text])
    return arr[0].tolist()


# ── FAISS ─────────────────────────────────────────────────────────────────────


def build_faiss_index(embeddings: np.ndarray) -> faiss.Index:
    """
    Build an in-memory FAISS index from a 2-D float32 embeddings matrix.
    Uses IndexFlatL2 (exact brute-force L2 distance search) - accurate and fast for hundreds of chunks.
    """
    # Read the vector dimension from the number of columns in the embeddings matrix
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    return index


def retrieve_chunks(
    question: str,
    top_k: Optional[int] = None,
    embedding: Optional[list[float]] = None,
) -> list[str]:
    """Retrieve the most relevant recipe chunks for a query.

    If *embedding* is provided (a pre-computed question vector), it is used
    directly and no extra HuggingFace API call is made.
    """
    top_k = top_k or Config.TOP_K
    if _index is None or not _chunks:
        return []
    if embedding is not None:
        q_emb = np.array([embedding], dtype="float32")
    else:
        q_emb = embed_texts([question])
    # Search the FAISS index for the top_k nearest vectors; returns distances (unused) and integer positions
    _, indices = _index.search(q_emb, min(top_k, len(_chunks)))
    # Map each returned position back to its original text chunk, guarding against out-of-range indices
    return [_chunks[i] for i in indices[0] if 0 <= i < len(_chunks)]


# ── Cosine similarity (for MongoDB conversation vector search) ────────────────


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between two embedding vectors.
    Returns a value from -1 (opposite direction) to 1 (identical direction).
    Used to rank past chat messages by semantic closeness to the current question.
    """
    va = np.array(a, dtype="float32")
    vb = np.array(b, dtype="float32")
    # Magnitude product: the denominator of the cosine similarity formula
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom < 1e-9:
        # Avoid division by zero when either vector is all zeros
        return 0.0
    # Dot product divided by the product of magnitudes gives the cosine of the angle between vectors
    return float(np.dot(va, vb) / denom)


def find_relevant_history(
    messages: list[dict],
    question_embedding: list[float],
    top_n: int = 3,
) -> list[dict]:
    """
    Find the most semantically similar past user messages using cosine similarity.
    Only considers messages that have stored embeddings.
    """
    scored: list[tuple[float, dict]] = []
    for msg in messages:
        emb = msg.get("embedding")
        if emb and msg.get("role") == "user":
            sim = cosine_similarity(question_embedding, emb)
            scored.append((sim, msg))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [msg for _, msg in scored[:top_n]]


# ── Gemini generation ─────────────────────────────────────────────────────────


def ask_chef(
    question: str,
    context_chunks: list[str],
    recent_history: list[dict],
    pantry: list[str] | None = None,
) -> str:
    """
    Call Gemini with:
    - A cookbook-focused system prompt
    - Retrieved recipe context
    - Recent conversation history (each message truncated to keep tokens low)
    - Optional user pantry
    Retries up to 2 times on transient 503 errors before raising.
    """
    gemini, _ = _get_clients()

    # Build system instruction
    system_parts = [SYSTEM_PROMPT]
    if pantry:
        system_parts.append(
            f"\nThe user's current pantry contains: {', '.join(pantry)}. "
            "Prioritise recipes they can make with these ingredients."
        )
    system_text = "\n".join(system_parts)

    # Build Gemini history - truncate long messages to keep token count low.
    _MAX_HISTORY_CHARS = 200
    history: list[types.Content] = []
    for msg in recent_history:
        role = "user" if msg["role"] == "user" else "model"
        content = msg["content"]
        if len(content) > _MAX_HISTORY_CHARS:
            content = content[:_MAX_HISTORY_CHARS] + "…"
        history.append(types.Content(role=role, parts=[types.Part(text=content)]))

    # Cap each individual chunk so one long recipe file can't dominate the prompt.
    _MAX_CHUNK_CHARS = 400
    capped_chunks = [
        (c[:_MAX_CHUNK_CHARS] + "…" if len(c) > _MAX_CHUNK_CHARS else c)
        for c in context_chunks
    ]

    # Build current user message with retrieved context
    has_context = bool(capped_chunks)
    context_text = "\n---\n".join(capped_chunks) if has_context else "(none)"
    no_context_note = (
        ""
        if has_context
        else "\n\nNo saved recipes matched. Answer from general culinary knowledge."
    )
    user_message = (
        f"Context:\n{context_text}\n\n" f"Question: {question}" f"{no_context_note}"
    )

    # Retry up to 2 extra times on transient 503 overload errors before failing.
    # 503s from Gemini are almost always short-lived capacity blips.
    _MAX_RETRIES = 2
    _RETRY_DELAY = 2.5  # seconds; doubles each attempt (2.5s, then 5s)
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            chat = gemini.chats.create(
                model=Config.GEMINI_MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=system_text,
                    temperature=0.7,
                    # Disable extended thinking - gemini-2.5-flash thinks by
                    # default (up to 8192 tokens of internal reasoning per
                    # request), consuming ~10x compute on the free tier and
                    # causing 503 overload errors. A cooking assistant needs
                    # fast practical answers, not deep reasoning.
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
                history=history,
            )
            response = chat.send_message(user_message)
            return response.text
        except Exception as exc:
            err_str = str(exc)
            is_transient = "503" in err_str or "UNAVAILABLE" in err_str
            if is_transient and attempt < _MAX_RETRIES:
                last_exc = exc
                time.sleep(_RETRY_DELAY * (attempt + 1))
                continue
            raise
    raise last_exc  # type: ignore[misc]


# ── Recipe extraction from raw text (PDF / TXT upload) ───────────────────────


def parse_recipe_from_text(raw_text: str) -> dict:
    """
    Use Gemini to extract structured recipe data from raw text.
    Returns a dict with keys: title, description, ingredients, steps, notes, tags.
    Raises ValueError if the response is not valid JSON.
    """
    import json

    gemini, _ = _get_clients()

    prompt = (
        "Extract the recipe from the text below and return ONLY a valid JSON object "
        "with these exact keys:\n"
        '- "title": string\n'
        '- "description": string (1-2 sentence summary, may be empty)\n'
        '- "ingredients": array of strings (one ingredient per item, include quantities)\n'
        '- "steps": array of strings (one clear instruction per item)\n'
        '- "notes": string (tips, variations, storage - may be empty)\n'
        '- "tags": array of lowercase strings, max 5 (e.g. ["italian","vegetarian"])\n\n'
        "Return ONLY the JSON object - no markdown fences, no explanation.\n\n"
        f"Recipe text:\n{raw_text[:8000]}"
    )

    response = gemini.models.generate_content(
        model=Config.GEMINI_MODEL,
        contents=prompt,
    )
    text = response.text.strip()
    # Strip accidental markdown fences if the model adds them anyway
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini returned non-JSON response: {exc}") from exc
