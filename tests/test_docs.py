"""Project-meta smoke tests for the public-facing documentation files.

These tests are repo-root meta tests, in the same family as
``tests/test_config.py`` and ``tests/test_release_config.py``: they
assert on repo-level invariants rather than on subpackage code, so
they live at ``tests/`` instead of being colocated under
``src/aeat/<subpackage>/``.

The justification for this placement is recorded in
``.vault/adr/2026-04-12-docs-rewrite-adr.md``.

The tests are smoke tests, not content tests — they ensure the
documentation files exist, are non-empty, and contain a small set of
load-bearing strings. They are NOT a substitute for hand-review of
the actual prose.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.config import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

PROJECT_NAME = "aeat"

ON_MAIN_SUBPACKAGES = (
    "aeat.auth",
    "aeat.browser",
    "aeat.cli",
    "aeat.deadlines",
    "aeat.filing",
    "aeat.i18n",
    "aeat.llm",
    "aeat.manuals",
    "aeat.models",
    "aeat.normatives",
    "aeat.portals",
    "aeat.schema",
    "aeat.sede",
    "aeat.storage",
    "aeat.submission",
    "aeat.sync",
    "aeat.testing",
)


def _read(path: Path) -> str:
    assert path.is_file(), f"missing documentation file: {path}"
    text = path.read_text(encoding="utf-8")
    assert text.strip(), f"documentation file is empty: {path}"
    return text


def test_readme_exists_and_names_the_project() -> None:
    text = _read(PROJECT_ROOT / "README.md")
    assert PROJECT_NAME in text


def test_getting_started_exists_and_is_non_empty() -> None:
    _read(PROJECT_ROOT / "docs" / "getting-started.md")


def test_releasing_exists_and_references_just_release() -> None:
    text = _read(PROJECT_ROOT / "RELEASING.md")
    assert "just release" in text


def test_architecture_references_at_least_five_subpackages() -> None:
    text = _read(PROJECT_ROOT / "docs" / "architecture.md")
    hits = {name for name in ON_MAIN_SUBPACKAGES if name in text}
    assert len(hits) >= 5, (
        f"docs/architecture.md must reference at least 5 on-main subpackages by name; found {sorted(hits)}"
    )
