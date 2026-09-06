"""The ``perf`` cohort's placement and ownership, measured against real pytest.

Both ownership gates in ``test_preflight_recipe_selection.py`` subtract the
``perf`` cohort before asserting that nothing is unowned, because the registered
policy in ``pyproject.toml`` holds ``perf`` out of every per-push lane. That
subtraction is correct for those gates and leaves the cohort itself measured by
nothing: a benchmark that lost its execution marker, lost ``serial``, or lost
the one recipe that actually runs it would disappear from every lane while both
ownership gates stayed green, because neither ever looks at it.

Four readings, each of the real tree:

* the perf cohort is exactly the set of tests in the modules that declare the
  marker, so the cohort cannot silently empty out and pass this file vacuously;
* every perf test carries an execution marker and ``serial`` -- the placement
  the benchmark module documents;
* no recipe over this directory admits a perf test into a lane running workers;
* some justfile recipe selects ALL of it and pins ``-n0``, because a ``serial``
  item collected under workers is deselected at collection behind a footer
  warning and never executes.

No mocks: every selection is a genuine ``--collect-only`` of the committed tree,
and every recipe expression is read out of the tracked justfile rather than
restated here.
"""

from __future__ import annotations

import ast
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
_UTF_8: Final = "utf-8"

#: Wall bound for one nested collection, sized like its sibling in
#: ``test_preflight_recipe_selection.py``: the heaviest costs about 8 s
#: unloaded, and an unbounded wait on a child cannot be interrupted by the
#: per-test ceiling.
_COLLECT_TIMEOUT_SECONDS: Final = 600

#: The marker whose cohort this file owns.
_PERF: Final = "perf"

#: The execution markers the marker-integrity contract requires exactly one of.
_EXECUTION_MARKERS: Final = ("unit", "integration", "aeat_live")

#: The scheduler argument that pins a run to the controller process.
_NO_WORKERS: Final = "-n0"

_RECIPE_HEADER: Final = re.compile(r"^(?P<name>[a-z][\w-]*)\s*:(?![=])")
_NODE_ID: Final = re.compile(r"^(?P<node_id>\S+\.py::\S.*)$")
_COLLECTED: Final = re.compile(r"(?:^|\s)(?P<count>\d+)(?:/\d+)? tests? collected")
_NO_TESTS_COLLECTED: Final = re.compile(r"(?:^|\s)no tests collected")

#: Collection exit statuses that are answers rather than faults. ``5`` is
#: pytest's "no tests collected", which is the CORRECT outcome for every
#: marker expression here that must select nothing; reading it as a failure
#: would turn the load-bearing negative cases into errors.
_COLLECTION_STATUSES: Final = frozenset({0, 5})


class Recipe(NamedTuple):
    """One pytest invocation over this directory, read off the justfile."""

    name: str
    arguments: tuple[str, ...]


def packaging_pytest_recipes() -> tuple[Recipe, ...]:
    """Discover every justfile recipe invoking pytest over this directory.

    Returns:
        One entry per matching recipe body line, in justfile order.
    """
    recipes: list[Recipe] = []
    current = ""
    for raw_line in _JUSTFILE.read_text(encoding=_UTF_8).splitlines():
        header = _RECIPE_HEADER.match(raw_line)
        if header is not None:
            current = header.group("name")
            continue
        if not raw_line[:1].isspace() or _TARGET_DIRECTORY not in raw_line:
            continue
        tokens = shlex.split(raw_line.strip().lstrip("@"))
        if "pytest" not in tokens:
            continue
        recipes.append(Recipe(name=current, arguments=tuple(tokens[tokens.index("pytest") + 1 :])))
    return tuple(recipes)


