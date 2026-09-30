"""Evidence-add CLI bridge preserves the bounded registered contract."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import click
import pytest
import typer

from ....application.ledger.evidence import MediaKind, derive_keyed_purchase_invoice_evidence_id
from ....application.ledger.evidence_add_operation import (
    LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
    LedgerEvidenceAddProjection,
    LedgerEvidenceAddRequest,
)
from ....application.ledger.evidence_read_operation import LedgerEvidenceRecordProjection
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import runtime_ledger_evidence_add as bridge

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)


def _record(**changes: object) -> LedgerEvidenceRecordProjection:
    data: dict[str, object] = {
        "evidence_id": "b" * 16,
        "bucket_id": str(_PROFILE),
        "source_path": "invoices/invoice.pdf",
        "source_sha256": "a" * 64,
        "attachment_id": "a" * 64,
        "media_kind": MediaKind.PDF,
        "supplier": "Supplier SL",
        "invoice_number": "INV-2026-05",
        "invoice_date": "2026-05-08",
        "taxable_base": "100.00",
        "iva_rate": "21",
        "iva_amount": "21.00",
        "notes": "invoice note",
        "created_at": _AT,
        "updated_at": _AT,
    }
    data.update(changes)
    return LedgerEvidenceRecordProjection.model_validate(data)


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    *,
    projection: LedgerEvidenceAddProjection,
    effect: OperationEffect,
) -> list[LedgerEvidenceAddRequest]:
    captured: list[LedgerEvidenceAddRequest] = []
    client = SimpleNamespace(profile_id=_PROFILE)
    monkeypatch.setattr(bridge, "bound_profile_client", lambda _ctx: client)

    def submit(_client, request, **kwargs):
        captured.append(request)
        assert kwargs["definition_id"] == LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is LedgerEvidenceAddProjection
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        assert kwargs["timeout"] == 120
        return SimpleNamespace(
            projection=projection,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            refusal_code=None,
            effect=effect,
            operation_id="f" * 64,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return captured


def test_add_bridge_uses_canonical_decimal_wire_text_and_correlates_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = LedgerEvidenceAddProjection(
        profile_id=_PROFILE,
        record=_record(),
        bucket_event_ids=("d" * 64,),
    )
    captured = _bind(monkeypatch, projection=projection, effect=OperationEffect.UPDATED)

    result = bridge.run_ledger_evidence_add(
        typer.Context(click.Command("test")),
        source_path="invoices/invoice.pdf",
        supplier="Supplier SL",
        invoice_number="INV-2026-05",
        invoice_date="2026-05-08",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21.00"),
        iva_amount=Decimal("21.00"),
        notes="invoice note",
        idempotency_key=None,
    )

    assert len(captured) == 1
    assert captured[0].taxable_base == "100"
    assert captured[0].iva_rate == "21"
    assert captured[0].iva_amount == "21"
    assert result.record.source_path == "invoices/invoice.pdf"
    assert result.bucket_event_ids == ("d" * 64,)


def test_keyed_add_replay_allows_original_path_and_empty_event_but_requires_updated_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "retry-key"
    evidence_id = derive_keyed_purchase_invoice_evidence_id(bucket_id=str(_PROFILE), idempotency_key=key)
    projection = LedgerEvidenceAddProjection(
        profile_id=_PROFILE,
        record=_record(evidence_id=evidence_id, source_path="earlier/invoice.pdf"),
        bucket_event_ids=(),
    )
    captured = _bind(monkeypatch, projection=projection, effect=OperationEffect.UPDATED)

    result = bridge.run_ledger_evidence_add(
        typer.Context(click.Command("test")),
        source_path="newer/location/same.pdf",
        supplier="Supplier SL",
        invoice_number="INV-2026-05",
        invoice_date="2026-05-08",
        taxable_base=Decimal("100"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21"),
        notes="invoice note",
        idempotency_key=key,
    )

    assert captured[0].idempotency_key == key
    assert result.record.source_path == "earlier/invoice.pdf"
    assert result.bucket_event_ids == ()
