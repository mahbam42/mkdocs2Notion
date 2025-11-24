"""Entry points for running mkdocs2notion operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Protocol

from .loaders.directory import DirectoryTree, DocumentNode
from .loaders.id_map import PageIdMap
from .loaders.mkdocs_nav import NavNode
from .loaders.mkdocs_project import MkdocsProject, load_mkdocs_project
from .markdown.parser import MarkdownParseError, parse_markdown

if TYPE_CHECKING:  # pragma: no cover
    from .notion.api_adapter import NotionAdapter


class PublishProgress(Protocol):
    """Reporting hook for publishing progress."""

    def start(self, total: int) -> None:
        """Begin tracking publish progress.

        Args:
            total: Total number of documents that will be published.
        """

    def advance(self, document: DocumentNode) -> None:
        """Advance the progress tracker when a document is published.

        Args:
            document: Document that has just been published.
        """

    def finish(self) -> None:
        """Finalize progress tracking."""


@dataclass
class PublishItem:
    """A single document ready to be published to Notion."""

    document: DocumentNode
    parent_path: Optional[str]


def run_push(
    docs_path: Path,
    mkdocs_yml: Optional[Path],
    parent_page_id: Optional[str] = None,
    fresh: bool = False,
    progress: PublishProgress | None = None,
) -> None:
    """
    Push a directory of Markdown files to Notion.

    Steps:
    - scan directory for markdown files
    - load optional mkdocs navigation tree
    - parse markdown → internal block structures
    - push pages to Notion using a Notion adapter
    """
    from .notion.api_adapter import get_default_adapter

    adapter = get_default_adapter()

    project: MkdocsProject = load_mkdocs_project(docs_path, mkdocs_yml)

    print(f"📁 Loading markdown directory: {project.docs_path}")
    if project.mkdocs_yml:
        print(f"📄 Loading mkdocs.yml navigation: {project.mkdocs_yml}")

    id_map = PageIdMap.from_default_location(project.docs_path, ignore_existing=fresh)

    print("📝 Pushing documents to Notion…")
    _publish_to_notion(
        directory_tree=project.directory_tree,
        nav_tree=project.nav_tree,
        adapter=adapter,
        id_map=id_map,
        parent_page_id=parent_page_id,
        progress=progress,
    )

    id_map.save()
    print("✅ Push complete.")


def run_dry_run(docs_path: Path, mkdocs_yml: Optional[Path]) -> None:
    """Print what the tool *would* do without contacting the Notion API."""

    print("🔎 Dry run: scanning directory…")
    project: MkdocsProject = load_mkdocs_project(docs_path, mkdocs_yml)

    if project.mkdocs_yml:
        print("🔍 Using mkdocs.yml structure:")
        print(project.nav_tree.pretty())

    print("📄 Directory structure:")
    print(project.pretty_nav())

    print("\n(no changes made)")


def run_validate(docs_path: Path, mkdocs_yml: Optional[Path]) -> int:
    """Validate markdown files and mkdocs.yml without publishing."""

    print("🔧 Validating docs…")
    project: MkdocsProject = load_mkdocs_project(docs_path, mkdocs_yml)

    errors = project.validate_structure()

    for document in project.directory_tree.documents:
        try:
            parse_markdown(document.content)
        except MarkdownParseError as exc:
            errors.append(f"{document.relative_path}: {exc}")

    if errors:
        print("❌ Validation errors:")
        for e in errors:
            print(f" - {e}")
        print(f"Found {len(errors)} validation error(s).")
        return 1
    else:
        print("✅ All checks passed.")
    return 0


def build_publish_plan(
    directory_tree: DirectoryTree, nav_tree: Optional[NavNode]
) -> list[PublishItem]:
    """Create an ordered list of documents to publish.

    Args:
        directory_tree: Loaded directory tree.
        nav_tree: Optional mkdocs navigation tree.

    Returns:
        list[PublishItem]: Ordered publish plan respecting nav ordering when
            available, otherwise filesystem order.
    """

    if nav_tree is None:
        return [
            PublishItem(document=doc, parent_path=None)
            for doc in directory_tree.documents
        ]

    plan: list[PublishItem] = []

    def _walk(node: NavNode, parent_path: Optional[str]) -> None:
        for child in node.children:
            next_parent = parent_path
            if child.file:
                document = directory_tree.find_by_path(child.file)
                if document:
                    plan.append(PublishItem(document=document, parent_path=parent_path))
                    next_parent = document.relative_path
            if child.children:
                _walk(child, next_parent)

    _walk(nav_tree, None)
    return plan


def _publish_to_notion(
    directory_tree: DirectoryTree,
    nav_tree: Optional[NavNode],
    adapter: "NotionAdapter",
    id_map: PageIdMap,
    parent_page_id: Optional[str],
    progress: PublishProgress | None = None,
) -> None:
    """Publish documents to Notion respecting navigation ordering."""

    publish_plan = build_publish_plan(directory_tree, nav_tree)

    if progress:
        progress.start(len(publish_plan))

    try:
        for item in publish_plan:
            parsed_page = parse_markdown(item.document.content)
            blocks = list(parsed_page.children)
            existing_page_id = id_map.get(item.document.relative_path)

            resolved_parent_id = (
                id_map.get(item.parent_path) if item.parent_path else parent_page_id
            )
            page_id = adapter.create_or_update_page(
                title=item.document.title,
                parent_page_id=resolved_parent_id,
                page_id=existing_page_id,
                blocks=blocks,
                source_path=item.document.path,
            )
            id_map.set(item.document.relative_path, page_id)

            if progress:
                progress.advance(item.document)
    finally:
        if progress:
            progress.finish()
