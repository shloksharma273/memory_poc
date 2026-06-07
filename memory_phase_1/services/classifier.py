import json
import re

import httpx

from config.settings import settings

_CLASSIFY_PROMPT = """You are a memory classification engine.

Classify the following text into exactly one memory type:

1. episodic   - an event that happened at a specific time
2. semantic   - a fact, entity relationship, or stable knowledge
3. procedural - a workflow, SOP, instruction, or repeated process

Return ONLY valid JSON, no markdown, no explanation outside the JSON.

Text:
{text}

Required JSON format:
{{"type": "episodic", "reason": "short reason"}}"""


def _fallback_classify(text: str) -> dict:
    t = text.lower()
    if any(w in t for w in ["reported", "happened", "created", "opened", "failed", "occurred", "experienced", "encountered"]):
        return {"type": "episodic", "reason": "keyword match"}
    if any(w in t for w in ["steps", "process", "how to", "workflow", "procedure", "first check", "then ", "notify"]):
        return {"type": "procedural", "reason": "keyword match"}
    return {"type": "semantic", "reason": "default"}


def classify_memory(text: str) -> dict:
    prompt = _CLASSIFY_PROMPT.format(text=text)
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
            if result.get("type") in ("episodic", "semantic", "procedural"):
                return result
    except Exception:
        pass

    return _fallback_classify(text)
