"""Registered evidence mutation bounds and effect settlement."""

from __future__ import annotations

from collections.abc import Sequence
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
    build_ledger_evidence_update_registration,
)
from ....application.ledger.evidence_ports import LedgerEvidencePorts
from ....application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ....application.operations.execution_actor import OperationExecutionCaller, OperationExecutionCallerReader
from ....application.operations.models import OperationIdentity, OperationRequest
from ....application.operations.owner import OperationExecutorContext
from ....application.operations.registry import OperationFrontendProjection, OperationRegistry
from ....application.user_profile.access_contracts import AccessAction, Availability, SessionKind
from ....core.operations import OperationEffect, profile_operation_subject
from ....core.secure_object_write import SecureObjectWrite
from .unused_repository_ports import UnusedBucketEventRepository, UnusedEvidenceAttachmentIngestor

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)
_TYPED_DIRECTORY = "/home/synthetic-person/invoices"


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


@pytest.mark.parametrize(
    "patch",
    [
        {"invoice_date": "08/05/2026"},
        {"invoice_date": "20260508"},
        {"invoice_date": "2026-02-30"},
        {"invoice_date": " 2026-05-08"},
        {"iva_rate": "100.01"},
        {"iva_rate": "-1"},
        {"taxable_base": "1e3"},
    ],
)
def test_update_request_refuses_a_date_or_figure_the_record_cannot_hold(patch: dict[str, str]) -> None:
    """The operation owns the grammar, so every frontend is refused the same value."""
    with pytest.raises(ValidationError):
        LedgerEvidenceUpdatePatch.model_validate(patch)


def test_update_request_admits_a_canonical_date_and_rate() -> None:
    patch = LedgerEvidenceUpdatePatch(invoice_date="2026-05-08", iva_rate="21", taxable_base="100.5")

    assert (patch.invoice_date, patch.iva_rate, patch.taxable_base) == ("2026-05-08", "21", "100.5")


@pytest.mark.parametrize("frontend", [OperationFrontendProjection.CLI, OperationFrontendProjection.MCP])
@pytest.mark.parametrize("action", [AccessAction.SUBMIT, AccessAction.COMMIT, AccessAction.RESULT])
def test_update_is_open_to_the_command_line_and_to_an_agent_under_one_policy(
    frontend: OperationFrontendProjection, action: AccessAction
) -> None:
    definition = build_ledger_evidence_update_definition(_unused_factory)
    registration = build_ledger_evidence_update_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = OperationRequest[BaseModel](
        definition_id=LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerEvidenceUpdateRequest(
            profile_id=_PROFILE,
            evidence_id="evidence-target",
            patch=LedgerEvidenceUpdatePatch(supplier="After SL"),
            patch_fields=("supplier",),
        ),
    )

    def context(asked_from: OperationFrontendProjection) -> OperationAccessContext:
        return OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=_SESSION_CLIENT,
            action=action,
            frontend=asked_from,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
        )

    resolved = resolve_operation_access(registry=registry, request=request, context=context(frontend))
    person = resolve_operation_access(
        registry=registry, request=request, context=context(OperationFrontendProjection.CLI)
    )

    assert registration.contract.permitted_frontends == frozenset(
        {OperationFrontendProjection.CLI, OperationFrontendProjection.MCP}
    )
    assert build_ledger_evidence_remove_definition(_unused_factory).permitted_frontends == frozenset(
        {OperationFrontendProjection.CLI}
    )
    assert resolved.policy == person.policy
    assert resolved.policy.requires_human is False
    assert AccessAction.COMMIT in resolved.policy.actions


