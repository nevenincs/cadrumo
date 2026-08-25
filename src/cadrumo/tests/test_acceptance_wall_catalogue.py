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
   nobody noticed" failure mode issue ``#406`` names. Every catalogued wall
   runs inside ONE shared subprocess boot (the module-scoped
   ``_batched_wall_results`` fixture, parsed from a real ``--junitxml``
   report), not one boot per wall, while each wall stays its own pytest test
   item with its own pass/fail attribution -- see that fixture for why the
   batch addresses modules plus ``-k`` rather than exact node ids, which is
   what keeps one reopened wall from failing every other wall with it.
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
from defusedxml import ElementTree

from .acceptance_wall_catalogue import ACCEPTANCE_WALL_CATALOGUE, AcceptanceWallEntry

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]
# 30 catalogued walls now run inside ONE subprocess boot (see
# _batched_wall_results below) rather than one boot each, so the ceiling
# covers the summed real runtime of every wall's own CLI-driven test, not
# just one node's worth of interpreter/collection overhead.
_SUBPROCESS_TIMEOUT_SECONDS = 800

#: Per-wall ceiling INSIDE the batched subprocess, overriding the repository's
#: inherited ``timeout = 300``. The batch runs ``-n0`` while the OUTER suite is an
#: ``-n auto`` run, so each wall executes on a fully saturated host: the slowest
#: catalogued wall costs ~36s idle, and load inflation of 5-9x is routinely
#: observed on this machine. The three bounds nest deliberately -- per-wall (600)
#: inside the whole-batch subprocess bound (800) inside the item's own
#: ``@pytest.mark.timeout`` (900) -- so a genuine hang is still caught at the
#: tightest layer that can attribute it, rather than by the outermost one.
_SUBPROCESS_PER_TEST_TIMEOUT_SECONDS = 600

#: Per-testcase pass/fail result keyed by (junit classname, test function name).
#: ``None`` means the testcase passed; a non-``None`` value is its failure/error message.
_JunitResults = dict[tuple[str, str], "str | None"]


