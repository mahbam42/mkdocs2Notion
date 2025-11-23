# Sample Page Title

Welcome to the example page that demonstrates the supported Markdown features.

## Links and Images

Paragraph text with an [inline link](https://example.com) and an embedded image: ![Diagram](https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Dunning%E2%80%93Kruger_Effect_01.svg/2462px-Dunning%E2%80%93Kruger_Effect_01.svg.png).

### Edge-case Inline Content

Links and images can include parentheses or titles without breaking parsing. For example:

- See the [API reference](https://example.com/path(with-details) "API Reference") for nested parentheses.
- Embedded image with spaces and a title: ![Flow chart](images/diagram (1).png "System Flow").

### Lists

- Unordered item one
- Unordered item two
- Unordered item three

1. Ordered item one
2. Ordered item two

#### Code Example

```python
print("hello world")
```

!!! note
    This is a simple note admonition with inline `code` and descriptive text.

#### Validation Example

The validator reports incomplete fenced code blocks to help catch formatting slips:

````markdown
```python
print("missing closing fence")
# (closing ``` would go here)
```
````
