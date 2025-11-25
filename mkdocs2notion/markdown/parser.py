"""Deterministic Markdown parser tuned for Notion-aligned blocks."""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Tuple

from mkdocs2notion.markdown.elements import (
    Block,
    BulletedListItem,
    Callout,
    CodeBlock,
    Divider,
    Heading,
    Image,
    ImageSpan,
    InlineSpan,
    LinkSpan,
    NumberedListItem,
    Page,
    Paragraph,
    Quote,
    RawMarkdown,
    StrikethroughSpan,
    Table,
    TableCell,
    TextSpan,
    Toggle,
)
from mkdocs2notion.utils.logging import NullLogger, WarningLogger


class MarkdownParseError(ValueError):
    """Raised when Markdown input cannot be parsed deterministically."""


def parse_markdown(
    text: str, *, source_file: str = "", logger: WarningLogger | None = None
) -> Page:
    """Parse Markdown content into a Page block tree."""

    lines = text.splitlines()
    active_logger = logger or NullLogger()
    children, _ = _parse_lines(lines, 0, source_file, active_logger)
    title = _infer_title(children)
    return Page(title=title, children=tuple(children))


def _parse_lines(
    lines: Sequence[str],
    start: int,
    source_file: str,
    logger: WarningLogger,
) -> Tuple[List[Block], int]:
    elements: List[Block] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        if line.startswith("```"):
            code_block, index = _parse_code_block(lines, index, source_file, logger)
            elements.append(code_block)
            continue

        if _is_tab_header(line):
            toggles, index = _parse_tabs(lines, index, source_file, logger)
            elements.extend(toggles)
            continue

        if _is_callout_line(line):
            callout, index = _parse_callout(lines, index, source_file, logger)
            elements.append(callout)
            continue

        if line.startswith(">"):
            quote, index = _parse_quote(lines, index, source_file, logger)
            elements.append(quote)
            continue

        if _is_table_start(lines, index):
            table, index = _parse_table(lines, index, source_file, logger)
            elements.append(table)
            continue

        if _is_divider(line):
            elements.append(Divider(source_line=index + 1, source_file=source_file))
            index += 1
            continue

        if _is_numbered_list(line):
            block, index = _parse_list(lines, index, source_file, ordered=True, logger=logger)
            elements.extend(block)
            continue

        if _is_bullet_list(line):
            block, index = _parse_list(lines, index, source_file, ordered=False, logger=logger)
            elements.extend(block)
            continue

        if line.startswith("#"):
            heading, index = _parse_heading(lines, index, source_file)
            elements.append(heading)
            continue

        paragraph_blocks, index = _parse_paragraph(lines, index, source_file)
        elements.extend(paragraph_blocks)
    return elements, index


def _parse_heading(lines: Sequence[str], index: int, source_file: str) -> Tuple[Heading, int]:
    line = lines[index]
    level = len(line) - len(line.lstrip("#"))
    text = line[level:].strip()
    normalized, inline_content = _parse_inline_formatting(text)
    heading = Heading(
        level=level,
        text=normalized,
        inlines=tuple(inline_content),
        source_line=index + 1,
        source_file=source_file,
    )
    return heading, index + 1


def _parse_paragraph(
    lines: Sequence[str], index: int, source_file: str
) -> Tuple[List[Block], int]:
    buffer: List[str] = []
    start = index
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            break
        if line.startswith(("#", "```", ">", "=== ")) or _starts_block(line):
            break
        buffer.append(line.strip())
        index += 1
    text = " ".join(buffer)
    normalized, inline_content = _parse_inline_formatting(text)
    image_spans = [span for span in inline_content if isinstance(span, ImageSpan)]
    non_image_inlines = [span for span in inline_content if not isinstance(span, ImageSpan)]

    blocks: List[Block] = []
    if normalized or non_image_inlines:
        paragraph = Paragraph(
            text=normalized,
            inlines=tuple(non_image_inlines),
            source_line=start + 1,
            source_file=source_file,
        )
        blocks.append(paragraph)

    for image_span in image_spans:
        blocks.append(
            Image(
                source=image_span.source,
                alt=image_span.text,
                source_line=start + 1,
                source_file=source_file,
            )
        )

    return blocks, index


def _parse_list(
    lines: Sequence[str],
    index: int,
    source_file: str,
    *,
    ordered: bool,
    logger: WarningLogger,
) -> Tuple[List[Block], int]:
    items: List[Block] = []
    while index < len(lines):
        line = lines[index]
        if not _is_bullet_list(line) and not _is_numbered_list(line):
            break
        bullet_text = line.split(" ", 1)[1]
        normalized, inline_content = _parse_inline_formatting(bullet_text)
        item_class = NumberedListItem if ordered else BulletedListItem
        item = item_class(
            text=normalized,
            inlines=tuple(inline_content),
            source_line=index + 1,
            source_file=source_file,
        )
        items.append(item)
        index += 1
    return items, index


