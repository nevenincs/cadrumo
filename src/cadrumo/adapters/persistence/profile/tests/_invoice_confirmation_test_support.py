"""Real adapter-layer setup for invoice-confirmation integration tests.

These tests exercise encrypted profile storage, document readers, and the
invoice-confirmation composition boundary.  The support therefore lives with
the persistence adapter tests and composes the same required application
ports as the executable roots; inward application tests do not need to reach
through this module.
"""

from __future__ import annotations

import json
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

import httpx
import pytest

from cadrumo.adapters.inbound.einvoice.application_translation import translate_parsed_einvoice
from cadrumo.adapters.inbound.einvoice.parsers import parse_einvoice_document
from cadrumo.adapters.inbound.einvoice.shape import probe_document_shape
from cadrumo.adapters.inbound.einvoice.xml import EInvoiceXmlParseError
from cadrumo.adapters.inbound.pdf.page_text_extraction import extract_pages_text_from_bytes
from cadrumo.adapters.outbound.llm.errors import LLMConsentError, LLMPdfRasterisationError, LLMProviderError
from cadrumo.adapters.outbound.llm.evidence_draft_text import TextInvoiceFieldExtractor, extract_invoice_fields_from_text
from cadrumo.adapters.outbound.llm.evidence_draft_vision import LocalVisionDocumentTranscriber, transcribe_document_images
from cadrumo.adapters.outbound.llm.models import MultimodalImageInput
from cadrumo.adapters.outbound.llm.preconditions import LLMPreconditionCondition, llm_no_recovery_verdict
from cadrumo.adapters.outbound.llm.providers.local import rasterise_pdf_pages_to_base64_png
from cadrumo.adapters.outbound.llm.supply_nature_proposal import SupplyNatureProposer
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
from cadrumo.adapters.persistence.profile.counterparty_establishment import CounterpartyEstablishmentRepository
from cadrumo.adapters.persistence.profile.invoice_confirmation import build_invoice_confirmation_ports
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.purchase_invoice_evidence import (
    LedgerEvidenceAttachmentIngestor,
    LedgerEvidenceRepositoryAdapter,
)
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from cadrumo.application.ledger.document_transcription import DocumentTranscription
from cadrumo.application.invoices.catalogue_creation_ports import CatalogueCreationPorts
from cadrumo.application.ledger.evidence import PurchaseInvoiceEvidenceService
from cadrumo.application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from cadrumo.application.ledger.evidence_input import (
    EvidenceInput,
    resolve_attachment_evidence_input,
    resolve_purchase_invoice_evidence_input,
)
from cadrumo.application.ledger.evidence_input_ports import EvidenceInputPorts
from cadrumo.application.ledger.evidence_ports import LedgerEvidencePorts
from cadrumo.application.ledger.evidence_textlayer_ports import EvidenceTextLayerPorts
from cadrumo.application.ledger.evidence_reference import (
    EvidenceReferenceOutcome,
    classify_evidence_reference,
    refuse_reference_without_document_bytes,
    refuse_unresolved_evidence_reference,
)
from cadrumo.application.ledger.invoice_draft_extraction_ports import (
    EvidenceConsentProof,
    InvoiceDraftExtractionPorts,
    InvoiceDraftReaderUnavailableError,
    StructuredInvoiceReadError,
    VisionImage,
)
from cadrumo.application.ledger.invoice_extraction_authority import InvoiceExtractionAuthorityValues
from cadrumo.application.ledger.preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict
from cadrumo.core.config import Settings, override_settings
from cadrumo.core.config_support import LLMProvider
from cadrumo.core.operator_action_enums import ActionEvidenceProvenance
from cadrumo.core.optional_extras import MissingOptionalExtraError
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from cadrumo.domain.iva.supply_nature import SupplyNature
from cadrumo.tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.ledger.filer_establishment import FILER_POSTCODE_FACT_PATH

_BUCKET_ID = "29292929-2929-4929-8929-292929292929"
_EVIDENCE_CORPUS = (
    Path(__file__).resolve().parents[4] / "application" / "ledger" / "tests" / "_evidence_corpus"
)

runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


def _ledger_evidence_ports(*, bucket_id: str) -> LedgerEvidencePorts:
    """Compose the encrypted evidence adapters for this adapter-layer fixture."""
    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    return LedgerEvidencePorts(
        evidence_repository=LedgerEvidenceRepositoryAdapter(objects=objects),
        attachment_ingestor=LedgerEvidenceAttachmentIngestor(store=AttachmentStore(objects=objects)),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )


def evidence_text_layer_ports_for_test() -> EvidenceTextLayerPorts:
    """Bind the real PDF reader for persistence-layer integration tests."""

    def extract_pages_text(data: bytes) -> tuple[str, ...]:
        try:
            return extract_pages_text_from_bytes(
                data,
                error_class=ValueError,
                pdf_label="the invoice PDF",
            )
        except ValueError as exc:
            raise PurchaseInvoiceEvidenceInputError(
                "evidence text-layer extraction failed",
                precondition_verdict=ledger_no_recovery_verdict(
                    LedgerPreconditionCondition.EVIDENCE_TEXT_LAYER_AVAILABLE,
                    facts={
                        "pdf_layer_present": False,
                        "text_layer_extraction_succeeded": False,
                    },
                ),
            ) from exc

    return EvidenceTextLayerPorts(extract_pages_text=extract_pages_text)


