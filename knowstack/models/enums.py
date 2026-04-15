from enum import StrEnum


class NodeType(StrEnum):
    FILE = "File"
    DIRECTORY = "Directory"
    MODULE = "Module"
    CLASS = "Class"
    FUNCTION = "Function"
    METHOD = "Method"
    INTERFACE = "Interface"
    TYPE_ALIAS = "TypeAlias"
    VARIABLE = "Variable"
    IMPORT = "Import"
    EXPORT = "Export"
    API_ENDPOINT = "ApiEndpoint"
    DB_MODEL = "DbModel"
    DB_TABLE = "DbTable"
    TEST = "Test"
    CONFIG_FILE = "ConfigFile"
    CONFIG_ENTRY = "ConfigEntry"


class EdgeType(StrEnum):
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    IMPLEMENTS = "IMPLEMENTS"
    REFERENCES = "REFERENCES"
    DEFINES = "DEFINES"
    INSTANTIATES = "INSTANTIATES"
    READS_FROM = "READS_FROM"
    WRITES_TO = "WRITES_TO"
    DEPENDS_ON = "DEPENDS_ON"
    TESTED_BY = "TESTED_BY"
    CONFIGURES = "CONFIGURES"
    EXPOSES_ENDPOINT = "EXPOSES_ENDPOINT"


class Language(StrEnum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    MARKDOWN = "markdown"
    UNKNOWN = "unknown"

    @classmethod
    def from_extension(cls, ext: str) -> "Language":
        ext = ext.lower().lstrip(".")
        mapping = {
            "py": cls.PYTHON,
            "ts": cls.TYPESCRIPT,
            "tsx": cls.TYPESCRIPT,
            "js": cls.JAVASCRIPT,
            "jsx": cls.JAVASCRIPT,
            "mjs": cls.JAVASCRIPT,
            "cjs": cls.JAVASCRIPT,
            "json": cls.JSON,
            "yaml": cls.YAML,
            "yml": cls.YAML,
            "toml": cls.TOML,
            "md": cls.MARKDOWN,
            "mdx": cls.MARKDOWN,
        }
        return mapping.get(ext, cls.UNKNOWN)
