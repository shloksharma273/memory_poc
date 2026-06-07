import httpx
from config.settings import settings


def generate_embedding(text: str) -> list[float]:
    response = httpx.post(
        f"{settings.ollama_base_url}/api/embeddings",
        json={"model": settings.ollama_embed_model, "prompt": text},
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()
    if "embedding" not in data:
        raise ValueError(f"Ollama embeddings response missing 'embedding' key: {data}")
    return data["embedding"]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
