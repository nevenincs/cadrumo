"""A plan row serves whether the year applies and, for an opening-data reason, the field that settles it."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import (
    OPENING_REMEDY_FIELD,
    OPENING_REMEDY_REASON_KEYS,
    TIMELINE_FIELD_PATHS,
    ActivityAssetClaimState,
)
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.application.actividad_asset.schedule_walk import PlanFigureAbsence
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.domain.renta.actividad_asset.election import DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    ActivityAssetRevision,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)

from .ledger_support import MemoryLedger
from .register_support import MemoryRepository, memory_register_authority
from .test_baja_correction import _low_value_forecast, _low_value_revision
from .test_register import _ACQUISITION, _NAME, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ASSET = "laptop-1"


def _free_register() -> ActivityAssetOperations:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=_low_value_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=date(2026, 12, 31)),
    )
    operations.create(_low_value_revision(), _NAME)
    return operations


def test_an_open_free_method_year_reads_as_applicable() -> None:
    row = _free_register().plan(_ASSET)[0]

    assert row.absence is PlanFigureAbsence.FREE_ELECTION
    assert row.claim_state is ActivityAssetClaimState.MISSING
    assert row.claimable_intervals
    assert row.applies is True


def test_a_year_after_the_basis_is_spent_does_not_apply() -> None:
    operations, _ = _operations()
    operations.create(_revision(), _NAME)

    last = operations.plan(_ASSET)[-1]

    assert last.absence is PlanFigureAbsence.BASIS_EXHAUSTED
    assert not last.claimable_intervals
    assert last.applies is False
    assert all(row.applies for row in operations.plan(_ASSET)[:-1])


def test_an_unknown_opening_history_serves_the_field_that_settles_it() -> None:
    base = _revision(in_service=date(2020, 1, 1))
    facts = {name: getattr(base, name) for name in type(base).model_fields}
    facts["opening_history"] = OpeningAmortizationHistory(status=OpeningHistoryStatus.MISSING)
    operations, _ = _operations()
    operations.create(ActivityAssetRevision(**facts), _NAME)

    row = operations.plan(_ASSET)[0]

    assert row.absence_reason_key in OPENING_REMEDY_REASON_KEYS
    assert row.absence_remedy_field_key == f"ledger.actividad_asset.field.{OPENING_REMEDY_FIELD}"
    assert row.claimable_refusal_remedy_field_key == row.absence_remedy_field_key


def test_a_reason_that_is_not_about_opening_data_serves_no_remedy_and_the_served_field_is_worded() -> None:
    row = _free_register().plan(_ASSET)[0]

    assert row.absence_remedy_field_key is None
    assert OPENING_REMEDY_FIELD in TIMELINE_FIELD_PATHS
    assert lookup_translation(f"ledger.actividad_asset.field.{OPENING_REMEDY_FIELD}", locale="en") is not None
    assert all(lookup_translation(key, locale="en") is not None for key in OPENING_REMEDY_REASON_KEYS)


def _unknown_opening_register() -> ActivityAssetOperations:
    base = _revision(in_service=date(2020, 1, 1))
    facts = {name: getattr(base, name) for name in type(base).model_fields}
    facts["opening_history"] = OpeningAmortizationHistory(status=OpeningHistoryStatus.MISSING)
    operations, _ = _operations()
    operations.create(ActivityAssetRevision(**facts), _NAME)
    return operations


def test_a_list_row_with_an_unknown_opening_amount_serves_the_same_remedy_as_the_plan_row() -> None:
    operations = _unknown_opening_register()

    (listed,) = operations.list_elements()

    assert listed.pending is None
    assert listed.opening_remedy_field_key is not None
    assert listed.opening_remedy_field_key == operations.plan(_ASSET)[0].absence_remedy_field_key


def test_a_list_row_with_a_known_opening_amount_serves_no_opening_remedy() -> None:
    operations, _ = _operations()
    operations.create(_revision(), _NAME)

    (listed,) = operations.list_elements()

    assert listed.pending is not None
    assert listed.opening_remedy_field_key is None
