"""Deterministic Markdown parser for Notion-oriented structures."""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Tuple

from mkdocs2notion.markdown.elements import (
    Admonition,
    CodeBlock,
    DefinitionItem,
    DefinitionList,
    Element,
    Heading,
    Image,
    InlineContent,
    Link,
    ListItem,
    Page,
    Paragraph,
    Strikethrough,
    Table,
    TableCell,
    TableRow,
    TaskItem,
    TaskList,
    Text,
)
from mkdocs2notion.markdown.elements import (
    List as ListElement,
)


class MarkdownParseError(ValueError):
    """Raised when Markdown input cannot be parsed deterministically."""


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

    Raises:
        MarkdownParseError: If malformed Markdown prevents deterministic parsing
            (for example, an unterminated code fence).
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
        if _is_table_start(lines, index):
            table, index = _parse_table(lines, index)
            elements.append(table)
            continue
        if _is_definition_start(lines, index):
            definition_list, index = _parse_definition_list(lines, index)
            elements.append(definition_list)
            continue
        if _is_task_item(line):
            task_list, index = _parse_task_list(lines, index)
            elements.append(task_list)
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


def _parse_task_list(lines: Sequence[str], index: int) -> Tuple[TaskList, int]:
    """Parse consecutive task list items into a TaskList element."""

    items: List[TaskItem] = []
    while index < len(lines):
        line = lines[index]
        if not _is_task_item(line):
            break
        checked = _is_checked_task(line)
        text = _strip_task_marker(line)
        normalized, inline_content = _parse_inline_formatting(text)
        items.append(
            TaskItem(text=normalized, checked=checked, inlines=tuple(inline_content))
        )
        index += 1
    return TaskList(items=tuple(items)), index


def _parse_code_block(lines: Sequence[str], index: int) -> Tuple[CodeBlock, int]:
    """Parse fenced code block starting at index.

    Raises:
        MarkdownParseError: If the closing code fence cannot be found.
    """

    opening = lines[index]
    language = opening.strip("`").strip() or None
    start_line = index + 1
    index += 1
    code_lines: List[str] = []
    while index < len(lines) and not lines[index].startswith("```"):
        code_lines.append(lines[index])
        index += 1
    if index >= len(lines):
        raise MarkdownParseError(
            f"Unterminated code fence starting at line {start_line}"
        )
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
    """Parse inline links and images while preserving plain text.

    This parser walks the string character by character to support nested
    parentheses in link targets and optional titles. Image alt text is preserved
    in the normalized plain-text output to keep heading and paragraph text
    aligned with rendered content.
    """

    spans: List[InlineContent] = []
    normalized_parts: List[str] = []
    buffer: List[str] = []
    index = 0

    while index < len(text):
        if text.startswith("~~", index):
            closing = text.find("~~", index + 2)
            if closing == -1:
                buffer.append(text[index])
                index += 1
                continue

            inner_content = text[index + 2 : closing]
            inner_normalized, inner_inlines = _parse_inline_formatting(inner_content)

            if buffer:
                literal = "".join(buffer)
                spans.append(Text(text=literal))
                normalized_parts.append(literal)
                buffer = []

            spans.append(
                Strikethrough(
                    text=inner_normalized, inlines=tuple(inner_inlines)
                )
            )
            if inner_normalized:
                normalized_parts.append(inner_normalized)
            index = closing + 2
            continue

        if text[index] == "[" or (
            text[index] == "!" and index + 1 < len(text) and text[index + 1] == "["
        ):
            inline = _parse_inline_span(text, index)
            if inline is None:
                buffer.append(text[index])
                index += 1
                continue

            start, end, span, normalized_fragment = inline
            if buffer:
                literal = "".join(buffer)
                spans.append(Text(text=literal))
                normalized_parts.append(literal)
                buffer = []

            if start > index:
                literal_prefix = text[index:start]
                if literal_prefix:
                    spans.append(Text(text=literal_prefix))
                    normalized_parts.append(literal_prefix)

            spans.append(span)
            if normalized_fragment:
                normalized_parts.append(normalized_fragment)
            index = end
            continue

        buffer.append(text[index])
        index += 1

    if buffer:
        literal = "".join(buffer)
        spans.append(Text(text=literal))
        normalized_parts.append(literal)

    normalized_text = "".join(normalized_parts).strip()
    return normalized_text, spans


def _parse_definition_list(
    lines: Sequence[str], index: int
) -> Tuple[DefinitionList, int]:
    """Parse definition list blocks consisting of term/definition pairs."""

    items: List[DefinitionItem] = []
    while index < len(lines) and _is_definition_start(lines, index):
        term_line = lines[index].strip()
        term_normalized, term_inlines = _parse_inline_formatting(term_line)
        index += 1

        descriptions: List[Element] = []
        while index < len(lines):
            line = lines[index]
            if not line.strip():
                index += 1
                break
            if not line.lstrip().startswith(":"):
                break
            desc_text = line.lstrip()[1:].strip()
            normalized, inline_content = _parse_inline_formatting(desc_text)
            descriptions.append(
                Paragraph(text=normalized, inlines=tuple(inline_content))
            )
            index += 1

        items.append(
            DefinitionItem(
                term=term_normalized,
                descriptions=tuple(descriptions),
                inlines=tuple(term_inlines),
            )
        )
    return DefinitionList(items=tuple(items)), index


