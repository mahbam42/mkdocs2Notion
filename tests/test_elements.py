from mkdocs2notion.markdown.elements import (
    Callout,
    Heading,
    LinkSpan,
    Page,
    Paragraph,
    Table,
    TableCell,
    TextSpan,
)


def test_blocks_include_metadata_and_children() -> None:
    heading = Heading(level=2, text="Title", inlines=(TextSpan(text="Title"),))
    paragraph = Paragraph(
        text="Body",
        inlines=(LinkSpan(text="docs", target="/docs"),),
        source_line=10,
        source_file="doc.md",
    )
    page = Page(title="Doc", children=(heading, paragraph))

    notion_payload = page.to_notion()
    assert notion_payload["type"] == "page"
    assert notion_payload["children"][0]["type"] == "heading"
    assert notion_payload["children"][1]["source_line"] == 10


def test_table_to_notion_structure() -> None:
    table = Table(
        headers=(TableCell(text="H1"), TableCell(text="H2")),
        rows=((TableCell(text="A"), TableCell(text="B")),),
    )

    payload = table.to_notion()
    assert payload["type"] == "table"
    assert payload["headers"][0]["text"] == "H1"
    assert payload["rows"][0][1]["text"] == "B"


def test_callout_serialization_keeps_icon() -> None:
    block = Callout(callout_type="NOTE", icon="💡", children=())

    payload = block.to_notion()
    assert payload["callout_type"] == "NOTE"
    assert payload["icon"] == "💡"
