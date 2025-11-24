from pathlib import Path

import pytest

from mkdocs2notion.loaders.mkdocs_project import load_mkdocs_project


@pytest.fixture
def mkdocs_project_path() -> Path:
    return Path(__file__).parent / "fixtures" / "mkdocs_project"


@pytest.fixture
def mkdocs_project_unlisted_path() -> Path:
    return Path(__file__).parent / "fixtures" / "mkdocs_project_unlisted"


def test_loads_docs_dir_and_orders_documents(mkdocs_project_path: Path) -> None:
    project = load_mkdocs_project(mkdocs_project_path)

    assert project.docs_path.name == "documentation"
    assert [doc.relative_path for doc in project.ordered_documents()] == [
        "index.md",
        "guide/first.md",
        "guide/second.md",
        "reference.md",
    ]


def test_accepts_direct_mkdocs_file(mkdocs_project_path: Path) -> None:
    mkdocs_file = mkdocs_project_path / "mkdocs.yml"

    project = load_mkdocs_project(mkdocs_file)

    assert project.mkdocs_yml == mkdocs_file


def test_validate_structure_surfaces_missing_and_unlisted(mkdocs_project_unlisted_path: Path) -> None:
    project = load_mkdocs_project(mkdocs_project_unlisted_path)

    result = project.validate_structure()

    assert any("missing" in warning.lower() for warning in result.warnings)
    assert any("not listed" in warning for warning in result.warnings)
