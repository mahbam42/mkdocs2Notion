from mkdocs2notion.markdown.elements import List, ListItem


def test_list_to_dict_includes_order_flag_and_consistent_type() -> None:
    list_element = List(items=(ListItem(text="one"), ListItem(text="two")), ordered=True)

    assert list_element.to_dict() == {
        "type": "list",
        "ordered": True,
        "items": [
            {"type": "list_item", "text": "one", "inlines": []},
            {"type": "list_item", "text": "two", "inlines": []},
        ],
    }

