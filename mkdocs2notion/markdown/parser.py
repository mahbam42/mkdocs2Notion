"""Minimal Markdown parser that produces Notion-ready block stubs."""
from __future__ import annotations

from typing import Any, List


def parse_markdown(markdown: str) -> List[dict[str, Any]]:
    """Convert Markdown into a list of simplified block dictionaries.

    The output is intentionally lightweight so it can be validated without the
    Notion API. Each block contains enough structure for adapter translation.

    Args:
        markdown: Raw Markdown content.

    Returns:
        list[dict[str, Any]]: Ordered block representations.
    """

    blocks: list[dict[str, Any]] = []
    lines = markdown.splitlines()
    in_code = False
    code_lang = ""
    code_lines: list[str] = []

    def _flush_code() -> None:
        nonlocal code_lines, code_lang
        if code_lines or code_lang:
            blocks.append(
                {
                    "type": "code_block",
                    "language": code_lang or None,
                    "text": "\n".join(code_lines),
                }
            )
        code_lines = []
        code_lang = ""

    for raw_line in lines + [""]:
        line = raw_line.rstrip("\n")

        if line.startswith("```"):
            if in_code:
                _flush_code()
            else:
                code_lang = line.strip("`").strip()
            in_code = not in_code
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not line.strip():
            continue

        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            text = line[level:].strip()
            blocks.append({"type": "heading", "level": level, "text": text})
            continue

        if line.lstrip().startswith("- "):
            text = line.split("- ", 1)[1].strip()
            blocks.append({"type": "bulleted_list_item", "text": text})
            continue

        blocks.append({"type": "paragraph", "text": line.strip()})

    return blocks
