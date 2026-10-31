"""A fresh forecast of a recorded claim's figures under a newer authority generation is a replay.

Figures use 2,000.00 at 26% linear from 1 January 2025: 520.00 a full year.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.domain.renta.actividad_asset.election import DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from cadrumo.domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduledAmortizationCharge,
)

from .ledger_support import MemoryLedger, acquisition_transaction
from .operations_support import build_forecast, build_revision
from .register_support import MemoryRepository, memory_register_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ASSET = "laptop-1"


class _Generations:
    """The register test forecast, stamped with a generation the test moves between forecasts."""

    def __init__(self) -> None:
        self.generation = "generation-1"

    def __call__(
        self,
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None = None,
    ) -> ScheduledAmortizationCharge:
        charge = build_forecast(
            revision,
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            requested_free_amount=requested_free_amount,
        )
        return charge.model_copy(update={"authority_generation": self.generation})


def _register() -> tuple[ActivityAssetOperations, MemoryRepository, _Generations]:
    generations = _Generations()
    repository = MemoryRepository()
    operations = ActivityAssetOperations(
        repository=repository,
        ledger=MemoryLedger(acquisition_transaction()),
        forecast_operation=generations,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(),
    )
    operations.create(build_revision(), ActivityAssetDescriptorFacts(name="Office laptop"))
    return operations, repository, generations


def _year_2025(operations: ActivityAssetOperations) -> ScheduledAmortizationCharge:
    return operations.forecast(asset_id=_ASSET, covered_from=date(2025, 1, 1), covered_until=date(2026, 1, 1))


def test_a_new_generation_forecast_of_the_same_figures_returns_the_recorded_claim_and_writes_nothing() -> None:
    operations, repository, generations = _register()
    first = operations.record_claim(_year_2025(operations), creating_operation="test.first")
    before = repository.history
    generations.generation = "generation-2"

    again = operations.record_claim(_year_2025(operations), creating_operation="test.again")

    assert again.reused_existing_claim
    assert again.claim.claim_id == first.claim.claim_id
    assert again.claim.authority_generation == "generation-1"
    assert repository.history == before


def test_a_voluntary_supersession_under_a_new_generation_adds_no_claim_when_the_figures_are_equal() -> None:
    operations, repository, generations = _register()
    first = operations.record_claim(_year_2025(operations), creating_operation="test.first")
    before = repository.history
    generations.generation = "generation-2"

    again = operations.record_claim(
        _year_2025(operations),
        creating_operation="test.supersede",
        supersedes_claim_id=first.claim.claim_id,
    )

    assert again.reused_existing_claim
    assert again.claim.claim_id == first.claim.claim_id
    assert repository.history == before
    (row,) = (row for row in operations.plan(_ASSET) if row.tax_year == 2025)
    assert [claim.matches_current_schedule for claim in row.claims] == [True]
