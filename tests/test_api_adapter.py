from __future__ import annotations

from types import SimpleNamespace

from mkdocs2notion.notion.api_adapter import NotionClientAdapter


class _FakeChildren:
    def __init__(self, existing: list[dict[str, object]]) -> None:
        self._existing = existing
        self.append_calls: list[tuple[str, list[dict[str, object]]]] = []

    def list(self, block_id: str) -> dict[str, object]:  # pragma: no cover - passthrough
        return {"results": self._existing}

    def append(self, block_id: str, children: list[dict[str, object]]) -> None:
        self.append_calls.append((block_id, children))


class _FakeBlocks:
    def __init__(self, existing: list[dict[str, object]]) -> None:
        self.children = _FakeChildren(existing)
        self.deleted: list[str] = []

    def delete(self, block_id: str) -> None:
        self.deleted.append(block_id)


def test_replace_block_children_preserves_child_pages() -> None:
    existing_children = [
        {"id": "page-1", "type": "child_page"},
        {"id": "db-1", "type": "child_database"},
        {"id": "text-1", "type": "paragraph"},
    ]
    adapter = NotionClientAdapter(token="dummy")
    adapter.client = SimpleNamespace(blocks=_FakeBlocks(existing_children))  # type: ignore[assignment]

    new_children = [{"type": "paragraph", "paragraph": {"rich_text": []}}]

    adapter._replace_block_children("parent", new_children)

    assert adapter.client.blocks.deleted == ["text-1"]  # type: ignore[attr-defined]
    assert adapter.client.blocks.children.append_calls == [  # type: ignore[attr-defined]
        ("parent", new_children)
    ]
