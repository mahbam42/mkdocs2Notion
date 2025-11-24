from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

from .runner import PublishProgress, run_dry_run, run_push, run_validate

if TYPE_CHECKING:
    from .loaders.directory import DocumentNode

app = typer.Typer(
    name="mkdocs2notion",
    help="Publish Markdown directories (optionally using mkdocs.yml) into Notion.",
    add_completion=True,
)

console = Console()


class RichPublishProgress(PublishProgress):
    """Render an animated progress bar while publishing documents."""

    def __init__(self, console: Console) -> None:
        """Initialize the progress renderer.

        Args:
            console: Console used to display progress output.
        """
        self.console = console
        self._progress: Optional[Progress] = None
        self._task_id: Optional[TaskID] = None

    def start(self, total: int) -> None:
        """Start the animated progress bar.

        Args:
            total: Total number of documents to publish.
        """
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total} pages"),
            TimeElapsedColumn(),
            console=self.console,
            transient=True,
        )
        self._progress.start()
        self._task_id = self._progress.add_task("Pushing to Notion", total=total)

    def advance(self, document: "DocumentNode") -> None:
        """Advance the bar for a published document.

        Args:
            document: Document that has just been published.
        """
        if not self._progress or self._task_id is None:
            return

        self._progress.update(
            self._task_id, description=f"Pushing {document.relative_path}"
        )
        self._progress.advance(self._task_id)

    def finish(self) -> None:
        """Stop rendering the progress bar."""
        if not self._progress:
            return

        self._progress.stop()
        self._progress = None
        self._task_id = None


@app.command("push")
def push(
    docs_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=True,
        help=(
            "Path to a MkDocs project root, mkdocs.yml file, or directory "
            "containing markdown files."
        ),
    ),
    mkdocs_yml: Path | None = typer.Option(
        None,
        "--mkdocs",
        "-m",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Optional mkdocs.yml to define navigation structure.",
    ),
    parent_page_id: str | None = typer.Option(
        None,
        "--parent",
        "-p",
        help="Notion page ID under which all pages will be created (overrides env variable).",
    ),
    fresh: bool = typer.Option(
        False,
        "--fresh",
        "-f",
        help="Ignore cached Notion page IDs when pushing.",
    ),
) -> None:
    """
    Push a directory of Markdown documents to Notion.

    Examples:
        mkdocs2notion push docs/
        mkdocs2notion push docs/ --mkdocs mkdocs.yml
        mkdocs2notion push docs/ --parent <NOTION_PAGE_ID>
        mkdocs2notion push docs/ --fresh

    """
    progress = RichPublishProgress(console)
    run_push(docs_path, mkdocs_yml, parent_page_id, fresh=fresh, progress=progress)


@app.command("dry-run")
def dry_run(
    docs_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=True,
        help=(
            "Path to a MkDocs project root, mkdocs.yml file, or directory "
            "containing markdown files."
        ),
    ),
    mkdocs_yml: Path | None = typer.Option(
        None,
        "--mkdocs",
        "-m",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Optional mkdocs.yml used for structure.",
    ),
) -> None:
    """
    Perform a dry run without touching Notion.

    Shows what pages, sections, and hierarchy would be created.

    Example:
        mkdocs2notion dry-run docs/
    """
    run_dry_run(docs_path, mkdocs_yml)


@app.command("validate")
def validate(
    docs_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=True,
        help=(
            "Path to a MkDocs project root, mkdocs.yml file, or directory "
            "containing markdown files."
        ),
    ),
    mkdocs_yml: Path | None = typer.Option(
        None,
        "--mkdocs",
        "-m",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Optional mkdocs.yml file to validate alongside.",
    ),
) -> None:
    """
    Validate that the docs directory and mkdocs.yml (if supplied)
    follow expected patterns and are ready for publishing.

    Checks:
    - readable markdown files
    - valid mkdocs.yml structure
    - no duplicate page names
    - relative paths are correct
    """
    exit_code = run_validate(docs_path, mkdocs_yml)
    if exit_code:
        raise typer.Exit(code=exit_code)


def main() -> None:
    """Entry point for Python -m execution."""
    app()


if __name__ == "__main__":
    main()
