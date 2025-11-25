from pathlib import Path
from typing import Any, List, Optional

from mkdocs2notion.loaders.directory import DocumentNode, load_directory
<<<<<<< HEAD
from mkdocs2notion.loaders.mkdocs_nav import NavNode, _page_key, load_mkdocs_nav
from mkdocs2notion.loaders.id_map import PageIdMap
from mkdocs2notion.markdown.elements import LinkSpan, Page, Paragraph
=======
from mkdocs2notion.loaders.id_map import PageIdMap
from mkdocs2notion.loaders.mkdocs_nav import _page_key, load_mkdocs_nav
>>>>>>> 14f64fc
from mkdocs2notion.runner import PublishProgress, _publish_to_notion, build_publish_plan
from mkdocs2notion.runner import _rewrite_internal_links


class RecordingAdapter:
    def __init__(self) -> None:
        self.created: list[tuple[str, Optional[str], List[Any]]] = []
        self.updated: list[tuple[str, List[Any]]] = []

    def create_page(
        self,
        title: str,
        parent_page_id: Optional[str],
        blocks: List[Any],
        source_path=None,
    ) -> str:
        page_id = f"page-{len(self.created) + 1}"
        self.created.append((title, parent_page_id, blocks))
        return page_id

    def update_page(self, page_id: str, blocks: List[Any], source_path=None) -> None:
        self.updated.append((page_id, blocks))

    def get_page(self, page_id: str) -> Any:  # pragma: no cover
        return {"id": page_id}

    def create_or_update_page(
        self,
        title: str,
        parent_page_id: Optional[str],
        page_id: Optional[str],
        blocks: List[Any],
        source_path=None,
    ) -> str:
        if page_id:
            self.update_page(page_id, blocks, source_path=source_path)
            return page_id
        return self.create_page(
            title,
            parent_page_id,
            blocks,
            source_path=source_path,
        )


class RecordingProgress(PublishProgress):
    def __init__(self) -> None:
        self.started_with: int | None = None
        self.advanced: list[str] = []
        self.finished = False

    def start(self, total: int) -> None:
        self.started_with = total

    def advance(self, document: DocumentNode) -> None:
        self.advanced.append(document.relative_path)

    def finish(self) -> None:
        self.finished = True


def test_build_publish_plan_uses_nav(sample_docs_path: Path) -> None:
    directory_tree = load_directory(sample_docs_path)
    nav_tree = load_mkdocs_nav(sample_docs_path / "mkdocs.yml")

    plan = build_publish_plan(directory_tree, nav_tree)

    assert [item.nav_node.title for item in plan] == [
        "Home",
        "Guide",
        "Overview",
        "Deep Dive",
    ]
    assert plan[2].parent_key == _page_key(nav_tree.children[1])


def test_publish_reports_progress(sample_docs_path: Path, tmp_path: Path) -> None:
    directory_tree = load_directory(sample_docs_path)
    nav_tree = load_mkdocs_nav(sample_docs_path / "mkdocs.yml")
    adapter = RecordingAdapter()
    progress = RecordingProgress()
    id_map = PageIdMap(path=tmp_path / "ids.json")

    _publish_to_notion(
        directory_tree,
        nav_tree,
        adapter,
        id_map,
        parent_page_id="root",
        progress=progress,
    )

    assert progress.started_with == 4
    assert progress.finished


def test_internal_links_use_shareable_notion_urls() -> None:
    nav_root = NavNode(title="root", children=[NavNode(title="Home", file="index.md")])
    nav_root.assign_paths()
    page = Page(
        title="Home",
        children=(Paragraph(text="", inlines=(LinkSpan(text="Start", target="nav://index.md"),)),),
    )

    rewritten, unresolved = _rewrite_internal_links(page, nav_root, {"index.md": "1234-5678"})

    rewritten_link = rewritten.children[0].inlines[0]
    assert isinstance(rewritten_link, LinkSpan)
    assert rewritten_link.target == "https://www.notion.so/12345678"
    assert unresolved == []
