"""Lightweight logging utilities for compiler-style warnings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

WARN_CODES = {
    "missing-page": "W001",
    "unresolved-link": "W002",
    "unsupported-block": "W003",
    "table-parse-warning": "W004",
    "file-io-warning": "W005",
}


@dataclass(frozen=True)
class WarningEntry:
    """Captured warning with minimal metadata."""

    filename: str
    line: int | None
    element_type: str
    message: str
    code: str

    def format(self) -> str:
        location = f"{self.filename}:{self.line}" if self.line is not None else self.filename
        return f"{location} [{self.code}][{self.element_type}] {self.message}"


class WarningLogger:
    """Collect warnings and write them to a timestamped log file."""

    def __init__(self, root_name: str, *, source_root: Path | None = None) -> None:
        sanitized = re.sub(r"[^A-Za-z0-9_-]", "_", root_name) or "docs"
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
        self.log_path = Path("logs") / f"{sanitized}_{timestamp}.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._source_root = source_root.resolve() if source_root else None
        self._warnings: List[WarningEntry] = []

    @property
    def warnings(self) -> list[WarningEntry]:
        return list(self._warnings)

    def warn(
        self,
        *,
        filename: str,
        line: int | None,
        element_type: str,
        message: str,
        code: str,
    ) -> None:
        code = WARN_CODES.get(code, code)
        normalized_filename = self._format_filename(filename)
        entry = WarningEntry(
            filename=normalized_filename,
            line=line,
            element_type=element_type,
            message=message,
            code=code,
        )
        self._warnings.append(entry)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{entry.format()}\n")

    def summary(self) -> str:
        return f"Found {len(self._warnings)} warnings. See {self.log_path.name}"

    def has_warnings(self) -> bool:
        return bool(self._warnings)

    def _format_filename(self, filename: str) -> str:
        path = Path(filename)
        if self._source_root:
            candidate = path if path.is_absolute() else (self._source_root / path).resolve()
            try:
                relative = candidate.relative_to(self._source_root)
                return (Path(self._source_root.name) / relative).as_posix()
            except ValueError:
                return candidate.as_posix()
        return path.as_posix()


class NullLogger(WarningLogger):  # pragma: no cover - trivial shim
    """Logger that swallows warnings but keeps API compatibility."""

    def __init__(self, source_root: Path | None = None) -> None:
        self.log_path = Path("/dev/null")
        self._source_root = source_root.resolve() if source_root else None
        self._warnings: list[WarningEntry] = []

    def warn(
        self,
        *,
        filename: str,
        line: int | None,
        element_type: str,
        message: str,
        code: str,
    ) -> None:
        normalized_filename = self._format_filename(filename)
        self._warnings.append(
            WarningEntry(
                filename=normalized_filename,
                line=line,
                element_type=element_type,
                message=message,
                code=code,
            )
        )


def render_summary(logger: WarningLogger) -> str:
    """Return a human-readable summary of captured warnings."""

    return logger.summary()


__all__ = ["WarningLogger", "WarningEntry", "render_summary", "NullLogger", "WARN_CODES"]
