"""One-strict-period-grammar tests for the ledger ``--period`` surface.

The operator-surface decision makes the AEAT modelo tokens the *only* operator
period grammar
everywhere. The ledger ``--period`` sites accept exactly the AEAT tokens
(``0A`` / ``1T``-``4T`` / ``01``-``12``) and take a separate ``--year`` to
supply the year the calendar shape used to embed, so ``--period 1T --year
2024`` reads identically across ledger and modelo. A filing period is ALWAYS
carried as a ``(year, bare-token)`` pair, materialised as a typed
:class:`Period` date span — never a combined calendar string. The calendar
shapes (``2024Q1`` / ``2024-03`` / ``2024``) and the ``2024-1T`` year-qualified
hybrid are **removed** — they now refuse.

These are real-behaviour tests: the resolution and refusal cases exercise the
production ``_canonical_period`` normaliser (which consumes the registry
period-union validator at :mod:`aeat.core`), and the end-to-end cases
drive ``aeat app ledger preflight`` / ``status`` against a real isolated
encrypted bucket and the real ledger backend.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
import typer

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core import Period
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .._common import _canonical_period, _filter_canonical_period

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# --- Strict resolution: (AEAT token, --year) -> typed Period date span --------
#
# Each row is (bare AEAT token, year, expected registry_token, expected
# inclusive start, expected inclusive end). The bare token is the only accepted
# operator grammar; the year arrives through ``--year``. The pair resolves to a
# typed :class:`Period` date span the ledger filters by — there is no
# intermediate calendar string.
_TOKEN_YEAR_SPAN = (
    ("1T", 2024, "1T", date(2024, 1, 1), date(2024, 3, 31)),
    ("2T", 2024, "2T", date(2024, 4, 1), date(2024, 6, 30)),
    ("3T", 2024, "3T", date(2024, 7, 1), date(2024, 9, 30)),
    ("4T", 2024, "4T", date(2024, 10, 1), date(2024, 12, 31)),
    ("0A", 2024, "0A", date(2024, 1, 1), date(2024, 12, 31)),
    ("01", 2024, "01", date(2024, 1, 1), date(2024, 1, 31)),
    ("03", 2024, "03", date(2024, 3, 1), date(2024, 3, 31)),
    ("12", 2024, "12", date(2024, 12, 1), date(2024, 12, 31)),
)


@pytest.mark.parametrize(("token", "year", "registry_token", "start", "end"), _TOKEN_YEAR_SPAN)
def test_aeat_token_plus_year_resolves_to_period(
    token: str,
    year: int,
    registry_token: str,
    start: date,
    end: date,
) -> None:
    """A bare AEAT token plus ``--year`` resolves to one typed :class:`Period`."""

    resolved = _canonical_period(token, year=year)
    assert isinstance(resolved, Period)
    assert resolved.year == year
    assert resolved.registry_token == registry_token
    assert resolved.start_date == start
    assert resolved.end_date == end


@pytest.mark.parametrize(("token", "year", "registry_token", "start", "end"), _TOKEN_YEAR_SPAN)
def test_resolved_period_round_trips_through_registry_token(
    token: str,
    year: int,
    registry_token: str,
    start: date,
    end: date,
) -> None:
    """The resolved :class:`Period` carries the bare registry token back out.

    Anti-leak proof: the operator's ``(year, token)`` pair is recoverable from
    the resolved date span, so no combined calendar string is needed to render
    the period back to the operator.
    """

    resolved = _canonical_period(token, year=year)
    assert (resolved.year, resolved.registry_token) == (year, registry_token)


def test_registry_union_validator_is_the_token_authority() -> None:
    """``_canonical_period`` accepts exactly the span-shaped registry tokens.

    Quarters, the annual period, and months are ledger-meaningful and resolve.
    The extended-union members the registry validator also accepts (``EXT-*``,
    ``AD-HOC``, ``EVENT-N``) and the instalment claves (``1P``-``4P``) are NOT
    a ledger date span, so they refuse rather than resolve to a usable period.
    """

    # Span-shaped tokens resolve.
    tokens = ("1T", "0A", "06")
    assert tuple(_canonical_period(token, year=2024).registry_token for token in tokens) == tokens

    # Non-span registry-union members and instalment claves do not resolve to a
    # ledger date span; they raise rather than emit an unusable period.
    for non_ledger in ("1P", "EXT-1T", "EVENT-3", "AD-HOC"):
        with pytest.raises(typer.BadParameter):
            _canonical_period(non_ledger, year=2024)


# --- Calendar shapes now REFUSE -----------------------------------------------


@pytest.mark.parametrize("calendar_shape", ["2024Q1", "2024-03", "2024", "2026Q4", "2025-12"])
def test_calendar_shape_refuses_naming_aeat_tokens_and_year(calendar_shape: str) -> None:
    """A calendar shape is no longer accepted; it refuses, naming the AEAT tokens and --year."""

    with pytest.raises(typer.BadParameter) as excinfo:
        _canonical_period(calendar_shape, year=2024)
    message = str(excinfo.value)
    # The refusal names the AEAT token grammar and the --year argument.
    assert "1T" in message
    assert "0A" in message
    assert "--year" in message


@pytest.mark.parametrize("hybrid", ["2024-1T", "2024-0A", "2026-1T"])
def test_year_qualified_hybrid_refuses(hybrid: str) -> None:
    """The ``2024-1T`` year-qualified hybrid now refuses.

    Bare ``--period`` carries no year; the year comes from ``--year``. A
    year-qualified hybrid is a calendar-style notation that the strict grammar
    rejects. (``2024-01`` collides with the month-token-with-year shape but is
    not a bare month token, so it refuses too.)
    """

    with pytest.raises(typer.BadParameter):
        _canonical_period(hybrid, year=2024)


@pytest.mark.parametrize("invalid_token", ["not-a-period", "ZZ", "99", "13T", "Q5"])
def test_invalid_token_refuses_naming_aeat_tokens(invalid_token: str) -> None:
    """A genuinely-invalid token refuses, naming the AEAT token grammar and --year."""

    with pytest.raises(typer.BadParameter) as excinfo:
        _canonical_period(invalid_token, year=2024)
    message = str(excinfo.value)
    assert "1T" in message
    assert "--year" in message


def test_empty_period_refuses() -> None:
    """An empty period refuses with the dedicated empty-period message."""

    with pytest.raises(typer.BadParameter):
        _canonical_period("   ", year=2024)


# --- Filter clause: bare AEAT token plus a separate year= clause --------------


def test_filter_clause_accepts_bare_token_with_year() -> None:
    """``--filter period=1T --filter year=2024`` resolves to a typed :class:`Period`.

    The filter grammar carries the year on a separate ``year=`` clause, so
    ``period=`` is the same bare AEAT token the ``--period`` option accepts —
    there is no year-qualified combined token.
    """

    tokens = ("1T", "0A", "03")
    assert tuple(_filter_canonical_period(token, year=2024).registry_token for token in tokens) == tokens


@pytest.mark.parametrize("rejected", ["2024Q1", "2024", "2024-1T", "not-a-period", "1P"])
def test_filter_clause_refuses_calendar_and_year_qualified(rejected: str) -> None:
    """The filter clause refuses a calendar shape or a year-qualified hybrid token."""

    with pytest.raises(typer.BadParameter):
        _filter_canonical_period(rejected, year=2024)


# --- End-to-end: real ledger command takes --period AEAT token + --year -------


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


def _add_business_row_missing_facts() -> None:
    add = invoke_cached_cli(
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-02-10",
            "--amount",
            "242.00",
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


def test_preflight_accepts_aeat_token_with_year(_isolated_backend: None) -> None:
    """``ledger preflight --period 1T --year 2026`` selects the Q1 2026 row and reports the gap.

    Real backend, real encrypted bucket: a February 2026 business row falls in
    Q1; the AEAT token plus ``--year`` must select it and surface the gap.
    """

    _add_business_row_missing_facts()

    result = invoke_cached_cli(["app", "ledger", "preflight", "--period", "1T", "--year", "2026"])

    assert result.exit_code == 0, result.output
    # The period echoes back as the operator-facing ``<token> <year>`` pair,
    # never a combined calendar string.
    assert "period\t1T 2026" in result.output
    assert "2026Q1" not in result.output
    assert "checked\t1" in result.output
    assert "ready\tfalse" in result.output


def test_status_accepts_aeat_token_with_year(_isolated_backend: None) -> None:
    """``ledger status --period 1T --year 2026`` reports the Q1 totals."""

    _add_business_row_missing_facts()

    result = invoke_cached_cli(["app", "ledger", "status", "--period", "1T", "--year", "2026"])

    assert result.exit_code == 0, result.output
    for marker in ("business_expense_total\t242", "business_net_total\t-242", "1T 2026"):
        assert marker in result.output, result.output
    assert "2026Q1" not in result.output


def test_preflight_calendar_shape_refuses(_isolated_backend: None) -> None:
    """``ledger preflight --period 2026Q1 --year 2026`` refuses, naming the AEAT tokens."""

    result = invoke_cached_cli(["app", "ledger", "preflight", "--period", "2026Q1", "--year", "2026"])
    assert result.exit_code != 0, result.output
    assert "1T" in result.output


def test_status_period_without_year_refuses(_isolated_backend: None) -> None:
    """``ledger status --period 1T`` (no --year) refuses, instructing to add --year."""

    _add_business_row_missing_facts()

    result = invoke_cached_cli(["app", "ledger", "status", "--period", "1T"])
    assert result.exit_code != 0, result.output
    assert "--year" in result.output


def test_preflight_help_documents_aeat_tokens_and_year() -> None:
    """The preflight ``--period`` help documents the AEAT tokens; ``--year`` is present.

    No calendar shape is mentioned. Locale-default output is Spanish, so assert
    on the language-invariant notation tokens and the ``--year`` flag.
    """

    result = invoke_cached_cli(["app", "ledger", "preflight", "--help"])
    assert result.exit_code == 0, result.output
    output = result.output
    assert "1T" in output
    assert "0A" in output
    assert "--year" in output
    # No calendar shape is advertised on the operator surface.
    assert "2026Q1" not in output
