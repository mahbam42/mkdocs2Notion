from __future__ import annotations

from pathlib import Path
from typing import Optional

from .loaders.directory import load_directory
from .loaders.mkdocs_nav import load_mkdocs_nav
from .loaders.id_map import PageIdMap
from .markdown.parser import parse_markdown
from .notion.api_adapter import NotionAdapter, get_default_adapter


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
    """
    Print what the tool *would* do without contacting the Notion API.
    """
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
    """
    Validate markdown files and mkdocs.yml without publishing.
    """
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


def _publish_to_notion(
    directory_tree,
    nav_tree,
    adapter: NotionAdapter,
    id_map: PageIdMap,
    parent_page_id: Optional[str],
) -> None:
    """
    Internal helper to publish pages in correct order based on nav_tree
    or filesystem fallback.
    """
    # TODO: implement page creation/update according to structure
    # iterate nav_tree if available, else directory_tree
    # for each markdown file:
    #   - parse with parse_markdown()
    #   - adapter.create_or_update_page()
    pass
