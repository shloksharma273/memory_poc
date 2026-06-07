import json
import re

import httpx

from config.settings import settings

_EXTRACT_PROMPT = """Extract important named entities from the text.

Supported entity types:
person, organization, customer, product, system, location, project, issue, unknown

Return ONLY valid JSON, no markdown.

Text:
{text}

Required JSON format:
{{"entities": [{{"name": "...", "type": "..."}}]}}"""


def extract_entities(text: str) -> list[dict]:
    prompt = _EXTRACT_PROMPT.format(text=text)
    try:
        response = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"].strip()

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            result = json.loads(match.group())
            entities = result.get("entities", [])
            return [e for e in entities if "name" in e and "type" in e]
    except Exception:
        pass

    return []
