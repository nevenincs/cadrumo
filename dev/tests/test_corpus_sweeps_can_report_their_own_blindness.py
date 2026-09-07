"""A gate that sweeps a corpus must be able to tell you it swept nothing.

The shape this refuses is `assert offenders == []` over a filesystem walk with
no way to distinguish "found nothing wrong" from "read nothing at all". A wrong
root, a moved package, or a renamed directory turns such a gate green and
silent, and it stays that way until someone probes it by hand.

That is not hypothetical here. Eleven gates were measured blind in one sweep of
this repository, including a taxpayer-identifier privacy guard that had never
read a byte, five filing-grade duplication gates walking 0 of 5,907 files, and
a modelo parity census whose empty id set made every modelo look covered. Three
real defects had accumulated behind them unseen.

WHY A GATE RATHER THAN MORE FLOORS. Each of those gates re-implemented its own
corpus discovery, and the suite had grown SIX different hand-rolled defences
against this exact failure -- a count floor, a root-existence check,
`require_root=True`, a roster cross-check, a sibling census test, and a
pre-sweep file read. Six idioms means a defended gate cannot be told from a
blind one by reading it, only by executing a probe against each. This asserts
the property once instead.

THIS MODULE OBEYS ITS OWN RULE. Its census is floored, because a gate against
unfloored sweeps that itself swept nothing would be the joke it is written to
prevent. It is `unit`-marked deliberately: an `integration`-marked gate is
deselected by the default lane and prints NOTHING RAN, which is how a red gate
in this repository stayed invisible through a rename.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.directory_scan import scan_directory

from .._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Trees holding gates that walk a corpus.
_SEARCHED_TREES: Final = ("src", "dev")

#: Floor for the census. The tree carries thousands of test modules; this floors
#: well below that so a new layout does not fail the gate on arrival, while a
#: collapsed walk still cannot pass.
_MINIMUM_TEST_MODULES: Final = 500

#: An assertion that a derived collection is empty -- the shape that reads the
#: same whether the sweep found nothing wrong or scanned nothing.
_EMPTY_ASSERT: Final = re.compile(r"assert \w+ == \[\]")

#: A filesystem walk. Both spellings matter: `scan_directory` returns an empty
#: tuple for a missing root and `Path.rglob` yields nothing, neither raising.
_SWEEP: Final = re.compile(r"scan_directory\(|\.glob\(|\.rglob\(")

#: Every defence idiom found in this suite. A unit carrying any of them can
#: report a collapsed sweep -- by count, by refusal, or by a cross-check that
#: reads the whole roster as missing.
_DEFENCE: Final = re.compile(
    r"assert len\("
    r"|_MINIMUM"
    r"|assert \w+, "
    r"|is_dir\(\)"
    r"|exists\(\)"
    r"|require_root=True"
    r"|does not exist"
    r"|raise AssertionError"
    r"|missing_\w+ == \[\]"
    r"|no longer exist"
    r"|def test_the_scan_reaches"
    r"|reaches the real",
)


def _units(source: str) -> list[str]:
    """Split a module into the scopes a defence can plausibly cover.

    A file-wide read conflates unrelated tests: one module here asserts an
    empty list of intercepted HTTP arrivals in one test and sweeps the package
    in another, and reading the two together reports a gate that is correct.

    Only ``test_`` functions become separate units. Everything else -- module
    scope and the helpers -- is prepended to each of them, because a test calls
    its helpers: a sweep hidden in one still belongs to the test, and a floor on
    a module-level constant still defends it. Splitting helpers out instead
    would hide exactly the gate this looks for, whose sweep and whose assertion
    sit either side of a function boundary.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [source]
    tests = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_")
    ]
    if not tests:
        return [source]
    lines = source.splitlines(keepends=True)
    shared = "".join(
        line
        for index, line in enumerate(lines, 1)
        if not any(test.lineno <= index <= (test.end_lineno or test.lineno) for test in tests)
    )
    return [shared + (ast.get_source_segment(source, test) or "") for test in tests]


