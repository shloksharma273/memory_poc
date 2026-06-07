# AQL cosine similarity search — works on all ArangoDB versions without a vector index.
# For 1000 memories this completes well under the 3-second Phase 1 SLA.
COSINE_SEARCH = """
FOR doc IN @@collection
  FILTER doc.tenant_id == @tenant_id AND doc.embedding != null
  LET sim = (
    LET a = doc.embedding
    LET b = @query_vec
    LET dot      = SUM(FOR i IN 0..LENGTH(a)-1 RETURN a[i] * b[i])
    LET norm_a   = SQRT(SUM(FOR v IN a RETURN v * v))
    LET norm_b   = SQRT(SUM(FOR v IN b RETURN v * v))
    RETURN dot / (norm_a * norm_b + 0.000001)
  )[0]
  FILTER sim > 0.1
  SORT sim DESC
  LIMIT @top_k
  RETURN MERGE(doc, {_similarity: sim})
"""

# Inbound traversal: find all memories that mention a given entity.
GRAPH_TRAVERSAL = """
FOR v, e IN 1..1 INBOUND @entity_id memory_mentions_entity
  FILTER v.tenant_id == @tenant_id
  RETURN DISTINCT {
    memory_id  : v._key,
    collection : SPLIT(v._id, "/")[0],
    text       : v.text != null ? v.text : (v.fact != null ? v.fact : (v.procedure != null ? v.procedure : "")),
    type       : v.type,
    memory_score: v.memory_score
  }
"""

# Fetch provenance linked to a memory.
GET_PROVENANCE = """
FOR v, e IN 1..1 OUTBOUND @memory_id memory_has_provenance
  RETURN v
"""
