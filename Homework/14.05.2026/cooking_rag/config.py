import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")

    # MongoDB
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB_NAME = os.getenv("MONGO_DB", "smart_cookbook")

    # JWT
    JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

    # Data folder (recipe markdown files)
    DATA_FOLDER = BASE_DIR / "data"

    # AI
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    HF_TOKEN = os.getenv("HF_TOKEN")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    HF_EMBEDDING_MODEL = os.getenv(
        "HF_EMBEDDING_MODEL",
        "ibm-granite/granite-embedding-97m-multilingual-r2",
    )

    # RAG
    TOP_K = int(os.getenv("TOP_K", "2"))
    BATCH_SIZE = 8
    HISTORY_MESSAGES = int(os.getenv("HISTORY_MESSAGES", "2"))
