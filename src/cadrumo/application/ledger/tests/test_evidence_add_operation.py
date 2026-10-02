"""Evidence-add request bounds and truthful worker effect settlement."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from ....application.ledger.evidence import (
    MediaKind,
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidenceResult,
    PurchaseInvoiceEvidenceService,
    derive_keyed_purchase_invoice_evidence_id,
)
from ....application.ledger.evidence_add_operation import (
    LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
    LedgerEvidenceAddExecutionResult,
    LedgerEvidenceAddExecutor,
    LedgerEvidenceAddRequest,
    build_ledger_evidence_add_definition,
)
from ....application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from ....application.ledger.evidence_ports import LedgerEvidencePorts
from ....application.operations.models import OperationRequest
from ....application.operations.owner import OperationExecutorContext
from ....core.operations import OperationEffect, profile_operation_subject
from .unused_repository_ports import UnusedBucketEventRepository, UnusedEvidenceAttachmentIngestor

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)


def _record(evidence_id: str, *, source_path: str = "invoice.pdf") -> PurchaseInvoiceEvidence:
    return PurchaseInvoiceEvidence(
        evidence_id=evidence_id,
        bucket_id=str(_PROFILE),
        source_path=source_path,
        source_sha256="a" * 64,
        attachment_id="a" * 64,
        media_kind=MediaKind.PDF,
        supplier="Supplier SL",
        invoice_number="INV-2026-05",
        invoice_date="2026-05-08",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        notes="invoice note",
        created_at=_AT,
        updated_at=_AT,
    )


def test_add_request_uses_wire_stable_canonical_date_and_amount_strings() -> None:
    request = LedgerEvidenceAddRequest(
        profile_id=_PROFILE,
        source_path="invoices/invoice.pdf",
        source_directory=str(Path.cwd()),
        invoice_date="2026-05-08",
        taxable_base="100",
        iva_rate="21",
        iva_amount="21",
    )

    dumped = request.model_dump(mode="json")
    assert dumped["invoice_date"] == "2026-05-08"
    assert dumped["taxable_base"] == "100"
    assert isinstance(dumped["iva_rate"], str)

    with pytest.raises(ValidationError, match="source_directory"):
        LedgerEvidenceAddRequest.model_validate({"profile_id": str(_PROFILE), "source_path": "invoice.pdf"})

    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        LedgerEvidenceAddRequest(
            profile_id=_PROFILE,
            source_path="invoice.pdf",
            source_directory=str(Path.cwd()),
            invoice_date="08-05-2026",
        )
    with pytest.raises(ValidationError, match="canonical non-negative"):
        LedgerEvidenceAddRequest(
            profile_id=_PROFILE,
            source_path="invoice.pdf",
            source_directory=str(Path.cwd()),
            taxable_base="100.00",
        )
    with pytest.raises(ValidationError, match="must not exceed 100"):
        LedgerEvidenceAddRequest(
            profile_id=_PROFILE, source_path="invoice.pdf", source_directory=str(Path.cwd()), iva_rate="101"
        )


@pytest.mark.parametrize("base", ["relative", "embedded-nul"])
def test_invalid_source_directory_refuses_before_custody_access(tmp_path: Path, base: str) -> None:
    """A transported source cannot fall back to the worker's ambient directory."""
    directory = Path("relative") if base == "relative" else tmp_path / "invalid\x00directory"
    service = PurchaseInvoiceEvidenceService(ports=cast(LedgerEvidencePorts, object()))
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        service.add(bucket_id=str(_PROFILE), source_path="invoice.pdf", source_directory=directory)


