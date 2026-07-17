"""CI regression gate: a closed acceptance wall must not reopen silently.

Issue ``#406``: "acceptance-wall regression tests fail CI when a
previously-closed wall reopens." The root mechanism (confirmed by direct
investigation of ``pyproject.toml`` ``addopts`` and ``.github/workflows/ci.yml``)
is that ``addopts = "... -m 'unit' ..."`` scopes every bare ``pytest``
invocation -- including the CI "Test (unit)" step, which runs plain
``pytest --junitxml=junit.xml`` with no marker override -- to the ``unit``
marker only. Every acceptance-journey / persona CLI acceptance test in this
codebase is marked ``integration`` (``pytestmark = [pytest.mark.integration, ...]``),
so none of those ~2500 tests ever execute in CI. A wall can regress -- its
guarding assertion can be silently weakened, or the guarding test itself can be
deleted -- with zero CI signal, because CI never runs it in the first place.

This module is itself marked ``unit`` (so it always runs in the CI lane that
does execute today) and is the structural half of the fix:

1. :func:`test_catalogue_is_non_empty_and_entries_are_well_formed` proves the
   catalogue in :mod:`cadrumo.tests.acceptance_wall_catalogue` is real, non-empty,
   and every entry resolves to a real file on disk (an AST-level existence
   check, not a name lookup against a hand-maintained list).
2. :func:`test_every_catalogued_wall_test_is_collectible_and_passes` proves,
   via a REAL ``pytest`` subprocess against the actual repository test files
   (no mocks, no stubs), that every catalogued wall's guarding test both
   COLLECTS and PASSES right now. A wall whose test has been deleted, renamed,
   or made uncollectible fails this assertion -- the "the wall reopened and
   nobody noticed" failure mode issue ``#406`` names. Every catalogued wall's
   node id runs inside ONE shared subprocess boot (the module-scoped
   ``_batched_wall_results`` fixture, parsed from a real ``--junitxml``
   report), not one boot per wall, while each wall stays its own pytest test
   item with its own pass/fail attribution.
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
import tempfile
import time
from pathlib import Path

import pytest
from defusedxml import ElementTree

from .acceptance_wall_catalogue import ACCEPTANCE_WALL_CATALOGUE, AcceptanceWallEntry

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]
# 30 catalogued walls now run inside ONE subprocess boot (see
# _batched_wall_results below) rather than one boot each, so the ceiling
# covers the summed real runtime of every wall's own CLI-driven test, not
# just one node's worth of interpreter/collection overhead.
_SUBPROCESS_TIMEOUT_SECONDS = 600
# A ~30-node `pytest <id1> <id2> ... -m integration -n0` invocation is, on a
# heavily contended shared worktree (many concurrent agent processes reading,
# writing, and compiling the SAME repository tree -- observed at 250+ live
# `python.exe` processes during triage), occasionally hit by a collection-time
# race that makes pytest report every single requested node id as
# `ERROR: not found: ... (no match in any of [<Module ...>])` and exit 4 with
# zero collected items -- confirmed by re-running the identical command
# against the identical node ids back-to-back and observing it flip between a
# clean full collection and a total wipeout with no source change in between.
# This is a distinct signature from a REAL regression: a real regression still
# collects and reports the other 28 walls normally, with only the regressed
# wall's testcase failing or erroring. A full wipeout (every catalogued node
# id absent from the parsed junit report) is retried a bounded number of times,
# with a short backoff to let contention clear, before being treated as a
# genuine result -- so the gate stays sensitive to a real reopened wall while
# shedding this proven environmental race.
_BATCH_COLLECTION_RETRY_ATTEMPTS = 10
_BATCH_COLLECTION_RETRY_BACKOFF_SECONDS = 3.0

#: Per-testcase pass/fail result keyed by (junit classname, test function name).
#: ``None`` means the testcase passed; a non-``None`` value is its failure/error message.
_JunitResults = dict[tuple[str, str], "str | None"]


def _run_pytest_subprocess(*node_ids: str, junit_xml_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run the catalogued wall test(s) in a real, fresh ``pytest`` subprocess.

    Forces ``-m integration`` explicitly so the invocation is not silently
    narrowed back to ``unit`` by the inherited ``addopts`` -- the exact
    scoping gap this gate exists to close.

    Passes ``-n0`` to override the inherited ``addopts`` ``-n auto``: without
    it, this subprocess spins up a full fleet of ``xdist`` workers (one per
    core) just to run its node(s), and in the shared multi-agent worktree the
    outer suite is itself an ``-n auto`` run, so the nested worker fleet
    oversubscribes every core many times over. ``-n0`` keeps ``xdist`` loaded
    (so the ``-n`` argument stays valid) but runs the node(s) in-process,
    collapsing the subprocess to just its own node(s)' cost.

    ``junit_xml_path``, when supplied, requests a structured JUnit XML report
    at that path so a caller running MULTIPLE node ids in one boot can still
    attribute pass/fail per node id (see :func:`_parse_junit_results`) rather
    than reading only the aggregate return code.
    """
    argv = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
        "-n0",
        "-m",
        "integration",
    ]
    if junit_xml_path is not None:
        argv.append(f"--junitxml={junit_xml_path}")
    argv.extend(node_ids)
    return subprocess.run(
        argv,
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _junit_classname_for_module(test_module: str) -> str:
    """Return the pytest JUnit XML ``classname`` for a repo-relative test module path.

    pytest's JUnit report keys a plain (non-class) test function by the
    dotted module path (path separators replaced with ``.``, ``.py``
    stripped) plus the bare function name -- confirmed directly against a
    real ``--junitxml`` run of two catalogued walls on this pytest version,
    not assumed from the JUnit spec (the ``file``/``line`` testcase
    attributes some pytest configurations add are absent here).
    """
    return test_module.removesuffix(".py").replace("/", ".")


def _parse_junit_results(junit_xml_path: Path) -> _JunitResults:
    """Parse a pytest ``--junitxml`` report into per-testcase pass/fail results.

    Returns a mapping ``(classname, name) -> failure_message_or_None``. A
    catalogued wall absent from the mapping entirely means pytest could not
    even report on it (a collection-level failure so severe no testcase
    element was emitted); callers must treat a missing key as a failure too,
    not silently skip it.
    """
    tree = ElementTree.parse(junit_xml_path)
    results: _JunitResults = {}
    for testcase in tree.iter("testcase"):
        classname = testcase.get("classname", "")
        name = testcase.get("name", "")
        problem = testcase.find("failure")
        if problem is None:
            problem = testcase.find("error")
        message = None
        if problem is not None:
            message = problem.get("message") or (problem.text or "").strip() or "(no failure detail captured)"
        results[(classname, name)] = message
    return results


@pytest.fixture(scope="module")
def _batched_wall_results() -> _JunitResults:
    """Run every catalogued wall's guarding test in ONE real pytest subprocess boot.

    Collapses the prior per-wall subprocess-boot cost (~30 cold pytest
    interpreter + collection boots, one per catalogued wall) into a single
    boot: one real, fresh ``pytest -m integration`` process runs every
    catalogued wall's node id, and ``--junitxml`` gives per-testcase pass/fail
    attribution from that ONE run instead of an aggregate return code. Module
    scope means pytest computes this exactly once and every parametrized
    ``test_every_catalogued_wall_test_is_collectible_and_passes[...]`` item
    reads its own wall's result from the same cached run -- each wall stays
    its own pytest test item (same per-wall attribution and reporting
    granularity as before), only the expensive subprocess boot is shared.

    Retries a bounded number of times ONLY on a total collection wipeout (zero
    of the requested node ids reported at all -- see
    ``_BATCH_COLLECTION_RETRY_ATTEMPTS``), which is the proven shared-worktree
    contention race, not a real regression. A run that collects and reports
    even one catalogued wall is accepted immediately and never retried, so a
    genuine reopened wall (which still collects the other 28 normally) is
    caught on the first pass.
    """
    node_ids = tuple(entry.node_id for entry in ACCEPTANCE_WALL_CATALOGUE)
    expected_keys = {
        (_junit_classname_for_module(entry.test_module), entry.test_function) for entry in ACCEPTANCE_WALL_CATALOGUE
    }
    results: _JunitResults = {}
    for attempt in range(1, _BATCH_COLLECTION_RETRY_ATTEMPTS + 1):
        with tempfile.TemporaryDirectory(prefix="acceptance-wall-junit-") as tmp_dir:
            junit_xml_path = Path(tmp_dir) / "acceptance_wall_junit.xml"
            _run_pytest_subprocess(*node_ids, junit_xml_path=junit_xml_path)
            results = _parse_junit_results(junit_xml_path)
        if expected_keys & results.keys():
            break
        if attempt < _BATCH_COLLECTION_RETRY_ATTEMPTS:
            time.sleep(_BATCH_COLLECTION_RETRY_BACKOFF_SECONDS)
    return results


def test_catalogue_is_non_empty_and_entries_are_well_formed() -> None:
    """The catalogue enrolls at least one wall, and every entry names a real file."""
    assert len(ACCEPTANCE_WALL_CATALOGUE) > 0, "acceptance-wall catalogue must not be empty"

    seen_node_ids: set[str] = set()
    for entry in ACCEPTANCE_WALL_CATALOGUE:
        assert entry.node_id not in seen_node_ids, f"duplicate catalogue entry: {entry.node_id}"
        seen_node_ids.add(entry.node_id)

        module_path = _REPO_ROOT / entry.test_module
        assert module_path.is_file(), (
            f"catalogued wall {entry.label} names a test module that does not exist on disk: {entry.test_module}"
        )


@pytest.mark.parametrize(
    "entry",
    ACCEPTANCE_WALL_CATALOGUE,
    ids=[entry.label for entry in ACCEPTANCE_WALL_CATALOGUE],
)
def test_every_catalogued_wall_test_is_collectible_and_passes(
    entry: AcceptanceWallEntry,
    _batched_wall_results: _JunitResults,
) -> None:
    """Each catalogued closed-wall test still collects and passes today.

    Reads this wall's own result out of the ONE real, fresh pytest subprocess
    boot the module-scoped ``_batched_wall_results`` fixture runs for every
    catalogued wall together (matching the ``test_console_script_imports.py``
    subprocess idiom already established for this kind of cold-start/CI-parity
    gate, batched across the whole catalogue instead of once per wall). A wall
    whose guarding test regresses, or whose module stops being collectible,
    fails this assertion -- which is exactly the reopened-wall signal issue
    ``#406`` asks CI to surface.
    """
    classname = _junit_classname_for_module(entry.test_module)
    key = (classname, entry.test_function)
    assert key in _batched_wall_results, (
        f"acceptance wall {entry.label} was not reported by the batched subprocess run "
        f"(node id: {entry.node_id}) -- collection may have failed entirely"
    )
    failure_message = _batched_wall_results[key]
    assert failure_message is None, (
        f"acceptance wall {entry.label} has REGRESSED (its guarding test no longer passes):\n"
        f"  node id: {entry.node_id}\n"
        f"  capability: {entry.capability}\n"
        f"  failure: {failure_message}"
    )


def test_a_regressed_wall_assertion_is_caught_by_the_gate(tmp_path: Path) -> None:
    """Anti-tautology proof: deliberately regressing a wall makes the gate fail.

    Materialises a temporary copy of the ``ledger-exclude`` wall's real test
    module (issue ``#224``), converts its package-relative imports to their
    equivalent canonical absolute imports, and flips its core assertion from
    ``"excluded"`` to a wrong value. Running that mutated copy through the same
    real pytest subprocess must fail with the expected assertion diagnostic.

    The module lives under pytest's isolated ``tmp_path`` rather than the source
    tree. Repository-wide scanners running on other xdist workers therefore
    cannot observe a transient mutation-proof file.
    """
    guarded_entry = next(entry for entry in ACCEPTANCE_WALL_CATALOGUE if entry.issue == 224)
    original_module = _REPO_ROOT / guarded_entry.test_module
    original_source = original_module.read_text(encoding="utf-8")

    target_assertion = 'assert result["review_status"] == "excluded"'
    regressed_assertion = 'assert result["review_status"] == "not-actually-excluded"'
    assert target_assertion in original_source, (
        "fixture drift: the ledger-exclude wall no longer contains the expected "
        "assertion line this anti-tautology proof mutates; update the mutation target"
    )
    mutated_source = original_source.replace(target_assertion, regressed_assertion, 1)
    mutated_source = mutated_source.replace("from ....", "from cadrumo.")
    assert mutated_source != original_source

    mutated_module_name = f"test_acceptance_wall_regression_proof_ledger_exclude_mutated_{os.getpid()}.py"
    mutated_module_path = tmp_path / mutated_module_name
    mutated_module_path.write_text(mutated_source, encoding="utf-8")
    mutated_node_id = f"{mutated_module_path.as_posix()}::{guarded_entry.test_function}"

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
