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
period-union validator at :mod:`cadrumo.core`), and the end-to-end cases
drive ``aeat app ledger preflight`` / ``status`` against a real isolated
encrypted bucket and the real ledger backend.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
import typer

from ....core.period import Period, StandardPeriodCode
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.cli_runner import invoke_cached_cli
from ..period_parsing import _canonical_period, _filter_canonical_period, _LedgerPeriodRefusal

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _expected_span_shaped_tokens() -> frozenset[str]:
    """Return the span-shaped registry tokens, derived from the enum + span rule.

    Independent of the production ``--period`` normaliser: iterate every
    :class:`StandardPeriodCode` member and keep those whose ``(year, token)``
    :class:`Period` carries a calendar date span. The instalment claves
    (``1P``-``4P``) have no span and are excluded, as do the extended-union forms
    (which are not enum members). This is the specification the ledger
    ``--period`` boundary must advertise; the grammar cases assert the boundary's
    advertised set equals it, so a wrong advertised set — or the old hardcoded
    ``{1T, 0A}`` prose — fails the comparison rather than passing silently.
    """
    return frozenset(
        member.value for member in StandardPeriodCode if Period.from_year_and_code(2024, member.value).has_date_span()
    )


# --- Strict resolution: (AEAT token, --year) -> typed Period date span --------
#
# Each row is (bare AEAT token, year, expected registry_token, expected
# inclusive start, expected inclusive end). The bare token is the only accepted
# operator grammar; the year arrives through ``--year``. The pair resolves to a
# typed :class:`Period` date span the ledger filters by — there is no
# intermediate calendar string.
#
# The table exercises EVERY span-shaped token, not a sample: 2024 is a leap year,
# so the February span ends on the 29th. ``test_token_year_span_table_exercises
# _every_span_shaped_token`` asserts this covers exactly the derived span-shaped
# set, so a newly-added span-shaped enum member cannot go unexercised.
_TOKEN_YEAR_SPAN = (
    ("1T", 2024, "1T", date(2024, 1, 1), date(2024, 3, 31)),
    ("2T", 2024, "2T", date(2024, 4, 1), date(2024, 6, 30)),
    ("3T", 2024, "3T", date(2024, 7, 1), date(2024, 9, 30)),
    ("4T", 2024, "4T", date(2024, 10, 1), date(2024, 12, 31)),
    ("0A", 2024, "0A", date(2024, 1, 1), date(2024, 12, 31)),
    ("01", 2024, "01", date(2024, 1, 1), date(2024, 1, 31)),
    ("02", 2024, "02", date(2024, 2, 1), date(2024, 2, 29)),
    ("03", 2024, "03", date(2024, 3, 1), date(2024, 3, 31)),
    ("04", 2024, "04", date(2024, 4, 1), date(2024, 4, 30)),
    ("05", 2024, "05", date(2024, 5, 1), date(2024, 5, 31)),
    ("06", 2024, "06", date(2024, 6, 1), date(2024, 6, 30)),
    ("07", 2024, "07", date(2024, 7, 1), date(2024, 7, 31)),
    ("08", 2024, "08", date(2024, 8, 1), date(2024, 8, 31)),
    ("09", 2024, "09", date(2024, 9, 1), date(2024, 9, 30)),
    ("10", 2024, "10", date(2024, 10, 1), date(2024, 10, 31)),
    ("11", 2024, "11", date(2024, 11, 1), date(2024, 11, 30)),
    ("12", 2024, "12", date(2024, 12, 1), date(2024, 12, 31)),
)
_CALENDAR_SHAPES = ("2024Q1", "2024-03", "2024", "2026Q4", "2025-12")
_YEAR_QUALIFIED_HYBRIDS = ("2024-1T", "2024-0A", "2026-1T")
_INVALID_TOKENS = ("not-a-period", "ZZ", "99", "13T", "Q5")
_FILTER_REJECTED_PERIODS = ("2024Q1", "2024", "2024-1T", "not-a-period", "1P")
_HISTORIC_IMPORT_PERIODS = ("2024-1T", "2024/1T", "2024Q1")


def test_aeat_token_plus_year_resolves_to_period() -> None:
    """A bare AEAT token plus ``--year`` resolves to one typed :class:`Period`.

    Anti-leak proof: the operator's ``(year, token)`` pair is recoverable from
    the resolved date span, so no combined calendar string is needed to render
    the period back to the operator.
    """

    for token, year, registry_token, start, end in _TOKEN_YEAR_SPAN:
        resolved = _canonical_period(token, year=year)
        assert isinstance(resolved, Period)
        assert resolved.filing_year == year
        assert resolved.registry_token == registry_token
        assert resolved.start_date == start
        assert resolved.end_date == end


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


