"""mkdocs.yml navigation parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, List

from mkdocs2notion.utils.simple_yaml import safe_load

from .directory import DirectoryTree


@dataclass
class NavNode:
    """Represents a single entry in the mkdocs navigation tree."""

    title: str
    file: str | None = None
    children: list["NavNode"] = field(default_factory=list)

    def validate(self, directory_tree: DirectoryTree) -> list[str]:
        """Validate that nav references align with discovered documents.

        Args:
            directory_tree: The directory tree produced by ``load_directory``.

        Returns:
            list[str]: Validation error messages.
        """

        errors: list[str] = []
        known_files = directory_tree.paths()
        seen_files: set[str] = set()

        def _walk(node: NavNode, stack: set[int]) -> None:
            if id(node) in stack:
                errors.append(f"Circular reference detected at {node.title}")
                return

            next_stack = set(stack)
            next_stack.add(id(node))

            if node.file:
                if node.file not in known_files:
                    errors.append(f"Nav references missing file: {node.file}")
                if node.file in seen_files:
                    errors.append(f"Duplicate nav entry for file: {node.file}")
                seen_files.add(node.file)

            for child in node.children:
                _walk(child, next_stack)

        _walk(self, set())
        return errors

    def referenced_files(self) -> list[str]:
        """Return all file paths referenced by this navigation tree.

        Returns:
            list[str]: File paths gathered in the order they appear in ``nav``.
        """

        files: list[str] = []

        def _walk(node: NavNode) -> None:
            if node.file:
                files.append(node.file)
            for child in node.children:
                _walk(child)

        _walk(self)
        return files

    def pretty(self) -> str:
        """Return a formatted representation of the navigation tree."""

        lines: List[str] = ["Navigation:"]

        def _render(nodes: Iterable[NavNode], indent: int) -> None:
            for node in nodes:
                prefix = "  " * indent + "- "
                if node.children:
                    label = f"{node.title}"
                    if node.file:
                        label = f"{label} → {node.file}"
                    lines.append(prefix + label)
                    _render(node.children, indent + 1)
                else:
                    target = f" → {node.file}" if node.file else ""
                    lines.append(prefix + f"{node.title}{target}")

        _render(self.children, 1)
        return "\n".join(lines)


def load_mkdocs_nav(path: Path, *, config: dict[str, Any] | None = None) -> NavNode:
    """Parse mkdocs.yml and return a navigation tree.

    Args:
        path: Path to ``mkdocs.yml``.
        config: Optional pre-parsed mkdocs configuration.

    Returns:
        NavNode: Root navigation node whose children mirror mkdocs ordering.
    """

    data = config if config is not None else safe_load(path.read_text(encoding="utf-8")) or {}
    nav_config = data.get("nav")
    if nav_config is None:
        return NavNode(title="root")
    if not isinstance(nav_config, list):
        raise ValueError("mkdocs nav must be a list")

    children = _parse_nav_list(nav_config)
    return NavNode(title="root", children=children)


def _parse_nav_list(items: list[Any]) -> list[NavNode]:
    nodes: list[NavNode] = []
    for item in items:
        if isinstance(item, str):
            normalized_file = _normalize_path(item)
            nodes.append(NavNode(title=_title_from_path(item), file=normalized_file))
            continue

        if isinstance(item, dict):
            if len(item) != 1:
                raise ValueError("Each nav entry must have a single key")
            title, value = next(iter(item.items()))
            if isinstance(value, str):
                nodes.append(
                    NavNode(title=title, file=_normalize_path(value)),
                )
            elif isinstance(value, list):
                nodes.append(NavNode(title=title, children=_parse_nav_list(value)))
            else:
                raise ValueError(f"Unsupported nav entry for {title}")
            continue

        raise ValueError(f"Unsupported nav entry: {item}")

    return nodes


def _normalize_path(path: str) -> str:
    return PurePosixPath(path).as_posix()


def _title_from_path(path: str) -> str:
    stem = Path(path).stem.replace("_", " ").replace("-", " ")
    return stem[:1].upper() + stem[1:]
