"""Attaching a document to a catalogue invoice: custody, the invoice link, and a refusal that writes nothing."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.invoices.catalogue_creation import build_catalogue_invoice, create_catalogue_invoice
from ....application.invoices.catalogue_selection import InvoiceLookupRefusedError
from ....application.invoices.document_attach_operation import (
    INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID,
    InvoiceDocumentAttachExecutionResult,
    InvoiceDocumentAttachExecutor,
    InvoiceDocumentAttachPorts,
    InvoiceDocumentAttachRequest,
)
from ....application.operations.models import OperationRequest
from ....application.tests.operation_host_fakes import (
    IrreversibleSectionGrant,
    RecordingEvents,
    RecordingOperands,
    executor_context,
)
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.iva.schema import InvoiceKind
from ...adapter_composition_work_ports import build_ledger_evidence_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET = "a77ac400-0000-4000-8000-0000000000a7"
_PDF = b"%PDF-1.4\n% synthetic factura F2026-0042\n%%EOF\n"


@pytest.fixture
def objects(tmp_path: Path) -> Generator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        yield profile.repository


def _seed_invoice(objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation) -> str:
    catalogue_ports = build_catalogue_creation_ports(bucket_id=_BUCKET)
    invoice = build_catalogue_invoice(
        bucket_id=_BUCKET,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Proveedor Ejemplo SL",
        counterparty_tax_id="B00015016",
        counterparty_country="ES",
        invoice_number="F2026-0042",
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
) -> tuple[RecordingEvents, RecordingOperands]:
    (tmp_path / "factura.pdf").write_bytes(_PDF)
    events = RecordingEvents()
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
            source_path="factura.pdf",
            source_directory=str(tmp_path),
        ),
    )
    context = executor_context(
        INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID,
        profile_id=_BUCKET,
        operation=operation,
        cancellation=IrreversibleSectionGrant(),
        events=events,
        operands=operands,
    )
    executor = InvoiceDocumentAttachExecutor(lambda **_bucket: ports)
    asyncio.run(executor.execute(request, context))
    return events, operands


def _result(operands: RecordingOperands) -> InvoiceDocumentAttachExecutionResult:
    (stored,) = operands.stored
    assert isinstance(stored, InvoiceDocumentAttachExecutionResult)
    return stored


def test_an_attached_document_is_kept_and_belongs_to_its_invoice(
    objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    invoice_id = _seed_invoice(objects, operation=operation)

    events, operands = _attach(objects, tmp_path, invoice_id=invoice_id, operation=operation)

    result = _result(operands).result
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert (result.invoice_id, result.already_linked) == (invoice_id, False)
    manifest = AttachmentStore(objects=objects).load_manifest(result.attachment_id)
    assert manifest.linked_invoice_ids == (invoice_id,)


def test_attaching_the_same_document_again_changes_nothing(
    objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    invoice_id = _seed_invoice(objects, operation=operation)
    _, first = _attach(objects, tmp_path, invoice_id=invoice_id, operation=operation)

    _, second = _attach(objects, tmp_path, invoice_id=invoice_id, operation=operation)

    assert _result(second).result.attachment_id == _result(first).result.attachment_id
    assert _result(second).result.already_linked is True
    manifests = tuple(AttachmentStore(objects=objects).iter_manifests())
    assert [manifest.linked_invoice_ids for manifest in manifests] == [(invoice_id,)]


def test_an_unknown_invoice_is_refused_before_any_document_is_kept(
    objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    _seed_invoice(objects, operation=operation)

    with pytest.raises(InvoiceLookupRefusedError):
        _attach(objects, tmp_path, invoice_id="f" * 64, operation=operation)

    assert tuple(AttachmentStore(objects=objects).iter_manifests()) == ()
