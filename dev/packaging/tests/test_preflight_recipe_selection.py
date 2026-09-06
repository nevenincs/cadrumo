"""Prove every pytest invocation over this directory leaves no test unowned.

``dev/packaging/tests`` is mixed-marker. An invocation that targets it without
an explicit ``-m`` inherits the default marker expression from
``pyproject.toml`` and silently deselects every integration contract while still
exiting zero -- the dangerous variant of a marker mismatch, because a FULLY
deselected run exits with the no-tests-collected status a caller notices whereas
a PARTIALLY deselected one exits zero under a green summary.

Two kinds of invocation reach this directory and BOTH are read here. The
justfile recipes are the local gates. The campaign driver
(``dev.packaging.campaign``) is the one that matters most on a release
candidate: it is the only caller that runs this directory off Linux, so its
passes carry every platform fork in the tree -- junctions against symlinks,
descriptor inheritance, launcher stubs, permission bits. Reading only the
justfile left the driver outside the guard that exists for it, and the driver
was inheriting the default expression while the recipe beside it stated one.
The driver's passes are therefore read from the argv the driver actually
builds, never from a parallel declaration that can drift from what runs.

Deselecting nothing is the wrong invariant, because a parallel pass must
exclude the ``serial`` cohort that needs an unshared process. The invariant
that IS honest is coverage: every test in this directory must be selected by
SOME invocation, and the campaign driver's own passes must cover it without
help from the justfile. An invocation may narrow its selection freely,
provided the remainder has a named owner.

``perf`` is the one marker-grounded exclusion. Its registered policy in
``pyproject.toml`` states it is held out of every per-push lane and enrolled
explicitly in the dispatch-only ``ci-full`` lane, so it is excluded by that
declared policy rather than by a per-test allowlist.

Selection is not the only way a test disappears. ``serial`` items are
DESELECTED at collection whenever xdist workers are active, behind a warning
in a footer nobody reads, so an invocation that selects one and runs with
workers reports green having never executed it. That is the same false green
one level down, and it is asserted here as a scheduler binding: an invocation
whose real selection intersects the ``serial`` cohort must carry ``-n0``.

The gate is behavioural, not textual. It boots REAL pytest ``--collect-only``
subprocesses with each invocation's own arguments and compares actual node-id
sets, because a marker expression can be present and still be narrower than the
directory it targets -- a difference no textual check can see.

Three construction details carry the gate's own honesty:

* The module is marked ``unit`` DELIBERATELY. A guard against marker
  under-selection must sit inside the selection that a regressed invocation
  still runs; marked ``integration`` it would be deselected by exactly the
  defect it exists to catch and could never fire.
* Every corpus is asserted non-empty, the recipe and pass sets are anchored to
  concrete names, and every output reader carries positive and negative
  controls over real captured pytest output and real captured argv. Each
  collection is read twice, by independent parsers, and the two readings must
  agree; a reader that silently stopped matching would otherwise report an
  empty set as full coverage.
* ``--basetemp`` is stripped before collecting, because pytest REMOVES the
  directory that option names and this gate must never delete a campaign's
  retained failure artifacts to ask a question about it.

No mocks: each case is a genuine pytest collection of the real tree.

See Also:
    :mod:`cadrumo.tests.test_deselection_hook`
        Sibling gate proven by the same real-subprocess idiom.
"""

from __future__ import annotations

import functools
import re
import shlex
import subprocess
import sys
from collections.abc import Sequence
from typing import Final, NamedTuple

import pytest

from ..._paths import REPO_ROOT
from ..campaign import campaign_pytest_argv

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT: Final = REPO_ROOT
_JUSTFILE: Final = _REPO_ROOT / "justfile"
_TARGET_DIRECTORY: Final = "dev/packaging/tests"
#: Wall-clock bound for one nested collection. The heaviest here costs
#: about 8.2s unloaded, so 300s carried roughly a thirty-sevenfold margin.
#: Its sibling in ``dev/quality/tests/test_shard.py`` ran the same kind of
#: nested ``--collect-only`` on a HUNDREDfold margin and still expired inside
#: a twenty-three-minute concurrent suite, so this one had a third of the
#: headroom of a budget already shown to be too tight. The bound stays --
#: an unbounded wait on a child cannot be interrupted by the per-test
#: ceiling, and the worker dies taking every sibling's result with it -- but
#: it is sized for real contention rather than an idle machine.
_COLLECT_TIMEOUT_SECONDS: Final = 600

