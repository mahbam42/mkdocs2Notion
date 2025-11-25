from pathlib import Path

from mkdocs2notion.loaders.directory import DirectoryTree, load_directory
from mkdocs2notion.loaders.mkdocs_nav import NavNode, load_mkdocs_nav
from mkdocs2notion.markdown.elements import BulletedListItem, Callout
from mkdocs2notion.markdown.parser import parse_markdown
from mkdocs2notion.notion.serializer import serialize_elements
from mkdocs2notion.runner import _rewrite_internal_links


def test_load_mkdocs_nav(sample_docs_path: Path) -> None:
    nav = load_mkdocs_nav(sample_docs_path / "mkdocs.yml")

    assert [child.title for child in nav.children] == ["Home", "Guide"]
    guide_children = nav.children[1].children
    assert [child.title for child in guide_children] == ["Overview", "Deep Dive"]
    assert guide_children[1].file == "nested/deep.md"


def test_nav_validation_detects_missing_files(sample_docs_path: Path) -> None:
    directory_tree = load_directory(sample_docs_path)
    nav = NavNode(title="root", children=[NavNode(title="Missing", file="absent.md")])

    errors, warnings = nav.validate(directory_tree)

    assert any("missing file" in warning for warning in warnings)


def test_nav_validation_flags_empty_entries() -> None:
    nav = NavNode(title="root", children=[NavNode(title="Empty Section")])

    errors, warnings = nav.validate(DirectoryTree(root=Path("."), documents=[]))

    assert not errors
    assert any("missing a file and children" in warning for warning in warnings)


def test_nav_pretty(sample_docs_path: Path) -> None:
    nav = load_mkdocs_nav(sample_docs_path / "mkdocs.yml")

    rendered = nav.pretty()

    assert "Navigation:" in rendered
    assert "Home → index.md" in rendered
    assert "Guide" in rendered


def test_nav_listing_parses_as_callout() -> None:
    nav = NavNode(
        title="root",
        children=[
            NavNode(title="Home", file="index.md"),
            NavNode(
                title="Guide",
                children=[NavNode(title="Overview", file="guide/overview.md")],
            ),
        ],
    )
    nav.assign_paths()

    markdown = nav.to_markdown_listing()
    page = parse_markdown(markdown, source_file="index.md")

    callout = page.children[0]
    assert isinstance(callout, Callout)
    assert callout.title == "Navigation"
    assert callout.icon == "📚"

    home, guide = callout.children
    assert isinstance(home, BulletedListItem)
    assert home.text == "Home"
    assert isinstance(guide, BulletedListItem)
    assert guide.text == "Guide"
    assert guide.children
    assert isinstance(guide.children[0], BulletedListItem)


def test_nav_listing_links_rewrite_to_notion_scheme() -> None:
    nav = NavNode(
        title="root",
        children=[
            NavNode(title="Home", file="index.md"),
            NavNode(
                title="Guide",
                children=[NavNode(title="Overview", file="guide/overview.md")],
            ),
        ],
    )
    nav.assign_paths()

    link_targets = {
        "index.md": "page-1",
        "guide/overview.md": "page-2",
        "guide": "page-2",
    }

    markdown = nav.to_markdown_listing()
    parsed_page = parse_markdown(markdown, source_file="index.md")
    rewritten, unresolved = _rewrite_internal_links(parsed_page, nav, link_targets)

    assert not unresolved
    notion_blocks = serialize_elements(rewritten.children)

    callout = notion_blocks[0]
    first_bullet = callout["callout"]["children"][0]["bulleted_list_item"]["rich_text"][0]
    assert first_bullet["text"]["content"] == "Home"
    assert first_bullet["text"]["link"] == {"url": "https://www.notion.so/page1"}
