"""Real-behaviour idempotency and duplicate-preservation proofs for manual ledger add.

No mocks: every case drives ``create_manual_transaction`` /
``import_ledger_transactions`` against a real encrypted
:class:`SecureObjectRepository`. Covers the guarded-idempotent keyed no-op
(P01), the same-key conflict refusal, the append-only keyless path (two genuine
identical same-day movements both persist), the content-fingerprint stamp (P02),
import-vs-manual interplay, and the adversarial hardening cases (3+ retries,
cross-bucket key reuse, zero-amount, boundary timestamps).
"""

from __future__ import annotations

from typing import TypedDict

import pytest
from pydantic import ValidationError

from ._action_test_support import (
    _BUCKET_ID,
    _OTHER_BUCKET_ID,
    UTC,
    BucketEventHistoryRepository,
    BucketEventType,
    BusinessClassification,
    Decimal,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionValidationError,
    _create_manual_row,
    _repositories,
    create_manual_transaction,
    date,
    datetime,
    import_ledger_transactions,
    parsed_import_transaction,
)
from ._action_test_support import secure_objects as secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["secure_objects"]

_DEFAULT_AMOUNT = Decimal("25.00")
_DEFAULT_BOOKED_DATE = date(2026, 5, 2)
_DEFAULT_OCCURRED_AT = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


class _ManualTransactionBaseArgs(TypedDict):
    """Base arguments for ManualLedgerTransactionCommand construction."""

    bucket_id: str
    booked_date: date
    amount: Decimal
    direction: TransactionDirection
    description: str
    idempotency_key: str


def _created_event_count(event_repository: BucketEventHistoryRepository, *, bucket_id: str = _BUCKET_ID) -> int:
    return sum(
        1
        for event in event_repository.load().for_bucket(bucket_id)
        if event.event_type is BucketEventType.LEDGER_TRANSACTION_CREATED
    )


def _add(
    transaction_repository: TransactionCatalogueRepository,
    event_repository: BucketEventHistoryRepository,
    *,
    description: str = "cash sale",
    amount: Decimal = _DEFAULT_AMOUNT,
    idempotency_key: str | None = None,
    booked_date: date = _DEFAULT_BOOKED_DATE,
    occurred_at: datetime = _DEFAULT_OCCURRED_AT,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    bucket_id: str = _BUCKET_ID,
):
    return create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=bucket_id,
            booked_date=booked_date,
            amount=amount,
            direction=direction,
            description=description,
            idempotency_key=idempotency_key,
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=occurred_at,
    )


def test_retried_keyed_add_is_guarded_noop(secure_objects: SecureObjectRepository) -> None:
    """Same key + identical content on retry: one row, one event, created_at unchanged, no-op signal."""
    repo, events, first = _create_manual_row(secure_objects, description="cash sale", idempotency_key="k-001")
    first_tx = repo.load().get(first.ref.transaction_id)
    assert first_tx is not None
    first_created_at = first_tx.created_at

    second = _add(repo, events, idempotency_key="k-001", occurred_at=datetime(2026, 5, 4, 10, 0, tzinfo=UTC))

    catalogue = repo.load()
    assert tuple(catalogue.transactions) == (first.ref.transaction_id,)
    assert second.ref.transaction_id == first.ref.transaction_id
    assert second.bucket_event_ids == ()
    assert _created_event_count(events) == 1
    second_tx = catalogue.get(second.ref.transaction_id)
    assert second_tx is not None
    assert second_tx.created_at == first_created_at


def test_keyed_add_three_retries_still_one_row_one_event(secure_objects: SecureObjectRepository) -> None:
    """3+ retries of an identical keyed add collapse to exactly one row and one creation event."""
    repo, events, first = _create_manual_row(secure_objects, description="cash sale", idempotency_key="k-002")
    for minute in (31, 32, 33):
        outcome = _add(repo, events, idempotency_key="k-002", occurred_at=datetime(2026, 5, 4, 9, minute, tzinfo=UTC))
        assert outcome.bucket_event_ids == ()
        assert outcome.ref.transaction_id == first.ref.transaction_id
    assert tuple(repo.load().transactions) == (first.ref.transaction_id,)
    assert _created_event_count(events) == 1


