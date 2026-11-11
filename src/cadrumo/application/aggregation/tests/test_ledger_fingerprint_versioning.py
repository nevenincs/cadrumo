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

V3 adds the two admission facts the manual edit path can change without moving
any V2 fact: the bienes de inversion link and the customer's identifying Member
State. Snapshots and evidence stored under V1 or V2 keep loading and keep their
own answer.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.hashing import sha256_hex
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.prorrata import InputClassification
from ....domain.iva.schema import EUMemberState
from ....domain.iva.vehicle_use import IvaVehicleUse
from ....domain.modelos.errors import ModeloValidationError
from ....domain.modelos.ledger_filing_snapshot import LedgerEvidenceRow, LedgerFilingEvidence, LedgerFilingSnapshot
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..ledger_filing_snapshot import (
    ACCRUAL_DATE_FIELD_SET_VERSION,
    CURRENT_FINGERPRINT_FIELD_SET_VERSION,
    FINGERPRINT_FIELDS_V1,
    FINGERPRINT_FIELDS_V2,
    FINGERPRINT_FIELDS_V3,
    FINGERPRINT_FIELDS_V5,
    FINGERPRINT_FIELDS_V6,
    FINGERPRINT_FIELDS_V7,
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
    evaluate_ledger_filing_staleness,
    row_fingerprint,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = filing_year_envelope().horizon
_BOOKED = date(_YEAR, 2, 10)
_ACCRUAL = date(_YEAR, 3, 30)
_MOVED_OPERATION = date(_YEAR, 4, 2)
_CAPTURED_AT = datetime(1980, 1, 1, tzinfo=UTC)
_LEGAL_REFS = ("ley-37-1992-art-97",)
_SOURCE_REFS = ("aeat-modelo-303",)


def _iva_transaction(transaction_id: str, *, direction: TransactionDirection, taxable_base: Decimal) -> Transaction:
    """Build the minimal transaction needed by the fingerprint contract tests."""
    booked_date = _BOOKED
    iva_amount = (taxable_base * Decimal("0.21")).quantize(Decimal("0.01"))
    fields: dict[str, object] = {
        "raw": RawTransaction(
            provider_transaction_id=transaction_id,
            booked_date=booked_date,
            value_date=booked_date,
            amount=taxable_base + iva_amount,
            currency="EUR",
            counterparty="Cliente o proveedor",
            description=f"fingerprint row {transaction_id}",
            provenance=RawProvenance(
                source_path=Path(__file__),
                source_sha256="e" * 64,
                source_row_index=1,
                source_format=SourceFormat.MANUAL,
                ingested_at=_CAPTURED_AT,
                provider_name="manual-ledger",
            ),
            raw_fields={"source_kind": "ledger_transaction"},
        ),
        "direction": direction,
        "group_label": None,
        "source_jurisdiction": "ES",
        "business_classification": BusinessClassification.BUSINESS,
        "category_id": "material_oficina",
        "taxable_base": taxable_base,
        "iva_rate": Decimal("0.21"),
        "iva_amount": iva_amount,
        "classified_at": _CAPTURED_AT,
        "classified_by": "manual",
    }
    if direction is TransactionDirection.OUTGOING:
        fields["deduction_fact_kind"] = IvaDeductionFactKind.from_registry("domestic_current")
        fields["deduction_provenance"] = IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
            source_locator=f"invoice:{transaction_id}",
            evidence_digest="a" * 64,
        )
    return Transaction.model_validate(fields)


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
    assert FINGERPRINT_FIELDS_V2[: len(FINGERPRINT_FIELDS_V1)] == FINGERPRINT_FIELDS_V1
    assert len(FINGERPRINT_FIELDS_V2) == len(FINGERPRINT_FIELDS_V1) + 7


def test_v3_appends_exactly_the_two_admission_facts_to_v2() -> None:
    assert FINGERPRINT_FIELDS_V3[: len(FINGERPRINT_FIELDS_V2)] == FINGERPRINT_FIELDS_V2
    assert FINGERPRINT_FIELDS_V3[len(FINGERPRINT_FIELDS_V2) :] == (
        ("investment_asset_id", "investment_asset_id"),
        ("counterparty_identification_state", "counterparty_identification_state"),
    )


