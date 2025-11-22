from notion_client import Client
import os

def main():
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN missing")

    notion = Client(auth=token)

    databases = notion.search(query="", filter={"property": "object", "value": "database"})
    pages = notion.search(query="", filter={"property": "object", "value": "page"})

    print("Databases:")
    for d in databases["results"]:
        print(" -", d["id"], d["title"][0]["plain_text"] if d.get("title") else "<no title>")

    print("\nPages:")
    for p in pages["results"]:
        print(" -", p["id"], p["properties"].get("title"))

if __name__ == "__main__":
    main()
