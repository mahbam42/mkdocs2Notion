"""Element model for representing parsed Markdown content.

This module defines structured data classes for a simplified Markdown
representation that can be serialized for downstream Notion conversion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class Element:
    """Base element with serialization support."""

    type: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the element into a dictionary."""

        return {"type": self.type}


@dataclass(frozen=True)
class Text(Element):
    """Inline text span."""

    text: str
    type: str = field(init=False, default="text")

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text}


@dataclass(frozen=True)
class Link(Element):
    """Inline hyperlink."""

    text: str
    target: str
    type: str = field(init=False, default="link")

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text, "target": self.target}


@dataclass(frozen=True)
class Image(Element):
    """Inline image reference."""

    src: str
    alt: str
    type: str = field(init=False, default="image")

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "src": self.src, "alt": self.alt}


InlineContent = Text | Link | Image


@dataclass(frozen=True)
class Heading(Element):
    """Markdown heading block."""

    level: int
    text: str
    inlines: Sequence[InlineContent] = field(default_factory=tuple)
    type: str = field(init=False, default="heading")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "level": self.level,
            "text": self.text,
            "inlines": [_serialize_inline(inline) for inline in self.inlines],
        }


@dataclass(frozen=True)
class Paragraph(Element):
    """Paragraph block supporting inline content."""

    text: str
    inlines: Sequence[InlineContent] = field(default_factory=tuple)
    type: str = field(init=False, default="paragraph")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "text": self.text,
            "inlines": [_serialize_inline(inline) for inline in self.inlines],
        }


@dataclass(frozen=True)
class ListItem(Element):
    """List item containing inline text."""

    text: str
    inlines: Sequence[InlineContent] = field(default_factory=tuple)
    type: str = field(init=False, default="list_item")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "text": self.text,
            "inlines": [_serialize_inline(inline) for inline in self.inlines],
        }


@dataclass(frozen=True)
class List(Element):
    """Ordered or unordered list block."""

    items: Sequence[ListItem]
    ordered: bool = False
    type: str = field(init=False, default="list")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "ordered_list" if self.ordered else "unordered_list",
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class CodeBlock(Element):
    """Fenced code block."""

    language: str | None
    code: str
    type: str = field(init=False, default="code_block")

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "language": self.language, "code": self.code}


@dataclass(frozen=True)
class Admonition(Element):
    """Admonition block with nested content."""

    kind: str
    title: str | None
    content: Sequence[Element]
    type: str = field(init=False, default="admonition")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "kind": self.kind,
            "title": self.title,
            "content": [child.to_dict() for child in self.content],
        }


@dataclass(frozen=True)
class Page(Element):
    """Page root holding all top-level elements."""

    title: str
    children: Sequence[Element] = field(default_factory=tuple)
    type: str = field(init=False, default="page")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "title": self.title,
            "children": [child.to_dict() for child in self.children],
        }


def _serialize_inline(inline: InlineContent) -> dict[str, Any]:
    """Serialize an inline element consistently."""

    return inline.to_dict()


__all__ = [
    "Admonition",
    "CodeBlock",
    "Element",
    "Heading",
    "Image",
    "InlineContent",
    "Link",
    "List",
    "ListItem",
    "Page",
    "Paragraph",
    "Text",
]
