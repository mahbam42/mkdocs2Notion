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


@dataclass(frozen=True)
class Strikethrough(Element):
    """Inline strikethrough span.

    Args:
        text: Raw text content for the span.
        inlines: Rich inline content reflecting the strikethrough range.
    """

    text: str
    inlines: Sequence["InlineContent"] = field(default_factory=tuple)
    type: ClassVar[str] = "strikethrough"

    def __post_init__(self) -> None:
        object.__setattr__(self, "inlines", _normalize_sequence(self.inlines))

    def _serialize(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "inlines": [_serialize_inline(inline) for inline in self.inlines],
        }


InlineContent = Text | Link | Image | Strikethrough


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
    children: Sequence["Element"] = field(default_factory=tuple)
    type: ClassVar[str] = "list_item"

    def __post_init__(self) -> None:
        object.__setattr__(self, "inlines", _normalize_sequence(self.inlines))
        object.__setattr__(self, "children", _normalize_sequence(self.children))

    def _serialize(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "inlines": [_serialize_inline(inline) for inline in self.inlines],
            "children": [child.to_dict() for child in self.children],
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


@dataclass(frozen=True)
class TaskItem(Element):
    """Task list item with completion state.

    Args:
        text: Visible task text.
        checked: Whether the task is completed.
        inlines: Inline content matching the task text.
    """

    text: str
    checked: bool
    inlines: Sequence[InlineContent] = field(default_factory=tuple)
    type: ClassVar[str] = "task_item"

    def __post_init__(self) -> None:
        object.__setattr__(self, "inlines", _normalize_sequence(self.inlines))

    def _serialize(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "checked": self.checked,
            "inlines": [_serialize_inline(inline) for inline in self.inlines],
        }


@dataclass(frozen=True)
class TaskList(Element):
    """Checklist container.

    Args:
        items: Task items preserving order.
    """

    items: Sequence[TaskItem]
    type: ClassVar[str] = "task_list"

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", _normalize_sequence(self.items))

    def _serialize(self) -> dict[str, Any]:
        return {"items": [item.to_dict() for item in self.items]}


@dataclass(frozen=True)
class DefinitionItem(Element):
    """Definition list entry mapping a term to definitions.

    Args:
        term: Defined term.
        descriptions: Element blocks describing the term.
        inlines: Inline rendering of the term text.
    """

    term: str
    descriptions: Sequence[Element]
    inlines: Sequence[InlineContent] = field(default_factory=tuple)
    type: ClassVar[str] = "definition_item"

    def __post_init__(self) -> None:
        object.__setattr__(self, "descriptions", _normalize_sequence(self.descriptions))
        object.__setattr__(self, "inlines", _normalize_sequence(self.inlines))

    def _serialize(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "inlines": [_serialize_inline(inline) for inline in self.inlines],
            "descriptions": [item.to_dict() for item in self.descriptions],
        }


@dataclass(frozen=True)
class DefinitionList(Element):
    """Container for a set of term definitions.

    Args:
        items: Ordered collection of definition entries.
    """

    items: Sequence[DefinitionItem]
    type: ClassVar[str] = "definition_list"

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", _normalize_sequence(self.items))

    def _serialize(self) -> dict[str, Any]:
        return {"items": [item.to_dict() for item in self.items]}


@dataclass(frozen=True)
class TableCell(Element):
    """Single table cell with inline content.

    Args:
        text: Plain text content of the cell.
        inlines: Inline elements matching the raw text.
    """

    text: str
    inlines: Sequence[InlineContent] = field(default_factory=tuple)
    type: ClassVar[str] = "table_cell"

    def __post_init__(self) -> None:
        object.__setattr__(self, "inlines", _normalize_sequence(self.inlines))

    def _serialize(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "inlines": [_serialize_inline(inline) for inline in self.inlines],
        }


@dataclass(frozen=True)
class TableRow(Element):
    """Row inside a table.

    Args:
        cells: Cells contained in the row.
        is_header: Flag indicating the row should be treated as a header.
    """

    cells: Sequence[TableCell]
    is_header: bool = False
    type: ClassVar[str] = "table_row"

    def __post_init__(self) -> None:
        object.__setattr__(self, "cells", _normalize_sequence(self.cells))

    def _serialize(self) -> dict[str, Any]:
        return {
            "is_header": self.is_header,
            "cells": [cell.to_dict() for cell in self.cells],
        }


@dataclass(frozen=True)
class Table(Element):
    """Markdown table block.

    Args:
        rows: Rows included in the table, header first if present.
        caption: Optional caption text for the table.
    """

    rows: Sequence[TableRow]
    caption: str | None = None
    type: ClassVar[str] = "table"

    def __post_init__(self) -> None:
        object.__setattr__(self, "rows", _normalize_sequence(self.rows))

    def _serialize(self) -> dict[str, Any]:
        return {
            "caption": self.caption,
            "rows": [row.to_dict() for row in self.rows],
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
    "DefinitionItem",
    "DefinitionList",
    "Element",
    "Heading",
    "Image",
    "InlineContent",
    "Link",
    "List",
    "ListItem",
    "Page",
    "Paragraph",
    "Strikethrough",
    "Table",
    "TableCell",
    "TableRow",
    "TaskItem",
    "TaskList",
    "Text",
]
