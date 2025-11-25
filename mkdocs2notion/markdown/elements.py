"""Element models aligned to Notion-style blocks.

The classes in this module mirror the Notion block hierarchy while keeping
enough metadata to surface parsing warnings and future cross-link resolution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass(frozen=True, kw_only=True)
class Block(ABC):
    """Base block with shared metadata.

    Every block exposes children for nested content, source_line/source_file for
    diagnostics, and a ``to_notion`` helper that returns a structured
    representation suitable for later conversion to the Notion API shape.
    """

    children: tuple["Block", ...] = field(default_factory=tuple)
    source_line: int | None = None
    source_file: str | None = None
    type: ClassVar[str]

    def to_notion(self) -> dict[str, Any]:
        """Serialize the block into a structured dictionary."""

        payload = {"type": self.type, **self._serialize()}
        if self.source_line is not None:
            payload["source_line"] = self.source_line
        if self.source_file is not None:
            payload["source_file"] = self.source_file
        if self.children:
            payload["children"] = [child.to_notion() for child in self.children]
        return payload

    @abstractmethod
    def _serialize(self) -> dict[str, Any]:
        """Return block-specific fields for serialization."""


@dataclass(frozen=True)
class TextSpan:
    """Plain text span used for inline content."""

    text: str


@dataclass(frozen=True)
class LinkSpan(TextSpan):
    """Hyperlink span."""

    target: str


@dataclass(frozen=True)
class StrikethroughSpan(TextSpan):
    """Strikethrough span that can wrap nested inline spans."""

    inlines: tuple["InlineSpan", ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ImageSpan(TextSpan):
    """Inline image with alt text and a source target."""

    source: str


InlineSpan = TextSpan | LinkSpan | StrikethroughSpan | ImageSpan


@dataclass(frozen=True)
class Paragraph(Block):
    """Paragraph block containing inline spans."""

    text: str
    inlines: tuple[InlineSpan, ...] = field(default_factory=tuple)
    type: ClassVar[str] = "paragraph"

    def _serialize(self) -> dict[str, Any]:
        return {"text": self.text, "inlines": [serialize_inline(i) for i in self.inlines]}


@dataclass(frozen=True)
class Heading(Block):
    """Heading block supporting levels 1–6."""

    level: int
    text: str
    inlines: tuple[InlineSpan, ...] = field(default_factory=tuple)
    type: ClassVar[str] = "heading"

    def _serialize(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "text": self.text,
            "inlines": [serialize_inline(i) for i in self.inlines],
        }


@dataclass(frozen=True)
class Quote(Block):
    """Quote block that can nest additional blocks."""

    type: ClassVar[str] = "quote"

    def _serialize(self) -> dict[str, Any]:  # pragma: no cover - marker only
        return {}


@dataclass(frozen=True)
class Divider(Block):
    """Horizontal rule divider."""

    type: ClassVar[str] = "divider"

    def _serialize(self) -> dict[str, Any]:  # pragma: no cover - marker only
        return {}


@dataclass(frozen=True)
class BulletedListItem(Block):
    """Bullet list item with inline text."""

    text: str
    inlines: tuple[InlineSpan, ...] = field(default_factory=tuple)
    type: ClassVar[str] = "bulleted_list_item"

    def _serialize(self) -> dict[str, Any]:
        return {"text": self.text, "inlines": [serialize_inline(i) for i in self.inlines]}


@dataclass(frozen=True)
class NumberedListItem(Block):
    """Numbered list item with inline text."""

    text: str
    inlines: tuple[InlineSpan, ...] = field(default_factory=tuple)
    type: ClassVar[str] = "numbered_list_item"

    def _serialize(self) -> dict[str, Any]:
        return {"text": self.text, "inlines": [serialize_inline(i) for i in self.inlines]}


@dataclass(frozen=True)
class Toggle(Block):
    """Toggle block mapping to Notion toggles."""

    title: str
    inlines: tuple[InlineSpan, ...] = field(default_factory=tuple)
    type: ClassVar[str] = "toggle"

    def _serialize(self) -> dict[str, Any]:
        return {"title": self.title, "inlines": [serialize_inline(i) for i in self.inlines]}


@dataclass(frozen=True)
class Callout(Block):
    """Callout/admonition block."""

    title: str
    callout_type: str
    icon: str | None
    type: ClassVar[str] = "callout"

    def _serialize(self) -> dict[str, Any]:
        return {"title": self.title, "callout_type": self.callout_type, "icon": self.icon}


@dataclass(frozen=True)
class CodeBlock(Block):
    """Fenced code block or diagram."""

    language: str | None
    code: str
    type: ClassVar[str] = "code_block"

    def _serialize(self) -> dict[str, Any]:
        return {"language": self.language, "code": self.code}


@dataclass(frozen=True)
class TableCell(Block):
    """Single table cell supporting nested blocks."""

    text: str
    inlines: tuple[InlineSpan, ...] = field(default_factory=tuple)
    type: ClassVar[str] = "table_cell"

    def _serialize(self) -> dict[str, Any]:
        return {"text": self.text, "inlines": [serialize_inline(i) for i in self.inlines]}


@dataclass(frozen=True)
class Table(Block):
    """GitHub-flavored table representation."""

    headers: tuple[TableCell, ...]
    rows: tuple[tuple[TableCell, ...], ...]
    type: ClassVar[str] = "table"

    def _serialize(self) -> dict[str, Any]:
        return {
            "headers": [cell.to_notion() for cell in self.headers],
            "rows": [[cell.to_notion() for cell in row] for row in self.rows],
        }


@dataclass(frozen=True)
class Image(Block):
    """Image block with alt text."""

    source: str
    alt: str | None = None
    type: ClassVar[str] = "image"

    def _serialize(self) -> dict[str, Any]:
        return {"source": self.source, "alt": self.alt}


@dataclass(frozen=True)
class RawMarkdown(Block):
    """Raw markdown passthrough for unsupported structures."""

    source_text: str
    type: ClassVar[str] = "raw_markdown"

    def _serialize(self) -> dict[str, Any]:
        return {"source_text": self.source_text}


@dataclass(frozen=True)
class Page(Block):
    """Page root that groups all parsed blocks."""

    title: str
    pending_links: list[str] = field(default_factory=list)
    type: ClassVar[str] = "page"

    def _serialize(self) -> dict[str, Any]:
        return {"title": self.title, "pending_links": list(self.pending_links)}


def serialize_inline(inline: InlineSpan) -> dict[str, Any]:
    """Serialize inline spans for debugging and test visibility."""

    if isinstance(inline, LinkSpan):
        return {"type": "link", "text": inline.text, "target": inline.target}
    if isinstance(inline, StrikethroughSpan):
        return {
            "type": "strikethrough",
            "text": inline.text,
            "inlines": [serialize_inline(child) for child in inline.inlines],
        }
    if isinstance(inline, ImageSpan):
        return {"type": "image", "text": inline.text, "source": inline.source}
    return {"type": "text", "text": inline.text}


__all__ = [
    "Block",
    "BulletedListItem",
    "Callout",
    "CodeBlock",
    "Divider",
    "Heading",
    "Image",
    "InlineSpan",
    "LinkSpan",
    "NumberedListItem",
    "Page",
    "Paragraph",
    "Quote",
    "RawMarkdown",
    "StrikethroughSpan",
    "ImageSpan",
    "Table",
    "TableCell",
    "TextSpan",
    "Toggle",
]
