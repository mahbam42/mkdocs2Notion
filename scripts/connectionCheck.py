import os

from notion_client import Client
from notion_client.errors import APIResponseError


def main() -> None:
    """Lightweight connectivity check against the Notion API."""
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN missing")

    notion = Client(auth=token)

    try:
        data_sources = notion.search(
            filter={"property": "object", "value": "data_source"}
        )
        pages = notion.search(filter={"property": "object", "value": "page"})
    except APIResponseError as exc:
        raise RuntimeError(f"Notion API call failed: {exc}") from exc

    print("✅ Successful Connection")
    print("Databases / Data sources:")
    for d in data_sources["results"]:
        title = d.get("title")
        name = title[0]["plain_text"] if title else "<no title>"
        print(f" - {name} - {d['id']}")

    print("\nPages:")
    for p in pages["results"]:
        print(" -", p["id"], p["properties"].get("title"))


if __name__ == "__main__":
    main()
