from mkdocs2notion.markdown.elements import (
    Heading,
    LinkSpan,
    ImageSpan,
    Paragraph,
    TextSpan,
)
from mkdocs2notion.notion.serializer import collect_images, serialize_elements


def test_serialize_elements_emits_notion_headings() -> None:
    heading = Heading(level=1, text="Title", inlines=(TextSpan(text="Title"),))

    payloads = serialize_elements((heading,))
    assert payloads[0]["type"] == "heading_1"
    assert payloads[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Title"


def test_collect_images_walks_children() -> None:
    heading = Heading(level=1, text="Title")

    images = collect_images((heading,))
    assert images == []


def test_inline_images_render_as_image_blocks() -> None:
    paragraph = Paragraph(text="", inlines=(ImageSpan(text="alt", source="http://img"),))

    payloads = serialize_elements((paragraph,))

    assert payloads[0]["type"] == "paragraph"
    assert payloads[1]["type"] == "image"
    assert payloads[1]["image"]["external"]["url"] == "http://img"


def test_invalid_link_targets_become_plain_text() -> None:
    paragraph = Paragraph(text="", inlines=(LinkSpan(text="anchor", target="#local"),))

    payloads = serialize_elements((paragraph,))

    rich_text = payloads[0]["paragraph"]["rich_text"][0]
    assert rich_text["text"]["content"] == "anchor"
    assert "link" not in rich_text["text"]
