"""Presence gate for the repository-bootstrap documentation surface.

Guards against silent loss of the user-facing narrative pages: the repository
README and the narrative guides the documentation index links. Each guide must
exist and be referenced from ``docs/index.rst`` so the published set never loses
a page without the build noticing.
"""

from __future__ import annotations

import pytest

from .inventory import repo_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DOCS = repo_path("docs")

_README = repo_path("README.md")
_GUIDES = ("architecture", "authoring-guide")


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
    assert _GUIDES, "the guide inventory is empty; every guide is trivially referenced when there are none"
    unreferenced = [name for name in _GUIDES if name not in index]
    assert not unreferenced, f"guides not referenced in docs/index.md toctree: {unreferenced}"
