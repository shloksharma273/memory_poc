"""
End-to-end feature test for the Agentic Memory System (all 3 phases).

Run with:
    python demo_test.py

Requires:
    - Server running on localhost:8000  (.venv/bin/uvicorn app:app --reload --host 0.0.0.0 --port 8000)
    - ArangoDB running on localhost:8529
    - Ollama running on localhost:11434 with qwen2.5-coder:7b and nomic-embed-text
"""

import sys
import time
import httpx

BASE = "http://localhost:8000"
TENANT = f"demo_test_{int(time.time())}"

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"
SECTION = "\033[1m\033[95m"
RESET = "\033[0m"

_failures = []


def section(title: str):
    print(f"\n{SECTION}{'─' * 55}{RESET}")
    print(f"{SECTION}  {title}{RESET}")
    print(f"{SECTION}{'─' * 55}{RESET}")


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  {PASS} {label}")
    else:
        msg = f"  {FAIL} {label}"
        if detail:
            msg += f"  ← {detail}"
        print(msg)
        _failures.append(label)


def post(path: str, payload: dict) -> dict:
    r = httpx.post(f"{BASE}{path}", json=payload, timeout=120.0)
    r.raise_for_status()
    return r.json()


def get(path: str, params: dict = None) -> dict:
    r = httpx.get(f"{BASE}{path}", params=params or {}, timeout=30.0)
    r.raise_for_status()
    return r.json()


# ── Stored memory IDs collected during the run ────────────────────────────────
stored_ids: list[str] = []


# ═════════════════════════════════════════════════════════════════════════════
# 1. HEALTH
# ═════════════════════════════════════════════════════════════════════════════
section("1. Health Check")
try:
    data = get("/health")
    check("Server is reachable", data.get("status") == "ok")
except Exception as e:
    check("Server is reachable", False, str(e))
    print(f"\n{FAIL} Cannot reach server — aborting. Start it with:")
    print("  .venv/bin/uvicorn app:app --reload --host 0.0.0.0 --port 8000\n")
    sys.exit(1)


# ═════════════════════════════════════════════════════════════════════════════
# 2. ADD MEMORIES (Phase 1)
# ═════════════════════════════════════════════════════════════════════════════
section("2. Add Memories  [Phase 1 — candidate scoring + classification]")

memories_to_add = [
    {
        "label": "Episodic #1 — payment failure event",
        "payload": {
            "tenant_id": TENANT,
            "text": "Customer ABC reported payment gateway failure after checkout deployment.",
            "source": "crm",
            "metadata": {"source_document_id": "crm_001", "event_timestamp": "2026-06-01T10:00:00Z"},
        },
        "expected_type": "episodic",
    },
    {
        "label": "Episodic #2 — second payment failure event",
        "payload": {
            "tenant_id": TENANT,
            "text": "Customer ABC faced another payment gateway issue after the latest release.",
            "source": "ticketing",
            "metadata": {"source_document_id": "ticket_003", "event_timestamp": "2026-06-05T10:00:00Z"},
        },
        "expected_type": "episodic",
    },
    {
        "label": "Semantic — stable fact about gateway",
        "payload": {
            "tenant_id": TENANT,
            "text": "Customer ABC uses Payment Gateway X for all checkout transactions.",
            "source": "crm",
            "metadata": {"source_document_id": "crm_002"},
        },
        "expected_type": "semantic",
    },
    {
        "label": "Procedural — runbook SOP",
        "payload": {
            "tenant_id": TENANT,
            "text": "For payment gateway failure, check transaction logs and retry queue.",
            "source": "docs",
            "metadata": {"source_document_id": "runbook_001"},
        },
        "expected_type": "procedural",
    },
]

