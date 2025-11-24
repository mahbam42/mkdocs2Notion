from pathlib import Path

from mkdocs2notion.loaders.directory import DirectoryTree, load_directory
from mkdocs2notion.loaders.mkdocs_nav import NavNode, load_mkdocs_nav


def test_load_mkdocs_nav(sample_docs_path: Path) -> None:
    nav = load_mkdocs_nav(sample_docs_path / "mkdocs.yml")

    assert [child.title for child in nav.children] == ["Home", "Guide"]
    guide_children = nav.children[1].children
    assert [child.title for child in guide_children] == ["Overview", "Deep Dive"]
    assert guide_children[1].file == "nested/deep.md"


def test_nav_validation_detects_missing_files(sample_docs_path: Path) -> None:
    directory_tree = load_directory(sample_docs_path)
    nav = NavNode(title="root", children=[NavNode(title="Missing", file="absent.md")])

    errors = nav.validate(directory_tree)

    assert "missing file" in errors[0]


def test_nav_validation_flags_empty_entries() -> None:
    nav = NavNode(title="root", children=[NavNode(title="Empty Section")])

    errors = nav.validate(DirectoryTree(root=Path("."), documents=[]))

    assert "missing a file and children" in errors[0]


def test_nav_pretty(sample_docs_path: Path) -> None:
    nav = load_mkdocs_nav(sample_docs_path / "mkdocs.yml")

    rendered = nav.pretty()

    assert "Navigation:" in rendered
    assert "Home → index.md" in rendered
    assert "Guide" in rendered
