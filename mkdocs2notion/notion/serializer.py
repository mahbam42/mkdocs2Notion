"""Serialize parsed blocks into lightweight dictionaries."""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from mkdocs2notion.markdown.elements import Block, Image


def serialize_elements(elements: Sequence[Block]) -> list[dict[str, Any]]:
    """Serialize parsed blocks to dictionaries using their ``to_notion`` hooks."""

    return [element.to_notion() for element in elements]


def collect_images(elements: Iterable[Block]) -> list[Image]:
    """Return any Image blocks nested inside the given elements."""

    images: list[Image] = []

    def _walk(block: Block) -> None:
        if isinstance(block, Image):
            images.append(block)
        for child in block.children:
            _walk(child)

    for element in elements:
        _walk(element)
    return images


__all__ = ["serialize_elements", "collect_images"]
