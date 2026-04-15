"""Named Cypher query templates used by the retrieval layer.

All query strings live here so the retrieval layer stays readable
and so query changes don't scatter across the codebase.
"""

# ── Lookup ────────────────────────────────────────────────────────────────────

GET_NODE_BY_ID = "MATCH (n {node_id: $node_id}) RETURN n LIMIT 1"

GET_NODES_BY_NAME = """
    MATCH (n)
    WHERE n.name = $name OR n.fqn CONTAINS $name
    RETURN n
    ORDER BY n.importance_score DESC
    LIMIT $limit
"""

GET_NODES_BY_TYPE = """
    MATCH (n:{node_type})
    RETURN n
    ORDER BY n.importance_score DESC
    LIMIT $limit
"""

GET_FILE_NODES = """
    MATCH (n:File)
    RETURN n
    ORDER BY n.importance_score DESC
    LIMIT $limit
"""

# ── Neighbourhood ─────────────────────────────────────────────────────────────

GET_CALLERS = """
    MATCH (caller)-[:CALLS]->(n {node_id: $node_id})
    RETURN caller
    ORDER BY caller.importance_score DESC
    LIMIT $limit
"""

GET_CALLEES = """
    MATCH (n {node_id: $node_id})-[:CALLS]->(callee)
    RETURN callee
    ORDER BY callee.importance_score DESC
    LIMIT $limit
"""

GET_IMPORTERS = """
    MATCH (importer:File)-[:IMPORTS]->(f:File {node_id: $node_id})
    RETURN importer
    ORDER BY importer.importance_score DESC
    LIMIT $limit
"""

GET_SUBGRAPH = """
    MATCH (n {node_id: $node_id})-[r*1..$depth]-(neighbor)
    RETURN DISTINCT neighbor
    ORDER BY neighbor.importance_score DESC
    LIMIT $limit
"""

# ── Impact analysis ───────────────────────────────────────────────────────────

GET_DEPENDENTS = """
    MATCH (n {node_id: $node_id})<-[*1..$depth]-(dependent)
    RETURN DISTINCT dependent
    ORDER BY dependent.importance_score DESC
    LIMIT $limit
"""

# ── Path finding ──────────────────────────────────────────────────────────────

SHORTEST_PATH = """
    MATCH (src {node_id: $src_id}), (dst {node_id: $dst_id}),
          path = shortestPath((src)-[*1..$max_depth]-(dst))
    RETURN path
    LIMIT 5
"""

# ── Centrality export ─────────────────────────────────────────────────────────

EXPORT_CALL_GRAPH = """
    MATCH (src)-[:CALLS]->(dst)
    RETURN src.node_id AS src, dst.node_id AS dst
"""

EXPORT_IMPORT_GRAPH = """
    MATCH (src:File)-[:IMPORTS]->(dst:File)
    RETURN src.node_id AS src, dst.node_id AS dst
"""

# ── Stats ─────────────────────────────────────────────────────────────────────

TOP_BY_IMPORTANCE = """
    MATCH (n:{node_type})
    RETURN n.fqn AS fqn, n.importance_score AS score, n.file_path AS file
    ORDER BY score DESC
    LIMIT $limit
"""
