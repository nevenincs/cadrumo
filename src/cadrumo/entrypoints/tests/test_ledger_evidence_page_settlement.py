"""The registered page read draws a stored document's page, or refuses it by a typed code.

Each case runs the production definition through the real registry,
supervisor, journal and encrypted operand store, with the production
composition of evidence catalogue, attachment custody and renderer, against
documents stored in a real encrypted profile. A success is read back as a
frontend reads it; a refusal is read from the operation's receipt.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID

import pytest
from PIL import Image
from pydantic import BaseModel

from ...adapters.inbound.pdf.page_image import PageImageRenderer
from ...adapters.persistence.operations.tests.supervision_support import run_to_settlement
from ...adapters.persistence.operations.tests.supervisor_test_support import operation_repositories
from ...adapters.persistence.storage.attachment import AttachmentStore
from ...adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...application.ledger.evidence import PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_page_contracts import (
    EVIDENCE_PAGE_IMAGE_URL_PREFIX,
    LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID,
    EvidencePageMediaType,
    EvidencePageRenderer,
    LedgerEvidencePageProjection,
    LedgerEvidencePageRequest,
)
from ...application.ledger.evidence_page_errors import (
    LedgerEvidencePageDigestMismatchError,
    LedgerEvidencePageNotFoundError,
    LedgerEvidencePageOutOfRangeError,
    LedgerEvidencePageTooLargeError,
    LedgerEvidencePageUnsupportedMediaError,
)
from ...application.ledger.evidence_page_operation import (
    build_ledger_evidence_page_definition,
    build_ledger_evidence_page_registration,
)
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationRequest, OperationTerminalReceipt
from ...application.operations.projection_services import OperationResultProjectionService
from ...application.operations.registry import OperationRegistry
from ...application.operations.supervisor import OperationSupervisor
from ...core.errors.error_codes import get_registered_error_code
from ...core.errors.hierarchy import CadrumoError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.attachments.enums import AttachmentKind, AttachmentSource
from ...domain.attachments.models import Attachment
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...tests.pdf_fixtures import multi_page_text_pdf_bytes
from ..adapter_composition_work_ports import build_ledger_evidence_ports
from ..evidence_page_operation_composition import build_ledger_evidence_page_operation_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE = UUID("3c1d5e7f-9a2b-4c4d-8e6f-1a2b3c4d5e6f")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True, slots=True)
class _Settled:
    receipt: OperationTerminalReceipt
    page: LedgerEvidencePageProjection | None


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=str(_PROFILE)) as runtime_profile:
        yield runtime_profile


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _photo(size: tuple[int, int]) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (200, 120, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _evidence(tmp_path: Path, name: str, data: bytes) -> PurchaseInvoiceEvidence:
    """Add a real evidence record from a file the person picked in a folder of their own."""
    folder = tmp_path / "alba-private-folder"
    folder.mkdir(exist_ok=True)
    source = folder / name
    source.write_bytes(data)
    bucket_id = str(_PROFILE)
    return (
        PurchaseInvoiceEvidenceService(ports=build_ledger_evidence_ports(bucket_id=bucket_id))
        .add(bucket_id=bucket_id, source_path=source)
        .record
    )


def _attachment(profile: TestRuntimeProfile, data: bytes, *, mime_type: str, source_reference: str) -> str:
    store = AttachmentStore(objects=profile.repository)
    attachment_id = store.put_bytes(data)
    store.write_manifest(
        Attachment(
            attachment_id=attachment_id,
            kind=AttachmentKind.RECEIPT_IMAGE,
            source=AttachmentSource.LOCAL_FILE,
            source_reference=source_reference,
            sha256=hashlib.sha256(data).hexdigest(),
            mime_type=mime_type,
            bytes_size=len(data),
            captured_at=datetime(2026, 10, 24, 9, 0, tzinfo=UTC),
            bucket_id=str(_PROFILE),
            captured_by="operator",
            source_command="aeat app ledger attach",
        )
    )
    return attachment_id


def _settle(
    tmp_path: Path,
    profile: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
    request: LedgerEvidencePageRequest,
    *,
    renderer: EvidencePageRenderer | None = None,
) -> _Settled:
    definition = build_ledger_evidence_page_definition(build_ledger_evidence_page_operation_ports(renderer=renderer))
    registration = build_ledger_evidence_page_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    journal, leases, operands = operation_repositories(
        storage_root=tmp_path / "durable-state", profile_objects=profile.repository
    )
    supervisor = OperationSupervisor(
        authority_operation=operation,
        registry=registry,
        journal=journal,
        event_stream=journal,
        leases=leases,
        operands=operands,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=5),
        execution_timeout=timedelta(minutes=2),
        cleanup_timeout=timedelta(minutes=1),
        response_token_factory=lambda: "3" * 64,
    )

    async def settle() -> _Settled:
        operation_id = await supervisor.submit(
            OperationRequest[BaseModel](
                definition_id=LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_PROFILE)),
                payload=request,
            ),
            operation_id="4" * 64,
        )
        terminal = await run_to_settlement(supervisor, operation_id)
        receipt = terminal.terminal_receipt
        assert receipt is not None
        if receipt.condition is not OperationTerminalCondition.SUCCEEDED:
            return _Settled(receipt=receipt, page=None)
        schema = registration.contract.result_schema
        assert schema is not None
        resolved = await OperationResultProjectionService(reader=journal, registry=registry, operands=operands).resolve(
            OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=terminal.revision,
                definition_contract_digest=registration.contract.definition_contract_digest,
                result_schema=schema,
            ),
            LedgerEvidencePageProjection,
        )
        assert isinstance(resolved, OperationResultProjectionSuccessV1), resolved
        page = resolved.projection
        assert isinstance(page, LedgerEvidencePageProjection)
        return _Settled(receipt=receipt, page=page)

    return asyncio.run(settle())


def _image(page: LedgerEvidencePageProjection) -> Image.Image:
    assert page.image_data_url.startswith(EVIDENCE_PAGE_IMAGE_URL_PREFIX)
    png = base64.b64decode(page.image_data_url.removeprefix(EVIDENCE_PAGE_IMAGE_URL_PREFIX), validate=True)
    assert png.startswith(_PNG_SIGNATURE)
    image = Image.open(BytesIO(png), formats=("PNG",))
    image.load()
    return image


def _assert_refused(settled: _Settled, error: type[CadrumoError]) -> None:
    assert settled.receipt.condition is OperationTerminalCondition.REFUSED
    assert settled.receipt.effect is OperationEffect.NONE
    assert settled.receipt.refusal_ref == get_registered_error_code(error).code


def test_a_pdf_evidence_page_is_drawn_with_its_file_name_and_no_folder(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    pdf = multi_page_text_pdf_bytes(("Factura 1 de 2",), ("Factura 2 de 2",))
    record = _evidence(tmp_path, "factura-luz.pdf", pdf)

    settled = _settle(
        tmp_path,
        profile,
        operation,
        LedgerEvidencePageRequest(profile_id=_PROFILE, evidence_id=record.evidence_id, page=2, max_width=640),
    )

    assert settled.receipt.condition is OperationTerminalCondition.SUCCEEDED
    assert settled.receipt.effect is OperationEffect.NONE
    page = settled.page
    assert page is not None
    assert (page.evidence_id, page.attachment_id) == (record.evidence_id, record.attachment_id)
    assert page.media_type is EvidencePageMediaType.PDF
    assert (page.page, page.page_count, page.width) == (2, 2, 640)
    assert page.source_sha256 == hashlib.sha256(pdf).hexdigest()
    assert page.file_name == "factura-luz.pdf"
    assert _image(page).size == (page.width, page.height)
    assert "alba-private-folder" not in page.model_dump_json()


def test_a_jpeg_attachment_is_scaled_down_to_the_asked_width(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    photo = _photo((2400, 1200))
    attachment_id = _attachment(
        profile, photo, mime_type="image/jpeg", source_reference=str(tmp_path / "alba-private-folder" / "ticket.jpg")
    )

    settled = _settle(
        tmp_path,
        profile,
        operation,
        LedgerEvidencePageRequest(profile_id=_PROFILE, attachment_id=attachment_id, max_width=800),
    )

    page = settled.page
    assert page is not None
    assert page.media_type is EvidencePageMediaType.JPEG
    assert (page.page, page.page_count, page.width, page.height) == (1, 1, 800, 400)
    assert page.source_sha256 == attachment_id
    assert page.file_name == "ticket.jpg"
    assert _image(page).size == (800, 400)
    assert "alba-private-folder" not in page.model_dump_json()


def test_a_record_whose_digest_its_stored_bytes_do_not_match_is_refused(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    record = _evidence(tmp_path, "factura.pdf", multi_page_text_pdf_bytes(("Factura",)))
    ports = build_ledger_evidence_ports(bucket_id=str(_PROFILE))
    ports.evidence_repository.save(
        bucket_id=str(_PROFILE), records=(record.model_copy(update={"source_sha256": "0" * 64}),)
    )

    settled = _settle(
        tmp_path,
        profile,
        operation,
        LedgerEvidencePageRequest(profile_id=_PROFILE, evidence_id=record.evidence_id),
    )

    _assert_refused(settled, LedgerEvidencePageDigestMismatchError)


def test_a_document_of_a_type_the_read_cannot_draw_is_refused(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    attachment_id = _attachment(
        profile, b"<Invoice>synthetic</Invoice>", mime_type="application/xml", source_reference="invoice.xml"
    )

    settled = _settle(
        tmp_path, profile, operation, LedgerEvidencePageRequest(profile_id=_PROFILE, attachment_id=attachment_id)
    )

    _assert_refused(settled, LedgerEvidencePageUnsupportedMediaError)


def test_a_document_above_the_byte_bound_is_refused(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    photo = _photo((600, 400))
    attachment_id = _attachment(profile, photo, mime_type="image/jpeg", source_reference="ticket.jpg")

    settled = _settle(
        tmp_path,
        profile,
        operation,
        LedgerEvidencePageRequest(profile_id=_PROFILE, attachment_id=attachment_id),
        renderer=PageImageRenderer(max_source_bytes=len(photo) - 1),
    )

    _assert_refused(settled, LedgerEvidencePageTooLargeError)


def test_a_page_beyond_the_document_is_refused(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    record = _evidence(tmp_path, "factura.pdf", multi_page_text_pdf_bytes(("Factura",), ("Anexo",)))

    settled = _settle(
        tmp_path,
        profile,
        operation,
        LedgerEvidencePageRequest(profile_id=_PROFILE, evidence_id=record.evidence_id, page=3),
    )

    _assert_refused(settled, LedgerEvidencePageOutOfRangeError)


def test_an_evidence_record_the_profile_does_not_hold_is_refused(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    settled = _settle(
        tmp_path, profile, operation, LedgerEvidencePageRequest(profile_id=_PROFILE, evidence_id="ev-missing")
    )

    _assert_refused(settled, LedgerEvidencePageNotFoundError)


@pytest.mark.parametrize(
    "fields",
    [{}, {"evidence_id": "ev-1", "attachment_id": "a" * 64}],
    ids=["neither", "both"],
)
def test_a_request_names_exactly_one_document(fields: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        LedgerEvidencePageRequest(profile_id=_PROFILE, **fields)
