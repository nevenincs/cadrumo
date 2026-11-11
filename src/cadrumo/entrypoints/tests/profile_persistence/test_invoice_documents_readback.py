"""An invoice read back from the catalogue carries the documents kept for it, named by file name alone."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Generator, Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
from ....adapters.persistence.profile.catalogue_reads import InvoiceCatalogueReadAdapter
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.invoices.catalogue_creation import build_catalogue_invoice, create_catalogue_invoice
from ....application.invoices.catalogue_read_operation import (
    INVOICE_LIST_OPERATION_DEFINITION_ID,
    INVOICE_VIEW_OPERATION_DEFINITION_ID,
    InvoiceCatalogueReadExecutor,
    InvoiceListRequest,
    InvoiceListResult,
    InvoiceViewRefusal,
    InvoiceViewRequest,
    InvoiceViewResult,
    InvoiceViewSuccess,
)
from ....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot, InvoiceDocumentSnapshot
from ....application.invoices.document_attach_operation import (
    INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID,
    InvoiceDocumentAttachExecutionResult,
    InvoiceDocumentAttachExecutor,
    InvoiceDocumentAttachPorts,
    InvoiceDocumentAttachRequest,
)
from ....application.invoices.inspection_read_ports import InvoiceInspectionReadPorts, InvoiceInspectionReadPortsFactory
from ....application.operations.models import OperationRequest
from ....application.operations.refusal_evidence import OperationRefusalEvidence
from ....application.tests.operation_host_fakes import (
    IrreversibleSectionGrant,
    RecordingEvents,
    RecordingOperands,
    executor_context,
)
from ....core.operations import profile_operation_subject
from ....domain.attachments.models import Attachment
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.iva.schema import InvoiceKind
from ...adapter_composition_work_ports import build_ledger_evidence_ports
from ...invoice_inspection_composition import build_invoice_inspection_read_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET = "d0c5d0c5-0000-4000-8000-0000000000d0"
_FOLDER = "carpeta-privada-proveedor"
_FILE_NAME = "factura-proveedor-0042.pdf"
_PDF = b"%PDF-1.4\n% synthetic factura F-0042\n%%EOF\n"


@pytest.fixture
def objects(tmp_path: Path) -> Generator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        yield profile.repository


def _seed_invoice(invoice_number: str, *, operation: PinnedAuthorityOperation) -> str:
    catalogue_ports = build_catalogue_creation_ports(bucket_id=_BUCKET)
    invoice = build_catalogue_invoice(
        bucket_id=_BUCKET,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Proveedor Ejemplo SL",
        counterparty_tax_id="B00015016",
        counterparty_country="ES",
        invoice_number=invoice_number,
        issued_at=date(filing_year_envelope().horizon, 2, 15),
        taxable_base=Decimal("200.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
        rate_provider=catalogue_ports.rate_provider,
        operation=operation,
    )
    return create_catalogue_invoice(invoice=invoice, ports=catalogue_ports).invoice.invoice_id


def _attach(
    objects: SecureObjectRepository,
    tmp_path: Path,
    *,
    invoice_id: str,
    operation: PinnedAuthorityOperation,
    data: bytes = _PDF,
    name: str = _FILE_NAME,
) -> str:
    folder = tmp_path / _FOLDER
    folder.mkdir(exist_ok=True)
    (folder / name).write_bytes(data)
    operands = RecordingOperands("operand")
    ports = InvoiceDocumentAttachPorts(
        evidence=build_ledger_evidence_ports(bucket_id=_BUCKET),
        invoice_reader=InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=objects),
        attachment_store=AttachmentStore(objects=objects),
    )
    request = OperationRequest[InvoiceDocumentAttachRequest](
        definition_id=INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(_BUCKET),
        payload=InvoiceDocumentAttachRequest(
            profile_id=UUID(_BUCKET),
            invoice_id=invoice_id,
            source_path=name,
            source_directory=str(folder),
        ),
    )
    context = executor_context(
        INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID,
        profile_id=_BUCKET,
        operation=operation,
        cancellation=IrreversibleSectionGrant(),
        events=RecordingEvents(),
        operands=operands,
    )
    asyncio.run(InvoiceDocumentAttachExecutor(lambda **_bucket: ports).execute(request, context))
    (stored,) = operands.stored
    assert isinstance(stored, InvoiceDocumentAttachExecutionResult)
    return stored.result.attachment_id


def _read(
    payload: InvoiceListRequest | InvoiceViewRequest,
    *,
    operation: PinnedAuthorityOperation,
    factory: InvoiceInspectionReadPortsFactory = build_invoice_inspection_read_ports,
    events: RecordingEvents | None = None,
) -> tuple[InvoiceListResult | InvoiceViewResult, str | OperationRefusalEvidence]:
    definition_id = (
        INVOICE_LIST_OPERATION_DEFINITION_ID
        if isinstance(payload, InvoiceListRequest)
        else INVOICE_VIEW_OPERATION_DEFINITION_ID
    )
    operands = RecordingOperands("0" * 64)
    request = OperationRequest[InvoiceListRequest | InvoiceViewRequest](
        definition_id=definition_id, subject_ref=profile_operation_subject(_BUCKET), payload=payload
    )
    context = executor_context(
        definition_id,
        profile_id=_BUCKET,
        operation=operation,
        cancellation=IrreversibleSectionGrant(),
        events=events or RecordingEvents(),
        operands=operands,
    )
    outcome = asyncio.run(InvoiceCatalogueReadExecutor(factory, definition_id).execute(request, context))
    (stored,) = operands.stored
    assert isinstance(stored, InvoiceListResult | InvoiceViewResult)
    return stored, outcome


def _listed(operation: PinnedAuthorityOperation) -> dict[str, CatalogueInvoiceSnapshot]:
    result, _ = _read(InvoiceListRequest(profile_id=UUID(_BUCKET)), operation=operation)
    assert isinstance(result, InvoiceListResult)
    return {invoice.invoice_id: invoice for invoice in result.invoices}


def _viewed(invoice_id: str, operation: PinnedAuthorityOperation) -> CatalogueInvoiceSnapshot:
    result, _ = _read(InvoiceViewRequest(profile_id=UUID(_BUCKET), invoice_id=invoice_id), operation=operation)
    assert isinstance(result, InvoiceViewResult)
    assert isinstance(result.outcome, InvoiceViewSuccess)
    return result.outcome.invoice


def test_list_and_view_serve_the_attached_document_by_its_file_name_alone(
    objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    documented = _seed_invoice("F-0042", operation=operation)
    undocumented = _seed_invoice("F-0043", operation=operation)
    attachment_id = _attach(objects, tmp_path, invoice_id=documented, operation=operation)
    expected = (InvoiceDocumentSnapshot(attachment_id=attachment_id, name=_FILE_NAME, media_type="application/pdf"),)

    listed = _listed(operation)
    viewed = _viewed(documented, operation)

    assert listed[documented].documents == expected
    assert listed[undocumented].documents == ()
    assert viewed.documents == expected
    assert _viewed(undocumented, operation).documents == ()
    assert _FOLDER not in viewed.model_dump_json()
    assert all(_FOLDER not in invoice.model_dump_json() for invoice in listed.values())


def test_a_view_shows_no_document_before_the_attach_and_the_document_after_it(
    objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    invoice_id = _seed_invoice("F-0042", operation=operation)
    assert _viewed(invoice_id, operation).documents == ()

    first = _attach(objects, tmp_path, invoice_id=invoice_id, operation=operation)
    second = _attach(
        objects, tmp_path, invoice_id=invoice_id, operation=operation, data=_PDF + b"% copia\n", name="copia.pdf"
    )

    documents = _viewed(invoice_id, operation).documents
    assert tuple(document.attachment_id for document in documents) == tuple(sorted((first, second)))
    assert {document.name for document in documents} == {_FILE_NAME, "copia.pdf"}


class _CountingManifests:
    """The profile's real attachment store, counting how often its manifests are read."""

    def __init__(self, store: AttachmentStore) -> None:
        self.store = store
        self.reads = 0

    def iter_manifests(self) -> Iterator[Attachment]:
        self.reads += 1
        return self.store.iter_manifests()


