# Parser Internals

This document explains the Markdown element model and the deterministic parsing strategy used to produce Notion-ready structures.

## Element Model

Elements are immutable dataclasses defined in `mkdocs2notion/markdown/elements.py`. Each element exposes a `type` identifier and a `to_dict()` method for stable serialization.

Key blocks:
- `Page` holds an ordered list of child elements and the derived title.
- `Heading`, `Paragraph`, `List`, `ListItem`, `CodeBlock`, and `Admonition` represent structural blocks.
- `List.to_dict()` normalizes the shape by keeping `type: "list"` and an `ordered` flag rather than varying the type value.
- Inline elements include `Text`, `Link`, and `Image`, which appear inside headings, paragraphs, and list items. Images currently support external URLs; relative/inline file paths are parsed but not resolved or uploaded.

## Parsing Pipeline

1. `parse_markdown` splits text into lines and delegates to `_parse_lines`.
2. `_parse_lines` walks line-by-line, identifying block types via leading markers (`#`, list markers, ``` fences, `!!!`).
3. Specialized helpers (`_parse_heading`, `_parse_list`, `_parse_code_block`, `_parse_admonition`, `_parse_paragraph`) build block elements.
4. Inline parsing via `_parse_inline_formatting` extracts links and images while maintaining normalized text for headings and paragraphs.

## Inline Tokenization

Inline tokens follow `[text](target)` for links and `![alt](src)` for images. The parser records inline elements in order and also produces a normalized text string that merges literal text with link labels.

## Extension Points

- Add new inline types by extending the `InlineContent` union and updating `_parse_inline_formatting`.
- Add new block-level elements by introducing additional detection branches in `_parse_lines` and corresponding parsing helpers.
- `Page.to_dict()` output is stable, making downstream adapters easy to implement or extend.

## Known Limitations

- Inline formatting is limited to links and images; emphasis or code spans are treated as plain text.
- Admonition detection relies on four-space indents for content.
- Lists are flat and do not parse nested list structures.
- Code blocks require fenced backticks and do not currently support indented code blocks.

## Notion API Integration

This stage owns the communication with Notion after Markdown has been parsed and serialized.
It should remain idempotent so reruns update existing pages instead of duplicating them, and
it must be resilient to API limits.

### Core API Operations

- Create new pages within a chosen parent (database, page, or configured default root)
- Update existing pages when page IDs are known
- Batch-insert serialized content blocks to honor request size limits
- Upload images via multipart file uploads or external URLs
- Link pages together to mirror navigation structure

### Sync Logic

- Maintain a map of MkDocs paths to Notion page IDs to keep updates deterministic
- Optionally detect changed files for incremental syncs
- Reconcile deleted pages when entries disappear from the source tree
- Support both incremental runs and full re-imports

### Error Handling

- Respect Notion API rate limits (3 requests per second) with retries and backoff
- Handle pagination for large block trees
- Surface actionable errors when uploads fail or parents are misconfigured
