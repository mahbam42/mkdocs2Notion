from mkdocs2notion.markdown.elements import Heading, Page, TextSpan
from mkdocs2notion.notion.serializer import collect_images, serialize_elements


def test_serialize_elements_uses_block_serializer() -> None:
    heading = Heading(level=1, text="Title", inlines=(TextSpan(text="Title"),))
    page = Page(title="Doc", children=(heading,))

    payloads = serialize_elements(page.children)
    assert payloads[0]["type"] == "heading"
    assert payloads[0]["text"] == "Title"


def test_collect_images_walks_children() -> None:
    heading = Heading(level=1, text="Title")
    page = Page(title="Doc", children=(heading,))

    images = collect_images(page.children)
    assert images == []
