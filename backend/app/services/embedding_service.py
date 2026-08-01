"""
Embedding service — turns chunk text into vectors using a local,
open-source sentence-transformers model (no external API calls, no
per-request cost). The model is loaded once, and reused across all
embedding calls in this process.
"""

from sentence_transformers import SentenceTransformer

from app.models.chunk import EMBEDDING_DIMENSIONS

_MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def warm_up() -> None:
    """
    Forces the model to load now instead of on the first real request.
    Call this once at app startup (see main.py) — otherwise whichever
    request happens to be first after every server restart eats a
    multi-second model-load penalty on top of its own work, which reads
    as random/inconsistent slowness rather than a one-time startup cost.
    """
    _get_model()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Returns one embedding vector per input text, same order."""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    embeddings = vectors.tolist()
    assert len(embeddings[0]) == EMBEDDING_DIMENSIONS, (
        f"Model output dimension {len(embeddings[0])} doesn't match "
        f"expected {EMBEDDING_DIMENSIONS} — model may have changed."
    )
    return embeddings