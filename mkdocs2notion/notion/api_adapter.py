"""Notion adapter implementations and factory."""

from __future__ import annotations

import json
import mimetypes
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    cast,
)
from urllib.parse import urljoin, urlparse

import requests
from notion_client import Client
from notion_client.errors import APIResponseError

from mkdocs2notion.markdown.elements import Element, Image, Page
from mkdocs2notion.notion.serializer import serialize_elements, text_rich


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
        source_path: Path | None = None,
    ) -> str:
        """Create a new Notion page and return its page_id."""
        raise NotImplementedError

    @abstractmethod
    def update_page(
        self,
        page_id: str,
        blocks: List[Any],
        source_path: Path | None = None,
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
        source_path: Path | None = None,
    ) -> str:
        """
        Convenience method:
        - if page_id exists → update
        - else → create
        """
        if page_id:
            self.update_page(page_id, blocks, source_path=source_path)
            return page_id

        return self.create_page(title, parent_page_id, blocks, source_path=source_path)


def get_default_adapter() -> NotionAdapter:
    """Return a functional adapter using the official Notion SDK.

    The factory currently prefers the official `notion-client` SDK. A future
    enhancement can auto-detect Ultimate Notion when it is available, but the
    basic SDK keeps this dependency light while remaining functional.

    Returns:
        NotionAdapter: Configured adapter ready for publishing.

    Raises:
        RuntimeError: If a Notion token is not provided via ``NOTION_TOKEN``.
    """

    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN is required to publish content to Notion.")

    parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID")
    return NotionClientAdapter(token=token, default_parent_page_id=parent_page_id)


