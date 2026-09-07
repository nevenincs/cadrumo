"""The fingerprint field set is versioned, append-only, and never back-applied.

A stored fingerprint is only comparable against one recomputed over the same
fields. Widening the set in place would therefore change every recomputed hash
and report every already-sealed snapshot as fully changed -- a mass false alarm
rather than a discovery. So each snapshot records the set it was sealed under
and is compared under that set forever.

The facts V2 adds are the ones that moved a casilla and were invisible: the
deduction and prorrata declarations, ``usage_ratio_id``, and the recargo. Of
those, the declarations are where the blindness was reachable, because
``Transaction`` ties the recargo to the gross and so a surcharge cannot move
without moving an amount V1 already watched.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....domain.iva.prorrata import InputClassification
from ....domain.modelos.errors import ModeloValidationError
from ....domain.modelos.ledger_filing_snapshot import LedgerFilingSnapshot
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ...modelo.tests.test_modelo_303_deductible_evidence_gate import _iva_transaction
from ..ledger_filing_snapshot import (
    _FINGERPRINT_FIELDS_V1,
    _FINGERPRINT_FIELDS_V2,
    CURRENT_FINGERPRINT_FIELD_SET_VERSION,
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
    evaluate_ledger_filing_staleness,
    row_fingerprint,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CAPTURED_AT = datetime(2026, 1, 1, tzinfo=UTC)
_LEGAL_REFS = ("ley-37-1992-art-97",)
_SOURCE_REFS = ("aeat-modelo-303",)


def _purchase() -> Transaction:
    """A deductible business purchase carrying no prorrata declaration yet."""
    return _iva_transaction("versioning-probe", direction=TransactionDirection.OUTGOING, taxable_base=Decimal("200.00"))


def _catalogue(*transactions: Transaction) -> TransactionCatalogue:
    return TransactionCatalogue.from_transactions(transactions)


def _snapshot_of(transaction: Transaction) -> LedgerFilingSnapshot:
    return compute_ledger_filing_snapshot(
        source_transaction_ids=[transaction.transaction_id],
        catalogue=_catalogue(transaction),
        captured_at=_CAPTURED_AT,
    )


def _sealed_under_v1(transaction: Transaction) -> LedgerFilingSnapshot:
    """A snapshot as an older build wrote them: V1 hashes under a V1 stamp."""
    live = _snapshot_of(transaction)
    return live.model_copy(
        update={
            "fingerprint_field_set_version": 1,
            "rows": tuple(
                row.model_copy(update={"fingerprint": row_fingerprint(transaction, field_set_version=1)})
                for row in live.rows
            ),
        },
    )


def test_v2_appends_to_v1_and_never_reorders_it() -> None:
    """The order feeds the hashed string, so a version cannot rescue a reshuffle."""
    assert _FINGERPRINT_FIELDS_V2[: len(_FINGERPRINT_FIELDS_V1)] == _FINGERPRINT_FIELDS_V1
    assert len(_FINGERPRINT_FIELDS_V2) == len(_FINGERPRINT_FIELDS_V1) + 7
    assert CURRENT_FINGERPRINT_FIELD_SET_VERSION == 2


def test_a_version_this_build_does_not_know_is_refused_not_approximated() -> None:
    """A snapshot from a newer build must not be compared under a narrower set."""
    with pytest.raises(ModeloValidationError, match="unknown to this build"):
        row_fingerprint(_purchase(), field_set_version=99)


def test_a_reclassified_deduction_is_drift_under_v2_and_invisible_under_v1() -> None:
    """The closed gap, and the deliberate preservation of the old answer.

    ``input_classification`` decides what a row deducts and carries no
    arithmetic identity, so it can move while every amount stays put. That is
    the shape V1 could not see and V2 can. The V1 snapshot keeps answering as
    it always did, because restating it would claim the wider facts had been
    checked when the filing was sealed, which nobody knows.
    """
    before = _purchase()
    assert before.input_classification is None
    after = before.model_copy(update={"input_classification": InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE})
    live = _catalogue(after)

    current = evaluate_ledger_filing_staleness(_snapshot_of(before), live)
    assert current.is_stale is True
    assert current.changed == (before.transaction_id,)
    assert current.covers_current_fact_set is True

    historical = evaluate_ledger_filing_staleness(_sealed_under_v1(before), live)
    assert historical.is_stale is False
    assert historical.covers_current_fact_set is False


def test_an_untouched_ledger_does_not_restate_a_v1_snapshot() -> None:
    """The mass-false-alarm case: versioning exists to make this stay quiet."""
    purchase = _purchase()
    verdict = evaluate_ledger_filing_staleness(_sealed_under_v1(purchase), _catalogue(purchase))
    assert verdict.is_stale is False
    assert verdict.changed == ()
    assert verdict.removed == ()
    assert verdict.unchanged == (purchase.transaction_id,)
    assert verdict.covers_current_fact_set is False


def test_a_surcharge_cannot_drift_alone_so_v1_blindness_to_it_was_unreachable() -> None:
    """Precision about which half of the gap was real.

    A recargo-only difference does hash identically under V1, but the catalogue
    will not hold such a pair: base, cuota and surcharge must sum to the gross.
    Moving the surcharge therefore moves the cuota, which V1 already watched.
    """
    before = _purchase()
    carved = before.model_copy(update={"iva_amount": Decimal("31.60"), "recargo_amount": Decimal("10.40")})
    assert row_fingerprint(before, field_set_version=2) != row_fingerprint(carved, field_set_version=2)
    assert row_fingerprint(before, field_set_version=1) != row_fingerprint(carved, field_set_version=1)

    with pytest.raises(ValueError, match="must equal the gross"):
        _catalogue(before.model_copy(update={"recargo_amount": Decimal("10.40")}))


def test_a_new_capture_stamps_the_current_version_on_snapshot_and_evidence() -> None:
    """Evidence and snapshot must agree, or the bundle explains the wrong facts."""
    purchase = _purchase()
    snapshot = _snapshot_of(purchase)
    evidence = compute_ledger_filing_evidence(
        source_transaction_ids=[purchase.transaction_id],
        catalogue=_catalogue(purchase),
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        captured_at=_CAPTURED_AT,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    assert snapshot.fingerprint_field_set_version == CURRENT_FINGERPRINT_FIELD_SET_VERSION
    assert evidence.fingerprint_field_set_version == CURRENT_FINGERPRINT_FIELD_SET_VERSION


def test_the_widened_facts_reach_the_exported_evidence_row() -> None:
    """The record mirrors the fingerprint, so widening one widens both."""
    declared = _purchase().model_copy(
        update={"input_classification": InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE},
    )
    evidence = compute_ledger_filing_evidence(
        source_transaction_ids=[declared.transaction_id],
        catalogue=_catalogue(declared),
        snapshot_fingerprint="f" * 64,
        captured_at=_CAPTURED_AT,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    assert evidence.rows[0].input_classification == InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE.value
