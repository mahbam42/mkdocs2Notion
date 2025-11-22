from mkdocs2notion.markdown.parser import parse_markdown


def test_parse_basic_blocks() -> None:
    content = """# Title

Paragraph text

- item one
- item two
"""

    blocks = parse_markdown(content)

    assert blocks[0] == {"type": "heading", "level": 1, "text": "Title"}
    assert blocks[1] == {"type": "paragraph", "text": "Paragraph text"}
    assert blocks[2]["text"] == "item one"
    assert blocks[3]["text"] == "item two"


def test_parse_code_block() -> None:
    content = """```python
print('hi')
```
"""

    blocks = parse_markdown(content)

    assert blocks[0]["type"] == "code_block"
    assert "print('hi')" in blocks[0]["text"]
    assert blocks[0]["language"] == "python"