def test_v5_appends_the_operation_date_and_the_evidence_facts_and_is_current() -> None:
    assert FINGERPRINT_FIELDS_V5[: len(FINGERPRINT_FIELDS_V3)] == FINGERPRINT_FIELDS_V3
    assert [label for label, _path in FINGERPRINT_FIELDS_V5[len(FINGERPRINT_FIELDS_V3) :]] == [
        "operation_date",
        "purchase_invoice_evidence_id",
        "deduction_authority",
        "deduction_source_locator",
        "deduction_evidence_digest",
    ]


@pytest.mark.parametrize("version", [1, 2, 3])
def test_the_older_field_sets_do_not_see_a_new_operation_date_or_a_detached_evidence(version: int) -> None:
    purchase = _purchase()
    moved = purchase.model_copy(update={"operation_date": _ACCRUAL, "deduction_provenance": None})
    assert row_fingerprint(moved, field_set_version=version) == row_fingerprint(purchase, field_set_version=version)
    assert row_fingerprint(moved, field_set_version=5) != row_fingerprint(purchase, field_set_version=5)


def test_v6_appends_exactly_the_stated_vehicle_use_to_v5() -> None:
    assert FINGERPRINT_FIELDS_V6[: len(FINGERPRINT_FIELDS_V5)] == FINGERPRINT_FIELDS_V5
    assert FINGERPRINT_FIELDS_V6[len(FINGERPRINT_FIELDS_V5) :] == (("iva_vehicle_use", "iva_vehicle_use"),)


def test_v7_appends_exactly_the_stated_accrual_date_to_v6_and_is_current() -> None:
    assert FINGERPRINT_FIELDS_V7[: len(FINGERPRINT_FIELDS_V6)] == FINGERPRINT_FIELDS_V6
    assert FINGERPRINT_FIELDS_V7[len(FINGERPRINT_FIELDS_V6) :] == (("accrual_date", "accrual_date"),)
    assert CURRENT_FINGERPRINT_FIELD_SET_VERSION == 7
    assert ACCRUAL_DATE_FIELD_SET_VERSION == 7


@pytest.mark.parametrize("version", [1, 2, 3, 5, 6])
def test_a_stated_accrual_date_is_drift_under_v7_and_quiet_under_every_older_field_set(version: int) -> None:
    purchase = _purchase()
    stated = purchase.model_copy(update={"accrual_date": _ACCRUAL})
    assert row_fingerprint(stated, field_set_version=version) == row_fingerprint(purchase, field_set_version=version)
    assert row_fingerprint(stated, field_set_version=7) != row_fingerprint(purchase, field_set_version=7)