def _parse_code_block(
    lines: Sequence[str], index: int, source_file: str, logger: WarningLogger
) -> Tuple[CodeBlock, int]:
    opening = lines[index]
    language = opening.strip("`").strip() or None
    start_line = index
    index += 1
    code_lines: List[str] = []
    while index < len(lines) and not lines[index].startswith("```"):
        code_lines.append(lines[index])
        index += 1
    if index >= len(lines):
        logger.warn(
            filename=source_file,
            line=start_line + 1,
            element_type="CodeBlock",
            message="unterminated code fence, treating as raw markdown",
            code="file-io-warning",
        )
        raw = RawMarkdown(
            source_text="\n".join(lines[start_line:]),
            source_line=start_line + 1,
            source_file=source_file,
        )
        return raw, len(lines)
    code = "\n".join(code_lines)
    block = CodeBlock(
        language=language,
        code=code,
        source_line=start_line + 1,
        source_file=source_file,
    )
    return block, index + 1


def _parse_callout(
    lines: Sequence[str], index: int, source_file: str, logger: WarningLogger
) -> Tuple[Block, int]:
    start = index
    header = lines[index]
    match = _CALLOUT_RE.match(header)
    if not match:
        logger.warn(
            filename=source_file,
            line=start + 1,
            element_type="Callout",
            message="unsupported callout syntax, passing through",
            code="unsupported-block",
        )
        return _raw_block(lines, start, source_file)

    callout_type = match.group("type").upper()
    icon = _CALL_OUT_ICONS.get(callout_type.lower())
    body = match.group("body").strip()
    content_lines = [body] if body else []
    index += 1
    while index < len(lines) and lines[index].startswith(">"):
        content_lines.append(lines[index][1:].lstrip())
        index += 1

    children, _ = _parse_lines(content_lines, 0, source_file, logger)
    callout = Callout(
        callout_type=callout_type,
        icon=icon,
        children=tuple(children),
        source_line=start + 1,
        source_file=source_file,
    )
    return callout, index


def _parse_quote(
    lines: Sequence[str], index: int, source_file: str, logger: WarningLogger
) -> Tuple[Quote, int]:
    start = index
    content_lines: List[str] = []
    while index < len(lines) and lines[index].startswith(">"):
        content_lines.append(lines[index][1:].lstrip())
        index += 1
    children, _ = _parse_lines(content_lines, 0, source_file, logger)
    quote = Quote(children=tuple(children), source_line=start + 1, source_file=source_file)
    return quote, index


def _parse_tabs(
    lines: Sequence[str], index: int, source_file: str, logger: WarningLogger
) -> Tuple[List[Toggle], int]:
    toggles: List[Toggle] = []
    start = index
    while index < len(lines) and _is_tab_header(lines[index]):
        header = lines[index]
        title = header.split("\"", 2)[1]
        index += 1
        tab_content: List[str] = []
        while index < len(lines) and not _is_tab_header(lines[index]) and lines[index].strip():
            tab_content.append(lines[index].lstrip())
            index += 1
        children, _ = _parse_lines(tab_content, 0, source_file, logger)
        toggle = Toggle(
            title=title,
            inlines=(TextSpan(text=title),),
            children=tuple(children),
            source_line=start + 1,
            source_file=source_file,
        )
        toggles.append(toggle)
        if index < len(lines) and not lines[index].strip():
            index += 1
    if not toggles:
        logger.warn(
            filename=source_file,
            line=start + 1,
            element_type="Tabs",
            message="malformed tabs, keeping raw markdown",
            code="unsupported-block",
        )
        raw, index = _raw_block(lines, start, source_file)
        return [raw], index
    return toggles, index


def _parse_table(
    lines: Sequence[str], index: int, source_file: str, logger: WarningLogger
) -> Tuple[Block, int]:
    start = index
    if index + 1 >= len(lines):
        return _raw_table(lines, start, source_file, logger)
    header_line = lines[index]
    divider_line = lines[index + 1]
    header_cells = _split_table_row(header_line)
    divider_cells = _split_table_row(divider_line)
    if len(header_cells) != len(divider_cells) or not _TABLE_DIVIDER_RE.match(divider_line):
        return _raw_table(lines, start, source_file, logger)

    row_lines: List[str] = []
    index += 2
    while index < len(lines) and lines[index].lstrip().startswith("|"):
        row_lines.append(lines[index])
        index += 1

    try:
        headers = tuple(_build_cells(header_cells))
        rows = []
        for row_line in row_lines:
            row_cells = _split_table_row(row_line)
            rows.append(tuple(_build_cells(row_cells)))
        table = Table(
            headers=headers,
            rows=tuple(rows),
            source_line=start + 1,
            source_file=source_file,
        )
        return table, index
    except Exception:
        return _raw_table(lines, start, source_file, logger)


