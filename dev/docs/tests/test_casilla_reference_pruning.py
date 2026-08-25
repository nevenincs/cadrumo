"""The generated casilla tree drops pages the render no longer produces.

The output directory is gitignored build residue, so a page left behind by a
render that no longer owns it survives every later build. Sphinx then reads it,
finds it in no toctree, and reds the nitpicky gate -- and the deploy runs that
build before it uploads, so stale residue fails a publish rather than merely
untidying a directory. Five pages from a removed preview surface did exactly
that, and nothing in the tree emitted them any more.

The legal reference already swept its own output for the same reason. These
gates hold the casilla generator to the same contract, and to the narrowing
that sweep had to learn: prune only what this render did not write, so an
unchanged page keeps its mtime and the whole tree is not re-read every build.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core import iter_directory, scan_directory

from ..._paths import REPO_ROOT
from ..casilla_reference import generate_casilla_reference

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT


def _generated_casilla_dir(docs_root: Path) -> Path:
    """Return the directory the generator materialises its pages into."""
    from ..terminology._casilla_anchor import CASILLA_REFERENCE_DIR

    return docs_root / CASILLA_REFERENCE_DIR


def test_a_page_the_registry_no_longer_produces_is_pruned(tmp_path: Path) -> None:
    """The exact defect: residue no render owns is removed, not left to Sphinx.

    The planted page stands in for the preview pages a removed surface left
    behind. It is in no toctree, so surviving this render is what reds the
    strict build the deploy depends on.
    """
    generate_casilla_reference(tmp_path, repo_root=_REPO_ROOT)
    out_dir = _generated_casilla_dir(tmp_path)
    stale = out_dir / "_preview_es.rst"
    stale.write_text("Stale\n=====\n", encoding="utf-8", newline="\n")

    generate_casilla_reference(tmp_path, repo_root=_REPO_ROOT)

    assert not stale.exists(), "a page no render owns survived, and Sphinx would read it"
    assert any(iter_directory(out_dir, pattern="*.rst")), "the prune removed the pages it was meant to keep"


def test_the_index_and_every_rendered_modelo_page_survive_the_prune(tmp_path: Path) -> None:
    """The prune must not reach the pages the render just wrote.

    Asserted against the render's own declared output rather than a hardcoded
    list, so a modelo entering or leaving the registry cannot make this pass
    vacuously.
    """
    result = generate_casilla_reference(tmp_path, repo_root=_REPO_ROOT)
    out_dir = _generated_casilla_dir(tmp_path)

    assert result.pages, "the registry rendered no casilla pages, so this proves nothing"
    assert (out_dir / "index.rst").is_file()
    for page in result.pages:
        assert (tmp_path / page.output_relpath).is_file(), f"the prune removed a rendered page: {page.output_relpath}"


def test_regenerating_an_unchanged_registry_leaves_every_page_untouched(tmp_path: Path) -> None:
    """A second render rewrites nothing, so Sphinx has no reason to re-read the tree.

    This is the narrowing the legal sweep had to learn: pruning everything
    first makes the write-if-changed comparison downstream vacuous, because it
    always finds a missing file and recreates the page with a fresh mtime.
    """
    generate_casilla_reference(tmp_path, repo_root=_REPO_ROOT)
    out_dir = _generated_casilla_dir(tmp_path)
    before = {path.name: path.stat().st_mtime_ns for path in scan_directory(out_dir, pattern="*.rst")}

    generate_casilla_reference(tmp_path, repo_root=_REPO_ROOT)
    after = {path.name: path.stat().st_mtime_ns for path in scan_directory(out_dir, pattern="*.rst")}

    assert before, "the registry rendered no pages, so this proves nothing"
    assert after == before


def test_a_non_rst_file_in_the_output_directory_is_left_alone(tmp_path: Path) -> None:
    """The sweep is scoped to generated RST, not to everything in the directory."""
    generate_casilla_reference(tmp_path, repo_root=_REPO_ROOT)
    out_dir = _generated_casilla_dir(tmp_path)
    bystander = out_dir / "notes.txt"
    bystander.write_text("not a generated page\n", encoding="utf-8", newline="\n")

    generate_casilla_reference(tmp_path, repo_root=_REPO_ROOT)

    assert bystander.is_file(), "the sweep removed a file it does not own"