#: Recipes known to invoke pytest over this directory. Asserted as a subset of
#: what the parser finds, so a parser that stops matching fails loudly instead
#: of reporting an empty corpus as a clean pass.
_ANCHOR_RECIPES: Final = frozenset(
    {
        "packaging-smoke-preflight-tests",
        "packaging-smoke-installed-oracles",
    },
)

#: Campaign driver passes known to invoke pytest over this directory, anchored
#: for the same reason as the recipes above.
_ANCHOR_CAMPAIGN_PASSES: Final = frozenset(
    {
        "campaign:preflight-tests",
        "campaign:preflight-serial",
        "campaign:installed-oracles",
    },
)

#: The worker widths the driver's argv is read at. ``None`` is the local
#: default, where the absence of any ``-n`` leaves the addopts ``-n auto`` in
#: place -- workers ARE active, which is precisely the case a check keyed on a
#: literal ``-n auto`` token would miss. The integer is the CI-leg shape.
_TEST_WORKER_WIDTHS: Final = (None, 8)

#: The argv prefix the driver builds every pytest pass on.
_INVOCATION_PREFIX: Final = (sys.executable, "-m", "pytest")

#: Scheduler argument that pins a run to the controller process.
_NO_WORKERS: Final = "-n0"

_RECIPE_HEADER: Final = re.compile(r"^(?P<name>[a-z][\w-]*)\s*:(?![=])")
_NODE_ID: Final = re.compile(r"^(?P<node_id>\S+\.py::\S.*)$")
_COLLECTED: Final = re.compile(r"(?:^|\s)(?P<count>\d+)(?:/\d+)? tests? collected")
_NO_TESTS_COLLECTED: Final = re.compile(r"(?:^|\s)no tests collected")


class Recipe(NamedTuple):
    """A justfile recipe's pytest invocation.

    Attributes:
        name: The recipe name as written in the justfile.
        arguments: The pytest arguments, excluding the ``pytest`` token itself.
    """

    name: str
    arguments: tuple[str, ...]


def parse_node_ids(output: str) -> frozenset[str]:
    r"""Read the collected node ids out of a quiet collect-only run.

    Node ids are taken verbatim. Normalising path separators looks harmless and
    is not: pytest emits the path segment with forward slashes on every
    platform, while a PARAMETER id may legitimately contain a backslash, so
    rewriting separators collapsed the distinct cases ``[a\\b]`` and ``[a//b]``
    of one real parametrized test into a single entry.

    Args:
        output: Captured stdout of a ``pytest --collect-only -q`` run.

    Returns:
        Every node id the run listed.
    """
    node_ids = set()
    for line in output.splitlines():
        match = _NODE_ID.match(line.rstrip())
        if match is not None:
            node_ids.add(match.group("node_id"))
    return frozenset(node_ids)


def parse_collected_count(output: str) -> int:
    """Read the collected count out of a quiet collect-only summary line.

    Args:
        output: Captured stdout of a ``pytest --collect-only -q`` run.

    Returns:
        The count pytest reported.

    Raises:
        AssertionError: If no summary line is present, which means the
            subprocess never reached a collection report.
    """
    collected: int | None = None
    for line in output.splitlines():
        if _NO_TESTS_COLLECTED.search(line):
            collected = 0
            continue
        match = _COLLECTED.search(line)
        if match is not None:
            collected = int(match.group("count"))

    assert collected is not None, f"no pytest collection summary in output:\n{output}"
    return collected


