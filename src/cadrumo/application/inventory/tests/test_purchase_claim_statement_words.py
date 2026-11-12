"""What a purchase states about its ledger transaction is served with the words that say what it does."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from cadrumo.application.inventory.registered_options_operation import (
    INVENTORY_EFFECT_FAMILIES,
    inventory_options,
)
from cadrumo.application.inventory.registered_projections import InventoryMovementProjection
from cadrumo.core.i18n.render import tr
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.contribuyente.inventory.records import (
    InventoryAcquisitionCost,
    MovementRecord,
    PurchaseLedgerRow,
    load_inventory_acquisition_cost,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("38383838-3838-4838-8838-383838383838")
_LOCALES = ("en", "es", "ca", "hu")
_TRANSACTION = "e" * 64


def _cost() -> InventoryAcquisitionCost:
    return load_inventory_acquisition_cost(
        json.dumps(
            {
                "consideration_excluding_iva": "100.00",
                "consideration_iva_amount": "0.00",
                "consideration_deductible_iva_ratio": "1.00",
                "attributable_cost_components": [],
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


def _purchase(*, ledger_row: PurchaseLedgerRow, claimed_transaction_id: str | None) -> MovementRecord:
    return MovementRecord.from_purchase_acquisition(
        movement_id="mv-1",
        movement_date=date(filing_year_envelope().horizon, 3, 1),
        quantity=Decimal(1),
        acquisition_cost=_cost(),
        ledger_row=ledger_row,
        claimed_transaction_id=claimed_transaction_id,
    )


def test_a_claimed_purchase_serves_its_statement_and_the_transaction_it_names() -> None:
    served = InventoryMovementProjection.from_movement(
        _purchase(ledger_row=PurchaseLedgerRow.CLAIMED, claimed_transaction_id=_TRANSACTION)
    )

    assert served.ledger_row is PurchaseLedgerRow.CLAIMED
    assert served.claimed_transaction_id == _TRANSACTION
    assert '"ledger_row":"claimed"' in served.model_dump_json().replace(" ", "")


@pytest.mark.parametrize("ledger_row", [PurchaseLedgerRow.UNSTATED, PurchaseLedgerRow.NONE])
def test_a_purchase_naming_no_transaction_serves_none_for_it(ledger_row: PurchaseLedgerRow) -> None:
    served = InventoryMovementProjection.from_movement(_purchase(ledger_row=ledger_row, claimed_transaction_id=None))

    assert served.ledger_row is ledger_row
    assert served.claimed_transaction_id is None


def test_the_statement_family_is_the_domain_vocabulary_in_order_and_alone_serves_effects() -> None:
    families = {family.family: family for family in inventory_options(_PROFILE).families}

    assert [option.value for option in families["purchase_ledger_row"].options] == [
        member.value for member in PurchaseLedgerRow
    ]
    with_effect = {
        family.family for family in families.values() for option in family.options if option.effect_key is not None
    }
    assert with_effect == INVENTORY_EFFECT_FAMILIES == {"purchase_ledger_row"}
    assert all(option.effect_key is not None for option in families["purchase_ledger_row"].options)


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_statement_has_its_word_and_its_effect_sentence_in_every_locale(locale: str) -> None:
    options = next(
        family for family in inventory_options(_PROFILE).families if family.family == "purchase_ledger_row"
    ).options
    keys = [key for option in options for key in (option.label_key, option.effect_key) if key is not None]

    rendered = {key: tr(key, locale=locale) for key in keys}

    # An unauthored key renders as itself.
    assert [key for key, text in rendered.items() if text == key or not text.strip()] == []
    effects = [rendered[option.effect_key] for option in options if option.effect_key is not None]
    # The sentence is shown as served, so it carries no placeholder for a caller to fill.
    assert all("{" not in text for text in effects)
    assert len(set(effects)) == len(effects)
