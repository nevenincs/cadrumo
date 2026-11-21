"""The registered ``ledger.evidence.probe`` read says what a picked file is, storing nothing.

The real executor, supervisor, journal and encrypted profile storage run with the
production document-shape probe. A file carrying a structured single invoice is
offered as a purchase invoice, naming the shape it rests on; a plain PDF or an
image is offered no kind; a file the add would refuse is refused with no effect.
No probe writes evidence, attachment bytes or a bucket event.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.inbound.einvoice.shape import probe_document_shape
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.purchase_invoice_evidence import (
    LedgerEvidenceAttachmentIngestor,
    LedgerEvidenceRepositoryAdapter,
)
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger import tests as ledger_application_tests
from cadrumo.application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from cadrumo.application.ledger.evidence_ports import LedgerEvidencePorts
from cadrumo.application.ledger.evidence_probe_operation import (
    LEDGER_EVIDENCE_PROBE_OPERATION_DEFINITION_ID,
    LedgerEvidenceProbeExecutionResult,
    LedgerEvidenceProbeProjection,
    LedgerEvidenceProbeRequest,
    build_ledger_evidence_probe_definition,
    build_ledger_evidence_probe_registration,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.document_shape import DocumentShape
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.tests.pdf_fixtures import text_pdf_bytes

from .supervision_support import run_to_settlement
from .supervisor_test_support import operation_repositories, operation_supervisor

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PROFILE = UUID("a0347100-3a01-4b0a-aeee-347102030407")
_CORPUS = Path(ledger_application_tests.__file__).parent / "_evidence_corpus"

# Each file, the shape the production probe recognises in it, and whether that shape supports a kind.
_FILES: tuple[tuple[str, bytes | str, DocumentShape | None, bool], ...] = (
    ("invoice.xml", "en16931_cii_export_third_country_invoice.xml", DocumentShape.XML_CII, True),
    ("invoice-ubl.xml", "en16931_ubl_two_rate_invoice.xml", DocumentShape.XML_UBL, True),
    ("factura.xml", "facturae_32_recargo_invoice.xml", DocumentShape.XML_FACTURAE, True),
    ("invoice-zugferd.pdf", "zugferd_en16931_invoice.pdf", DocumentShape.PDF_EMBEDDED_XML, True),
    ("receipt.pdf", text_pdf_bytes(("synthetic purchase receipt",)), DocumentShape.PDF_TEXT_LAYER, False),
    ("photo.jpg", "com_2026_0005_camera_photo.jpg", DocumentShape.IMAGE, False),
    ("broken.pdf", "adversarial_malformed.pdf", None, False),
)


@pytest.mark.parametrize(("name", "source", "shape", "proposed"), _FILES, ids=[item[0] for item in _FILES])
def test_registered_probe_proposes_a_purchase_invoice_only_for_a_structured_invoice_and_stores_nothing(
    tmp_path: Path, name: str, source: bytes | str, shape: DocumentShape | None, proposed: bool
) -> None:
    source_directory = tmp_path / "documents"
    source_directory.mkdir()
    (source_directory / name).write_bytes(source if isinstance(source, bytes) else (_CORPUS / source).read_bytes())

    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=str(_PROFILE)) as profile:
        objects = profile.repository

        def ports_factory(*, bucket_id: str) -> LedgerEvidencePorts:
            assert bucket_id == str(_PROFILE)
            return LedgerEvidencePorts(
                evidence_repository=LedgerEvidenceRepositoryAdapter(objects=objects),
                attachment_ingestor=LedgerEvidenceAttachmentIngestor(store=AttachmentStore(objects=objects)),
                bucket_event_repository=BucketEventHistoryRepository(objects=objects),
                document_shape_probe=probe_document_shape,
            )

        definition = build_ledger_evidence_probe_definition(ports_factory)
        registration = build_ledger_evidence_probe_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        journal, leases, operands = operation_repositories(
            storage_root=tmp_path / "durable-state", profile_objects=objects
        )
        supervisor = operation_supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            execution_timeout=timedelta(minutes=1),
        )
        events_before = set(BucketEventHistoryRepository(objects=objects).load().events)

        async def settle() -> LedgerEvidenceProbeProjection | None:
            operation_id = await supervisor.submit(
                OperationRequest[BaseModel](
                    definition_id=LEDGER_EVIDENCE_PROBE_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                    payload=LedgerEvidenceProbeRequest(
                        profile_id=_PROFILE,
                        source_path=name,
                        source_directory=str(source_directory),
                    ),
                ),
                operation_id="4" * 64,
            )
            await run_to_settlement(supervisor, operation_id)
            terminal = await supervisor.inspect(operation_id)
            receipt = terminal.terminal_receipt
            assert receipt is not None
            assert receipt.effect is OperationEffect.NONE
            if shape is None:
                assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
                assert receipt.result_ref is None
                assert receipt.refusal_ref == get_registered_error_code(PurchaseInvoiceEvidenceInputError).code
                return None
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert receipt.result_ref is not None
            stored = await operands.resolve(receipt.result_ref, LedgerEvidenceProbeExecutionResult)
            projector = registration.result_projector
            assert projector is not None
            released = projector(stored, receipt)
            assert isinstance(released, LedgerEvidenceProbeProjection)
            return released

        released = asyncio.run(settle())

        if shape is not None:
            assert released is not None
            assert released.profile_id == _PROFILE
            assert released.document_shape is shape
            if proposed:
                assert released.kind_proposal is not None
                assert released.kind_proposal.kind == "purchase_invoice"
                assert released.kind_proposal.basis is shape
            else:
                assert released.kind_proposal is None
        assert LedgerEvidenceRepositoryAdapter(objects=objects).load(bucket_id=str(_PROFILE)) == ()
        assert tuple(AttachmentStore(objects=objects).iter_manifests()) == ()
        assert set(BucketEventHistoryRepository(objects=objects).load().events) == events_before


def test_probe_result_refuses_a_proposal_its_shape_does_not_support() -> None:
    from pydantic import ValidationError

    from cadrumo.application.ledger.evidence_kind_proposal import EvidenceKindProposalV1

    with pytest.raises(ValidationError):
        LedgerEvidenceProbeProjection(
            profile_id=_PROFILE,
            document_shape=DocumentShape.PDF_SCAN,
            kind_proposal=EvidenceKindProposalV1(basis=DocumentShape.XML_UBL),
        )
    with pytest.raises(ValidationError):
        LedgerEvidenceProbeProjection(profile_id=_PROFILE, document_shape=DocumentShape.XML_CII, kind_proposal=None)
    with pytest.raises(ValidationError):
        EvidenceKindProposalV1(basis=DocumentShape.XML_AEAT_SII)
