"""Notion adapter implementations and factory."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Iterable, List, Optional, Sequence

from notion_client import Client

from mkdocs2notion.markdown.elements import (
    Admonition,
    CodeBlock,
    Element,
    Heading,
    Image,
    InlineContent,
    Link,
    List as ListElement,
    Page,
    Paragraph,
    Text,
)


class NotionAdapter(ABC):
    """
    Abstract interface for communicating with Notion.

    The rest of the codebase should never import Ultimate Notion directly.
    This makes it easy to switch between:

    - Ultimate Notion
    - Official Notion API client (future)
    - Mock adapters for unit tests
    """

    @abstractmethod
    def create_page(
        self,
        title: str,
        parent_page_id: Optional[str],
        blocks: List[Any],
    ) -> str:
        """Create a new Notion page and return its page_id."""
        raise NotImplementedError

    @abstractmethod
    def update_page(
        self,
        page_id: str,
        blocks: List[Any],
    ) -> None:
        """Update an existing Notion page."""
        raise NotImplementedError

    @abstractmethod
    def get_page(self, page_id: str) -> Any:
        """Retrieve metadata for an existing page."""
        raise NotImplementedError

    def create_or_update_page(
        self,
        title: str,
        parent_page_id: Optional[str],
        page_id: Optional[str],
        blocks: List[Any],
    ) -> str:
        """
        Convenience method:
        - if page_id exists → update
        - else → create
        """
        if page_id:
            self.update_page(page_id, blocks)
            return page_id

        return self.create_page(title, parent_page_id, blocks)


def get_default_adapter() -> NotionAdapter:
    """Return a functional adapter using the official Notion SDK.

    The factory currently prefers the official `notion-client` SDK. A future
    enhancement can auto-detect Ultimate Notion when it is available, but the
    basic SDK keeps this dependency light while remaining functional.

    Returns:
        NotionAdapter: Configured adapter ready for publishing.

    Raises:
        RuntimeError: If a Notion token is not provided via ``NOTION_TOKEN``.
    """

    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN is required to publish content to Notion.")

    parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID")
    return NotionClientAdapter(token=token, default_parent_page_id=parent_page_id)


class NotionClientAdapter(NotionAdapter):
    """Adapter backed by the official Notion Python client."""

    def __init__(self, token: str, default_parent_page_id: str | None = None) -> None:
        self.client = Client(auth=token)
        self.default_parent_page_id = default_parent_page_id

    def create_or_update_page(
        self,
        title: str,
        parent_page_id: Optional[str],
        page_id: Optional[str],
        blocks: List[Any],
    ) -> str:
        payload_blocks = self._normalize_blocks(blocks)
        if page_id:
            self._update_page(page_id, title, payload_blocks)
            return page_id
        return self._create_page(title, parent_page_id, payload_blocks)

    def create_page(
        self,
        title: str,
        parent_page_id: Optional[str],
        blocks: List[Any],
    ) -> str:
        payload_blocks = self._normalize_blocks(blocks)
        return self._create_page(title, parent_page_id, payload_blocks)

    def update_page(self, page_id: str, blocks: List[Any]) -> None:
        payload_blocks = self._normalize_blocks(blocks)
        self._update_page(page_id, None, payload_blocks)

    def get_page(self, page_id: str) -> Any:
        return self.client.pages.retrieve(page_id=page_id)

    def _create_page(
        self, title: str, parent_page_id: str | None, children: list[dict[str, Any]]
    ) -> str:
        parent = self._build_parent(parent_page_id)
        result = self.client.pages.create(
            parent=parent,
            properties={"title": {"title": [_text_rich(title)]}},
            children=children,
        )
        return result["id"]

    def _update_page(
        self,
        page_id: str,
        title: str | None,
        children: list[dict[str, Any]],
    ) -> None:
        if title:
            self.client.pages.update(
                page_id=page_id, properties={"title": {"title": [_text_rich(title)]}}
            )
        self._replace_block_children(block_id=page_id, children=children)

    def _replace_block_children(
        self, block_id: str, children: list[dict[str, Any]]
    ) -> None:
        existing = self.client.blocks.children.list(block_id=block_id)
        for child in existing.get("results", []):
            self.client.blocks.delete(block_id=child["id"])
        if children:
            self.client.blocks.children.append(block_id=block_id, children=children)

    def _normalize_blocks(self, blocks: List[Any] | Page) -> list[dict[str, Any]]:
        if isinstance(blocks, Page):
            elements: Iterable[Element] = blocks.children
        else:
            elements = blocks
        if not isinstance(elements, Iterable):
            raise TypeError("Blocks payload must be a Page or iterable of elements.")

        materialized = list(elements)
        if materialized and isinstance(materialized[0], dict):
            return [dict(block) for block in materialized]
        return _render_elements(materialized)

    def _build_parent(self, provided_parent: str | None) -> dict[str, Any]:
        parent_page = provided_parent or self.default_parent_page_id
        if parent_page:
            return {"type": "page_id", "page_id": parent_page}
        return {"type": "workspace", "workspace": True}


def _render_elements(elements: Sequence[Element]) -> list[dict[str, Any]]:
    """Convert parsed elements into Notion block payloads."""

    blocks: list[dict[str, Any]] = []
    for element in elements:
        blocks.extend(_render_element(element))
    return blocks


def _render_element(element: Element) -> list[dict[str, Any]]:
    if isinstance(element, Heading):
        heading_type = {1: "heading_1", 2: "heading_2"}.get(element.level, "heading_3")
        return [
            {
                "type": heading_type,
                heading_type: {
                    "rich_text": _rich_text_from_inlines(element.inlines, element.text)
                },
            }
        ]

    if isinstance(element, Paragraph):
        return [
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": _rich_text_from_inlines(element.inlines, element.text)
                },
            }
        ]

    if isinstance(element, ListElement):
        block_type = "numbered_list_item" if element.ordered else "bulleted_list_item"
        return [
            {
                "type": block_type,
                block_type: {
                    "rich_text": _rich_text_from_inlines(item.inlines, item.text)
                },
            }
            for item in element.items
        ]

    if isinstance(element, CodeBlock):
        return [
            {
                "type": "code",
                "code": {
                    "language": element.language or "plain text",
                    "rich_text": [_text_rich(element.code)],
                },
            }
        ]

    if isinstance(element, Admonition):
        children: list[dict[str, Any]] = []
        for child in element.content:
            children.extend(_render_element(child))
        headline = element.title or element.kind.title()
        return [
            {
                "type": "callout",
                "callout": {
                    "icon": _callout_icon(element.kind),
                    "rich_text": _rich_text_from_inlines(
                        [Text(text=headline)], headline
                    ),
                    "children": children,
                },
            }
        ]

    # Fallback: render unknown element as a paragraph of text
    return [
        {
            "type": "paragraph",
            "paragraph": {"rich_text": [_text_rich(str(element))]},
        }
    ]


def _callout_icon(kind: str) -> dict[str, str]:
    lookup = {"warning": "⚠️", "note": "💡", "tip": "💡", "info": "ℹ️"}
    return {"type": "emoji", "emoji": lookup.get(kind.lower(), "💬")}


def _rich_text_from_inlines(
    inlines: Sequence[InlineContent], fallback_text: str
) -> list[dict[str, Any]]:
    if not inlines:
        return [_text_rich(fallback_text)]

    parts: list[dict[str, Any]] = []
    for inline in inlines:
        if isinstance(inline, Text):
            parts.append(_text_rich(inline.text))
        elif isinstance(inline, Link):
            parts.append(_text_rich(inline.text, inline.target))
        elif isinstance(inline, Image):
            alt = inline.alt or inline.src
            parts.append(_text_rich(alt, inline.src))
    return parts


def _text_rich(content: str, url: str | None = None) -> dict[str, Any]:
    text: dict[str, Any] = {"content": content}
    if url:
        text["link"] = {"url": url}
    return {"type": "text", "text": text}


__all__ = ["NotionAdapter", "NotionClientAdapter", "get_default_adapter"]
