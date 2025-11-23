"""Deterministic Markdown parser for Notion-oriented structures."""
from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Tuple

from mkdocs2notion.markdown.elements import (
    Admonition,
    CodeBlock,
    Element,
    Heading,
    Image,
    InlineContent,
    Link,
    List as ListElement,
    ListItem,
    Page,
    Paragraph,
    Text,
)


def parse_markdown(text: str) -> Page:
    """Parse Markdown content into a Page element tree.

    The parser performs a line-oriented scan to deterministically identify block
    types and attaches inline structures such as links and images. The goal is
    to produce a stable intermediate representation suitable for later Notion
    serialization.

    Args:
        text: Raw Markdown source.

    Returns:
        Page: Root page containing all parsed child elements.
    """

    lines = text.splitlines()
    children, _ = _parse_lines(lines, 0)
    title = _infer_title(children)
    return Page(title=title, children=tuple(children))


def _parse_lines(lines: Sequence[str], start: int) -> Tuple[List[Element], int]:
    """Parse lines into block elements starting from an index.

    Args:
        lines: Raw Markdown lines.
        start: Starting index for parsing.

    Returns:
        Tuple[List[Element], int]: Parsed elements and the next index to read.
    """

    elements: List[Element] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("```"):
            code_block, index = _parse_code_block(lines, index)
            elements.append(code_block)
            continue
        if line.startswith("!!!"):
            admonition, index = _parse_admonition(lines, index)
            elements.append(admonition)
            continue
        if line.startswith("#"):
            heading, index = _parse_heading(lines, index)
            elements.append(heading)
            continue
        if _is_list_item(line):
            list_block, index = _parse_list(lines, index)
            elements.append(list_block)
            continue
        paragraph, index = _parse_paragraph(lines, index)
        elements.append(paragraph)
    return elements, index


def _parse_heading(lines: Sequence[str], index: int) -> Tuple[Heading, int]:
    """Parse a single heading line."""

    line = lines[index]
    level = len(line) - len(line.lstrip("#"))
    text = line[level:].strip()
    normalized, inline_content = _parse_inline_formatting(text)
    heading = Heading(level=level, text=normalized, inlines=tuple(inline_content))
    return heading, index + 1


def _parse_list(lines: Sequence[str], index: int) -> Tuple[ListElement, int]:
    """Parse consecutive list items into a List element."""

    items: List[ListItem] = []
    ordered = _is_ordered_list_item(lines[index])
    while index < len(lines):
        line = lines[index]
        if not _is_list_item(line):
            break
        current_ordered = _is_ordered_list_item(line)
        if current_ordered != ordered:
            break
        text = _strip_list_marker(line)
        normalized, inline_content = _parse_inline_formatting(text)
        items.append(ListItem(text=normalized, inlines=tuple(inline_content)))
        index += 1
    return ListElement(items=tuple(items), ordered=ordered), index


def _parse_code_block(lines: Sequence[str], index: int) -> Tuple[CodeBlock, int]:
    """Parse fenced code block starting at index."""

    opening = lines[index]
    language = opening.strip("`").strip() or None
    index += 1
    code_lines: List[str] = []
    while index < len(lines) and not lines[index].startswith("```"):
        code_lines.append(lines[index])
        index += 1
    if index < len(lines):
        index += 1
    return CodeBlock(language=language, code="\n".join(code_lines)), index


def _parse_admonition(lines: Sequence[str], index: int) -> Tuple[Admonition, int]:
    """Parse admonition blocks introduced by `!!!` markers."""

    header = lines[index].strip()
    _, _, raw_meta = header.partition("!!!")
    meta_parts = raw_meta.strip().split(" ", 1)
    kind = meta_parts[0] if meta_parts else "note"
    title = meta_parts[1].strip() if len(meta_parts) > 1 else None
    index += 1

    content_lines: List[str] = []
    while index < len(lines):
        line = lines[index]
        if not line.startswith("    ") and line.strip():
            break
        if not line.strip():
            content_lines.append("")
        else:
            content_lines.append(line[4:])
        index += 1

    content, _ = _parse_lines(content_lines, 0)
    return Admonition(kind=kind, title=title, content=tuple(content)), index


def _parse_paragraph(lines: Sequence[str], index: int) -> Tuple[Paragraph, int]:
    """Parse paragraph lines until a blank or new block."""

    buffer: List[str] = []
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            break
        if line.startswith(("#", "!!!", "```")) or _is_list_item(line):
            break
        buffer.append(line.strip())
        index += 1
    text = " ".join(buffer)
    normalized, inline_content = _parse_inline_formatting(text)
    return Paragraph(text=normalized, inlines=tuple(inline_content)), index


def _parse_inline_formatting(text: str) -> Tuple[str, List[InlineContent]]:
    """Parse inline links and images while preserving plain text."""

    pattern = re.compile(r"(!?\[([^\]]+)\]\(([^)]+)\))")
    cursor = 0
    spans: List[InlineContent] = []
    normalized_parts: List[str] = []
    for match in pattern.finditer(text):
        start, end = match.span()
        if start > cursor:
            literal = text[cursor:start]
            spans.append(Text(text=literal))
            normalized_parts.append(literal)
        label = match.group(2)
        target = match.group(3)
        if match.group(1).startswith("!"):
            spans.append(Image(src=target, alt=label))
        else:
            spans.append(Link(text=label, target=target))
            normalized_parts.append(label)
        cursor = end
    if cursor < len(text):
        trailing = text[cursor:]
        spans.append(Text(text=trailing))
        normalized_parts.append(trailing)
    normalized_text = "".join(normalized_parts).strip()
    return normalized_text, spans


def _strip_list_marker(line: str) -> str:
    """Remove list marker from a line."""

    stripped = line.lstrip()
    if stripped[0] == "-":
        return stripped[2:].strip()
    dot_index = stripped.find(". ")
    if dot_index != -1:
        return stripped[dot_index + 2 :].strip()
    return stripped


def _is_list_item(line: str) -> bool:
    """Determine if a line starts a list item."""

    stripped = line.lstrip()
    return stripped.startswith("- ") or bool(re.match(r"\d+\. ", stripped))


def _is_ordered_list_item(line: str) -> bool:
    """Check if a line is an ordered list item."""

    return bool(re.match(r"\d+\. ", line.lstrip()))


def _infer_title(children: Iterable[object]) -> str:
    """Choose a page title from the first level-one heading or fallback."""

    for element in children:
        if isinstance(element, Heading) and element.level == 1:
            return element.text
    return "Document"


__all__ = ["parse_markdown"]
