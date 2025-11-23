"""Entry points for running mkdocs2notion operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .loaders.directory import DirectoryTree, DocumentNode, load_directory
from .loaders.id_map import PageIdMap
from .loaders.mkdocs_nav import NavNode, load_mkdocs_nav
from .markdown.parser import parse_markdown
from .notion.api_adapter import NotionAdapter, get_default_adapter


@dataclass
class PublishItem:
    """A single document ready to be published to Notion."""

    document: DocumentNode
    parent_path: Optional[str]


def run_push(
    docs_path: Path,
    mkdocs_yml: Optional[Path],
    parent_page_id: Optional[str] = None,
) -> None:
    """
    Push a directory of Markdown files to Notion.

    Steps:
    - scan directory for markdown files
    - load optional mkdocs navigation tree
    - parse markdown → internal block structures
    - push pages to Notion using a Notion adapter
    """
    adapter = get_default_adapter()

    print(f"📁 Loading markdown directory: {docs_path}")
    directory_tree = load_directory(docs_path)

    nav_tree = None
    if mkdocs_yml:
        print(f"📄 Loading mkdocs.yml navigation: {mkdocs_yml}")
        nav_tree = load_mkdocs_nav(mkdocs_yml)

    id_map = PageIdMap.from_default_location(docs_path)

    print("📝 Pushing documents to Notion…")
    _publish_to_notion(
        directory_tree=directory_tree,
        nav_tree=nav_tree,
        adapter=adapter,
        id_map=id_map,
        parent_page_id=parent_page_id,
    )

    id_map.save()
    print("✅ Push complete.")


def run_dry_run(docs_path: Path, mkdocs_yml: Optional[Path]) -> None:
    """Print what the tool *would* do without contacting the Notion API."""

    print("🔎 Dry run: scanning directory…")
    directory_tree = load_directory(docs_path)

    if mkdocs_yml:
        nav_tree = load_mkdocs_nav(mkdocs_yml)
        print("🔍 Using mkdocs.yml structure:")
        print(nav_tree.pretty())
    else:
        nav_tree = None

    print("📄 Directory structure:")
    print(directory_tree.pretty())

    print("\n(no changes made)")


def run_validate(docs_path: Path, mkdocs_yml: Optional[Path]) -> None:
    """Validate markdown files and mkdocs.yml without publishing."""

    print("🔧 Validating docs…")
    directory_tree = load_directory(docs_path)

    errors: list[str] = directory_tree.validate()

    if mkdocs_yml:
        nav_tree = load_mkdocs_nav(mkdocs_yml)
        errors.extend(nav_tree.validate(directory_tree))

    if errors:
        print("❌ Validation errors:")
        for e in errors:
            print(f" - {e}")
    else:
        print("✅ All checks passed.")


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
    adapter: NotionAdapter,
    id_map: PageIdMap,
    parent_page_id: Optional[str],
) -> None:
    """Publish documents to Notion respecting navigation ordering."""

    publish_plan = build_publish_plan(directory_tree, nav_tree)

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
        )
        id_map.set(item.document.relative_path, page_id)
