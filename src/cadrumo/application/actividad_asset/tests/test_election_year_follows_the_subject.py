"""An election is read under the year it enters service, whatever the clock says.

The limits, the used-element advisory and the timeline's class names rest on the edition of the
election's own year.  Moving the register's clock across the whole envelope changes none of them.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.renta.actividad_asset.election import DirectEstimationRegime

from .ledger_support import MemoryLedger
from .register_support import MemoryRepository, memory_register_authority
from .test_register import ACQUISITION, NAME, register_forecast, register_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ASSET = "laptop-1"


def _operations(*, in_service_year: int, today: date) -> ActivityAssetOperations:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(ACQUISITION),
        forecast_operation=register_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=today),
    )
    operations.create(register_revision(in_service=date(in_service_year, 1, 1)), NAME)
    return operations


def _clocks() -> tuple[date, ...]:
    envelope = filing_year_envelope()
    return (
        date(envelope.floor - 3, 6, 30),
        *(date(year, 12, 31) for year in envelope.years),
        date(envelope.horizon + 5, 1, 1),
    )


@pytest.mark.parametrize("in_service_year", filing_year_envelope().years)
def test_the_limits_advisories_and_class_names_do_not_move_with_the_clock(in_service_year: int) -> None:
    readings = []
    for today in _clocks():
        operations = _operations(in_service_year=in_service_year, today=today)
        readings.append(
            (
                operations.plan_limits(_ASSET),
                operations.plan_advisories(_ASSET),
                operations.timeline(_ASSET),
            )
        )

    assert all(reading == readings[0] for reading in readings)
    limits = readings[0][0]
    assert limits.unavailable_reason_key is None
    assert limits.class_key is not None


def test_an_election_that_entered_service_before_the_floor_is_read_under_the_floor_edition() -> None:
    envelope = filing_year_envelope()
    earlier = _operations(in_service_year=envelope.floor - 2, today=date(envelope.horizon, 12, 31))
    at_floor = _operations(in_service_year=envelope.floor, today=date(envelope.horizon, 12, 31))

    assert earlier.plan_limits(_ASSET).unavailable_reason_key is None
    assert earlier.plan_limits(_ASSET).legal_citations == at_floor.plan_limits(_ASSET).legal_citations
