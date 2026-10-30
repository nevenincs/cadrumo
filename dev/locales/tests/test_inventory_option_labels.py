"""Every value an inventory form is offered has a word in every locale."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
import yaml
from pydantic import ValidationError

from cadrumo.application.inventory.registered_options_operation import INVENTORY_OPTION_FAMILIES, inventory_options
from cadrumo.domain.contribuyente.inventory.closing_foundations import InventoryClosingAuthority
from cadrumo.domain.contribuyente.inventory.records import (
    InventoryAcquisitionEvidenceKind,
    MovementRecord,
    load_inventory_acquisition_cost,
)

from .._paths import LOCALES_DIR

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("28282828-2828-4828-8828-282828282828")


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_every_option_is_worded(locale: str) -> None:
    catalogue = yaml.safe_load((LOCALES_DIR / locale / "application.yml").read_text(encoding="utf-8"))
    missing: list[str] = []
    for family in inventory_options(_PROFILE).families:
        for option in family.options:
            node = catalogue
            for part in option.label_key.split("."):
                node = node.get(part) if isinstance(node, dict) else None
            if not isinstance(node, str) or not node.strip():
                missing.append(option.label_key)

    assert missing == []


def _role_values() -> dict[str, tuple[str, str]]:
    return {
        option.role: (family.family, option.value)
        for family in inventory_options(_PROFILE).families
        for option in family.options
        if option.role is not None
    }


def test_each_role_marks_the_member_the_domain_rules_treat_that_way() -> None:
    roles = _role_values()
    assert set(roles) == {"cost_check", "iva_check", "count_authority", "purchase"}
    kinds = {
        "invoice": InventoryAcquisitionEvidenceKind.PURCHASE_INVOICE,
        "cost": InventoryAcquisitionEvidenceKind(roles["cost_check"][1]),
        "iva": InventoryAcquisitionEvidenceKind(roles["iva_check"][1]),
    }

    def cost(kinds_by_reference: dict[str, InventoryAcquisitionEvidenceKind]) -> str:
        return json.dumps(
            {
                "consideration_excluding_iva": "10.00",
                "consideration_iva_amount": "0.00",
                "consideration_deductible_iva_ratio": "1.00",
                "attributable_cost_components": [],
                "evidence": [
                    {"reference": {"reference": name}, "evidence_kind": kind.value, "content_digest": "a" * 64}
                    for name, kind in kinds_by_reference.items()
                ],
                "completeness": {
                    "consideration_evidence": {"reference": "invoice"},
                    "attributable_cost_review_evidence": {"reference": "cost"},
                    "iva_recoverability_review_evidence": {"reference": "iva"},
                },
            }
        )

    purchase = load_inventory_acquisition_cost(cost(kinds))
    with pytest.raises(ValidationError):
        load_inventory_acquisition_cost(cost({**kinds, "cost": kinds["iva"], "iva": kinds["cost"]}))

    made = MovementRecord.from_purchase_acquisition(
        movement_id="m", movement_date=date(2026, 1, 1), quantity=Decimal("1"), acquisition_cost=purchase
    )
    assert roles["purchase"] == ("movement_kind", made.kind.value)
    assert roles["count_authority"] == ("closing_authority", InventoryClosingAuthority.PHYSICAL_OBSERVATION.value)


def test_the_options_are_exactly_the_canonical_vocabularies() -> None:
    served = {family.family: [item.value for item in family.options] for family in inventory_options(_PROFILE).families}

    assert served == {family: [member.value for member in enum] for family, enum in INVENTORY_OPTION_FAMILIES}