def _invoice_draft_extraction_ports(*, evidence_ports: LedgerEvidencePorts) -> InvoiceDraftExtractionPorts:
    """Compose reader adapters locally for the profile persistence tests."""
    evidence_input_ports = EvidenceInputPorts(document_shape_probe=probe_document_shape)
    text_layer_ports = evidence_text_layer_ports_for_test()

    def resolve_evidence_input(
        bucket_id: str, evidence_id: str | None, attachment_id: str | None, settings: Settings
    ) -> EvidenceInput:
        store = AttachmentStore(objects=secure_object_repository_for_bucket(bucket_id, settings))
        if evidence_id is not None:
            reference = classify_evidence_reference(
                evidence_id,
                bucket_id=bucket_id,
                evidence_records=PurchaseInvoiceEvidenceService(ports=evidence_ports).list_all(bucket_id=bucket_id),
                invoices=InvoiceCatalogueRepository(bucket_id=bucket_id).load(),
            )
            if reference.outcome is EvidenceReferenceOutcome.UNRESOLVED:
                raise refuse_unresolved_evidence_reference(evidence_id)
            if reference.record is None:
                raise refuse_reference_without_document_bytes(evidence_id)
            return resolve_purchase_invoice_evidence_input(reference.record, store=store, ports=evidence_input_ports)
        if attachment_id is None:
            raise PurchaseInvoiceEvidenceInputError(translated_message="errors.refused.refused_ledger_evidence_input")
        return resolve_attachment_evidence_input(attachment_id, store=store, ports=evidence_input_ports)

    def parse_structured_invoice(data: bytes):
        try:
            return translate_parsed_einvoice(parse_einvoice_document(data))
        except EInvoiceXmlParseError as exc:
            raise StructuredInvoiceReadError() from exc

    def read_text(
        transcription: DocumentTranscription,
        settings: Settings,
        provider: LLMProvider | None,
        consent_token: EvidenceConsentProof | None,
        authority_values: InvoiceExtractionAuthorityValues,
    ):
        try:
            if provider is None:
                return extract_invoice_fields_from_text(transcription, authority_values=authority_values)
            return TextInvoiceFieldExtractor(
                provider=provider,
                model=settings.cadrumo_llm_cloud_text_model,
                settings=settings,
                authority_values=authority_values,
                consent_token=consent_token,
            ).extract(transcription=transcription)
        except (MissingOptionalExtraError, LLMProviderError, httpx.HTTPError) as exc:
            raise InvoiceDraftReaderUnavailableError(exc) from exc

    def propose_supply_nature(transcription: DocumentTranscription, settings: Settings) -> SupplyNature | None:
        try:
            return SupplyNatureProposer(settings=settings).propose(transcription.text.splitlines()).nature
        except Exception:
            return None

    def rasterise_pdf(data: bytes) -> tuple[str, ...]:
        try:
            return tuple(rasterise_pdf_pages_to_base64_png(data))
        except LLMPdfRasterisationError as exc:
            raise InvoiceDraftReaderUnavailableError(exc) from exc

    def transcribe_vision(
        images: tuple[VisionImage, ...],
        source_content_sha256: str,
        settings: Settings,
        provider: LLMProvider | None,
        consent_token: EvidenceConsentProof | None,
    ) -> DocumentTranscription:
        try:
            inputs = tuple(MultimodalImageInput.from_base64(image.base64_data, image.media_type) for image in images)
            if provider is None:
                return transcribe_document_images(
                    inputs, source_content_sha256=source_content_sha256, settings=settings
                )
            return LocalVisionDocumentTranscriber(
                provider=provider,
                model=settings.cadrumo_llm_cloud_vision_model,
                settings=settings,
                consent_token=consent_token,
            ).transcribe(evidence_images=inputs, source_content_sha256=source_content_sha256)
        except (MissingOptionalExtraError, LLMProviderError, httpx.HTTPError) as exc:
            raise InvoiceDraftReaderUnavailableError(exc) from exc

    def consent_binding_error(facts: dict[str, object]) -> Exception:
        return LLMConsentError(
            translated_message="llm.evidence.consent.binding_mismatch",
            context=facts,
            precondition_verdict=llm_no_recovery_verdict(
                LLMPreconditionCondition.EVIDENCE_TOKEN_BOUND,
                facts=facts,
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            ),
        )

    return InvoiceDraftExtractionPorts(
        resolve_evidence_input=resolve_evidence_input,
        evidence_input_ports=evidence_input_ports,
        text_layer_ports=text_layer_ports,
        parse_structured_invoice=parse_structured_invoice,
        read_text=read_text,
        propose_supply_nature=propose_supply_nature,
        rasterise_pdf=rasterise_pdf,
        transcribe_vision=transcribe_vision,
        consent_binding_error=consent_binding_error,
    )


