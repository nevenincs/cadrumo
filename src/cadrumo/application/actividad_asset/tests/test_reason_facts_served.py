"""A refusal the register serves for the plan and the election limits carries the facts that word it.

The catalogue entry for a year no edition covers states the year, so a reason key served alone
would render with its placeholder showing.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import (
    ActivityAssetClaimState,
    ActivityAssetReasonFact,
    project_reason_facts,
)
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.application.actividad_asset.ports import ActivityAssetForecastOperation
from cadrumo.core.i18n.render import tr
from cadrumo.domain.renta.actividad_asset.election import AmortizationMethod, DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetUnsupportedError, PercentFact
from cadrumo.domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from cadrumo.domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge

from .ledger_support import MemoryLedger
from .register_support import MemoryRepository, memory_register_authority
from .test_claim_years_and_replay import _constant_forecast
from .test_register import _ACQUISITION, _NAME, _forecast, _full_year, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ASSET = "laptop-1"
_NO_EDITION = "ledger.actividad_asset.errors.tax_year_without_edition"


def _stated(facts: tuple[ActivityAssetReasonFact, ...]) -> dict[str, str]:
    return {fact.key: fact.value for fact in facts}


def test_the_election_limits_of_a_year_no_edition_covers_state_the_year_that_words_the_reason() -> None:
    operations, _ = _operations(today=date(2021, 6, 30))
    operations.create(_revision(in_service=date(2020, 1, 1)), _NAME)

    limits = operations.plan_limits(_ASSET)

    key = limits.unavailable_reason_key
    assert key == _NO_EDITION
    assert _stated(limits.unavailable_reason_facts) == {"tax_year": "2021"}
    rendered = tr(key, **_stated(limits.unavailable_reason_facts))
    assert "2021" in rendered
    assert "{" not in rendered


def test_the_election_limits_of_a_year_with_an_edition_state_no_reason() -> None:
    operations, _ = _operations()
    operations.create(_revision(), _NAME)

    limits = operations.plan_limits(_ASSET)

    assert limits.unavailable_reason_key is None
    assert limits.unavailable_reason_facts == ()


def _without_edition_after_2026(
    revision: ActivityAssetRevision,
    *,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None = None,
) -> ScheduledAmortizationCharge:
    if covered_from.year > 2026:
        raise ActividadAssetUnsupportedError(
            context={"tax_year": covered_from.year},
            translated_message=_NO_EDITION,
        )
    return _forecast(
        revision,
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


def _register(forecast: ActivityAssetForecastOperation, revision: ActivityAssetRevision) -> ActivityAssetOperations:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=date(2028, 12, 31), last_admitted_year=2028),
    )
    operations.create(revision, _NAME)
    return operations


def test_a_year_the_plan_cannot_figure_serves_its_refusal_with_the_facts_the_absence_carries() -> None:
    operations = _register(_without_edition_after_2026, _revision())

    row = {item.tax_year: item for item in operations.plan(_ASSET)}[2027]

    assert row.claimable_refusal_key == row.absence_reason_key == _NO_EDITION
    key = row.claimable_refusal_key
    assert key is not None
    assert _stated(row.claimable_refusal_facts) == _stated(row.absence_reason_facts) == {"tax_year": "2027"}
    assert "2027" in tr(key, **_stated(row.claimable_refusal_facts))


def test_a_method_refusal_for_a_missing_year_serves_the_method_that_words_it() -> None:
    operations = _register(_constant_forecast, _revision(method=AmortizationMethod.CONSTANT_PERCENTAGE))
    operations.record_claim(_full_year(operations, 2027), creating_operation="test.2027")

    row = {item.tax_year: item for item in operations.plan(_ASSET)}[2025]

    assert row.claim_state is ActivityAssetClaimState.MISSING
    assert row.claimable_intervals == ()
    assert row.claimable_refusal_key == "ledger.actividad_asset.errors.earlier_year_depends_on_pending_value"
    key = row.claimable_refusal_key
    assert _stated(row.claimable_refusal_facts) == {"method": "constant_percentage"}
    assert "{" not in tr(key, **_stated(row.claimable_refusal_facts))


def test_each_fact_states_the_kind_it_was_raised_with() -> None:
    facts = project_reason_facts(
        {
            "on": date(2026, 6, 30),
            "paid": Decimal("1234.50"),
            "elected": PercentFact("0.16"),
            "months": 7,
            "method": "linear",
        },
    )

    assert [(fact.key, fact.value, fact.kind.value) for fact in facts] == [
        ("elected", "0.16", "percent"),
        ("method", "linear", "text"),
        ("months", "7", "count"),
        ("on", "2026-06-30", "date"),
        ("paid", "1234.50", "amount"),
    ]


def test_a_refusal_projects_the_kinds_its_context_was_raised_with() -> None:
    operations = _register(_without_edition_after_2026, _revision())

    row = {item.tax_year: item for item in operations.plan(_ASSET)}[2027]

    assert [(fact.key, fact.kind.value) for fact in row.claimable_refusal_facts] == [("tax_year", "count")]
