from mkdocs2notion.markdown.elements import (
    BoldSpan,
    BulletedListItem,
    Callout,
    Image,
    LinkSpan,
    NumberedListItem,
    Paragraph,
    RawMarkdown,
    Table,
    TextSpan,
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
    assert callout.title == "Heading"
    assert callout.icon == "💡"
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


def test_numbered_list_children_keep_indentation_and_inlines() -> None:
    content = """1. First item
    Extra details with a [link](https://example.com)
    - Nested bullet
2. Second item
"""

    page = parse_markdown(content, source_file="list.md")

    first, second = page.children[0], page.children[1]
    assert isinstance(first, NumberedListItem)
    assert isinstance(second, NumberedListItem)
    assert first.children
    paragraph = first.children[0]
    assert isinstance(paragraph, Paragraph)
    assert paragraph.inlines and isinstance(paragraph.inlines[0], TextSpan)
    assert isinstance(paragraph.inlines[1], LinkSpan)
    nested = first.children[1]
    assert isinstance(nested, BulletedListItem)
    assert nested.text == "Nested bullet"


def test_star_bullets_preserve_inline_formatting() -> None:
    content = """* **Managers** — ensuring data stays clean and consistent
* **Inventory staff** — adjusting stock and reviewing deliveries
"""

    page = parse_markdown(content, source_file="teams.md")

    managers, staff = page.children
    assert isinstance(managers, BulletedListItem)
    assert isinstance(staff, BulletedListItem)
    assert managers.inlines and isinstance(managers.inlines[0], BoldSpan)
    assert managers.inlines[0].text == "Managers"
    assert staff.inlines and isinstance(staff.inlines[0], BoldSpan)
    assert staff.inlines[0].text == "Inventory staff"


def test_material_callout_with_nested_list_parses_structure() -> None:
    content = """!!! note "📚 Navigation"
    - Home
    - Guide
        - Overview
"""

    page = parse_markdown(content, source_file="nav.md")

    callout = page.children[0]
    assert isinstance(callout, Callout)
    assert callout.callout_type == "NOTE"
    assert callout.title == "Navigation"
    assert callout.icon == "📚"

    home, guide = callout.children[0], callout.children[1]
    assert isinstance(home, BulletedListItem)
    assert home.text == "Home"
    assert isinstance(guide, BulletedListItem)
    assert guide.text == "Guide"
    assert guide.children
    assert isinstance(guide.children[0], BulletedListItem)
    assert guide.children[0].text == "Overview"
