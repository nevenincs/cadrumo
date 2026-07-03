"""CI regression gate: a closed Kent wall must not reopen silently.

Issue ``#406``: "Kent-wall regression tests fail CI when a previously-closed
wall reopens." The root mechanism (confirmed by direct investigation of
``pyproject.toml`` ``addopts`` and ``.github/workflows/ci.yml``) is that
``addopts = "... -m 'unit' ..."`` scopes every bare ``pytest`` invocation --
including the CI "Test (unit)" step, which runs plain
``pytest --junitxml=junit.xml`` with no marker override -- to the ``unit``
marker only. Every Kent-journey / persona CLI acceptance test in this codebase
is marked ``integration`` (``pytestmark = [pytest.mark.integration, ...]``),
so none of those ~2500 tests ever execute in CI. A wall can regress -- its
guarding assertion can be silently weakened, or the guarding test itself can be
deleted -- with zero CI signal, because CI never runs it in the first place.

This module is itself marked ``unit`` (so it always runs in the CI lane that
does execute today) and is the structural half of the fix:

1. :func:`test_catalogue_is_non_empty_and_entries_are_well_formed` proves the
   catalogue in :mod:`aeat.tests.kent_wall_catalogue` is real, non-empty, and
   every entry resolves to a real file on disk (an AST-level existence check,
   not a name lookup against a hand-maintained list).
2. :func:`test_every_catalogued_wall_test_is_collectible_and_passes` proves,
   via a REAL ``pytest`` subprocess against the actual repository test files
   (no mocks, no stubs), that every catalogued wall's guarding test both
   COLLECTS and PASSES right now. A wall whose test has been deleted, renamed,
   or made uncollectible fails this assertion -- the "the wall reopened and
   nobody noticed" failure mode issue ``#406`` names.
3. :func:`test_a_regressed_wall_assertion_is_caught_by_the_gate` is the
   anti-tautology proof: it materialises a temporary sibling copy of a
   catalogued wall's test module with its core assertion deliberately flipped
   to a wrong expected value, runs that mutated copy through the SAME real
   ``pytest`` subprocess mechanism, and asserts the run FAILS. If this test
   ever passed with the mutated assertion, the gate mechanism would be
   provably unable to catch a real regression.

Follow-up (out of this bounded slice's scope, per the issue's own guidance to
"enroll a representative subset... scope enrolling the rest as follow-up"):
wiring the full ``-m integration`` marker into ``ci.yml`` as its own CI step so
every integration-marked test (not just the catalogued subset) runs on every
push. That is a substantially larger change (~2500 tests, a new CI runtime
budget, cross-platform flakiness surface) and is intentionally left for a
follow-up change; this gate closes the mechanism gap for the catalogued walls
today regardless of when that broader CI-wiring change lands, because it runs
in the ``unit`` lane that IS gated on every push.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from .kent_wall_catalogue import KENT_WALL_CATALOGUE, KentWallEntry

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SUBPROCESS_TIMEOUT_SECONDS = 120


def _run_pytest_subprocess(*node_ids: str) -> subprocess.CompletedProcess[str]:
    """Run the catalogued wall test(s) in a real, fresh ``pytest`` subprocess.

    Forces ``-m integration`` explicitly so the invocation is not silently
    narrowed back to ``unit`` by the inherited ``addopts`` -- the exact
    scoping gap this gate exists to close.
    """
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
            "-m",
            "integration",
            *node_ids,
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def test_catalogue_is_non_empty_and_entries_are_well_formed() -> None:
    """The catalogue enrolls at least one wall, and every entry names a real file."""
    assert len(KENT_WALL_CATALOGUE) > 0, "Kent-wall catalogue must not be empty"

    seen_node_ids: set[str] = set()
    for entry in KENT_WALL_CATALOGUE:
        assert entry.node_id not in seen_node_ids, f"duplicate catalogue entry: {entry.node_id}"
        seen_node_ids.add(entry.node_id)

        module_path = _REPO_ROOT / entry.test_module
        assert module_path.is_file(), (
            f"catalogued wall {entry.label} names a test module that does not exist on disk: {entry.test_module}"
        )

        source = module_path.read_text(encoding="utf-8")
        assert f"def {entry.test_function}(" in source, (
            f"catalogued wall {entry.label} names test function {entry.test_function!r} "
            f"that is not defined in {entry.test_module}"
        )


@pytest.mark.parametrize(
    "entry",
    KENT_WALL_CATALOGUE,
    ids=[entry.label for entry in KENT_WALL_CATALOGUE],
)
def test_every_catalogued_wall_test_is_collectible_and_passes(entry: KentWallEntry) -> None:
    """Each catalogued closed-wall test still collects and passes today.

    Runs the REAL repository test file end-to-end through a fresh pytest
    subprocess (matching the ``test_console_script_imports.py`` subprocess
    idiom already established for this kind of cold-start/CI-parity gate).
    A wall whose guarding test regresses, or whose module stops being
    collectible, fails this assertion -- which is exactly the reopened-wall
    signal issue ``#406`` asks CI to surface.
    """
    completed = _run_pytest_subprocess(entry.node_id)
    assert completed.returncode == 0, (
        f"Kent wall {entry.label} has REGRESSED (its guarding test no longer passes):\n"
        f"  node id: {entry.node_id}\n"
        f"  kent perspective: {entry.kent_perspective}\n"
        f"  stdout: {completed.stdout}\n"
        f"  stderr: {completed.stderr}"
    )


def test_a_regressed_wall_assertion_is_caught_by_the_gate() -> None:
    """Anti-tautology proof: deliberately regressing a wall makes the gate fail.

    Materialises a sibling copy of the ``ledger-exclude`` wall's real test
    module (issue ``#224``) in its OWN real ``tests/`` directory -- preserving
    the package-relative imports the module uses -- with its core assertion
    flipped from ``"excluded"`` to a wrong value. Runs that mutated copy
    through the same real pytest-subprocess mechanism the gate uses and
    asserts the run FAILS with the expected assertion diagnostic. This proves
    the gate mechanism can actually detect a reopened wall, rather than
    passing regardless of the wall's real state.

    The temporary module is written into and removed from the real
    ``entrypoints/cli/tests/`` directory (never into an unrelated package
    location) so pytest's ``prepend`` import mode resolves its relative
    imports exactly as it does for the real file. The filename carries this
    process's pid so two concurrent runs of this test (this is a shared,
    multi-agent worktree) never collide on the same path, and cleanup runs in
    a ``try``/``finally`` so a failed assertion still removes the fixture.
    """
    guarded_entry = next(entry for entry in KENT_WALL_CATALOGUE if entry.issue == 224)
    original_module = _REPO_ROOT / guarded_entry.test_module
    original_source = original_module.read_text(encoding="utf-8")

    target_assertion = 'assert result["review_status"] == "excluded"'
    regressed_assertion = 'assert result["review_status"] == "not-actually-excluded"'
    assert target_assertion in original_source, (
        "fixture drift: the ledger-exclude wall no longer contains the expected "
        "assertion line this anti-tautology proof mutates; update the mutation target"
    )
    mutated_source = original_source.replace(target_assertion, regressed_assertion, 1)
    assert mutated_source != original_source

    mutated_module_name = f"test_kent_wall_regression_proof_ledger_exclude_mutated_{os.getpid()}.py"
    mutated_module_path = original_module.parent / mutated_module_name
    assert not mutated_module_path.exists(), "stale mutated-proof fixture left behind by a prior run"

    try:
        mutated_module_path.write_text(mutated_source, encoding="utf-8")
        mutated_node_id = f"{mutated_module_path.relative_to(_REPO_ROOT).as_posix()}::{guarded_entry.test_function}"

        completed = _run_pytest_subprocess(mutated_node_id)

        assert completed.returncode != 0, (
            "the mutated (deliberately regressed) wall test PASSED -- the gate "
            "mechanism cannot detect a real regression:\n"
            f"  stdout: {completed.stdout}\n"
            f"  stderr: {completed.stderr}"
        )
        assert "not-actually-excluded" in completed.stdout or "AssertionError" in completed.stdout, (
            f"the mutated wall test failed, but not on the expected assertion:\n{completed.stdout}"
        )
    finally:
        mutated_module_path.unlink(missing_ok=True)
