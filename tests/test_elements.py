from typing import ClassVar

from mkdocs2notion.markdown.elements import (
    Admonition,
    CodeBlock,
    Element,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    Page,
    Paragraph,
    Text,
)


def test_element_to_dict_reports_type_only() -> None:
    class Dummy(Element):
        type: ClassVar[str] = "custom"

        def _serialize(self) -> dict[str, str]:
            return {"extra": "ok"}

    base = Dummy()

    assert base.to_dict() == {"type": "custom", "extra": "ok"}


def test_inline_elements_to_dict() -> None:
    assert Text(text="plain").to_dict() == {"type": "text", "text": "plain"}
    assert Link(text="site", target="https://example.com").to_dict() == {
        "type": "link",
        "text": "site",
        "target": "https://example.com",
    }
    assert Image(src="img.png", alt="diagram").to_dict() == {
        "type": "image",
        "src": "img.png",
        "alt": "diagram",
    }


def test_heading_and_paragraph_serialize_inlines() -> None:
    inlines = [Text(text="Hello "), Link(text="world", target="/path")]
    heading = Heading(level=2, text="Hello world", inlines=inlines)
    paragraph = Paragraph(text="Hello world", inlines=inlines)

    expected_inlines = [
        {"type": "text", "text": "Hello "},
        {"type": "link", "text": "world", "target": "/path"},
    ]

    assert heading.to_dict() == {
        "type": "heading",
        "level": 2,
        "text": "Hello world",
        "inlines": expected_inlines,
    }
    assert paragraph.to_dict() == {
        "type": "paragraph",
        "text": "Hello world",
        "inlines": expected_inlines,
    }
    assert isinstance(heading.inlines, tuple)
    assert isinstance(paragraph.inlines, tuple)


def test_list_and_list_item_to_dict_with_inlines() -> None:
    list_element = List(
        items=[
            ListItem(text="one", inlines=[Text(text="one")]),
            ListItem(text="two", inlines=[Link(text="two", target="#two")]),
        ],
        ordered=True,
    )

    assert list_element.to_dict() == {
        "type": "list",
        "ordered": True,
        "items": [
            {
                "type": "list_item",
                "text": "one",
                "inlines": [{"type": "text", "text": "one"}],
            },
            {
                "type": "list_item",
                "text": "two",
                "inlines": [{"type": "link", "text": "two", "target": "#two"}],
            },
        ],
    }
    assert isinstance(list_element.items, tuple)
    assert all(isinstance(item.inlines, tuple) for item in list_element.items)


def test_code_block_to_dict_allows_missing_language() -> None:
    code_block = CodeBlock(language=None, code="print('hi')")

    assert code_block.to_dict() == {
        "type": "code_block",
        "language": None,
        "code": "print('hi')",
    }


def test_admonition_to_dict_with_nested_content() -> None:
    admonition = Admonition(
        kind="note",
        title=None,
        content=[
            Paragraph(text="line one"),
            CodeBlock(language="python", code="x = 1"),
        ],
    )

    assert admonition.to_dict() == {
        "type": "admonition",
        "kind": "note",
        "title": None,
        "content": [
            {"type": "paragraph", "text": "line one", "inlines": []},
            {"type": "code_block", "language": "python", "code": "x = 1"},
        ],
    }
    assert isinstance(admonition.content, tuple)


def test_page_to_dict_includes_children() -> None:
    page = Page(
        title="Doc",
        children=[
            Heading(level=1, text="Doc"),
            Admonition(kind="warning", title="Careful", content=[Paragraph(text="p")]),
        ],
    )

    assert page.to_dict() == {
        "type": "page",
        "title": "Doc",
        "children": [
            {
                "type": "heading",
                "level": 1,
                "text": "Doc",
                "inlines": [],
            },
            {
                "type": "admonition",
                "kind": "warning",
                "title": "Careful",
                "content": [
                    {"type": "paragraph", "text": "p", "inlines": []},
                ],
            },
        ],
    }
    assert isinstance(page.children, tuple)


def test_sequences_are_normalized_to_tuples() -> None:
    list_element = List(items=[ListItem(text="alpha"), ListItem(text="beta")])
    admonition = Admonition(kind="note", title="Title", content=[Paragraph(text="p")])
    page = Page(title="Doc", children=[Paragraph(text="p")])

    assert isinstance(list_element.items, tuple)
    assert all(isinstance(item.inlines, tuple) for item in list_element.items)
    assert isinstance(admonition.content, tuple)
    assert isinstance(page.children, tuple)