def _test_modules() -> tuple[Path, ...]:
    """Every test module in the searched trees, refusing an empty census.

    Floored for the reason this module exists: a gate against unfloored sweeps
    that itself swept nothing would report the same green as a compliant tree.
    """
    modules = tuple(
        sorted(
            path
            for tree in _SEARCHED_TREES
            for path in scan_directory(REPO_ROOT / tree, pattern="test_*.py", recursive=True, require_root=True)
        )
    )
    if not modules:
        message = f"the sweep census reached no test module under {_SEARCHED_TREES}"
        raise AssertionError(message)
    return modules


def undefended_sweeps(sources: dict[str, str]) -> list[str]:
    """Return each source that asserts emptiness over a sweep with no defence.

    Two scopes, because the suite defends this shape at two scopes. A floor
    inside the test is local. A floor in a SIBLING test is module-wide: it goes
    red when the walk collapses, so every assertion in the module is covered by
    it, and reporting the module anyway is the noise that teaches a reader to
    ignore a gate. So a module carrying any unit that both sweeps and floors is
    accepted whole -- which subsumes the hand-rolled sibling-census idiom
    without naming it.

    Takes already-read text rather than paths so the rule can be exercised
    against synthetic inputs, which is what lets the cases below prove this
    detects anything at all.
    """
    offenders: list[str] = []
    for name, text in sources.items():
        units = _units(text)
        if any(_SWEEP.search(unit) and _DEFENCE.search(unit) for unit in units):
            continue
        if any(_EMPTY_ASSERT.search(unit) and _SWEEP.search(unit) for unit in units):
            offenders.append(name)
    return sorted(offenders)


def test_the_census_reaches_the_test_tree() -> None:
    """The gate below asserts an empty list, which nothing proves on its own."""
    modules = _test_modules()

    assert len(modules) >= _MINIMUM_TEST_MODULES, (
        f"the census reached only {len(modules)} test module(s) under {_SEARCHED_TREES}; "
        "a narrowed walk reports an empty offender list exactly as a compliant tree does"
    )


def test_every_corpus_sweep_can_report_its_own_blindness() -> None:
    """No gate may assert emptiness over a walk it cannot prove it performed."""
    sources = {
        path.relative_to(REPO_ROOT).as_posix(): path.read_text(encoding="utf-8", errors="ignore")
        for path in _test_modules()
    }

    offenders = undefended_sweeps(sources)

    assert offenders == [], (
        "these gates assert a derived collection is empty over a filesystem walk, with no way to "
        "tell 'found nothing wrong' from 'read nothing at all'. Floor the discovery funnel: pass "
        "`require_root=True` and assert the result is non-empty, with a message naming what the "
        "sweep is for.\n  " + "\n  ".join(offenders)
    )


def test_the_rule_detects_an_undefended_sweep() -> None:
    """Teeth, in the shape eleven real gates took."""
    detected = undefended_sweeps(
        {
            "blind.py": (
                "root = Path(__file__).parents[3]\n"
                "offenders = [p for p in scan_directory(root, pattern='*.py')]\n"
                "assert offenders == []\n"
            ),
        },
    )

    assert detected == ["blind.py"], "the rule must report a sweep that cannot detect its own blindness"


@pytest.mark.parametrize(
    "defence",
    [
        "assert len(scanned) >= 10\n",
        "assert scanned, 'reached nothing'\n",
        "if not root.is_dir():\n    raise AssertionError('missing')\n",
        "scanned = scan_directory(root, pattern='*.py', require_root=True)\n",
        "assert missing_swept == []\n",
        "def test_the_scan_reaches_the_real_call_sites() -> None:\n    pass\n",
    ],
)
def test_each_defence_idiom_is_accepted(defence: str) -> None:
    """The six idioms this suite already uses must not be reported as offenders.

    Asserted one per case rather than as a set: a single combined fixture would
    pass while five of the six were unrecognised, and reporting a defended gate
    is how a gate of this kind becomes noise nobody reads.
    """
    source = (
        "root = Path(__file__).parents[3]\n"
        + defence
        + "offenders = [p for p in scan_directory(root, pattern='*.py')]\n"
        "assert offenders == []\n"
    )

    assert undefended_sweeps({"defended.py": source}) == []
