"""Full builds purge orphaned pages and never resolve operator storage.

Furo bakes theme variables and templates into every page at build time, so a
built page whose source was removed keeps rendering its build-era design and
leaks into the search index (the docs-brand audit found 2208 such orphans
rendering a retired theme). :func:`dev.docs.build.remove_orphan_pages` is the
full-build purge; :func:`dev.docs.build.ensure_isolated_storage_root` keeps
the build's application imports off the workstation's product state.

Run via::

    uv run --no-sync pytest dev/docs/tests/test_orphan_page_removal.py -q
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dev.docs.build import ensure_isolated_storage_root, remove_orphan_pages

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _write(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _build_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Materialise a docs source tree, built HTML tree, and src tree."""
    repo_root = tmp_path
    docs_root = tmp_path / "docs"
    html_root = docs_root / "_build" / "html"

    # Live pages: markdown, reStructuredText, and a dotted autodoc docname.
    _write(docs_root / "index.md")
    _write(html_root / "index.html")
    _write(docs_root / "api" / "cadrumo.core.rst")
    _write(html_root / "api" / "cadrumo.core.html")

    # Orphans: a removed narrative page and a removed dotted autodoc page.
    _write(html_root / "getting-started.html")
    _write(html_root / "api" / "aeat.core.html")

    # Builder-owned specials and asset directories survive untouched.
    _write(html_root / "genindex.html")
    _write(html_root / "search.html")
    _write(html_root / "404.html")
    _write(html_root / "_static" / "vendored.html")

    # Viewcode pages map to src/ modules; the module overview index stays.
    _write(repo_root / "src" / "cadrumo" / "core" / "_modelo.py")
    _write(html_root / "_modules" / "cadrumo" / "core" / "_modelo.html")
    _write(html_root / "_modules" / "cadrumo" / "core" / "_gone.html")
    _write(html_root / "_modules" / "index.html")

    return docs_root, html_root, repo_root


def test_orphans_removed_live_pages_and_specials_kept(tmp_path: Path) -> None:
    """Pages without a source are deleted; sourced, special, and asset pages stay."""
    docs_root, html_root, repo_root = _build_tree(tmp_path)

    removed = remove_orphan_pages(docs_root, html_root, repo_root)

    assert removed == 3
    assert not (html_root / "getting-started.html").exists()
    assert not (html_root / "api" / "aeat.core.html").exists()
    assert not (html_root / "_modules" / "cadrumo" / "core" / "_gone.html").exists()
    assert (html_root / "index.html").exists()
    assert (html_root / "api" / "cadrumo.core.html").exists()
    assert (html_root / "genindex.html").exists()
    assert (html_root / "search.html").exists()
    assert (html_root / "404.html").exists()
    assert (html_root / "_static" / "vendored.html").exists()
    assert (html_root / "_modules" / "cadrumo" / "core" / "_modelo.html").exists()
    assert (html_root / "_modules" / "index.html").exists()


def test_missing_html_root_is_a_noop(tmp_path: Path) -> None:
    """A first build with no prior output removes nothing and does not fail."""
    assert remove_orphan_pages(tmp_path / "docs", tmp_path / "docs" / "_build" / "html", tmp_path) == 0


def test_isolated_storage_root_set_and_created() -> None:
    """When unset, the storage root points at a created build-scoped scratch dir."""
    prior = os.environ.pop("CADRUMO_LOCAL_STORAGE_ROOT", None)
    try:
        ensure_isolated_storage_root()
        configured = Path(os.environ["CADRUMO_LOCAL_STORAGE_ROOT"])
        assert configured.name == "cadrumo-docs-build-storage"
        assert configured.is_dir()
    finally:
        if prior is None:
            os.environ.pop("CADRUMO_LOCAL_STORAGE_ROOT", None)
        else:
            os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = prior


def test_isolated_storage_root_respects_caller_pin(tmp_path: Path) -> None:
    """A deliberately pinned storage root is kept verbatim."""
    prior = os.environ.get("CADRUMO_LOCAL_STORAGE_ROOT")
    os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = str(tmp_path / "pinned")
    try:
        ensure_isolated_storage_root()
        assert os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] == str(tmp_path / "pinned")
        assert (tmp_path / "pinned").is_dir()
    finally:
        if prior is None:
            os.environ.pop("CADRUMO_LOCAL_STORAGE_ROOT", None)
        else:
            os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = prior
