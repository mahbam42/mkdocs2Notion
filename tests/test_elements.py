from typing import ClassVar

from mkdocs2notion.markdown.elements import (
    Admonition,
    CodeBlock,
    DefinitionItem,
    DefinitionList,
    Element,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    Page,
    Paragraph,
    Strikethrough,
    Table,
    TableCell,
    TableRow,
    TaskItem,
    TaskList,
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
    assert Strikethrough(text="crossed", inlines=[Text(text="crossed")]).to_dict() == {
        "type": "strikethrough",
        "text": "crossed",
        "inlines": [{"type": "text", "text": "crossed"}],
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


def test_task_list_to_dict_with_checked_items() -> None:
    task_list = TaskList(
        items=[
            TaskItem(text="done", checked=True, inlines=[Text(text="done")]),
            TaskItem(text="todo", checked=False, inlines=[Text(text="todo")]),
        ]
    )

    assert task_list.to_dict() == {
        "type": "task_list",
        "items": [
            {
                "type": "task_item",
                "text": "done",
                "checked": True,
                "inlines": [{"type": "text", "text": "done"}],
            },
            {
                "type": "task_item",
                "text": "todo",
                "checked": False,
                "inlines": [{"type": "text", "text": "todo"}],
            },
        ],
    }
    assert isinstance(task_list.items, tuple)
    assert all(isinstance(item.inlines, tuple) for item in task_list.items)


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


def test_definition_list_to_dict_with_descriptions() -> None:
    definition_list = DefinitionList(
        items=[
            DefinitionItem(
                term="Foo",
                descriptions=[Paragraph(text="Definition text")],
                inlines=[Text(text="Foo")],
            )
        ]
    )

    assert definition_list.to_dict() == {
        "type": "definition_list",
        "items": [
            {
                "type": "definition_item",
                "term": "Foo",
                "inlines": [{"type": "text", "text": "Foo"}],
                "descriptions": [
                    {"type": "paragraph", "text": "Definition text", "inlines": []}
                ],
            }
        ],
    }
    assert isinstance(definition_list.items, tuple)
    assert isinstance(definition_list.items[0].descriptions, tuple)
    assert isinstance(definition_list.items[0].inlines, tuple)


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


def test_table_to_dict_with_caption_and_header() -> None:
    table = Table(
        caption="Example",
        rows=[
            TableRow(
                cells=[
                    TableCell(text="H1", inlines=[Text(text="H1")]),
                    TableCell(text="H2", inlines=[Text(text="H2")]),
                ],
                is_header=True,
            ),
            TableRow(
                cells=[
                    TableCell(text="R1C1", inlines=[Text(text="R1C1")]),
                    TableCell(text="R1C2", inlines=[Text(text="R1C2")]),
                ]
            ),
        ],
    )

    assert table.to_dict() == {
        "type": "table",
        "caption": "Example",
        "rows": [
            {
                "type": "table_row",
                "is_header": True,
                "cells": [
                    {
                        "type": "table_cell",
                        "text": "H1",
                        "inlines": [{"type": "text", "text": "H1"}],
                    },
                    {
                        "type": "table_cell",
                        "text": "H2",
                        "inlines": [{"type": "text", "text": "H2"}],
                    },
                ],
            },
            {
                "type": "table_row",
                "is_header": False,
                "cells": [
                    {
                        "type": "table_cell",
                        "text": "R1C1",
                        "inlines": [{"type": "text", "text": "R1C1"}],
                    },
                    {
                        "type": "table_cell",
                        "text": "R1C2",
                        "inlines": [{"type": "text", "text": "R1C2"}],
                    },
                ],
            },
        ],
    }
    assert isinstance(table.rows, tuple)
    assert isinstance(table.rows[0].cells, tuple)


def test_sequences_are_normalized_to_tuples() -> None:
    list_element = List(items=[ListItem(text="alpha"), ListItem(text="beta")])
    admonition = Admonition(kind="note", title="Title", content=[Paragraph(text="p")])
    page = Page(title="Doc", children=[Paragraph(text="p")])
    task_list = TaskList(items=[TaskItem(text="alpha", checked=True)])
    definition_list = DefinitionList(
        items=[DefinitionItem(term="term", descriptions=[Paragraph(text="desc")])]
    )
    table = Table(
        rows=[TableRow(cells=[TableCell(text="cell")], is_header=True)],
    )

    assert isinstance(list_element.items, tuple)
    assert all(isinstance(item.inlines, tuple) for item in list_element.items)
    assert isinstance(admonition.content, tuple)
    assert isinstance(page.children, tuple)
    assert isinstance(task_list.items, tuple)
    assert all(isinstance(item.inlines, tuple) for item in task_list.items)
    assert isinstance(definition_list.items, tuple)
    assert isinstance(definition_list.items[0].descriptions, tuple)
    assert isinstance(table.rows, tuple)
    assert isinstance(table.rows[0].cells, tuple)
