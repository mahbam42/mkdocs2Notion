from pathlib import Path

from mkdocs2notion.loaders.id_map import PageIdMap


def test_page_id_map_persistence(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    id_map = PageIdMap.from_default_location(docs_root)

    id_map.set("nested/file.md", "abc123")
    id_map.save()

    reloaded = PageIdMap.from_default_location(docs_root)
    assert reloaded.get("nested/file.md") == "abc123"


def test_page_id_map_normalizes_paths(tmp_path: Path) -> None:
    target = tmp_path / "map.json"
    id_map = PageIdMap(path=target)

    id_map.set("folder\\file.md", "xyz")

    assert "folder/file.md" in id_map.map


def test_page_id_map_can_ignore_existing(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    existing = docs_root / ".mkdocs2notion_ids.json"
    existing.write_text('{"old.md": "old-id"}', encoding="utf-8")

    id_map = PageIdMap.from_default_location(docs_root, ignore_existing=True)

    assert id_map.get("old.md") is None
