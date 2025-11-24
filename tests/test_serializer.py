"""Unit tests for the Notion block serializer."""

from mkdocs2notion.markdown.elements import (
    Admonition,
    CodeBlock,
    DefinitionItem,
    DefinitionList,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    Paragraph,
    Strikethrough,
    Table,
    TableCell,
    TableRow,
    TaskItem,
    TaskList,
    Text,
)
from mkdocs2notion.notion.serializer import serialize_elements, text_rich


def _stub_resolve_image(image: Image) -> dict:
    return {
        "type": "image",
        "image": {
            "type": "external",
            "external": {"url": image.src},
            "caption": [text_rich(image.alt or image.src)],
        },
    }


def test_paragraph_renders_rich_text_and_inline_image() -> None:
    paragraph = Paragraph(
        text="Hello Docs",
        inlines=(
            Text(text="Hello"),
            Link(text="Docs", target="https://example.com"),
            Image(src="https://example.com/image.png", alt="diagram"),
        ),
    )

    blocks = serialize_elements([paragraph], _stub_resolve_image)

    assert len(blocks) == 2
    paragraph_block, image_block = blocks

    assert paragraph_block["type"] == "paragraph"
    rich_text = paragraph_block["paragraph"]["rich_text"]
    assert rich_text[0]["text"]["content"] == "Hello"
    assert rich_text[1]["text"]["link"]["url"] == "https://example.com"

    assert image_block["type"] == "image"
    assert image_block["image"]["caption"][0]["text"]["content"] == "diagram"


def test_heading_levels_map_to_notion_types() -> None:
    heading = Heading(level=2, text="Subheading", inlines=(Text(text="Subheading"),))

    blocks = serialize_elements([heading], _stub_resolve_image)

    assert blocks[0]["type"] == "heading_2"
    assert blocks[0]["heading_2"]["rich_text"][0]["text"]["content"] == "Subheading"


def test_ordered_list_items_generate_numbered_blocks() -> None:
    items = (
        ListItem(text="First", inlines=(Text(text="First"),)),
        ListItem(text="Second", inlines=(Text(text="Second"),)),
    )
    list_element = List(items=items, ordered=True)

    blocks = serialize_elements([list_element], _stub_resolve_image)

    assert {block["type"] for block in blocks} == {"numbered_list_item"}
    assert blocks[0]["numbered_list_item"]["rich_text"][0]["text"]["content"] == "First"


def test_nested_list_items_render_as_children() -> None:
    nested_list = List(
        items=(ListItem(text="Child", inlines=(Text(text="Child"),)),)
    )
    parent_item = ListItem(
        text="Parent",
        inlines=(Text(text="Parent"),),
        children=(nested_list,),
    )
    list_element = List(items=(parent_item,), ordered=False)

    blocks = serialize_elements([list_element], _stub_resolve_image)

    assert blocks[0]["type"] == "bulleted_list_item"
    children = blocks[0]["bulleted_list_item"]["children"]
    assert children
    assert children[0]["type"] == "bulleted_list_item"
    assert (
        children[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"]
        == "Child"
    )


def test_code_block_defaults_language() -> None:
    code_block = CodeBlock(language=None, code="print('hi')")

    blocks = serialize_elements([code_block], _stub_resolve_image)

    assert blocks[0]["type"] == "code"
    assert blocks[0]["code"]["language"] == "plain text"
    assert blocks[0]["code"]["rich_text"][0]["text"]["content"] == "print('hi')"


def test_admonition_becomes_callout_with_children() -> None:
    admonition = Admonition(
        kind="warning",
        title="Heads up",
        content=(Paragraph(text="Be careful", inlines=(Text(text="Be careful"),)),),
    )

    blocks = serialize_elements([admonition], _stub_resolve_image)

    assert blocks[0]["type"] == "callout"
    callout = blocks[0]["callout"]
    assert callout["icon"]["emoji"] == "⚠️"
    assert callout["rich_text"][0]["text"]["content"] == "Heads up"
    assert callout["children"][0]["paragraph"]["rich_text"][0]["text"]["content"] == "Be careful"


def test_strikethrough_inlines_set_annotations() -> None:
    paragraph = Paragraph(
        text="strike",
        inlines=(Strikethrough(text="strike"),),
    )

    blocks = serialize_elements([paragraph], _stub_resolve_image)

    rich_text = blocks[0]["paragraph"]["rich_text"][0]
    assert rich_text["annotations"]["strikethrough"] is True


def test_task_list_serializes_to_todo_blocks() -> None:
    task_list = TaskList(
        items=(
            TaskItem(text="done", checked=True, inlines=(Text(text="done"),)),
            TaskItem(text="todo", checked=False, inlines=(Text(text="todo"),)),
        )
    )

    blocks = serialize_elements([task_list], _stub_resolve_image)

    assert [block["type"] for block in blocks][:2] == ["to_do", "to_do"]
    assert blocks[0]["to_do"]["checked"] is True
    assert blocks[0]["to_do"]["rich_text"][0]["text"]["content"] == "done"
    assert blocks[1]["to_do"]["checked"] is False


def test_definition_list_becomes_bulleted_items_with_children() -> None:
    definition_list = DefinitionList(
        items=(
            DefinitionItem(
                term="Term",
                inlines=(Text(text="Term"),),
                descriptions=(Paragraph(text="Definition", inlines=(Text(text="Definition"),)),),
            ),
        )
    )

    blocks = serialize_elements([definition_list], _stub_resolve_image)

    assert blocks[0]["type"] == "bulleted_list_item"
    bullet = blocks[0]["bulleted_list_item"]
    assert bullet["rich_text"][0]["text"]["content"] == "Term"
    assert bullet["rich_text"][0]["annotations"]["bold"] is True
    assert (
        bullet["children"][0]["paragraph"]["rich_text"][0]["text"]["content"]
        == ": "
    )
    assert (
        bullet["children"][0]["paragraph"]["rich_text"][1]["text"]["content"]
        == "Definition"
    )


def test_table_serializes_to_table_block_with_rows() -> None:
    table = Table(
        rows=(
            TableRow(
                cells=(
                    TableCell(text="H1", inlines=(Text(text="H1"),)),
                    TableCell(text="H2", inlines=(Text(text="H2"),)),
                ),
                is_header=True,
            ),
            TableRow(
                cells=(
                    TableCell(text="R1C1", inlines=(Text(text="R1C1"),)),
                    TableCell(text="R1C2", inlines=(Text(text="R1C2"),)),
                )
            ),
        )
    )

    blocks = serialize_elements([table], _stub_resolve_image)

    assert blocks[0]["type"] == "table"
    table_payload = blocks[0]["table"]
    assert table_payload["table_width"] == 2
    assert table_payload["has_column_header"] is True
    assert len(table_payload["children"]) == 2
    header_row = table_payload["children"][0]
    assert header_row["type"] == "table_row"
    assert header_row["table_row"]["cells"][0][0]["text"]["content"] == "H1"