def _parse_table(lines: Sequence[str], index: int) -> Tuple[Table, int]:
    """Parse a GitHub-flavored Markdown table starting at index."""

    header_line = lines[index]
    header_cells = _split_table_row(header_line)
    rows: List[TableRow] = [
        TableRow(
            cells=tuple(_build_table_cells(header_cells)),
            is_header=True,
        )
    ]
    index += 2  # Skip header + divider

    while index < len(lines):
        line = lines[index]
        if not line.strip().startswith("|"):
            break
        row_cells = _split_table_row(line)
        rows.append(TableRow(cells=tuple(_build_table_cells(row_cells))))
        index += 1

    return Table(rows=tuple(rows)), index


def _parse_inline_span(
    text: str, start_index: int
) -> Tuple[int, int, InlineContent, str | None] | None:
    """Parse a link or image span starting at a given index.

    Args:
        text: Full text being processed.
        start_index: Index where the potential inline element begins.

    Returns:
        Tuple[int, int, InlineContent, str | None] | None: A tuple containing the
        original start index, the position immediately after the parsed span, the
        inline element, and the normalized text fragment to include. If parsing
        fails, returns ``None``.
    """

    is_image = text[start_index] == "!"
    bracket_index = start_index + 1 if is_image else start_index
    if bracket_index >= len(text) or text[bracket_index] != "[":
        return None

    bracket_content = _extract_balanced(text, bracket_index, "[", "]")
    if bracket_content is None:
        return None
    label, closing_bracket_index = bracket_content

    paren_index = closing_bracket_index + 1
    if paren_index >= len(text) or text[paren_index] != "(":
        return None

    paren_content = _extract_balanced(text, paren_index, "(", ")")
    if paren_content is None:
        return None
    link_target, closing_paren_index = paren_content
    target, _title = _split_target_and_title(link_target)
    if not target:
        return None

    if is_image:
        span: InlineContent = Image(src=target, alt=label)
        normalized_fragment = label
    else:
        span = Link(text=label, target=target)
        normalized_fragment = label

    return start_index, closing_paren_index + 1, span, normalized_fragment


def _extract_balanced(
    text: str, start_index: int, opener: str, closer: str
) -> Tuple[str, int] | None:
    """Extract text enclosed by balanced opener/closer characters."""

    if text[start_index] != opener:
        return None

    depth = 1
    index = start_index + 1
    while index < len(text):
        char = text[index]
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start_index + 1 : index], index
        index += 1
    return None


_TITLE_PATTERN = re.compile(r"^(?P<target>.+?)\s+(?P<title>(\".*\"|'.*'))$")


def _split_target_and_title(content: str) -> Tuple[str, str | None]:
    """Split link target from an optional title fragment."""

    cleaned = content.strip()
    if not cleaned:
        return "", None

    match = _TITLE_PATTERN.match(cleaned)
    if match:
        return match.group("target").strip(), match.group("title")
    return cleaned, None


_TABLE_DIVIDER_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$")


def _split_table_row(line: str) -> list[str]:
    """Split a pipe-delimited table row into cell strings."""

    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def _build_table_cells(cells: list[str]) -> list[TableCell]:
    """Convert raw cell strings into TableCell elements."""

    table_cells: list[TableCell] = []
    for cell in cells:
        normalized, inline_content = _parse_inline_formatting(cell)
        table_cells.append(
            TableCell(text=normalized, inlines=tuple(inline_content))
        )
    return table_cells


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


def _is_task_item(line: str) -> bool:
    """Determine if a line starts a task list item."""

    return bool(re.match(r"\s*-\s\[[ xX]\]\s", line))


def _is_checked_task(line: str) -> bool:
    """Return True if the task line is marked as completed."""

    return "[x]" in line.lower()


def _strip_task_marker(line: str) -> str:
    """Remove task marker from a line."""

    stripped = line.lstrip()
    after_marker = stripped.split("]", 1)
    if len(after_marker) == 2:
        return after_marker[1].strip()
    return stripped


def _is_definition_start(lines: Sequence[str], index: int) -> bool:
    """Detect the start of a definition list term/definition pair."""

    if index + 1 >= len(lines):
        return False
    if not lines[index].strip():
        return False
    return lines[index + 1].lstrip().startswith(":")


def _is_table_start(lines: Sequence[str], index: int) -> bool:
    """Detect whether the current line begins a table block."""

    if index + 1 >= len(lines):
        return False
    header = lines[index]
    divider = lines[index + 1]
    if "|" not in header or "|" not in divider:
        return False
    return bool(_TABLE_DIVIDER_RE.match(divider))


def _is_ordered_list_item(line: str) -> bool:
    """Check if a line is an ordered list item."""

    return bool(re.match(r"\d+\. ", line.lstrip()))


def _infer_title(children: Iterable[object]) -> str:
    """Choose a page title from the first level-one heading or fallback."""

    for element in children:
        if isinstance(element, Heading) and element.level == 1:
            return element.text
    return "Document"


__all__ = ["MarkdownParseError", "parse_markdown"]
