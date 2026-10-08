"""Ledger missing-reference facts survive real encrypted operation settlement."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.purchase_invoice_evidence import (
    LedgerEvidenceAttachmentIngestor,
    LedgerEvidenceRepositoryAdapter,
)
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger.evidence import PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceService
from cadrumo.application.ledger.evidence_errors import PurchaseInvoiceEvidenceNotFoundError
from cadrumo.application.ledger.evidence_ports import LedgerEvidencePorts
from cadrumo.application.ledger.evidence_read_operation import (
    LEDGER_EVIDENCE_VIEW_NOT_FOUND_REFUSAL_CODE,
    LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceViewExecutionResult,
    LedgerEvidenceViewProjection,
    LedgerEvidenceViewRefusal,
    LedgerEvidenceViewRequest,
    build_ledger_evidence_view_definition,
    build_ledger_evidence_view_registration,
)
from cadrumo.application.operations.error_detail import OperationErrorDetailV1, operation_error_detail_schema
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.projection_services import OperationResultProjectionService
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject

from .supervision_support import run_to_settlement
from .test_supervisor import _repositories, _supervisor

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PROFILE = UUID("a0347100-3a01-4b0a-aeee-347102030405")
_EVIDENCE_ID = "missing-private-evidence-9b18a4"
_PRIVATE_CONTEXT = "private-taxpayer-path-and-financial-value-89a19c"


class _ContextualMissingRepository:
    """A catalogue boundary whose canonical error also carries private content."""

    def load(self, *, bucket_id: str) -> tuple[PurchaseInvoiceEvidence, ...]:
        del bucket_id
        raise PurchaseInvoiceEvidenceNotFoundError(
            translated_message="errors.refused.refused_ledger_evidence_not_found",
            context={"evidence_id": _EVIDENCE_ID, "source_path": _PRIVATE_CONTEXT},
        )

    def save(self, *, bucket_id: str, records: Sequence[PurchaseInvoiceEvidence]) -> None:
        del bucket_id, records
        raise AssertionError("a no-effect read must not save evidence")


@pytest.mark.parametrize("case", ["missing", "contextual_missing", "unexpected", "other_refusal"])
def test_ledger_view_settles_only_declared_static_refusal_detail(
    tmp_path: Path, case: Literal["missing", "contextual_missing", "unexpected", "other_refusal"]
) -> None:
    """Run the real service, executor, supervisor and encrypted projection path.

    The empty production catalogue exercises the original missing-record path.
    A contextual domain error proves that neither its context nor the request
    identity is copied into refusal evidence. Other faults remain code-only.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile:
        ports = LedgerEvidencePorts(
            evidence_repository=LedgerEvidenceRepositoryAdapter(objects=profile.repository),
            attachment_ingestor=LedgerEvidenceAttachmentIngestor(store=AttachmentStore(objects=profile.repository)),
            bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
        )
        with pytest.raises(PurchaseInvoiceEvidenceNotFoundError):
            PurchaseInvoiceEvidenceService(ports=ports).view(bucket_id=str(_PROFILE), evidence_id=_EVIDENCE_ID)

        if case == "contextual_missing":
            ports = replace(ports, evidence_repository=_ContextualMissingRepository())

        attempts: list[str] = []

        def bound_ports(*, bucket_id: str) -> LedgerEvidencePorts:
            assert bucket_id == str(_PROFILE)
            attempts.append(bucket_id)
            if case == "unexpected":
                raise RuntimeError(_PRIVATE_CONTEXT)
            if case == "other_refusal":
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            return ports

        definition = build_ledger_evidence_view_definition(bound_ports)
        registration = build_ledger_evidence_view_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            execution_timeout=timedelta(minutes=1),
        )

        async def settle_and_project() -> None:
            operation_id = await supervisor.submit(
                OperationRequest[BaseModel](
                    definition_id=LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                    payload=LedgerEvidenceViewRequest(profile_id=_PROFILE, evidence_id=_EVIDENCE_ID),
                ),
                operation_id="4" * 64,
            )
            await run_to_settlement(supervisor, operation_id)
            terminal = await supervisor.inspect(operation_id)
            receipt = terminal.terminal_receipt
            assert receipt is not None
            assert receipt.effect is OperationEffect.NONE
            assert receipt.result_ref is None and receipt.error_detail_ref is None
            assert attempts == [str(_PROFILE)]
            schema = registration.contract.result_schema
            assert schema is not None and schema.schema_version == 2
            request = OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=terminal.revision,
                definition_contract_digest=registration.contract.definition_contract_digest,
                result_schema=schema,
            )
            service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)
            resolved = await service.resolve(request, LedgerEvidenceViewProjection)
            if case in {"missing", "contextual_missing"}:
                assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
                assert receipt.refusal_ref == LEDGER_EVIDENCE_VIEW_NOT_FOUND_REFUSAL_CODE
                assert receipt.refusal_detail_ref is not None
                assert isinstance(resolved, OperationResultProjectionSuccessV1)
                projection = resolved.projection
                assert isinstance(projection, LedgerEvidenceViewProjection)
                assert projection.profile_id == _PROFILE
                assert projection.outcome == LedgerEvidenceViewRefusal()
                private = await operands.resolve(receipt.refusal_detail_ref, LedgerEvidenceViewExecutionResult)
                assert private.result == projection
                assert _EVIDENCE_ID not in private.model_dump_json()
                assert _PRIVATE_CONTEXT not in private.model_dump_json()

                stale = await service.resolve(
                    request.model_copy(update={"terminal_revision": terminal.revision + 1}),
                    LedgerEvidenceViewProjection,
                )
                assert isinstance(stale, OperationResultProjectionRefusalV1)
                assert stale.code is OperationResultProjectionRefusalCode.STALE_OPERATION_REVISION
                old_schema = await service.resolve(
                    request.model_copy(update={"result_schema": schema.model_copy(update={"schema_version": 1})}),
                    LedgerEvidenceViewProjection,
                )
                assert isinstance(old_schema, OperationResultProjectionRefusalV1)
                assert old_schema.code is OperationResultProjectionRefusalCode.RESULT_SCHEMA_MISMATCH
                raw_private = await service.resolve(request, LedgerEvidenceViewExecutionResult)
                assert isinstance(raw_private, OperationResultProjectionRefusalV1)
                assert raw_private.code is OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE
            else:
                assert receipt.refusal_detail_ref is None
                assert isinstance(resolved, OperationResultProjectionRefusalV1)
                if case == "unexpected":
                    assert terminal.terminal_condition is OperationTerminalCondition.FAILED
                    assert receipt.failure_error_code is None and receipt.diagnostic_ref is not None
                else:
                    assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
                    assert receipt.refusal_ref == get_registered_error_code(ProfileAccessRefusedError).code

            generic_detail = await service.resolve(
                request.model_copy(update={"result_schema": operation_error_detail_schema()}), OperationErrorDetailV1
            )
            assert isinstance(generic_detail, OperationResultProjectionRefusalV1)

        asyncio.run(settle_and_project())

        stored_bytes = b"".join(path.read_bytes() for path in tmp_path.rglob("*") if path.is_file())
        assert _EVIDENCE_ID.encode() not in stored_bytes
        assert _PRIVATE_CONTEXT.encode() not in stored_bytes
