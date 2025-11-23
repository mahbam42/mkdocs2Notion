"""Lightweight YAML loader for environments without PyYAML."""

from __future__ import annotations

from typing import Any


def safe_load(text: str) -> Any:
    """Parse a minimal subset of YAML into Python objects.

    The implementation is intentionally small and supports only the constructs
    needed by the test fixtures:

    * nested dictionaries via indentation
    * lists prefixed with ``-``
    * ``key: value`` pairs

    Args:
        text: Raw YAML content.

    Returns:
        Any: A nested combination of dicts, lists, and scalars.
    """

    lines = [
        (_indentation(line), line.strip())
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not lines:
        return {}

    def _parse(expected_indent: int) -> Any:
        if not lines:
            return {}

        use_list: bool | None = None
        items_list: list[Any] = []
        items_dict: dict[str, Any] = {}

        while lines:
            indent, content = lines[0]
            if indent < expected_indent:
                break
            lines.pop(0)

            if content.startswith("- "):
                if use_list is False:
                    # switching from dict to list is not supported; rewind one line
                    lines.insert(0, (indent, content))
                    break
                use_list = True
                value = content[2:].strip()
                if value and ":" in value:
                    key, rest = value.split(":", 1)
                    if rest.strip() == "":
                        child = _parse(indent + 2)
                        items_list.append({key.strip(): child})
                    else:
                        items_list.append({key.strip(): _parse_scalar(rest.strip())})
                elif value == "":
                    items_list.append(_parse(indent + 2))
                else:
                    items_list.append(_parse_scalar(value))
            else:
                if use_list is True:
                    lines.insert(0, (indent, content))
                    break
                use_list = False
                if ":" not in content:
                    continue
                key, rest = content.split(":", 1)
                if rest.strip() == "":
                    items_dict[key.strip()] = _parse(indent + 2)
                else:
                    items_dict[key.strip()] = _parse_scalar(rest.strip())

        return items_list if use_list else items_dict

    return _parse(lines[0][0])


def _indentation(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_scalar(value: str) -> Any:
    value = value.strip().strip('"').strip("'")
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.isdigit():
        try:
            return int(value)
        except ValueError:
            pass
    try:
        return float(value)
    except ValueError:
        return value