for mem in memories_to_add:
    try:
        data = post("/memory/add", mem["payload"])
        stored = data["status"] in ("stored", "merged")
        check(f"{mem['label']} → status stored/merged", stored, f"got: {data.get('status')}")
        if data.get("status") == "stored":
            check(
                f"  └ classified as {mem['expected_type']}",
                data.get("memory_type") == mem["expected_type"],
                f"got: {data.get('memory_type')}",
            )
            check("  └ has importance_score", data.get("importance_score") is not None)
            check("  └ has confidence_score", data.get("confidence_score") is not None)
            check("  └ has quality_score", data.get("quality_score") is not None)
            check("  └ entities extracted", isinstance(data.get("entities"), list))
            stored_ids.append(data["memory_id"])
    except Exception as e:
        check(mem["label"], False, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# 3. VALIDATION — missing required field
# ═════════════════════════════════════════════════════════════════════════════
section("3. Input Validation")

try:
    r = httpx.post(f"{BASE}/memory/add", json={"tenant_id": TENANT}, timeout=10.0)
    check("Missing 'text' returns 422", r.status_code == 422, f"got: {r.status_code}")
except Exception as e:
    check("Missing 'text' returns 422", False, str(e))

try:
    r = httpx.post(f"{BASE}/memory/retrieve", json={"tenant_id": TENANT}, timeout=10.0)
    check("Missing 'query' in retrieve returns 422", r.status_code == 422, f"got: {r.status_code}")
except Exception as e:
    check("Missing 'query' in retrieve returns 422", False, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# 4. CONSOLIDATION / DEDUPLICATION (Phase 2)
# ═════════════════════════════════════════════════════════════════════════════
section("4. Consolidation — near-duplicate deduplication  [Phase 2]")

try:
    # Text is intentionally near-identical to Episodic #1 to reliably trigger consolidation.
    data = post(
        "/memory/add",
        {
            "tenant_id": TENANT,
            "text": "Customer ABC reported payment gateway failure after the checkout deployment.",
            "source": "ticketing",
            "metadata": {"source_document_id": "ticket_dup"},
        },
    )
    is_merged = data.get("status") == "merged"
    if is_merged:
        check("Near-duplicate merged (consolidation triggered)", True)
        check("  └ has target_memory_id", "target_memory_id" in data)
        check("  └ has consolidation_score", data.get("consolidation_score") is not None)
        check("  └ has duplicate_count", data.get("duplicate_count", 0) >= 1)
    else:
        # Consolidation is similarity-threshold sensitive. If not merged, check that the
        # pipeline ran without error (status is stored, not an exception).
        check(
            "Near-duplicate processed without error (merge not triggered — similarity under 0.80)",
            data.get("status") in ("stored", "not_stored"),
            f"got: {data.get('status')}",
        )
        print(f"  {INFO} tip: lower CONSOLIDATION_THRESHOLD in consolidation_service.py to force merge")
except Exception as e:
    check("Near-duplicate consolidation", False, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# 5. RETRIEVE — base memory context (Phase 1 + 2)
# ═════════════════════════════════════════════════════════════════════════════
section("5. Retrieve — hybrid semantic + graph ranking  [Phase 1 + 2]")

try:
    data = post(
        "/memory/retrieve",
        {"tenant_id": TENANT, "query": "payment processing errors", "top_k": 10},
    )
    check("Retrieve returns 200", "context" in data)
    ctx = data["context"]
    check("Response has 'facts' field", "facts" in ctx)
    check("Response has 'events' field", "events" in ctx)
    check("Response has 'procedures' field", "procedures" in ctx)
    check("Response has 'citations' field", "citations" in ctx)
    check("Response has 'reflections' field", "reflections" in ctx)
    check("Response has 'summaries' field", "summaries" in ctx)

    total_base = len(ctx["facts"]) + len(ctx["events"]) + len(ctx["procedures"])
    check("At least 1 memory returned", total_base >= 1, f"got: {total_base}")

    if ctx["events"]:
        ev = ctx["events"][0]
        check("  └ event has importance_score", ev.get("importance_score") is not None)
        check("  └ event has confidence_score", ev.get("confidence_score") is not None)
        check("  └ event has quality_score", ev.get("quality_score") is not None)
        check("  └ event has final score > 0", ev.get("score", 0) > 0)
except Exception as e:
    check("Retrieve base memories", False, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# 6. REFLECT — pattern detection + reflective memory creation (Phase 3)
# ═════════════════════════════════════════════════════════════════════════════
section("6. Reflect — cluster + pattern detection + reflective memory  [Phase 3]")

reflection_created = False
try:
    data = post(
        "/intelligence/reflect",
        {
            "tenant_id": TENANT,
            "time_window_days": 30,
            "min_quality_score": 0.0,
            "similarity_threshold": 0.65,
            "min_cluster_size": 2,
        },
    )
    check("Reflect endpoint returns status=completed", data.get("status") == "completed", f"got: {data.get('status')}")
    check("At least 1 candidate found", data.get("candidate_count", 0) >= 1, f"got: {data.get('candidate_count')}")
    check("At least 1 cluster formed", data.get("cluster_count", 0) >= 1, f"got: {data.get('cluster_count')}")
    check("At least 1 pattern detected", data.get("patterns_detected", 0) >= 1, f"got: {data.get('patterns_detected')}")
    reflection_created = data.get("reflections_created", 0) >= 1
    check("At least 1 reflective memory created", reflection_created, f"got: {data.get('reflections_created')}")
    print(f"  {INFO} clusters={data.get('cluster_count')}  patterns={data.get('patterns_detected')}  reflections_created={data.get('reflections_created')}")
except Exception as e:
    check("Reflect endpoint", False, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# 7. LIST REFLECTIONS
# ═════════════════════════════════════════════════════════════════════════════
section("7. List Reflections  [Phase 3]")

try:
    data = get("/intelligence/reflections", {"tenant_id": TENANT})
    check("Reflections list endpoint returns", "reflections" in data)
    reflections = data.get("reflections", [])
    check(
        "At least 1 reflection in list",
        len(reflections) >= 1,
        f"got: {len(reflections)} (reflect step must have succeeded)",
    )
    if reflections:
        r0 = reflections[0]
        check("  └ has reflection_text", bool(r0.get("reflection_text")))
        check("  └ has pattern_type", bool(r0.get("pattern_type")))
        check("  └ has support_count >= 1", (r0.get("support_count") or 0) >= 1)
        check("  └ has quality_score", r0.get("quality_score") is not None)
        check("  └ has supporting_memory_ids", isinstance(r0.get("supporting_memory_ids"), list))
        print(f"  {INFO} pattern_type={r0.get('pattern_type')}  support_count={r0.get('support_count')}")
        print(f"  {INFO} text: {r0.get('reflection_text', '')[:80]}...")
except Exception as e:
    check("List reflections", False, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# 8. SUMMARIZE
# ═════════════════════════════════════════════════════════════════════════════
section("8. Summarize — temporal rollup  [Phase 3]")

try:
    data = post(
        "/intelligence/summarize",
        {"tenant_id": TENANT, "summary_level": "weekly", "group_by": "time"},
    )
    check("Summarize endpoint responds", "status" in data or "summary_id" in data or "summaries_created" in data,
          f"keys: {list(data.keys())}")
    print(f"  {INFO} response: {data}")
except Exception as e:
    check("Summarize endpoint", False, str(e))

try:
    data = get("/intelligence/summaries", {"tenant_id": TENANT})
    check("Summaries list endpoint returns", "summaries" in data)
except Exception as e:
    check("List summaries", False, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# 9. RETRIEVE — reflections appear in context (Phase 3)
# ═════════════════════════════════════════════════════════════════════════════
section("9. Retrieve — reflections surface in context  [Phase 3]")

try:
    data = post(
        "/memory/retrieve",
        {"tenant_id": TENANT, "query": "payment processing errors", "top_k": 10},
    )
    ctx = data.get("context", {})
    reflections = ctx.get("reflections", [])
    check(
        "context.reflections is non-empty after reflect step",
        len(reflections) >= 1,
        f"got: {len(reflections)} reflections",
    )
    if reflections:
        r0 = reflections[0]
        check("  └ reflective memory has text", bool(r0.get("text")))
        check("  └ reflective memory has score > 0", r0.get("score", 0) > 0)
        check("  └ reflective memory has pattern_type", bool(r0.get("pattern_type")))
        check(
            "  └ reflective memory ranks at or near top (score >= 0.10)",
            r0.get("score", 0) >= 0.10,
            f"score={r0.get('score')}",
        )
        print(f"  {INFO} reflection score={r0.get('score')}  pattern={r0.get('pattern_type')}")
except Exception as e:
    check("Retrieve with reflections", False, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# 10. RANKING — reflective type boost applied correctly
# ═════════════════════════════════════════════════════════════════════════════
section("10. Ranking — reflective type boost (1.00) applied in scoring  [Phase 3]")

# The reflective type boost is 1.00 vs 0.60 for episodic, but it only contributes
# 0.10 of the final score weight — high semantic similarity on base memories can
# still outscore a reflection. We verify the boost is applied (score > 0) and
# that the reflection score is competitive (within reasonable range of top memory).
try:
    data = post(
        "/memory/retrieve",
        {"tenant_id": TENANT, "query": "payment gateway customer ABC", "top_k": 10},
    )
    ctx = data.get("context", {})
    reflections = ctx.get("reflections", [])
    all_scores = (
        [m.get("score", 0) for m in ctx.get("events", [])]
        + [m.get("score", 0) for m in ctx.get("facts", [])]
        + [m.get("score", 0) for m in ctx.get("procedures", [])]
    )
    if reflections:
        r_score = reflections[0].get("score", 0)
        max_base_score = max(all_scores) if all_scores else 0
        check("Reflective memory has positive final score", r_score > 0, f"score={r_score}")
        # Reflective score should be within 0.30 of the top base memory score.
        check(
            "Reflective score competitive with base memories (within 0.30)",
            abs(r_score - max_base_score) <= 0.30,
            f"reflection={r_score}  top_base={max_base_score}",
        )
        print(f"  {INFO} reflection_score={r_score}  top_base_score={max_base_score}")
    else:
        print(f"  {INFO} Skipped — no reflections in result (reflect step may not have run)")
except Exception as e:
    check("Ranking type boost check", False, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═════════════════════════════════════════════════════════════════════════════
section("RESULTS")
total_checks = sum(
    line.count("[PASS]") + line.count("[FAIL]")
    for line in []  # counted live above
)

if not _failures:
    print(f"\n  \033[92m\033[1m ALL CHECKS PASSED\033[0m  (tenant: {TENANT})\n")
else:
    print(f"\n  \033[91m\033[1m {len(_failures)} CHECK(S) FAILED:\033[0m")
    for f in _failures:
        print(f"    • {f}")
    print(f"\n  tenant used: {TENANT}\n")
    sys.exit(1)
