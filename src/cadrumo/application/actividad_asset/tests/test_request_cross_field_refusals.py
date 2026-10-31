"""A request fact that breaks a cross-field rule decodes, and is refused with that rule's reason key and facts.

The request reaches the executor intact; restoring its records raises the registered refusal, which the
executors store through the same refusal projection every other refusal uses.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.actividad_asset.activity_asset_contracts import (
    ActivityAssetCorrectRequest,
    ActivityAssetCreateRequest,
    ActivityAssetFilingHandoffRequest,
    ActivityAssetForecastRequest,
)
from cadrumo.application.actividad_asset.activity_asset_executors import _refusal
from cadrumo.application.actividad_asset.operation_dtos import (
    ActivityAssetCorrectionRevisionSnapshot,
    ActivityAssetRevisionSnapshot,
)
from cadrumo.application.actividad_asset.request_restoration import restoring
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.domain.renta.actividad_asset.election import AcquiredCondition, AmortizationMethod
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetError, ActividadAssetValidationError
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionShape,
    ActivityAssetRevision,
    AssetBasisStage,
    OpeningHistoryStatus,
)
from cadrumo.domain.renta.actividad_asset.register_records import (
    AcquisitionDocumentKind,
    ActivityAssetDescriptorFacts,
)

from .test_register import _NAME, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ERRORS = "ledger.actividad_asset.errors."
_PROFILE = uuid4()


def _broken(**changes: object) -> ActivityAssetRevision:
    """Build a revision with facts that break a rule, which the domain model would refuse to construct."""
    return _revision().model_copy(update=changes)


def _opening(**changes: object) -> ActivityAssetRevision:
    base = _revision()
    return base.model_copy(update={"opening_history": base.opening_history.model_copy(update=changes)})


def _basis(**changes: object) -> ActivityAssetRevision:
    base = _revision()
    return base.model_copy(update={"basis": base.basis.model_copy(update=changes)})


def _election(**changes: object) -> ActivityAssetRevision:
    base = _revision()
    return base.model_copy(update={"amortization": base.amortization.model_copy(update=changes)})


_CASES: dict[str, Callable[[], ActivityAssetRevision]] = {
    "opening_covered_year_requires_amount": lambda: _opening(
        status=OpeningHistoryStatus.KNOWN, accumulated_amount=Decimal("0"), covered_through_tax_year=2022
    ),
    "opening_amount_requires_covered_year": lambda: _opening(
        status=OpeningHistoryStatus.KNOWN, accumulated_amount=Decimal("3000"), covered_through_tax_year=None
    ),
    "opening_known_requires_amount": lambda: _opening(status=OpeningHistoryStatus.KNOWN, accumulated_amount=None),
    "opening_missing_states_nothing": lambda: _opening(
        status=OpeningHistoryStatus.MISSING, accumulated_amount=Decimal("5")
    ),
    "basis_stage_refuses_fact": lambda: _basis(stage=AssetBasisStage.TAXPAYER_OWNED, business_use_share=Decimal("1")),
    "basis_amount_not_positive": lambda: _basis(basis_amount=Decimal("0")),
    "basis_share_out_of_range": lambda: _basis(
        stage=AssetBasisStage.TAXPAYER_OWNED, prior_allocation_provenance=None, business_use_share=Decimal("0")
    ),
    "revision_first_cannot_supersede": lambda: _broken(supersedes_revision_id="a" * 64),
    "revision_requires_superseded": lambda: _broken(revision_number=2),
    "building_construction_date_requires_used_asset": lambda: _broken(
        acquired_condition=AcquiredCondition.NEW, building_construction_date=date(2000, 1, 1)
    ),
    "building_construction_date_after_service": lambda: _broken(
        acquired_condition=AcquiredCondition.USED, building_construction_date=date(2090, 1, 1)
    ),
    "residual_value_not_below_basis": lambda: _broken(residual_value=Decimal("999999")),
    "acquisition_shape_not_registerable": lambda: _broken(acquisition_shape=AcquisitionShape.SPLIT_PAYMENT),
    "election_fact_not_of_method": lambda: _election(
        method=AmortizationMethod.CONSTANT_PERCENTAGE, shift_hours_per_day=Decimal("8")
    ),
}


@pytest.mark.parametrize("key", sorted(_CASES))
def test_a_broken_cross_field_rule_decodes_and_is_refused_with_its_reason_key(key: str) -> None:
    snapshot = ActivityAssetRevisionSnapshot.from_domain(_CASES[key]())
    request = ActivityAssetCreateRequest(
        profile_id=_PROFILE, revision=snapshot, descriptor=ActivityAssetDescriptorFacts(name="Element")
    )

    with pytest.raises(ActividadAssetError) as refused:
        request.revision.to_domain()

    refusal = _refusal(refused.value)
    assert refusal is not None
    assert refusal.reason_key == _ERRORS + key


def test_the_zero_opening_amount_with_a_covered_year_is_refused_with_the_field_it_concerns() -> None:
    refused = _refused(_CASES["opening_covered_year_requires_amount"]())

    refusal = _refusal(refused)
    assert refusal is not None
    assert refusal.reason_facts == {"field": "covered_through_tax_year"}


def test_a_correction_states_the_same_refusals() -> None:
    snapshot = ActivityAssetCorrectionRevisionSnapshot.model_validate(
        ActivityAssetRevisionSnapshot.from_domain(
            _CASES["building_construction_date_requires_used_asset"]()
        ).model_dump()
        | {"disposal": None}
    )
    request = ActivityAssetCorrectRequest(profile_id=_PROFILE, revision=snapshot)

    with pytest.raises(ActividadAssetValidationError, match="building_construction_date_requires_used_asset"):
        request.revision.to_domain(revision_number=1)


def _refused(revision: ActivityAssetRevision) -> ActividadAssetError:
    with pytest.raises(ActividadAssetError) as refused:
        ActivityAssetRevisionSnapshot.from_domain(revision).to_domain()
    return refused.value


def test_a_document_kind_without_its_number_is_refused_when_the_descriptor_is_written() -> None:
    operations, _ = _operations()
    operations.create(_revision(), _NAME)
    lopsided = ActivityAssetDescriptorFacts(name="Element").model_copy(
        update={"document_kind": next(iter(AcquisitionDocumentKind))}
    )

    with pytest.raises(ActividadAssetValidationError, match="document_number_and_kind_together") as refused:
        operations.describe("laptop-1", lopsided)

    refusal = _refusal(refused.value)
    assert refusal is not None
    assert refusal.reason_facts == {"field": "document_number"}


def test_a_forecast_interval_that_cannot_be_settled_is_refused_with_its_own_reason() -> None:
    def interval(**ends: str | None) -> ActivityAssetForecastRequest:
        return ActivityAssetForecastRequest.model_validate_json(
            json.dumps({"profile_id": str(_PROFILE), "asset_id": "laptop-1", "covered_from": "2025-01-01", **ends})
        )

    expected = {
        "forecast_interval_end_required": interval(),
        "covered_through_has_no_boundary": interval(covered_through="9999-12-31"),
        "covered_through_not_day_before_until": interval(covered_until="2025-07-01", covered_through="2025-06-29"),
    }
    for key, request in expected.items():
        with pytest.raises(ActividadAssetValidationError, match=key) as refused:
            request.exclusive_end()
        refusal = _refusal(refused.value)
        assert refusal is not None
        assert refusal.reason_key == _ERRORS + key


def test_a_period_that_is_not_one_of_the_tax_year_is_refused_with_its_reason() -> None:
    request = ActivityAssetFilingHandoffRequest.model_validate_json(
        json.dumps({"profile_id": str(_PROFILE), "tax_year": 2025, "m130_period": "9T"})
    )

    with pytest.raises(ActividadAssetValidationError, match="m130_period_invalid") as refused:
        request.requested_period()

    refusal = _refusal(refused.value)
    assert refusal is not None
    assert refusal.reason_facts == {"field": "m130_period"}


def test_a_fault_no_rule_words_is_still_refused_with_a_reason_key_and_its_field() -> None:
    snapshot = ActivityAssetRevisionSnapshot.from_domain(_revision())
    broken = snapshot.model_copy(update={"asset_id": "   "})

    with pytest.raises(ActividadAssetValidationError) as refused:
        broken.to_domain()

    refusal = _refusal(refused.value)
    assert refusal is not None
    assert refusal.reason_key == _ERRORS + "request_record_invalid"
    assert refusal.reason_facts == {"field": "asset_id"}


def test_restoring_passes_a_result_through() -> None:
    assert restoring(lambda: 3) == 3


def test_every_reason_key_the_domain_rules_raise_is_worded_in_all_four_locales() -> None:
    sources = Path(__file__).resolve().parents[3] / "domain" / "renta" / "actividad_asset"
    keys = {
        key
        for path in sources.glob("*.py")
        for key in re.findall(r"ledger\.actividad_asset\.errors\.([a-z0-9_]+)", path.read_text(encoding="utf-8"))
    }
    keys.add("request_record_invalid")

    assert keys
    for key in sorted(keys):
        english = lookup_translation(_ERRORS + key, locale="en")
        assert english is not None and english != "", key
        for locale in ("es", "ca", "hu"):
            assert lookup_translation(_ERRORS + key, locale=locale) not in {None, ""}, (key, locale)
