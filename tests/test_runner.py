from pathlib import Path
from typing import Any, List, Optional

from mkdocs2notion.loaders.directory import DocumentNode, load_directory
from mkdocs2notion.loaders.id_map import PageIdMap
from mkdocs2notion.loaders.mkdocs_nav import load_mkdocs_nav
from mkdocs2notion.markdown.elements import Heading, List as ListElement
from mkdocs2notion.notion.api_adapter import NotionAdapter
from mkdocs2notion.runner import _publish_to_notion, build_publish_plan


class RecordingAdapter(NotionAdapter):
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

    def get_page(self, page_id: str) -> Any:  # pragma: no cover - not used in tests
        return {"id": page_id}


class RecordingProgress:
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

    assert [item.document.relative_path for item in plan] == [
        "index.md",
        "guide.md",
        "nested/deep.md",
    ]
    # pages under a nav section without its own file should use the shared parent
    assert plan[2].parent_path is None


def test_publish_to_notion_sets_ids(sample_docs_path: Path, tmp_path: Path) -> None:
    directory_tree = load_directory(sample_docs_path)
    nav_tree = load_mkdocs_nav(sample_docs_path / "mkdocs.yml")
    adapter = RecordingAdapter()
    id_map = PageIdMap(path=tmp_path / "ids.json")

    _publish_to_notion(directory_tree, nav_tree, adapter, id_map, parent_page_id="root")

    assert id_map.get("index.md") is not None
    assert id_map.get("guide.md") is not None
    assert id_map.get("nested/deep.md") is not None
    # parent relationship for nested entry should target provided root when no parent path
    assert adapter.created[2][1] == "root"


def test_publish_reports_progress(sample_docs_path: Path, tmp_path: Path) -> None:
    directory_tree = load_directory(sample_docs_path)
    nav_tree = load_mkdocs_nav(sample_docs_path / "mkdocs.yml")
    adapter = RecordingAdapter()
    id_map = PageIdMap(path=tmp_path / "ids.json")
    progress = RecordingProgress()

    _publish_to_notion(
        directory_tree,
        nav_tree,
        adapter,
        id_map,
        parent_page_id="root",
        progress=progress,
    )

    assert progress.started_with == 3
    assert progress.advanced == ["index.md", "guide.md", "nested/deep.md"]
    assert progress.finished


def test_nav_structure_injected_into_index(
    sample_docs_path: Path, tmp_path: Path
) -> None:
    directory_tree = load_directory(sample_docs_path)
    nav_tree = load_mkdocs_nav(sample_docs_path / "mkdocs.yml")
    adapter = RecordingAdapter()
    id_map = PageIdMap(path=tmp_path / "ids.json")

    _publish_to_notion(
        directory_tree,
        nav_tree,
        adapter,
        id_map,
        parent_page_id=None,
    )

    index_blocks = adapter.created[0][2]

    nav_heading = next(
        block
        for block in index_blocks
        if isinstance(block, Heading) and block.text == "Navigation"
    )
    assert isinstance(nav_heading, Heading)

    nav_list = next(block for block in index_blocks if isinstance(block, ListElement))
    assert any(item.text.startswith("Home") for item in nav_list.items)
    assert any(item.text.startswith("Guide") for item in nav_list.items)