def test_interleaved_retry_through_fresh_repo_is_noop(secure_objects: SecureObjectRepository) -> None:
    """A retry observed through a fresh repository over the same store still no-ops.

    Models an interleaved/separate invocation: the single-writer upsert path
    (``_upsert_transaction`` + ``_save_transaction_catalogue_and_events``) loads
    the committed catalogue, so the second add reads the first's row and writes
    nothing rather than tearing a double-write.
    """
    repo, events, first = _create_manual_row(secure_objects, description="cash sale", idempotency_key="k-003")
    fresh_repo, fresh_events = _repositories(secure_objects)
    second = _add(fresh_repo, fresh_events, idempotency_key="k-003", occurred_at=datetime(2026, 5, 5, 8, 0, tzinfo=UTC))
    assert second.ref.transaction_id == first.ref.transaction_id
    assert second.bucket_event_ids == ()
    assert tuple(repo.load().transactions) == (first.ref.transaction_id,)
    assert _created_event_count(events) == 1


def test_same_key_different_content_raises_conflict(secure_objects: SecureObjectRepository) -> None:
    """Reusing a key for a different movement is a conflict refusal, never a silent overwrite."""
    repo, events, _ = _create_manual_row(secure_objects, description="cash sale", idempotency_key="k-004")
    with pytest.raises(TransactionValidationError):
        _add(repo, events, idempotency_key="k-004", amount=Decimal("99.00"), description="different movement")
    # The original row is untouched and no second row appeared.
    assert len(repo.load().transactions) == 1
    assert _created_event_count(events) == 1


def test_same_key_differing_only_in_recargo_raises_conflict(secure_objects: SecureObjectRepository) -> None:
    """A same-key add differing ONLY in recargo_amount is a conflict, never a silent no-op.

    Guards against a silent under-declaration: the idempotency match must include
    the recargo de equivalencia surcharge, or a retry that changes only the
    recargo would no-op and drop the new surcharge value.
    """
    repo, events = _repositories(secure_objects)
    base: _ManualTransactionBaseArgs = {
        "bucket_id": _BUCKET_ID,
        "booked_date": _DEFAULT_BOOKED_DATE,
        "amount": _DEFAULT_AMOUNT,
        "direction": TransactionDirection.OUTGOING,
        "description": "recargo sale",
        "idempotency_key": "rec-1",
    }
    create_manual_transaction(
        ManualLedgerTransactionCommand(**base, recargo_amount=Decimal("1.30")),
        transaction_repository=repo,
        bucket_event_repository=events,
        occurred_at=_DEFAULT_OCCURRED_AT,
    )
    with pytest.raises(TransactionValidationError):
        create_manual_transaction(
            ManualLedgerTransactionCommand(**base, recargo_amount=Decimal("2.60")),
            transaction_repository=repo,
            bucket_event_repository=events,
            occurred_at=datetime(2026, 5, 4, 10, 0, tzinfo=UTC),
        )
    assert len(repo.load().transactions) == 1
    assert _created_event_count(events) == 1


def test_same_key_differing_only_in_source_jurisdiction_raises_conflict(
    secure_objects: SecureObjectRepository,
) -> None:
    """A same-key add differing ONLY in source_jurisdiction is a conflict, never a silent no-op."""
    repo, events = _repositories(secure_objects)
    base: _ManualTransactionBaseArgs = {
        "bucket_id": _BUCKET_ID,
        "booked_date": _DEFAULT_BOOKED_DATE,
        "amount": _DEFAULT_AMOUNT,
        "direction": TransactionDirection.OUTGOING,
        "description": "cross-border sale",
        "idempotency_key": "jur-1",
    }
    create_manual_transaction(
        ManualLedgerTransactionCommand(**base, source_jurisdiction="ES"),
        transaction_repository=repo,
        bucket_event_repository=events,
        occurred_at=_DEFAULT_OCCURRED_AT,
    )
    with pytest.raises(TransactionValidationError):
        create_manual_transaction(
            ManualLedgerTransactionCommand(**base, source_jurisdiction="PT"),
            transaction_repository=repo,
            bucket_event_repository=events,
            occurred_at=datetime(2026, 5, 4, 10, 0, tzinfo=UTC),
        )
    assert len(repo.load().transactions) == 1
    assert _created_event_count(events) == 1


