"""CLI evidence mutation bridges correlate request, profile, and effect."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
import typer
from typer.core import TyperCommand

from cadrumo.application.ledger.evidence import PurchaseInvoiceEvidencePatch
from cadrumo.application.ledger.evidence_mutation_operation import (
    LedgerEvidenceUpdateProjection,
    LedgerEvidenceUpdateRequest,
)
from cadrumo.application.ledger.evidence_read_operation import LedgerEvidenceRecordProjection
from cadrumo.application.ledger.tests.evidence_mutation_support import (
    EVIDENCE_MUTATION_PROFILE,
    evidence_mutation_record,
)
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.entrypoints.cli import operation_ledger_evidence_mutation as bridge

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _run_bridge(
    monkeypatch: pytest.MonkeyPatch,
    *,
    patch: PurchaseInvoiceEvidencePatch,
    projection: LedgerEvidenceUpdateProjection,
    effect: OperationEffect,
) -> tuple[LedgerEvidenceUpdateProjection, LedgerEvidenceUpdateRequest]:
    client = SimpleNamespace(profile_id=EVIDENCE_MUTATION_PROFILE)
    captured: list[LedgerEvidenceUpdateRequest] = []
    monkeypatch.setattr(bridge, "bound_profile_client", lambda _ctx: client)

    def run_registered(_client: object, request: LedgerEvidenceUpdateRequest, **_kwargs: object):
        captured.append(request)
        return SimpleNamespace(
            projection=projection,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            refusal_code=None,
            effect=effect,
            operation_id="operation-ref",
        )

    monkeypatch.setattr(bridge, "run_registered_operation", run_registered)
    result = bridge.run_ledger_evidence_update(
        typer.Context(TyperCommand("test")), evidence_id="evidence-target", patch=patch
    )
    assert len(captured) == 1
    return result, captured[0]


def test_update_bridge_canonicalizes_trailing_zero_decimal_and_correlates_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = LedgerEvidenceUpdateProjection(
        profile_id=EVIDENCE_MUTATION_PROFILE,
        record=LedgerEvidenceRecordProjection.from_record(evidence_mutation_record()),
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
        profile_id=EVIDENCE_MUTATION_PROFILE,
        record=LedgerEvidenceRecordProjection.from_record(evidence_mutation_record()),
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