def _raw_table(
    lines: Sequence[str], index: int, source_file: str, logger: WarningLogger
) -> Tuple[RawMarkdown, int]:
    raw_lines: List[str] = []
    start = index
    while index < len(lines) and lines[index].strip():
        raw_lines.append(lines[index])
        index += 1
    logger.warn(
        filename=source_file,
        line=start + 1,
        element_type="Table",
        message="malformed GFM table, falling back to raw markdown",
        code="table-parse-warning",
    )
    raw = RawMarkdown(
        source_text="\n".join(raw_lines),
        source_line=start + 1,
        source_file=source_file,
    )
    return raw, index


def _raw_block(
    lines: Sequence[str], index: int, source_file: str
) -> Tuple[RawMarkdown, int]:
    raw_lines: List[str] = []
    start = index
    while index < len(lines) and lines[index].strip():
        raw_lines.append(lines[index])
        index += 1
    return (
        RawMarkdown(
            source_text="\n".join(raw_lines),
            source_line=start + 1,
            source_file=source_file,
        ),
        index,
    )


def _parse_inline_formatting(text: str) -> Tuple[str, List[InlineSpan]]:
    spans: List[InlineSpan] = []
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
            inner = text[index + 2 : closing]
            inner_normalized, inner_inlines = _parse_inline_formatting(inner)
            if buffer:
                literal = "".join(buffer)
                spans.append(TextSpan(text=literal))
                normalized_parts.append(literal)
                buffer = []
            spans.append(
                StrikethroughSpan(
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
                spans.append(TextSpan(text=literal))
                normalized_parts.append(literal)
                buffer = []
            if start > index:
                literal_prefix = text[index:start]
                if literal_prefix:
                    spans.append(TextSpan(text=literal_prefix))
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
        spans.append(TextSpan(text=literal))
        normalized_parts.append(literal)
    normalized_text = "".join(normalized_parts).strip()
    return normalized_text, spans


def _parse_inline_span(text: str, start_index: int):
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
        span = ImageSpan(text=label, source=target)
        normalized_fragment = ""
    else:
        span = LinkSpan(text=label, target=target)
        normalized_fragment = label
    return start_index, closing_paren_index + 1, span, normalized_fragment


def _extract_balanced(text: str, start_index: int, opener: str, closer: str):
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


def _split_target_and_title(content: str):
    cleaned = content.strip()
    if not cleaned:
        return "", None
    match = _TITLE_PATTERN.match(cleaned)
    if match:
        return match.group("target").strip(), match.group("title")
    return cleaned, None


_TABLE_DIVIDER_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$")
_CALLOUT_RE = re.compile(r"^>\s*\[!(?P<type>[A-Za-z]+)\]\s*(?P<body>.*)$")
_CALL_OUT_ICONS = {"note": "💡", "tip": "💡", "warning": "⚠️", "info": "ℹ️"}


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def _build_cells(cells: list[str]) -> list[TableCell]:
    result: list[TableCell] = []
    for cell in cells:
        normalized, inlines = _parse_inline_formatting(cell)
        result.append(TableCell(text=normalized, inlines=tuple(inlines)))
    return result


def _is_table_start(lines: Sequence[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    header = lines[index]
    divider = lines[index + 1]
    if "|" not in header or "|" not in divider:
        return False
    return True


def _is_divider(line: str) -> bool:
    return line.strip() in {"---", "***"}


def _is_bullet_list(line: str) -> bool:
    return line.lstrip().startswith("- ")


def _is_numbered_list(line: str) -> bool:
    return bool(re.match(r"\d+\. ", line.lstrip()))


def _starts_block(line: str) -> bool:
    return _is_bullet_list(line) or _is_numbered_list(line) or _is_table_start([line, ""], 0)


def _is_tab_header(line: str) -> bool:
    return line.startswith('=== "') and line.endswith('"')


def _is_callout_line(line: str) -> bool:
    return bool(_CALLOUT_RE.match(line))


def _infer_title(children: Iterable[object]) -> str:
    for element in children:
        if isinstance(element, Heading) and element.level == 1:
            return element.text
    return "Document"


__all__ = ["MarkdownParseError", "parse_markdown"]
