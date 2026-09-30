"""Registered evidence mutation bounds and effect settlement."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from ....application.ledger.evidence import (
    MediaKind,
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidencePatch,
    PurchaseInvoiceEvidenceResult,
    PurchaseInvoiceEvidenceService,
    prepare_purchase_invoice_evidence_update,
)
from ....application.ledger.evidence_mutation_operation import (
    LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID,
    LedgerEvidenceUpdateExecutionResult,
    LedgerEvidenceUpdateExecutor,
    LedgerEvidenceUpdatePatch,
    LedgerEvidenceUpdateRequest,
    build_ledger_evidence_remove_definition,
    build_ledger_evidence_update_definition,
)
from ....application.ledger.evidence_ports import LedgerEvidencePorts, PurchaseInvoiceEvidenceRepositoryProtocol
from ....application.operations.models import OperationRequest
from ....application.operations.owner import OperationExecutorContext
from ....core.operations import OperationEffect, profile_operation_subject
from ....core.secure_object_write import SecureObjectWrite
from ....domain.buckets.protocols import BucketEventHistoryRepositoryProtocol

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


def _unused_factory(*, bucket_id: str) -> LedgerEvidencePorts:
    raise AssertionError(f"unexpected port construction for {bucket_id}")


def test_update_contracts_allow_only_explicit_empty_mask_and_only_update_permits_none() -> None:
    patch = LedgerEvidenceUpdatePatch(supplier="After SL")
    with pytest.raises(ValidationError, match="explicit patch field mask"):
        LedgerEvidenceUpdateRequest(
            profile_id=_PROFILE,
            evidence_id="evidence-target",
            patch=patch,
            patch_fields=(),
        )

    explicit_patch = LedgerEvidenceUpdateRequest(
        profile_id=_PROFILE,
        evidence_id="evidence-target",
        patch=patch,
        patch_fields=("supplier",),
    )
    restored_patch = LedgerEvidenceUpdateRequest.model_validate_json(explicit_patch.model_dump_json())
    assert restored_patch.patch_fields == ("supplier",)

    no_op = LedgerEvidenceUpdateRequest(
        profile_id=_PROFILE,
        evidence_id="evidence-target",
        patch=LedgerEvidenceUpdatePatch(),
        patch_fields=(),
    )
    assert no_op.patch_fields == ()
    assert LedgerEvidenceUpdateRequest.model_validate_json(no_op.model_dump_json()).patch_fields == ()
    update = build_ledger_evidence_update_definition(_unused_factory)
    remove = build_ledger_evidence_remove_definition(_unused_factory)
    assert OperationEffect.NONE in update.capabilities.permitted_effects
    assert OperationEffect.NONE not in remove.capabilities.permitted_effects


@pytest.mark.asyncio
async def test_update_effect_is_unknown_before_guarded_mutation_and_updated_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = _record()
    backend = object()

    class EvidenceRepository:
        secure_object_repository = backend

        def load(self, *, bucket_id: str) -> tuple[PurchaseInvoiceEvidence, ...]:
            assert bucket_id == str(_PROFILE)
            return (current,)

        def load_revisioned(self, *, bucket_id: str) -> tuple[tuple[PurchaseInvoiceEvidence, ...], str]:
            return self.load(bucket_id=bucket_id), "0" * 64

        def save_if_revision_with_secure_object_writes(
            self,
            *,
            bucket_id: str,
            records: tuple[PurchaseInvoiceEvidence, ...],
            expected_revision_id: str,
            extra_writes: tuple[SecureObjectWrite, ...],
        ) -> None:
            raise AssertionError("the fake service update owns its test result")

    class EventRepository:
        secure_object_repository = backend

        def load_revisioned(self):
            return object(), "0" * 64

    ports = cast(
        LedgerEvidencePorts,
        SimpleNamespace(
            evidence_repository=cast(PurchaseInvoiceEvidenceRepositoryProtocol, EvidenceRepository()),
            attachment_ingestor=object(),
            bucket_event_repository=cast(BucketEventHistoryRepositoryProtocol, EventRepository()),
        ),
    )

    class Cancellation:
        active = False

        @asynccontextmanager
        async def irreversible_section(self):
            assert not self.active
            self.active = True
            try:
                yield
            finally:
                self.active = False

    cancellation = Cancellation()
    effects: list[OperationEffect] = []
    mutated = False

    class Events:
        async def phase(self, _phase: str) -> None:
            return None

        async def effect(self, effect: OperationEffect) -> None:
            if effect is OperationEffect.UNKNOWN:
                assert cancellation.active and not mutated
            elif effect is OperationEffect.UPDATED:
                assert cancellation.active and mutated
            effects.append(effect)

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            assert cancellation.active
            assert effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
            assert written_at.tzinfo is not None
            assert isinstance(operand, LedgerEvidenceUpdateExecutionResult)
            assert operand.result.record.supplier == "After SL"
            return "d" * 64

    def update_service(
        _self: PurchaseInvoiceEvidenceService,
        *,
        bucket_id: str,
        evidence_id: str,
        patch: PurchaseInvoiceEvidencePatch,
        actor: str,
        expected_current: PurchaseInvoiceEvidence,
        occurred_at: datetime,
    ) -> PurchaseInvoiceEvidenceResult:
        nonlocal mutated
        assert bucket_id == str(_PROFILE)
        assert evidence_id == current.evidence_id
        assert actor == "cli"
        assert expected_current == current
        assert cancellation.active
        assert effects == [OperationEffect.UNKNOWN]
        updated = prepare_purchase_invoice_evidence_update(current, patch, updated_at=occurred_at)
        mutated = True
        return PurchaseInvoiceEvidenceResult(record=updated, bucket_event_ids=("f" * 64,))

    monkeypatch.setattr(PurchaseInvoiceEvidenceService, "update", update_service)
    monkeypatch.setattr(
        "cadrumo.application.ledger.evidence_mutation_operation.require_active_bucket_id",
        lambda: str(_PROFILE),
    )

    def ports_factory(*, bucket_id: str) -> LedgerEvidencePorts:
        assert bucket_id == str(_PROFILE)
        return ports

    executor = LedgerEvidenceUpdateExecutor(ports_factory)
    request = OperationRequest[LedgerEvidenceUpdateRequest](
        definition_id=LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerEvidenceUpdateRequest(
            profile_id=_PROFILE,
            evidence_id=current.evidence_id,
            patch=LedgerEvidenceUpdatePatch(supplier="After SL"),
            patch_fields=("supplier",),
        ),
    )
    context = SimpleNamespace(
        identity=SimpleNamespace(
            definition_id=LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        cancellation=cancellation,
        events=Events(),
        operands=Operands(),
    )

    result_ref = await executor.execute(request, cast(OperationExecutorContext, context))

    assert result_ref == "d" * 64
    assert effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert cancellation.active is False
