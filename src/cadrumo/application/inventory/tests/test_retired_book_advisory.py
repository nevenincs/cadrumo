"""A retired book that still holds entries says its year's Anexo D stays unresolved."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.application.inventory.registered_projections import InventoryLedgerProjection
from cadrumo.core.i18n.render import tr
from cadrumo.domain.contribuyente.inventory.corrections import InventoryChangeStamp, retire_ledger
from cadrumo.domain.contribuyente.inventory.records import (
    InventoryLedger,
    InventoryLedgerDocument,
    InventoryRetirementReason,
    ValuationMethod,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)


def _ledger(opening: str) -> InventoryLedger:
    return InventoryLedger(
        actividad_id="act-1",
        year=2026,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal(opening),
        closing_authority_record=None,
        opening_layers=(),
        period_movements=(),
    )


def _retired(opening: str) -> InventoryLedger:
    ledger = _ledger(opening)
    return retire_ledger(
        InventoryLedgerDocument(ledgers=(ledger,)),
        ledger,
        stamp=InventoryChangeStamp(correction_id="c-1", recorded_at=_AT, actor="cli"),
        reason=next(iter(InventoryRetirementReason)),
    )


def test_a_retired_book_with_facts_carries_a_real_sentence_key() -> None:
    advisories = InventoryLedgerProjection.from_ledger(_retired("10.00")).advisories

    assert [(item.code, item.year) for item in advisories] == [("retired_book_leaves_year_unresolved", 2026)]
    sentence = tr(advisories[0].key, year=2026)
    assert sentence != advisories[0].key
    assert "2026" in sentence


def test_a_retired_empty_book_and_a_live_book_say_nothing() -> None:
    assert InventoryLedgerProjection.from_ledger(_retired("0.00")).advisories == ()
    assert InventoryLedgerProjection.from_ledger(_ledger("10.00")).advisories == ()
