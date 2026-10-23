"""Embedding-model switch and vector-store cache. No model download, no Chroma."""
import importlib

import rag.config as config
import rag.retriever as retriever


def reload_config(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("RAG_EMBEDDING_MODEL", raising=False)
    else:
        monkeypatch.setenv("RAG_EMBEDDING_MODEL", value)
    return importlib.reload(config)


def teardown_module(module):
    # restore the real config for any test that runs after this file
    import os
    os.environ.pop("RAG_EMBEDDING_MODEL", None)
    importlib.reload(config)


def test_default_model_keeps_original_index_folder(monkeypatch):
    cfg = reload_config(monkeypatch, None)
    assert cfg.EMBEDDING_MODEL_NAME == "paraphrase-multilingual-mpnet-base-v2"
    assert cfg.CHROMA_DB_DIR == cfg.DATA_DIR / "chroma_db"


def test_blank_env_var_falls_back_to_default(monkeypatch):
    cfg = reload_config(monkeypatch, "   ")
    assert cfg.EMBEDDING_MODEL_NAME == cfg.DEFAULT_EMBEDDING_MODEL


def test_other_model_gets_its_own_sibling_folder(monkeypatch):
    cfg = reload_config(monkeypatch, "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    assert cfg.CHROMA_DB_DIR.parent == cfg.DATA_DIR
    assert cfg.CHROMA_DB_DIR.name == "chroma_db_sentence-transformers-paraphrase-multilingual-minilm-l12-v2"
    # must not live inside the default folder, which ingest deletes before rebuilding
    assert cfg.DATA_DIR / "chroma_db" not in cfg.CHROMA_DB_DIR.parents


def test_vector_store_is_built_once(monkeypatch):
    built = []
    captured = {}

    def fake_embeddings(**kwargs):
        captured.update(kwargs)
        built.append("emb")
        return object()

    monkeypatch.setattr(retriever, "HuggingFaceEmbeddings", fake_embeddings)
    monkeypatch.setattr(retriever, "Chroma", lambda **kw: built.append("chroma") or object())
    retriever.get_vector_store.cache_clear()
    first = retriever.get_vector_store()
    second = retriever.get_vector_store()
    assert first is second
    assert built == ["emb", "chroma"]
    # Vectors must be normalised: the distance cutoff in agents/retrieval_adapter.py assumes unit vectors
    assert captured["encode_kwargs"] == {"normalize_embeddings": True}
    retriever.get_vector_store.cache_clear()
    retriever.get_vector_store()
    assert built == ["emb", "chroma", "emb", "chroma"]
    retriever.get_vector_store.cache_clear()