def _run_pytest_subprocess(
    *args: str,
    junit_xml_path: Path | None = None,
    keyword_expression: str | None = None,
    storage_root: Path | None = None,
    rootdir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
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
    at that path so a caller running MULTIPLE walls in one boot can still
    attribute pass/fail per wall (see :func:`_parse_junit_results`) rather
    than reading only the aggregate return code.

    ``keyword_expression``, when supplied, is passed as ``-k`` to narrow a
    whole-module ``args`` set down to the catalogued wall functions. See
    :func:`_batched_wall_results` for why the batch addresses MODULES plus
    ``-k`` rather than exact ``module::function`` node ids.

    ``storage_root``, when supplied, sets ``CADRUMO_LOCAL_STORAGE_ROOT`` for
    the subprocess. Callers running a module that lives OUTSIDE the repository
    tree must supply it: pytest only loads conftests from the rootdir down to
    the test file's own directory, so an out-of-tree module never traverses
    ``conftest.py`` / ``src/cadrumo/conftest.py`` -- the two files that point
    that variable at a process-private temp root BEFORE any Cadrumo import
    resolves ``Settings``. Without it, the subprocess's collection-time imports
    resolve the real platform state root and a retired former-product database
    there trips ``FormerProductStateError`` at collection, so the run dies
    before the wall's own assertion is ever reached. In-tree callers pass
    ``None`` and let the conftest chain establish the root as usual.

    ``rootdir``, when supplied, pins pytest's ``--rootdir`` at that directory
    and clears the inherited ``testpaths`` (``--override-ini testpaths=``).
    A caller running an OUT-OF-TREE module (one written under the OS temp tree,
    not under the repository) MUST supply it, set to the module's own
    directory, and run the subprocess with that same directory as its ``cwd``.
    Otherwise pytest infers a rootdir spanning the ``cwd`` (the Y:-drive repo)
    and the temp-drive node, and the inherited ``testpaths = ["src/cadrumo"]``
    then drives a broad collection walk that ``lstat()``s sibling entries in
    the shared OS temp directory. In the multi-agent worktree a concurrent
    agent deleting its own transient temp directory (e.g. a ``cli-sequence-*``
    scratch dir) mid-walk surfaces here as a spurious collection
    ``FileNotFoundError`` that interrupts the whole session before the wall's
    own assertion is reached -- the residual ``-n auto`` flake of issue
    ``#66``/``#24``. Pinning the rootdir to the module's own directory and
    clearing ``testpaths`` confines collection to the explicit node, so no
    shared-temp walk happens. (Mirrors the identical guard in
    ``registry/tests/testloader_cache_isolation.py``.) In-tree callers pass
    ``None`` and keep the repository rootdir.
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
        "--override-ini",
        f"timeout={_SUBPROCESS_PER_TEST_TIMEOUT_SECONDS}",
    ]
    if rootdir is not None:
        argv.extend(["--rootdir", str(rootdir), "--override-ini", "testpaths="])
    if junit_xml_path is not None:
        argv.append(f"--junitxml={junit_xml_path}")
    if keyword_expression is not None:
        argv.extend(["-k", keyword_expression])
    argv.extend(args)
    env = None
    if storage_root is not None:
        env = {**os.environ, "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root)}
    return subprocess.run(
        argv,
        cwd=rootdir if rootdir is not None else _REPO_ROOT,
        env=env,
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
def _batched_wall_results(tmp_path_factory: pytest.TempPathFactory) -> _JunitResults:
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

    Addresses the batch by MODULE path plus a ``-k`` selection of the
    catalogued wall function names, NOT by exact ``module::function`` node
    ids, and passes only modules that exist on disk. This is load-bearing for
    per-wall attribution, not a stylistic choice. An unmatched command-line
    argument is a pytest USAGE error (exit 4): pytest resolves every argument
    before running anything, so ONE catalogued node id whose function has been
    deleted or renamed aborts the entire batch -- zero tests run, the junit
    report is empty, and all 29 walls then fail with the same misleading "not
    reported by the batched subprocess run ... collection may have failed
    entirely" message, hiding which wall actually reopened behind 28
    false failures. A module path always resolves (existence is asserted by
    :func:`test_catalogue_is_non_empty_and_entries_are_well_formed`, and a
    module deleted underneath the catalogue is filtered out here), so the run
    never dies on argument resolution; a wall whose function no longer exists
    simply produces no testcase in the report and fails on its OWN
    parametrized item, while every other wall still runs and reports normally.

    This is strictly more sensitive than the exact-node-id form, not less: a
    deleted, renamed, or uncollectible wall test is still absent from the
    report and still fails its own item. ``-k`` matches substrings, so a run
    may execute a few extra same-module tests whose names contain a catalogued
    name; those simply never match a catalogued ``(classname, name)`` key and
    are ignored.

    No retry: the total-wipeout signature this fixture used to retry against
    was never a contention race, it was this exit-4 argument-resolution abort
    firing deterministically on the two catalogued walls whose guarding tests
    had been deleted. With module-path arguments the wipeout is structurally
    impossible, so a bounded retry would only multiply the runtime of a
    genuinely failing run.
    """
    modules = tuple(
        dict.fromkeys(
            entry.test_module for entry in ACCEPTANCE_WALL_CATALOGUE if (_REPO_ROOT / entry.test_module).is_file()
        )
    )
    keyword_expression = " or ".join(dict.fromkeys(entry.test_function for entry in ACCEPTANCE_WALL_CATALOGUE))
    # The junit sink lives under pytest's per-worker basetemp, NOT a bare
    # tempfile.TemporaryDirectory in the shared OS temp root: under `-n auto`
    # this module-scoped fixture is evaluated once PER xdist worker, and a
    # TemporaryDirectory removed at block exit while a concurrent worker's
    # subprocess is still resolving paths under the shared temp root races into
    # a FileNotFoundError collection abort. tmp_path_factory is worker-namespaced
    # and session-lived, so no concurrent run deletes a sibling's directory.
    junit_dir = tmp_path_factory.mktemp("acceptance-wall-junit")
    junit_xml_path = junit_dir / "acceptance_wall_junit.xml"
    _run_pytest_subprocess(*modules, junit_xml_path=junit_xml_path, keyword_expression=keyword_expression)
    return _parse_junit_results(junit_xml_path)


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


# The global `timeout = 300` in pyproject.toml is documented as a deadlock
# ceiling "no legitimate unit test approaches". This one legitimately does: the
# FIRST parametrized item constructs the module-scoped batched-subprocess fixture
# and so pays for all 30 catalogued walls' real CLI-driven runtime in one item --
# measured at ~89s on an idle machine, which needs only a ~3.4x parallel-load
# inflation to cross 300s. When it does, pytest-timeout kills the xdist worker
# mid-fixture and only that first item is reported failed, which reads as "wall
# #220 reopened" when nothing regressed. The explicit bound keeps a genuine hang
# guard while leaving headroom for a saturated host.
@pytest.mark.timeout(900)
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
        f"acceptance wall {entry.label} has REOPENED: its guarding test was not reported by the "
        f"batched subprocess run, which ran this wall's whole module and every other catalogued "
        f"wall normally. The guarding test has therefore been deleted, renamed, or made "
        f"uncollectible -- the exact failure mode issue #406 asks CI to surface.\n"
        f"  node id: {entry.node_id}\n"
        f"  capability now unguarded: {entry.capability}\n"
        f"Repair the wall by restoring coverage for that capability. Re-pointing this entry at a "
        f"test that does not exercise the capability, or deleting the entry, reopens the wall "
        f"silently -- which is what this gate exists to prevent."
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
    cannot observe a transient mutation-proof file. Living out of tree costs the
    run its conftest chain, so the subprocess is handed an explicit
    ``storage_root`` -- see :func:`_run_pytest_subprocess` for why omitting it
    kills the run at collection, long before the mutated assertion is reached.
    It is likewise handed an explicit ``rootdir`` pinned to ``tmp_path`` (and
    runs with that directory as its ``cwd``): without it, the cross-drive
    rootdir inference between the repo ``cwd`` and this temp-tree node drives an
    inherited-``testpaths`` collection walk over the shared OS temp directory,
    which flakes with a spurious ``FileNotFoundError`` when a concurrent agent
    deletes its own transient temp dir mid-walk (issue ``#66``) -- again see
    :func:`_run_pytest_subprocess`.
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

    # ``tmp_path`` is already per-worker unique and session-lived, so the module
    # basename needs no PID key to avoid a cross-worker collision.
    mutated_module_name = "test_acceptance_wall_regression_proof_ledger_exclude_mutated.py"
    mutated_module_path = tmp_path / mutated_module_name
    mutated_module_path.write_text(mutated_source, encoding="utf-8")
    mutated_node_id = f"{mutated_module_path.as_posix()}::{guarded_entry.test_function}"

    storage_root = tmp_path / "cadrumo-storage-root"
    storage_root.mkdir()
    completed = _run_pytest_subprocess(mutated_node_id, storage_root=storage_root, rootdir=tmp_path)

    assert completed.returncode != 0, (
        "the mutated (deliberately regressed) wall test PASSED -- the gate "
        "mechanism cannot detect a real regression:\n"
        f"  stdout: {completed.stdout}\n"
        f"  stderr: {completed.stderr}"
    )
    assert "not-actually-excluded" in completed.stdout or "AssertionError" in completed.stdout, (
        f"the mutated wall test failed, but not on the expected assertion:\n{completed.stdout}"
    )
