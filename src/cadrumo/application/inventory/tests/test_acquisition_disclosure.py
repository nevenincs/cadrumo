"""A purchase's private facts leave only through the projection that names them."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.inventory.registered_projections import (
    InventoryLedgerProjection,
    InventoryMovementProjection,
)
from cadrumo.application.inventory.registered_requests import InventoryAcquisitionCostRequest
from cadrumo.domain.contribuyente.inventory.records import (
    InventoryAcquisitionCost,
    InventoryLedger,
    MovementRecord,
    ValuationMethod,
    load_inventory_acquisition_cost,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _cost() -> InventoryAcquisitionCost:
    return load_inventory_acquisition_cost(
        json.dumps(
            {
                "consideration_excluding_iva": "100.00",
                "consideration_iva_amount": "21.00",
                "consideration_deductible_iva_ratio": "0.50",
                "attributable_cost_components": [
                    {
                        "component_id": "carriage",
                        "kind": "freight",
                        "taxable_base": "10.00",
                        "iva_amount": "2.10",
                        "deductible_iva_ratio": "1.00",
                        "evidence_references": [{"reference": "invoice"}],
                    }
                ],
                "evidence": [
                    {"reference": {"reference": name}, "evidence_kind": kind, "content_digest": digit * 64}
                    for name, kind, digit in (
                        ("invoice", "purchase_invoice", "a"),
                        ("cost-review", "attributable_cost_review", "b"),
                        ("iva-review", "iva_recoverability_review", "c"),
                    )
                ],
                "completeness": {
                    "consideration_evidence": {"reference": "invoice"},
                    "attributable_cost_review_evidence": {"reference": "cost-review"},
                    "iva_recoverability_review_evidence": {"reference": "iva-review"},
                },
            }
        )
    )


def _movement() -> MovementRecord:
    return MovementRecord.from_purchase_acquisition(
        movement_id="mv-1",
        movement_date=date(2026, 3, 1),
        sku="widget",
        quantity=Decimal("10"),
        acquisition_cost=_cost(),
    )


def test_a_movement_withholds_its_purchase_facts_unless_they_are_named() -> None:
    plain = InventoryMovementProjection.from_movement(_movement()).model_dump_json()

    assert '"acquisition_detail":null' in plain.replace(" ", "")
    assert "a" * 64 not in plain
    assert "carriage" not in plain


def test_the_named_detail_returns_what_a_correction_would_otherwise_ask_for() -> None:
    ledger = InventoryLedger(
        actividad_id="act-1",
        year=2026,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("0.00"),
        closing_authority_record=None,
        opening_layers=(),
        period_movements=(_movement(),),
    )
    projected = InventoryLedgerProjection.from_ledger(ledger, with_acquisition_detail=True)
    detail = projected.period_movements[0].acquisition_detail

    assert detail is not None
    assert detail.consideration_iva_amount.decimal == "21.00"
    assert detail.consideration_deductible_iva_ratio.decimal == "0.50"
    assert [item.component_id for item in detail.components] == ["carriage"]
    assert detail.components[0].evidence_references == ("invoice",)
    assert {item.reference: item.content_digest for item in detail.documents} == {
        "invoice": "a" * 64,
        "cost-review": "b" * 64,
        "iva-review": "c" * 64,
    }
    assert detail.attributable_cost_review_evidence == "cost-review"


def test_a_request_without_totals_settles_as_the_same_cost() -> None:
    stated = InventoryAcquisitionCostRequest.from_domain(_cost())
    omitted = stated.model_copy(
        update={
            "directly_attributable_cost_total": None,
            "nonrecoverable_iva_included": None,
            "recoverable_iva_excluded": None,
            "total_acquisition_cost": None,
        }
    )

    assert omitted.to_domain() == _cost()
