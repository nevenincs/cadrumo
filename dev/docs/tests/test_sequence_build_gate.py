"""Build-mode guard for the ``cli-tree.json`` projection emit.

The ``cli-tree.json`` projection is a walk of the live ``aeat`` command tree — it
derives from the CLI surface, never from a docs page — so an incremental
docs-only changed-page build cannot change it and must not pay the projection's
subprocess cost. These tests pin :func:`should_emit_cli_tree`'s decision across
every build mode and prove :func:`emit_cli_tree` leaves an existing artifact
untouched on an incremental build (the skip path spawns no projection
subprocess, so a sentinel that a real rebuild would overwrite survives).

They mirror the sibling ``_should_generate_cli_reference`` guard's build-mode
shape (full/absent/forced regenerate, incremental skip) with two dedicated env
seams (``CADRUMO_DOCS_FORCE_CLI_TREE`` / ``CADRUMO_DOCS_SKIP_CLI_TREE``).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from sphinx.application import Sphinx

from cadrumo.tests.env_scope import scoped_env_var
from dev.docs.cli_tree import default_cli_tree_path
from dev.docs.sequence_build_gate import (
    check_sequence_goldens,
    emit_cli_tree,
    should_check_sequences,
    should_emit_cli_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _artifact(root: Path) -> Path:
    """Return the projection destination under a source tree root."""
    return default_cli_tree_path(root)


def test_full_build_regenerates(tmp_path: Path) -> None:
    """A full/update build (no specific sources) always regenerates."""
    assert should_emit_cli_tree(_artifact(tmp_path), specific_sources=None) is True


def test_incremental_with_existing_artifact_skips(tmp_path: Path) -> None:
    """An incremental changed-page build whose artifact exists is skipped."""
    output = _artifact(tmp_path)
    output.parent.mkdir(parents=True)
    output.write_text("{}", encoding="utf-8")
    assert should_emit_cli_tree(output, specific_sources=[tmp_path / "index.md"]) is False


def test_incremental_without_artifact_regenerates(tmp_path: Path) -> None:
    """An incremental build with no artifact yet must build it once."""
    output = _artifact(tmp_path)
    assert not output.is_file()
    assert should_emit_cli_tree(output, specific_sources=[tmp_path / "index.md"]) is True


def test_force_env_overrides_incremental_skip(tmp_path: Path) -> None:
    """``CADRUMO_DOCS_FORCE_CLI_TREE`` regenerates even on an incremental build."""
    output = _artifact(tmp_path)
    output.parent.mkdir(parents=True)
    output.write_text("{}", encoding="utf-8")
    with scoped_env_var("CADRUMO_DOCS_FORCE_CLI_TREE", "1"):
        assert should_emit_cli_tree(output, specific_sources=[tmp_path / "index.md"]) is True


def test_skip_env_overrides_full_build(tmp_path: Path) -> None:
    """``CADRUMO_DOCS_SKIP_CLI_TREE`` suppresses the projection unconditionally."""
    with scoped_env_var("CADRUMO_DOCS_SKIP_CLI_TREE", "1"):
        assert should_emit_cli_tree(_artifact(tmp_path), specific_sources=None) is False


def test_emit_skips_incremental_build_leaving_artifact_untouched(tmp_path: Path) -> None:
    """``emit_cli_tree`` on an incremental build leaves the existing artifact as-is.

    A real regeneration would overwrite the sentinel with the serialised tree;
    its survival proves the guard short-circuited before the projection
    subprocess ran (no 4.9s cost on a docs-only changed-page build).
    """
    output = _artifact(tmp_path)
    output.parent.mkdir(parents=True)
    sentinel = "SENTINEL-not-a-real-cli-tree"
    output.write_text(sentinel, encoding="utf-8")

    # emit_cli_tree reads only ``app.srcdir``; a stand-in carrier suffices to
    # exercise the guard's early return without materialising a full Sphinx app.
    app = cast(Sphinx, SimpleNamespace(srcdir=str(tmp_path)))
    emit_cli_tree(app, specific_sources=[tmp_path / "index.md"])

    assert output.read_text(encoding="utf-8") == sentinel


def test_sequence_check_runs_by_default() -> None:
    """With no opt-out set, every build runs the golden check."""
    assert should_check_sequences() is True


def test_sequence_check_skip_env_suppresses_the_check(tmp_path: Path) -> None:
    """``CADRUMO_DOCS_SKIP_SEQUENCE_CHECK`` short-circuits before any execution.

    The stand-in app's ``srcdir`` points at an EMPTY directory: an unskipped
    check would spawn the engine subprocess against it and, at minimum, pay
    seconds of interpreter/app import — while the skip path must return before
    reading ``srcdir`` at all. The guard decision is pinned here; the
    divergence-reds proof for the UNSKIPPED hook lives in
    ``test_sequence_goldens.TestBothSurfacesRedOnDivergence``.
    """
    with scoped_env_var("CADRUMO_DOCS_SKIP_SEQUENCE_CHECK", "1"):
        assert should_check_sequences() is False
        app = cast(Sphinx, SimpleNamespace(srcdir=str(tmp_path / "never-read"), config=SimpleNamespace()))
        check_sequence_goldens(app, pages=None)
