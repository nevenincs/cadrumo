"""A strict full-scope build record stands in for a rebuild only while it is clean and its inputs are unchanged.

Every record here is written by a real strict Sphinx build run through the
production build entry point over a small fixture checkout, and read back by
the same reader the full-scope nitpicky gate uses.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..build import DocBuildPlan, build_docs
from ..build_paths import DOCS_BASE_URL_ENV, DOCS_BUILD_ROOT_ENV
from ..strict_build_record import (
    StrictBuildRecord,
    strict_build_input_paths,
    strict_build_record_problems,
    warning_log_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_CONF = 'project = "Fixture"\nextensions = []\n'
_CLEAN_PAGE = "Fixture\n=======\n\nA page with nothing to resolve.\n"
_BROKEN_PAGE = "Fixture\n=======\n\nSee :ref:`a-label-no-page-defines`.\n"
_FULL_BUILD = DocBuildPlan(targets=[], full_build_required=True)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fixture checkout carrying one file in each declared input tree, built into its own output root."""
    root = tmp_path / "checkout"
    _write(root / "docs" / "conf.py", _CONF)
    _write(root / "docs" / "index.rst", _CLEAN_PAGE)
    _write(root / "docs" / "api" / "index.md", "# API\n")
    _write(root / "src" / "fixture_package" / "__init__.py", "")
    _write(root / "dev" / "tool.py", "VALUE = 1\n")
    _write(root / "pyproject.toml", "[project]\nname = 'fixture'\n")
    _write(root / "uv.lock", "version = 1\n")
    monkeypatch.setenv(DOCS_BUILD_ROOT_ENV, str(tmp_path / "build"))
    monkeypatch.setenv("CADRUMO_STORAGE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("CADRUMO_DOCS_PAGEFIND_MODE", "none")
    for name in (
        "CADRUMO_DOCS_SCOPE",
        "CADRUMO_DOCS_LANGUAGE",
        "CADRUMO_DOCS_FLAVOR",
        "CADRUMO_DOCS_ONLY",
        "CADRUMO_DOCS_MASTER_DOC",
        "CADRUMO_DOCS_SINGLE_PAGE",
        "CADRUMO_DOCS_SELF_INVENTORY",
        DOCS_BASE_URL_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
    return root


def _read(record: Path) -> StrictBuildRecord:
    return StrictBuildRecord.model_validate(json.loads(record.read_text(encoding="utf-8")))


def test_a_clean_strict_build_records_a_record_the_gate_accepts(checkout: Path, tmp_path: Path) -> None:
    record = tmp_path / "records" / "strict.json"

    build_docs(checkout, _FULL_BUILD, strict=True, record=record)

    written = _read(record)
    assert written.clean
    assert written.returncode == 0
    assert written.warnings == 0
    assert written.configuration.builder == "html"
    assert written.configuration.nitpicky
    assert written.configuration.warnings_as_errors
    assert not written.configuration.self_inventory
    assert warning_log_path(record).is_file()
    assert strict_build_record_problems(record, repo_root=checkout) == ()


@pytest.mark.parametrize(
    "relative",
    ["docs/index.rst", "docs/api/index.md", "src/fixture_package/__init__.py", "dev/tool.py", "uv.lock"],
)
def test_an_input_changed_after_the_build_refuses_the_record(checkout: Path, tmp_path: Path, relative: str) -> None:
    record = tmp_path / "strict.json"
    build_docs(checkout, _FULL_BUILD, strict=True, record=record)

    path = checkout / relative
    _write(path, path.read_text(encoding="utf-8") + "\n.. edited\n")

    problems = strict_build_record_problems(record, repo_root=checkout)
    assert len(problems) == 1
    assert "inputs changed since the recorded build" in problems[0]


def test_an_input_added_after_the_build_refuses_the_record(checkout: Path, tmp_path: Path) -> None:
    record = tmp_path / "strict.json"
    build_docs(checkout, _FULL_BUILD, strict=True, record=record)

    _write(checkout / "docs" / "added.md", "# Added\n")

    assert any("inputs changed" in problem for problem in strict_build_record_problems(record, repo_root=checkout))


@pytest.mark.parametrize(
    "relative", ["docs/api/cadrumo.generated.rst", "docs/cli/index.rst", "docs/_build/html/index.html"]
)
def test_output_the_build_writes_into_its_source_tree_is_not_an_input(
    checkout: Path, tmp_path: Path, relative: str
) -> None:
    record = tmp_path / "strict.json"
    build_docs(checkout, _FULL_BUILD, strict=True, record=record)

    _write(checkout / relative, "generated\n")

    assert checkout / relative not in set(strict_build_input_paths(checkout))
    assert strict_build_record_problems(record, repo_root=checkout) == ()


def test_a_build_with_a_nitpicky_warning_records_an_unclean_record_the_gate_refuses(
    checkout: Path, tmp_path: Path
) -> None:
    _write(checkout / "docs" / "index.rst", _BROKEN_PAGE)
    record = tmp_path / "strict.json"

    with pytest.raises(SystemExit) as exited:
        build_docs(checkout, _FULL_BUILD, strict=True, record=record)

    assert exited.value.code != 0
    written = _read(record)
    assert not written.clean
    assert written.returncode != 0
    assert written.warnings >= 1
    assert "a-label-no-page-defines" in warning_log_path(record).read_text(encoding="utf-8")
    problems = strict_build_record_problems(record, repo_root=checkout)
    assert len(problems) == 1
    assert "was not clean" in problems[0]


def test_a_user_scope_build_does_not_prove_the_full_scope_contract(checkout: Path, tmp_path: Path) -> None:
    record = tmp_path / "strict.json"
    build_docs(checkout, _FULL_BUILD, strict=True, scope="user", record=record)

    assert _read(record).clean
    problems = strict_build_record_problems(record, repo_root=checkout)
    assert len(problems) == 1
    assert "full-scope nitpicky configuration" in problems[0]


def test_a_record_taken_under_another_interpreter_is_refused(checkout: Path, tmp_path: Path) -> None:
    record = tmp_path / "strict.json"
    build_docs(checkout, _FULL_BUILD, strict=True, record=record)
    document = json.loads(record.read_text(encoding="utf-8"))
    document["python"] = "0.0.0 (another interpreter)"
    record.write_text(json.dumps(document), encoding="utf-8")

    problems = strict_build_record_problems(record, repo_root=checkout)
    assert len(problems) == 1
    assert "not this interpreter" in problems[0]


@pytest.mark.parametrize("content", [None, "{not json", '{"schema": "cadrumo-docs-strict-build/1"}'])
def test_a_missing_or_unreadable_record_is_refused(checkout: Path, tmp_path: Path, content: str | None) -> None:
    record = tmp_path / "strict.json"
    if content is not None:
        record.write_text(content, encoding="utf-8")

    problems = strict_build_record_problems(record, repo_root=checkout)
    assert len(problems) == 1
    assert "missing or unreadable" in problems[0]


@pytest.mark.parametrize(
    ("strict", "plan"),
    [(False, _FULL_BUILD), (True, DocBuildPlan(targets=[Path("index.rst")], full_build_required=False))],
    ids=["not-strict", "not-whole"],
)
def test_only_a_strict_whole_build_writes_a_record(
    checkout: Path, tmp_path: Path, strict: bool, plan: DocBuildPlan
) -> None:
    record = tmp_path / "strict.json"
    with pytest.raises(SystemExit, match="--record applies to a strict whole-scope build"):
        build_docs(checkout, plan, strict=strict, record=record)
    assert not record.exists()
