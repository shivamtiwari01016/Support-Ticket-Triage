"""Environment-backed application configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_DIR = _project_path(os.getenv("MODEL_DIR", "models"))
MODEL_PATH = MODEL_DIR / "ticket_triage.joblib"
EVALUATION_PATH = MODEL_DIR / "evaluation.json"
MODEL_VERSION = os.getenv("MODEL_VERSION", "v1")
SPACY_MODEL = os.getenv("SPACY_MODEL", "en_core_web_sm")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
API_KEY = os.getenv("TICKET_TRIAGE_API_KEY", "").strip()
RATE_LIMIT_PER_MINUTE = int(os.getenv("TICKET_TRIAGE_RATE_LIMIT_PER_MINUTE", "60"))
MAX_REQUEST_BYTES = int(os.getenv("TICKET_TRIAGE_MAX_REQUEST_BYTES", str(1024 * 1024)))
if ENVIRONMENT != "development" and not API_KEY:
    raise RuntimeError("TICKET_TRIAGE_API_KEY must be set outside development.")
CORS_ALLOW_ALL = os.getenv("TICKET_TRIAGE_CORS_ALLOW_ALL", "false").strip().lower() in {
    "1",
    "true",
    "yes",
}

CORS_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv(
        "TICKET_TRIAGE_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
)
