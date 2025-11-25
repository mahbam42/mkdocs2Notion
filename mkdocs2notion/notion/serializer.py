"""Utilities for converting parsed blocks into Notion API payloads."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence, Tuple
from urllib.parse import urlparse

from mkdocs2notion.markdown.elements import (
    Block,
    BoldSpan,
    BulletedListItem,
    Callout,
    CodeBlock,
    Divider,
    Heading,
    Image,
    ImageSpan,
    InlineSpan,
    ItalicSpan,
    LinkSpan,
    NumberedListItem,
    Paragraph,
    Quote,
    RawMarkdown,
    StrikethroughSpan,
    Table,
    TableCell,
    TextSpan,
    Toggle,
)


def serialize_elements(
    elements: Sequence[Block],
    resolve_image: Callable[[Image], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Convert blocks to Notion-ready dictionaries.

    Args:
        elements: Parsed block tree to render.
        resolve_image: Optional resolver that transforms an ``Image`` element into
            a Notion ``image`` block payload. When omitted, images are treated as
            external URLs.

    Returns:
        A list of dictionaries matching the Notion API schema for blocks.
    """

    resolver = resolve_image or _default_image_resolver
    blocks: list[dict[str, Any]] = []
    for element in elements:
        blocks.extend(_serialize_block(element, resolver))
    return blocks


def collect_images(elements: Iterable[Block]) -> list[Image]:
    """Return any Image blocks nested inside the given elements."""

    images: list[Image] = []

    def _walk(block: Block) -> None:
        if isinstance(block, Image):
            images.append(block)
        for child in block.children:
            _walk(child)

    for element in elements:
        _walk(element)
    return images


def _serialize_block(
    element: Block, resolve_image: Callable[[Image], dict[str, Any]]
) -> list[dict[str, Any]]:
    if isinstance(element, Heading):
        rich_text, image_blocks = _render_text_and_images(
            element.inlines, element.text, resolve_image
        )
        heading_type = _heading_type(element.level)
        block = {
            "type": heading_type,
            heading_type: {"rich_text": rich_text},
        }
        return [block, *image_blocks]

    if isinstance(element, Paragraph):
        rich_text, image_blocks = _render_text_and_images(
            element.inlines, element.text, resolve_image
        )
        children = serialize_elements(element.children, resolve_image)
        paragraph: dict[str, Any] = {
            "type": "paragraph",
            "paragraph": {"rich_text": rich_text},
        }
        if children:
            paragraph["paragraph"]["children"] = children
        return [paragraph, *image_blocks]

    if isinstance(element, BulletedListItem):
        rich_text, image_blocks = _render_text_and_images(
            element.inlines, element.text, resolve_image
        )
        children = serialize_elements(element.children, resolve_image)
        payload: dict[str, Any] = {
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": rich_text},
        }
        if children:
            payload["bulleted_list_item"]["children"] = children
        return [payload, *image_blocks]

    if isinstance(element, NumberedListItem):
        rich_text, image_blocks = _render_text_and_images(
            element.inlines, element.text, resolve_image
        )
        children = serialize_elements(element.children, resolve_image)
        payload = {
            "type": "numbered_list_item",
            "numbered_list_item": {"rich_text": rich_text},
        }
        if children:
            payload["numbered_list_item"]["children"] = children
        return [payload, *image_blocks]

    if isinstance(element, Toggle):
        rich_text, image_blocks = _render_text_and_images(
            element.inlines, element.title, resolve_image
        )
        children = serialize_elements(element.children, resolve_image)
        payload = {"type": "toggle", "toggle": {"rich_text": rich_text}}
        if children:
            payload["toggle"]["children"] = children
        return [payload, *image_blocks]

    if isinstance(element, Callout):
        children = serialize_elements(element.children, resolve_image)
        callout_text = element.title or element.callout_type.title()
        rich_text, image_blocks = _render_text_and_images((), callout_text, resolve_image)
        callout: dict[str, Any] = {
            "type": "callout",
            "callout": {
                "rich_text": rich_text,
                "children": children,
            },
        }
        if element.icon:
            callout["callout"]["icon"] = {"type": "emoji", "emoji": element.icon}
        return [callout, *image_blocks]

    if isinstance(element, CodeBlock):
        language = element.language or "plain text"
        block = {
            "type": "code",
            "code": {
                "language": language,
                "rich_text": [text_rich(element.code)],
            },
        }
        return [block]

    if isinstance(element, Quote):
        children = serialize_elements(element.children, resolve_image)
        block = {
            "type": "quote",
            "quote": {
                "rich_text": [text_rich("")],
                "children": children,
            },
        }
        return [block]

    if isinstance(element, Divider):
        return [{"type": "divider", "divider": {}}]

    if isinstance(element, Table):
        header_cells, header_images = _serialize_cells(
            element.headers, resolve_image
        )
        row_blocks: list[dict[str, Any]] = []
        image_blocks = list(header_images)
        if header_cells:
            row_blocks.append({"type": "table_row", "table_row": {"cells": header_cells}})
        for row in element.rows:
            cells, images = _serialize_cells(row, resolve_image)
            row_blocks.append({"type": "table_row", "table_row": {"cells": cells}})
            image_blocks.extend(images)
        table_width = max((len(element.headers), *(len(row) for row in element.rows)))
        table_block = {
            "type": "table",
            "table": {
                "table_width": table_width,
                "has_column_header": bool(element.headers),
                "has_row_header": False,
                "children": row_blocks,
            },
        }
        return [table_block, *image_blocks]

    if isinstance(element, Image):
        return [resolve_image(element)]

    if isinstance(element, RawMarkdown):
        return [
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [text_rich(element.source_text)]},
            }
        ]

    return [
        {
            "type": "paragraph",
            "paragraph": {"rich_text": [text_rich(str(element))]},
        }
    ]