def test_same_key_differing_only_in_classified_by_override_raises_conflict(
    secure_objects: SecureObjectRepository,
) -> None:
    """A same-key add differing ONLY in classified_by_override is a conflict, never a silent no-op.

    ``classified_by_override`` is persisted content: the create path stamps it into
    ``Transaction.classified_by`` (falling back to ``manual``). An idempotency match
    that omitted it would return the stored row unchanged and silently drop the new
    classifier provenance — the failure mode
    ``single-subject-mutation-is-idempotent-guarded`` forbids.
    """
    repo, events = _repositories(secure_objects)
    base: _ManualTransactionBaseArgs = {
        "bucket_id": _BUCKET_ID,
        "booked_date": _DEFAULT_BOOKED_DATE,
        "amount": _DEFAULT_AMOUNT,
        "direction": TransactionDirection.OUTGOING,
        "description": "rule-classified sale",
        "idempotency_key": "cls-1",
    }
    first = create_manual_transaction(
        ManualLedgerTransactionCommand(
            **base,
            business_classification=BusinessClassification.BUSINESS,
            classified_by_override="rule:office-supplies",
        ),
        transaction_repository=repo,
        bucket_event_repository=events,
        occurred_at=_DEFAULT_OCCURRED_AT,
    )
    stored = repo.load().get(first.ref.transaction_id)
    assert stored is not None
    assert stored.classified_by == "rule:office-supplies"

    with pytest.raises(TransactionValidationError):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                **base,
                business_classification=BusinessClassification.BUSINESS,
                classified_by_override="rule:travel",
            ),
            transaction_repository=repo,
            bucket_event_repository=events,
            occurred_at=datetime(2026, 5, 4, 10, 0, tzinfo=UTC),
        )

    # The refusal is loud, and the stored provenance is neither overwritten nor lost.
    assert len(repo.load().transactions) == 1
    assert _created_event_count(events) == 1
    unchanged = repo.load().get(first.ref.transaction_id)
    assert unchanged is not None
    assert unchanged.classified_by == "rule:office-supplies"


def test_same_key_repeating_the_same_classified_by_override_is_a_noop(
    secure_objects: SecureObjectRepository,
) -> None:
    """A faithful retry carrying the same override still collapses to the guarded no-op.

    Anti-tautology companion to the conflict case above: the projection must
    discriminate a CHANGED override, not refuse every classified retry.
    """
    repo, events = _repositories(secure_objects)
    base: _ManualTransactionBaseArgs = {
        "bucket_id": _BUCKET_ID,
        "booked_date": _DEFAULT_BOOKED_DATE,
        "amount": _DEFAULT_AMOUNT,
        "direction": TransactionDirection.OUTGOING,
        "description": "rule-classified sale",
        "idempotency_key": "cls-2",
    }
    first = create_manual_transaction(
        ManualLedgerTransactionCommand(
            **base,
            business_classification=BusinessClassification.BUSINESS,
            classified_by_override="rule:office-supplies",
        ),
        transaction_repository=repo,
        bucket_event_repository=events,
        occurred_at=_DEFAULT_OCCURRED_AT,
    )
    retry = create_manual_transaction(
        ManualLedgerTransactionCommand(
            **base,
            business_classification=BusinessClassification.BUSINESS,
            classified_by_override="rule:office-supplies",
        ),
        transaction_repository=repo,
        bucket_event_repository=events,
        occurred_at=datetime(2026, 5, 4, 10, 0, tzinfo=UTC),
    )
    assert retry.ref.transaction_id == first.ref.transaction_id
    assert retry.bucket_event_ids == ()
    assert tuple(repo.load().transactions) == (first.ref.transaction_id,)
    assert _created_event_count(events) == 1


def test_deliberate_duplicate_via_distinct_keys_two_rows(secure_objects: SecureObjectRepository) -> None:
    """Two genuinely-distinct movements with identical content but distinct keys both persist."""
    repo, events, first = _create_manual_row(secure_objects, description="retainer", idempotency_key="dup-A")
    second = _add(repo, events, description="retainer", idempotency_key="dup-B")
    assert first.ref.transaction_id != second.ref.transaction_id
    assert set(repo.load().transactions) == {first.ref.transaction_id, second.ref.transaction_id}
    assert _created_event_count(events) == 2


def test_keyless_identical_same_day_movements_both_persist(secure_objects: SecureObjectRepository) -> None:
    """The keyless path is append-only: two identical same-day cash movements both persist."""
    repo, events = _repositories(secure_objects)
    first = _add(repo, events, description="cash tip", occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC))
    second = _add(repo, events, description="cash tip", occurred_at=datetime(2026, 5, 4, 14, 15, tzinfo=UTC))
    assert first.ref.transaction_id != second.ref.transaction_id
    assert set(repo.load().transactions) == {first.ref.transaction_id, second.ref.transaction_id}
    assert first.bucket_event_ids and second.bucket_event_ids
    assert _created_event_count(events) == 2