def _evidence_row_of(transaction: Transaction) -> LedgerEvidenceRow:
    evidence = compute_ledger_filing_evidence(
        source_transaction_ids=[transaction.transaction_id],
        catalogue=_catalogue(transaction),
        snapshot_fingerprint=_snapshot_of(transaction).snapshot_fingerprint,
        captured_at=_CAPTURED_AT,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    return evidence.rows[0]


def test_an_iva_operation_date_change_alone_leaves_the_accrual_date_alone() -> None:
    """The two dates are separate facts: moving the IVA devengo never rewrites the Renta one."""
    stated = _purchase().model_copy(update={"accrual_date": _ACCRUAL})
    moved = stated.model_copy(update={"operation_date": _MOVED_OPERATION})
    assert moved.accrual_date == stated.accrual_date == _ACCRUAL
    assert row_fingerprint(moved, field_set_version=6) != row_fingerprint(stated, field_set_version=6)
    assert row_fingerprint(moved) != row_fingerprint(stated)

    before_row = _evidence_row_of(stated)
    after_row = _evidence_row_of(moved)
    assert before_row.accrual_date == after_row.accrual_date == _ACCRUAL.isoformat()
    assert before_row.operation_date is None
    assert after_row.operation_date == _MOVED_OPERATION.isoformat()


def test_the_evidence_row_carries_the_stated_accrual_date_and_an_older_row_loads_without_it() -> None:
    purchase = _purchase()
    stated = purchase.model_copy(update={"accrual_date": _ACCRUAL})
    assert _evidence_row_of(purchase).accrual_date is None
    assert _evidence_row_of(stated).accrual_date == _ACCRUAL.isoformat()
    older = {key: value for key, value in _evidence_row_of(purchase).model_dump().items() if key != "accrual_date"}
    assert LedgerEvidenceRow.model_validate(older).accrual_date is None


def test_a_v6_snapshot_stays_quiet_on_an_accrual_date_and_a_current_one_drifts() -> None:
    before = _purchase()
    stated = before.model_copy(update={"accrual_date": _ACCRUAL})
    v6 = _sealed_under_v6(before)
    assert v6.fingerprint_field_set_version == 6
    narrower = evaluate_ledger_filing_staleness(v6, _catalogue(stated))
    assert narrower.is_stale is False
    assert narrower.covers_current_fact_set is False
    current = evaluate_ledger_filing_staleness(_snapshot_of(before), _catalogue(stated))
    assert current.is_stale is True
    assert current.changed == (before.transaction_id,)


def _sealed_under_v6(transaction: Transaction) -> LedgerFilingSnapshot:
    live = _snapshot_of(transaction)
    return live.model_copy(
        update={
            "fingerprint_field_set_version": 6,
            "rows": tuple(
                row.model_copy(update={"fingerprint": row_fingerprint(transaction, field_set_version=6)})
                for row in live.rows
            ),
        },
    )


@pytest.mark.parametrize("version", [1, 2, 3, 5])
def test_a_stated_vehicle_use_is_drift_under_v6_and_quiet_under_every_older_field_set(version: int) -> None:
    purchase = _purchase()
    stated = purchase.model_copy(update={"iva_vehicle_use": IvaVehicleUse.SURVEILLANCE})
    assert row_fingerprint(stated, field_set_version=version) == row_fingerprint(purchase, field_set_version=version)
    assert row_fingerprint(stated, field_set_version=6) != row_fingerprint(purchase, field_set_version=6)


def _sealed_under_v5(transaction: Transaction) -> LedgerFilingSnapshot:
    """A snapshot as the V5 build wrote it: V5 hashes under a V5 stamp."""
    live = _snapshot_of(transaction)
    return live.model_copy(
        update={
            "fingerprint_field_set_version": 5,
            "rows": tuple(
                row.model_copy(update={"fingerprint": row_fingerprint(transaction, field_set_version=5)})
                for row in live.rows
            ),
        },
    )


def test_a_v5_snapshot_stays_quiet_on_a_vehicle_use_and_on_an_untouched_row() -> None:
    """Stored V5 anchors are compared under V5 forever: no false drift, no rehash."""
    before = _purchase()
    stated = before.model_copy(update={"iva_vehicle_use": IvaVehicleUse.SURVEILLANCE})

    untouched = evaluate_ledger_filing_staleness(_sealed_under_v5(before), _catalogue(before))
    assert untouched.is_stale is False
    assert untouched.unchanged == (before.transaction_id,)

    narrower = evaluate_ledger_filing_staleness(_sealed_under_v5(before), _catalogue(stated))
    assert narrower.is_stale is False
    assert narrower.covers_current_fact_set is False


def test_a_v5_snapshot_still_detects_drift_in_a_v5_fact() -> None:
    before = _purchase()
    after = before.model_copy(update={"operation_date": _ACCRUAL})
    verdict = evaluate_ledger_filing_staleness(_sealed_under_v5(before), _catalogue(after))
    assert verdict.is_stale is True
    assert verdict.changed == (before.transaction_id,)


def test_a_current_snapshot_drifts_when_the_stated_vehicle_use_changes() -> None:
    before = _purchase()
    stated = before.model_copy(update={"iva_vehicle_use": IvaVehicleUse.SURVEILLANCE})
    verdict = evaluate_ledger_filing_staleness(_snapshot_of(before), _catalogue(stated))
    assert verdict.is_stale is True
    assert verdict.changed == (before.transaction_id,)
    assert verdict.covers_current_fact_set is True


def _with_admission_facts(transaction: Transaction) -> Transaction:
    return transaction.model_copy(
        update={
            "investment_asset_id": "bien-inversion-0001",
            "counterparty_identification_state": EUMemberState.from_registry("FR"),
        },
    )


def _rendered(transaction: Transaction, path: str) -> str:
    """Render one field the way stored V1/V2 hashes rendered it, written out independently."""
    target: object = transaction
    for attr in path.split("."):
        target = None if target is None else getattr(target, attr)
    if target is None:
        return ""
    if isinstance(target, date):
        return target.isoformat()
    inner = getattr(target, "value", None)
    return inner if isinstance(inner, str) else str(target)


def test_v2_was_not_widened_in_place_so_its_hashes_ignore_the_v3_facts() -> None:
    """A V2 hash recomputed today must equal the one an older build sealed."""
    before = _purchase()
    after = _with_admission_facts(before)
    v2_canonical = "|".join(f"{label}={_rendered(before, path)}" for label, path in FINGERPRINT_FIELDS_V2)
    assert row_fingerprint(after, field_set_version=2) == sha256_hex(v2_canonical.encode("utf-8"))
    assert row_fingerprint(before, field_set_version=2) == row_fingerprint(after, field_set_version=2)
    assert row_fingerprint(before, field_set_version=1) == row_fingerprint(after, field_set_version=1)
    assert row_fingerprint(before, field_set_version=3) != row_fingerprint(after, field_set_version=3)


def test_the_v3_canonical_string_renders_each_admission_fact_by_its_value() -> None:
    """The hashed form is the V2 string plus two ``label=value`` pairs, in order."""
    transaction = _with_admission_facts(_purchase())
    v2_canonical = "|".join(f"{label}={_rendered(transaction, path)}" for label, path in FINGERPRINT_FIELDS_V2)
    expected = sha256_hex(
        f"{v2_canonical}|investment_asset_id=bien-inversion-0001|counterparty_identification_state=FR".encode(),
    )
    assert row_fingerprint(transaction, field_set_version=3) == expected


def _sealed_under_v2(transaction: Transaction) -> LedgerFilingSnapshot:
    """A snapshot as the previous build wrote them: V2 hashes under a V2 stamp."""
    live = _snapshot_of(transaction)
    return live.model_copy(
        update={
            "fingerprint_field_set_version": 2,
            "rows": tuple(
                row.model_copy(update={"fingerprint": row_fingerprint(transaction, field_set_version=2)})
                for row in live.rows
            ),
        },
    )


@pytest.mark.parametrize(
    "update",
    [
        {"investment_asset_id": "bien-inversion-0001"},
        {"counterparty_identification_state": EUMemberState.from_registry("FR")},
    ],
    ids=["investment_asset_id", "counterparty_identification_state"],
)
def test_a_v2_snapshot_stays_quiet_on_a_v3_fact_and_says_it_is_narrower(update: dict[str, object]) -> None:
    """Stored V2 anchors are compared under V2 forever: no false drift, no rehash."""
    before = _purchase()
    after = before.model_copy(update=update)

    historical = evaluate_ledger_filing_staleness(_sealed_under_v2(before), _catalogue(after))
    assert historical.is_stale is False
    assert historical.unchanged == (before.transaction_id,)
    assert historical.covers_current_fact_set is False

    current = evaluate_ledger_filing_staleness(_snapshot_of(before), _catalogue(after))
    assert current.is_stale is True
    assert current.changed == (before.transaction_id,)
    assert current.covers_current_fact_set is True


def test_a_v2_snapshot_still_detects_drift_in_a_v2_fact() -> None:
    before = _purchase()
    after = before.model_copy(
        update={"input_classification": InputClassification.from_registry("exclusively_non_deductible")},
    )
    verdict = evaluate_ledger_filing_staleness(_sealed_under_v2(before), _catalogue(after))
    assert verdict.is_stale is True
    assert verdict.changed == (before.transaction_id,)
    assert verdict.covers_current_fact_set is False


def test_a_version_this_build_does_not_know_is_refused_not_approximated() -> None:
    """A snapshot from a newer build must not be compared under a narrower set."""
    with pytest.raises(ModeloValidationError, match="unknown to this build"):
        row_fingerprint(_purchase(), field_set_version=99)
    with pytest.raises(ModeloValidationError, match="unknown to this build"):
        row_fingerprint(_purchase(), field_set_version=8)


def test_a_stored_snapshot_stamped_with_an_unknown_version_is_refused_at_comparison() -> None:
    purchase = _purchase()
    unknown = _snapshot_of(purchase).model_copy(update={"fingerprint_field_set_version": 8})
    with pytest.raises(ModeloValidationError, match=r"known versions are \[1, 2, 3, 5, 6, 7\]"):
        evaluate_ledger_filing_staleness(unknown, _catalogue(purchase))


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
    after = before.model_copy(
        update={"input_classification": InputClassification.from_registry("exclusively_non_deductible")}
    )
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
        update={"input_classification": InputClassification.from_registry("exclusively_non_deductible")},
    )
    evidence = compute_ledger_filing_evidence(
        source_transaction_ids=[declared.transaction_id],
        catalogue=_catalogue(declared),
        snapshot_fingerprint="f" * 64,
        captured_at=_CAPTURED_AT,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    assert (
        evidence.rows[0].input_classification == InputClassification.from_registry("exclusively_non_deductible").value
    )


def test_the_v3_admission_facts_reach_the_exported_evidence_row() -> None:
    declared = _with_admission_facts(_purchase())
    evidence = compute_ledger_filing_evidence(
        source_transaction_ids=[declared.transaction_id],
        catalogue=_catalogue(declared),
        snapshot_fingerprint="f" * 64,
        captured_at=_CAPTURED_AT,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    (row,) = evidence.rows
    assert row.investment_asset_id == "bien-inversion-0001"
    assert row.counterparty_identification_state == "FR"
    assert row.fingerprint == row_fingerprint(declared, field_set_version=CURRENT_FINGERPRINT_FIELD_SET_VERSION)


@pytest.mark.parametrize("version", [1, 2])
def test_a_bundle_stored_before_v3_hydrates_unchanged_and_compares_under_its_own_version(version: int) -> None:
    """A persisted pre-V3 bundle carries no V3 keys; it must load and keep its answer."""
    purchase = _purchase()
    fingerprint = row_fingerprint(purchase, field_set_version=version)
    stored_json = json.dumps(
        {
            "snapshot_fingerprint": "f" * 64,
            "captured_at": _CAPTURED_AT.isoformat(),
            "fingerprint_field_set_version": version,
            "rows": [
                {
                    "transaction_id": purchase.transaction_id,
                    "fingerprint": fingerprint,
                    "booked_date": _BOOKED.isoformat(),
                    "value_date": _BOOKED.isoformat(),
                    "amount": "242.00",
                    "currency": "EUR",
                    "direction": purchase.direction.value,
                    "business_classification": purchase.business_classification.value,
                    "taxable_base": "200.00",
                    "iva_rate": "0.21",
                    "iva_amount": "42.00",
                    "lifecycle_state": purchase.lifecycle_state.value,
                    "legal_refs": list(_LEGAL_REFS),
                    "source_refs": list(_SOURCE_REFS),
                },
            ],
        },
    )
    stored = LedgerFilingEvidence.model_validate_json(stored_json)
    (row,) = stored.rows
    assert stored.fingerprint_field_set_version == version
    assert row.investment_asset_id is None
    assert row.counterparty_identification_state is None

    stored_snapshot = LedgerFilingSnapshot.model_validate_json(
        json.dumps(
            {
                "rows": [{"transaction_id": row.transaction_id, "fingerprint": row.fingerprint}],
                "snapshot_fingerprint": "f" * 64,
                "captured_at": _CAPTURED_AT.isoformat(),
                "fingerprint_field_set_version": version,
            },
        ),
    )
    verdict = evaluate_ledger_filing_staleness(stored_snapshot, _catalogue(_with_admission_facts(purchase)))
    assert verdict.is_stale is False
    assert verdict.unchanged == (purchase.transaction_id,)
    assert verdict.covers_current_fact_set is False