def _serialize_cells(
    cells: Sequence[TableCell], resolve_image: Callable[[Image], dict[str, Any]]
) -> Tuple[list[list[dict[str, Any]]], list[dict[str, Any]]]:
    table_cells: list[list[dict[str, Any]]] = []
    image_blocks: list[dict[str, Any]] = []
    for cell in cells:
        rich_text, images = _render_text_and_images(cell.inlines, cell.text, resolve_image)
        table_cells.append(rich_text)
        image_blocks.extend(images)
    return table_cells, image_blocks


def _render_text_and_images(
    inlines: Sequence[InlineSpan],
    fallback_text: str,
    resolve_image: Callable[[Image], dict[str, Any]],
) -> Tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not inlines:
        return [text_rich(fallback_text)], []

    rich_text: list[dict[str, Any]] = []
    image_blocks: list[dict[str, Any]] = []
    for inline in inlines:
        if isinstance(inline, ImageSpan):
            image_blocks.append(
                resolve_image(Image(source=inline.source, alt=inline.text))
            )
            continue
        if isinstance(inline, StrikethroughSpan):
            nested_text, nested_images = _render_text_and_images(
                inline.inlines, inline.text, resolve_image
            )
            for segment in nested_text:
                annotations = segment.get("annotations") or _default_annotations()
                rich_text.append(
                    {**segment, "annotations": {**annotations, "strikethrough": True}}
                )
            image_blocks.extend(nested_images)
            continue
        rich_text.extend(_rich_text_for_inline(inline))

    return rich_text or [text_rich(fallback_text)], image_blocks


def _rich_text_for_inline(inline: InlineSpan) -> list[dict[str, Any]]:
    if isinstance(inline, LinkSpan):
        return [text_rich(inline.text, url=_validated_link(inline.target))]
    if isinstance(inline, BoldSpan):
        bold = text_rich(inline.text)
        bold["annotations"]["bold"] = True
        return [bold]
    if isinstance(inline, ItalicSpan):
        italic = text_rich(inline.text)
        italic["annotations"]["italic"] = True
        return [italic]
    if isinstance(inline, TextSpan):
        return [text_rich(inline.text)]
    return []


def text_rich(content: str, url: str | None = None) -> dict[str, Any]:
    """Return a Notion rich text payload."""

    text: dict[str, Any] = {"content": content}
    if url:
        text["link"] = {"url": url}
    return {"type": "text", "text": text, "annotations": _default_annotations()}


def _default_annotations() -> dict[str, Any]:
    return {
        "bold": False,
        "italic": False,
        "strikethrough": False,
        "underline": False,
        "code": False,
        "color": "default",
    }


def _heading_type(level: int) -> str:
    if level <= 1:
        return "heading_1"
    if level == 2:
        return "heading_2"
    return "heading_3"


def _validated_link(url: str | None) -> str | None:
    """Return the URL if it is valid for Notion, otherwise strip the link."""

    if url and _is_valid_url(url):
        return url
    return None


def _is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"}:
        return bool(parsed.netloc)
    if parsed.scheme == "notion":
        return bool(parsed.netloc or parsed.path)
    return False


def _default_image_resolver(image: Image) -> dict[str, Any]:
    """Fallback image resolver that links to the source URL."""

    return {
        "type": "image",
        "image": {
            "type": "external",
            "external": {"url": image.source},
            "caption": [text_rich(image.alt or image.source)],
        },
    }


__all__ = ["serialize_elements", "collect_images"]
