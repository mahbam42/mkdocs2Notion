from mkdocs2notion.markdown.elements import (
    Heading,
    ImageSpan,
    ItalicSpan,
    LinkSpan,
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


def test_invalid_links_fall_back_to_plain_text() -> None:
    paragraph = Paragraph(
        text="link",
        inlines=(LinkSpan(text="link", target="/relative/path"),),
    )

    payloads = serialize_elements((paragraph,))

    rich_text = payloads[0]["paragraph"]["rich_text"]
    expected = [
        {
            "type": "text",
            "text": {"content": "link"},
            "annotations": {
                "bold": False,
                "italic": False,
                "strikethrough": False,
                "underline": False,
                "code": False,
                "color": "default",
            },
        }
    ]
    assert rich_text == expected


def test_valid_links_include_url_metadata() -> None:
    paragraph = Paragraph(
        text="link",
        inlines=(LinkSpan(text="link", target="https://example.com"),),
    )

    payloads = serialize_elements((paragraph,))

    rich_text = payloads[0]["paragraph"]["rich_text"]
    assert rich_text[0]["text"]["link"] == {"url": "https://example.com"}


def test_italic_annotations_render() -> None:
    paragraph = Paragraph(text="", inlines=(ItalicSpan(text="soft"),))

    payloads = serialize_elements((paragraph,))

    annotations = payloads[0]["paragraph"]["rich_text"][0]["annotations"]
    assert annotations["italic"] is True
