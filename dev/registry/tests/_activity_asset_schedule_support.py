"""Shared builders for the activity asset schedule authority tests."""

from __future__ import annotations

import re
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from functools import cache

import pytest
from pydantic import ValidationError

from cadrumo.application.actividad_asset.tests.ledger_support import acquisition_transaction
from cadrumo.application.calculations.actividad_asset_schedule import forecast_activity_asset_charge
from cadrumo.core.errors.error_codes import resolve_error_message
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import LegalReference
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
    SmallEnterpriseEvidence,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from cadrumo.domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduledAmortizationCharge,
)
from cadrumo.domain.renta.actividad_asset.vehicle_affectation import (
    VehicleAffectation,
)
from cadrumo.domain.transactions.models import Transaction
from cadrumo.domain.user_profile.plantilla_media import PlantillaMediaYear

from ..compiler.loader import load_modelo_directory, load_shared_catalogues

_ERRORS = "ledger.actividad_asset.errors."


@contextmanager
def _refused(
    error_type: type[Exception],
    key: str,
    *,
    rendered: str | None = None,
    **context: object,
) -> Generator[None]:
    """Expect a refusal that carries catalogue ``key`` and the named context facts.

    ``rendered`` additionally matches the English text the catalogue produces for
    the refusal, so a legal citation the message must keep is still asserted.
    """
    with pytest.raises((error_type, ValidationError)) as caught:
        yield
    error = caught.value
    if isinstance(error, ValidationError):
        details = error.errors()
        assert len(details) == 1
        wrapper = details[0].get("ctx", {}).get("error")
        assert isinstance(wrapper, ValueError)
        error = wrapper.__cause__
        assert isinstance(error, error_type)
    assert getattr(error, "translated_message", None) == _ERRORS + key
    recorded = getattr(error, "context", None) or {}
    for name, value in context.items():
        assert recorded.get(name) == value, (name, recorded)
    if rendered is not None:
        assert re.search(rendered, resolve_error_message(error, locale="en")), rendered


@cache
def _acquisition() -> Transaction:
    """One payment large enough to bear every asset the tests register; the check bounds, not equates."""
    return acquisition_transaction(amount=Decimal("10000000.00"), taxable_base=None, iva_amount=None)


_YEAR_START = date(2025, 1, 1)


_YEAR_END = date(2026, 1, 1)


_DESCRIPTOR = ActivityAssetDescriptorFacts(name="Published-authority element")


_NORMAL = DirectEstimationRegime.NORMAL


_SIMPLIFIED = DirectEstimationRegime.SIMPLIFIED


def _modelo_100() -> ModeloRevision:
    return load_modelo_directory(bundled_path("registry", "aeat", "modelos", "100")).revisions["2025"]


def _legal_reference(reference_id: str) -> LegalReference:
    return load_shared_catalogues(bundled_path("registry", "aeat")).legal[reference_id]


def _election(
    method: AmortizationMethod,
    regime: DirectEstimationRegime = _NORMAL,
    **facts: object,
) -> ActivityAssetAmortizationElection:
    return ActivityAssetAmortizationElection.model_validate({"regime": regime, "method": method, **facts})


def _asset(
    election: ActivityAssetAmortizationElection,
    *,
    basis: str,
    kind: AssetKind = AssetKind.MATERIAL,
    in_service: date = _YEAR_START,
    condition: AcquiredCondition = AcquiredCondition.NEW,
    residual: str = "0",
    opening: str = "0",
    opening_through: int | None = None,
    opening_method: AmortizationMethod | None = None,
    built: date | None = None,
    asset_id: str = "asset",
    vehicle: VehicleAffectation | None = None,
) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id=_acquisition().transaction_id,
            invoice_evidence_id=f"invoice-{asset_id}",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=kind,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal(basis),
            non_deductible_iva=Decimal("0"),
            prior_allocation_provenance="reviewed business allocation",
        ),
        residual_value=Decimal(residual),
        in_service_date=in_service,
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal(opening),
            amortization_method=opening_method,
            covered_through_tax_year=(opening_through or in_service.year) if Decimal(opening) else None,
        ),
        acquired_condition=condition,
        building_construction_date=built,
        amortization=election,
        vehicle_affectation=vehicle,
    )


def _charge(
    asset: ActivityAssetRevision,
    *,
    covered_from: date = _YEAR_START,
    covered_until: date = _YEAR_END,
    history: AssetScheduleHistory | None = None,
    free_amount: str | None = None,
    workforce: tuple[PlantillaMediaYear, ...] = (),
) -> ScheduledAmortizationCharge:
    return forecast_activity_asset_charge(
        asset,
        modelo_100_revision=_modelo_100(),
        authority_generation="candidate-source",
        covered_from=covered_from,
        covered_until=covered_until,
        history=history or AssetScheduleHistory(),
        taxpayer_workforce=lambda: workforce,
        legal_reference=_legal_reference,
        requested_free_amount=Decimal(free_amount) if free_amount is not None else None,
    )


def _linear(class_key: str, regime: DirectEstimationRegime = _NORMAL, **facts: object):
    return _election(AmortizationMethod.LINEAR, regime, authority_class_key=class_key, **facts)


def _small_enterprise(turnover: str, made_available: date = date(2025, 11, 15)) -> SmallEnterpriseEvidence:
    return SmallEnterpriseEvidence(
        evidence_reference="prior-year-accounts",
        made_available_on=made_available,
        prior_period_net_turnover=Decimal(turnover),
    )


def _constant(class_key: str, coefficient: str | None = None, regime: DirectEstimationRegime = _NORMAL):
    facts: dict[str, object] = {"authority_class_key": class_key}
    if coefficient is not None:
        facts["linear_coefficient"] = Decimal(coefficient)
    return _election(AmortizationMethod.CONSTANT_PERCENTAGE, regime, **facts)
