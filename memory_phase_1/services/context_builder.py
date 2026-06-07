from models.api_models import Citation, MemoryContext, MemoryItem


def build_context(memories: list[dict]) -> MemoryContext:
    facts: list[MemoryItem] = []
    events: list[MemoryItem] = []
    procedures: list[MemoryItem] = []
    citations: list[Citation] = []

    for m in memories:
        item = MemoryItem(
            memory_id=m["memory_id"],
            text=m["text"],
            score=m["final_score"],
            importance_score=m.get("importance_score"),
            confidence_score=m.get("confidence_score"),
            quality_score=m.get("quality_score"),
            valid_from=m.get("valid_from"),
            valid_to=m.get("valid_to"),
        )

        if m["type"] == "semantic":
            facts.append(item)
        elif m["type"] == "episodic":
            events.append(item)
        elif m["type"] == "procedural":
            procedures.append(item)

        if m.get("source_system") or m.get("source_document_id"):
            citations.append(
                Citation(
                    memory_id=m["memory_id"],
                    source_system=m.get("source_system") or None,
                    source_document_id=m.get("source_document_id") or None,
                    confidence_score=m.get("confidence_score"),
                )
            )

    return MemoryContext(facts=facts, events=events, procedures=procedures, citations=citations)
