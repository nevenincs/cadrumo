"""Direct ``IvaLedgerCandidate`` validation and binding contracts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....domain.bienes_inversion.register import BienesInversionIvaRegister
from ....domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_references import PeriodSelector
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.flow import IvaFlowDirection
from ....domain.iva.schema import (
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from .. import (
    AggregationValidationError,
    IvaLedgerCandidate,
    aggregate_iva_ledger_candidate_bindings,
    aggregate_iva_ledger_candidates,
    validate_iva_ledger_observation,
)
from ._renta_income_aggregation_support import _period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_Q2_2026 = _period(2026, "2T")


def _intra_eu_deduction_provenance(locator: str) -> IvaDeductionClassificationProvenance:
    return IvaDeductionClassificationProvenance(
        authority=IvaDeductionEvidenceAuthority.INTRA_EU_SELF_ASSESSMENT,
        source_locator=locator,
        evidence_digest="c" * 64,
    )


def _iva_binding(
    binding_id: str,
    *,
    categories: tuple[IvaCategory, ...],
    rate_kinds: tuple[IvaRateKind, ...],
    flow_direction: IvaFlowDirection,
) -> DataBindingDefinition:
    return DataBindingDefinition(
        id=binding_id,
        source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        selector={
            "categories": categories,
            "rate_kinds": rate_kinds,
            "flow_direction": flow_direction,
            "observation_roles": (IvaLedgerObservationRole.SETTLEMENT,),
            "cash_accounting_treatments": (
                IvaCashAccountingTreatment.NONE,
                IvaCashAccountingTreatment.TAXPAYER_REGIME,
                IvaCashAccountingTreatment.SUPPLIER_REGIME,
            ),
            "fact": "iva_amount_sum",
        },
        aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
        legal_refs=("ley-37-1992:art-88",),
        source_refs=("test-iva-ledger-binding",),
    )


def _revision_with_iva_bindings(revision_id: str, *bindings: DataBindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id=revision_id,
        localization_key=f"test.schema.revision.{revision_id}.label",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(year_from=2026, periods=("1T", "2T", "3T", "4T", "0A")),
        legal_refs=("ley-37-1992:art-88",),
        source_refs=("test-iva-ledger-binding",),
        bindings=bindings,
    )


def _modelo_309_iva_revision() -> ModeloRevision:
    return _revision_with_iva_bindings(
        "2004-y-siguientes",
        _iva_binding(
            "modelo-309-iva-autorepercutido-intracomunitaria-cuota",
            categories=(IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,),
            rate_kinds=(IvaRateKind.GENERAL, IvaRateKind.REDUCED, IvaRateKind.SUPER_REDUCED),
            flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        ),
        _iva_binding(
            "modelo-309-iva-soportado-recargo-equivalencia-cuota",
            categories=(IvaCategory.RECARGO_EQUIVALENCIA,),
            rate_kinds=(IvaRateKind.GENERAL, IvaRateKind.REDUCED, IvaRateKind.SUPER_REDUCED),
            flow_direction=IvaFlowDirection.SOPORTADO,
        ),
    )


def _modelo_390_without_recargo_revision() -> ModeloRevision:
    return _revision_with_iva_bindings(
        "2010-y-siguientes",
        _iva_binding(
            "modelo-390-iva-repercutido-general-cuota",
            categories=(IvaCategory.DOMESTIC_GENERAL,),
            rate_kinds=(IvaRateKind.GENERAL,),
            flow_direction=IvaFlowDirection.REPERCUTIDO,
        ),
    )


def test_preclassified_candidate_preserves_exemption_article_on_observation_projection() -> None:
    candidate = IvaLedgerCandidate(
        ledger_id="art-20-8-candidate",
        transaction_date=date(2026, 4, 10),
        category=IvaCategory.DOMESTIC_EXEMPT,
        exemption_article=IvaExemptionArticle.ART_20_UNO_8,
        rate_kind=IvaRateKind.EXEMPT,
        flow_direction=IvaFlowDirection.REPERCUTIDO,
        base_amount=Decimal("400.00"),
        iva_amount=Decimal("0.00"),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )

    observation = validate_iva_ledger_observation(candidate)
    aggregation = aggregate_iva_ledger_candidates(
        (candidate,),
        period=_Q2_2026,
        ledger_profile_id="test-profile",
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id="test-profile",
    )

    assert observation.exemption_article is IvaExemptionArticle.ART_20_UNO_8
    assert aggregation.issues == ()
    assert aggregation.observations == (observation,)


def test_preclassified_candidates_cover_non_domestic_exempt_recargo_and_adjustments() -> None:
    candidates = (
        IvaLedgerCandidate(
            ledger_id="exempt-consulting",
            transaction_date=date(2026, 4, 10),
            category=IvaCategory.DOMESTIC_EXEMPT,
            rate_kind=IvaRateKind.EXEMPT,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("400.00"),
            iva_amount=Decimal("0.00"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerCandidate(
            ledger_id="eu-acquisition",
            transaction_date=date(2026, 4, 11),
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
            deduction_provenance=_intra_eu_deduction_provenance("test:eu-acquisition"),
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            base_amount=Decimal("200.00"),
            iva_amount=Decimal("42.00"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerCandidate(
            ledger_id="retail-recargo",
            transaction_date=date(2026, 4, 12),
            category=IvaCategory.RECARGO_EQUIVALENCIA,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.SOPORTADO,
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("5.20"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerCandidate(
            ledger_id="prior-period-adjustment",
            transaction_date=date(2026, 4, 13),
            category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
            rate_kind=IvaRateKind.ZERO,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("-50.00"),
            iva_amount=Decimal("0.00"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
    )

    result = aggregate_iva_ledger_candidates(
        candidates,
        period=_Q2_2026,
        ledger_profile_id="test-profile",
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id="test-profile",
    )

    assert result.issues == ()
    assert [observation.category for observation in result.observations] == [
        IvaCategory.DOMESTIC_EXEMPT,
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        IvaCategory.RECARGO_EQUIVALENCIA,
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
    ]
    assert result.observations[-1].base_amount == Decimal("-50.00")


def test_preclassified_candidates_feed_modelo_309_recargo_and_reverse_charge_bindings() -> None:
    revision = _modelo_309_iva_revision()
    candidates = (
        IvaLedgerCandidate(
            ledger_id="eu-acquisition",
            transaction_date=date(2026, 4, 11),
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
            deduction_provenance=_intra_eu_deduction_provenance("test:eu-acquisition-binding"),
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            base_amount=Decimal("200.00"),
            iva_amount=Decimal("42.00"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerCandidate(
            ledger_id="retail-recargo",
            transaction_date=date(2026, 4, 12),
            category=IvaCategory.RECARGO_EQUIVALENCIA,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.SOPORTADO,
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("5.20"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
    )

    binding_values = aggregate_iva_ledger_candidate_bindings(
        revision,
        candidates,
        period=_Q2_2026,
        ledger_profile_id="test-profile",
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id="test-profile",
    )

    assert binding_values["modelo-309-iva-autorepercutido-intracomunitaria-cuota"] == Decimal("42.00")
    assert binding_values["modelo-309-iva-soportado-recargo-equivalencia-cuota"] == Decimal("5.20")


def test_preclassified_candidate_blocks_unsupported_modelo_390_regime() -> None:
    revision = _modelo_390_without_recargo_revision()
    candidate = IvaLedgerCandidate(
        ledger_id="retail-recargo",
        transaction_date=date(2026, 4, 12),
        category=IvaCategory.RECARGO_EQUIVALENCIA,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.SOPORTADO,
        base_amount=Decimal("100.00"),
        iva_amount=Decimal("5.20"),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )

    with pytest.raises(AggregationValidationError, match="unsupported_iva_category") as exc_info:
        aggregate_iva_ledger_candidate_bindings(
            revision,
            (candidate,),
            period=_Q2_2026,
            ledger_profile_id="test-profile",
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id="test-profile",
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["ledger_id"] == "retail-recargo"
    assert exc_info.value.context["category"] == IvaCategory.RECARGO_EQUIVALENCIA.value
    assert exc_info.value.context["revision_id"] == "2010-y-siguientes"


def test_preclassified_candidate_rejects_non_declarable_sentinel_category() -> None:
    candidate = IvaLedgerCandidate(
        ledger_id="unknown-row",
        transaction_date=date(2026, 4, 10),
        category=IvaCategory.UNKNOWN,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.REPERCUTIDO,
        base_amount=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )

    with pytest.raises(AggregationValidationError, match="unsupported_iva_category"):
        validate_iva_ledger_observation(candidate)


def test_preclassified_candidate_outside_period_blocks_binding_resolution() -> None:
    revision = _modelo_309_iva_revision()
    candidate = IvaLedgerCandidate(
        ledger_id="late-row",
        transaction_date=date(2026, 7, 1),
        category=IvaCategory.RECARGO_EQUIVALENCIA,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.SOPORTADO,
        base_amount=Decimal("100.00"),
        iva_amount=Decimal("5.20"),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )

    with pytest.raises(AggregationValidationError, match="candidate_outside_period"):
        aggregate_iva_ledger_candidate_bindings(
            revision,
            (candidate,),
            period=_Q2_2026,
            ledger_profile_id="test-profile",
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id="test-profile",
        )