def packaging_pytest_recipes() -> tuple[Recipe, ...]:
    """Discover every justfile recipe invoking pytest over this directory.

    Returns:
        One entry per matching recipe body line, in justfile order.
    """
    recipes: list[Recipe] = []
    current = ""
    for raw_line in _JUSTFILE.read_text(encoding="utf-8").splitlines():
        header = _RECIPE_HEADER.match(raw_line)
        if header is not None:
            current = header.group("name")
            continue
        if not raw_line[:1].isspace() or _TARGET_DIRECTORY not in raw_line:
            continue
        tokens = shlex.split(raw_line.strip().lstrip("@"))
        if "pytest" not in tokens:
            continue
        arguments = tuple(tokens[tokens.index("pytest") + 1 :])
        recipes.append(Recipe(name=current, arguments=arguments))
    return tuple(recipes)


def parse_pass_arguments(argv: Sequence[str]) -> tuple[str, ...]:
    """Read the collectable pytest arguments out of one real driver argv.

    Two tokens are removed and nothing else. The interpreter prefix is dropped
    because this gate supplies its own, and ``--basetemp`` is dropped because
    pytest REMOVES the directory that option names: collecting with the
    campaign's own basetemp would delete the retained failure artifacts of the
    run the operator is trying to read. Every selection-bearing and
    scheduler-bearing token survives, which is what makes the ``-n0`` and
    coverage assertions below readings of the real invocation.

    Args:
        argv: The argv the driver builds for one pass.

    Returns:
        The arguments, in order, ready to hand to a collection.

    Raises:
        AssertionError: If the argv does not begin with the interpreter prefix,
            which means this reader is no longer looking at a pytest
            invocation and every downstream selection would be measured from
            the wrong offset.
    """
    prefix = tuple(argv[: len(_INVOCATION_PREFIX)])
    assert prefix == _INVOCATION_PREFIX, (
        f"campaign pass argv does not start with the pytest invocation prefix "
        f"{list(_INVOCATION_PREFIX)}; got {list(prefix)} from {list(argv)}"
    )
    return tuple(token for token in argv[len(_INVOCATION_PREFIX) :] if not token.startswith("--basetemp="))


def campaign_pytest_passes(test_workers: int | None) -> tuple[Recipe, ...]:
    """Read the campaign driver's pytest passes off the argv it really builds.

    The driver is asked for its invocations rather than parsed for them, so the
    selection this gate measures is the selection a release lane executes.
    A declaration the driver did not use is exactly the drift that let the
    preflight inherit the default marker expression while the recipe beside it
    stated one.

    Args:
        test_workers: The preflight worker width to build the argv at.

    Returns:
        One entry per declared pass, namespaced so a failure message says
        which surface owns it.
    """
    return tuple(
        Recipe(name=f"campaign:{label}", arguments=parse_pass_arguments(argv))
        for label, argv in campaign_pytest_argv(_REPO_ROOT, test_workers)
    )


def packaging_pytest_invocations(test_workers: int | None = None) -> tuple[Recipe, ...]:
    """Return every pytest invocation over this directory, from both surfaces.

    Args:
        test_workers: The preflight worker width to read the driver at.

    Returns:
        The justfile recipes followed by the campaign driver's passes.
    """
    return packaging_pytest_recipes() + campaign_pytest_passes(test_workers)


