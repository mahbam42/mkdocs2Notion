from mkdocs2notion.markdown.elements import List, ListItem, Paragraph, Text


def test_list_to_dict_includes_order_flag_and_consistent_type() -> None:
    list_element = List(
        items=(ListItem(text="one"), ListItem(text="two")), ordered=True
    )

    assert list_element.to_dict() == {
        "type": "list",
        "ordered": True,
        "items": [
            {"type": "list_item", "text": "one", "inlines": []},
            {"type": "list_item", "text": "two", "inlines": []},
        ],
    }


def test_sequences_are_normalized_to_tuples() -> None:
    paragraph = Paragraph(text="hi", inlines=[Text(text="hi")])
    list_element = List(items=[ListItem(text="alpha"), ListItem(text="beta")])

    assert isinstance(paragraph.inlines, tuple)
    assert all(isinstance(item, ListItem) for item in list_element.items)
    assert isinstance(list_element.items, tuple)