@functools.cache
def _collect(label: str, arguments: tuple[str, ...]) -> frozenset[str]:
    """Boot a real pytest collection and return the node ids it selected.

    Memoized per ``(label, arguments)``: a collection is a pure function of the
    committed tree, which nothing here mutates. The node-id lines and the
    summary count are read by independent parsers and must agree, so a reader
    that stopped matching cannot report an empty selection as a clean one.

    Args:
        label: Human name for the invocation, used in failure messages.
        arguments: The pytest arguments to reproduce.

    Returns:
        The node ids the collection selected.

    Raises:
        AssertionError: If the collection did not finish inside its bound.
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
                _NO_WORKERS,
            ],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            errors="replace",
            check=False,
            timeout=_COLLECT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as expiry:
        message = (
            f"{label} did not finish collecting within {_COLLECT_TIMEOUT_SECONDS}s; the machine was "
            "contended, which is not a placement defect"
        )
        raise AssertionError(message) from expiry

    assert completed.returncode in _COLLECTION_STATUSES, (
        f"{label} failed to collect (exit {completed.returncode}):\n{completed.stdout}\n{completed.stderr}"
    )
    node_ids: set[str] = set()
    reported: int | None = None
    for line in completed.stdout.splitlines():
        match = _NODE_ID.match(line.rstrip())
        if match is not None:
            node_ids.add(match.group("node_id"))
            continue
        if _NO_TESTS_COLLECTED.search(line):
            reported = 0
            continue
        summary = _COLLECTED.search(line)
        if summary is not None:
            reported = int(summary.group("count"))

    assert reported is not None, f"{label} printed no collection summary:\n{completed.stdout}"
    assert len(node_ids) == reported, (
        f"{label} listed {len(node_ids)} node ids but reported {reported} collected; one reader is not measuring"
    )
    return frozenset(node_ids)


def _selection(marker_expression: str) -> frozenset[str]:
    """Collect this directory under one marker expression.

    Args:
        marker_expression: The ``-m`` value; empty selects everything.

    Returns:
        The node ids selected.
    """
    return _collect(f"selection -m {marker_expression!r}", ("-q", "-m", marker_expression, _TARGET_DIRECTORY))


def _modules_declaring_the_marker() -> frozenset[str]:
    """Read which modules here declare the ``perf`` marker, from their source.

    An independent reading of the same fact the collection reports, so the
    cohort cannot shrink to nothing and leave every case below vacuously true.

    Returns:
        Repository-relative posix paths of the declaring modules.
    """
    declaring: set[str] = set()
    for path in sorted((_REPO_ROOT / _TARGET_DIRECTORY).glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding=_UTF_8))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute) or node.attr != _PERF:
                continue
            owner = node.value
            if isinstance(owner, ast.Attribute) and owner.attr == "mark":
                declaring.add(path.relative_to(_REPO_ROOT).as_posix())
    return frozenset(declaring)


def test_the_perf_cohort_is_exactly_the_modules_that_declare_the_marker() -> None:
    """Anchor: the cohort this file measures is the cohort the tree declares.

    Equality against a live scan rather than a count or a floor. A total floor
    cannot see a whole declaring module disappear; this can.
    """
    declared = _modules_declaring_the_marker()
    collected = frozenset(node_id.split("::", 1)[0] for node_id in _selection(_PERF))

    assert declared, f"no module in {_TARGET_DIRECTORY} declares pytest.mark.{_PERF}; every case here would be vacuous"
    assert collected == declared, (
        f"the collected {_PERF} cohort and the modules declaring the marker disagree; "
        f"collected-only {sorted(collected - declared)}, declared-only {sorted(declared - collected)}"
    )


def test_every_perf_test_carries_an_execution_marker_and_serial() -> None:
    """The documented placement: ``perf`` plus an execution marker plus ``serial``.

    ``perf`` is a classification, not an execution marker, so a perf test
    without one is selected by no lane's execution expression at all. Without
    ``serial`` it is collected by the parallel selectors it must stay out of,
    and its measurement is taken under co-resident worker load.
    """
    unexecutable = _selection(f"{_PERF} and not ({' or '.join(_EXECUTION_MARKERS)})")
    parallel = _selection(f"{_PERF} and not serial")

    assert not unexecutable, (
        f"{len(unexecutable)} {_PERF} test(s) carry no execution marker, so no lane's marker expression "
        f"can select them: {sorted(unexecutable)[:10]}"
    )
    assert not parallel, (
        f"{len(parallel)} {_PERF} test(s) do not carry 'serial', so a parallel selector collects them and "
        f"measures them under worker contention: {sorted(parallel)[:10]}"
    )


def test_no_recipe_over_this_directory_admits_perf_into_a_parallel_lane() -> None:
    """The registered policy, read off the recipes rather than restated.

    A recipe that both selects a ``perf`` test and runs workers is the failure
    the policy exists to prevent: the measurement is taken on a machine the
    lane itself is loading.
    """
    cohort = _selection(_PERF)
    assert cohort, f"collected no {_PERF} tests; this gate would pass vacuously"

    for recipe in packaging_pytest_recipes():
        admitted = _collect(f"'{recipe.name}'", recipe.arguments) & cohort
        if not admitted:
            continue
        assert _NO_WORKERS in recipe.arguments, (
            f"'{recipe.name}' selects {len(admitted)} {_PERF} test(s) without pinning {_NO_WORKERS}, so they "
            f"are measured under its own worker pool: {sorted(admitted)[:10]}"
        )


def test_some_recipe_owns_and_executes_the_whole_perf_cohort() -> None:
    """The ownership question both sibling gates subtract away.

    They exclude the ``perf`` cohort before asserting nothing is unowned, so
    this is the only place that asks whether the cohort has an owner at all. It
    must be selected in full by a single recipe that also pins ``-n0``, since a
    split owner leaves whichever half the other recipe dropped running nowhere.
    """
    cohort = _selection(_PERF)
    assert cohort, f"collected no {_PERF} tests; this gate would pass vacuously"

    owners = [
        recipe.name
        for recipe in packaging_pytest_recipes()
        if _NO_WORKERS in recipe.arguments and cohort <= _collect(f"'{recipe.name}'", recipe.arguments)
    ]

    assert owners, (
        f"no justfile recipe over {_TARGET_DIRECTORY} selects the whole {_PERF} cohort at {_NO_WORKERS}, so "
        f"{len(cohort)} benchmark test(s) execute in no lane: {sorted(cohort)[:10]}"
    )