@functools.cache
def _collect(label: str, arguments: tuple[str, ...]) -> frozenset[str]:
    """Boot a real pytest collection and return the node ids it selected.

    Memoized per ``(label, arguments)``. A collection is a pure function of the
    committed tree, which no test here mutates, so the per-recipe cases and the
    union case below were booting the identical subprocess twice for every
    recipe and asserting the identical thing about it. Re-running a
    deterministic check is not a second check; caching it drops the duplicate
    collections without weakening either assertion.

    The output is read twice by independent parsers -- the node-id lines and
    the summary count -- and the two readings must agree, so a reader that
    stopped matching cannot report an empty selection as a successful one.

    ``-n0`` is appended after the recipe's own arguments: marker deselection is
    a selection-time decision, so the worker count cannot change WHICH tests are
    collected, and booting a worker pool to collect nothing is pure overhead.

    Args:
        label: Human name for the invocation, used in failure messages.
        arguments: The pytest arguments to reproduce.

    Returns:
        The node ids the collection selected.
    """
    try:
        completed = subprocess.run(  # noqa: S603 - fixed interpreter argv; arguments come from the tracked justfile.
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "--collect-only",
                *arguments,
                "-n0",
            ],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=_COLLECT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as expiry:
        # Chained on purpose: the expiry carries the argv and the elapsed budget,
        # and none of it is sensitive. Reading an expiry as a recipe-selection
        # defect is the wrong first move, so the message says what it means.
        message = (
            f"{label} did not finish collecting within {_COLLECT_TIMEOUT_SECONDS}s. The heaviest "
            "collection here costs about 8.2s unloaded, so an expiry means the machine was "
            "contended, not that the recipe selection changed"
        )
        raise AssertionError(message) from expiry

    assert completed.returncode == 0, (
        f"{label} failed to collect (exit {completed.returncode}):\n{completed.stdout}\n{completed.stderr}"
    )
    node_ids = parse_node_ids(completed.stdout)
    reported = parse_collected_count(completed.stdout)

    unread = [line for line in completed.stdout.splitlines() if line.strip() and _NODE_ID.match(line.rstrip()) is None]

    assert len(node_ids) == reported, (
        f"{label} listed {len(node_ids)} node ids but reported {reported} collected; "
        f"one reader is not measuring. Unread non-blank lines: {unread}"
    )
    return node_ids


def _directory_selection(marker_expression: str) -> frozenset[str]:
    """Collect this directory under one marker expression.

    Args:
        marker_expression: The ``-m`` value; empty selects everything.

    Returns:
        The node ids selected.
    """
    return _collect(
        f"selection -m {marker_expression!r}",
        ("-q", "-m", marker_expression, _TARGET_DIRECTORY),
    )


_REAL_COLLECT_OUTPUT: Final = (
    "dev/packaging/tests/test_evidence.py::test_row_kinds_are_closed\n"
    "dev/packaging/tests/test_cohort_manifest.py::test_artifact_record_rejects_nonportable_paths[a\\\\b]\n"
    "dev/packaging/tests/test_cohort_manifest.py::test_artifact_record_rejects_nonportable_paths[a//b]\n"
    "\n"
    "332/345 tests collected (13 deselected) in 1.11s\n"
)


def test_the_node_id_reader_extracts_real_collect_only_lines() -> None:
    """Positive control: node-id lines are read, the summary line is not one, and ids stay distinct.

    The input is verbatim captured ``--collect-only -q`` output, including the
    real parametrized pair whose ids differ only in path separator. Reading it
    as two entries rather than one is the property a separator-normalising
    reader silently lost. Without this control a pattern that stopped matching
    would report an empty selection, and an empty selection is
    indistinguishable from a clean one in every set-difference assertion below.
    """
    assert parse_node_ids(_REAL_COLLECT_OUTPUT) == frozenset(
        {
            "dev/packaging/tests/test_evidence.py::test_row_kinds_are_closed",
            "dev/packaging/tests/test_cohort_manifest.py::test_artifact_record_rejects_nonportable_paths[a\\\\b]",
            "dev/packaging/tests/test_cohort_manifest.py::test_artifact_record_rejects_nonportable_paths[a//b]",
        },
    )


@pytest.mark.parametrize(
    "line",
    [
        "332/345 tests collected (13 deselected) in 1.11s",
        "  dev/packaging/tests/test_evidence.py::test_indented_is_not_a_node_id",
        "dev/packaging/tests/test_evidence.py",
        "",
    ],
)
def test_the_node_id_reader_declines_lines_that_are_not_node_ids(line: str) -> None:
    """Negative control: a summary, an indented tree line, a bare path, and a blank line."""
    assert parse_node_ids(line) == frozenset()


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        ("332/345 tests collected (13 deselected) in 1.11s", 332),
        ("345 tests collected in 1.08s", 345),
        ("6 tests collected in 0.98s", 6),
        ("1 test collected in 0.50s", 1),
        ("no tests collected (345 deselected) in 1.05s", 0),
    ],
    ids=["partial", "full", "file-scoped", "single", "empty"],
)
def test_the_count_reader_reads_real_pytest_summary_lines(summary: str, expected: int) -> None:
    """Positive control: every summary shape pytest really emits parses to its own count."""
    assert parse_collected_count(summary) == expected


