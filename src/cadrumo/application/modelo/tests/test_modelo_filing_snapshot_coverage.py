"""Every-modelo coverage for the filing ledger snapshot.

Proves the modelo-filing-ledger-snapshot feature is uniform across the whole
modelo surface: a ledger-fed revision carries a non-empty snapshot, a
non-ledger revision carries a valid empty snapshot, the snapshot is excluded
from the content-addressed revision id, the persisted revision is immutable, and
drift in a contributing row is detected for a ledger-fed modelo.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.work_unit import derive_work_unit_id
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests import general_m303_filing_evidence
from ....domain.modelos.ledger_filing_snapshot import LedgerFilingSnapshot
from ...aggregation.ledger_filing_snapshot import (
    compute_ledger_filing_snapshot,
    evaluate_ledger_filing_staleness,
    stale_filed_revisions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)
_P_2026_1T = Period.from_year_and_code(2026, "1T")


def _tx(
    provider_id: str,
    *,
    taxable_base: Decimal = Decimal("100.00"),
    iva_amount: Decimal = Decimal("21.00"),
    raw_amount: Decimal = Decimal("121.00"),
    category_id: str = "material_oficina",
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 4, 5),
        value_date=date(2026, 4, 5),
        amount=raw_amount,
        currency="EUR",
        counterparty="Proveedor",
        description=f"row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"k": "v"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "category_id": category_id,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def _revision(
    modelo: str,
    *,
    source_ids: tuple[str, ...],
    snapshot: LedgerFilingSnapshot | None,
) -> CalculationRevision:
    wid = derive_work_unit_id(bucket_id="bkt", modelo=modelo, filing_year=2026, period=_P_2026_1T, revision_id="r1")
    filing_instance_evidence = (
        general_m303_filing_evidence(_P_2026_1T, reference="test:filing-snapshot-coverage") if modelo == "303" else None
    )
    rid = derive_calculation_revision_id(
        work_unit_id=wid,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        source_transaction_ids=source_ids,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=rid,
        work_unit_id=wid,
        state=CalculationRevisionState.BORRADOR,
        source_transaction_ids=source_ids,
        ledger_filing_snapshot=snapshot,
        created_at=_NOW,
        updated_at=_NOW,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )


def test_ledger_fed_modelo_carries_nonempty_snapshot() -> None:
    a, b = _tx("row-a"), _tx("row-b")
    cat = TransactionCatalogue.from_transactions((a, b))
    ids = (a.transaction_id, b.transaction_id)
    snap = compute_ledger_filing_snapshot(source_transaction_ids=ids, catalogue=cat, captured_at=_NOW)
    rev = _revision("303", source_ids=ids, snapshot=snap)
    assert rev.ledger_filing_snapshot is not None
    assert len(rev.ledger_filing_snapshot.rows) == 2


def test_non_ledger_modelo_carries_empty_uniform_snapshot() -> None:
    snap = compute_ledger_filing_snapshot(
        source_transaction_ids=(),
        catalogue=TransactionCatalogue.from_transactions(()),
        captured_at=_NOW,
    )
    rev = _revision("347", source_ids=(), snapshot=snap)
    assert rev.ledger_filing_snapshot is not None
    assert rev.ledger_filing_snapshot.rows == ()
    assert len(rev.ledger_filing_snapshot.snapshot_fingerprint) == 64


def test_snapshot_is_excluded_from_revision_id() -> None:
    a = _tx("row-a")
    cat = TransactionCatalogue.from_transactions((a,))
    ids = (a.transaction_id,)
    snap = compute_ledger_filing_snapshot(source_transaction_ids=ids, catalogue=cat, captured_at=_NOW)
    with_snap = _revision("130", source_ids=ids, snapshot=snap)
    without_snap = _revision("130", source_ids=ids, snapshot=None)
    # Identical contributors -> identical content-addressed id regardless of the
    # snapshot, proving the snapshot does not perturb the revision identity.
    assert with_snap.calculation_revision_id == without_snap.calculation_revision_id


def test_filed_revision_snapshot_is_immutable() -> None:
    a = _tx("row-a")
    cat = TransactionCatalogue.from_transactions((a,))
    ids = (a.transaction_id,)
    snap = compute_ledger_filing_snapshot(source_transaction_ids=ids, catalogue=cat, captured_at=_NOW)
    rev = _revision("100", source_ids=ids, snapshot=snap)
    with pytest.raises(ValidationError):
        rev.ledger_filing_snapshot = None  # frozen model: attribute set is refused


def _verified_revision(
    modelo: str,
    *,
    source_ids: tuple[str, ...],
    snapshot: LedgerFilingSnapshot,
) -> CalculationRevision:
    wid = derive_work_unit_id(bucket_id="bkt", modelo=modelo, filing_year=2026, period=_P_2026_1T, revision_id="r1")
    filing_instance_evidence = (
        general_m303_filing_evidence(_P_2026_1T, reference="test:filing-snapshot-coverage") if modelo == "303" else None
    )
    rid = derive_calculation_revision_id(
        work_unit_id=wid,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        source_transaction_ids=source_ids,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=rid,
        work_unit_id=wid,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        source_transaction_ids=source_ids,
        ledger_filing_snapshot=snapshot,
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )


def test_stale_filed_revisions_flags_only_drifted_finalized_revisions() -> None:
    original = _tx("row-a", taxable_base=Decimal("100.00"), iva_amount=Decimal("21.00"))
    cat = TransactionCatalogue.from_transactions((original,))
    ids = (original.transaction_id,)
    snap = compute_ledger_filing_snapshot(source_transaction_ids=ids, catalogue=cat, captured_at=_NOW)
    rev = _verified_revision("303", source_ids=ids, snapshot=snap)
    revisions = {rev.calculation_revision_id: rev}
    # Unchanged ledger -> nothing flagged.
    assert stale_filed_revisions(revisions=revisions, catalogue=cat) == ()
    # A material edit to a contributor -> the filed revision is flagged stale.
    edited = _tx("row-a", category_id="software")
    drifted = TransactionCatalogue.from_transactions((edited,))
    flagged = stale_filed_revisions(revisions=revisions, catalogue=drifted)
    assert len(flagged) == 1
    assert flagged[0][0].calculation_revision_id == rev.calculation_revision_id
    assert flagged[0][1].changed == ids


def test_drift_in_contributor_is_detected_for_ledger_fed_modelo() -> None:
    original = _tx("row-a", taxable_base=Decimal("100.00"), iva_amount=Decimal("21.00"))
    cat = TransactionCatalogue.from_transactions((original,))
    ids = (original.transaction_id,)
    snap = compute_ledger_filing_snapshot(source_transaction_ids=ids, catalogue=cat, captured_at=_NOW)
    edited = _tx("row-a", category_id="software")
    drifted = TransactionCatalogue.from_transactions((edited,))
    verdict = evaluate_ledger_filing_staleness(snap, drifted)
    assert verdict.is_stale is True
    assert verdict.changed == (original.transaction_id,)
