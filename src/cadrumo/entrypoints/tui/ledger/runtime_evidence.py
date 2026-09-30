"""Purchase invoice evidence through one retained installed TUI session."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ....application.ledger.evidence import MediaKind
from ....application.ledger.evidence_add_operation import (
    LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
    LedgerEvidenceAddProjection,
    LedgerEvidenceAddRequest,
)
from ....application.ledger.evidence_read_operation import (
    LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
    LedgerEvidenceListProjection,
    LedgerEvidenceListRequest,
    LedgerEvidenceRecordProjection,
)
from ....application.ledger.invoice_evidence_operation import (
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
    LedgerEvidenceConfirmProjection,
    LedgerEvidenceConfirmRequest,
    LedgerEvidenceExtractProjection,
    LedgerEvidenceExtractRequest,
    LedgerEvidenceReaderReadinessProjection,
    LedgerEvidenceReaderReadinessRequest,
)
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....application.operations.frontend_requests import (
    OperationObservationRefusalV1,
    OperationObservationSuccessV1,
)
from ....application.operations.public_scalar import PublicDecimal
from ....application.operations.registry import OperationFrontendProjection, OperationSchemaIdentityV1
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ....entrypoints.tui.account import AccountSessionExpiredError
from ..operations.runtime_controller import RuntimeOperationController
from ..runtime_account_session import read_runtime_account_session
from .models import (
    LedgerEvidenceConfirmationV1,
    LedgerEvidenceConfirmedV1,
    LedgerEvidenceDraftV1,
    LedgerEvidenceRecordRowV1,
    LedgerEvidenceRecordStatus,
    LedgerReaderReadinessV1,
)

_ResultT = TypeVar("_ResultT", bound=BaseModel)
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic", ".heif"})


@dataclass(frozen=True, slots=True)
class _ReviewedEvidence:
    """The opaque review binding retained for one exact TUI session."""

    profile_id: UUID
    session_id: UUID
    evidence_id: str
    source_sha256: str
    draft_review_sha256: str


class RuntimeEvidenceTuiDoorV1:
    """Submit registered evidence operations under the original TUI profile lease."""

    def __init__(self, client: RuntimeFrontendClient, *, profile_label: str) -> None:
        """Pin the exact authenticated client and start with no reviewed draft."""
        if client.frontend is not OperationFrontendProjection.TUI or not profile_label:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._client = client
        self._profile_id = client.profile_id
        self._session_id = client.session_id
        self._profile_label = profile_label
        self._review: _ReviewedEvidence | None = None
        self._require_binding()

    def _require_binding(self) -> None:
        if (
            self._client.frontend is not OperationFrontendProjection.TUI
            or self._client.profile_id != self._profile_id
            or self._client.session_id != self._session_id
        ):
            self._review = None
            raise AccountSessionExpiredError()
        try:
            read_runtime_account_session(
                self._client,
                profile_id=self._profile_id,
                session_id=self._session_id,
                profile_label=self._profile_label,
            )
        except AccountSessionExpiredError:
            self._review = None
            raise

    def list_records(self) -> tuple[LedgerEvidenceRecordRowV1, ...]:
        """Read the complete catalogue on the caller's background thread."""
        projection = self._call_sync(
            LedgerEvidenceListRequest(profile_id=self._profile_id),
            definition_id=LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
            result_type=LedgerEvidenceListProjection,
            success_effect=OperationEffect.NONE,
        )
        if projection.count != len(projection.rows):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return tuple(self._record_row(row) for row in projection.rows)

    async def add(self, source_path: str) -> LedgerEvidenceRecordRowV1:
        """Register one file and correlate its typed result with the durable receipt."""
        projection = await self._execute(
            LedgerEvidenceAddRequest(profile_id=self._profile_id, source_path=source_path),
            definition_id=LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
            result_type=LedgerEvidenceAddProjection,
            success_effect=OperationEffect.UPDATED,
        )
        record = projection.record
        expected_kind = MediaKind.IMAGE if Path(source_path).suffix.lower() in _IMAGE_EXTENSIONS else MediaKind.PDF
        if (
            projection.profile_id != self._profile_id
            or len(projection.bucket_event_ids) != 1
            or not _hex_digest(projection.bucket_event_ids[0])
            or record.bucket_id != str(self._profile_id)
            or record.source_path != source_path
            or record.media_kind is not expected_kind
            or record.attachment_id != record.source_sha256
            or not _evidence_id(record.evidence_id)
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return self._record_row(record)

    def reader_readiness(self) -> LedgerReaderReadinessV1:
        """Measure the local reader without provisioning or starting it."""
        projection = self._call_sync(
            LedgerEvidenceReaderReadinessRequest(profile_id=self._profile_id),
            definition_id=LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
            result_type=LedgerEvidenceReaderReadinessProjection,
            success_effect=OperationEffect.NONE,
        )
        failed_condition = projection.host.failed_condition_id
        if failed_condition is None:
            failed_condition = next(
                (role.failed_condition_id for role in projection.roles if not role.ready),
                None,
            )
        return LedgerReaderReadinessV1(
            extraction_ready=projection.extraction_ready,
            failed_condition_id=failed_condition,
        )

    async def extract(self, evidence_id: str) -> LedgerEvidenceDraftV1:
        """Extract locally and retain only digests needed to bind a later confirmation."""
        self._require_binding()
        self._review = None
        projection = await self._execute(
            LedgerEvidenceExtractRequest(profile_id=self._profile_id, evidence_id=evidence_id),
            definition_id=LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
            result_type=LedgerEvidenceExtractProjection,
            success_effect=OperationEffect.NONE,
        )
        if (
            projection.profile_id != self._profile_id
            or projection.evidence_id != evidence_id
            or projection.attachment_id is not None
            or projection.consent_audit_effect is not OperationEffect.NONE
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._review = _ReviewedEvidence(
            profile_id=self._profile_id,
            session_id=self._session_id,
            evidence_id=evidence_id,
            source_sha256=projection.source_sha256,
            draft_review_sha256=projection.draft_review_sha256,
        )
        return self._draft(projection, evidence_id=evidence_id)

    async def confirm(self, confirmation: LedgerEvidenceConfirmationV1) -> LedgerEvidenceConfirmedV1:
        """Re-read and confirm only the exact source and draft reviewed in this session."""
        self._require_binding()
        reviewed = self._review
        if (
            reviewed is None
            or reviewed.profile_id != self._profile_id
            or reviewed.session_id != self._session_id
            or reviewed.evidence_id != confirmation.evidence_id
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        # Confirmation is a one-shot use of the review. A refusal, uncertain
        # receipt, or successful write all require the operator to review again.
        self._review = None
        projection = await self._execute(
            LedgerEvidenceConfirmRequest(
                profile_id=self._profile_id,
                evidence_id=confirmation.evidence_id,
                expected_source_sha256=reviewed.source_sha256,
                expected_draft_review_sha256=reviewed.draft_review_sha256,
                kind=confirmation.kind,
                counterparty_country=confirmation.country_code,
                counterparty_name=confirmation.counterparty_name,
            ),
            definition_id=LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
            result_type=LedgerEvidenceConfirmProjection,
            success_effect=OperationEffect.UPDATED,
        )
        if (
            projection.profile_id != self._profile_id
            or projection.evidence_id != confirmation.evidence_id
            or projection.attachment_id is not None
            or projection.source_sha256 != reviewed.source_sha256
            or projection.reviewed_draft_sha256 != reviewed.draft_review_sha256
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        invoice = projection.confirmation.invoice
        if (
            invoice.bucket_id is None
            or str(invoice.bucket_id) != str(self._profile_id)
            or invoice.kind is not confirmation.kind
            or invoice.counterparty_country != confirmation.country_code
            or invoice.source_sha256 != reviewed.source_sha256
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        discrepancy = projection.confirmation.total_discrepancy
        return LedgerEvidenceConfirmedV1(
            invoice_id=invoice.invoice_id,
            invoice_number=invoice.invoice_number,
            grand_total=Decimal(invoice.grand_total.decimal),
            currency=invoice.currency,
            created=projection.confirmation.created,
            printed_total_disagrees=discrepancy is not None and Decimal(discrepancy.difference.decimal) != 0,
        )

    def _call_sync[ResultT: BaseModel](
        self,
        request: BaseModel,
        *,
        definition_id: str,
        result_type: type[ResultT],
        success_effect: OperationEffect,
    ) -> ResultT:
        """Run a sync protocol method on the screen's worker thread."""
        return asyncio.run(
            self._execute(
                request,
                definition_id=definition_id,
                result_type=result_type,
                success_effect=success_effect,
            )
        )

    async def _execute[ResultT: BaseModel](
        self,
        request: BaseModel,
        *,
        definition_id: str,
        result_type: type[ResultT],
        success_effect: OperationEffect,
    ) -> ResultT:
        """Submit, observe, disclose and correlate one terminal receipt."""
        self._require_binding()
        if getattr(request, "profile_id", None) != self._profile_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        subject_ref = profile_operation_subject(str(self._profile_id))
        request_schema = OperationSchemaIdentityV1.from_model(
            schema_id=f"{definition_id}.request",
            schema_version=1,
            model_type=type(request),
        )
        deadline = time.monotonic() + 120
        controller: RuntimeOperationController | None = None
        terminal_projection: OperationPublicProjectionV1 | None = None
        try:
            controller = await RuntimeOperationController.submit(
                self._client,
                definition_id=definition_id,
                subject_ref=subject_ref,
                payload=request,
                expected_session_id=self._session_id,
                deadline=deadline,
            )
            await controller.start()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                observed = await controller.observe(0, page_limit=1)
                if isinstance(observed, OperationObservationRefusalV1):
                    raise RuntimeFrontendRefusedError(observed.code.value)
                if not isinstance(observed, OperationObservationSuccessV1):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                state = observed.projection
                if (
                    state.operation_id != controller.operation_id
                    or state.definition_id != definition_id
                    or state.subject_ref != subject_ref
                    or state.definition_contract.request_schema != request_schema
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if state.lifecycle is OperationLifecycle.TERMINAL:
                    terminal_projection = state
                    break
                await asyncio.sleep(min(0.05, remaining))

            condition = terminal_projection.terminal_condition
            if condition is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if condition is not OperationTerminalCondition.SUCCEEDED:
                raise RuntimeFrontendRefusedError(
                    terminal_projection.refusal_ref
                    or terminal_projection.failure_error_code
                    or "operation_not_successful"
                )
            if (
                terminal_projection.effect is not success_effect
                or terminal_projection.refusal_ref is not None
                or terminal_projection.failure_error_code is not None
                or terminal_projection.diagnostic_ref is not None
                or terminal_projection.result_ref is None
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            result = await controller.read_settled_result(
                terminal_projection,
                result_type,
                result_version=1,
            )
            self._require_binding()
            if getattr(result, "profile_id", None) != self._profile_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return result
        except AccountSessionExpiredError as error:
            raise self._session_expired_with_receipt(controller, terminal_projection) from error
        except (RuntimeFrontendRefusedError, RuntimeRefusalError):
            try:
                self._require_binding()
            except AccountSessionExpiredError as error:
                raise self._session_expired_with_receipt(controller, terminal_projection) from error
            raise

    @staticmethod
    def _session_expired_with_receipt(
        controller: RuntimeOperationController | None,
        projection: OperationPublicProjectionV1 | None,
    ) -> AccountSessionExpiredError:
        """Keep an observed operation ID and effect visible if the retained session expires."""
        if controller is None:
            return AccountSessionExpiredError()
        condition = projection.terminal_condition if projection is not None else None
        effect = projection.effect if projection is not None else OperationEffect.UNKNOWN
        refusal_code = projection.refusal_ref if projection is not None else None
        return AccountSessionExpiredError(
            context={
                "operation_id": str(controller.operation_id),
                "terminal_condition": condition.value if condition is not None else "unknown",
                "effect": effect.value,
                "refusal_code": refusal_code,
            }
        )

    @staticmethod
    def _record_row(record: LedgerEvidenceRecordProjection) -> LedgerEvidenceRecordRowV1:
        """Expose only the filename and fields the current evidence screen declares."""
        return LedgerEvidenceRecordRowV1(
            evidence_id=record.evidence_id,
            media_kind=record.media_kind.value,
            file_name=Path(record.source_path).name,
            supplier=record.supplier,
            invoice_number=record.invoice_number,
            created_at=record.created_at.isoformat(),
            status=LedgerEvidenceRecordStatus.UNMEASURED,
        )

    @staticmethod
    def _draft(projection: LedgerEvidenceExtractProjection, *, evidence_id: str) -> LedgerEvidenceDraftV1:
        """Map the review screen's display fields from the complete canonical draft."""
        draft = projection.draft
        return LedgerEvidenceDraftV1(
            evidence_id=evidence_id,
            supplier_name=draft.supplier_name,
            supplier_tax_id=draft.supplier_tax_id,
            invoice_number=draft.invoice_number,
            invoice_date=draft.invoice_date,
            taxable_base=_decimal_text(draft.taxable_base),
            iva_rate=_decimal_text(draft.iva_rate),
            iva_amount=_decimal_text(draft.iva_amount),
            grand_total=_decimal_text(draft.grand_total),
            currency=draft.currency,
            suggested_kind=draft.suggested_kind,
            discrepancies=len(draft.discrepancies),
        )


def _decimal_text(value: PublicDecimal | None) -> str | None:
    return None if value is None else value.decimal


def _evidence_id(value: str) -> bool:
    return len(value) == 16 and all(character in "0123456789abcdef" for character in value)


def _hex_digest(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


__all__ = ["RuntimeEvidenceTuiDoorV1"]
