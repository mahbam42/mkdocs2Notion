"""Helpers for loading MkDocs projects and navigation structure."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mkdocs2notion.utils.simple_yaml import safe_load

from .directory import DirectoryTree, DocumentNode, load_directory
from .mkdocs_nav import NavNode, load_mkdocs_nav


@dataclass
class MkdocsProject:
    """Container for MkDocs configuration and loaded content."""

    docs_path: Path
    mkdocs_yml: Path | None
    directory_tree: DirectoryTree
    nav_tree: NavNode | None

    def ordered_documents(self) -> list[DocumentNode]:
        """Return documents in MkDocs navigation order when available.

        Returns:
            list[DocumentNode]: Documents sorted to match mkdocs navigation.
        """

        if not self.nav_tree:
            return list(self.directory_tree.documents)

        ordered: list[DocumentNode] = []

        def _walk(node: NavNode) -> None:
            for child in node.children:
                if child.file:
                    document = self.directory_tree.find_by_path(child.file)
                    if document:
                        ordered.append(document)
                if child.children:
                    _walk(child)

        _walk(self.nav_tree)
        return ordered

    def validate_structure(self) -> list[str]:
        """Validate that docs align with mkdocs.yml expectations.

        Returns:
            list[str]: Validation errors covering documents and navigation.
        """

        errors = self.directory_tree.validate()
        if self.nav_tree:
            errors.extend(self.nav_tree.validate(self.directory_tree))
            referenced = set(self.nav_tree.referenced_files())
            for document in self.directory_tree.documents:
                if document.relative_path not in referenced:
                    errors.append(
                        f"Document not listed in mkdocs nav: {document.relative_path}"
                    )
        return errors

    def pretty_nav(self) -> str:
        """Return a human-readable view of the navigation and documents."""

        if not self.nav_tree:
            return self.directory_tree.pretty()

        lines: list[str] = ["Docs (mkdocs navigation):"]

        def _walk(node: NavNode, indent: int) -> None:
            for child in node.children:
                prefix = "  " * indent + "- "
                if child.file:
                    doc = self.directory_tree.find_by_path(child.file)
                    label = doc.title if doc else child.title
                    lines.append(f"{prefix}{label} ({child.file})")
                else:
                    lines.append(f"{prefix}{child.title}")
                if child.children:
                    _walk(child, indent + 1)

        _walk(self.nav_tree, 1)
        return "\n".join(lines)


def load_mkdocs_project(
    target_path: Path, mkdocs_yml: Path | None = None
) -> MkdocsProject:
    """Load docs and navigation for a MkDocs project or plain directory.

    The ``target_path`` may be the MkDocs project root, a direct path to
    ``mkdocs.yml``, or a directory of markdown files when mkdocs configuration is
    unavailable.

    Args:
        target_path: Source location supplied by the CLI.
        mkdocs_yml: Optional explicit ``mkdocs.yml`` path.

    Returns:
        MkdocsProject: Loaded documents and optional navigation tree.
    """

    if not target_path.exists():
        raise FileNotFoundError(f"Docs path does not exist: {target_path}")

    config_path = _resolve_mkdocs_config(target_path, mkdocs_yml)
    config: dict[str, Any] = {}

    if config_path:
        config = safe_load(config_path.read_text(encoding="utf-8")) or {}
        docs_path = (config_path.parent / config.get("docs_dir", "docs")).resolve()
    else:
        docs_path = target_path

    if not docs_path.is_dir():
        raise FileNotFoundError(f"Docs directory not found: {docs_path}")

    directory_tree = load_directory(docs_path)
    nav_tree = load_mkdocs_nav(config_path, config=config) if config_path else None

    return MkdocsProject(
        docs_path=docs_path,
        mkdocs_yml=config_path,
        directory_tree=directory_tree,
        nav_tree=nav_tree,
    )


def _resolve_mkdocs_config(
    target_path: Path, override: Path | None
) -> Path | None:
    """Select the mkdocs.yml path to use, if any."""

    if override:
        return override
    if target_path.is_file() and target_path.name == "mkdocs.yml":
        return target_path
    candidate = target_path / "mkdocs.yml"
    return candidate if candidate.exists() else None
