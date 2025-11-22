"""Persistent mapping between filesystem paths and Notion page IDs."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath


@dataclass
class PageIdMap:
    """Simple JSON-backed mapping of document paths to Notion page IDs."""

    path: Path
    map: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_default_location(cls, docs_root: Path) -> "PageIdMap":
        """Load mapping from ``<docs_root>/.mkdocs2notion_ids.json``.

        Args:
            docs_root: Root directory containing Markdown docs.

        Returns:
            PageIdMap: A loaded or newly initialized mapping.
        """

        mapping_path = docs_root / ".mkdocs2notion_ids.json"
        mapping: dict[str, str] = {}
        if mapping_path.exists():
            try:
                data = json.loads(mapping_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    mapping = {PurePosixPath(k).as_posix(): str(v) for k, v in data.items()}
            except (OSError, json.JSONDecodeError):
                mapping = {}
        return cls(path=mapping_path, map=mapping)

    def get(self, page_path: str) -> str | None:
        """Retrieve a stored Notion page ID for a file path."""

        return self.map.get(self._normalize(page_path))

    def set(self, page_path: str, page_id: str) -> None:
        """Store a Notion page ID for a given file path."""

        self.map[self._normalize(page_path)] = page_id

    def remove(self, page_path: str) -> None:
        """Remove a mapping if it exists."""

        self.map.pop(self._normalize(page_path), None)

    def save(self) -> None:
        """Persist the mapping to disk as indented JSON."""

        if not self.path.parent.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.map, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _normalize(page_path: str) -> str:
        return PurePosixPath(str(page_path).replace("\\", "/")).as_posix()
