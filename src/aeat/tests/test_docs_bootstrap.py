"""Presence gate for the repository-bootstrap documentation surface.

Guards against silent loss of the user-facing narrative pages: the repository
README and the narrative guides the documentation index links. Each guide must
exist and be referenced from ``docs/index.rst`` so the published set never loses
a page without the build noticing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core, pytest.mark.docs]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCS = _REPO_ROOT / "docs"

_README = _REPO_ROOT / "README.md"
_GUIDES = ("getting-started", "architecture", "authoring-guide")


def test_readme_exists_and_is_substantive() -> None:
    """The repository README must exist and carry real content."""
    assert _README.is_file(), "README.md is missing from the repository root"
    body = _README.read_text(encoding="utf-8")
    assert len(body.splitlines()) >= 20, "README.md is too short to orient a reader"
    assert "aeat" in body


def test_narrative_guides_exist() -> None:
    """Each bootstrap narrative guide must exist under docs/."""
    missing = [name for name in _GUIDES if not (_DOCS / f"{name}.md").is_file()]
    assert not missing, f"missing narrative guides under docs/: {missing}"


def test_guides_are_wired_into_the_index() -> None:
    """Each narrative guide must be referenced from the documentation index."""
    index = (_DOCS / "index.md").read_text(encoding="utf-8")
    unreferenced = [name for name in _GUIDES if name not in index]
    assert not unreferenced, f"guides not referenced in docs/index.md toctree: {unreferenced}"

