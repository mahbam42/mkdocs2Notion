from pathlib import Path

from typer.testing import CliRunner

from mkdocs2notion.cli import app

runner = CliRunner()


def test_validate_command_success(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Title\n\nContent", encoding="utf-8")

    result = runner.invoke(app, ["validate", str(docs_dir)])

    assert result.exit_code == 0
    assert "All checks passed." in result.output


def test_validate_command_reports_errors(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("```python\nprint('hi')", encoding="utf-8")

    result = runner.invoke(app, ["validate", str(docs_dir)])

    assert result.exit_code == 1
    assert "Unterminated code fence" in result.output
    assert "validation error(s)" in result.output