@pytest.mark.parametrize(
    "summary",
    ["collected 345 items", "13 deselected", ""],
    ids=["verbose-header", "bare-deselection", "no-output"],
)
def test_the_count_reader_refuses_output_carrying_no_collection_outcome(summary: str) -> None:
    """Negative control: unrecognised or absent output raises rather than reading as zero.

    A reader that returned 0 for these would turn a broken subprocess into a
    silently empty selection, which is the false green this gate exists to
    prevent.
    """
    with pytest.raises(AssertionError) as refusal:
        parse_collected_count(summary)

    # `AssertionError` is the widest possible claim here: it is what EVERY
    # failed assertion raises, including one from inside the reader for an
    # unrelated reason. Requiring the guard's own sentence proves the reader
    # refused deliberately, and the echoed output proves it refused THIS
    # input rather than carrying a verdict from another case.
    message = str(refusal.value)
    assert "no pytest collection summary in output" in message, message
    assert summary in message, message


def test_the_scanned_recipe_corpus_is_non_empty_and_carries_the_known_gates() -> None:
    """The parser must find the recipes this gate exists to bind.

    An empty scan satisfies every per-recipe assertion vacuously, so the corpus
    is anchored to concrete recipe names rather than to a bare count.
    """
    discovered = {recipe.name for recipe in packaging_pytest_recipes()}

    assert discovered >= _ANCHOR_RECIPES, f"expected {sorted(_ANCHOR_RECIPES)}, found {sorted(discovered)}"


def test_the_campaign_pass_corpus_is_non_empty_and_carries_the_known_passes() -> None:
    """The driver must expose the passes this gate exists to bind.

    An empty read satisfies every per-pass assertion vacuously, so the corpus
    is anchored to concrete pass labels rather than to a bare count. The
    driver previously ran ONE pytest pass over this directory and stated no
    selection for it; a regression back to that shape drops a label here.
    """
    discovered = {invocation.name for invocation in campaign_pytest_passes(None)}

    assert discovered >= _ANCHOR_CAMPAIGN_PASSES, (
        f"expected {sorted(_ANCHOR_CAMPAIGN_PASSES)}, found {sorted(discovered)}"
    )


def test_the_pass_argument_reader_keeps_selection_and_scheduler_tokens() -> None:
    """Positive control: a real driver argv reads back without its basetemp.

    The input is a verbatim argv the driver builds. Every token that decides
    WHICH tests run or HOW MANY processes run them must survive, because the
    coverage and ``-n0`` assertions are readings of this output; only the
    interpreter prefix and the destructive ``--basetemp`` may be dropped.
    """
    argv = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--timeout=900",
        "--basetemp=var/packaging-smoke/pytest-basetemp/preflight-serial",
        "-m",
        "serial and not perf",
        _TARGET_DIRECTORY,
        f"--ignore={_TARGET_DIRECTORY}/test_installed_oracles.py",
        _NO_WORKERS,
    ]

    assert parse_pass_arguments(argv) == (
        "-q",
        "--timeout=900",
        "-m",
        "serial and not perf",
        _TARGET_DIRECTORY,
        f"--ignore={_TARGET_DIRECTORY}/test_installed_oracles.py",
        _NO_WORKERS,
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["pytest", "-q", "-m", "unit", _TARGET_DIRECTORY],
        [sys.executable, "-m", "dev.packaging.dependency_surface"],
        [],
    ],
    ids=["bare-pytest", "not-a-pytest-step", "empty"],
)
def test_the_pass_argument_reader_refuses_an_argv_it_cannot_offset(argv: list[str]) -> None:
    """Negative control: an argv that is not a pytest invocation raises.

    A reader that returned a best-effort slice here would measure a selection
    from the wrong offset and report a partial or empty set as a full one,
    which is the false green this gate exists to prevent.
    """
    with pytest.raises(AssertionError) as refusal:
        parse_pass_arguments(argv)

    message = str(refusal.value)
    assert "does not start with the pytest invocation prefix" in message, message


