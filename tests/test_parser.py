import pytest

from mkdocs2notion.markdown.elements import (
    Admonition,
    CodeBlock,
    Heading,
    Image,
    Link,
    List,
    Page,
    Paragraph,
)
from mkdocs2notion.markdown.parser import MarkdownParseError, parse_markdown


def test_parse_basic_blocks() -> None:
    content = """# Title

Paragraph text with [link](https://example.com).

- item one
- item two
"""

    page = parse_markdown(content)

    assert isinstance(page, Page)
    assert page.title == "Title"
    assert isinstance(page.children[0], Heading)
    assert isinstance(page.children[1], Paragraph)
    assert isinstance(page.children[2], List)
    paragraph = page.children[1]
    assert isinstance(paragraph.inlines[1], Link)


def test_parse_code_block_and_admonition() -> None:
    content = """!!! note Reminder
    important details

```python
print('hi')
```
"""

    page = parse_markdown(content)
    admonition = page.children[0]
    code_block = page.children[1]

    assert isinstance(admonition, Admonition)
    assert admonition.title == "Reminder"
    assert isinstance(admonition.content[0], Paragraph)

    assert isinstance(code_block, CodeBlock)
    assert "print('hi')" in code_block.code
    assert code_block.language == "python"


def test_parse_inline_images() -> None:
    content = "Inline with image ![alt](images/example.png)"

    page = parse_markdown(content)
    paragraph = page.children[0]

    assert isinstance(paragraph, Paragraph)
    assert any(isinstance(inline, Image) for inline in paragraph.inlines)


def test_parse_inline_links_and_images_with_parentheses_and_titles() -> None:
    content = (
        "Mixed [spec](https://example.com/path(foo) \"Spec Title\") "
        "and image ![diagram](./assets/diagram (1).png \"Diagram\") end."
    )

    page = parse_markdown(content)
    paragraph = page.children[0]

    assert isinstance(paragraph, Paragraph)
    assert paragraph.text == "Mixed spec and image diagram end."

    link = next(inline for inline in paragraph.inlines if isinstance(inline, Link))
    assert link.target == "https://example.com/path(foo)"
    assert link.text == "spec"

    image = next(inline for inline in paragraph.inlines if isinstance(inline, Image))
    assert image.src == "./assets/diagram (1).png"
    assert image.alt == "diagram"


def test_parse_unterminated_code_block_raises() -> None:
    content = """Intro
```python
print('hi')
"""

    with pytest.raises(MarkdownParseError) as excinfo:
        parse_markdown(content)

    assert "Unterminated code fence" in str(excinfo.value)
