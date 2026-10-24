"""Settle each registered operation that wraps a local AI consumer, and read what a client in another process reads.

Every driver runs one operation through the production registry and the real
supervisor, journal and encrypted operand store, inside an enrolled profile,
against a real loopback runtime that answers its inventory with no model and
records every request it is sent. What the driver returns is what a frontend
in another process can read of the settled operation: its recorded error
detail when it stopped, or its public result when it succeeded. Either may
carry the reader probe's verdict, and the gate judges that verdict.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Protocol, override
from uuid import UUID

from pydantic import BaseModel

from ...adapters.outbound.llm.column_role_mapping import resolve_column_roles
from ...adapters.outbound.llm.statement_reading import LocalStatementReader
from ...adapters.persistence.storage.attachment import AttachmentStore
from ...application.invoices.catalogue_intake_contracts import (
    INVOICE_IMPORT_OPERATION_DEFINITION_ID,
    InvoiceImportRequest,
)
from ...application.ledger.actions_import import LedgerProviderID
from ...application.ledger.attachment_mutation_operation import (
    LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    LedgerAttachmentOperationResult,
    LedgerAttachRequest,
)
from ...application.ledger.column_roles import bind_column_role_mapping_resolver
from ...application.ledger.evidence_ingestion_contracts import (
    LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
)
from ...application.ledger.import_operation import (
    LEDGER_IMPORT_OPERATION_DEFINITION_ID,
    LedgerImportRequest,
    LedgerImportResultProjection,
)
from ...application.ledger.invoice_evidence_confirm_operation import (
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
    LedgerEvidenceConfirmRequest,
)
from ...application.ledger.invoice_evidence_extract_operation import (
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
    LedgerEvidenceExtractRequest,
)
from ...application.ledger.llm_review_contracts import (
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
    LEDGER_SPLIT_REVIEW_DEFINITION_ID,
    LedgerLlmReviewRequest,
)
from ...application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from ...application.ledger.statement_reading import bind_statement_reader_factory
from ...application.operations.error_detail import OperationErrorDetailV1, operation_error_detail_schema
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.registry import OperationRegistry
from ...application.operations.subject_reference import expected_operation_subject
from ...application.operator_actions.models import PreconditionVerdict
from ...application.operator_actions.projection import PreconditionVerdictSnapshot
from ...core.config import override_settings
from ...core.model_catalogue import ModelRole, candidates_for_role, default_model_runtime_id
from ...core.operations import OperationTerminalCondition
from ...domain.attachments.enums import AttachmentKind, AttachmentSource
from ...domain.attachments.models import Attachment
from ...domain.iva.schema import InvoiceKind
from ...tests.inventory import FIXTURES_DIR
from ...tests.llm_vision_evidence_support import png_image
from ...tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from ...tests.pdf_fixtures import text_pdf_bytes
from . import registered_executor_case_support as conformance

#: An operator-named mapping model, honoured as written.
_OPERATOR_MAPPING_MODEL = next(
    candidate.runtime_id
    for candidate in candidates_for_role(ModelRole.COLUMN_ROLE_MAPPING)
    if candidate.runtime_id != default_model_runtime_id(ModelRole.COLUMN_ROLE_MAPPING)
)
#: The document readers' models, named as the shipped defaults so no row depends
#: on this host's settings. The probe judges them against installed memory only,
#: never against what is free while the gate runs beside other work.
_VISION_MODEL = default_model_runtime_id(ModelRole.VISION_TRANSCRIPTION)
_TEXT_MODEL = default_model_runtime_id(ModelRole.TEXT_EXTRACTION)
_EXPORT_ONLY_THE_MAPPER_READS = FIXTURES_DIR / "financial" / "tabular-dialects" / "expenses_app_export_2026.csv"
_BOOK_ONLY_THE_MAPPER_READS = FIXTURES_DIR / "financial" / "tabular-dialects" / "libro_facturas_expedidas_2025_2026.csv"
_READABLE_STATEMENT = (
    "Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda\n"
    "08/04/2026;08/04/2026;Pago material oficina;-121,00;4300,75;EUR\n"
)
#: Figures with no label the rules read, so a text-layer document needs the text model.
_NO_LABELS = ("B1234567X B17283946 766,30",)


@dataclass(frozen=True)
class SettledOperation:
    """What a client in another process can read of one settled operation."""

    definition_id: str
    condition: OperationTerminalCondition
    published: BaseModel | None
    """The recorded error detail, the public result, or ``None`` when neither can be read."""


class ProjectionResolver(Protocol):
    """Resolve one settled projection, as the frontend result service does."""

    def __call__[ProjectionT: BaseModel](
        self, request: OperationResultProjectionRequestV1, projection_type: type[ProjectionT], /
    ) -> Awaitable[object]:
        """Return the projection, or the refusal that withholds it."""
        ...


async def read_published(
    resolve: ProjectionResolver,
    registry: OperationRegistry,
    *,
    definition_id: str,
    operation_id: str,
    condition: OperationTerminalCondition,
    revision: int,
    result_type: type[BaseModel],
) -> SettledOperation:
    """Read the detail of a stopped operation or the public result of a successful one."""
    contract = registry.lookup_public_contract(definition_id)
    succeeded = condition is OperationTerminalCondition.SUCCEEDED
    schema = contract.result_schema if succeeded else operation_error_detail_schema()
    assert schema is not None
    resolved = await resolve(
        OperationResultProjectionRequestV1(
            operation_id=operation_id,
            terminal_revision=revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=schema,
        ),
        result_type if succeeded else OperationErrorDetailV1,
    )
    published = resolved.projection if isinstance(resolved, OperationResultProjectionSuccessV1) else None
    return SettledOperation(definition_id=definition_id, condition=condition, published=published)


def published_verdicts(published: BaseModel) -> tuple[PreconditionVerdict, ...]:
    """Return every verdict a published detail or result carries, wherever the result holds it."""
    if isinstance(published, OperationErrorDetailV1):
        verdict = published.precondition_verdict()
        return () if verdict is None else (verdict,)
    found: list[PreconditionVerdict] = []

    def walk(value: object) -> None:
        if isinstance(value, PreconditionVerdictSnapshot):
            found.append(value.to_verdict())
        elif isinstance(value, BaseModel):
            for name in type(value).model_fields:
                walk(getattr(value, name))
        elif isinstance(value, tuple | list):
            for item in value:
                walk(item)

    walk(published)
    return tuple(found)


@dataclass(frozen=True)
class OperationRuntime:
    """One enrolled profile's supervised operations and the runtime they read with."""

    driver: conformance._ExecutionDriver
    registry: OperationRegistry
    profile_id: UUID
    tmp_path: Path
    posts: list[str]

    def settle(self, definition_id: str, payload: BaseModel, result_type: type[BaseModel]) -> SettledOperation:
        """Submit, start and settle ``payload``, then read what another process can read of it."""

        subject = expected_operation_subject(
            self.registry.lookup(definition_id).subject_reference, profile_id=self.profile_id, payload=payload
        )
        assert subject is not None, definition_id

        async def run() -> SettledOperation:
            submitted, _observed = await self.driver.run(
                definition_id=definition_id,
                subject_ref=subject,
                payload=payload,
            )
            observed = (await self.driver.observe(submitted.receipt.operation_id)).projection
            assert observed.terminal_condition is not None, observed
            return await read_published(
                self.driver.services.result.resolve,
                self.registry,
                definition_id=definition_id,
                operation_id=observed.operation_id,
                condition=observed.terminal_condition,
                revision=observed.revision,
                result_type=result_type,
            )

        return asyncio.run(run())


