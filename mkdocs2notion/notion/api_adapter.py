from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class NotionAdapter(ABC):
    """
    Abstract interface for communicating with Notion.

    The rest of the codebase should never import Ultimate Notion directly.
    This makes it easy to switch between:

    - Ultimate Notion
    - Official Notion API client (future)
    - Mock adapters for unit tests
    """

    @abstractmethod
    def create_page(
        self,
        title: str,
        parent_page_id: Optional[str],
        blocks: List[Any],
    ) -> str:
        """Create a new Notion page and return its page_id."""
        raise NotImplementedError

    @abstractmethod
    def update_page(
        self,
        page_id: str,
        blocks: List[Any],
    ) -> None:
        """Update an existing Notion page."""
        raise NotImplementedError

    @abstractmethod
    def get_page(self, page_id: str) -> Any:
        """Retrieve metadata for an existing page."""
        raise NotImplementedError

    def create_or_update_page(
        self,
        title: str,
        parent_page_id: Optional[str],
        page_id: Optional[str],
        blocks: List[Any],
    ) -> str:
        """
        Convenience method:
        - if page_id exists → update
        - else → create
        """
        if page_id:
            self.update_page(page_id, blocks)
            return page_id

        return self.create_page(title, parent_page_id, blocks)


def get_default_adapter() -> NotionAdapter:
    """
    Factory that returns the preferred adapter.

    Eventually this may:

    - auto-detect Ultimate Notion if installed
    - fall back to a minimal raw Notion API client
    - use mocks for dry-run mode or testing

    For now, we return a placeholder adapter.
    """
    return DummyAdapter()


class DummyAdapter(NotionAdapter):
    """
    Development placeholder — prints actions instead of calling Notion.
    """

    def create_page(
        self,
        title: str,
        parent_page_id: Optional[str],
        blocks: List[Any],
    ) -> str:
        print(f"[dummy] create page '{title}' under {parent_page_id} ({len(blocks)} blocks)")
        return "dummy_page_id"

    def update_page(self, page_id: str, blocks: List[Any]) -> None:
        print(f"[dummy] update page {page_id} ({len(blocks)} blocks)")

    def get_page(self, page_id: str) -> Any:
        print(f"[dummy] get page {page_id}")
        return {"id": page_id}
