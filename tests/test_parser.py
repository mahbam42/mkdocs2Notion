from mkdocs2notion.markdown.elements import (
    Callout,
    Image,
    Paragraph,
    RawMarkdown,
    Table,
    Toggle,
)
from mkdocs2notion.markdown.parser import parse_markdown
from mkdocs2notion.utils.logging import WarningLogger


def test_parses_callouts_and_tabs_with_children() -> None:
    content = """> [!note] Heading
> detail line

=== "First"
Content in tab

=== "Second"
More
"""

    logger = WarningLogger("docs")
    page = parse_markdown(content, source_file="doc.md", logger=logger)

    callout = page.children[0]
    assert isinstance(callout, Callout)
    assert callout.callout_type == "NOTE"
    assert isinstance(callout.children[0], Paragraph)

    first_toggle = page.children[1]
    assert isinstance(first_toggle, Toggle)
    assert first_toggle.title == "First"
    assert isinstance(first_toggle.children[0], Paragraph)
    assert not logger.has_warnings()


def test_warns_and_falls_back_for_bad_table() -> None:
    content = """| h1 |
| not a divider |
| c1 |
"""

    logger = WarningLogger("docs")
    page = parse_markdown(content, source_file="table.md", logger=logger)

    assert isinstance(page.children[0], RawMarkdown)
    assert logger.has_warnings()
    assert "table" in logger.warnings[0].format().lower()


def test_parses_valid_table_cells() -> None:
    content = """| H1 | H2 |
| --- | --- |
| A | B |
"""

    page = parse_markdown(content, source_file="table.md")

    table = page.children[0]
    assert isinstance(table, Table)
    assert table.headers[0].text == "H1"
    assert table.rows[0][1].text == "B"


def test_unterminated_code_block_becomes_raw_markdown_with_warning() -> None:
    content = """Intro
```
code
"""

    logger = WarningLogger("docs")
    page = parse_markdown(content, source_file="code.md", logger=logger)

    assert isinstance(page.children[1], RawMarkdown)
    assert logger.has_warnings()


def test_inline_image_becomes_image_block() -> None:
    page = parse_markdown("![diagram](img.png)\n")

    assert isinstance(page.children[0], Image)
    assert page.children[0].source == "img.png"
    assert page.children[0].alt == "diagram"
