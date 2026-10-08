"""Purchase invoice evidence through one retained installed TUI session."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.ledger.evidence import MediaKind
from ...application.ledger.evidence_add_operation import (
    LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
    LedgerEvidenceAddProjection,
    LedgerEvidenceAddRequest,
)
from ...application.ledger.evidence_read_operation import (
    LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
    LedgerEvidenceListProjection,
    LedgerEvidenceListRequest,
    LedgerEvidenceRecordProjection,
)
from ...application.ledger.invoice_evidence_confirm_operation import (
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
    LedgerEvidenceConfirmProjection,
    LedgerEvidenceConfirmRequest,
)
from ...application.ledger.invoice_evidence_extract_operation import (
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
    LedgerEvidenceExtractProjection,
    LedgerEvidenceExtractRequest,
)
from ...application.ledger.invoice_evidence_readiness_operation import (
    LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
    LedgerEvidenceReaderReadinessProjection,
    LedgerEvidenceReaderReadinessRequest,
)
from ...application.operations.frontend_projection import OperationPublicProjectionV1
from ...application.operations.public_scalar import PublicDecimal
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.hex import is_hex16, is_hex64
from ...core.operations import (
    OperationEffect,
    OperationTerminalCondition,
)
from .ledger.models import (
    LedgerEvidenceConfirmationV1,
    LedgerEvidenceConfirmedV1,
    LedgerEvidenceDraftV1,
    LedgerEvidenceRecordRowV1,
    LedgerEvidenceRecordStatus,
    LedgerReaderReadinessV1,
)
from .operations.runtime_profile_session import RuntimeProfileSession

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


def _require_review(
    reviewed: _ReviewedEvidence | None,
    *,
    profile_id: UUID,
    session_id: UUID,
    evidence_id: str,
) -> _ReviewedEvidence:
    if (
        reviewed is None
        or reviewed.profile_id != profile_id
        or reviewed.session_id != session_id
        or reviewed.evidence_id != evidence_id
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return reviewed


def _validate_confirmation_projection(
    projection: LedgerEvidenceConfirmProjection,
    reviewed: _ReviewedEvidence,
    confirmation: LedgerEvidenceConfirmationV1,
    profile_id: UUID,
) -> None:
    if (
        projection.profile_id != profile_id
        or projection.evidence_id != confirmation.evidence_id
        or projection.attachment_id is not None
        or projection.source_sha256 != reviewed.source_sha256
        or projection.reviewed_draft_sha256 != reviewed.draft_review_sha256
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def _validate_confirmed_invoice(
    projection: LedgerEvidenceConfirmProjection,
    reviewed: _ReviewedEvidence,
    confirmation: LedgerEvidenceConfirmationV1,
    profile_id: UUID,
) -> None:
    invoice = projection.confirmation.invoice
    if (
        invoice.bucket_id is None
        or str(invoice.bucket_id) != str(profile_id)
        or invoice.kind is not confirmation.kind
        or invoice.counterparty_country != confirmation.country_code
        or invoice.source_sha256 != reviewed.source_sha256
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def _confirmed_result(projection: LedgerEvidenceConfirmProjection) -> LedgerEvidenceConfirmedV1:
    invoice = projection.confirmation.invoice
    discrepancy = projection.confirmation.total_discrepancy
    return LedgerEvidenceConfirmedV1(
        invoice_id=invoice.invoice_id,
        invoice_number=invoice.invoice_number,
        grand_total=Decimal(invoice.grand_total.decimal),
        currency=invoice.currency,
        created=projection.confirmation.created,
        printed_total_disagrees=discrepancy is not None and Decimal(discrepancy.difference.decimal) != 0,
    )


class RuntimeEvidenceTuiDoorV1:
    """Submit registered evidence operations under the original TUI profile lease."""

    def __init__(self, client: RuntimeFrontendClient, *, profile_label: str) -> None:
        """Pin the exact authenticated client and start with no reviewed draft."""
        self._review: _ReviewedEvidence | None = None
        self._session = RuntimeProfileSession(client, profile_label=profile_label, on_expired=self._drop_review)
        self._profile_id = self._session.profile_id

    def _drop_review(self) -> None:
        self._review = None

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
            LedgerEvidenceAddRequest(
                profile_id=self._profile_id,
                source_path=source_path,
                source_directory=str(Path.cwd()),
            ),
            definition_id=LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
            result_type=LedgerEvidenceAddProjection,
            success_effect=OperationEffect.UPDATED,
        )
        record = projection.record
        expected_kind = MediaKind.IMAGE if Path(source_path).suffix.lower() in _IMAGE_EXTENSIONS else MediaKind.PDF
        if (
            projection.profile_id != self._profile_id
            or len(projection.bucket_event_ids) != 1
            or not is_hex64(projection.bucket_event_ids[0])
            or record.bucket_id != str(self._profile_id)
            or record.source_path != source_path
            or record.media_kind is not expected_kind
            or record.attachment_id != record.source_sha256
            or not is_hex16(record.evidence_id)
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
        self._session.require_binding()
        self._review = None
        projection = await self._execute(
            LedgerEvidenceExtractRequest(profile_id=self._profile_id, evidence_id=evidence_id),
            definition_id=LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
            result_type=LedgerEvidenceExtractProjection,
            result_version=2,
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
            session_id=self._session.session_id,
            evidence_id=evidence_id,
            source_sha256=projection.source_sha256,
            draft_review_sha256=projection.draft_review_sha256,
        )
        return self._draft(projection, evidence_id=evidence_id)

    async def confirm(self, confirmation: LedgerEvidenceConfirmationV1) -> LedgerEvidenceConfirmedV1:
        """Re-read and confirm only the exact source and draft reviewed in this session."""
        self._session.require_binding()
        reviewed = _require_review(
            self._review,
            profile_id=self._profile_id,
            session_id=self._session.session_id,
            evidence_id=confirmation.evidence_id,
        )
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
            result_version=2,
            success_effect=OperationEffect.UPDATED,
        )
        _validate_confirmation_projection(projection, reviewed, confirmation, self._profile_id)
        _validate_confirmed_invoice(projection, reviewed, confirmation, self._profile_id)
        return _confirmed_result(projection)

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
        result_version: int = 1,
        success_effect: OperationEffect,
    ) -> ResultT:
        """Submit, observe, disclose and correlate one terminal receipt."""

        def admit(terminal: OperationPublicProjectionV1) -> None:
            if (
                terminal.effect is not success_effect
                or terminal.refusal_ref is not None
                or terminal.failure_error_code is not None
                or terminal.diagnostic_ref is not None
                or terminal.result_ref is None
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

        def settle(
            result: ResultT,
            _condition: OperationTerminalCondition,
            _terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if getattr(result, "profile_id", None) != self._profile_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

        return await self._session.run_operation(
            request,
            definition_id=definition_id,
            result_type=result_type,
            settle=settle,
            admit=admit,
            result_version=result_version,
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
            label_reading_fallback=(
                None if projection.label_reading_fallback is None else projection.label_reading_fallback.to_fallback()
            ),
            full_projection=draft,
        )


def _decimal_text(value: PublicDecimal | None) -> str | None:
    return None if value is None else value.decimal


__all__ = ["RuntimeEvidenceTuiDoorV1"]
