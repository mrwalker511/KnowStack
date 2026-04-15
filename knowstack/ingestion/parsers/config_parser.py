"""Config file parser for JSON, YAML, and TOML files.

Emits a ConfigFileNode for each config file. Does not attempt to extract
individual keys — that level of granularity produces too much noise without
sufficient payoff. The node is still indexed for semantic search.
"""
from __future__ import annotations

import logging

from knowstack.ingestion.scanner import FileRecord
from knowstack.models.enums import Language, NodeType
from knowstack.models.nodes import ConfigFileNode, make_node_id
from knowstack.models.source_span import SourceSpan

from .base import BaseParser, ParseResult

log = logging.getLogger(__name__)

_CONFIG_LANGUAGES = {Language.JSON, Language.YAML, Language.TOML}
_FORMAT_MAP = {
    Language.JSON: "json",
    Language.YAML: "yaml",
    Language.TOML: "toml",
}


class ConfigParser(BaseParser):
    def can_parse(self, record: FileRecord) -> bool:
        return record.language in _CONFIG_LANGUAGES

    def parse(self, record: FileRecord) -> ParseResult:
        result = ParseResult(file_record=record)
        try:
            fmt = _FORMAT_MAP.get(record.language, "unknown")
            node = ConfigFileNode(
                node_id=make_node_id(record.rel_path, record.rel_path),
                node_type=NodeType.CONFIG_FILE,
                name=record.abs_path.name,
                fqn=record.rel_path,
                language=record.language,
                file_path=record.rel_path,
                format=fmt,
                source_span=SourceSpan(
                    file_path=record.rel_path,
                    start_line=1,
                    end_line=record.text.count("\n") + 1,
                ),
            )
            result.nodes.append(node)
        except Exception as exc:
            result.errors.append(str(exc))
            log.debug("Config parse error in %s: %s", record.rel_path, exc)
        return result
