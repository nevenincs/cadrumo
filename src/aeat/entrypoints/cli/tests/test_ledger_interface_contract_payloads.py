"""Pydantic construction / validation / serialisation suite for the
ledger-interface-contract payload schemas (D1, D2, D6).

Exercises the typed CLI envelopes the ledger-interface-contract ADR settled —
the uniform mutation quintet (D1), the typed list-row payload that replaces the
former bare ``dict[str, object]`` boundary (D2), and the persistence-record
lifecycle timestamps (D6) — directly as pydantic models (no CLI runner, no
mocks). These lock the schema shape, the strict extra-forbid contract, and the
JSON round-trip.
"""

from __future__ import annotations

import pytest

from .._ledger_payloads import (
    LedgerAddResult,
    LedgerClassifyBulkResult,
    LedgerClassifyLlmSaturateResult,
    LedgerClassifyLlmSuggestResult,
    LedgerClassifySingleResult,
    LedgerHistoryEventPayload,
    LedgerHistoryResult,
    LedgerImportTransactionRefPayload,
    LedgerLinkEvidenceUpdatePayload,
    LedgerLinkResult,
    LedgerListRowPayload,
    TransactionPayload,
    _LedgerMutationResult,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _transaction_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "transaction_id": "a" * 64,
        "date": "2024-04-10",
        "booked_date": "2024-04-10",
        "amount": "100.00",
        "currency": "EUR",
        "direction": "OUTGOING",
        "description": "Compra material",
        "business_classification": "BUSINESS",
        "lifecycle_state": "ACTIVE",
        "classified_by": "manual",
        "created_at": "2024-04-10T09:30:00+00:00",
        "modified_at": "2024-06-01T16:45:00+00:00",
    }
    base.update(overrides)
    return base


def test_add_result_subclasses_mutation_quintet_and_carries_review_status() -> None:
    """D1: LedgerAddResult is a _LedgerMutationResult and carries review_status."""
    assert issubclass(LedgerAddResult, _LedgerMutationResult)
    result = LedgerAddResult.model_validate(
        {
            "bucket_id": "default",
            "transaction_id": "a" * 64,
            "bucket_event_ids": ["e" * 64],
            "review_status": "pending",
            "transaction": _transaction_payload(),
        },
    )
    assert result.review_status == "pending"
    # Round-trips through JSON without losing the quintet.
    dumped = result.model_dump(mode="json")
    assert set(dumped) >= {"bucket_id", "transaction_id", "bucket_event_ids", "review_status", "transaction"}
    assert LedgerAddResult.model_validate(dumped) == result


def test_classify_single_result_is_the_mutation_quintet() -> None:
    """D1: the single-transaction classify path returns the mutation quintet."""
    assert issubclass(LedgerClassifySingleResult, _LedgerMutationResult)
    result = LedgerClassifySingleResult.model_validate(
        {
            "bucket_id": "default",
            "transaction_id": "a" * 64,
            "bucket_event_ids": [],
            "review_status": "reviewed",
            "transaction": _transaction_payload(),
        },
    )
    assert result.transaction.created_at == "2024-04-10T09:30:00+00:00"


def test_classify_branches_are_distinct_discriminated_shapes() -> None:
    """D1: bulk / llm-suggest / llm-saturate are distinct, non-optional branches."""
    bulk = LedgerClassifyBulkResult.model_validate(
        {"total": 10, "applied": 7, "skipped": 2, "failures": []},
    )
    assert bulk.total == 10 and bulk.applied == 7

    suggest = LedgerClassifyLlmSuggestResult.model_validate(
        {"llm": True, "provider": "claude", "transaction_id": "a" * 64, "persisted": False},
    )
    assert suggest.persisted is False

    saturate = LedgerClassifyLlmSaturateResult.model_validate(
        {"llm": True, "provider": "claude", "transaction_id": "a" * 64, "iva_category": "DOMESTIC", "persisted": False},
    )
    assert saturate.iva_category == "DOMESTIC"


def test_bulk_result_rejects_extra_field() -> None:
    """The strict OutputSchema base forbids unknown keys on the bulk branch."""
    with pytest.raises(ValueError):  # noqa: PT011 - pydantic ValidationError is a ValueError subclass
        LedgerClassifyBulkResult.model_validate(
            {"total": 1, "applied": 1, "skipped": 0, "failures": [], "bogus": "x"},
        )