class _StoredEvidence:
    """One stored record behind the revision-guarded repository surface the executor requires."""

    def __init__(self, record: PurchaseInvoiceEvidence, backend: object) -> None:
        self.secure_object_repository = backend
        self._record = record

    def load(self, *, bucket_id: str) -> tuple[PurchaseInvoiceEvidence, ...]:
        assert bucket_id == str(_PROFILE)
        return (self._record,)

    def load_revisioned(self, *, bucket_id: str) -> tuple[tuple[PurchaseInvoiceEvidence, ...], str]:
        return self.load(bucket_id=bucket_id), "0" * 64

    def save(self, *, bucket_id: str, records: Sequence[PurchaseInvoiceEvidence]) -> None:
        raise AssertionError("an update that changes nothing wrote the catalogue")

    def save_if_revision_with_secure_object_writes(
        self,
        *,
        bucket_id: str,
        records: Sequence[PurchaseInvoiceEvidence],
        expected_revision_id: str,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        raise AssertionError("an update that changes nothing wrote the catalogue")


def _session_host(frontend: OperationFrontendProjection) -> OperationExecutionCallerReader:
    """What a session host answers for an update it admitted on ``frontend``."""

    def read(identity: OperationIdentity) -> OperationExecutionCaller:
        assert identity.definition_id == LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.ATTENDED, client_id=_SESSION_CLIENT)

    return read


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("frontend", "sealed_path", "withheld"),
    [
        (OperationFrontendProjection.MCP, "invoice.pdf", True),
        (OperationFrontendProjection.CLI, f"{_TYPED_DIRECTORY}/invoice.pdf", False),
    ],
    ids=["mcp", "cli"],
)
async def test_update_result_keeps_the_directory_the_evidence_was_added_from_out_of_an_agents_result(
    monkeypatch: pytest.MonkeyPatch, frontend: OperationFrontendProjection, sealed_path: str, withheld: bool
) -> None:
    """The path is the person's own typing; an agent's result names the file and says the rest was left out."""
    current = _record().model_copy(update={"source_path": f"{_TYPED_DIRECTORY}/invoice.pdf"})
    backend = object()
    ports = LedgerEvidencePorts(
        evidence_repository=_StoredEvidence(current, backend),
        attachment_ingestor=UnusedEvidenceAttachmentIngestor(backend),
        bucket_event_repository=UnusedBucketEventRepository(backend),
    )
    monkeypatch.setattr(
        "cadrumo.application.ledger.evidence_mutation_operation.require_active_bucket_id",
        lambda: str(_PROFILE),
    )
    sealed: list[BaseModel] = []
    effects: list[OperationEffect] = []

    class Events:
        async def phase(self, _phase: str) -> None:
            return None

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            sealed.append(operand)
            return "d" * 64

    def ports_factory(*, bucket_id: str) -> LedgerEvidencePorts:
        assert bucket_id == str(_PROFILE)
        return ports

    executor = LedgerEvidenceUpdateExecutor(ports_factory, execution_caller_reader=_session_host(frontend))
    request = OperationRequest[LedgerEvidenceUpdateRequest](
        definition_id=LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerEvidenceUpdateRequest(
            profile_id=_PROFILE, evidence_id=current.evidence_id, patch=LedgerEvidenceUpdatePatch(), patch_fields=()
        ),
    )
    context = SimpleNamespace(
        identity=SimpleNamespace(
            definition_id=LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        events=Events(),
        operands=Operands(),
    )

    assert await executor.execute(request, cast(OperationExecutorContext, context)) == "d" * 64

    (result,) = sealed
    assert isinstance(result, LedgerEvidenceUpdateExecutionResult)
    assert effects == [OperationEffect.NONE]
    assert result.result.record.source_path == sealed_path
    assert result.result.source_directory_withheld is withheld
    assert (_TYPED_DIRECTORY in result.model_dump_json()) is not withheld
    assert result.result.record.supplier == current.supplier


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

        def save(self, *, bucket_id: str, records: Sequence[PurchaseInvoiceEvidence]) -> None:
            raise AssertionError("the fake service update owns its test result")

        def save_if_revision_with_secure_object_writes(
            self,
            *,
            bucket_id: str,
            records: Sequence[PurchaseInvoiceEvidence],
            expected_revision_id: str,
            extra_writes: tuple[SecureObjectWrite, ...],
        ) -> None:
            raise AssertionError("the fake service update owns its test result")

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
