"""An unanswered profile fact reaches the operator as a warning, end to end, and never refuses.

A declared taxpayer model with one gating fact unanswered still renders every
overview verb through the installed runtime: the obligations the fact decides
stay undetermined, and the warning names the fact with a door to the profile
editor. The control answers the same fact and the warning goes away, so the
omission is what produced it.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from ...native_commands.runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from .overview_calendar_support import CALENDAR_GATING_FACT_OVERRIDES
from .overview_native_support import invoke_native_overview

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]
_ACTIVE_NATIVE: ContextVar[NativeCliProfileFixture | None] = ContextVar("overview_unanswered_native", default=None)

#: The gating fact this module leaves unanswered, and the warning code it raises.
_OMITTED_FACT_PATH = "withholding.has_employees"
_OMITTED_WARNING_CODE = "has_employees"
_PROFILE_EDIT_ACTION_ID = "operator.profile.edit"


def _horizon() -> int:
    with bundled_indexed_authority().operation() as operation:
        return operation.supported_filing_years().horizon


_HORIZON = _horizon()
_INVOCATIONS = (
    pytest.param(
        [
            "app",
            "overview",
            "calendar",
            "--from",
            date(_HORIZON, 1, 1).isoformat(),
            "--to",
            date(_HORIZON, 3, 31).isoformat(),
        ],
        id="calendar",
    ),
    pytest.param(["app", "overview", "agenda", "--date", date(_HORIZON, 4, 15).isoformat()], id="agenda"),
    pytest.param(["app", "overview", "backlog"], id="backlog"),
)

#: The ids above, as the parameter every assertion selects its capture by.
_VERBS = tuple(str(parameters.id) for parameters in _INVOCATIONS)


def _invoke(args: Sequence[str]) -> Result:
    fixture = _ACTIVE_NATIVE.get()
    if fixture is None:
        raise AssertionError("unanswered-fact native fixture is not active")
    return invoke_native_overview(fixture, args)


@dataclass(frozen=True, slots=True)
class _Rendered:
    """One invocation, captured as the operator saw it."""

    text: Result
    json: Result


def _capture(root: Path, facts: Mapping[str, str]) -> dict[str, _Rendered]:
    """Run every verb once over one backend registered with ``facts``.

    The backend is closed before the captures are handed out, because the
    active-profile pointer transaction refuses to nest across storage roots.
    """
    captured: dict[str, _Rendered] = {}
    with native_cli_profile_scope(root) as fixture:
        fixture.register(label="Overview unanswered-fact profile", facts=facts)
        token = _ACTIVE_NATIVE.set(fixture)
        try:
            for parameters in _INVOCATIONS:
                args = parameters.values[0]
                assert isinstance(args, list)
                captured[str(parameters.id)] = _Rendered(
                    text=_invoke(args),
                    json=_invoke(["--format", "json", *args]),
                )
        finally:
            _ACTIVE_NATIVE.reset(token)
    return captured


@pytest.fixture(scope="module")
def unanswered(tmp_path_factory: pytest.TempPathFactory) -> dict[str, _Rendered]:
    return _capture(
        tmp_path_factory.mktemp("unanswered"),
        {key: value for key, value in CALENDAR_GATING_FACT_OVERRIDES.items() if key != _OMITTED_FACT_PATH},
    )


@pytest.fixture(scope="module")
def answered(tmp_path_factory: pytest.TempPathFactory) -> dict[str, _Rendered]:
    return _capture(tmp_path_factory.mktemp("answered"), CALENDAR_GATING_FACT_OVERRIDES)


def _warnings(result: Result) -> list[dict[str, object]]:
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    # A rendered projection reports ok or warning; only a refusal is an error.
    assert envelope["status"] != "error", result.output
    warnings: object = envelope["result"]["warnings"]
    assert isinstance(warnings, list), result.output
    return [{str(key): value for key, value in warning.items()} for warning in warnings if isinstance(warning, dict)]


def _omitted_fact_warnings(result: Result) -> list[dict[str, object]]:
    return [warning for warning in _warnings(result) if warning["code"] == _OMITTED_WARNING_CODE]


@pytest.mark.parametrize("verb", _VERBS)
def test_the_verb_renders_and_warns_that_the_fact_is_unanswered(verb: str, unanswered: dict[str, _Rendered]) -> None:
    """The unanswered fact is a warning on a rendered projection, not a refusal."""
    assert len(_omitted_fact_warnings(unanswered[verb].json)) == 1, unanswered[verb].json.output


def test_the_calendar_warning_opens_the_profile_editor(unanswered: dict[str, _Rendered]) -> None:
    """The calendar is the projection whose warnings carry their profile door."""
    (warning,) = _omitted_fact_warnings(unanswered["calendar"].json)
    fix_action = warning["fix_action"]
    assert isinstance(fix_action, dict), warning
    assert fix_action["action"]["action"]["action_id"] == _PROFILE_EDIT_ACTION_ID, warning


@pytest.mark.parametrize("verb", _VERBS)
def test_the_text_rendering_is_not_invalid_operator_input(verb: str, unanswered: dict[str, _Rendered]) -> None:
    """An unanswered profile fact is workflow state, not a bad command line."""
    result = unanswered[verb].text

    assert result.exit_code == 0, result.output
    assert "Invalid value" not in result.output, result.output


@pytest.mark.parametrize("verb", _VERBS)
def test_answering_the_fact_removes_its_warning(verb: str, answered: dict[str, _Rendered]) -> None:
    """The warning is caused by the absent fact, not by the fixture generally."""
    assert _omitted_fact_warnings(answered[verb].json) == [], answered[verb].json.output
