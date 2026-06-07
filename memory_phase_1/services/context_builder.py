from models.api_models import Citation, MemoryContext, MemoryItem, ReflectionItem, SummaryItem


def build_context(memories: list[dict]) -> MemoryContext:
    facts: list[MemoryItem] = []
    events: list[MemoryItem] = []
    procedures: list[MemoryItem] = []
    reflections: list[ReflectionItem] = []
    summaries: list[SummaryItem] = []
    citations: list[Citation] = []

    for m in memories:
        mem_type = m["type"]

        if mem_type == "reflective":
            reflections.append(ReflectionItem(
                memory_id=m["memory_id"],
                text=m["text"],
                score=m["final_score"],
                pattern_type=m.get("pattern_type"),
                support_count=m.get("support_count"),
                confidence_score=m.get("confidence_score"),
                supporting_memory_ids=m.get("supporting_memory_ids") or [],
            ))
            continue

        if mem_type == "summary":
            summaries.append(SummaryItem(
                memory_id=m["memory_id"],
                text=m["text"],
                score=m["final_score"],
                summary_level=m.get("summary_level"),
                memory_count=m.get("memory_count"),
                confidence_score=m.get("confidence_score"),
            ))
            continue

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

        if mem_type == "semantic":
            facts.append(item)
        elif mem_type == "episodic":
            events.append(item)
        elif mem_type == "procedural":
            procedures.append(item)

        if m.get("source_system") or m.get("source_document_id"):
            citations.append(Citation(
                memory_id=m["memory_id"],
                source_system=m.get("source_system") or None,
                source_document_id=m.get("source_document_id") or None,
                confidence_score=m.get("confidence_score"),
            ))

    return MemoryContext(
        facts=facts,
        events=events,
        procedures=procedures,
        reflections=reflections,
        summaries=summaries,
        citations=citations,
    )
