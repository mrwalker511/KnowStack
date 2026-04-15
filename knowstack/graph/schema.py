"""Kuzu DDL for the KnowStack property graph schema.

Each NodeType gets its own node table so Kuzu can enforce typed schemas.
Relationship tables declare which node table pairs they connect.

Schema version is bumped whenever DDL changes — migrations.py handles upgrades.
"""

SCHEMA_VERSION = 1

# ── Node table DDL ───────────────────────────────────────────────────────────
# Common columns on every node table:
#   node_id STRING PRIMARY KEY
#   name STRING, fqn STRING, language STRING
#   docstring STRING, tags STRING (JSON array)
#   change_frequency DOUBLE, centrality_score DOUBLE, importance_score DOUBLE

_COMMON_NODE_COLS = """
    node_id STRING PRIMARY KEY,
    name STRING,
    fqn STRING,
    language STRING,
    docstring STRING,
    tags STRING,
    change_frequency DOUBLE,
    centrality_score DOUBLE,
    importance_score DOUBLE,
    last_modified_commit STRING
"""

NODE_TABLES: dict[str, str] = {
    "File": f"""
        CREATE NODE TABLE IF NOT EXISTS File(
            {_COMMON_NODE_COLS},
            file_path STRING,
            extension STRING,
            size_bytes INT64,
            content_hash STRING
        )
    """,
    "Directory": f"""
        CREATE NODE TABLE IF NOT EXISTS Directory(
            {_COMMON_NODE_COLS},
            dir_path STRING
        )
    """,
    "Class": f"""
        CREATE NODE TABLE IF NOT EXISTS Class(
            {_COMMON_NODE_COLS},
            file_path STRING,
            start_line INT32,
            end_line INT32,
            is_abstract BOOLEAN,
            decorator_names STRING,
            bases STRING
        )
    """,
    "Function": f"""
        CREATE NODE TABLE IF NOT EXISTS Function(
            {_COMMON_NODE_COLS},
            file_path STRING,
            start_line INT32,
            end_line INT32,
            signature STRING,
            is_async BOOLEAN,
            is_generator BOOLEAN,
            return_type STRING,
            decorator_names STRING,
            parameter_names STRING
        )
    """,
    "Method": f"""
        CREATE NODE TABLE IF NOT EXISTS Method(
            {_COMMON_NODE_COLS},
            file_path STRING,
            start_line INT32,
            end_line INT32,
            signature STRING,
            is_async BOOLEAN,
            is_generator BOOLEAN,
            return_type STRING,
            decorator_names STRING,
            parameter_names STRING,
            class_fqn STRING,
            is_static BOOLEAN,
            is_classmethod BOOLEAN,
            is_property BOOLEAN
        )
    """,
    "Interface": f"""
        CREATE NODE TABLE IF NOT EXISTS Interface(
            {_COMMON_NODE_COLS},
            file_path STRING,
            start_line INT32,
            end_line INT32,
            extends STRING
        )
    """,
    "TypeAlias": f"""
        CREATE NODE TABLE IF NOT EXISTS TypeAlias(
            {_COMMON_NODE_COLS},
            file_path STRING,
            start_line INT32,
            end_line INT32,
            type_expression STRING
        )
    """,
    "ApiEndpoint": f"""
        CREATE NODE TABLE IF NOT EXISTS ApiEndpoint(
            {_COMMON_NODE_COLS},
            file_path STRING,
            start_line INT32,
            end_line INT32,
            http_method STRING,
            path_pattern STRING,
            framework STRING
        )
    """,
    "DbModel": f"""
        CREATE NODE TABLE IF NOT EXISTS DbModel(
            {_COMMON_NODE_COLS},
            file_path STRING,
            start_line INT32,
            end_line INT32,
            table_name STRING,
            orm_framework STRING,
            fields STRING
        )
    """,
    "Test": f"""
        CREATE NODE TABLE IF NOT EXISTS Test(
            {_COMMON_NODE_COLS},
            file_path STRING,
            start_line INT32,
            end_line INT32,
            test_framework STRING,
            is_parametrized BOOLEAN,
            targets STRING
        )
    """,
    "ConfigFile": f"""
        CREATE NODE TABLE IF NOT EXISTS ConfigFile(
            {_COMMON_NODE_COLS},
            file_path STRING,
            format STRING
        )
    """,
}

