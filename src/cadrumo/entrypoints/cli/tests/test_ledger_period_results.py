"""The CLI's JSON shape of the served periods accepts exactly what the application serves."""

from __future__ import annotations

from datetime import date

import pytest

from ....application.ledger.period_options import LedgerPeriodSpanRequest, LedgerPeriodsQuery, ledger_periods
from ....core.external_constants import OutputLanguage
from ..ledger_period_results import LedgerPeriodsPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("language", list(OutputLanguage), ids=lambda language: language.value)
def test_the_payload_takes_the_served_periods_as_the_wire_carries_them(language: OutputLanguage) -> None:
    served = ledger_periods(
        LedgerPeriodsQuery(
            year=2026,
            days=(date(2025, 12, 31), date(2026, 1, 1)),
            covering=LedgerPeriodSpanRequest(first_day=date(2026, 1, 2), last_day=date(2026, 2, 3)),
        ),
        reference_day=date(2026, 11, 3),
        language=language,
    )

    payload = LedgerPeriodsPayload.model_validate(served.model_dump(mode="json"))

    assert payload.model_dump(mode="json") == served.model_dump(mode="json")
    assert len(payload.periods) == 17
    assert payload.periods[0].period.code == payload.annual_code


def test_the_payload_refuses_a_field_the_application_does_not_serve() -> None:
    served = ledger_periods(LedgerPeriodsQuery(), reference_day=date(2026, 11, 3)).model_dump(mode="json")

    with pytest.raises(ValueError, match="extra"):
        LedgerPeriodsPayload.model_validate({**served, "invented": 1})
