"""The verify and file gate runs on the caller's authority generation and the Spanish date.

Two separate ways the gate used to answer about a different thing than the run
it belongs to:

* Nothing carried the caller's pinned authority into the gate's input replay or
  its deadline-window period lookup, so each opened a fresh bundled operation.
  Two generations can declare different windows for the same filing, and a
  memoised lookup keyed only on modelo, year and period served one generation's
  answer to a caller pinned to another.
* The filing calendar is a Europe/Madrid civil boundary (Ley 39/2015 art. 31).
  The reference date passed on verify and file was the UTC date of the clock,
  which is the previous Spanish day for up to two hours every night.

These tests pin the wiring itself, at the seams a run actually uses.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

from ....core.time.clock import MADRID_TZ
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .. import filing_actions, verification_actions, workflow_gate
from ..workflow_gate import RevisionInputsProvider, run_revision_workflow_gate, workflow_period_for_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _keyword_names(call: ast.Call) -> set[str]:
    return {keyword.arg for keyword in call.keywords if keyword.arg is not None}


def _calls_named(module: ModuleType, name: str) -> list[ast.Call]:
    source = inspect.getsourcefile(module)
    assert source is not None, f"{module.__name__} has no source file to read"
    tree = ast.parse(Path(source).read_text(encoding="utf-8"))
    found: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        leaf = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if leaf == name:
            found.append(node)
    return found


def test_the_gate_requires_a_pinned_authority() -> None:
    """A run cannot reach the gate without declaring the generation it reads."""
    parameters = inspect.signature(run_revision_workflow_gate).parameters

    assert parameters["operation"].default is inspect.Parameter.empty
    assert inspect.signature(RevisionInputsProvider.__init__).parameters["operation"].default is (
        inspect.Parameter.empty
    )


def test_the_window_period_lookup_is_not_memoised_across_generations() -> None:
    """A cached window period keyed without a generation answers for the wrong one."""
    helper = workflow_gate._deadline_window_period_for_registry_period

    assert not hasattr(helper, "cache_info"), "the lookup must not memoise a generation-dependent answer"
    assert "operation" in inspect.signature(helper).parameters
    assert "operation" in inspect.signature(workflow_period_for_work_unit).parameters


@pytest.mark.parametrize(
    "module",
    [filing_actions, verification_actions],
    ids=["file", "verify"],
)
def test_both_gate_routes_pass_the_pin_and_the_spanish_civil_date(module: ModuleType) -> None:
    """Each route hands the gate its own generation and the Madrid date."""
    calls = _calls_named(module, "run_revision_workflow_gate")

    assert len(calls) == 1, f"{module.__name__} must drive the gate from one site"
    keywords = _keyword_names(calls[0])
    assert "operation" in keywords
    today = next(keyword.value for keyword in calls[0].keywords if keyword.arg == "today")
    rendered = ast.unparse(today)
    assert "MADRID_TZ" in rendered, f"{module.__name__} passes {rendered!r} rather than the Madrid civil date"


def test_the_madrid_date_differs_from_the_utc_date_at_the_boundary() -> None:
    """The distinction the routes rely on is real, not nominal.

    Europe/Madrid leads UTC by two hours in April, so a filing stamped at 22:30
    UTC on the last day of a window happened on the following Spanish day.
    """
    instant = datetime(filing_year_envelope().horizon, 4, 20, 22, 30, tzinfo=UTC)

    assert instant.date() != instant.astimezone(MADRID_TZ).date()