class NotionClientAdapter(NotionAdapter):
    """Adapter backed by the official Notion Python client."""

    def __init__(self, token: str, default_parent_page_id: str | None = None) -> None:
        self.client = Client(auth=token)
        self._token = token
        self._api_version = os.getenv("NOTION_VERSION", "2022-06-28")
        self.default_parent_page_id = default_parent_page_id
        self._validated_parents: Set[str] = set()
        self._parent_types: Dict[str, str] = {}

    def create_or_update_page(
        self,
        title: str,
        parent_page_id: Optional[str],
        page_id: Optional[str],
        blocks: List[Any],
        source_path: Path | None = None,
    ) -> str:
        upload_parent = page_id or parent_page_id or self.default_parent_page_id
        parent_type = self._parent_types.get(upload_parent) if upload_parent else None
        if upload_parent and not parent_type:
            parent_type = self._validate_parent_access(upload_parent)
        payload_blocks = self._normalize_blocks(
            blocks, source_path, upload_parent, parent_type
        )
        if page_id:
            self._update_page(page_id, title, payload_blocks)
            return page_id
        return self._create_page(title, parent_page_id, payload_blocks)

    def create_page(
        self,
        title: str,
        parent_page_id: Optional[str],
        blocks: List[Any],
        source_path: Path | None = None,
    ) -> str:
        upload_parent = parent_page_id or self.default_parent_page_id
        parent_type = self._parent_types.get(upload_parent) if upload_parent else None
        if upload_parent and not parent_type:
            parent_type = self._validate_parent_access(upload_parent)
        payload_blocks = self._normalize_blocks(
            blocks, source_path, upload_parent, parent_type
        )
        return self._create_page(title, parent_page_id, payload_blocks)

    def update_page(
        self, page_id: str, blocks: List[Any], source_path: Path | None = None
    ) -> None:
        parent_type = self._parent_types.get(page_id) if page_id else None
        if page_id and not parent_type:
            parent_type = self._validate_parent_access(page_id)
        payload_blocks = self._normalize_blocks(
            blocks, source_path, page_id, parent_type
        )
        self._update_page(page_id, None, payload_blocks)

    def get_page(self, page_id: str) -> Any:
        return self.client.pages.retrieve(page_id=page_id)

    def _create_page(
        self, title: str, parent_page_id: str | None, children: list[dict[str, Any]]
    ) -> str:
        parent = self._build_parent(parent_page_id)
        result = cast(
            dict[str, Any],
            self.client.pages.create(
                parent=parent,
                properties={"title": {"title": [text_rich(title)]}},
                children=children,
            ),
        )
        return cast(str, result["id"])

    def _update_page(
        self,
        page_id: str,
        title: str | None,
        children: list[dict[str, Any]],
    ) -> None:
        if title:
            self.client.pages.update(
                page_id=page_id, properties={"title": {"title": [text_rich(title)]}}
            )
        self._replace_block_children(block_id=page_id, children=children)

    def _replace_block_children(
        self, block_id: str, children: list[dict[str, Any]]
    ) -> None:
        existing = cast(
            dict[str, Any], self.client.blocks.children.list(block_id=block_id)
        )
        for child in existing.get("results", []):
            self.client.blocks.delete(block_id=child["id"])
        if children:
            self.client.blocks.children.append(block_id=block_id, children=children)

    def _normalize_blocks(
        self,
        blocks: Sequence[Element] | Sequence[Mapping[str, Any]] | Page,
        source_path: Path | None,
        upload_parent: str | None,
        upload_parent_type: str | None,
    ) -> list[dict[str, Any]]:
        elements: Sequence[Element] | Sequence[Mapping[str, Any]]
        if isinstance(blocks, Page):
            elements = blocks.children
        else:
            elements = blocks

        materialized = list(elements)
        if materialized and all(isinstance(block, Mapping) for block in materialized):
            return [
                dict(block) for block in cast(Sequence[Mapping[str, Any]], materialized)
            ]

        resolver = lambda img: self._resolve_image(  # noqa: E731
            img, source_path, upload_parent, upload_parent_type
        )
        return serialize_elements(cast(Sequence[Element], materialized), resolver)

    def _build_parent(self, provided_parent: str | None) -> dict[str, Any]:
        parent_raw = provided_parent or self.default_parent_page_id
        if not parent_raw:
            raise RuntimeError(
                "A parent page ID is required. Provide --parent or NOTION_PARENT_PAGE_ID. "
                "Notion does not allow workspace-level pages for internal integrations."
            )
        normalized_parent = _normalize_parent_id(parent_raw)
        parent_type = self._parent_types.get(normalized_parent)
        if not parent_type:
            parent_type = self._validate_parent_access(normalized_parent)
        return {"type": f"{parent_type}_id", f"{parent_type}_id": normalized_parent}

    def _validate_parent_access(self, parent_id: str) -> str:
        if parent_id in self._validated_parents:
            return self._parent_types[parent_id]
        try:
            self.client.pages.retrieve(page_id=parent_id)
            self._cache_parent(parent_id, "page")
            return "page"
        except APIResponseError:
            pass

        try:
            self.client.databases.retrieve(database_id=parent_id)
            self._cache_parent(parent_id, "database")
            return "database"
        except APIResponseError as exc_db:
            raise RuntimeError(
                "Parent is not accessible. Verify the ID is correct (copy the 32-character "
                "ID from the share link) and that the integration is shared with the page "
                "or database."
            ) from exc_db

    def _cache_parent(self, parent_id: str, parent_type: str) -> None:
        self._validated_parents.add(parent_id)
        self._parent_types[parent_id] = parent_type

    def _resolve_image(
        self,
        image: Image,
        source_path: Path | None,
        upload_parent: str | None,
        upload_parent_type: str | None,
    ) -> dict[str, Any]:
        caption = image.alt or image.src
        if _is_valid_url(image.src):
            return _image_block("external", {"url": image.src}, caption)

        base = os.getenv("MKDOCS2NOTION_ASSET_BASE_URL", "").strip()
        if base and _is_valid_url(base):
            resolved = urljoin(base.rstrip("/") + "/", image.src.lstrip("/"))
            if _is_valid_url(resolved):
                return _image_block("external", {"url": resolved}, caption)

        if source_path:
            local_path = (source_path.parent / image.src).resolve()
            if local_path.is_file():
                file_type, payload = self._upload_local_file(
                    local_path, upload_parent, upload_parent_type
                )
                return _image_block(file_type, payload, caption)

        raise RuntimeError(
            "Image source is not a valid URL and no local file was found. Provide an "
            "absolute URL, ensure the image path is correct relative to the markdown "
            "file, or configure MKDOCS2NOTION_ASSET_BASE_URL."
        )

    def _upload_local_file(
        self, path: Path, upload_parent: str | None, upload_parent_type: str | None
    ) -> Tuple[str, dict[str, Any]]:
        mime_type, _ = mimetypes.guess_type(path.name)
        parent = upload_parent or self.default_parent_page_id
        if not parent:
            raise RuntimeError("A parent page ID is required to upload local images.")
        if upload_parent_type and upload_parent_type != "page":
            raise RuntimeError(
                "Local image uploads must target a page parent, not a database. Please use a page "
                "as the parent for image uploads."
            )
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": self._api_version,
            "Accept": "application/json",
        }
        with path.open("rb") as file_handle:
            files = {
                "file": (
                    path.name,
                    file_handle,
                    mime_type or "application/octet-stream",
                ),
            }
            response = requests.post(
                "https://api.notion.com/v1/files",
                headers=headers,
                files=files,
                data={"parent": json.dumps({"type": "page_id", "page_id": parent})},
                timeout=30,
            )
        if not response.ok:
            try:
                error_body = response.json()
            except ValueError:
                error_body = response.text
            raise RuntimeError(
                f"Failed to upload image {path.name} to Notion: {response.status_code} {error_body}"
            )

        payload = response.json()
        file_id = payload.get("id") or payload.get("file", {}).get("id")
        file_url = payload.get("file", {}).get("url")
        if file_id:
            return "file", {"file_id": file_id}
        if file_url:
            return "external", {"url": file_url}
        raise RuntimeError(
            "Unexpected response from Notion file upload; missing file id or url."
        )


def _normalize_parent_id(raw_id: str) -> str:
    """Extract the canonical Notion ID from a URL, slug, or raw ID."""

    cleaned = raw_id.strip()
    match = re.search(r"([0-9a-fA-F]{32})", cleaned)
    if not match:
        return cleaned
    hex_id = match.group(1)
    return (
        f"{hex_id[0:8]}-{hex_id[8:12]}-{hex_id[12:16]}-{hex_id[16:20]}-{hex_id[20:32]}"
    )


def _is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _image_block(
    image_type: str, payload: dict[str, Any], caption: str
) -> dict[str, Any]:
    if image_type == "file" and "file_id" in payload:
        image_payload: dict[str, Any] = {
            "type": "file",
            "file": {"file_id": payload["file_id"]},
        }
    elif image_type == "external" and "url" in payload:
        image_payload = {"type": "external", "external": {"url": payload["url"]}}
    else:
        raise RuntimeError("Unsupported image payload returned from upload.")

    image_payload["caption"] = [text_rich(caption)]
    return {"type": "image", "image": image_payload}


__all__ = ["NotionAdapter", "NotionClientAdapter", "get_default_adapter"]