#: Per-surface floors for the invocation census. Live: four justfile recipes
#: and three campaign driver passes. Stated per surface because the census
#: is the SUM of two independent readers -- a justfile parse and a campaign
#: driver walk -- and either can stop yielding while the other carries the
#: total past any combined floor.
_MINIMUM_PACKAGING_RECIPES = 3
_MINIMUM_CAMPAIGN_PASSES = 2


def test_the_invocation_census_reaches_both_surfaces() -> None:
    """The parametrized gates below vanish silently if this census empties.

    Two cases are generated from ``packaging_pytest_invocations()`` at
    COLLECTION time, and a filter and a loop read it again further down. An
    empty census does not fail any of them: it produces no parametrized case
    at all, so the gates stop existing rather than stop passing. The floor
    therefore lives here, outside the parametrize it protects.
    """
    recipes = packaging_pytest_recipes()
    passes = campaign_pytest_passes(None)

    assert len(recipes) >= _MINIMUM_PACKAGING_RECIPES, (
        f"only {len(recipes)} justfile pytest recipe(s) were read; the invocation gates "
        "would parametrise over a surface that stopped being discovered"
    )
    assert len(passes) >= _MINIMUM_CAMPAIGN_PASSES, (
        f"only {len(passes)} campaign driver pass(es) were read; the driver half of the "
        "census can empty while the justfile half carries the total"
    )


@pytest.mark.parametrize("invocation", packaging_pytest_invocations(), ids=lambda invocation: invocation.name)
def test_each_invocation_states_its_marker_selection_explicitly(invocation: Recipe) -> None:
    """No invocation over this mixed-marker directory may inherit the default expression."""
    assert "-m" in invocation.arguments, (
        f"'{invocation.name}' invokes pytest over {_TARGET_DIRECTORY} without an explicit -m; "
        f"it would inherit the default marker expression from pyproject: {' '.join(invocation.arguments)}"
    )


@pytest.mark.parametrize("invocation", packaging_pytest_invocations(), ids=lambda invocation: invocation.name)
def test_each_invocation_collects_a_non_empty_selection(invocation: Recipe) -> None:
    """An invocation whose expression selects nothing is a gate that measures nothing."""
    assert _collect(f"'{invocation.name}'", invocation.arguments)


def test_every_serial_test_here_is_run_by_some_single_process_invocation() -> None:
    """A ``serial`` test must be EXECUTED by something, not merely selected.

    Selection is not the only way a test disappears. ``serial`` items are
    deselected inside the collection hook whenever xdist workers are active,
    and the hold is announced as a warning in a footer nobody reads, so an
    invocation that selects one and does not pin ``-n0`` reports a green
    summary having never executed it. The count in that summary is correct
    for what ran, which is what makes this harder to see than a marker
    mismatch.

    Coverage is therefore measured over the ``-n0`` invocations ALONE. A
    broad multi-directory lane that selects a serial test and hands it to
    workers contributes nothing here, because what it contributes is a
    warning; only an invocation that can actually run the test counts as its
    owner.

    The ``perf`` cohort is NOT subtracted here, unlike in the selection
    assertions. That exclusion is a policy about which lanes ENROL the
    benchmark, and the whole benchmark cohort is serial: subtracting it would
    let its only single-process owner narrow away from it and leave seven
    tests that nothing anywhere runs.
    """
    serial_cohort = _directory_selection("serial")

    assert serial_cohort, "collected no serial tests; this gate would pass vacuously"

    single_process = [
        invocation for invocation in packaging_pytest_invocations() if _NO_WORKERS in invocation.arguments
    ]
    assert single_process, f"no invocation over {_TARGET_DIRECTORY} pins {_NO_WORKERS}"

    executed: set[str] = set()
    for invocation in single_process:
        executed |= _collect(f"'{invocation.name}'", invocation.arguments)

    never_run = serial_cohort - executed

    assert not never_run, (
        f"{len(never_run)} serial-marked test(s) in {_TARGET_DIRECTORY} are run by no {_NO_WORKERS} invocation. "
        f"A lane that selects them alongside xdist workers does not count: the collection hook holds them out "
        f"behind a warning and the summary stays green: {sorted(never_run)[:10]}"
    )


