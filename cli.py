from __future__ import annotations

import typer
from pathlib import Path

from .runner import run_push, run_dry_run, run_validate


app = typer.Typer(
    name="mkdocs2notion",
    help="Publish Markdown directories (optionally using mkdocs.yml) into Notion.",
    add_completion=True,
)


@app.command("push")
def push(
    docs_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Path to the directory containing markdown files.",
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
) -> None:
    """
    Push a directory of Markdown documents to Notion.

    Examples:
        mkdocs2notion push docs/
        mkdocs2notion push docs/ --mkdocs mkdocs.yml
        mkdocs2notion push docs/ --parent <NOTION_PAGE_ID>

    """
    run_push(docs_path, mkdocs_yml, parent_page_id)


@app.command("dry-run")
def dry_run(
    docs_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Path to the directory containing markdown files.",
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
        file_okay=False,
        dir_okay=True,
        help="Path to documentation folder.",
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
    run_validate(docs_path, mkdocs_yml)


def main() -> None:
    """Entry point for Python -m execution."""
    app()


if __name__ == "__main__":
    main()