@contextmanager
def runtime_holding_nothing(posts: list[str]) -> Generator[None]:
    """Serve a real local AI runtime whose inventory is empty and that records every request it is sent."""

    class _EmptyRuntime(SilentLoopbackHandler):
        @override
        def do_GET(self) -> None:
            write_json_response(self, {"models": []}, status=HTTPStatus.OK)

        @override
        def do_POST(self) -> None:
            posts.append(self.path)
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)

    with (
        serving_loopback(_EmptyRuntime, path="/api/chat") as chat_url,
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_ollama_vision_model=_VISION_MODEL,
            cadrumo_llm_ollama_text_model=_TEXT_MODEL,
            cadrumo_llm_ollama_mapping_model=_OPERATOR_MAPPING_MODEL,
            # The documented setting for a host whose headroom cannot be
            # measured, so the reader is the only cause a lane can stop for.
            cadrumo_llm_contention_check_override=True,
        ),
    ):
        yield


@contextmanager
def operation_runtime(tmp_path: Path) -> Generator[OperationRuntime]:
    """Enrol a profile under the production registry, with the readers its adapter composition binds."""
    posts: list[str] = []
    with (
        runtime_holding_nothing(posts),
        bind_column_role_mapping_resolver(resolve_column_roles),
        bind_statement_reader_factory(LocalStatementReader),
        conformance.conformance_operation_runtime(
            tmp_path / "runtime", cleanup=conformance.OperationRuntimeCloseWitness()
        ) as (driver, registry, profile_id),
    ):
        yield OperationRuntime(driver=driver, registry=registry, profile_id=profile_id, tmp_path=tmp_path, posts=posts)


def _stored_image(runtime: OperationRuntime) -> tuple[str, str]:
    data = png_image()
    store = AttachmentStore(bucket_id=str(runtime.profile_id))
    attachment_id = store.put_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    store.write_manifest(
        Attachment(
            attachment_id=attachment_id,
            kind=AttachmentKind.RECEIPT_IMAGE,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="consumer-gating-evidence",
            sha256=digest,
            mime_type="image/png",
            bytes_size=len(data),
            captured_at=datetime(2026, 10, 24, 9, 0, tzinfo=UTC),
            bucket_id=str(runtime.profile_id),
            captured_by="operator",
            source_command="aeat app ledger attach",
        )
    )
    return attachment_id, digest


