"""Entry points for running mkdocs2notion operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Protocol

from .loaders.directory import DirectoryTree, DocumentNode
from .loaders.id_map import PageIdMap
from .loaders.mkdocs_nav import NavNode, _page_key
from .loaders.mkdocs_project import MkdocsProject, load_mkdocs_project
from .markdown.elements import (
    Admonition,
    DefinitionItem,
    DefinitionList,
    Element,
    Heading,
    InlineContent,
    Link,
    List as ListElement,
    ListItem,
    Page,
    Paragraph,
    Strikethrough,
    Table,
    TableCell,
    TableRow,
    TaskItem,
    TaskList,
    Text,
)
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
    """A single nav entry ready to be published to Notion."""

    nav_node: NavNode
    document: DocumentNode | None
    parent_key: Optional[str]


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

    nav_tree = project.nav_tree
    if project.mkdocs_yml and nav_tree:
        print("🔍 Using mkdocs.yml structure:")
        print(nav_tree.pretty())

    print("📄 Directory structure:")
    print(project.pretty_nav())

    print("\n(no changes made)")


def run_validate(docs_path: Path, mkdocs_yml: Optional[Path]) -> int:
    """Validate markdown files and mkdocs.yml without publishing."""

    print("🔧 Validating docs…")
    project: MkdocsProject = load_mkdocs_project(docs_path, mkdocs_yml)

    result = project.validate_structure()

    for document in project.directory_tree.documents:
        try:
            parse_markdown(document.content)
        except MarkdownParseError as exc:
            result.errors.append(f"{document.relative_path}: {exc}")

    if result.warnings:
        for warning in result.warnings:
            print(f"[WARN] {warning}")

    if result.errors:
        print("❌ Validation errors:")
        for e in result.errors:
            print(f" - {e}")
        print(f"Found {len(result.errors)} validation error(s).")
        return 1
    else:
        print("✅ All checks passed.")
    return 0


def build_publish_plan(
    directory_tree: DirectoryTree, nav_tree: Optional[NavNode]
) -> list[PublishItem]:
    """Create an ordered list of nav entries to publish."""

    if nav_tree is None:
        fallback_root = NavNode(title="root", children=[NavNode(title=doc.title, file=doc.relative_path) for doc in directory_tree.documents])
        fallback_root.assign_paths()
        nav_tree = fallback_root

    plan: list[PublishItem] = []

    def _walk(node: NavNode, parent_key: Optional[str]) -> None:
        for child in node.children:
            document = None
            if child.file:
                document = directory_tree.find_by_path(child.file)
                if document is None:
                    document = _stub_document(directory_tree.root, child)
                    print(
                        f"[WARN] Nav item '{child.title}' → '{child.file}' not found. Created stub page."
                    )
            elif not child.children:
                document = _stub_document(directory_tree.root, child)
                print(
                    f"[WARN] Nav item '{child.title}' is empty; creating stub container."
                )
            plan.append(
                PublishItem(nav_node=child, document=document, parent_key=parent_key)
            )
            _walk(child, _page_key(child))

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
        # First pass: create empty shells to resolve internal references
        for item in publish_plan:
            existing_page_id = id_map.get(_page_key(item.nav_node))
            resolved_parent_id = (
                id_map.get(item.parent_key) if item.parent_key else parent_page_id
            )
            page_id = adapter.create_or_update_page(
                title=item.nav_node.title,
                parent_page_id=resolved_parent_id,
                page_id=existing_page_id,
                blocks=[],
                source_path=item.document.path if item.document else None,
            )
            id_map.set(_page_key(item.nav_node), page_id)

        link_targets = {_page_key(item.nav_node): id_map.get(_page_key(item.nav_node)) for item in publish_plan}

        for item in publish_plan:
            content = _prepare_document_content(item.document, nav_tree)
            parsed_page = parse_markdown(content)
            rewritten_page, unresolved = _rewrite_internal_links(
                parsed_page, nav_tree, link_targets
            )
            for missing in unresolved:
                print(f"[WARN] Unresolved link: {missing}")
            blocks = list(rewritten_page.children)
            resolved_parent_id = (
                id_map.get(item.parent_key) if item.parent_key else parent_page_id
            )
            adapter.create_or_update_page(
                title=item.nav_node.title,
                parent_page_id=resolved_parent_id,
                page_id=id_map.get(_page_key(item.nav_node)),
                blocks=blocks,
                source_path=item.document.path if item.document else None,
            )

            if progress and item.document:
                progress.advance(item.document)
    finally:
        if progress:
            progress.finish()


def _prepare_document_content(
    document: DocumentNode | None, nav_tree: Optional[NavNode]
) -> str:
    """Return the Markdown content to send to Notion.

    When an mkdocs navigation tree is available, the navigation outline is
    appended to ``index.md`` so Notion readers can see the intended structure.

    Args:
        document: Document being published.
        nav_tree: Optional mkdocs navigation tree.

    Returns:
        str: Markdown content with navigation injected when applicable.
    """

    if document is None:
        return ""

    if not nav_tree or document.relative_path != "index.md":
        return document.content

    nav_listing = nav_tree.to_markdown_listing()
    if not nav_listing:
        return document.content

    base_content = document.content.rstrip()
    spacer = "\n\n" if base_content else ""
    return f"{base_content}{spacer}{nav_listing}\n"


def _stub_document(root: Path, nav_node: NavNode) -> DocumentNode:
    relative = nav_node.file or f"nav/{_page_key(nav_node)}.md"
    return DocumentNode(
        path=root / relative,
        relative_path=relative,
        title=nav_node.title,
        content="",
        stub=True,
    )

def _rewrite_internal_links(
    page: "Page", nav_tree: Optional[NavNode], link_targets: dict[str, str | None]
) -> tuple["Page", list[str]]:
    unresolved: list[str] = []

    def _normalize_target(target: str) -> str:
        cleaned = target
        if cleaned.startswith("nav://"):
            return cleaned.removeprefix("nav://")
        anchor = ""
        if "#" in cleaned:
            cleaned, anchor = cleaned.split("#", 1)
        if cleaned.endswith(".md"):
            cleaned = cleaned[:-3]
        return cleaned or anchor

    def _resolve_link(target: str) -> str | None:
        normalized = _normalize_target(target)
        if normalized in link_targets:
            return link_targets.get(normalized)
        if f"{normalized}.md" in link_targets:
            return link_targets.get(f"{normalized}.md")
        return None

    def _rewrite_inline(inline: InlineContent) -> InlineContent:
        if isinstance(inline, Link):
            target_id = _resolve_link(inline.target) if nav_tree else None
            if target_id:
                return Link(text=inline.text, target=f"notion://{target_id}")
            unresolved.append(inline.target)
            return Text(text=inline.text)
        if isinstance(inline, Strikethrough) and inline.inlines:
            return Strikethrough(
                text=inline.text,
                inlines=tuple(_rewrite_inline(child) for child in inline.inlines),
            )
        return inline

    def _rewrite_element(element: Element) -> Element:
        if isinstance(element, Heading):
            return Heading(
                level=element.level,
                text=element.text,
                inlines=tuple(_rewrite_inline(i) for i in element.inlines),
            )
        if isinstance(element, Paragraph):
            return Paragraph(
                text=element.text,
                inlines=tuple(_rewrite_inline(i) for i in element.inlines),
            )
        if isinstance(element, ListElement):
            return ListElement(
                items=tuple(
                    ListItem(
                        text=item.text,
                        inlines=tuple(_rewrite_inline(i) for i in item.inlines),
                    )
                    for item in element.items
                ),
                ordered=element.ordered,
            )
        if isinstance(element, TaskList):
            return TaskList(
                items=tuple(
                    TaskItem(
                        text=item.text,
                        checked=item.checked,
                        inlines=tuple(_rewrite_inline(i) for i in item.inlines),
                    )
                    for item in element.items
                )
            )
        if isinstance(element, Admonition):
            return Admonition(
                kind=element.kind,
                title=element.title,
                content=tuple(_rewrite_element(child) for child in element.content),
            )
        if isinstance(element, DefinitionList):
            return DefinitionList(
                items=tuple(
                    DefinitionItem(
                        term=item.term,
                        inlines=tuple(_rewrite_inline(i) for i in item.inlines),
                        descriptions=tuple(
                            _rewrite_element(desc) for desc in item.descriptions
                        ),
                    )
                    for item in element.items
                )
            )
        if isinstance(element, Table):
            return Table(
                rows=tuple(
                    TableRow(
                        cells=tuple(
                            TableCell(
                                text=cell.text,
                                inlines=tuple(
                                    _rewrite_inline(inline) for inline in cell.inlines
                                ),
                                is_header=cell.is_header,
                            )
                            for cell in row.cells
                        ),
                        is_header=row.is_header,
                    )
                    for row in element.rows
                )
            )
        return element

    rewritten_children = tuple(_rewrite_element(child) for child in page.children)
    return Page(title=page.title, children=rewritten_children), unresolved