@pytest.mark.parametrize("test_workers", _TEST_WORKER_WIDTHS, ids=["local-auto", "ci-width"])
def test_no_campaign_pass_schedules_a_serial_test_across_xdist_workers(test_workers: int | None) -> None:
    """The driver must bind each pass to a scheduler that can run its selection.

    Stricter than the coverage assertion above and scoped to the passes this
    driver owns: a campaign pass may not select a serial test at all unless it
    pins ``-n0``. Covering the test from a second pass would keep the run
    honest but leave the first pass paying collection cost to emit a warning,
    and a pass whose stated selection is not the set it runs is the drift this
    whole gate exists to refuse.

    Read at both worker widths on purpose. The absence of any ``-n`` token is
    NOT single-process: it leaves the addopts ``-n auto`` in force, so a check
    that looked for an explicit worker flag would call the local default safe.

    Args:
        test_workers: The width the driver's argv is built at.
    """
    serial_cohort = _directory_selection("serial")
    assert serial_cohort, "collected no serial tests; this gate would pass vacuously"

    for invocation in campaign_pytest_passes(test_workers):
        selected = _collect(f"'{invocation.name}'", invocation.arguments)
        held = selected & serial_cohort
        if not held:
            continue
        assert _NO_WORKERS in invocation.arguments, (
            f"'{invocation.name}' selects {len(held)} serial-marked test(s) but does not pin {_NO_WORKERS}, "
            f"so the collection hook holds them out of the run behind a warning and they never execute "
            f"while the summary stays green: {sorted(held)[:10]}"
        )


def test_the_campaign_driver_passes_alone_own_every_test_in_this_directory() -> None:
    """The release-candidate driver must cover this directory without the justfile.

    The load-bearing assertion for the campaign. This is the only caller that
    runs this directory off Linux, so a test its passes miss is a platform
    fork that no lane on that OS ever exercises. Asserted against the driver
    ALONE rather than against the union below, because a justfile recipe
    nobody runs on a release leg would otherwise hide the driver's own hole.
    """
    everything = _directory_selection("")
    held_out_by_policy = _directory_selection("perf")

    assert everything, "collected nothing for the whole directory"
    assert held_out_by_policy < everything, "the perf policy exclusion must be a proper subset"

    owned: set[str] = set()
    for invocation in campaign_pytest_passes(None):
        owned |= _collect(f"'{invocation.name}'", invocation.arguments)

    unowned = everything - held_out_by_policy - owned

    assert not unowned, (
        f"{len(unowned)} test(s) in {_TARGET_DIRECTORY} are selected by no campaign pass, so the packaging "
        f"campaign proves nothing about them on any OS it is the sole caller for: {sorted(unowned)[:10]}"
    )


def test_the_invocations_together_own_every_test_in_this_directory() -> None:
    """Every non-perf test here is selected by some recipe or campaign pass.

    An invocation may narrow its own selection, but the remainder must have a
    named owner, so no test can be dropped by a marker expression without
    another invocation picking it up.
    """
    everything = _directory_selection("")
    held_out_by_policy = _directory_selection("perf")

    assert everything, "collected nothing for the whole directory"

    owned: set[str] = set()
    for invocation in packaging_pytest_invocations():
        owned |= _collect(f"'{invocation.name}'", invocation.arguments)

    unowned = everything - held_out_by_policy - owned

    assert not unowned, (
        f"{len(unowned)} test(s) in {_TARGET_DIRECTORY} are selected by no justfile recipe and no campaign "
        f"pass, so they are silently dropped by every gate over this directory: {sorted(unowned)[:10]}"
    )