def _make_svc(isolated_settings: Settings, objects: SecureObjectRepository) -> PurchaseInvoiceEvidenceService:
    """Build the evidence service from the adapter-local encrypted fixture."""
    del isolated_settings, objects
    return PurchaseInvoiceEvidenceService(ports=_ledger_evidence_ports(bucket_id=_BUCKET_ID))


def seed_filer_profile(*, tax_id: str | None = "12345678Z") -> None:
    """Seed the filer profile the evidence draft path reads its territory from."""
    clock = datetime(2026, 1, 1, tzinfo=UTC)
    facts = [UserProfileFact(path=FILER_POSTCODE_FACT_PATH, value="28001")]
    if tax_id is not None:
        facts.insert(0, UserProfileFact(path="identity.tax_id", value=tax_id))
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=tuple(facts),
            created_at=clock,
            updated_at=clock,
        ),
    )


@pytest.fixture(autouse=True)
def seeded_filer_profile(secure_objects: SecureObjectRepository) -> None:
    """Provide the profile facts required by the real confirmation path."""
    del secure_objects
    seed_filer_profile()


@pytest.fixture
def isolated_settings(runtime_profile) -> Settings:
    return runtime_profile.settings


@pytest.fixture
def secure_objects(runtime_profile) -> SecureObjectRepository:
    return runtime_profile.repository


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    path = tmp_path / "receipt.pdf"
    path.write_bytes(b"%PDF-1.4 test")
    return path


def invoice_confirmation_kwargs(*, bucket_id: str) -> Mapping[str, object]:
    """Compose every required port for a real confirmation invocation."""
    evidence_ports = _ledger_evidence_ports(bucket_id=bucket_id)
    return {
        "catalogue_creation_ports": build_catalogue_creation_ports(bucket_id=bucket_id),
        "invoice_confirmation_ports": build_invoice_confirmation_ports(bucket_id=bucket_id),
        "counterparty_establishment_repository": CounterpartyEstablishmentRepository(bucket_id=bucket_id),
        "evidence_ports": evidence_ports,
        "extraction_ports": _invoice_draft_extraction_ports(evidence_ports=evidence_ports),
    }


def invoice_confirmation_kwargs_with_catalogue(
    *,
    bucket_id: str,
    catalogue_creation_ports: CatalogueCreationPorts,
) -> Mapping[str, object]:
    """Compose confirmation ports while retaining a test-specific catalogue port."""
    evidence_ports = _ledger_evidence_ports(bucket_id=bucket_id)
    return {
        "catalogue_creation_ports": catalogue_creation_ports,
        "invoice_confirmation_ports": build_invoice_confirmation_ports(bucket_id=bucket_id),
        "counterparty_establishment_repository": CounterpartyEstablishmentRepository(bucket_id=bucket_id),
        "evidence_ports": evidence_ports,
        "extraction_ports": _invoice_draft_extraction_ports(evidence_ports=evidence_ports),
    }


ReaderReply = tuple[str, Mapping[str, str]]
READING_RUNTIME_MODEL = "qwen2.5:7b"


class _LoopbackRequestHandler(SilentLoopbackHandler):
    """A real local endpoint speaking the reading runtime's ``/api/chat`` shape."""

    replies: ClassVar[Sequence[ReaderReply]] = ()
    fallback: ClassVar[Mapping[str, str]] = dict[str, str]()

    def _fields_for(self, prompt: str) -> Mapping[str, str]:
        for marker, fields in self.replies:
            if marker in prompt:
                return fields
        return self.fallback

    @override
    def do_POST(self) -> None:
        prompt = json.dumps(read_json_body(self)["messages"])
        write_json_response(
            self,
            ollama_chat_reply(
                json.dumps(dict(self._fields_for(prompt))),
                model=READING_RUNTIME_MODEL,
                prompt_eval_count=100,
                eval_count=50,
            ),
            status=HTTPStatus.OK,
        )


@contextmanager
def serving_a_loopback_reader(
    replies: Sequence[ReaderReply],
    *,
    fallback: Mapping[str, str] | None = None,
) -> Generator[str]:
    """Serve the deterministic local reading endpoint used by these tests."""
    _LoopbackRequestHandler.replies = tuple(replies)
    _LoopbackRequestHandler.fallback = dict(fallback or {})
    with (
        serving_loopback(_LoopbackRequestHandler, path="/api/chat") as chat_url,
        override_settings(cadrumo_llm_ollama_chat_url=chat_url),
    ):
        yield chat_url


__all__ = [
    "READING_RUNTIME_MODEL",
    "_BUCKET_ID",
    "_EVIDENCE_CORPUS",
    "_make_svc",
    "invoice_confirmation_kwargs",
    "invoice_confirmation_kwargs_with_catalogue",
    "isolated_settings",
    "pdf_file",
    "runtime_profile",
    "secure_objects",
    "seed_filer_profile",
    "seeded_filer_profile",
    "serving_a_loopback_reader",
]
