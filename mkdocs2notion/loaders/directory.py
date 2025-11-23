"""Directory scanning utilities for Markdown sources."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, TypedDict

from mkdocs2notion.utils.simple_yaml import safe_load

HIDDEN_PREFIX = "."


class _RenderNode(TypedDict):
    files: list["DocumentNode"]
    children: Dict[str, "_RenderNode"]


@dataclass
class DocumentNode:
    """Represents a single Markdown document discovered on disk."""

    path: Path
    relative_path: str
    title: str
    content: str
    children: list["DocumentNode"] = field(default_factory=list)
    read_error: bool = False


@dataclass
class DirectoryTree:
    """In-memory representation of a directory of Markdown documents."""

    root: Path
    documents: list[DocumentNode]

    def pretty(self) -> str:
        """Return a human-readable tree representation of the directory.

        Returns:
            str: A tree where each line shows the folder hierarchy and file titles.
        """

        structure: _RenderNode = {"files": [], "children": {}}
        for doc in self.documents:
            parts = doc.relative_path.split("/")
            current = structure
            for part in parts[:-1]:
                current = current["children"].setdefault(
                    part, {"files": [], "children": {}}
                )
            current["files"].append(doc)

        lines: List[str] = [f"{self.root.name}/"]

        def _render(node: _RenderNode, indent: int) -> None:
            for file_node in sorted(node["files"], key=lambda d: d.relative_path):
                lines.append(
                    f"{'  ' * indent}{Path(file_node.relative_path).name} ({file_node.title})"
                )

            for name, child in sorted(node["children"].items()):
                lines.append(f"{'  ' * indent}{name}/")
                _render(child, indent + 1)

        _render(structure, 1)
        return "\n".join(lines)

    def validate(self) -> list[str]:
        """Validate directory contents for common issues.

        Returns:
            list[str]: A list of validation error messages.
        """

        errors: list[str] = []
        titles: Dict[str, int] = {}
        for doc in self.documents:
            if doc.title.strip() == "":
                errors.append(f"Missing title for {doc.relative_path}")
            titles[doc.title] = titles.get(doc.title, 0) + 1

            rel_path = Path(doc.relative_path)
            if rel_path.is_absolute() or ".." in rel_path.parts:
                errors.append(f"Invalid relative path: {doc.relative_path}")
            if doc.read_error:
                errors.append(f"Unreadable file: {doc.relative_path}")

        for title, count in titles.items():
            if count > 1:
                errors.append(f"Duplicate title detected: {title}")

        return errors

    def find_by_path(self, relative_path: str) -> DocumentNode | None:
        """Locate a document by its relative path.

        Args:
            relative_path: POSIX-style relative path to search for.

        Returns:
            DocumentNode | None: The matching node, if present.
        """

        normalized = _normalize_path(relative_path)
        for doc in self.documents:
            if doc.relative_path == normalized:
                return doc
        return None

    def paths(self) -> set[str]:
        """Return a set of all document relative paths."""

        return {doc.relative_path for doc in self.documents}


def load_directory(root_path: Path) -> DirectoryTree:
    """Recursively load Markdown files from a root directory.

    Args:
        root_path: Base directory containing Markdown content.

    Returns:
        DirectoryTree: Populated with all discovered Markdown documents.
    """

    documents: list[DocumentNode] = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if not d.startswith(HIDDEN_PREFIX)]
        for filename in filenames:
            if filename.startswith(HIDDEN_PREFIX) or not filename.endswith(".md"):
                continue
            full_path = Path(dirpath) / filename
            rel_path = full_path.relative_to(root_path)
            content = ""
            read_error = False
            try:
                content = full_path.read_text(encoding="utf-8")
            except OSError:
                read_error = True
            title = _extract_title(content, full_path)
            documents.append(
                DocumentNode(
                    path=full_path,
                    relative_path=_normalize_path(rel_path),
                    title=title,
                    content=content,
                    read_error=read_error,
                )
            )

    documents.sort(key=lambda d: d.relative_path)
    return DirectoryTree(root=root_path, documents=documents)


def _normalize_path(path: Path | str) -> str:
    return PurePosixPath(path).as_posix()


def _extract_title(content: str, path: Path) -> str:
    frontmatter_title = _extract_frontmatter_title(content)
    if frontmatter_title:
        return frontmatter_title

    h1_match = re.search(r"^#\s+(.+)$", content, flags=re.MULTILINE)
    if h1_match:
        return h1_match.group(1).strip()

    fallback = path.stem.replace("_", " ").replace("-", " ")
    return fallback.title()


def _extract_frontmatter_title(content: str) -> str:
    if not content.startswith("---"):
        return ""
    parts = content.split("\n")
    # locate closing '---'
    try:
        end_index = parts[1:].index("---") + 1
    except ValueError:
        return ""
    raw_frontmatter = "\n".join(parts[1:end_index])
    try:
        data = safe_load(raw_frontmatter) or {}
    except Exception:
        return ""
    title = data.get("title") if isinstance(data, dict) else None
    return title if isinstance(title, str) else ""
