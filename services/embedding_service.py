"""
Embedding generation using Ollama + nomic-embed-text.
"""

import ollama
from config import OLLAMA_EMBED_MODEL, OLLAMA_BASE_URL

_client: ollama.Client | None = None


def _get_client() -> ollama.Client:
    global _client
    if _client is None:
        _client = ollama.Client(host=OLLAMA_BASE_URL)
    return _client


def generate_embedding(text: str) -> list[float]:
    """Generate a vector embedding for the given text."""
    client = _get_client()
    response = client.embeddings(model=OLLAMA_EMBED_MODEL, prompt=text)
    return response["embedding"]
