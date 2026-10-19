"""Keeps Member 1's vector store alive between requests.

rag.retriever.get_vector_store() builds a new embedding model + Chroma client on
every call (several seconds each). Behind an API that is too slow, so at startup
we wrap it in an lru_cache. search_attractions() looks the function up by name
at call time, so it picks up the cached version without any change to rag/.
If Member 1 adds caching inside rag/retriever.py, this becomes a no-op.
"""
import logging
from functools import lru_cache

from rag.config import CHROMA_DB_DIR

logger = logging.getLogger("rehlaguide.api")


def index_exists() -> bool:
    # Chroma creates an empty directory on first open, so check for its database file.
    return (CHROMA_DB_DIR / "chroma.sqlite3").is_file()


def enable_vector_store_cache() -> None:
    import rag.retriever as retriever

    if not hasattr(retriever.get_vector_store, "cache_info"):
        retriever.get_vector_store = lru_cache(maxsize=1)(retriever.get_vector_store)


def vector_store_loaded() -> bool:
    import rag.retriever as retriever

    info = getattr(retriever.get_vector_store, "cache_info", None)
    return bool(info and info().currsize)


def warmup() -> bool:
    """Load the embedding model and open Chroma once. Never raises."""
    enable_vector_store_cache()
    if not index_exists():
        logger.warning("Vector index not found at %s. Run: uv run python -m rag.ingest", CHROMA_DB_DIR)
        return False
    try:
        import rag.retriever as retriever

        retriever.get_vector_store()
        logger.info("Vector store loaded")
        return True
    except Exception:
        logger.exception("Could not load the vector store")
        return False
