"""Shared supplied-date boundary tests for diagnostics and ledger reporting."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pytest
import typer
from pydantic import ValidationError

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..app_diagnostics_commands import parse_iso_date
from ..diagnostics_results import (
    ErrorsBreakdownResult,
    LatencyPercentilesPayload,
    LatencyResult,
    LlmUsageResult,
    RunHealthResult,
    RunsListResult,
)
from ..ledger_read_commands import parse_iso_date as parse_ledger_date

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_EARLIER = date(filing_year_envelope().horizon, 1, 1).isoformat()
_LATER = date(filing_year_envelope().horizon, 2, 1).isoformat()


@pytest.mark.parametrize("parser", (parse_iso_date, parse_ledger_date))
def test_supplied_blank_date_bound_refuses(parser: Callable[[str | None, str], date | None]) -> None:
    """A blank supplied --since is never widened into an unbounded query."""
    with pytest.raises(typer.BadParameter):
        parser("", "--since")


@pytest.mark.parametrize("parser", (parse_iso_date, parse_ledger_date))
def test_absent_date_bound_remains_optional(parser: Callable[[str | None, str], date | None]) -> None:
    """Only an omitted date option remains an unbounded query."""
    assert parser(None, "--since") is None


class TestWireWindowInvariant:
    """A diagnostics envelope cannot publish a window its own report refuses.

    The report models carry the closed-interval invariant, but the wire
    envelopes redeclared the bounds as unconstrained strings, so a directly
    constructed or deserialized envelope could still present a reversed
    window. ``RunsListResult.limit`` had the same split: the ``--limit``
    option declares ``min=1`` while the payload accepted ``0``, a cap that can
    never return a row.
    """

    def _runs(self, **overrides: object) -> RunsListResult:
        fields: dict[str, object] = {"runs": [], "total_runs": 0, "has_run_data": False}
        fields.update(overrides)
        return RunsListResult.model_validate(fields)

    def _envelopes(self) -> tuple[tuple[type, dict[str, object]], ...]:
        return (
            (
                RunHealthResult,
                {
                    "llm_providers": [],
                    "total_runs": 0,
                    "total_succeeded": 0,
                    "total_failed": 0,
                    "has_run_data": False,
                    "auth_provider": "",
                    "auth_configured": False,
                    "persisted_session_present": False,
                    "persisted_session_state": "",
                    "probe_summary": "",
                    "session_stale": False,
                },
            ),
            (RunsListResult, {"runs": [], "total_runs": 0, "has_run_data": False}),
            (
                LatencyResult,
                {
                    "overall": LatencyPercentilesPayload(entries=0),
                    "by_provider": [],
                    "has_run_data": False,
                },
            ),
            (
                ErrorsBreakdownResult,
                {"total_runs": 0, "total_failed": 0, "by_error_kind": [], "has_failures": False},
            ),
            (
                LlmUsageResult,
                {
                    "by_provider": [],
                    "total_runs": 0,
                    "total_succeeded": 0,
                    "total_failed": 0,
                    "overall_success_rate": "0",
                    "has_run_data": False,
                },
            ),
        )

    def test_every_envelope_refuses_a_reversed_window(self) -> None:
        for envelope, required in self._envelopes():
            with pytest.raises(ValidationError):
                envelope(since=_LATER, until=_EARLIER, **required)

    def test_every_envelope_accepts_an_ordered_window(self) -> None:
        for envelope, required in self._envelopes():
            built = envelope(since=_EARLIER, until=_LATER, **required)
            assert built.since == _EARLIER
            assert built.until == _LATER

    def test_every_envelope_keeps_absent_bounds_optional(self) -> None:
        for envelope, required in self._envelopes():
            assert envelope(**required).since is None

    def test_reversed_window_is_refused_on_deserialization(self) -> None:
        """The invariant holds for a payload rebuilt from JSON, not only construction."""
        valid = self._runs(since=_EARLIER, until=_LATER)
        assert RunsListResult.model_validate_json(valid.model_dump_json()) == valid
        reversed_payload = valid.model_dump()
        reversed_payload["since"], reversed_payload["until"] = _LATER, _EARLIER
        with pytest.raises(ValidationError):
            RunsListResult.model_validate(reversed_payload)

    def test_zero_limit_is_refused_and_one_is_accepted(self) -> None:
        with pytest.raises(ValidationError):
            self._runs(limit=0)
        with pytest.raises(ValidationError):
            self._runs(limit=-1)
        assert self._runs(limit=1).limit == 1
        assert self._runs().limit is None