def test_same_key_across_two_buckets_yields_two_distinct_rows(secure_objects: SecureObjectRepository) -> None:
    """A reused idempotency key in a different bucket is a distinct row (bucket-scoped id), no false no-op."""
    repo_a, _events_a, first = _create_manual_row(secure_objects, description="cash sale", idempotency_key="shared")
    repo_b, events_b = _repositories(secure_objects, bucket_id=_OTHER_BUCKET_ID)
    second = _add(repo_b, events_b, idempotency_key="shared", bucket_id=_OTHER_BUCKET_ID)
    assert first.ref.transaction_id != second.ref.transaction_id
    assert second.bucket_event_ids != ()
    assert tuple(repo_a.load().transactions) == (first.ref.transaction_id,)
    assert tuple(repo_b.load().transactions) == (second.ref.transaction_id,)


def test_zero_amount_add_is_refused_not_silently_deduped(secure_objects: SecureObjectRepository) -> None:
    """A zero-amount manual add is refused at the command boundary, never silently created or deduped."""
    repo, events = _repositories(secure_objects)
    with pytest.raises(ValidationError, match="non-zero"):
        _add(repo, events, amount=Decimal("0"), description="zero correction", idempotency_key="z-1")
    assert len(repo.load().transactions) == 0


def test_keyed_retry_is_clock_free_across_boundary_timestamps(secure_objects: SecureObjectRepository) -> None:
    """The keyed id is clock-free: a retry at a boundary timestamp still resolves to the no-op."""
    repo, events, first = _create_manual_row(
        secure_objects,
        description="cash sale",
        idempotency_key="bound-1",
        occurred_at=datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC),
    )
    retry = _add(repo, events, idempotency_key="bound-1", occurred_at=datetime(2026, 5, 4, 23, 59, 59, tzinfo=UTC))
    assert retry.ref.transaction_id == first.ref.transaction_id
    assert retry.bucket_event_ids == ()
    assert tuple(repo.load().transactions) == (first.ref.transaction_id,)


def test_manual_row_carries_content_fingerprint_surviving_reload(secure_objects: SecureObjectRepository) -> None:
    """Roundtrip a created manual row's content fingerprint across the encrypted boundary.

    Strengthened beyond a presence check: the full row is compared for strict
    equality across a FRESH repository over the same store (so the non-default
    ``import_fingerprint`` genuinely roundtrips, not merely re-defaults), and an
    anti-tautology leg proves the fingerprint is content-bound rather than a
    constant — a different movement yields a different fingerprint, so a dropped
    or content-independent fingerprint would surface as an inequality here.
    """
    repo, _events, created = _create_manual_row(secure_objects, description="cash sale", idempotency_key="fp-1")
    original = repo.load().get(created.ref.transaction_id)
    assert original is not None
    assert original.import_fingerprint is not None
    assert len(original.import_fingerprint) == 64
    assert all(char in "0123456789abcdef" for char in original.import_fingerprint)

    # Strict save->load equality across a fresh repository reading the same store:
    # every field, the non-default import_fingerprint included, roundtrips exactly.
    fresh_repo, _fresh_events = _repositories(secure_objects)
    reloaded = fresh_repo.load().get(created.ref.transaction_id)
    assert reloaded is not None
    assert reloaded == original

    # Anti-tautology: the fingerprint is content-derived, not a constant. A row
    # with different content produces a different fingerprint.
    other_repo, other_events = _repositories(secure_objects, bucket_id=_OTHER_BUCKET_ID)
    other = _add(
        other_repo,
        other_events,
        description="a different movement",
        amount=Decimal("77.00"),
        bucket_id=_OTHER_BUCKET_ID,
    )
    other_row = other_repo.load().get(other.ref.transaction_id)
    assert other_row is not None
    assert other_row.import_fingerprint is not None
    assert other_row.import_fingerprint != original.import_fingerprint


def test_import_recognises_a_prior_manual_movement(secure_objects: SecureObjectRepository) -> None:
    """A movement entered manually is recognised by a later import of the same movement (no reduplication)."""
    repo, events, manual = _create_manual_row(
        secure_objects,
        description="provider import row",
        idempotency_key="m-1",
        amount=Decimal("80.00"),
        booked_date=date(2026, 5, 1),
    )
    outcome = import_ledger_transactions(
        bucket_id=_BUCKET_ID,
        parsed_rows=(parsed_import_transaction(),),
        transaction_repository=repo,
        bucket_event_repository=events,
        occurred_at=datetime(2026, 5, 6, 9, 0, tzinfo=UTC),
    )
    assert outcome.summary.imported == 0
    assert outcome.summary.skipped == 1
    assert tuple(repo.load().transactions) == (manual.ref.transaction_id,)