def test_link_result_carries_transaction_and_typed_evidence_update() -> None:
    """D1/D2: link gains a transaction slot and a typed evidence_update payload."""
    evidence = LedgerLinkEvidenceUpdatePayload.model_validate(
        {
            "bucket_id": "default",
            "transaction_id": "a" * 64,
            "review_status": "pending",
            "transaction": _transaction_payload(),
        },
    )
    result = LedgerLinkResult.model_validate(
        {
            "operation": "ledger.link",
            "bucket_id": "default",
            "transaction_id": "a" * 64,
            "evidence_id": "ev-1",
            "actor": "operator",
            "transaction": _transaction_payload(),
            "evidence_update": evidence.model_dump(mode="json"),
        },
    )
    assert result.transaction is not None
    assert result.evidence_update is not None
    assert result.evidence_update.transaction.transaction_id == "a" * 64
    # Invoice-only link: both slots are None.
    invoice_only = LedgerLinkResult.model_validate(
        {
            "operation": "ledger.link",
            "bucket_id": "default",
            "transaction_id": "a" * 64,
            "invoice_id": "inv-1",
            "actor": "operator",
        },
    )
    assert invoice_only.transaction is None
    assert invoice_only.evidence_update is None


def test_list_row_payload_carries_full_contract_and_round_trips() -> None:
    """D2/D6: the typed list row carries the full field set incl. timestamps."""
    row = LedgerListRowPayload.model_validate(
        {
            "full_id": "a" * 64,
            "display_id": "aaaa",
            "transaction_id": "a" * 64,
            "date": "2024-04-10",
            "booked_date": "2024-04-10",
            "amount": "100.00",
            "currency": "EUR",
            "direction": "OUTGOING",
            "description": "Compra material",
            "business_classification": "BUSINESS",
            "lifecycle_state": "ACTIVE",
            "review_status": "pending",
            "classified_by": "manual",
            "created_at": "2024-04-10T09:30:00+00:00",
            "modified_at": "2024-06-01T16:45:00+00:00",
            "group_label": "Proyecto Acme",
        },
    )
    # Non-negative amount + direction (money shape fixed by C1).
    assert row.amount == "100.00"
    assert row.direction == "OUTGOING"
    assert row.created_at == "2024-04-10T09:30:00+00:00"
    assert row.group_label == "Proyecto Acme"
    assert LedgerListRowPayload.model_validate(row.model_dump(mode="json")) == row


def test_history_events_are_typed_not_bare_dicts() -> None:
    """D2: ledger history events are a typed list, not list[dict[str, object]]."""
    event = {
        "event_id": "e" * 64,
        "bucket_id": "default",
        "event_type": "LEDGER_TRANSACTION_CREATED",
        "occurred_at": "2024-04-10T09:30:00+00:00",
        "actor": "operator",
        "object_type": "LEDGER_TRANSACTION",
        "object_id": "a" * 64,
        "payload_version": 1,
        "payload": {"source_command": "aeat app ledger add"},
    }
    result = LedgerHistoryResult.model_validate(
        {"bucket_id": "default", "transaction_id": "a" * 64, "event_count": 1, "events": [event]},
    )
    assert isinstance(result.events[0], LedgerHistoryEventPayload)
    assert result.events[0].payload == {"source_command": "aeat app ledger add"}
    assert LedgerHistoryResult.model_validate(result.model_dump(mode="json")) == result


def test_import_transaction_refs_are_typed() -> None:
    """D2: import transaction-ref lists are typed, not list[dict[str, object]]."""
    ref = LedgerImportTransactionRefPayload.model_validate(
        {"bucket_id": "default", "transaction_id": "a" * 64},
    )
    assert ref.bucket_id == "default"
    assert ref.transaction_id == "a" * 64
    assert LedgerImportTransactionRefPayload.model_validate(ref.model_dump(mode="json")) == ref


def test_transaction_payload_carries_d6_timestamps() -> None:
    """D6: the nested TransactionPayload exposes created_at / modified_at."""
    payload = TransactionPayload.model_validate(_transaction_payload())
    assert payload.created_at == "2024-04-10T09:30:00+00:00"
    assert payload.modified_at == "2024-06-01T16:45:00+00:00"
    # Grandfathered None default for pre-axis rows.
    bare = TransactionPayload.model_validate(_transaction_payload(created_at=None, modified_at=None))
    assert bare.created_at is None
    assert bare.modified_at is None
