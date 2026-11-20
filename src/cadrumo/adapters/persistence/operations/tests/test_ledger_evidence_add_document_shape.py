"""The registered ``ledger.evidence.add`` operation refuses unreadable bytes as a refusal.

The real executor, supervisor, journal and encrypted profile storage run with the
production document-shape probe. A document no reader can read must settle as a
refusal with no effect: the ``UNKNOWN`` effect, which tells an operator a write
may have happened, is reserved for work that reached custody.
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
from cadrumo.application.ledger.evidence_add_operation import (
    LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
    LedgerEvidenceAddRequest,
    build_ledger_evidence_add_definition,
    build_ledger_evidence_add_registration,
)
from cadrumo.application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from cadrumo.application.ledger.evidence_ports import LedgerEvidencePorts
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.tests.pdf_fixtures import text_pdf_bytes

from .supervision_support import run_to_settlement
from .supervisor_test_support import operation_repositories, operation_supervisor

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PROFILE = UUID("a0347100-3a01-4b0a-aeee-347102030406")
_CORPUS = Path(ledger_application_tests.__file__).parent / "_evidence_corpus"


@pytest.mark.parametrize("readable", [False, True])
def test_registered_add_refuses_unreadable_bytes_before_any_effect_and_stores_readable_ones(
    tmp_path: Path, readable: bool
) -> None:
    source_directory = tmp_path / "invoices"
    source_directory.mkdir()
    source = source_directory / "invoice.pdf"
    source.write_bytes(
        text_pdf_bytes(("synthetic purchase invoice",))
        if readable
        else (_CORPUS / "adversarial_malformed.pdf").read_bytes()
    )

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

        definition = build_ledger_evidence_add_definition(ports_factory)
        registration = build_ledger_evidence_add_registration(definition)
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

        async def settle() -> None:
            operation_id = await supervisor.submit(
                OperationRequest[BaseModel](
                    definition_id=LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                    payload=LedgerEvidenceAddRequest(
                        profile_id=_PROFILE,
                        source_path="invoice.pdf",
                        source_directory=str(source_directory),
                    ),
                ),
                operation_id="4" * 64,
            )
            await run_to_settlement(supervisor, operation_id)
            terminal = await supervisor.inspect(operation_id)
            receipt = terminal.terminal_receipt
            assert receipt is not None
            if readable:
                assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert receipt.effect is OperationEffect.UPDATED
                assert receipt.result_ref is not None
            else:
                assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
                assert receipt.effect is OperationEffect.NONE
                assert receipt.result_ref is None
                assert receipt.refusal_ref == get_registered_error_code(PurchaseInvoiceEvidenceInputError).code

        asyncio.run(settle())

        evidence = LedgerEvidenceRepositoryAdapter(objects=objects).load(bucket_id=str(_PROFILE))
        manifests = tuple(AttachmentStore(objects=objects).iter_manifests())
        events_after = set(BucketEventHistoryRepository(objects=objects).load().events)
        if readable:
            assert len(evidence) == 1 and len(manifests) == 1 and len(events_after - events_before) == 1
        else:
            assert evidence == () and manifests == () and events_after == events_before
