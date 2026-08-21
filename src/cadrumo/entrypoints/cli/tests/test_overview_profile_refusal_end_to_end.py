"""An unanswered profile fact drives a real overview refusal naming the field.

The sibling grounding module covers the enrichment function against real data
and covers the pass-through branch end to end, because the shared calendar
fixture answers every gating fact and its only warning is a non-profile code.

This module closes that gap from the other side: its profile genuinely leaves a
gating fact unanswered, so the refusal an operator actually sees is produced by
a missing PROFILE FIELD, and the assertion is that the field's operator label
reaches the terminal rather than the selector token the deadline engine gates
on.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....application.user_profile import build_profile_preflight_requirement
from ....core.resources import resources
from ....tests.cli_runner import invoke_cached_cli
from ._overview_calendar_support import calendar_backend_omitting_gating_facts

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The gating fact this module leaves unanswered, and the selector token the
#: warning stream carries for it. The refusal must show the label, not this.
_OMITTED_FACT_PATH = "withholding.has_employees"
_OMITTED_SELECTOR = "has_employees"

_REFUSING_INVOCATIONS = (
    pytest.param(
        ["app", "overview", "calendar", "--from", "2026-01-01", "--to", "2026-03-31"],
        id="calendar",
    ),
    pytest.param(["app", "overview", "agenda", "--date", "2026-04-15"], id="agenda"),
    pytest.param(["app", "overview", "backlog"], id="backlog"),
)


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


@pytest.fixture
def backend_missing_a_gating_fact(tmp_path: Path) -> Iterator[None]:
    """Deliberately NOT autouse.

    The control test at the bottom of this module needs a backend with the
    fact ANSWERED, and the active-profile pointer transaction refuses to nest
    across storage roots, so a test cannot opt out of an autouse backend by
    opening its own.
    """
    with calendar_backend_omitting_gating_facts(tmp_path, _OMITTED_FACT_PATH):
        yield


def _expected_label() -> str:
    """The operator label for the omitted field, read from the live schema."""
    return build_profile_preflight_requirement(
        _OMITTED_FACT_PATH,
        schema=resources().user_profile_schema.singleton,
        selector=_OMITTED_SELECTOR,
    ).label


def test_the_omitted_field_has_a_label_distinct_from_its_selector_token() -> None:
    """Anchor: every assertion below is vacuous if label and token coincide."""
    assert _expected_label() != _OMITTED_SELECTOR


@pytest.mark.parametrize("args", _REFUSING_INVOCATIONS)
def test_the_verb_refuses_because_the_profile_fact_is_unanswered(
    args: list[str],
    backend_missing_a_gating_fact: None,
) -> None:
    """The positive control for the label assertions below.

    Establishes that omitting the fact is what causes the refusal. Without
    this, a refusal caused by something else entirely could still carry the
    label and the next test would pass for the wrong reason.
    """
    # Asserted on the envelope rather than on the prose, because the refusal
    # word is translated and an English token never appears in a
    # Spanish-rendered refusal. The siblings below stay on text only because
    # they resolve their expected label through the locale the CLI renders in.
    #
    # The FAILED CONDITION is the assertion, not the category or the code:
    # both of those are shared with a Click parameter error on the same verb,
    # measured against the live CLI, so neither can establish that omitting the
    # fact is what refused. A parameter error names no condition at all.
    result = _invoke(["--format", "json", *args])

    assert result.exit_code != 0, result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == "error", result.output
    action = envelope["error"]["action"] or {}
    assert action["failed_condition_id"] == "cli.overview.profile.complete", result.output


@pytest.mark.parametrize("args", _REFUSING_INVOCATIONS)
def test_the_refusal_names_the_unanswered_field_by_its_operator_label(
    args: list[str],
    backend_missing_a_gating_fact: None,
) -> None:
    result = _invoke(list(args))

    assert result.exit_code != 0, result.output
    assert _expected_label() in result.output, result.output


@pytest.mark.parametrize("args", _REFUSING_INVOCATIONS)
def test_the_refusal_never_shows_the_bare_selector_token(
    args: list[str],
    backend_missing_a_gating_fact: None,
) -> None:
    """The token may appear only inside the enriched text, never on its own.

    Checked by removing the enriched rendering from the output first, so a
    label that happens to embed the token does not mask a second, raw
    occurrence elsewhere in the refusal.
    """
    result = _invoke(list(args))

    assert result.exit_code != 0, result.output
    residue = result.output.replace(_expected_label(), "")
    assert _OMITTED_SELECTOR not in residue, result.output


@pytest.mark.parametrize("args", _REFUSING_INVOCATIONS)
def test_the_refusal_is_not_rendered_as_invalid_operator_input(
    args: list[str],
    backend_missing_a_gating_fact: None,
) -> None:
    """An unanswered profile fact is workflow state, not a bad command line."""
    result = _invoke(list(args))

    assert result.exit_code != 0, result.output
    assert "Invalid value" not in result.output, result.output


def test_answering_the_fact_removes_this_refusal(tmp_path: Path) -> None:
    """The refusal is caused by the ABSENT fact, not by the fixture generally.

    The strongest available control: the same verb over the same backend with
    the fact answered must not refuse for this reason. Without it, the module
    proves only that the verb refuses, never that the omission is why.
    """
    with calendar_backend_omitting_gating_facts(tmp_path):
        result = _invoke(["app", "overview", "calendar", "--from", "2026-01-01", "--to", "2026-03-31"])

    assert _expected_label() not in result.output, result.output
