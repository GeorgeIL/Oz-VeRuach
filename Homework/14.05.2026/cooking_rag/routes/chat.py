from datetime import datetime, timezone

from bson import ObjectId  # type: ignore
from flask import Blueprint, render_template, request, jsonify

from auth_utils import get_current_user, login_required
from config import Config
from db import get_db
from rag import engine as rag

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


# ── Conversation helpers ──────────────────────────────────────────────────────


def _get_or_create_conversation(db, user_id: str) -> dict:
    conv = db.conversations.find_one({"user_id": ObjectId(user_id)})
    if conv is None:
        now = datetime.now(timezone.utc)
        doc = {
            "user_id": ObjectId(user_id),
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        result = db.conversations.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc
    return conv


# ── Routes ────────────────────────────────────────────────────────────────────


@chat_bp.route("/")
@login_required
def chat_page():
    user = get_current_user()
    db = get_db()
    conv = _get_or_create_conversation(db, user["sub"])
    # Show last 40 messages for display
    messages = conv.get("messages", [])[-40:]
    # Strip embeddings from display messages (they're large float arrays)
    display_msgs = [{"role": m["role"], "content": m["content"]} for m in messages]
    chunks, _, err = rag.get_index_state()
    return render_template(
        "chat/index.html",
        messages=display_msgs,
        index_ready=err is None and len(chunks) > 0,
        index_error=err,
        chunk_count=len(chunks),
    )


@chat_bp.route("/ask", methods=["POST"])
@login_required
def ask():
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()

    if not question:
        return jsonify({"error": "No question provided"}), 400

    db = get_db()

    # Ensure index is built
    chunks, index, index_err = rag.get_index_state()
    if index is None:
        count = rag.rebuild_index()
        chunks, index, index_err = rag.get_index_state()
        if index_err:
            return jsonify({"error": f"Index error: {index_err}"}), 503

    # Fetch user pantry
    user_doc = db.users.find_one({"_id": ObjectId(user["sub"])}, {"pantry": 1})
    pantry = user_doc.get("pantry", []) if user_doc else []

    # Get conversation
    conv = _get_or_create_conversation(db, user["sub"])
    all_messages = conv.get("messages", [])

    # Embed question for vector search on conversation history
    q_embedding: list[float] | None = None
    try:
        q_embedding = rag.embed_single(question)
    except Exception:
        pass  # Non-fatal, we just skip vector history search

    # Find semantically similar past messages (MongoDB vector search in Python)
    extra_context: list[str] = []
    if q_embedding and all_messages:
        relevant = rag.find_relevant_history(all_messages, q_embedding, top_n=2)
        if relevant:
            extra_context.append("**Relevant past conversation:**")
            for msg in relevant:
                snippet = msg["content"][:150]
                extra_context.append(f"- {msg['role'].title()}: {snippet}")

    # Retrieve recipe chunks from FAISS - reuse the embedding already computed
    # above so we only make ONE HuggingFace API call per request instead of two.
    recipe_chunks = rag.retrieve_chunks(question, Config.TOP_K, embedding=q_embedding)

    # Combine context: semantic history first, then recipe chunks
    context_chunks = extra_context + recipe_chunks

    # Recent conversation window (last N messages as Gemini history)
    recent = all_messages[-(Config.HISTORY_MESSAGES) :]

    # Call Gemini
    try:
        answer = rag.ask_chef(question, context_chunks, recent, pantry)
    except Exception as exc:
        err_str = str(exc)
        if "503" in err_str or "UNAVAILABLE" in err_str:
            friendly = "Chef AI is very busy right now, the model is experiencing high demand. Please wait a moment and try again. 🙏"
        elif (
            "429" in err_str
            or "RESOURCE_EXHAUSTED" in err_str
            or "quota" in err_str.lower()
        ):
            friendly = "Chef AI has reached its daily usage limit. Please try again in a little while. ⏳"
        elif "404" in err_str or "NOT_FOUND" in err_str:
            friendly = (
                "The AI model is currently unavailable. Please check back shortly. 🔧"
            )
        else:
            friendly = "Something went wrong on Chef AI's end. Please try again. 🔧"
        return jsonify({"error": friendly}), 500

    # Persist messages in MongoDB
    now = datetime.now(timezone.utc)
    new_msgs = [
        {
            "role": "user",
            "content": question,
            "timestamp": now,
            "embedding": q_embedding,
        },
        {"role": "assistant", "content": answer, "timestamp": now, "embedding": None},
    ]
    db.conversations.update_one(
        {"_id": conv["_id"]},
        {
            "$push": {"messages": {"$each": new_msgs}},
            "$set": {"updated_at": now},
        },
    )

    return jsonify(
        {
            "answer": answer,
            "sources": len(recipe_chunks),
        }
    )


@chat_bp.route("/clear", methods=["POST"])
@login_required
def clear_history():
    user = get_current_user()
    db = get_db()
    db.conversations.update_one(
        {"user_id": ObjectId(user["sub"])},
        {"$set": {"messages": [], "updated_at": datetime.now(timezone.utc)}},
    )
    return jsonify({"message": "Conversation history cleared"})


@chat_bp.route("/reload-index", methods=["POST"])
@login_required
def reload_index():
    count = rag.rebuild_index()
    _, _, err = rag.get_index_state()
    if err:
        return jsonify({"error": err}), 503
    return jsonify({"message": f"Index rebuilt with {count} chunks"})
