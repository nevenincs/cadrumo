"""A purchase's totals come from its components, and stated totals are still judged."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.domain.contribuyente.inventory.records import load_inventory_acquisition_cost

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _facts(**totals: str) -> str:
    # Worked by hand:
    # price 100.00 with 21.00 IVA half recoverable: 10.50 recoverable, 10.50 not.
    # carriage 10.00 with 2.10 IVA fully recoverable: 2.10 recoverable, 0.00 not.
    # attributable 10.00; recoverable 12.60; not recoverable 10.50;
    # total 100.00 + 10.00 + 10.50 = 120.50.
    return json.dumps(
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
                {
                    "reference": {"reference": reference},
                    "evidence_kind": kind,
                    "content_digest": digit * 64,
                }
                for reference, kind, digit in (
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
            **totals,
        }
    )


def test_omitted_totals_are_added_up_from_the_components() -> None:
    cost = load_inventory_acquisition_cost(_facts())

    assert cost.directly_attributable_cost_total == Decimal("10.00")
    assert cost.recoverable_iva_excluded == Decimal("12.60")
    assert cost.nonrecoverable_iva_included == Decimal("10.50")
    assert cost.total_acquisition_cost == Decimal("120.50")


def test_totals_stated_correctly_are_accepted() -> None:
    cost = load_inventory_acquisition_cost(
        _facts(
            directly_attributable_cost_total="10.00",
            recoverable_iva_excluded="12.60",
            nonrecoverable_iva_included="10.50",
            total_acquisition_cost="120.50",
        )
    )

    assert cost == load_inventory_acquisition_cost(_facts())


def test_one_wrong_stated_total_is_refused_rather_than_replaced() -> None:
    with pytest.raises(ValidationError):
        load_inventory_acquisition_cost(_facts(total_acquisition_cost="120.51"))
