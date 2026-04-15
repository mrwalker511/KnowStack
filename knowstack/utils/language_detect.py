from pathlib import Path

from knowstack.models.enums import Language


def detect_language(path: Path) -> Language:
    """Infer language from file extension."""
    return Language.from_extension(path.suffix)


def is_code_file(path: Path) -> bool:
    """Return True if the file is a parseable source file."""
    return detect_language(path) not in (Language.UNKNOWN,)


def is_config_file(path: Path) -> bool:
    """Return True if the file is a structured config file."""
    return detect_language(path) in (Language.JSON, Language.YAML, Language.TOML)
