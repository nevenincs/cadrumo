"""Strict complete 2025 inventory projection tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from ....filing_evidence import FilingEvidenceReference
from ..records import (
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionCost,
    InventoryAcquisitionEvidence,
    InventoryAcquisitionEvidenceKind,
    InventoryAnexoDResult,
    InventoryAttributableCostComponent,
    InventoryAttributableCostKind,
    InventoryClosingAuthority,
    InventoryClosingAuthorityDecision,
    InventoryClosingAuthorityRecord,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    InventoryClosingValuationBasis,
    InventoryLedger,
    InventoryLedgerError,
    MovementKind,
    MovementRecord,
    PhysicalClosingEvidence,
    PhysicalClosingEvidenceRole,
    PhysicalClosingObservation,
    PriorAuthoritativeClosingLink,
    PriorClosingContinuityEvidence,
    ValuationMethod,
    compute_inventory_anexo_d_projection,
    fingerprint_prior_authoritative_closing,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _ref(value: str) -> FilingEvidenceReference:
    return FilingEvidenceReference(reference=value)


def _acquisition() -> InventoryAcquisitionCost:
    return InventoryAcquisitionCost(
        consideration_excluding_iva=Decimal("100.00"),
        consideration_iva_amount=Decimal("21.00"),
        consideration_deductible_iva_ratio=Decimal("0.50"),
        attributable_cost_components=(
            InventoryAttributableCostComponent(
                component_id="freight-1",
                kind=InventoryAttributableCostKind.FREIGHT,
                taxable_base=Decimal("10.00"),
                iva_amount=Decimal("2.10"),
                deductible_iva_ratio=Decimal("0"),
                evidence_references=(_ref("freight-evidence"),),
            ),
        ),
        evidence=(
            InventoryAcquisitionEvidence(
                reference=_ref("invoice-evidence"),
                evidence_kind=InventoryAcquisitionEvidenceKind.PURCHASE_INVOICE,
                content_digest="a" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref("freight-evidence"),
                evidence_kind=InventoryAcquisitionEvidenceKind.TRANSPORT_DOCUMENT,
                content_digest="b" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref("cost-review-evidence"),
                evidence_kind=InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW,
                content_digest="c" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref("iva-review-evidence"),
                evidence_kind=InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW,
                content_digest="d" * 64,
            ),
        ),
        completeness=InventoryAcquisitionCompleteness(
            consideration_evidence=_ref("invoice-evidence"),
            attributable_cost_review_evidence=_ref("cost-review-evidence"),
            iva_recoverability_review_evidence=_ref("iva-review-evidence"),
        ),
        directly_attributable_cost_total=Decimal("10.00"),
        nonrecoverable_iva_included=Decimal("12.60"),
        recoverable_iva_excluded=Decimal("10.50"),
        total_acquisition_cost=Decimal("122.60"),
    )


def _purchase(movement_id: str = "purchase-1", movement_date: date = date(2025, 2, 1)) -> MovementRecord:
    return MovementRecord(
        movement_id=movement_id,
        movement_date=movement_date,
        kind=MovementKind.PURCHASE,
        quantity=Decimal("2"),
        unit_cost=Decimal("50.00"),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        deductible_iva_ratio=Decimal("0.50"),
        acquisition_cost=_acquisition(),
    )


def _authority(
    opening: Decimal, *, physical: Decimal | None = None, select_physical: bool = False
) -> InventoryClosingAuthorityRecord:
    continuity = (PriorClosingContinuityEvidence(reference=_ref("prior-evidence"), content_digest="f" * 64),)
    observation = (
        None
        if physical is None
        else PhysicalClosingObservation(
            observation_id="physical-2025",
            observed_on=date(2026, 1, 1),
            as_of_date=date(2025, 12, 31),
            actividad_id="retail",
            filing_year=2025,
            closing_value=physical,
            valuation_basis=InventoryClosingValuationBasis.FIFO_ACQUISITION_PRICE,
            evidence=(
                PhysicalClosingEvidence(
                    reference=_ref("count-evidence"),
                    role=PhysicalClosingEvidenceRole.PHYSICAL_COUNT,
                    content_digest="1" * 64,
                ),
                PhysicalClosingEvidence(
                    reference=_ref("value-evidence"),
                    role=PhysicalClosingEvidenceRole.ACQUISITION_PRICE_VALUATION,
                    content_digest="2" * 64,
                ),
            ),
        )
    )
    return InventoryClosingAuthorityRecord(
        decision=InventoryClosingAuthorityDecision(
            decision_id="decision-2025",
            actividad_id="retail",
            filing_year=2025,
            authority=InventoryClosingAuthority.PHYSICAL_OBSERVATION
            if select_physical
            else InventoryClosingAuthority.MOVEMENT_DERIVED,
            physical_observation_id=observation.observation_id if observation else None,
            physical_observation_fingerprint=observation.fingerprint if observation else None,
            reason="Reviewed annual inventory authority.",
            actor="reviewer",
            source_command="inventory.closing.authority.decide",
            decided_at=datetime(2026, 1, 2, tzinfo=UTC),
            evidence=(
                InventoryClosingDecisionEvidence(
                    reference=_ref("decision-evidence"),
                    role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                    content_digest="e" * 64,
                ),
            ),
        ),
        physical_observation=observation,
        prior_closing_link=PriorAuthoritativeClosingLink(
            actividad_id="retail",
            current_filing_year=2025,
            prior_filing_year=2024,
            prior_authoritative_closing_value=opening,
            current_opening_value=opening,
            prior_authoritative_source_fingerprint="3" * 64,
            prior_authoritative_closing_fingerprint=fingerprint_prior_authoritative_closing(
                actividad_id="retail",
                filing_year=2024,
                authoritative_closing_value=opening,
                authoritative_source_fingerprint="3" * 64,
                evidence=continuity,
            ),
            evidence=continuity,
        ),
    )


def _ledger(
    *,
    opening: str = "100.00",
    movements: tuple[MovementRecord, ...] = (),
    physical: str | None = None,
    select_physical: bool = False,
) -> InventoryLedger:
    value = Decimal(opening)
    return InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=value,
        period_movements=movements,
        closing_authority_record=_authority(
            value, physical=Decimal(physical) if physical else None, select_physical=select_physical
        ),
    )


def _projection_validation_payload(result: InventoryAnexoDResult) -> dict[str, object]:
    payload = cast(dict[str, object], result.model_dump())
    return payload | {"source_ledger": result.source_ledger}


def test_complete_cost_owns_0181_and_increase() -> None:
    result = compute_inventory_anexo_d_projection(_ledger(movements=(_purchase(),)))
    assert result.casilla_0181 == result.complete_acquisition_total == Decimal("122.60")
    assert (result.casilla_0177, result.casilla_0182) == (Decimal("122.60"), Decimal("0.00"))
    assert len(result.acquisition_fingerprints) == 1
    assert result.authority_record_fingerprint and result.decision_fingerprint and result.prior_closing_link_fingerprint


def test_equal_and_decrease_split() -> None:
    equal = compute_inventory_anexo_d_projection(_ledger())
    assert (equal.casilla_0177, equal.casilla_0182) == (Decimal("0.00"), Decimal("0.00"))
    sale = MovementRecord(
        movement_id="sale", movement_date=date(2025, 3, 1), kind=MovementKind.COGS, quantity=Decimal("0.25")
    )
    decrease = compute_inventory_anexo_d_projection(_ledger(movements=(sale,)))
    assert (decrease.casilla_0177, decrease.casilla_0182) == (Decimal("0.00"), Decimal("25.00"))


def test_both_authorities_retain_conflict() -> None:
    physical = compute_inventory_anexo_d_projection(_ledger(physical="130.00", select_physical=True))
    movement = compute_inventory_anexo_d_projection(_ledger(physical="130.00"))
    assert physical.authoritative_closing_value == Decimal("130.00")
    assert movement.authoritative_closing_value == Decimal("100.00")
    assert physical.closing_conflict == movement.closing_conflict
    assert physical.issues == movement.issues == ("physical_closing_conflict",)


def test_missing_unreadable_wrong_year_and_out_of_period_refuse() -> None:
    with pytest.raises(InventoryLedgerError, match="requires a complete closing-authority"):
        compute_inventory_anexo_d_projection(_ledger().model_copy(update={"closing_authority_record": None}))
    tampered_purchase = _purchase().model_copy(update={"acquisition_cost": None})
    with pytest.raises(InventoryLedgerError, match="incomplete or unreadable"):
        compute_inventory_anexo_d_projection(
            _ledger(movements=(_purchase(),)).model_copy(update={"period_movements": (tampered_purchase,)})
        )
    with pytest.raises(InventoryLedgerError, match="grounded only"):
        compute_inventory_anexo_d_projection(_ledger().model_copy(update={"year": 2024}))
    out_of_period = _purchase().model_copy(update={"movement_date": date(2024, 12, 31)})
    with pytest.raises(InventoryLedgerError, match="outside its filing year"):
        compute_inventory_anexo_d_projection(_ledger(movements=(out_of_period,)))
    ledger = _ledger()
    assert ledger.closing_authority_record is not None
    broken_link = ledger.closing_authority_record.prior_closing_link.model_copy(
        update={"current_opening_value": Decimal("99.00")}
    )
    broken_record = ledger.closing_authority_record.model_copy(update={"prior_closing_link": broken_link})
    with pytest.raises(InventoryLedgerError, match="incomplete or unreadable"):
        compute_inventory_anexo_d_projection(ledger.model_copy(update={"closing_authority_record": broken_record}))


def test_purchase_fingerprints_are_reorder_invariant() -> None:
    first, second = _purchase("b", date(2025, 3, 1)), _purchase("a", date(2025, 2, 1))
    forward = compute_inventory_anexo_d_projection(_ledger(movements=(first, second)))
    reversed_result = compute_inventory_anexo_d_projection(_ledger(movements=(second, first)))
    assert forward.acquisition_fingerprints == reversed_result.acquisition_fingerprints
    assert forward.projection_fingerprint == reversed_result.projection_fingerprint
    acquisition = _acquisition()
    reordered_acquisition = acquisition.model_copy(update={"evidence": tuple(reversed(acquisition.evidence))})
    reordered_evidence = first.model_copy(update={"acquisition_cost": reordered_acquisition})
    evidence_result = compute_inventory_anexo_d_projection(_ledger(movements=(reordered_evidence, second)))
    assert evidence_result.projection_fingerprint == forward.projection_fingerprint
    scale_equivalent = first.model_copy(
        update={
            "quantity": Decimal("2.0"),
            "unit_cost": Decimal("50.0"),
            "taxable_base": Decimal("100.0"),
            "iva_rate": Decimal("21.0"),
            "iva_amount": Decimal("21.0"),
            "deductible_iva_ratio": Decimal("0.5"),
        }
    )
    scaled_result = compute_inventory_anexo_d_projection(_ledger(movements=(scale_equivalent, second)))
    assert scaled_result.projection_fingerprint == forward.projection_fingerprint
    duplicate = _purchase("a", date(2025, 2, 1)).model_copy(update={"sku": "other"})
    with pytest.raises(ValidationError, match="movement_id values must be unique"):
        _ledger(movements=(first.model_copy(update={"movement_id": "a"}), duplicate))


def test_projection_refuses_output_override_and_result_forgery() -> None:
    result = compute_inventory_anexo_d_projection(
        _ledger(movements=(_purchase(),), physical="130.00", select_physical=True)
    )
    movement_result = compute_inventory_anexo_d_projection(_ledger(movements=(_purchase(),), physical="130.00"))
    unsupported_override: dict[str, object] = {"authoritative_closing_value": Decimal("999")}
    with pytest.raises(TypeError):
        compute_inventory_anexo_d_projection(_ledger(), **unsupported_override)
    assert result.closing_conflict is not None
    correlated_physical_fingerprint = "8" * 64
    for mutation in (
        {"casilla_0181": Decimal("1.00")},
        {"acquisition_fingerprints": ()},
        {"acquisition_fingerprints": result.acquisition_fingerprints * 2},
        {"acquisition_fingerprints": ("7" * 64,)},
        {"authority_record_fingerprint": "6" * 64},
        {"decision_id": "forged-decision"},
        {"decision_fingerprint": "5" * 64},
        {"prior_closing_link_fingerprint": "4" * 64},
        {"issues": ()},
        {"authoritative_closing_value": Decimal("100.00")},
        {"physical_observation_id": None},
        {"physical_observation_fingerprint": "9" * 64},
        {
            "physical_observation_id": "forged-observation",
            "physical_observation_fingerprint": correlated_physical_fingerprint,
            "closing_conflict": result.closing_conflict.model_copy(
                update={"physical_observation_fingerprint": correlated_physical_fingerprint}
            ),
        },
        {
            "selected_authority": InventoryClosingAuthority.MOVEMENT_DERIVED,
            "authoritative_closing_value": result.movement_derived_closing_value,
            "casilla_0177": result.movement_derived_closing_value - result.opening_value,
        },
        {"opening_value": Decimal("100.001")},
        {"closing_conflict": result.closing_conflict.model_copy(update={"actividad_id": "other"})},
        {"closing_conflict": result.closing_conflict.model_copy(update={"physical_observed_value": Decimal("131.00")})},
    ):
        with pytest.raises(ValidationError) as exc_info:
            candidate = result.model_copy(update=mutation)
            type(result).model_validate(_projection_validation_payload(candidate))
        assert "source_ledger\n  Field required" not in str(exc_info.value)
    with pytest.raises(ValidationError) as exc_info:
        candidate = movement_result.model_copy(update={"closing_conflict": None, "issues": ()})
        type(movement_result).model_validate(_projection_validation_payload(candidate))
    assert "source_ledger\n  Field required" not in str(exc_info.value)
    correlated = result.model_copy(
        update={
            "selected_authority": InventoryClosingAuthority.MOVEMENT_DERIVED,
            "authoritative_closing_value": result.movement_derived_closing_value,
            "casilla_0177": result.movement_derived_closing_value - result.opening_value,
        }
    )
    reminted = correlated.model_copy(update={"projection_fingerprint": correlated.expected_projection_fingerprint})
    with pytest.raises(ValidationError, match="retained source authority"):
        type(result).model_validate(_projection_validation_payload(reminted))
    serialized = result.model_dump_json()
    for canary in (
        "invoice-evidence",
        "freight-evidence",
        "cost-review-evidence",
        "iva-review-evidence",
        "decision-evidence",
        "count-evidence",
        "value-evidence",
        "prior-evidence",
        "1" * 64,
        "2" * 64,
        "3" * 64,
        "a" * 64,
        "b" * 64,
        "c" * 64,
        "d" * 64,
        "e" * 64,
        "f" * 64,
        "reviewer",
        "inventory.closing.authority.decide",
    ):
        assert canary not in serialized
    with pytest.raises(ValidationError, match="source_ledger"):
        type(result).model_validate(result.model_dump())
    assert type(result).model_validate(_projection_validation_payload(result)) == result


def test_reminted_substituted_sources_refuse_but_distinct_projection_succeeds() -> None:
    baseline_ledger = _ledger(movements=(_purchase(),), physical="130.00", select_physical=True)
    baseline = compute_inventory_anexo_d_projection(baseline_ledger)
    assert baseline_ledger.closing_authority_record is not None
    changed_decision = baseline_ledger.closing_authority_record.decision.model_copy(update={"reason": "Other review."})
    changed_record = baseline_ledger.closing_authority_record.model_copy(update={"decision": changed_decision})
    alternatives = (
        _ledger(movements=(_purchase("other-purchase"),), physical="130.00", select_physical=True),
        baseline_ledger.model_copy(update={"closing_authority_record": changed_record}),
        _ledger(movements=(_purchase(),), physical="131.00", select_physical=True),
        _ledger(opening="90.00", movements=(_purchase(),), physical="130.00", select_physical=True),
    )
    for alternative_ledger in alternatives:
        alternative = compute_inventory_anexo_d_projection(alternative_ledger)
        assert alternative.projection_fingerprint != baseline.projection_fingerprint
        substituted = baseline.model_copy(
            update={
                "source_ledger": alternative.source_ledger,
                "source_ledger_fingerprint": alternative.source_ledger_fingerprint,
            }
        )
        reminted = substituted.model_copy(
            update={"projection_fingerprint": substituted.expected_projection_fingerprint}
        )
        with pytest.raises(ValidationError, match="retained source authority"):
            type(baseline).model_validate(_projection_validation_payload(reminted))
