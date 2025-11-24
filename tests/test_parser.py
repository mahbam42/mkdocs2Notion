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
    Text,
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
        'Mixed [spec](https://example.com/path(foo) "Spec Title") '
        'and image ![diagram](./assets/diagram (1).png "Diagram") end.'
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


def test_parse_headings_with_mixed_levels_and_inline_links() -> None:
    content = """# Title with [inline](https://example.com/path)
## Subheading
### Deep Heading with trailing space   
"""

    page = parse_markdown(content)
    headings = [child for child in page.children if isinstance(child, Heading)]

    assert page.title == "Title with inline"
    assert [heading.level for heading in headings] == [1, 2, 3]
    top_heading = headings[0]
    assert any(isinstance(inline, Link) for inline in top_heading.inlines)
    assert headings[-1].text == "Deep Heading with trailing space"


def test_parse_lists_separates_ordered_and_unordered_blocks() -> None:
    content = """- alpha
- beta

1. first
2. second

- trailing
"""

    page = parse_markdown(content)

    assert [type(child) for child in page.children] == [List, List, List]
    first_list, second_list, third_list = page.children

    assert not first_list.ordered
    assert [item.text for item in first_list.items] == ["alpha", "beta"]
    assert second_list.ordered
    assert [item.text for item in second_list.items] == ["first", "second"]
    assert not third_list.ordered
    assert [item.text for item in third_list.items] == ["trailing"]


def test_parse_inline_links_handles_nested_parentheses_and_ignores_invalid() -> None:
    content = (
        "Prefix [nested(fun)](http://example.com/path(a,b(c))) middle "
        "[broken](missing"
    )

    page = parse_markdown(content)
    paragraph = page.children[0]

    link = next(inline for inline in paragraph.inlines if isinstance(inline, Link))
    assert link.target == "http://example.com/path(a,b(c))"
    text_fragments = "".join(
        inline.text for inline in paragraph.inlines if isinstance(inline, Text)
    )
    assert "[broken](missing" in text_fragments


def test_parse_code_block_without_language_and_preserves_blank_lines() -> None:
    content = """Intro
```
line one

line three
```
After
"""

    page = parse_markdown(content)

    paragraph, code_block, trailing_paragraph = page.children
    assert isinstance(code_block, CodeBlock)
    assert code_block.language is None
    assert code_block.code == "line one\n\nline three"
    assert isinstance(paragraph, Paragraph)
    assert isinstance(trailing_paragraph, Paragraph)


def test_parse_admonition_with_multiple_paragraphs_and_fallback_title() -> None:
    content = """!!! warning Custom title
    first line

    second paragraph

Outside text
"""

    page = parse_markdown(content)

    admonition, trailing_paragraph = page.children
    assert isinstance(admonition, Admonition)
    assert admonition.kind == "warning"
    assert admonition.title == "Custom title"
    assert [type(block) for block in admonition.content] == [Paragraph, Paragraph]
    assert [block.text for block in admonition.content] == [
        "first line",
        "second paragraph",
    ]
    assert isinstance(trailing_paragraph, Paragraph)


def test_parse_markdown_is_deterministic_for_identical_input() -> None:
    content = """# Title

Intro with [link](https://example.com).

1. first
2. second

!!! note
    nested paragraph
"""

    first_page = parse_markdown(content)
    second_page = parse_markdown(content)

    assert first_page == second_page
    assert first_page.to_dict() == second_page.to_dict()
