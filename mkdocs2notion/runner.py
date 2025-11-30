"""Entry points for running mkdocs2notion operations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Protocol

from .loaders.directory import DirectoryTree, DocumentNode
from .loaders.id_map import PageIdMap
from .loaders.mkdocs_nav import NavNode, _page_key
from .loaders.mkdocs_project import MkdocsProject, load_mkdocs_project
from .markdown.elements import (
    Block,
    BulletedListItem,
    Callout,
    Heading,
    InlineSpan,
    LinkSpan,
    NumberedListItem,
    Page,
    Paragraph,
    StrikethroughSpan,
    Table,
    TableCell,
    TextSpan,
    Toggle,
)
from .markdown.parser import MarkdownParseError, parse_markdown
from .utils.logging import WarningLogger

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
    *,
    strict: bool = False,
    logger: WarningLogger | None = None,
) -> None:
    """Push a directory of Markdown files to Notion.

    Args:
        docs_path: Path to a docs directory or mkdocs project root.
        mkdocs_yml: Optional mkdocs.yml path for navigation ordering.
        parent_page_id: Optional Notion parent page ID overriding ``NOTION_PARENT_PAGE_ID``.
        fresh: When True, ignore any cached page IDs and rebuild the local map.
        progress: Optional reporter for publish progress.
        strict: When True, abort before publishing when parse warnings are present.
        logger: Optional warning logger to reuse across parsing and publishing.

    Raises:
        SystemExit: If ``strict`` is True and parsing emitted warnings.
    """
    from .notion.api_adapter import get_default_adapter

    adapter = get_default_adapter()
    project: MkdocsProject = load_mkdocs_project(docs_path, mkdocs_yml)
    active_logger = logger or WarningLogger(
        project.docs_path.name, source_root=project.docs_path
    )

    for document in project.directory_tree.documents:
        parse_markdown(
            document.content,
            source_file=document.relative_path,
            logger=active_logger,
        )

    if strict and active_logger.has_warnings():
        print(active_logger.summary())
        raise SystemExit(1)

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
        logger=active_logger,
    )

    id_map.save()
    if active_logger.has_warnings():
        print(active_logger.summary())
    print("✅ Push complete.")


def run_dry_run(
    docs_path: Path, mkdocs_yml: Optional[Path], *, logger: WarningLogger | None = None
) -> WarningLogger:
    """Print what the tool *would* do without contacting the Notion API.

    Args:
        docs_path: Path to a docs directory or mkdocs project root.
        mkdocs_yml: Optional mkdocs.yml path for navigation ordering.
        logger: Optional warning logger to reuse when reporting parsing issues.

    Notes:
        The caller enforces strict-mode exits; this function only gathers and
        reports warnings.

    Returns:
        WarningLogger: Captured warnings from parsing the provided docs.
    """

    print("🔎 Dry run: scanning directory…")
    project: MkdocsProject = load_mkdocs_project(docs_path, mkdocs_yml)
    active_logger = logger or WarningLogger(
        project.docs_path.name, source_root=project.docs_path
    )

    for document in project.directory_tree.documents:
        parse_markdown(
            document.content,
            source_file=document.relative_path,
            logger=active_logger,
        )

    nav_tree = project.nav_tree
    if project.mkdocs_yml and nav_tree:
        print("🔍 Using mkdocs.yml structure:")
        print(nav_tree.pretty())

    print("📄 Directory structure:")
    print(project.pretty_nav())

    if active_logger.has_warnings():
        print(active_logger.summary())
    print("\n(no changes made)")
    return active_logger


def run_validate(
    docs_path: Path, mkdocs_yml: Optional[Path], *, strict: bool = False
) -> int:
    """Validate markdown files and mkdocs.yml without publishing.

    Args:
        docs_path: Path to a docs directory or mkdocs project root.
        mkdocs_yml: Optional mkdocs.yml path for navigation ordering checks.
        strict: When True, treat warnings as failures and return a non-zero code.

    Returns:
        int: 0 when all checks pass; 1 when validation errors or strict warnings occur.
    """

    print("🔧 Validating docs…")
    if strict:
        print("Strict mode enabled: warnings will block validation.")
    project: MkdocsProject = load_mkdocs_project(docs_path, mkdocs_yml)
    logger = WarningLogger(project.docs_path.name, source_root=project.docs_path)

    result = project.validate_structure()

    errors = list(result.errors)
    warnings = list(result.warnings)

    for document in project.directory_tree.documents:
        try:
            parse_markdown(
                document.content,
                source_file=document.relative_path,
                logger=logger,
            )
        except MarkdownParseError as exc:
            errors.append(f"{document.relative_path}: {exc}")

    parse_warnings = [warning.format() for warning in logger.warnings]
    errors.extend(parse_warnings)

    if logger.has_warnings():
        print(logger.summary())

    if errors:
        print("❌ Validation errors:")
        for e in errors:
            print(f" - {e}")
        print(f"Found {len(errors)} validation error(s).")
        return 1

    if warnings:
        print("⚠️ Validation warnings:")
        for warning in warnings:
            print(f" - {warning}")
        print(f"Found {len(warnings)} warning(s).")
        if strict:
            return 1

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
            else:
                document = _stub_document(directory_tree.root, child)
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
    logger: WarningLogger | None = None,
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

        active_logger = logger or WarningLogger("docs")
        for item in publish_plan:
            content = _prepare_document_content(item.document, nav_tree)
            parsed_page = parse_markdown(
                content,
                source_file=item.document.relative_path if item.document else "",
                logger=active_logger,
            )
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

    def _notion_page_url(page_id: str) -> str:
        normalized_id = page_id.replace("-", "")
        return f"https://www.notion.so/{normalized_id}"

    def _rewrite_inline(inline: TextSpan | LinkSpan | StrikethroughSpan) -> InlineSpan:
        if isinstance(inline, LinkSpan):
            if not nav_tree:
                return inline
            if inline.target.startswith("#"):
                return inline
            if inline.target.startswith(("http://", "https://", "mailto:", "tel:")):
                return inline
            if "://" in inline.target and not inline.target.startswith("nav://"):
                return inline
            target_id = _resolve_link(inline.target)
            if target_id:
                return LinkSpan(text=inline.text, target=_notion_page_url(target_id))
            unresolved.append(inline.target)
            return TextSpan(text=inline.text)
        if isinstance(inline, StrikethroughSpan) and inline.inlines:
            return StrikethroughSpan(
                text=inline.text,
                inlines=tuple(_rewrite_inline(child) for child in inline.inlines),
            )
        return inline

    def _rewrite_block(block: Block) -> Block:
        if isinstance(block, Heading):
            return Heading(
                level=block.level,
                text=block.text,
                inlines=tuple(_rewrite_inline(i) for i in block.inlines),
                source_line=block.source_line,
                source_file=block.source_file,
            )
        if isinstance(block, Paragraph):
            return Paragraph(
                text=block.text,
                inlines=tuple(_rewrite_inline(i) for i in block.inlines),
                source_line=block.source_line,
                source_file=block.source_file,
            )
        if isinstance(block, BulletedListItem):
            return BulletedListItem(
                text=block.text,
                inlines=tuple(_rewrite_inline(i) for i in block.inlines),
                children=tuple(_rewrite_block(child) for child in block.children),
                source_line=block.source_line,
                source_file=block.source_file,
            )
        if isinstance(block, NumberedListItem):
            return NumberedListItem(
                text=block.text,
                inlines=tuple(_rewrite_inline(i) for i in block.inlines),
                children=tuple(_rewrite_block(child) for child in block.children),
                source_line=block.source_line,
                source_file=block.source_file,
            )
        if isinstance(block, Toggle):
            return Toggle(
                title=block.title,
                inlines=tuple(_rewrite_inline(i) for i in block.inlines),
                children=tuple(_rewrite_block(child) for child in block.children),
                source_line=block.source_line,
                source_file=block.source_file,
            )
        if isinstance(block, Callout):
            return Callout(
                title=block.title,
                callout_type=block.callout_type,
                icon=block.icon,
                children=tuple(_rewrite_block(child) for child in block.children),
                source_line=block.source_line,
                source_file=block.source_file,
            )
        if isinstance(block, Table):
            headers = tuple(
                TableCell(
                    text=cell.text,
                    inlines=tuple(_rewrite_inline(i) for i in cell.inlines),
                    source_line=cell.source_line,
                    source_file=cell.source_file,
                )
                for cell in block.headers
            )
            rows = []
            for row in block.rows:
                rows.append(
                    tuple(
                        TableCell(
                            text=cell.text,
                            inlines=tuple(_rewrite_inline(i) for i in cell.inlines),
                            source_line=cell.source_line,
                            source_file=cell.source_file,
                        )
                        for cell in row
                    )
                )
            return Table(
                headers=headers,
                rows=tuple(rows),
                source_line=block.source_line,
                source_file=block.source_file,
            )
        rewritten_children = tuple(_rewrite_block(child) for child in block.children)
        if rewritten_children != block.children:
            return replace(block, children=rewritten_children)
        return block

    rewritten_children = tuple(_rewrite_block(child) for child in page.children)
    return Page(title=page.title, children=rewritten_children), unresolved
