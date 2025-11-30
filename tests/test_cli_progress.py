from io import StringIO
from pathlib import Path

from rich.console import Console

from mkdocs2notion.cli import RichPublishProgress
from mkdocs2notion.loaders.directory import DocumentNode


def test_rich_progress_keeps_final_status_visible() -> None:
    console_file = StringIO()
    console = Console(
        file=console_file,
        force_terminal=True,
        color_system=None,
        width=80,
    )
    progress = RichPublishProgress(console)
    document = DocumentNode(
        path=Path("docs/index.md"),
        relative_path="docs/index.md",
        title="Index",
        content="",
    )

    progress.start(1)
    assert progress._progress is not None
    assert progress._progress.live.transient is False

    progress.advance(document)
    progress.finish()

    output = console_file.getvalue()
    assert "1/1 pages" in output
