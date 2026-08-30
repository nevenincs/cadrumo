"""Real validation coverage for the differentiated-sector deduction taxonomy."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest

from ....core import IvaDeductionEvidenceAuthority, IvaDeductionFactKind, Period
from ....domain.bienes_inversion import (
    BienesInversionIvaRegister,
    BienInversionIvaRecord,
    BienInversionKind,
)
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.flow import IvaFlowDirection
from ....domain.iva.schema import IvaCategory, IvaLedgerObservationRole, IvaRateKind
from .. import IvaLedgerCandidate, aggregate_iva_ledger_candidates, validate_iva_ledger_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _invoice_provenance(locator: str) -> IvaDeductionClassificationProvenance:
    return IvaDeductionClassificationProvenance(
        authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
        source_locator=locator,
        evidence_digest="a" * 64,
    )


def _domestic_current_candidate() -> IvaLedgerCandidate:
    return IvaLedgerCandidate(
        ledger_id="current-purchase",
        transaction_date=date(2026, 4, 10),
        category=IvaCategory.DOMESTIC_GENERAL,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.SOPORTADO,
        base_amount=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
        deduction_provenance=_invoice_provenance("invoice:purchase-2026-001"),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def test_candidate_freeze_preserves_exact_deduction_authority_losslessly() -> None:
    candidate = _domestic_current_candidate()

    observation = validate_iva_ledger_observation(candidate)

    assert observation.deduction_fact_kind is IvaDeductionFactKind.DOMESTIC_CURRENT
    assert observation.deduction_provenance == candidate.deduction_provenance
    assert observation.investment_asset_id is None
    assert observation.rectifies_ledger_id is None


def test_investment_kind_requires_an_asset_and_current_kind_forbids_one() -> None:
    payload = _domestic_current_candidate().model_dump()
    payload["deduction_fact_kind"] = IvaDeductionFactKind.DOMESTIC_INVESTMENT
    with pytest.raises(ValueError, match="requires investment_asset_id"):
        IvaLedgerCandidate.model_validate(payload)

    payload["deduction_fact_kind"] = IvaDeductionFactKind.DOMESTIC_CURRENT
    payload["investment_asset_id"] = "asset-001"
    with pytest.raises(ValueError, match="cannot carry investment_asset_id"):
        IvaLedgerCandidate.model_validate(payload)


def test_signed_rectification_with_one_corrected_fact_is_accepted_once() -> None:
    rectification = IvaLedgerCandidate(
        ledger_id="rectification-001",
        transaction_date=date(2026, 4, 11),
        category=IvaCategory.DOMESTIC_GENERAL,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.SOPORTADO,
        base_amount=Decimal("-100.00"),
        iva_amount=Decimal("-21.00"),
        deduction_fact_kind=IvaDeductionFactKind.RECTIFICATION,
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.RECTIFICATION_EVIDENCE,
            source_locator="invoice-rectification:2026-001",
            evidence_digest="b" * 64,
        ),
        rectifies_ledger_id="current-purchase",
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )

    aggregation = aggregate_iva_ledger_candidates(
        (rectification,),
        period=Period.from_year_and_code(2026, "2T"),
        ledger_profile_id="profile-a",
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id="profile-a",
    )

    assert aggregation.observations[0].iva_amount == Decimal("-21.00")
    with pytest.raises(ValueError, match=r"aggregation\.iva_ledger\.errors\.rectification_consumed_more_than_once"):
        aggregate_iva_ledger_candidates(
            (rectification, rectification.model_copy(update={"ledger_id": "rectification-002"})),
            period=Period.from_year_and_code(2026, "2T"),
            ledger_profile_id="profile-a",
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id="profile-a",
        )


@pytest.mark.parametrize(
    ("category", "flow"),
    (
        (IvaCategory.IMPORT_THIRD_COUNTRY, IvaFlowDirection.SOPORTADO),
        (
            IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        ),
    ),
)
def test_rectification_preserves_the_corrected_import_or_intra_eu_legal_axes(
    category: IvaCategory,
    flow: IvaFlowDirection,
) -> None:
    candidate = IvaLedgerCandidate(
        ledger_id=f"rectification-{category.value}",
        transaction_date=date(2026, 4, 11),
        category=category,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=flow,
        base_amount=Decimal("-100.00"),
        iva_amount=Decimal("-21.00"),
        deduction_fact_kind=IvaDeductionFactKind.RECTIFICATION,
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.RECTIFICATION_EVIDENCE,
            source_locator=f"rectification:{category.value}",
            evidence_digest="c" * 64,
        ),
        rectifies_ledger_id="corrected-source",
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )

    assert validate_iva_ledger_observation(candidate).category is category


def test_rectification_refuses_category_flow_mismatch_and_exempt_rate() -> None:
    payload = {
        "ledger_id": "rectification-invalid",
        "transaction_date": date(2026, 4, 11),
        "category": IvaCategory.IMPORT_THIRD_COUNTRY,
        "rate_kind": IvaRateKind.GENERAL,
        "flow_direction": IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        "base_amount": Decimal("-100.00"),
        "iva_amount": Decimal("-21.00"),
        "observation_role": IvaLedgerObservationRole.SETTLEMENT,
        "deduction_fact_kind": IvaDeductionFactKind.RECTIFICATION,
        "deduction_provenance": IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.RECTIFICATION_EVIDENCE,
            source_locator="rectification:invalid",
            evidence_digest="d" * 64,
        ),
        "rectifies_ledger_id": "corrected-source",
    }
    with pytest.raises(ValueError, match="category and input IVA flow"):
        IvaLedgerCandidate.model_validate(payload)
    payload["flow_direction"] = IvaFlowDirection.SOPORTADO
    payload["rate_kind"] = IvaRateKind.EXEMPT
    with pytest.raises(ValueError, match="cannot use the exempt rate tier"):
        IvaLedgerCandidate.model_validate(payload)


def test_reagp_requires_its_exact_category_flow_and_rate_axes() -> None:
    payload = {
        "ledger_id": "reagp-001",
        "transaction_date": date(2026, 4, 11),
        "category": IvaCategory.REAGP_COMPENSATION,
        "rate_kind": IvaRateKind.EXEMPT,
        "flow_direction": IvaFlowDirection.SOPORTADO,
        "base_amount": Decimal("100.00"),
        "iva_amount": Decimal("12.00"),
        "observation_role": IvaLedgerObservationRole.SETTLEMENT,
        "deduction_fact_kind": IvaDeductionFactKind.REAGP_COMPENSATION,
        "deduction_provenance": IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.REAGP_RECEIPT,
            source_locator="reagp-receipt:001",
            evidence_digest="e" * 64,
        ),
    }
    assert IvaLedgerCandidate.model_validate(payload).category is IvaCategory.REAGP_COMPENSATION
    payload["category"] = IvaCategory.REGIMEN_SIMPLIFICADO
    with pytest.raises(ValueError, match="closed compensation category"):
        IvaLedgerCandidate.model_validate(payload)


def _investment_candidate(*, ledger_id: str, asset_id: str, sector_id: str) -> IvaLedgerCandidate:
    return IvaLedgerCandidate(
        ledger_id=ledger_id,
        transaction_date=date(2026, 4, 10),
        category=IvaCategory.DOMESTIC_GENERAL,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.SOPORTADO,
        base_amount=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
        deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_INVESTMENT,
        deduction_provenance=_invoice_provenance(f"invoice:{ledger_id}"),
        investment_asset_id=asset_id,
        prorrata_sector_id=sector_id,
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _investment_record(*, ledger_id: str, asset_id: str, sector_id: str) -> BienInversionIvaRecord:
    return BienInversionIvaRecord(
        identifier=asset_id,
        description=f"Asset {asset_id}",
        acquisition_year=2026,
        cuota_soportada=Decimal("210.00"),
        prorrata_inicial_pct=Decimal("100"),
        kind=BienInversionKind.MUEBLE,
        acquisition_ledger_id=ledger_id,
        prorrata_sector_id=sector_id,
    )


def test_production_candidate_aggregation_requires_and_accepts_exact_reciprocal_asset_authority() -> None:
    candidate = _investment_candidate(ledger_id="ledger-machine", asset_id="asset-machine", sector_id="sector-a")
    register = BienesInversionIvaRegister(
        records=(_investment_record(ledger_id="ledger-machine", asset_id="asset-machine", sector_id="sector-a"),)
    )

    with pytest.raises(TypeError, match="investment_asset_register"):
        cast(Any, aggregate_iva_ledger_candidates)((candidate,), period=Period.from_year_and_code(2026, "2T"))

    result = aggregate_iva_ledger_candidates(
        (candidate,),
        period=Period.from_year_and_code(2026, "2T"),
        ledger_profile_id="profile-a",
        investment_asset_register=register,
        investment_asset_profile_id="profile-a",
    )
    assert result.observations[0].investment_asset_id == "asset-machine"


def test_production_candidate_aggregation_refuses_an_unobserved_filing_year_asset() -> None:
    candidate = _investment_candidate(ledger_id="ledger-machine", asset_id="asset-machine", sector_id="sector-a")
    register = BienesInversionIvaRegister(
        records=(
            _investment_record(ledger_id="ledger-machine", asset_id="asset-machine", sector_id="sector-a"),
            _investment_record(ledger_id="ledger-vehicle", asset_id="asset-vehicle", sector_id="sector-b"),
        )
    )

    with pytest.raises(ValueError, match="asset-vehicle"):
        aggregate_iva_ledger_candidates(
            (candidate,),
            period=Period.from_year_and_code(2026, "2T"),
            ledger_profile_id="profile-a",
            investment_asset_register=register,
            investment_asset_profile_id="profile-a",
        )
