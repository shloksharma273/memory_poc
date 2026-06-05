"""
Entity & relationship extraction using Ollama + qwen2.5-coder:7b.
"""

import json
import os
import ollama
from config import OLLAMA_CHAT_MODEL, OLLAMA_BASE_URL
from models.schemas import ExtractionResult

_client: ollama.Client | None = None
_prompt_template: str | None = None


def _get_client() -> ollama.Client:
    global _client
    if _client is None:
        _client = ollama.Client(host=OLLAMA_BASE_URL)
    return _client


def _load_prompt() -> str:
    global _prompt_template
    if _prompt_template is None:
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts",
            "entity_extraction.txt",
        )
        with open(prompt_path, "r") as f:
            _prompt_template = f.read()
    return _prompt_template


def extract_entities(message: str) -> ExtractionResult:
    """
    Use the LLM to extract entities and relationships from a message.
    Returns an ExtractionResult with parsed entities and relationships.
    Falls back to empty result on failure.
    """
    client = _get_client()
    prompt = _load_prompt().replace("{message}", message)

    try:
        response = client.chat(
            model=OLLAMA_CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a JSON-only extraction system. "
                        "Return ONLY valid JSON with no additional text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            format="json",
        )

        content = response["message"]["content"]
        data = json.loads(content)
        return ExtractionResult(**data)

    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        print(f"⚠ Entity extraction failed: {e}")
        return ExtractionResult(entities=[], relationships=[])
    except Exception as e:
        print(f"⚠ Entity extraction error: {e}")
        return ExtractionResult(entities=[], relationships=[])
