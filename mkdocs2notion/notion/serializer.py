"""Utilities for converting Markdown elements into Notion block payloads.

The serializer translates parsed ``mkdocs2notion.markdown.elements`` objects
into JSON structures expected by the Notion API. Block classes encapsulate the
payload shape for each supported Notion block type, and helper functions provide
rich-text assembly and visitor-based traversal of the element tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Sequence

from mkdocs2notion.markdown.elements import (
    Admonition,
    CodeBlock,
    Element,
    Heading,
    Image,
    InlineContent,
    Link,
    Paragraph,
    Text,
)
from mkdocs2notion.markdown.elements import List as ListElement


@dataclass(frozen=True)
class NotionBlock:
    """Base class for Notion block payloads."""

    type: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the block into a Notion-compatible dictionary.

        Returns:
            dict[str, Any]: Payload matching the Notion block schema for the block
            type.
        """

        return {"type": self.type, self.type: self._serialize()}

    def _serialize(self) -> dict[str, Any]:
        """Return block-specific payload data."""

        raise NotImplementedError


@dataclass(frozen=True)
class ParagraphBlock(NotionBlock):
    """Notion paragraph block."""

    rich_text: Sequence[dict[str, Any]]
    type: ClassVar[str] = "paragraph"

    def _serialize(self) -> dict[str, Any]:
        return {"rich_text": list(self.rich_text)}


@dataclass(frozen=True)
class HeadingBlock(NotionBlock):
    """Notion heading block supporting levels 1–3."""

    level: int
    rich_text: Sequence[dict[str, Any]]
    type: ClassVar[str] = "heading"

    def to_dict(self) -> dict[str, Any]:
        heading_type = _heading_type(self.level)
        return {"type": heading_type, heading_type: {"rich_text": list(self.rich_text)}}

    def _serialize(self) -> dict[str, Any]:  # pragma: no cover - delegated in to_dict
        return {"rich_text": list(self.rich_text)}


@dataclass(frozen=True)
class ListItemBlock(NotionBlock):
    """Numbered or bulleted list item block."""

    ordered: bool
    rich_text: Sequence[dict[str, Any]]
    type: ClassVar[str] = "list_item"

    def to_dict(self) -> dict[str, Any]:
        block_type = "numbered_list_item" if self.ordered else "bulleted_list_item"
        return {"type": block_type, block_type: {"rich_text": list(self.rich_text)}}

    def _serialize(self) -> dict[str, Any]:  # pragma: no cover - delegated in to_dict
        return {"rich_text": list(self.rich_text)}


@dataclass(frozen=True)
class CodeBlockPayload(NotionBlock):
    """Code block with language metadata."""

    language: str
    code: str
    type: ClassVar[str] = "code"

    def _serialize(self) -> dict[str, Any]:
        return {"language": self.language, "rich_text": [text_rich(self.code)]}


@dataclass(frozen=True)
class CalloutBlock(NotionBlock):
    """Callout block used for admonitions."""

    rich_text: Sequence[dict[str, Any]]
    icon: dict[str, Any]
    children: Sequence[dict[str, Any]]
    type: ClassVar[str] = "callout"

    def _serialize(self) -> dict[str, Any]:
        return {
            "rich_text": list(self.rich_text),
            "icon": self.icon,
            "children": list(self.children),
        }


@dataclass(frozen=True)
class ImageBlock(NotionBlock):
    """Image block returned from a resolver."""

    payload: dict[str, Any]
    type: ClassVar[str] = "image"

    def to_dict(self) -> dict[str, Any]:
        return self.payload

    def _serialize(self) -> dict[str, Any]:  # pragma: no cover - delegated in to_dict
        return self.payload


def serialize_elements(
    elements: Sequence[Element], resolve_image: Callable[[Image], dict[str, Any]]
) -> list[dict[str, Any]]:
    """Serialize Markdown elements into Notion block dictionaries.

    Args:
        elements: Parsed Markdown elements to convert.
        resolve_image: Callable that transforms an ``Image`` element into a fully
            resolved Notion image block dictionary. This hook keeps upload and URL
            resolution outside the serializer.

    Returns:
        List of dictionaries ready to send to the Notion API.
    """

    blocks: list[dict[str, Any]] = []
    for element in elements:
        blocks.extend(_serialize_element(element, resolve_image))
    return blocks