def test_the_list_reads_the_document_manifests_once_for_every_invoice(
    objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    invoice_ids = [_seed_invoice(f"F-00{number}", operation=operation) for number in (42, 43, 44)]
    _attach(objects, tmp_path, invoice_id=invoice_ids[0], operation=operation)
    _attach(objects, tmp_path, invoice_id=invoice_ids[2], operation=operation, data=_PDF + b"%\n", name="otra.pdf")
    manifests = _CountingManifests(AttachmentStore(objects=objects, bucket_id=_BUCKET))

    def ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> InvoiceInspectionReadPorts:
        del operation
        return InvoiceInspectionReadPorts(
            bucket_id=bucket_id,
            invoices=InvoiceCatalogueReadAdapter(
                repository=InvoiceCatalogueRepository(bucket_id=bucket_id, objects=objects)
            ),
            documents=manifests,
        )

    result, _ = _read(InvoiceListRequest(profile_id=UUID(_BUCKET)), operation=operation, factory=ports)

    assert isinstance(result, InvoiceListResult)
    assert manifests.reads == 1
    assert [
        len(invoice.documents) for invoice in sorted(result.invoices, key=lambda row: invoice_ids.index(row.invoice_id))
    ] == [1, 0, 1]


def test_the_document_name_stays_out_of_events_logs_and_the_lookup_refusal(
    objects: SecureObjectRepository,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    invoice_id = _seed_invoice("F-0042", operation=operation)
    _attach(objects, tmp_path, invoice_id=invoice_id, operation=operation)
    events = RecordingEvents()

    with caplog.at_level(logging.DEBUG):
        _read(InvoiceListRequest(profile_id=UUID(_BUCKET)), operation=operation, events=events)
        _read(InvoiceViewRequest(profile_id=UUID(_BUCKET), invoice_id=invoice_id), operation=operation, events=events)
        refused, outcome = _read(
            InvoiceViewRequest(profile_id=UUID(_BUCKET), invoice_id="f" * 64), operation=operation, events=events
        )

    assert isinstance(outcome, OperationRefusalEvidence)
    assert isinstance(refused, InvoiceViewResult)
    assert isinstance(refused.outcome, InvoiceViewRefusal)
    assert _FILE_NAME not in refused.model_dump_json()
    assert all(_FILE_NAME not in phase for phase in events.phases)
    assert _FILE_NAME not in caplog.text
    assert _FOLDER not in caplog.text
