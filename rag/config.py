import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


RAW_DATA_PATH = DATA_DIR / "raw_attractions.json"

DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
# Override per run to compare models, e.g. (PowerShell):
#   $env:RAG_EMBEDDING_MODEL="paraphrase-multilingual-MiniLM-L12-v2"
# Ingest, retriever and eval all read this one setting, so they stay in sync.
EMBEDDING_MODEL_NAME = os.getenv("RAG_EMBEDDING_MODEL", "").strip() or DEFAULT_EMBEDDING_MODEL


def index_dir_for(model_name: str) -> Path:
    """Index folder for a model. The default model keeps the original path.

    Other models get a sibling folder (not a subfolder): ingest deletes its own
    folder before rebuilding, so a subfolder would be wiped by the default index.
    Vectors from different models are not comparable, so they must not share a folder.
    """
    if model_name == DEFAULT_EMBEDDING_MODEL:
        return DATA_DIR / "chroma_db"
    slug = re.sub(r"[^a-z0-9]+", "-", model_name.lower()).strip("-")
    return DATA_DIR / f"chroma_db_{slug}"


CHROMA_DB_DIR = index_dir_for(EMBEDDING_MODEL_NAME)

DEFAULT_TOP_K = 5
