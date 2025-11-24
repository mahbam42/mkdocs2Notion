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
    parent: "NavNode | None" = field(default=None, repr=False)
    stub: bool = False
    nav_path: str | None = None

    def assign_paths(self, ancestors: list[str] | None = None) -> None:
        """Assign hierarchical nav paths used for stable identifiers."""

        ancestors = ancestors or []
        if self.parent is None:
            base = ancestors
        else:
            base = [*ancestors, _slugify(self.title)]
        self.nav_path = "/".join(base) if base else None
        for child in self.children:
            child.parent = self
            child.assign_paths(base)

    def iter_nodes(self) -> Iterable["NavNode"]:
        yield self
        for child in self.children:
            yield from child.iter_nodes()

    def validate(self, directory_tree: DirectoryTree) -> tuple[list[str], list[str]]:
        """Validate that nav references align with discovered documents.

        Returns:
            tuple[list[str], list[str]]: (errors, warnings)
        """

        errors: list[str] = []
        warnings: list[str] = []
        known_files = directory_tree.paths()
        seen_files: set[str] = set()
        seen_titles: dict[str, set[str]] = {}
        seen_slugs: set[str] = set()

        def _walk(node: NavNode, stack: set[int]) -> None:
            if id(node) in stack:
                errors.append(f"Circular reference detected at {node.title}")
                return

            next_stack = set(stack)
            next_stack.add(id(node))

            siblings = seen_titles.setdefault(node.parent.nav_path if node.parent else "root", set())
            if node.title in siblings:
                errors.append(
                    f"Duplicate page title '{node.title}' under {node.parent.title if node.parent else 'root'}"
                )
            siblings.add(node.title)

            if node.nav_path:
                slug = _slugify(node.nav_path)
                if slug in seen_slugs:
                    warnings.append(f"Duplicate nav slug detected: {node.nav_path}")
                seen_slugs.add(slug)

            if not node.file and not node.children:
                warnings.append(
                    f"Nav item '{node.title}' is missing content; creating empty container"
                )

            if node.file:
                if not node.file.lower().endswith(".md"):
                    warnings.append(
                        f"Nav item '{node.title}' → '{node.file}' is not a Markdown file"
                    )
                if node.file not in known_files:
                    warnings.append(
                        f"Nav item '{node.title}' → '{node.file}' not found. Created stub page."
                    )
                    node.stub = True
                if node.file in seen_files:
                    errors.append(f"Duplicate nav entry for file: {node.file}")
                seen_files.add(node.file)

            for child in node.children:
                _walk(child, next_stack)

        _walk(self, set())
        referenced = set(self.referenced_files())
        for document in directory_tree.documents:
            if document.relative_path not in referenced:
                warnings.append(
                    f"Document not listed in mkdocs nav: {document.relative_path}"
                )
        return errors, warnings

    def to_markdown_listing(self) -> str:
        """Render the navigation tree as a Markdown callout with bullets."""

        if not self.children:
            return ""

        lines: list[str] = ['!!! note "📚 Navigation"']

        def _walk(nodes: Iterable[NavNode], depth: int) -> None:
            for node in nodes:
                indent = "    " * (depth + 1)
                target = _page_key(node)
                link_target = f"nav://{target}"
                lines.append(f"{indent}- [{node.title}]({link_target})")
                if node.children:
                    _walk(node.children, depth + 1)

        _walk(self.children, 0)
        return "\n".join(lines)

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
    root = NavNode(title="root", children=children)
    root.assign_paths()
    return root


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


def _page_key(node: NavNode) -> str:
    if node.file:
        return node.file
    return node.nav_path or node.title


def _slugify(text: str) -> str:
    return PurePosixPath(text.replace(" ", "-").lower()).as_posix()