def _stored_transaction_id(runtime: OperationRuntime) -> str:
    """Import one readable statement through the registered import and return the movement it stored."""
    statement = runtime.tmp_path / "readable-statement.csv"
    statement.write_text(_READABLE_STATEMENT, encoding="utf-8")
    imported = runtime.settle(
        LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        LedgerImportRequest(profile_id=runtime.profile_id, files=(statement,), provider=LedgerProviderID.AUTO),
        LedgerImportResultProjection,
    )
    assert isinstance(imported.published, LedgerImportResultProjection), imported
    (reference,) = imported.published.imported_transaction_refs
    return reference.transaction_id


def settle_ledger_import(runtime: OperationRuntime) -> SettledOperation:
    export = runtime.tmp_path / "expenses-export.csv"
    export.write_bytes(_EXPORT_ONLY_THE_MAPPER_READS.read_bytes())
    return runtime.settle(
        LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        LedgerImportRequest(profile_id=runtime.profile_id, files=(export,), provider=LedgerProviderID.AUTO),
        LedgerImportResultProjection,
    )


def settle_ledger_import_pdf(runtime: OperationRuntime) -> SettledOperation:
    return runtime.settle(
        LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        LedgerImportRequest(
            profile_id=runtime.profile_id,
            files=(FIXTURES_DIR / "financial" / "n26" / "n26-savings-2025-01.pdf",),
            provider=LedgerProviderID.PDF,
        ),
        LedgerImportResultProjection,
    )


def settle_invoice_import(runtime: OperationRuntime) -> SettledOperation:
    book = runtime.tmp_path / "libro.csv"
    book.write_bytes(_BOOK_ONLY_THE_MAPPER_READS.read_bytes())
    return runtime.settle(
        INVOICE_IMPORT_OPERATION_DEFINITION_ID,
        InvoiceImportRequest(profile_id=runtime.profile_id, kind=InvoiceKind.ISSUED, source_path=str(book)),
        BaseModel,
    )


def settle_evidence_extract(runtime: OperationRuntime) -> SettledOperation:
    attachment_id, _digest = _stored_image(runtime)
    return runtime.settle(
        LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
        LedgerEvidenceExtractRequest(profile_id=runtime.profile_id, attachment_id=attachment_id),
        BaseModel,
    )


def settle_evidence_confirm(runtime: OperationRuntime) -> SettledOperation:
    attachment_id, digest = _stored_image(runtime)
    return runtime.settle(
        LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
        LedgerEvidenceConfirmRequest(
            profile_id=runtime.profile_id,
            attachment_id=attachment_id,
            expected_source_sha256=digest,
            expected_draft_review_sha256="e" * 64,
            kind=InvoiceKind.RECEIVED,
        ),
        BaseModel,
    )


def settle_evidence_batch(runtime: OperationRuntime) -> SettledOperation:
    folder = runtime.tmp_path / "documents"
    folder.mkdir()
    document = folder / "unlabelled.pdf"
    document.write_bytes(text_pdf_bytes(_NO_LABELS))
    return runtime.settle(
        LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
        LedgerEvidenceBatchRequest(
            profile_id=runtime.profile_id,
            sources=(str(document),),
            source_directory=str(folder),
            direction=InvoiceKind.RECEIVED,
        ),
        LedgerEvidenceBatchProjection,
    )


def settle_classify_review(runtime: OperationRuntime) -> SettledOperation:
    transaction_id = _stored_transaction_id(runtime)
    return runtime.settle(
        LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
        LedgerLlmReviewRequest(
            profile_id=runtime.profile_id,
            transaction_id=transaction_id[:12],
            mode="classification",
            origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
        ),
        BaseModel,
    )


def settle_split_review(runtime: OperationRuntime) -> SettledOperation:
    """A split is proposed only from image evidence, so the movement first gets an image through the registered attach."""
    transaction_id = _stored_transaction_id(runtime)
    attachment_id, _digest = _stored_image(runtime)
    attached = runtime.settle(
        LEDGER_ATTACH_OPERATION_DEFINITION_ID,
        LedgerAttachRequest(
            profile_id=runtime.profile_id, transaction_id=transaction_id[:12], attachment_ids=(attachment_id,)
        ),
        LedgerAttachmentOperationResult,
    )
    assert attached.condition is OperationTerminalCondition.SUCCEEDED, attached
    return runtime.settle(
        LEDGER_SPLIT_REVIEW_DEFINITION_ID,
        LedgerLlmReviewRequest(
            profile_id=runtime.profile_id,
            transaction_id=transaction_id[:12],
            mode="split",
            origin=LlmReviewInvocationOrigin.SPLIT_LLM,
            read_evidence=True,
        ),
        BaseModel,
    )


type OperationSettler = Callable[[OperationRuntime], SettledOperation]

__all__ = [
    "OperationRuntime",
    "OperationSettler",
    "ProjectionResolver",
    "SettledOperation",
    "operation_runtime",
    "published_verdicts",
    "read_published",
    "runtime_holding_nothing",
    "settle_classify_review",
    "settle_evidence_batch",
    "settle_evidence_confirm",
    "settle_evidence_extract",
    "settle_invoice_import",
    "settle_ledger_import",
    "settle_ledger_import_pdf",
    "settle_split_review",
]
