from pymongo import MongoClient, ASCENDING
from pymongo.errors import OperationFailure

from config import Config

_client: MongoClient | None = None
_db = None


def get_db():
    """
    Return the shared MongoDB database instance, creating it on first call.
    Uses a module-level singleton so only one MongoClient is created per process.
    Also triggers index creation on the first connection.
    """
    global _client, _db
    if _db is None:
        _client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=5000)
        _db = _client[Config.MONGO_DB_NAME]
        _ensure_indexes(_db)
    return _db


def _ensure_indexes(db):
    """
    Create MongoDB indexes for all collections if they do not already exist.
    Indexes speed up lookups by email, username, user_id, slug, tags, and author_id.
    Silently ignores OperationFailure in case indexes were already created by a previous run.
    """
    try:
        db.users.create_index([("email", ASCENDING)], unique=True)
        db.users.create_index([("username", ASCENDING)], unique=True)
        db.conversations.create_index([("user_id", ASCENDING)])
        db.conversations.create_index([("updated_at", ASCENDING)])
        db.recipes.create_index([("slug", ASCENDING)], unique=True)
        db.recipes.create_index([("tags", ASCENDING)])
        db.recipes.create_index([("author_id", ASCENDING)])
    except OperationFailure:
        pass  # Indexes already exist