def test_token_year_span_table_exercises_every_span_shaped_token() -> None:
    """The resolution fixture covers exactly the derived span-shaped token set.

    Anti-vacuity: a newly-added span-shaped :class:`StandardPeriodCode` member (or
    a dropped table row) fails this equality, so
    :func:`test_aeat_token_plus_year_resolves_to_period` cannot silently stop
    exercising a token. Nine of the seventeen were previously untested.
    """

    covered = {row[0] for row in _TOKEN_YEAR_SPAN}
    assert covered == _expected_span_shaped_tokens()


def test_calendar_shape_refuses_advertising_accepted_tokens_as_data() -> None:
    """A calendar shape refuses, carrying the accepted token set as structured data.

    Load-bearing assertion: the refusal advertises the accepted span-shaped
    tokens on the structured carrier the JSON error envelope's context is built
    from (:attr:`_LedgerPeriodRefusal.accepted_period_tokens`), compared against
    the set derived independently from the enum plus the span rule — never the
    refusal's own message. A wording pass on the rendered prose therefore cannot
    red this case. One thin, wording-tolerant check keeps the human refusal
    instructive per the CLI-boundary contract.
    """

    expected = _expected_span_shaped_tokens()
    assert len(expected) == 17  # 1T-4T, 0A, 01-12; instalment claves 1P-4P carry no span
    for calendar_shape in _CALENDAR_SHAPES:
        with pytest.raises(typer.BadParameter) as excinfo:
            _canonical_period(calendar_shape, year=2024)
        refusal = excinfo.value
        assert isinstance(refusal, _LedgerPeriodRefusal), calendar_shape
        assert frozenset(refusal.accepted_period_tokens) == expected, calendar_shape
        message = str(refusal)
        assert "1T" in message and "--year" in message, calendar_shape


def test_year_qualified_hybrid_refuses() -> None:
    """The ``2024-1T`` year-qualified hybrid now refuses.

    Bare ``--period`` carries no year; the year comes from ``--year``. A
    year-qualified hybrid is a calendar-style notation that the strict grammar
    rejects. (``2024-01`` collides with the month-token-with-year shape but is
    not a bare month token, so it refuses too.)
    """

    for hybrid in _YEAR_QUALIFIED_HYBRIDS:
        with pytest.raises(typer.BadParameter):
            _canonical_period(hybrid, year=2024)


def test_invalid_token_refuses_advertising_accepted_tokens_as_data() -> None:
    """A genuinely-invalid token refuses, carrying the accepted set as structured data.

    Same structured contract as the calendar-shape case: the accepted span-shaped
    set rides on the refusal's carrier and is compared against the enum-derived
    set, so the grammar case survives a wording pass on the message.
    """

    expected = _expected_span_shaped_tokens()
    for invalid_token in _INVALID_TOKENS:
        with pytest.raises(typer.BadParameter) as excinfo:
            _canonical_period(invalid_token, year=2024)
        refusal = excinfo.value
        assert isinstance(refusal, _LedgerPeriodRefusal), invalid_token
        assert frozenset(refusal.accepted_period_tokens) == expected, invalid_token
        message = str(refusal)
        assert "1T" in message and "--year" in message, invalid_token


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


def test_filter_clause_refuses_calendar_and_year_qualified() -> None:
    """The filter clause refuses a calendar shape or a year-qualified hybrid token."""

    for rejected in _FILTER_REJECTED_PERIODS:
        with pytest.raises(typer.BadParameter):
            _filter_canonical_period(rejected, year=2024)


# --- End-to-end: real ledger command takes --period AEAT token + --year -------


_isolated_backend = active_profile_isolated_backend_fixture(autouse=False)


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
    # The period echoes back through Period.__str__, never as a combined
    # calendar string or reversed ``<token> <year>`` pair.
    assert "period\t2026 1T" in result.output
    assert "1T 2026" not in result.output
    assert "2026Q1" not in result.output
    assert "checked\t1" in result.output
    assert "ready\tfalse" in result.output


def test_ledger_read_period_display_matches_typed_period_across_text_and_json(_isolated_backend: None) -> None:
    """Real ledger reads use ``Period.__str__`, while JSON retains raw period fields."""

    _add_business_row_missing_facts()
    period = Period.from_year_and_code(2026, "1T")
    preflight = invoke_cached_cli(["app", "ledger", "preflight", "--period", "1T", "--year", "2026"])
    status = invoke_cached_cli(["app", "ledger", "status", "--period", "1T", "--year", "2026"])
    preflight_json = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "preflight", "--period", "1T", "--year", "2026"],
    )

    assert preflight.exit_code == 0, preflight.output
    assert status.exit_code == 0, status.output
    assert preflight_json.exit_code == 0, preflight_json.output
    assert f"period\t{period}" in preflight.output
    assert f"\t{period}" in status.output
    assert "1T 2026" not in preflight.output
    assert "1T 2026" not in status.output
    assert json.loads(preflight_json.output)["result"]["period"] == {
        "filing_year": 2026,
        "code": "1T",
    }