@pytest.mark.asyncio
@pytest.mark.parametrize("keyed_replay", [False, True])
async def test_add_effect_is_unknown_before_ingestion_and_updated_even_for_keyed_replay(
    monkeypatch: pytest.MonkeyPatch,
    keyed_replay: bool,
) -> None:
    backend = object()
    key = "retry-key" if keyed_replay else None
    prior = (
        _record(derive_keyed_purchase_invoice_evidence_id(bucket_id=str(_PROFILE), idempotency_key=key))
        if key is not None
        else None
    )

    class EvidenceRepository:
        secure_object_repository = backend

        def load(self, *, bucket_id: str) -> tuple[PurchaseInvoiceEvidence, ...]:
            assert bucket_id == str(_PROFILE)
            return () if prior is None else (prior,)

        def save(self, *, bucket_id: str, records: Sequence[PurchaseInvoiceEvidence]) -> None:
            raise AssertionError("the service stub owns the operation result")

        def load_revisioned(self, *, bucket_id: str) -> tuple[tuple[PurchaseInvoiceEvidence, ...], str]:
            assert bucket_id == str(_PROFILE)
            return (() if prior is None else (prior,)), "0" * 64

        def save_if_revision_with_secure_object_writes(self, **_kwargs: object) -> None:
            raise AssertionError("the service stub owns the operation result")

    ports = LedgerEvidencePorts(
        evidence_repository=EvidenceRepository(),
        attachment_ingestor=UnusedEvidenceAttachmentIngestor(backend),
        bucket_event_repository=UnusedBucketEventRepository(backend),
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

    class Events:
        async def phase(self, _phase: str) -> None:
            return None

        async def effect(self, effect: OperationEffect) -> None:
            if effect is OperationEffect.UNKNOWN:
                assert cancellation.active and effects == []
            elif effect is OperationEffect.UPDATED:
                assert cancellation.active and effects == [OperationEffect.UNKNOWN]
            effects.append(effect)

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            assert cancellation.active
            assert effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
            assert written_at.tzinfo is not None
            assert isinstance(operand, LedgerEvidenceAddExecutionResult)
            assert operand.result.record.supplier == "Supplier SL"
            assert operand.result.bucket_event_ids == (() if keyed_replay else ("f" * 64,))
            return "d" * 64

    def add_service(
        _self: PurchaseInvoiceEvidenceService,
        *,
        bucket_id: str,
        source_path: str,
        source_directory: Path,
        supplier: str | None,
        invoice_number: str | None,
        invoice_date: str | None,
        taxable_base: Decimal | None,
        iva_rate: Decimal | None,
        iva_amount: Decimal | None,
        notes: str,
        actor: str,
        idempotency_key: str | None,
    ) -> PurchaseInvoiceEvidenceResult:
        assert bucket_id == str(_PROFILE)
        assert source_path == "invoice.pdf"
        assert source_directory == Path.cwd()
        assert supplier == "Supplier SL"
        assert invoice_number == "INV-2026-05"
        assert invoice_date == "2026-05-08"
        assert taxable_base == Decimal("100")
        assert iva_rate == Decimal("21")
        assert iva_amount == Decimal("21")
        assert notes == "invoice note"
        assert actor == "cli"
        assert idempotency_key == key
        assert cancellation.active and effects == [OperationEffect.UNKNOWN]
        if keyed_replay:
            assert prior is not None
            return PurchaseInvoiceEvidenceResult(record=prior, bucket_event_ids=())
        created = _record("0" * 16).model_copy(
            update={
                "evidence_id": "b" * 16,
                "source_path": source_path,
                "source_sha256": "c" * 64,
                "attachment_id": "c" * 64,
                "taxable_base": taxable_base,
                "iva_rate": iva_rate,
                "iva_amount": iva_amount,
                "notes": notes,
            },
        )
        return PurchaseInvoiceEvidenceResult(record=created, bucket_event_ids=("f" * 64,))

    monkeypatch.setattr(PurchaseInvoiceEvidenceService, "add", add_service)
    monkeypatch.setattr(
        "cadrumo.application.ledger.evidence_add_operation.require_active_bucket_id", lambda: str(_PROFILE)
    )

    def ports_factory(*, bucket_id: str) -> LedgerEvidencePorts:
        assert bucket_id == str(_PROFILE)
        return ports

    executor = LedgerEvidenceAddExecutor(ports_factory)
    request = OperationRequest[LedgerEvidenceAddRequest](
        definition_id=LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerEvidenceAddRequest(
            profile_id=_PROFILE,
            source_path="invoice.pdf",
            source_directory=str(Path.cwd()),
            supplier="Supplier SL",
            invoice_number="INV-2026-05",
            invoice_date="2026-05-08",
            taxable_base="100",
            iva_rate="21",
            iva_amount="21",
            notes="invoice note",
            idempotency_key=key,
        ),
    )
    context = SimpleNamespace(
        identity=SimpleNamespace(
            definition_id=LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
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
    definition = build_ledger_evidence_add_definition(ports_factory)
    assert definition.capabilities.permitted_effects == frozenset({OperationEffect.UPDATED, OperationEffect.UNKNOWN})
