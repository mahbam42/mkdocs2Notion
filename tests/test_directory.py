from pathlib import Path

from mkdocs2notion.loaders.directory import load_directory


def test_load_directory_reads_titles(sample_docs_path: Path) -> None:
    tree = load_directory(sample_docs_path)

    assert {doc.relative_path for doc in tree.documents} == {
        "guide.md",
        "index.md",
        "nested/deep.md",
    }
    titles = {doc.relative_path: doc.title for doc in tree.documents}
    assert titles["index.md"] == "Home Page"
    assert titles["guide.md"] == "Guide"
    assert titles["nested/deep.md"] == "Deep Dive"


def test_pretty_renders_tree(sample_docs_path: Path) -> None:
    tree = load_directory(sample_docs_path)
    pretty = tree.pretty()

    assert "sample_docs/" in pretty
    assert "guide.md (Guide)" in pretty
    assert "nested/" in pretty
    assert "deep.md (Deep Dive)" in pretty


def test_duplicate_title_detection(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (docs_root / "a.md").write_text("# Title", encoding="utf-8")
    (docs_root / "b.md").write_text("# Title", encoding="utf-8")

    errors = load_directory(docs_root).validate()

    assert any("Duplicate title" in err for err in errors)


def test_filename_title_fallback(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (docs_root / "no-title-file.md").write_text("No headings here", encoding="utf-8")

    tree = load_directory(docs_root)

    assert tree.documents[0].title == "No title file".title()
