"""Element model for representing parsed Markdown content.

This module defines structured data classes for a simplified Markdown
representation that can be serialized for downstream Notion conversion.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Sequence, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Element(ABC):
    """Base element with serialization support."""

    type: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the element into a dictionary."""

        payload = {"type": self.type}
        payload.update(self._serialize())
        return payload

    @abstractmethod
    def _serialize(self) -> dict[str, Any]:
        """Return a dictionary of element-specific fields."""

        raise NotImplementedError


@dataclass(frozen=True)
class Text(Element):
    """Inline text span."""

    text: str
    type: ClassVar[str] = "text"

    def _serialize(self) -> dict[str, Any]:
        return {"text": self.text}


@dataclass(frozen=True)
class Link(Element):
    """Inline hyperlink."""

    text: str
    target: str
    type: ClassVar[str] = "link"

    def _serialize(self) -> dict[str, Any]:
        return {"text": self.text, "target": self.target}


@dataclass(frozen=True)
class Image(Element):
    """Inline image reference."""

    src: str
    alt: str
    type: ClassVar[str] = "image"

    def _serialize(self) -> dict[str, Any]:
        return {"src": self.src, "alt": self.alt}


InlineContent = Text | Link | Image


@dataclass(frozen=True)
class Heading(Element):
    """Markdown heading block."""

    level: int
    text: str
    inlines: Sequence[InlineContent] = field(default_factory=tuple)
    type: ClassVar[str] = "heading"

    def __post_init__(self) -> None:
        object.__setattr__(self, "inlines", _normalize_sequence(self.inlines))

    def _serialize(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "text": self.text,
            "inlines": [_serialize_inline(inline) for inline in self.inlines],
        }


@dataclass(frozen=True)
class Paragraph(Element):
    """Paragraph block supporting inline content."""

    text: str
    inlines: Sequence[InlineContent] = field(default_factory=tuple)
    type: ClassVar[str] = "paragraph"

    def __post_init__(self) -> None:
        object.__setattr__(self, "inlines", _normalize_sequence(self.inlines))

    def _serialize(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "inlines": [_serialize_inline(inline) for inline in self.inlines],
        }


@dataclass(frozen=True)
class ListItem(Element):
    """List item containing inline text."""

    text: str
    inlines: Sequence[InlineContent] = field(default_factory=tuple)
    type: ClassVar[str] = "list_item"

    def __post_init__(self) -> None:
        object.__setattr__(self, "inlines", _normalize_sequence(self.inlines))

    def _serialize(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "inlines": [_serialize_inline(inline) for inline in self.inlines],
        }


@dataclass(frozen=True)
class List(Element):
    """Ordered or unordered list block."""

    items: Sequence[ListItem]
    ordered: bool = False
    type: ClassVar[str] = "list"

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", _normalize_sequence(self.items))

    def _serialize(self) -> dict[str, Any]:
        return {
            "ordered": self.ordered,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class CodeBlock(Element):
    """Fenced code block."""

    language: str | None
    code: str
    type: ClassVar[str] = "code_block"

    def _serialize(self) -> dict[str, Any]:
        return {"language": self.language, "code": self.code}


@dataclass(frozen=True)
class Admonition(Element):
    """Admonition block with nested content."""

    kind: str
    title: str | None
    content: Sequence[Element]
    type: ClassVar[str] = "admonition"

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", _normalize_sequence(self.content))

    def _serialize(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "content": [child.to_dict() for child in self.content],
        }


@dataclass(frozen=True)
class Page(Element):
    """Page root holding all top-level elements."""

    title: str
    children: Sequence[Element] = field(default_factory=tuple)
    type: ClassVar[str] = "page"

    def __post_init__(self) -> None:
        object.__setattr__(self, "children", _normalize_sequence(self.children))

    def _serialize(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "children": [child.to_dict() for child in self.children],
        }


def _serialize_inline(inline: InlineContent) -> dict[str, Any]:
    """Serialize an inline element consistently."""

    return inline.to_dict()


def _normalize_sequence(items: Sequence[T] | None) -> tuple[T, ...]:
    """Normalize potentially mutable sequences into tuples for determinism."""

    if items is None:
        return tuple()
    return tuple(items)


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
