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

from ..cli_tree import default_cli_tree_path
from ..sequence_build_gate import (
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


def test_sequence_check_skip_env_suppresses_the_check_for_a_non_html_build(tmp_path: Path) -> None:
    """``CADRUMO_DOCS_SKIP_SEQUENCE_CHECK`` short-circuits a non-HTML build before any execution.

    The stand-in app's ``srcdir`` points at a directory that does not exist: a
    non-HTML builder renders no sequence output, so the skip path must return
    before reading ``srcdir`` at all. The divergence-reds proof for the
    UNSKIPPED hook, and the skipped HTML build that re-checks missing records,
    live in ``test_sequence_goldens``.
    """
    with scoped_env_var("CADRUMO_DOCS_SKIP_SEQUENCE_CHECK", "1"):
        assert should_check_sequences() is False
        app = cast(
            Sphinx,
            SimpleNamespace(
                srcdir=str(tmp_path / "never-read"),
                config=SimpleNamespace(),
                builder=SimpleNamespace(format=""),
            ),
        )
        check_sequence_goldens(app, pages=None)


def test_a_skipped_html_build_with_every_record_verified_runs_nothing(tmp_path: Path) -> None:
    """With every enrolled sequence's record verified, a skipped HTML build executes nothing.

    The seeded contract could not execute in any sandbox (its import file does
    not exist), so a hook that ran the check anyway would raise here; the
    golden and its matching record are written straight to disk.
    """
    from ..sequences.golden_store import write_golden
    from ..sequences.record_store import RecordFrame, SequenceRecord, golden_from_record, record_path, write_record
    from ..sequences.schema import FrameKind

    docs = tmp_path / "docs"
    page = docs / "how-to" / "seeded.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "# Seeded\n\nCreate a profile first with `aeat config profile create`.\n\n"
        "```{cli-sequence} seeded-demo\n:verify: Confirm the import.\n```\n",
        encoding="utf-8",
    )
    contract = docs / "_sequences" / "contracts" / "how-to" / "seeded" / "seeded-demo.seq"
    contract.parent.mkdir(parents=True)
    contract.write_text(
        "@result aeat app ledger import --file fixtures/missing.csv\n@expect result.imported == 3\n",
        encoding="utf-8",
    )
    record = SequenceRecord(
        sequence_id="seeded-demo",
        frames=(
            RecordFrame(
                kind=FrameKind.RESULT,
                argv=("aeat", "app", "ledger", "import", "--file", "fixtures/missing.csv"),
                exit_code=0,
                text="Imported 3 transactions.\n",
            ),
        ),
    )
    goldens, records = tmp_path / "goldens", tmp_path / "records"
    write_golden(golden_from_record(record), page="how-to/seeded", goldens_root=goldens)
    write_record(record, target=record_path("how-to/seeded", "seeded-demo", records_root=records))
    config = SimpleNamespace(cadrumo_sequences_goldens_root=str(goldens), cadrumo_sequences_records_root=str(records))

    with scoped_env_var("CADRUMO_DOCS_SKIP_SEQUENCE_CHECK", "1"):
        app = cast(Sphinx, SimpleNamespace(srcdir=str(docs), config=config, builder=SimpleNamespace(format="html")))
        check_sequence_goldens(app, pages=None)
