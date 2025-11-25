from mkdocs2notion.markdown.parser import parse_markdown
from mkdocs2notion.utils.logging import WarningLogger


def test_logger_reports_paths_from_source_root(tmp_path) -> None:
    docs_dir = tmp_path / "docs_source"
    docs_dir.mkdir()
    file_path = docs_dir / "guide" / "page.md"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("```\n", encoding="utf-8")

    logger = WarningLogger("docs_source", source_root=docs_dir)
    parse_markdown(file_path.read_text(), source_file="guide/page.md", logger=logger)

    assert logger.warnings
    entry = logger.warnings[0]
    assert entry.filename == "docs_source/guide/page.md"
    assert entry.format().startswith(
        "docs_source/guide/page.md:1 [W005][CodeBlock] Unterminated code fence"
    )