def test_status_accepts_aeat_token_with_year(_isolated_backend: None) -> None:
    """``ledger status --period 1T --year 2026`` reports the Q1 totals."""

    _add_business_row_missing_facts()

    result = invoke_cached_cli(["app", "ledger", "status", "--period", "1T", "--year", "2026"])

    assert result.exit_code == 0, result.output
    for marker in ("business_expense_total\t242", "business_net_total\t-242", "2026 1T"):
        assert marker in result.output, result.output
    assert "1T 2026" not in result.output
    assert "2026Q1" not in result.output


def test_preflight_calendar_shape_refuses(_isolated_backend: None) -> None:
    """``ledger preflight --period 2026Q1 --year 2026`` refuses, naming the AEAT tokens."""

    result = invoke_cached_cli(["app", "ledger", "preflight", "--period", "2026Q1", "--year", "2026"])
    assert result.exit_code != 0, result.output
    assert "1T" in result.output


def _error_context(output: str) -> dict[str, object]:
    """Return the ``error.context`` object from the shared-spine JSON document."""
    for line in output.splitlines():
        candidate = line.strip()
        if candidate.startswith("{"):
            document = json.loads(candidate)
            assert document["status"] == "error", document
            error = document["error"]
            assert isinstance(error, dict), error
            context = error["context"]
            assert isinstance(context, dict), f"context is not an object: {context!r}"
            return {str(name): value for name, value in context.items()}
    raise AssertionError(f"no JSON error document found in output:\n{output}")


def test_period_refusal_advertises_accepted_tokens_on_error_envelope(_isolated_backend: None) -> None:
    """A JSON-mode ``--period`` refusal carries the accepted set on the error context.

    Real cached CLI, ``--format json``: a calendar shape refuses and the
    shared-spine error document's structured ``context`` advertises the accepted
    span-shaped tokens, compared against the enum-derived set. Proves the refusal
    site's structured carrier reaches the operator-facing envelope — not merely
    the exception object — so automation reads the accepted grammar as data. The
    ``accepted_periods`` key deliberately avoids the ``token`` substring the
    error-context scrubber redacts.
    """

    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "status", "--period", "2024Q1", "--year", "2024"],
    )
    assert result.exit_code != 0, result.output
    context = _error_context(result.output)
    advertised = context["accepted_periods"]
    assert isinstance(advertised, str), context
    assert frozenset(advertised.split(", ")) == _expected_span_shaped_tokens()


def _write_import_statement(path: Path) -> None:
    path.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2024-02-10,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )


def test_import_accepts_aeat_token_with_year(
    tmp_path: Path,
    _isolated_backend: None,
) -> None:
    """``ledger import --period 1T --year 2024`` accepts the canonical period form."""

    statement = tmp_path / "statement.csv"
    _write_import_statement(statement)

    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "import",
            "--file",
            str(statement),
            "--provider",
            "csv",
            "--dry-run",
            "--period",
            "1T",
            "--year",
            "2024",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Rows\t1" in result.output
    assert "DRY RUN MODE\tYes" in result.output
    assert "2024Q1" not in result.output
    assert "2024-1T" not in result.output


def test_import_historic_period_forms_refuse_with_current_canonical_grammar(
    tmp_path: Path,
    _isolated_backend: None,
) -> None:
    """Historic combined forms refuse and teach the AEAT token plus ``--year`` grammar."""

    statement = tmp_path / "statement.csv"
    _write_import_statement(statement)

    for historic_period in _HISTORIC_IMPORT_PERIODS:
        result = invoke_cached_cli(
            [
                "app",
                "ledger",
                "import",
                "--file",
                str(statement),
                "--provider",
                "csv",
                "--dry-run",
                "--period",
                historic_period,
                "--year",
                "2024",
            ],
        )

        assert result.exit_code != 0, result.output
        assert historic_period in result.output
        assert "1T" in result.output
        assert "0A" in result.output
        assert "--year" in result.output


def test_import_period_without_year_refuses_with_year_guidance(
    tmp_path: Path,
    _isolated_backend: None,
) -> None:
    """``ledger import --period 1T`` refuses because import also requires ``--year``."""

    statement = tmp_path / "statement.csv"
    _write_import_statement(statement)

    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "import",
            "--file",
            str(statement),
            "--provider",
            "csv",
            "--dry-run",
            "--period",
            "1T",
        ],
    )

    assert result.exit_code != 0, result.output
    assert "1T" in result.output
    assert "--year" in result.output


def test_import_period_year_prefixed_token_refuses_with_current_canonical_grammar(
    tmp_path: Path,
    _isolated_backend: None,
) -> None:
    """``ledger import --period 2026T1 --year 2026`` refuses and teaches ``1T`` plus ``--year``."""

    statement = tmp_path / "statement.csv"
    _write_import_statement(statement)

    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "import",
            "--file",
            str(statement),
            "--provider",
            "csv",
            "--dry-run",
            "--period",
            "2026T1",
            "--year",
            "2026",
        ],
    )

    assert result.exit_code != 0, result.output
    assert "2026T1" in result.output
    assert "1T" in result.output
    assert "--year" in result.output
    assert "2026-Q1" not in result.output


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
