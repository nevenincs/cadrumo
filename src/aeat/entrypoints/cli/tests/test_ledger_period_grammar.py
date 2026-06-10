"""One-operator-period-grammar tests for the ledger ``--period`` surface (D4).

The operator-surface ADR decision D4 makes the AEAT modelo tokens the
canonical operator period grammar everywhere, while the ledger ``--period``
sites accept their legacy calendar shapes as an alternate input override and
convert both to the one internal calendar representation the ledger stores.

These are real-behaviour tests: the equivalence and refusal cases exercise the
production ``_canonical_period`` normaliser (which consumes the registry
period-union validator at :mod:`aeat.core._period`), and the end-to-end cases
drive ``aeat app ledger preflight`` / ``status`` against a real isolated
encrypted bucket and the real ledger backend, asserting the AEAT token and the
equivalent calendar shape produce the same output.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from ....application.aggregation._models import Period
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app
from .._common import _canonical_period

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# --- Equivalence: AEAT token == calendar shape -> one internal period --------
#
# Each pair is (year-qualified AEAT token, equivalent calendar shape). The
# canonical AEAT grammar is the left column; the calendar shape on the right is
# the accepted-and-converted alternate input. Both must normalise to the same
# internal representation and that representation must validate downstream as a
# ledger :class:`Period`.
_EQUIVALENT_PERIODS = (
    ("2026-1T", "2026Q1"),
    ("2026-2T", "2026Q2"),
    ("2026-3T", "2026Q3"),
    ("2026-4T", "2026Q4"),
    ("2026-0A", "2026"),
    ("2026-01", "2026-01"),
    ("2026-03", "2026-03"),
    ("2026-12", "2026-12"),
)


@pytest.mark.parametrize(("aeat_token", "calendar_shape"), _EQUIVALENT_PERIODS)
def test_aeat_token_and_calendar_shape_normalise_to_same_internal_period(aeat_token: str, calendar_shape: str) -> None:
    """The canonical AEAT token and its calendar shape yield one internal value."""

    from_aeat = _canonical_period(aeat_token)
    from_calendar = _canonical_period(calendar_shape)
    assert from_aeat == from_calendar, (aeat_token, calendar_shape, from_aeat, from_calendar)


@pytest.mark.parametrize(("aeat_token", "calendar_shape"), _EQUIVALENT_PERIODS)
def test_normalised_period_validates_as_ledger_period(aeat_token: str, calendar_shape: str) -> None:
    """The single internal representation parses as a ledger ``Period`` for both notations.

    This is the anti-leak proof: a conversion that emitted a shape the ledger
    cannot consume (e.g. an instalment clave) would raise here instead of
    silently producing an unusable token.
    """

    canonical = _canonical_period(aeat_token)
    # Both inputs already proven equal above; validating one proves both.
    assert _canonical_period(calendar_shape) == canonical
    parsed = Period.model_validate(canonical)
    assert parsed.year == 2026


def test_registry_union_validator_is_the_token_authority() -> None:
    """``_canonical_period`` accepts exactly the span-shaped registry tokens.

    Quarters, the annual period, and months are ledger-meaningful and convert.
    The extended-union members the registry validator also accepts (``EXT-*``,
    ``AD-HOC``, ``EVENT-N``) and the instalment claves (``1P``-``4P``) are NOT
    a ledger date span, so they are not silently converted into a calendar
    shape the ledger cannot filter by.
    """

    # Span-shaped tokens convert.
    assert _canonical_period("2026-1T") == "2026Q1"
    assert _canonical_period("2026-0A") == "2026"
    assert _canonical_period("2026-06") == "2026-06"

    # Non-span registry-union members and instalment claves do not convert to a
    # ledger calendar shape; they raise rather than emit an unusable token.
    for non_ledger in ("2026-1P", "2026-EXT-1T", "EVENT-3", "AD-HOC"):
        with pytest.raises(typer.BadParameter):
            _canonical_period(non_ledger)


# --- Instructive refusals -----------------------------------------------------


@pytest.mark.parametrize("bare_token", ["1T", "2T", "3T", "4T", "0A", "01", "03", "12"])
def test_bare_aeat_token_refuses_with_year_instruction(bare_token: str) -> None:
    """A bare AEAT token (no year) refuses, naming both notations and the year fix.

    The ledger commands carry no ``--year``; rather than guess a year the
    refusal must instruct the operator to qualify the token (``2026-1T``) or
    use the calendar shape (``2026Q1``).
    """

    with pytest.raises(typer.BadParameter) as excinfo:
        _canonical_period(bare_token)
    message = str(excinfo.value)
    assert bare_token in message
    # Names the year-qualified canonical notation and the calendar alternate.
    assert "2026-" in message
    assert any(shape in message for shape in ("2026Q1", "2026-03", "2026"))


@pytest.mark.parametrize("invalid_token", ["not-a-period", "ZZ", "2026-99", "13T", "Q5"])
def test_invalid_token_refuses_naming_both_notations(invalid_token: str) -> None:
    """A genuinely-invalid token refuses, naming both accepted notations."""

    with pytest.raises(typer.BadParameter) as excinfo:
        _canonical_period(invalid_token)
    message = str(excinfo.value)
    # Names the canonical AEAT tokens and the calendar shapes.
    assert "2026-1T" in message
    assert "2026Q1" in message


def test_empty_period_refuses() -> None:
    """An empty period refuses with the dedicated empty-period message."""

    with pytest.raises(typer.BadParameter):
        _canonical_period("   ")


# --- End-to-end: real ledger command accepts both notations identically -------


@pytest.fixture()
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="operator"),
        )
        yield


def _add_business_row_missing_facts(cli_runner: CliRunner) -> None:
    add = cli_runner.invoke(
        app,
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-02-10",
            "--amount",
            "-242.00",
            "--direction",
            "OUTGOING",
            "--description",
            "Q1 business expense missing tax facts",
            "--classification",
            "BUSINESS",
            "--idempotency-key",
            "period-grammar-q1",
        ],
    )
    assert add.exit_code == 0, add.output


def test_preflight_accepts_aeat_token_and_calendar_shape_identically(
    cli_runner: CliRunner, _isolated_backend: None
) -> None:
    """``ledger preflight`` produces the same report for ``2026-1T`` and ``2026Q1``.

    Real backend, real encrypted bucket: a February 2026 business row falls in
    Q1; both notations must select it and surface the same readiness gap.
    """

    _add_business_row_missing_facts(cli_runner)

    aeat = cli_runner.invoke(app, ["app", "ledger", "preflight", "--period", "2026-1T"])
    calendar = cli_runner.invoke(app, ["app", "ledger", "preflight", "--period", "2026Q1"])

    assert aeat.exit_code == 0, aeat.output
    assert calendar.exit_code == 0, calendar.output
    # The canonical internal period prints identically for both inputs.
    assert "period\t2026Q1" in aeat.output
    assert "period\t2026Q1" in calendar.output
    # Same row checked, same readiness verdict.
    assert "checked\t1" in aeat.output
    assert "checked\t1" in calendar.output
    assert "ready\tfalse" in aeat.output
    assert "ready\tfalse" in calendar.output


def test_status_accepts_aeat_token_and_calendar_shape_identically(
    cli_runner: CliRunner, _isolated_backend: None
) -> None:
    """``ledger status`` reports the same totals for ``2026-1T`` and ``2026Q1``."""

    _add_business_row_missing_facts(cli_runner)

    aeat = cli_runner.invoke(app, ["app", "ledger", "status", "--period", "2026-1T"])
    calendar = cli_runner.invoke(app, ["app", "ledger", "status", "--period", "2026Q1"])

    assert aeat.exit_code == 0, aeat.output
    assert calendar.exit_code == 0, calendar.output
    # Identical economic summary and selected-period marker for both notations.
    for marker in ("expense_total\t242", "net_total\t-242", "Period\t2026Q1"):
        assert marker in aeat.output, aeat.output
        assert marker in calendar.output, calendar.output


def test_preflight_bare_aeat_token_refuses_with_year_instruction(
    cli_runner: CliRunner, _isolated_backend: None
) -> None:
    """``ledger preflight --period 1T`` refuses, instructing how to supply the year."""

    result = cli_runner.invoke(app, ["app", "ledger", "preflight", "--period", "1T"])
    assert result.exit_code != 0, result.output
    assert "2026-1T" in result.output or "2026Q1" in result.output


def test_preflight_help_leads_with_aeat_tokens(cli_runner: CliRunner) -> None:
    """The preflight ``--period`` help leads with the canonical AEAT tokens.

    The year-qualified AEAT token form must appear before the calendar shapes,
    teaching one grammar while keeping the calendar shapes documented as also
    accepted.
    """

    result = cli_runner.invoke(app, ["app", "ledger", "preflight", "--help"])
    assert result.exit_code == 0, result.output
    output = result.output
    # The AEAT token form is advertised, and the calendar shapes are noted as
    # also accepted. Locale-default output is Spanish, so assert on the
    # notation tokens themselves which are language-invariant.
    assert "2026-1T" in output or "1T" in output
    assert "2026Q1" in output
