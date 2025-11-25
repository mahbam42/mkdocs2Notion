from __future__ import annotations

from types import SimpleNamespace

from mkdocs2notion.notion.api_adapter import NotionClientAdapter


class _FakeChildren:
    def __init__(self, existing: list[dict[str, object]]) -> None:
        self._existing = existing
        self.append_calls: list[tuple[str, list[dict[str, object]]]] = []
        self._counter = 0

    def list(self, block_id: str) -> dict[str, object]:  # pragma: no cover - passthrough
        return {"results": self._existing}

    def append(self, block_id: str, children: list[dict[str, object]]) -> None:
        self.append_calls.append((block_id, children))
        self._counter += 1
        return {"results": [{"id": f"block-{self._counter}"}]}


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


def test_replace_block_children_uploads_nested_blocks_recursively() -> None:
    adapter = NotionClientAdapter(token="dummy")
    adapter.client = SimpleNamespace(blocks=_FakeBlocks([]))  # type: ignore[assignment]

    nested_children = [
        {
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [],
                "children": [
                    {
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": []},
                    }
                ],
            },
        }
    ]

    adapter._replace_block_children("parent", nested_children)

    calls = adapter.client.blocks.children.append_calls  # type: ignore[attr-defined]
    assert calls[0][0] == "parent"
    assert "children" not in calls[0][1][0]["bulleted_list_item"]
    assert calls[1][0] == "block-1"


def test_table_children_are_preserved_on_append() -> None:
    adapter = NotionClientAdapter(token="dummy")
    adapter.client = SimpleNamespace(blocks=_FakeBlocks([]))  # type: ignore[assignment]

    table_block = {
        "type": "table",
        "table": {
            "table_width": 2,
            "has_column_header": True,
            "has_row_header": False,
            "children": [
                {"type": "table_row", "table_row": {"cells": []}},
            ],
        },
    }

    adapter._replace_block_children("parent", [table_block])

    calls = adapter.client.blocks.children.append_calls  # type: ignore[attr-defined]
    assert calls[0][1][0]["table"]["children"]
