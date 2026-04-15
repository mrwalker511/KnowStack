from pydantic import BaseModel


class SourceSpan(BaseModel):
    """Precise location of a symbol within a source file."""

    file_path: str  # Repo-relative path, e.g. "src/auth/service.py"
    start_line: int
    end_line: int
    start_byte: int = 0
    end_byte: int = 0

    def __str__(self) -> str:
        return f"{self.file_path}:{self.start_line}-{self.end_line}"

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1