def _serialize_element(
    element: Element, resolve_image: Callable[[Image], dict[str, Any]]
) -> list[dict[str, Any]]:
    """Serialize a single element into one or more Notion blocks."""

    if isinstance(element, Heading):
        rich_text, image_blocks = _render_text_and_images(
            element.inlines, element.text, resolve_image
        )
        heading_block = HeadingBlock(level=element.level, rich_text=rich_text)
        return [heading_block.to_dict(), *image_blocks]

    if isinstance(element, Paragraph):
        rich_text, image_blocks = _render_text_and_images(
            element.inlines, element.text, resolve_image
        )
        paragraph_block = ParagraphBlock(rich_text=rich_text)
        return [paragraph_block.to_dict(), *image_blocks]

    if isinstance(element, ListElement):
        list_blocks: list[dict[str, Any]] = []
        for item in element.items:
            rich_text, image_blocks = _render_text_and_images(
                item.inlines, item.text, resolve_image
            )
            list_blocks.append(
                ListItemBlock(ordered=element.ordered, rich_text=rich_text).to_dict()
            )
            list_blocks.extend(image_blocks)
        return list_blocks

    if isinstance(element, CodeBlock):
        language = element.language or "plain text"
        return [CodeBlockPayload(language=language, code=element.code).to_dict()]

    if isinstance(element, Admonition):
        children: list[dict[str, Any]] = []
        for child in element.content:
            children.extend(_serialize_element(child, resolve_image))
        headline = element.title or element.kind.title()
        callout = CalloutBlock(
            icon=_callout_icon(element.kind),
            rich_text=_rich_text_from_inlines([Text(text=headline)], headline),
            children=children,
        )
        return [callout.to_dict()]

    if isinstance(element, Image):
        return [ImageBlock(resolve_image(element)).to_dict()]

    fallback = ParagraphBlock(rich_text=[text_rich(str(element))])
    return [fallback.to_dict()]


def text_rich(content: str, url: str | None = None) -> dict[str, Any]:
    """Build a Notion rich text payload for plain text or links.

    Args:
        content: Raw textual content to render.
        url: Optional hyperlink target to attach to the text span.

    Returns:
        dict[str, Any]: Notion rich text dictionary that can be embedded inside
        block payloads.
    """

    text: dict[str, Any] = {"content": content}
    if url:
        text["link"] = {"url": url}
    return {"type": "text", "text": text}


def _rich_text_from_inlines(
    inlines: Sequence[InlineContent], fallback_text: str
) -> list[dict[str, Any]]:
    if not inlines:
        return [text_rich(fallback_text)]

    parts: list[dict[str, Any]] = []
    for inline in inlines:
        if isinstance(inline, Text):
            parts.append(text_rich(inline.text))
        elif isinstance(inline, Link):
            url = inline.target if _is_valid_url(inline.target) else None
            parts.append(text_rich(inline.text, url))
        elif isinstance(inline, Image):
            alt = inline.alt or inline.src
            url = inline.src if _is_valid_url(inline.src) else None
            parts.append(text_rich(alt, url))
    return parts or [text_rich(fallback_text)]


def _render_text_and_images(
    inlines: Sequence[InlineContent],
    fallback_text: str,
    resolve_image: Callable[[Image], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Assemble rich text and collect separate image blocks for inline images."""

    rich_text: list[dict[str, Any]] = []
    image_blocks: list[dict[str, Any]] = []

    if not inlines:
        return [text_rich(fallback_text)], []

    for inline in inlines:
        if isinstance(inline, Image):
            image_blocks.append(resolve_image(inline))
            continue
        if isinstance(inline, Text):
            rich_text.append(text_rich(inline.text))
        elif isinstance(inline, Link):
            url = inline.target if _is_valid_url(inline.target) else None
            rich_text.append(text_rich(inline.text, url))
        else:
            rich_text.append(text_rich(fallback_text))

    if not rich_text:
        rich_text = [text_rich(fallback_text)]

    return rich_text, image_blocks


def _heading_type(level: int) -> str:
    if level == 1:
        return "heading_1"
    if level == 2:
        return "heading_2"
    return "heading_3"


def _callout_icon(kind: str) -> dict[str, str]:
    lookup = {"warning": "⚠️", "note": "💡", "tip": "💡", "info": "ℹ️"}
    return {"type": "emoji", "emoji": lookup.get(kind.lower(), "💬")}


def _is_valid_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


__all__ = [
    "CalloutBlock",
    "CodeBlockPayload",
    "HeadingBlock",
    "ImageBlock",
    "ListItemBlock",
    "NotionBlock",
    "ParagraphBlock",
    "serialize_elements",
    "text_rich",
]
