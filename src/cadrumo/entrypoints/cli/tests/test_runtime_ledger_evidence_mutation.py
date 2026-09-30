"""CLI evidence mutation bridges correlate request, profile, and effect."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest

from cadrumo.application.ledger.evidence import MediaKind, PurchaseInvoiceEvidence, PurchaseInvoiceEvidencePatch
from cadrumo.application.ledger.evidence_mutation_operation import (
    LedgerEvidenceUpdateProjection,
)
from cadrumo.application.ledger.evidence_read_operation import LedgerEvidenceRecordProjection
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.entrypoints.cli import runtime_ledger_evidence_mutation as runtime

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)


def _record() -> PurchaseInvoiceEvidence:
    return PurchaseInvoiceEvidence(
        evidence_id="evidence-target",
        bucket_id=str(_PROFILE),
        source_path="invoice.pdf",
        source_sha256="a" * 64,
        attachment_id="a" * 64,
        media_kind=MediaKind.PDF,
        supplier="Before SL",
        invoice_number="INV-2026-05",
        invoice_date="2026-05-08",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
        notes="invoice note",
        created_at=_AT,
        updated_at=_AT,
    )


def _run_bridge(
    monkeypatch: pytest.MonkeyPatch,
    *,
    patch: PurchaseInvoiceEvidencePatch,
    projection: LedgerEvidenceUpdateProjection,
    effect: OperationEffect,
) -> tuple[LedgerEvidenceUpdateProjection, object]:
    client = SimpleNamespace(profile_id=_PROFILE)
    captured: dict[str, object] = {}
    monkeypatch.setattr(runtime, "bound_profile_client", lambda _ctx: client)

    def run_registered(_client, request, **_kwargs):
        captured["request"] = request
        return SimpleNamespace(
            projection=projection,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            refusal_code=None,
            effect=effect,
            operation_id="operation-ref",
        )

    monkeypatch.setattr(runtime, "run_registered_operation", run_registered)
    result = runtime.run_ledger_evidence_update(object(), evidence_id="evidence-target", patch=patch)
    return result, captured["request"]


def test_update_bridge_canonicalizes_trailing_zero_decimal_and_correlates_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = LedgerEvidenceUpdateProjection(
        profile_id=_PROFILE,
        record=LedgerEvidenceRecordProjection.from_record(_record()),
        bucket_event_ids=("f" * 64,),
    )

    result, request = _run_bridge(
        monkeypatch,
        patch=PurchaseInvoiceEvidencePatch(taxable_base=Decimal("100.00")),
        projection=projection,
        effect=OperationEffect.UPDATED,
    )

    assert request.patch_fields == ("taxable_base",)
    assert request.patch.taxable_base == "100"
    assert result.record.taxable_base == "100.00"


def test_empty_update_bridge_requires_none_effect_and_no_event(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = LedgerEvidenceUpdateProjection(
        profile_id=_PROFILE,
        record=LedgerEvidenceRecordProjection.from_record(_record()),
        bucket_event_ids=(),
    )

    result, request = _run_bridge(
        monkeypatch,
        patch=PurchaseInvoiceEvidencePatch(),
        projection=projection,
        effect=OperationEffect.NONE,
    )

    assert request.patch_fields == ()
    assert result.bucket_event_ids == ()
