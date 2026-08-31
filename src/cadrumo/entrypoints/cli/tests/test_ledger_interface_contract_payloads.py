"""Pydantic construction / validation / serialisation suite for ledger payloads.

Exercises the typed CLI envelopes directly as pydantic models: the uniform
mutation quintet, typed list-row payloads that replace bare
``dict[str, object]`` boundaries, and persistence-record lifecycle timestamps.
These lock the schema shape, the strict extra-forbid contract, and the JSON
round-trip.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ....application.export.tabular import ExportSerializationFormat
from ....application.ledger.models import LedgerExportResult, LedgerExportRow
from ....core.operator_action_enums import OperatorActionAxis
from ....domain.categories.proportionality import ProportionalityKind
from ....domain.categories.spending_category import SpendingCategory
from ....domain.transactions.enums import BusinessClassification
from .._ledger_catalogue_invoice_payloads import (
    CatalogueInvoiceListResult,
    CatalogueInvoiceRecordPayload,
)
from .._ledger_llm_payloads import (
    LedgerClassifyLlmRejectResult,
    LedgerClassifyLlmSaturateResult,
    LedgerClassifyLlmSuggestResult,
)
from .._ledger_payloads import (
    EvidenceListResult,
    EvidenceRecordPayload,
    InventoryLedgerPayload,
    InventoryListResult,
    InventoryMovementPayload,
    InventoryStockLayerPayload,
    LedgerAddResult,
    LedgerClassifyBulkResult,
    LedgerClassifySingleResult,
    LedgerExportPayload,
    LedgerExportRowPayload,
    LedgerHistoryEventPayload,
    LedgerHistoryResult,
    LedgerImportTransactionRefPayload,
    LedgerLinkResult,
    LedgerListRowPayload,
    LedgerPeriodPayload,
    LedgerPreflightIssuePayload,
    LedgerPreflightResult,
    RatiosEligibleResult,
    RatiosEligibleRowPayload,
    RatiosValidateFindingPayload,
    RatiosValidateResult,
    RuleApplyAppliedPayload,
    RuleApplyResult,
    TransactionPayload,
    _LedgerMutationResult,
)
from .._modelo_payloads import LedgerIssuePayload

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


def _period_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "filing_year": 2026,
        "code": "1T",
    }
    base.update(overrides)
    return base


def test_readiness_issue_payloads_keep_the_domain_detail_requirement() -> None:
    """Both operator projections refuse an issue the ledger preflight model rejects."""
    shared = {"transaction_id": "a" * 64, "reason": "missing_category", "detail": "category required"}
    # The readiness projection additionally carries the typed operator action
    # the envelope contract requires; the preflight projection does not. The
    # detail requirement under test is what they still share.
    readiness = {**shared, "operator_action": OperatorActionAxis.IMPORT_LEDGER_DATA}

    assert LedgerPreflightIssuePayload.model_validate(shared).detail == "category required"
    assert LedgerIssuePayload.model_validate(readiness).detail == "category required"

    for payload_type, valid in ((LedgerPreflightIssuePayload, shared), (LedgerIssuePayload, readiness)):
        invalid = {**valid, "detail": ""}
        with pytest.raises(ValueError, match="at least 1 character"):
            payload_type.model_validate(invalid)


def test_add_result_subclasses_mutation_quintet_and_carries_review_status() -> None:
    """LedgerAddResult is a _LedgerMutationResult and carries review_status."""
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
    """The single-transaction classify path returns the mutation quintet."""
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
    """Bulk / llm-suggest / llm-saturate are distinct, non-optional branches."""
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

    reject = LedgerClassifyLlmRejectResult.model_validate(
        {
            "llm": True,
            "rejected": True,
            "provider": "claude",
            "transaction_id": "a" * 64,
            "suggestion_kind": "classification",
            "provenance": "llm:claude:m",
            "bucket_event_id": "e" * 64,
            "operator_reason": "wrong",
            "persisted": False,
        },
    )
    assert reject.rejected is True and reject.persisted is False
    # Strict OutputSchema base forbids unknown keys and round-trips through JSON.
    assert LedgerClassifyLlmRejectResult.model_validate_json(reject.model_dump_json()) == reject
    with pytest.raises(ValueError, match="extra"):
        LedgerClassifyLlmRejectResult.model_validate(
            {
                "llm": True,
                "rejected": True,
                "provider": "claude",
                "transaction_id": "a" * 64,
                "suggestion_kind": "classification",
                "provenance": "llm:claude:m",
                "bucket_event_id": "e" * 64,
                "bogus": "x",
            },
        )


def test_bulk_result_rejects_extra_field() -> None:
    """The strict OutputSchema base forbids unknown keys on the bulk branch."""
    with pytest.raises(ValueError):
        LedgerClassifyBulkResult.model_validate(
            {"total": 1, "applied": 1, "skipped": 0, "failures": [], "bogus": "x"},
        )


def test_link_result_is_invoice_only() -> None:
    """`ledger link` carries only invoice-link metadata; no evidence slots exist
    on the result (evidence assignment is the separate `attach` operation)."""
    result = LedgerLinkResult.model_validate(
        {
            "operation": "ledger.link",
            "bucket_id": "default",
            "transaction_id": "a" * 64,
            "invoice_id": "b" * 64,
            "actor": "operator",
        },
    )
    assert result.invoice_id == "b" * 64
    assert not hasattr(result, "evidence_id")
    assert not hasattr(result, "evidence_update")
    assert not hasattr(result, "transaction")


def test_list_row_payload_carries_full_contract_and_round_trips() -> None:
    """The typed list row carries the full field set incl. timestamps."""
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
    assert LedgerListRowPayload.model_validate_json(row.model_dump_json()) == row


def test_history_events_are_typed_not_bare_dicts() -> None:
    """Ledger history events are a typed list, not list[dict[str, object]]."""
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
    assert LedgerHistoryResult.model_validate_json(result.model_dump_json()) == result


def test_import_transaction_refs_are_typed() -> None:
    """Import transaction-ref lists are typed, not list[dict[str, object]]."""
    ref = LedgerImportTransactionRefPayload.model_validate(
        {"bucket_id": "default", "transaction_id": "a" * 64},
    )
    assert ref.bucket_id == "default"
    assert ref.transaction_id == "a" * 64
    assert LedgerImportTransactionRefPayload.model_validate_json(ref.model_dump_json()) == ref


def test_export_and_preflight_payloads_use_typed_nested_rows() -> None:
    """Export rows and preflight period/issues are typed nested models."""
    export_row = {
        "bucket_id": "default",
        "transaction_id": "a" * 64,
        "lifecycle_state": "ACTIVE",
        "booked_date": "2026-04-05",
        "effective_date": "2026-04-05",
        "amount": "42.00",
        "currency": "EUR",
        "direction": "OUTGOING",
        "description": "Material",
        "business_classification": "BUSINESS",
    }
    export = LedgerExportPayload.model_validate(
        {
            "bucket_id": "default",
            "export_id": "e" * 64,
            "export_format": "csv",
            "media_type": "text/csv",
            "filename_extension": ".csv",
            "row_count": 1,
            "byte_size": 128,
            "sha256": "f" * 64,
            "fieldnames": ["transaction_id"],
            "rows": [export_row],
            "output_path": "ledger.csv",
        },
    )
    assert isinstance(export.rows[0], LedgerExportRowPayload)

    for field, value in (
        ("export_id", "not-a-digest"),
        ("sha256", "not-a-digest"),
        ("byte_size", -1),
        ("rows", [{**export_row, "booked_date": "not-a-date"}]),
        ("rows", [{**export_row, "amount": "not-a-decimal"}]),
        # "EURO" rather than "eur". A lowercase code is NORMALISED by the
        # canonical currency annotation, on the payload and on the
        # application row alike, so it is no longer a wall on either side --
        # asserting a refusal here would pin the payload as stricter than the
        # record it mirrors, which is the divergence this test exists to
        # forbid. The word "euros" is a real operator mistake the LLM
        # extraction fixtures carry, and both sides refuse it.
        ("rows", [{**export_row, "currency": "EURO"}]),
    ):
        with pytest.raises(ValidationError):
            LedgerExportPayload.model_validate({**export.model_dump(), field: value})

    preflight = LedgerPreflightResult.model_validate(
        {
            "bucket_id": "default",
            "period": _period_payload(),
            "checked_transaction_count": 1,
            "issues": [{"transaction_id": "a" * 64, "reason": "missing_category", "detail": "category required"}],
            "ready": False,
        },
    )
    assert isinstance(preflight.period, LedgerPeriodPayload)
    assert isinstance(preflight.issues[0], LedgerPreflightIssuePayload)
    assert LedgerPreflightResult.model_validate_json(preflight.model_dump_json()) == preflight


def test_export_payload_accepts_application_intracommunity_rows() -> None:
    """CLI export envelope accepts every field emitted by the application export row."""
    app_result = LedgerExportResult(
        bucket_id="default",
        export_id="e" * 64,
        export_format=ExportSerializationFormat.JSONL,
        media_type="application/x-ndjson",
        filename_extension="jsonl",
        row_count=1,
        byte_size=86,
        sha256="8be63b9a5518ec747a470d0a2a8bb79cdd2892f2aa99c87376991d801dc43477",
        fieldnames=("transaction_id", "iva_category", "counterparty_country"),
        rows=(
            LedgerExportRow(
                bucket_id="default",
                transaction_id="a" * 64,
                lifecycle_state="ACTIVE",
                booked_date="2026-04-05",
                effective_date="2026-04-05",
                amount="2000.00",
                currency="EUR",
                direction="INCOMING",
                description="EU B2B supply",
                business_classification="BUSINESS",
                iva_category="intra_community_supply",
                counterparty_country="DE",
            ),
        ),
        payload=b'{"transaction_id":"%s"}\n' % (b"a" * 64),
    )

    export = LedgerExportPayload.from_result(app_result, output_path="ledger.jsonl")

    assert export.rows[0].iva_category == "intra_community_supply"
    assert export.rows[0].counterparty_country == "DE"


def test_ratios_payloads_use_typed_rows_and_findings() -> None:
    """Ratios eligible/validate rows are typed payloads."""
    eligible = RatiosEligibleResult.model_validate(
        {
            "bucket_id": "default",
            "rows": [
                {
                    "category": SpendingCategory.VEHICULO_COMBUSTIBLE,
                    "proportionality_kind": ProportionalityKind.USAGE_RATIO_PERSONAL,
                    "default_ratio": None,
                    "override_present": False,
                },
            ],
            "count": 1,
        },
    )
    assert isinstance(eligible.rows[0], RatiosEligibleRowPayload)

    validate = RatiosValidateResult.model_validate(
        {
            "bucket_id": "default",
            "profile_present": True,
            "eligible_count": 1,
            "overrides_count": 1,
            "missing_overrides": [SpendingCategory.VEHICULO_COMBUSTIBLE],
            "findings": [
                {
                    "category": SpendingCategory.VEHICULO_COMBUSTIBLE,
                    "kind": "missing_override",
                    "detail": "required",
                },
            ],
        },
    )
    assert isinstance(validate.findings[0], RatiosValidateFindingPayload)
    # model_validate(x.model_dump(mode="json")) round-trips a plain-string
    # payload but not a strict enum-typed one: mode="json" dumps the StrEnum
    # to its bare string value, and strict validation on an already-Python
    # dict refuses to coerce that string back into the enum instance (only
    # model_validate_json's genuine JSON-text parse gets that leniency). The
    # wire format is JSON text, so this is the round-trip that actually
    # matters.
    assert RatiosValidateResult.model_validate_json(validate.model_dump_json()) == validate


def test_invoice_inventory_evidence_and_rule_apply_lists_use_typed_rows() -> None:
    """List payloads for companion ledger sub-apps are typed."""
    invoice_list = CatalogueInvoiceListResult.model_validate_json(
        json.dumps(
            {
                "bucket_id": "default",
                "rows": [
                    {
                        "invoice_id": "b" * 64,
                        "kind": "received",
                        "invoice_number": "F-001",
                        "issued_at": "2026-04-05",
                        "counterparty_name": "Proveedor SL",
                        "counterparty_tax_id": "B12345674",
                        "counterparty_country": "ES",
                        "base_total": "100.00",
                        "iva_total": "21.00",
                        "grand_total": "121.00",
                        "currency": "EUR",
                        "payment_status": "PENDING",
                    },
                ],
                "count": 1,
            }
        ),
    )
    assert isinstance(invoice_list.rows[0], CatalogueInvoiceRecordPayload)

    inventory = InventoryListResult.model_validate(
        {
            "bucket_id": "default",
            "rows": [
                {
                    "actividad_id": "act-1",
                    "year": 2026,
                    "valuation_method": "fifo",
                    "opening_stock": "10.00",
                    "opening_layers": [
                        {
                            "sku": "default",
                            "quantity": "1",
                            "unit_cost": "10.00",
                            "source_movement_id": "opening",
                        },
                    ],
                    "period_movements": [
                        {
                            "movement_id": "m-1",
                            "movement_date": "2026-04-05",
                            "kind": "purchase",
                            "quantity": "1",
                            "unit_cost": "10.00",
                            "iva_rate": "21",
                            "deductible_iva_ratio": "1.00",
                            "schema_version": "3",
                        },
                    ],
                    "schema_version": "3",
                },
            ],
            "count": 1,
        },
    )
    assert isinstance(inventory.rows[0], InventoryLedgerPayload)
    assert isinstance(inventory.rows[0].opening_layers[0], InventoryStockLayerPayload)
    assert isinstance(inventory.rows[0].period_movements[0], InventoryMovementPayload)

    evidence = EvidenceListResult.model_validate(
        {
            "bucket_id": "default",
            "count": 1,
            "rows": [
                {
                    "evidence_id": "evidence-001",
                    "bucket_id": "default",
                    "source_path": "invoice.pdf",
                    "source_sha256": "e" * 64,
                    "attachment_id": "a" * 64,
                    "media_kind": "pdf",
                    "created_at": "2026-04-05T10:00:00+00:00",
                    "updated_at": "2026-04-05T10:00:00+00:00",
                },
            ],
        },
    )
    assert isinstance(evidence.rows[0], EvidenceRecordPayload)

    rule_apply = RuleApplyResult.model_validate(
        {
            "rules_evaluated": 1,
            "transactions_scanned": 1,
            "matched": 1,
            "skipped_already_classified": 0,
            "no_match": 0,
            "applied": [
                {
                    "transaction_id": "a" * 64,
                    "matched_rule_id": "e" * 64,
                    "classification": BusinessClassification.BUSINESS,
                },
            ],
        },
    )
    assert rule_apply.applied is not None
    assert isinstance(rule_apply.applied[0], RuleApplyAppliedPayload)
    # See the matching comment in test_ratios_payloads_use_typed_rows_and_findings:
    # a strict enum-typed field (classification) does not survive
    # model_validate(model_dump(mode="json")); model_validate_json is the
    # round-trip that reflects the actual wire format.
    assert RuleApplyResult.model_validate_json(rule_apply.model_dump_json()) == rule_apply


def test_transaction_payload_carries_d6_timestamps() -> None:
    """The nested TransactionPayload exposes created_at / modified_at."""
    payload = TransactionPayload.model_validate(_transaction_payload())
    assert payload.created_at == "2024-04-10T09:30:00+00:00"
    assert payload.modified_at == "2024-06-01T16:45:00+00:00"
    with pytest.raises(ValueError):
        TransactionPayload.model_validate(_transaction_payload(created_at=None, modified_at=None))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("transaction_id", "bad"),
        ("date", "not-date"),
        ("description", ""),
        ("currency", "X"),
    ],
)
def test_transaction_payload_rejects_malformed_values_the_canonical_model_rejects(field: str, value: object) -> None:
    """A malformed identity/date/description/currency crosses the same wall LedgerTransactionPayload holds."""
    with pytest.raises(ValidationError):
        TransactionPayload.model_validate(_transaction_payload(**{field: value}))


def test_ledger_add_result_refuses_a_malformed_nested_transaction() -> None:
    """Every mutation-quintet result reuses the same nested transaction contract as ``TransactionPayload``."""
    with pytest.raises(ValidationError):
        LedgerAddResult.model_validate(
            {
                "bucket_id": "default",
                "transaction_id": "a" * 64,
                "bucket_event_ids": ["b" * 64],
                "review_status": "reviewed",
                "transaction": _transaction_payload(currency="X"),
            },
        )


def test_ledger_add_result_accepts_a_valid_mutation_quintet_round_trip() -> None:
    """A genuine mutation-quintet payload carrying a well-formed nested transaction round-trips cleanly."""
    result = LedgerAddResult.model_validate(
        {
            "bucket_id": "default",
            "transaction_id": "a" * 64,
            "bucket_event_ids": ["b" * 64],
            "review_status": "reviewed",
            "transaction": _transaction_payload(),
        },
    )

    assert result.transaction.transaction_id == "a" * 64
    assert LedgerAddResult.model_validate_json(result.model_dump_json()) == result
