# Parser Internals

This document explains the Markdown element model and the deterministic parsing strategy used to produce Notion-ready structures.

## Element Model

Elements are immutable dataclasses defined in `mkdocs2notion/markdown/elements.py`. Each block exposes a `type` identifier and `to_notion()` for stable serialization.

Key blocks:
- `Page` holds ordered child blocks and the derived title.
- Structural blocks include `Heading`, `Paragraph`, `BulletedListItem`, `NumberedListItem`, `Quote`, `Toggle` (for tab content), `Callout`, `CodeBlock`, `Table`/`TableCell`, `Divider`, `Image`, and `RawMarkdown` for passthroughs.
- Inline spans include `TextSpan`, `LinkSpan`, `ImageSpan`, and `StrikethroughSpan`; spans attach to headings, paragraphs, list items, toggles, and table cells. Strikethrough spans can nest other inline spans.
- Paragraph parsing extracts inline images into standalone `Image` blocks while keeping other inline spans in the paragraph `inlines` field.

## Parsing Pipeline

1. `parse_markdown` splits text into lines and delegates to `_parse_lines`.
2. `_parse_lines` walks line-by-line, matching blocks in priority order: code fences, tabs (`=== "Title"` → `Toggle`), callouts (`> [!TYPE]`), block quotes, GitHub-flavored tables, dividers, numbered lists, bullet lists, headings, and finally paragraphs.
3. Specialized helpers (`_parse_heading`, `_parse_paragraph`, `_parse_list`, `_parse_code_block`, `_parse_callout`, `_parse_quote`, `_parse_tabs`, `_parse_table`) build blocks and recurse as needed for nested content.
4. Inline parsing via `_parse_inline_formatting` normalizes text and produces ordered inline spans. It supports links, images, and strikethrough (`~~text~~`); unsupported inline formatting is treated as literal text.
5. `_parse_code_block`, `_parse_callout`, and `_parse_table` fall back to `RawMarkdown` with warnings when input is malformed (unterminated fences, bad callout header, invalid table divider). Tabs are also passed through as raw markdown when headers are malformed or empty.
6. Title inference prefers the first level-1 heading; otherwise, `Document` is used.

## Inline Tokenization

Inline tokens follow `[text](target)` for links and `![alt](src)` for images. Strikethrough uses `~~` pairs and can wrap nested spans. The parser records spans in order and also produces a normalized text string that merges literal text with link labels.

## Extension Points

- Add new inline types by extending the inline span union and updating `_parse_inline_formatting`.
- Add new block-level elements by introducing additional detection branches in `_parse_lines` and corresponding parsing helpers.
- `Page.to_notion()` output is stable, making downstream adapters easy to implement or extend.

## Known Limitations

- Inline formatting is limited to links, images, and strikethrough; emphasis/strong/code spans are treated as plain text.
- List handling is flat; nested lists are not parsed.
- Tab blocks require the mkdocs-material `=== "Title"` pattern; malformed tabs are passed through as raw markdown.
- Callouts only support `[!TYPE]` headers and map type to icon via a small hardcoded set.
- GitHub-flavored table parsing expects a header row followed by a divider row; malformed tables become `RawMarkdown`.
- Code blocks require fenced backticks; indented code blocks are not parsed.
- Footnotes are currently ignored by the parser and serializer.

## Runner and CLI Flow

The Typer CLI in `mkdocs2notion/cli.py` wraps the runner entry points in `mkdocs2notion/runner.py`.

- `push` loads the mkdocs project (with optional `--mkdocs` path), parses documents for warnings, honors `--fresh` to rebuild the page-ID map, and aborts before publishing when warnings exist and `--strict` is set.
- `dry-run` renders the mkdocs navigation tree (when provided) and directory structure without contacting Notion; `--strict` causes the command to exit with status 1 if warnings were recorded.
- `validate` performs structure checks and markdown parsing only; it returns 1 on errors and treats warnings as failures when `--strict` is provided.
- Page IDs are persisted via `PageIdMap` next to the docs root; `--fresh` ignores existing mappings so new Notion pages are created.
