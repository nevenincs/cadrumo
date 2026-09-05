"""Prove the justfile pytest recipes over this directory leave no test unowned.

``dev/packaging/tests`` is mixed-marker. A recipe that invokes pytest against it
without an explicit ``-m`` inherits the default marker expression from
``pyproject.toml`` and silently deselects every integration contract while still
exiting zero -- the dangerous variant of a marker mismatch, because a FULLY
deselected run exits with the no-tests-collected status a caller notices whereas
a PARTIALLY deselected one exits zero under a green summary.

Deselecting nothing is the wrong invariant, because the preflight recipe
deliberately excludes the ``serial`` cohort that needs a built wheel cohort and
an unshared process. The invariant that IS honest is coverage: every test in
this directory must be selected by SOME justfile recipe. A recipe may then
narrow its own selection freely, provided the remainder has a named owner --
which is exactly what the audit asked for.

``perf`` is the one marker-grounded exclusion. Its registered policy in
``pyproject.toml`` states it is held out of every per-push lane and enrolled
explicitly in the dispatch-only ``ci-full`` lane, so it is excluded by that
declared policy rather than by a per-test allowlist.

The gate is behavioural, not textual. It boots REAL pytest ``--collect-only``
subprocesses with each recipe's own arguments and compares actual node-id sets,
because a marker expression can be present and still be narrower than the
directory it targets -- a difference no textual check can see.

Two construction details carry the gate's own honesty:

* The module is marked ``unit`` DELIBERATELY. A guard against marker
  under-selection must sit inside the selection that a regressed recipe still
  runs; marked ``integration`` it would be deselected by exactly the defect it
  exists to catch and could never fire.
* Every corpus is asserted non-empty, the recipe set is anchored to concrete
  recipe names, and both output readers carry positive and negative controls
  over real captured pytest output. Each collection is read twice, by
  independent parsers, and the two readings must agree; a reader that silently
  stopped matching would otherwise report an empty set as full coverage.

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
from typing import Final, NamedTuple

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT: Final = REPO_ROOT
_JUSTFILE: Final = _REPO_ROOT / "justfile"
_TARGET_DIRECTORY: Final = "dev/packaging/tests"
_COLLECT_TIMEOUT_SECONDS: Final = 300

#: Recipes known to invoke pytest over this directory. Asserted as a subset of
#: what the parser finds, so a parser that stops matching fails loudly instead
#: of reporting an empty corpus as a clean pass.
_ANCHOR_RECIPES: Final = frozenset(
    {
        "packaging-smoke-preflight-tests",
        "packaging-smoke-installed-oracles",
    },
)

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


@pytest.mark.parametrize("recipe", packaging_pytest_recipes(), ids=lambda recipe: recipe.name)
def test_each_recipe_states_its_marker_selection_explicitly(recipe: Recipe) -> None:
    """No recipe over this mixed-marker directory may inherit the default expression."""
    assert "-m" in recipe.arguments, (
        f"recipe '{recipe.name}' invokes pytest over {_TARGET_DIRECTORY} without an explicit -m; "
        f"it would inherit the default marker expression from pyproject: {' '.join(recipe.arguments)}"
    )


@pytest.mark.parametrize("recipe", packaging_pytest_recipes(), ids=lambda recipe: recipe.name)
def test_each_recipe_collects_a_non_empty_selection(recipe: Recipe) -> None:
    """A recipe whose expression selects nothing is a gate that measures nothing."""
    assert _collect(f"recipe '{recipe.name}'", recipe.arguments)


def test_the_justfile_recipes_together_own_every_test_in_this_directory() -> None:
    """Every non-perf test here is selected by some justfile recipe.

    This is the load-bearing assertion. A recipe may narrow its own selection,
    but the remainder must have a named owner, so no test can be dropped by a
    marker expression without another recipe picking it up.
    """
    everything = _directory_selection("")
    held_out_by_policy = _directory_selection("perf")

    assert everything, "collected nothing for the whole directory"
    assert held_out_by_policy < everything, "the perf policy exclusion must be a proper subset"

    owned: set[str] = set()
    for recipe in packaging_pytest_recipes():
        owned |= _collect(f"recipe '{recipe.name}'", recipe.arguments)

    unowned = everything - held_out_by_policy - owned

    assert not unowned, (
        f"{len(unowned)} test(s) in {_TARGET_DIRECTORY} are selected by no justfile recipe, so they are "
        f"silently dropped by every local gate over this directory: {sorted(unowned)[:10]}"
    )
