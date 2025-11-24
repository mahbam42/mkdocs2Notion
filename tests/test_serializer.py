"""Unit tests for the Notion block serializer."""

from mkdocs2notion.markdown.elements import (
    Admonition,
    CodeBlock,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    Paragraph,
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