# ── Relationship table DDL ────────────────────────────────────────────────────
# Kuzu requires explicit FROM/TO node table declarations.
# We use ANY → ANY shorthand via a single "Node" group where possible,
# but Kuzu needs at least one concrete pair; we list the most common ones.

REL_TABLES: dict[str, str] = {
    "CONTAINS": """
        CREATE REL TABLE IF NOT EXISTS CONTAINS(
            FROM Directory TO File,
            FROM Directory TO Directory,
            FROM File TO Class,
            FROM File TO Function,
            FROM File TO Interface,
            FROM File TO TypeAlias,
            FROM File TO DbModel,
            FROM File TO Test,
            FROM File TO ConfigFile,
            FROM Class TO Method,
            edge_id STRING
        )
    """,
    "IMPORTS": """
        CREATE REL TABLE IF NOT EXISTS IMPORTS(
            FROM File TO File,
            edge_id STRING,
            imported_names STRING,
            is_dynamic BOOLEAN,
            confidence DOUBLE
        )
    """,
    "CALLS": """
        CREATE REL TABLE IF NOT EXISTS CALLS(
            FROM Function TO Function,
            FROM Function TO Method,
            FROM Method TO Function,
            FROM Method TO Method,
            edge_id STRING,
            is_conditional BOOLEAN,
            is_dynamic BOOLEAN,
            confidence DOUBLE
        )
    """,
    "INHERITS": """
        CREATE REL TABLE IF NOT EXISTS INHERITS(
            FROM Class TO Class,
            edge_id STRING,
            is_mixin BOOLEAN,
            confidence DOUBLE
        )
    """,
    "IMPLEMENTS": """
        CREATE REL TABLE IF NOT EXISTS IMPLEMENTS(
            FROM Class TO Interface,
            edge_id STRING,
            confidence DOUBLE
        )
    """,
    "READS_FROM": """
        CREATE REL TABLE IF NOT EXISTS READS_FROM(
            FROM Function TO DbModel,
            FROM Method TO DbModel,
            edge_id STRING,
            access_pattern STRING,
            confidence DOUBLE
        )
    """,
    "WRITES_TO": """
        CREATE REL TABLE IF NOT EXISTS WRITES_TO(
            FROM Function TO DbModel,
            FROM Method TO DbModel,
            edge_id STRING,
            access_pattern STRING,
            confidence DOUBLE
        )
    """,
    "TESTED_BY": """
        CREATE REL TABLE IF NOT EXISTS TESTED_BY(
            FROM Function TO Test,
            FROM Method TO Test,
            FROM Class TO Test,
            edge_id STRING
        )
    """,
    "EXPOSES_ENDPOINT": """
        CREATE REL TABLE IF NOT EXISTS EXPOSES_ENDPOINT(
            FROM Function TO ApiEndpoint,
            FROM Method TO ApiEndpoint,
            edge_id STRING
        )
    """,
    "DEFINES": """
        CREATE REL TABLE IF NOT EXISTS DEFINES(
            FROM File TO Function,
            FROM File TO Class,
            FROM File TO Interface,
            FROM File TO TypeAlias,
            edge_id STRING
        )
    """,
}

# ── Schema metadata table ─────────────────────────────────────────────────────
SCHEMA_META_TABLE = """
    CREATE NODE TABLE IF NOT EXISTS _SchemaMeta(
        key STRING PRIMARY KEY,
        value STRING
    )
"""

ALL_DDL = [SCHEMA_META_TABLE] + list(NODE_TABLES.values()) + list(REL_TABLES.values())
