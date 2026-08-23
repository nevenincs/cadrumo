"""Grounded 2025 inventory-variation projection tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.domain.contribuyente.inventory import (
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionCost,
    InventoryAcquisitionEvidence,
    InventoryAcquisitionEvidenceKind,
    InventoryAnexoDResult,
    InventoryLedger,
    InventoryLedgerError,
    InventoryValidationError,
    MovementKind,
    MovementRecord,
    ValuationMethod,
    compute_inventory_anexo_d_projection,
)
from cadrumo.domain.filing_evidence import FilingEvidenceReference

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _purchase_cost(value: str) -> InventoryAcquisitionCost:
    reference = FilingEvidenceReference(reference="purchase-evidence")
    cost_review = FilingEvidenceReference(reference="cost-review-evidence")
    iva_review = FilingEvidenceReference(reference="iva-review-evidence")
    iva = Decimal(value) * Decimal("0.21")
    return InventoryAcquisitionCost(
        consideration_excluding_iva=Decimal(value),
        consideration_iva_amount=iva,
        consideration_deductible_iva_ratio=Decimal("1"),
        attributable_cost_components=(),
        evidence=(
            InventoryAcquisitionEvidence(
                reference=reference,
                evidence_kind=InventoryAcquisitionEvidenceKind.PURCHASE_INVOICE,
                content_digest="a" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=cost_review,
                evidence_kind=InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW,
                content_digest="b" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=iva_review,
                evidence_kind=InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW,
                content_digest="c" * 64,
            ),
        ),
        completeness=InventoryAcquisitionCompleteness(
            consideration_evidence=reference,
            attributable_cost_review_evidence=cost_review,
            iva_recoverability_review_evidence=iva_review,
        ),
        directly_attributable_cost_total=Decimal("0.00"),
        nonrecoverable_iva_included=Decimal("0.00"),
        recoverable_iva_excluded=iva,
        total_acquisition_cost=Decimal(value),
    )


def _ledger(*, opening: str, purchase: str | None = None, closing: str | None = None) -> InventoryLedger:
    movements = ()
    if purchase is not None:
        movements = (
            MovementRecord(
                movement_id="purchase-1",
                movement_date=date(2025, 2, 1),
                kind=MovementKind.PURCHASE,
                quantity=Decimal("1"),
                unit_cost=Decimal(purchase),
                acquisition_cost=_purchase_cost(purchase),
            ),
        )
    return InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal(opening),
        closing_stock=None if closing is None else Decimal(closing),
        period_movements=movements,
    )


def test_closing_over_opening_populates_only_casilla_0177() -> None:
    result = compute_inventory_anexo_d_projection(_ledger(opening="100.00", purchase="25.00"))

    assert result == InventoryAnexoDResult(
        actividad_id="retail",
        filing_year=2025,
        opening_value=Decimal("100.00"),
        closing_value=Decimal("125.00"),
        casilla_0177=Decimal("25.00"),
        casilla_0182=Decimal("0.00"),
    )


def test_opening_over_closing_populates_only_casilla_0182() -> None:
    ledger = InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("100.00"),
        period_movements=(
            MovementRecord(
                movement_id="sale-1",
                movement_date=date(2025, 2, 1),
                kind=MovementKind.COGS,
                quantity=Decimal("0.25"),
            ),
        ),
    )

    result = compute_inventory_anexo_d_projection(ledger)

    assert result.opening_value == Decimal("100.00")
    assert result.closing_value == Decimal("75.00")
    assert result.casilla_0177 == Decimal("0.00")
    assert result.casilla_0182 == Decimal("25.00")


def test_equal_opening_and_closing_produce_two_zeroes() -> None:
    result = compute_inventory_anexo_d_projection(_ledger(opening="100.00", closing="100.00"))

    assert result.casilla_0177 == Decimal("0.00")
    assert result.casilla_0182 == Decimal("0.00")


def test_projection_refuses_a_revision_outside_grounded_2025_scope() -> None:
    ledger = _ledger(opening="0.00").model_copy(update={"year": 2024})

    with pytest.raises(InventoryLedgerError, match="grounded only for filing year 2025"):
        compute_inventory_anexo_d_projection(ledger)


def test_projection_refuses_unadjudicated_explicit_closing_conflict() -> None:
    ledger = _ledger(opening="100.00", purchase="25.00", closing="130.00")

    with pytest.raises(InventoryLedgerError, match="explicit inventory closing conflicts"):
        compute_inventory_anexo_d_projection(ledger)


def test_projection_refuses_movements_outside_the_ledger_year() -> None:
    ledger = _ledger(opening="0.00", purchase="25.00")
    movement = ledger.period_movements[0].model_copy(update={"movement_date": date(2024, 12, 31)})
    ledger = ledger.model_copy(update={"period_movements": (movement,)})

    with pytest.raises(InventoryLedgerError, match="movements outside its filing year"):
        compute_inventory_anexo_d_projection(ledger)


def test_result_refuses_a_split_that_does_not_match_its_audited_basis() -> None:
    with pytest.raises(ValidationError) as exc_info:
        InventoryAnexoDResult(
            actividad_id="retail",
            filing_year=2025,
            opening_value=Decimal("100.00"),
            closing_value=Decimal("125.00"),
            casilla_0177=Decimal("25.00"),
            casilla_0182=Decimal("1.00"),
        )

    assert isinstance(exc_info.value.errors()[0]["ctx"]["error"], InventoryValidationError)


def test_result_refuses_non_cent_audited_values() -> None:
    with pytest.raises(ValidationError, match="quantised to cents"):
        InventoryAnexoDResult(
            actividad_id="retail",
            filing_year=2025,
            opening_value=Decimal("100.001"),
            closing_value=Decimal("125.00"),
            casilla_0177=Decimal("25.00"),
            casilla_0182=Decimal("0.00"),
        )
