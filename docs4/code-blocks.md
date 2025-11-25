# Code Blocks

## Fenced code block

```python
def allocate_bin(item: str, quantity: int) -> str:
    """Return a bin label based on item and quantity."""
    size = "XL" if quantity > 100 else "STD"
    return f"{item}-{size}"
```

## Indented code block

    # Simple CSV export sketch
    for row in rows:
        line = ",".join(row)
        buffer.write(line + "\n")

Combine fenced and indented examples to confirm both render correctly and stay distinct during conversion.
