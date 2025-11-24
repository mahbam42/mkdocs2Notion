from pathlib import Path
from typing import Any, List, Optional

from mkdocs2notion.loaders.directory import DocumentNode, load_directory
from mkdocs2notion.loaders.id_map import PageIdMap
from mkdocs2notion.loaders.mkdocs_nav import _page_key, load_mkdocs_nav
from mkdocs2notion.markdown.elements import Admonition, Link
from mkdocs2notion.markdown.elements import List as ListElement
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

    assert [item.nav_node.title for item in plan] == [
        "Home",
        "Guide",
        "Overview",
        "Deep Dive",
    ]
    assert plan[2].parent_key == _page_key(nav_tree.children[1])


def test_publish_to_notion_sets_ids(sample_docs_path: Path, tmp_path: Path) -> None:
    directory_tree = load_directory(sample_docs_path)
    nav_tree = load_mkdocs_nav(sample_docs_path / "mkdocs.yml")
    adapter = RecordingAdapter()
    id_map = PageIdMap(path=tmp_path / "ids.json")

    _publish_to_notion(directory_tree, nav_tree, adapter, id_map, parent_page_id="root")

    assert id_map.get("index.md") is not None
    assert id_map.get("guide.md") is not None
    assert id_map.get("nested/deep.md") is not None
    assert id_map.get("guide") is not None
    # parent relationship for nested entry should target provided root when no parent path
    assert adapter.created[2][1] == id_map.get("guide")


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

    assert progress.started_with == 4
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

    index_blocks = adapter.updated[0][1]

    nav_callout = next(block for block in index_blocks if isinstance(block, Admonition))
    assert nav_callout.title == "📚 Navigation"

    nav_list = next(block for block in nav_callout.content if isinstance(block, ListElement))
    guide_item = next(item for item in nav_list.items if item.text == "Guide")
    assert guide_item.children
    guide_children = guide_item.children[0]
    assert isinstance(guide_children, ListElement)
    assert [child.text for child in guide_children.items] == ["Overview", "Deep Dive"]

    def _collect_links(list_element: ListElement) -> list[Link]:
        links: list[Link] = []
        for item in list_element.items:
            links.extend(
                inline for inline in item.inlines if isinstance(inline, Link)
            )
            for child in item.children:
                if isinstance(child, ListElement):
                    links.extend(_collect_links(child))
        return links

    link_targets = _collect_links(nav_list)
    assert any(link.target.startswith("notion://") for link in link_targets)
