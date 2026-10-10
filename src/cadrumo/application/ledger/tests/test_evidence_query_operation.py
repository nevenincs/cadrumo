"""The agent-facing evidence query: admitted on MCP alone, and released without a host path."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.time.clock import now
from ....domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import evidence_read_operation as worker
from ..evidence import MediaKind, PurchaseInvoiceEvidence
from ..evidence_ports import EvidenceAttachmentIngestorProtocol, LedgerEvidencePorts
from ..evidence_read_operation import (
    LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID,
    LedgerEvidenceListExecutionResult,
    LedgerEvidenceListExecutor,
    LedgerEvidenceListRequest,
    LedgerEvidenceQueryExecutionResult,
    LedgerEvidenceQueryExecutor,
    LedgerEvidenceQueryProjection,
    LedgerEvidenceQueryRequest,
    build_ledger_evidence_query_definition,
    build_ledger_evidence_query_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_WINDOWS_EVIDENCE_ID = "e" * 16
_POSIX_EVIDENCE_ID = "f" * 16
_WINDOWS_PATH = r"C:\Users\synthetic-operator\Documents\facturas-privadas\factura-417.pdf"
_POSIX_PATH = "/home/synthetic-operator/facturas-privadas/recibo-88.png"
_HOST_PATH_FRAGMENTS = ("synthetic-operator", "facturas-privadas", "Documents", "C:", "/home")


def _record(evidence_id: str, source_path: str, media_kind: MediaKind) -> PurchaseInvoiceEvidence:
    return PurchaseInvoiceEvidence.model_validate(
        {
            "evidence_id": evidence_id,
            "bucket_id": str(_PROFILE),
            "source_path": source_path,
            "source_sha256": "a" * 64,
            "attachment_id": "a" * 64,
            "media_kind": media_kind,
            "supplier": "Proveedor Sintetico SL",
            "invoice_number": "SYN-001",
            "invoice_date": "2026-04-01",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "notes": "nota escrita por la persona",
            "created_at": datetime(2026, 4, 2, 10, 30, tzinfo=UTC),
            "updated_at": datetime(2026, 4, 3, 9, 0, tzinfo=UTC),
        }
    )


_RECORDS = (
    _record(_WINDOWS_EVIDENCE_ID, _WINDOWS_PATH, MediaKind.PDF),
    _record(_POSIX_EVIDENCE_ID, _POSIX_PATH, MediaKind.IMAGE),
)


class _StoredEvidence:
    """An evidence catalogue held in memory, which the reads under test never write."""

    def load(self, *, bucket_id: str) -> tuple[PurchaseInvoiceEvidence, ...]:
        return tuple(record for record in _RECORDS if record.bucket_id == bucket_id)

    def save(self, *, bucket_id: str, records: Sequence[PurchaseInvoiceEvidence]) -> None:
        raise AssertionError(f"an evidence read wrote the catalogue of {bucket_id}: {len(records)} record(s)")


def _ports_factory(*, bucket_id: str) -> LedgerEvidencePorts:
    assert bucket_id == str(_PROFILE)
    return LedgerEvidencePorts(
        evidence_repository=_StoredEvidence(),
        attachment_ingestor=cast(EvidenceAttachmentIngestorProtocol, object()),
        bucket_event_repository=cast(BucketEventHistoryRepositoryProtocol, object()),
    )


def _unopened_factory(*, bucket_id: str) -> LedgerEvidencePorts:
    raise AssertionError(f"schema and access construction must not compose evidence ports for {bucket_id}")


def _registry() -> OperationRegistry:
    definition = build_ledger_evidence_query_definition(_unopened_factory)
    registration = build_ledger_evidence_query_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def _request(
    payload: BaseModel, definition_id: str, *, subject_profile_id: UUID = _PROFILE
) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(subject_profile_id)),
        payload=payload,
    )


def _query_request(evidence_id: str | None = None) -> OperationRequest[BaseModel]:
    return _request(
        LedgerEvidenceQueryRequest(profile_id=_PROFILE, evidence_id=evidence_id),
        LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID,
    )


def _access_context(registry: OperationRegistry, frontend: OperationFrontendProjection) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=frontend,
        contract=registry.lookup_public_contract(LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID),
        published_authority=Availability.AVAILABLE,
    )


class _Operands:
    def __init__(self) -> None:
        self.values: list[BaseModel] = []

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        self.values.append(value)
        return "d" * 64


class _Events:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, code: str) -> None:
        self.phases.append(code)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


def _executor_context(definition_id: str) -> tuple[OperationExecutorContext, _Operands, _Events]:
    operands, events = _Operands(), _Events()
    context = SimpleNamespace(
        identity=OperationIdentity(
            operation_id="e" * 64,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        events=events,
        operands=operands,
    )
    return cast(OperationExecutorContext, cast(object, context)), operands, events


def _receipt(definition_id: str) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="e" * 64,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=now(),
        result_ref="d" * 64,
    )


async def _run_query(monkeypatch: pytest.MonkeyPatch, evidence_id: str | None) -> LedgerEvidenceQueryProjection:
    """Run the real executor and release its result through the registered projector."""
    monkeypatch.setattr(worker, "require_active_bucket_id", lambda: str(_PROFILE))
    request = OperationRequest[LedgerEvidenceQueryRequest](
        definition_id=LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerEvidenceQueryRequest(profile_id=_PROFILE, evidence_id=evidence_id),
    )
    context, operands, events = _executor_context(LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID)

    reference = await LedgerEvidenceQueryExecutor(_ports_factory).execute(request, context)

    assert reference == "d" * 64
    assert events.phases == [LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID]
    assert events.effects == [OperationEffect.NONE]
    (private,) = operands.values
    assert isinstance(private, LedgerEvidenceQueryExecutionResult)
    registration = _registry().lookup_public_registration(LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID)
    projector = registration.result_projector
    assert projector is not None
    released = projector(private, _receipt(LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID))
    assert isinstance(released, LedgerEvidenceQueryProjection)
    return released


def test_the_query_is_admitted_on_mcp_alone_for_either_kind_of_session_without_a_commit_door() -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID)

    resolved = resolve_operation_access(
        registry=registry,
        request=_query_request(),
        context=_access_context(registry, OperationFrontendProjection.MCP),
    )

    assert contract.permitted_frontends == frozenset({OperationFrontendProjection.MCP})
    assert resolved.request.frontend is OperationFrontendProjection.MCP
    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.period_independent is True
    # A session under the person's sign-in and one under an enrolled key differ
    # in kind alone, and only a human-only policy tells the two apart.
    assert resolved.policy.requires_human is False
    assert AccessAction.COMMIT not in resolved.policy.actions
    for frontend in (OperationFrontendProjection.CLI, OperationFrontendProjection.TUI):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(
                registry=registry, request=_query_request(), context=_access_context(registry, frontend)
            )
        assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED


def test_the_query_refuses_a_request_addressed_to_another_profile() -> None:
    registry = _registry()
    foreign = _request(
        LedgerEvidenceQueryRequest(profile_id=_PROFILE),
        LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID,
        subject_profile_id=_OTHER_PROFILE,
    )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry, request=foreign, context=_access_context(registry, OperationFrontendProjection.MCP)
        )

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


@pytest.mark.asyncio
async def test_the_query_releases_every_record_with_its_file_name_and_no_host_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    released = await _run_query(monkeypatch, None)

    assert released.profile_id == _PROFILE
    assert released.evidence_id is None
    assert released.count == 2
    windows, posix = released.rows
    assert (windows.evidence_id, windows.source_file_name) == (_WINDOWS_EVIDENCE_ID, "factura-417.pdf")
    assert (posix.evidence_id, posix.source_file_name) == (_POSIX_EVIDENCE_ID, "recibo-88.png")
    assert windows.media_kind is MediaKind.PDF and posix.media_kind is MediaKind.IMAGE
    assert windows.source_sha256 == "a" * 64 and windows.attachment_id == "a" * 64
    assert windows.supplier == "Proveedor Sintetico SL"
    assert windows.invoice_number == "SYN-001" and windows.invoice_date == "2026-04-01"
    assert (windows.taxable_base, windows.iva_rate, windows.iva_amount) == ("100.00", "0.21", "21.00")
    assert windows.notes == "nota escrita por la persona"
    assert windows.created_at == datetime(2026, 4, 2, 10, 30, tzinfo=UTC)
    assert windows.updated_at == datetime(2026, 4, 3, 9, 0, tzinfo=UTC)
    document = released.model_dump_json()
    assert [fragment for fragment in _HOST_PATH_FRAGMENTS if fragment in document] == []
    assert "source_path" not in document


@pytest.mark.asyncio
async def test_the_query_narrows_to_one_exact_identity_and_reports_an_unknown_one_as_no_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    one = await _run_query(monkeypatch, _POSIX_EVIDENCE_ID)
    none = await _run_query(monkeypatch, "0" * 16)

    assert one.evidence_id == _POSIX_EVIDENCE_ID
    assert [row.evidence_id for row in one.rows] == [_POSIX_EVIDENCE_ID]
    assert (none.evidence_id, none.count, none.rows) == ("0" * 16, 0, ())


@pytest.mark.asyncio
async def test_the_person_list_still_releases_the_path_the_operator_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker, "require_active_bucket_id", lambda: str(_PROFILE))
    request = OperationRequest[LedgerEvidenceListRequest](
        definition_id=LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerEvidenceListRequest(profile_id=_PROFILE),
    )
    context, operands, _events = _executor_context(LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID)

    await LedgerEvidenceListExecutor(_ports_factory).execute(request, context)

    (private,) = operands.values
    assert isinstance(private, LedgerEvidenceListExecutionResult)
    assert [row.source_path for row in private.result.rows] == [_WINDOWS_PATH, _POSIX_PATH]


def test_the_query_result_declares_a_file_name_and_no_path_field() -> None:
    schema = LedgerEvidenceQueryProjection.model_json_schema()
    row = schema["$defs"]["LedgerEvidenceAgentRecordProjection"]["properties"]

    assert set(schema["properties"]) == {"profile_id", "evidence_id", "count", "rows"}
    assert set(row) == {
        "evidence_id",
        "bucket_id",
        "source_file_name",
        "source_sha256",
        "attachment_id",
        "media_kind",
        "supplier",
        "invoice_number",
        "invoice_date",
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "notes",
        "created_at",
        "updated_at",
    }


def test_the_query_projector_refuses_the_person_list_and_a_receipt_of_another_operation() -> None:
    registration = _registry().lookup_public_registration(LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID)
    projector = registration.result_projector
    assert projector is not None
    result = LedgerEvidenceQueryExecutionResult(
        profile_id=_PROFILE, result=LedgerEvidenceQueryProjection(profile_id=_PROFILE, count=0, rows=())
    )

    with pytest.raises(ValueError):
        projector(result, _receipt(LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID))
    with pytest.raises(ValueError):
        projector(
            LedgerEvidenceListRequest(profile_id=_PROFILE), _receipt(LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID)
        )
