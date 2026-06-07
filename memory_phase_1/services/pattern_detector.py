"""Detect patterns in memory clusters using LLM."""
import json
import re
import httpx
from config.settings import settings

PATTERN_TYPES = [
    "recurring_issue",
    "behavior_pattern",
    "entity_relationship_pattern",
    "workflow_pattern",
    "risk_pattern",
    "preference_pattern",
    "unknown",
]

_DETECT_PROMPT = """You are a memory reflection engine.

Analyze the following related memories and identify whether they show a meaningful recurring pattern.

Supported pattern types:
1. recurring_issue
2. behavior_pattern
3. entity_relationship_pattern
4. workflow_pattern
5. risk_pattern
6. preference_pattern
7. unknown

Return ONLY valid JSON, no markdown.

Memories:
{memories}

Required JSON format:
{{"has_pattern": true, "pattern_type": "recurring_issue", "pattern_summary": "short summary", "evidence_count": 3, "reason": "why this is meaningful"}}"""

def _fallback(cluster: dict) -> dict:
    size = len(cluster.get("memories", []))
    avg_q = cluster.get("avg_quality_score", 0.0)
    if size >= 2 and avg_q >= 0.50:
        texts = " ".join(m["text"][:60] for m in cluster["memories"][:3])
        return {
            "has_pattern": True,
            "pattern_type": "recurring_issue",
            "pattern_summary": f"Recurring pattern across {size} memories: {texts[:100]}",
            "evidence_count": size,
            "reason": "Cluster size and quality threshold met",
        }
    return {"has_pattern": False, "pattern_type": "unknown", "pattern_summary": "", "evidence_count": size, "reason": "Insufficient evidence"}

def detect_pattern(cluster: dict) -> dict:
    memories = cluster.get("memories", [])
    if len(memories) < 2:
        return {"has_pattern": False, "pattern_type": "unknown", "pattern_summary": "", "evidence_count": len(memories), "reason": "Cluster too small"}

    memory_lines = "\n".join(f"- {m['text']}" for m in memories)
    prompt = _DETECT_PROMPT.format(memories=memory_lines)

    try:
        response = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=90.0,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"].strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            result = json.loads(match.group())
            if result.get("pattern_type") not in PATTERN_TYPES:
                result["pattern_type"] = "unknown"
            return result
    except Exception:
        pass

    return _fallback(cluster)
