"""Closed request, result and port contracts for the stored-document page read.

The read shows one page of a document the profile holds, an evidence record's
source or an attachment, so the person can look at it while they confirm what
was read from it. A PDF or an image page is drawn as a PNG that travels in the
result as a ``data:`` URL, so no frontend writes it anywhere or parses the
document itself. A structured e-invoice has no page to draw: it is shown as
the facts its own record states, each under the served key of the word that
names it. The result names the file and never where it came from.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Final, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.document_shape import DocumentShape
from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.attachments.models import normalize_media_type
from ..operations.public_scalar import PublicDecimal

if TYPE_CHECKING:
    from .evidence_followup_contracts import AttachmentStoreFactory
    from .evidence_ports import LedgerEvidencePortsFactory
    from .structured_invoice_ports import StructuredInvoiceReader

LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID: Final = "ledger.evidence.page"

EVIDENCE_PAGE_MIN_WIDTH: Final = 64
EVIDENCE_PAGE_MAX_WIDTH: Final = 4_096
EVIDENCE_PAGE_DEFAULT_WIDTH: Final = 1_600
EVIDENCE_PAGE_MAX_NUMBER: Final = 10_000

EVIDENCE_PAGE_MAX_IMAGE_BYTES: Final = 8 * 1024 * 1024
"""The largest PNG a page read returns.

Base64 makes it a third larger, which keeps the whole result well inside the
16 MiB document a frontend reads back through the runtime.
"""

EVIDENCE_PAGE_IMAGE_URL_PREFIX: Final = "data:image/png;base64,"
_IMAGE_URL_MAX_LENGTH: Final = len(EVIDENCE_PAGE_IMAGE_URL_PREFIX) + 4 * -(-EVIDENCE_PAGE_MAX_IMAGE_BYTES // 3)

EVIDENCE_STRUCTURED_MAX_TEXT_LENGTH: Final = 4_096
"""The longest text one fact of a shown e-invoice carries; a longer one refuses the read as too large."""

EVIDENCE_STRUCTURED_MAX_LINES: Final = 5_000
"""The most lines a shown e-invoice carries; more refuse the read as too large."""

#: The served key of the word naming each structured e-invoice the read shows, by its document shape.
EVIDENCE_STRUCTURED_TITLE_KEYS: Final[Mapping[DocumentShape, str]] = MappingProxyType(
    {
        DocumentShape.XML_FACTURAE: "application.ledger.evidence.structured.title.xml_facturae",
        DocumentShape.XML_UBL: "application.ledger.evidence.structured.title.xml_ubl",
        DocumentShape.XML_CII: "application.ledger.evidence.structured.title.xml_cii",
    }
)

#: The invoice facts a shown e-invoice carries, in reading order: the record's field and the served key of its word.
EVIDENCE_STRUCTURED_FACT_KEYS: Final[tuple[tuple[str, str], ...]] = (
    ("supplier_name", "application.ledger.evidence.structured.fact.supplier_name"),
    ("supplier_tax_id", "application.ledger.evidence.structured.fact.supplier_tax_id"),
    ("customer_name", "application.ledger.evidence.structured.fact.customer_name"),
    ("customer_tax_id", "application.ledger.evidence.structured.fact.customer_tax_id"),
    ("invoice_series", "application.ledger.evidence.structured.fact.invoice_series"),
    ("invoice_number", "application.ledger.evidence.structured.fact.invoice_number"),
    ("invoice_date", "application.ledger.evidence.structured.fact.invoice_date"),
    ("rectifies_invoice_number", "application.ledger.evidence.structured.fact.rectifies_invoice_number"),
    ("currency", "application.ledger.evidence.structured.fact.currency"),
    ("taxable_base", "application.ledger.evidence.structured.fact.taxable_base"),
    ("iva_amount", "application.ledger.evidence.structured.fact.iva_amount"),
    ("recargo_amount", "application.ledger.evidence.structured.fact.recargo_amount"),
    ("retencion_rate", "application.ledger.evidence.structured.fact.retencion_rate"),
    ("retencion_amount", "application.ledger.evidence.structured.fact.retencion_amount"),
    ("suplidos_amount", "application.ledger.evidence.structured.fact.suplidos_amount"),
    ("grand_total", "application.ledger.evidence.structured.fact.grand_total"),
    ("regime_legend", "application.ledger.evidence.structured.fact.regime_legend"),
)

#: The facts of one line of a shown e-invoice, in reading order: the line's field and the served key of its word.
EVIDENCE_STRUCTURED_LINE_KEYS: Final[tuple[tuple[str, str], ...]] = (
    ("description", "application.ledger.evidence.structured.line.description"),
    ("quantity", "application.ledger.evidence.structured.line.quantity"),
    ("unit_price", "application.ledger.evidence.structured.line.unit_price"),
    ("taxable_base", "application.ledger.evidence.structured.line.taxable_base"),
    ("iva_rate", "application.ledger.evidence.structured.line.iva_rate"),
    ("iva_amount", "application.ledger.evidence.structured.line.iva_amount"),
)

#: Every key a shown e-invoice can serve; a frontend translates each as it comes.
EVIDENCE_STRUCTURED_LABEL_KEYS: Final[frozenset[str]] = frozenset(
    (
        *EVIDENCE_STRUCTURED_TITLE_KEYS.values(),
        *(key for _field, key in EVIDENCE_STRUCTURED_FACT_KEYS),
        *(key for _field, key in EVIDENCE_STRUCTURED_LINE_KEYS),
    )
)

_XML_MEDIA_TYPES: Final = frozenset({"application/xml", "text/xml"})

_EvidenceIdentity = Annotated[str, Field(min_length=1, max_length=64)]
_AttachmentId = Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
_FileName = Annotated[str, Field(min_length=1, max_length=1_024)]
_ImageDataUrl = Annotated[
    str,
    Field(
        min_length=len(EVIDENCE_PAGE_IMAGE_URL_PREFIX) + 4,
        max_length=_IMAGE_URL_MAX_LENGTH,
        pattern=r"^data:image/png;base64,[A-Za-z0-9+/]+={0,2}$",
    ),
]
_Pixels = Annotated[int, Field(ge=1, le=EVIDENCE_PAGE_MAX_WIDTH * 16)]
_LabelKey = Annotated[str, Field(min_length=1, max_length=128)]
_FactText = Annotated[str, Field(min_length=1, max_length=EVIDENCE_STRUCTURED_MAX_TEXT_LENGTH)]


class EvidencePageMediaType(StrEnum):
    """The document media types a page read can show: drawn as a page, or shown as a structured record."""

    PDF = "application/pdf"
    JPEG = "image/jpeg"
    PNG = "image/png"
    XML = "application/xml"
    """A structured e-invoice, shown as the facts its record states and never drawn."""

    @classmethod
    def of_declared(cls, mime_type: str) -> EvidencePageMediaType | None:
        """Return the member a stored manifest's declared MIME type names, or ``None`` for any other."""
        normalized = normalize_media_type(mime_type)
        if normalized in _XML_MEDIA_TYPES:
            return cls.XML
        return next((member for member in cls if member.value == normalized), None)


@dataclass(frozen=True, slots=True)
class RenderedEvidencePage:
    """One page drawn as a PNG, with the size it was drawn at and the document's page count."""

    page_count: int
    width: int
    height: int
    png: bytes


class EvidencePageRenderer(Protocol):
    """Draw one page of a document's bytes, in memory, as a bounded PNG.

    Implementations refuse with the read's typed refusals: a page beyond the
    document, bytes that do not decode as ``media_type``, and an image above
    the pixel or byte bound. The read never asks one to draw a structured
    e-invoice.
    """

    @property
    def max_source_bytes(self) -> int:
        """The largest document, in bytes, this renderer accepts."""
        ...

    def render(
        self,
        source: bytes,
        *,
        media_type: EvidencePageMediaType,
        page: int,
        max_width: int,
        max_image_bytes: int,
    ) -> RenderedEvidencePage:
        """Return page ``page`` (1-based) of ``source`` at most ``max_width`` pixels wide."""
        ...


@dataclass(frozen=True, slots=True)
class LedgerEvidencePagePorts:
    """The page read's capabilities: evidence catalogue, attachment custody, renderer and e-invoice reader."""

    evidence_ports_factory: LedgerEvidencePortsFactory
    attachment_store_factory: AttachmentStoreFactory
    renderer: EvidencePageRenderer
    structured_reader: StructuredInvoiceReader


class LedgerEvidencePageRequest(BaseModel):
    """Private request for one page of one stored document, named by exactly one identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_id: _EvidenceIdentity | None = None
    attachment_id: _AttachmentId | None = None
    page: Annotated[int, Field(ge=1, le=EVIDENCE_PAGE_MAX_NUMBER)] = 1
    max_width: Annotated[int, Field(ge=EVIDENCE_PAGE_MIN_WIDTH, le=EVIDENCE_PAGE_MAX_WIDTH)] = (
        EVIDENCE_PAGE_DEFAULT_WIDTH
    )

    @model_validator(mode="after")
    def _names_one_document(self) -> Self:
        if (self.evidence_id is None) == (self.attachment_id is None):
            raise ValueError("a page read names exactly one of evidence_id or attachment_id")
        return self


class EvidenceStructuredFactV1(BaseModel):
    """One fact a structured e-invoice states, under the served key of the word that names it.

    The fact is either text the record states, copied as it stands, or a
    figure it states; never both.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    label_key: _LabelKey
    text: _FactText | None = None
    number: PublicDecimal | None = None

    @model_validator(mode="after")
    def _one_served_value(self) -> Self:
        if self.label_key not in EVIDENCE_STRUCTURED_LABEL_KEYS:
            raise ValueError("a structured e-invoice fact is named by a served key")
        if (self.text is None) == (self.number is None):
            raise ValueError("a structured e-invoice fact states text or a figure")
        return self


class EvidenceStructuredLineV1(BaseModel):
    """The facts one line of a structured e-invoice states, in reading order."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    facts: Annotated[tuple[EvidenceStructuredFactV1, ...], Field(min_length=1)]


class EvidenceStructuredInvoiceV1(BaseModel):
    """A structured e-invoice shown as the facts its own record states, as the e-invoice reader reads them."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    title_key: _LabelKey
    facts: tuple[EvidenceStructuredFactV1, ...]
    lines: Annotated[tuple[EvidenceStructuredLineV1, ...], Field(max_length=EVIDENCE_STRUCTURED_MAX_LINES)]

    @model_validator(mode="after")
    def _served_title(self) -> Self:
        if self.title_key not in EVIDENCE_STRUCTURED_TITLE_KEYS.values():
            raise ValueError("a structured e-invoice is named by a served key")
        return self


class LedgerEvidencePageProjection(BaseModel):
    """One shown page of a stored document, with the facts the person needs to place it.

    A drawn page carries its image and the size it was drawn at; a structured
    e-invoice carries ``structured_invoice`` instead, as its one page.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_id: _EvidenceIdentity | None = None
    attachment_id: Hex64Str
    media_type: EvidencePageMediaType
    page: Annotated[int, Field(ge=1, le=EVIDENCE_PAGE_MAX_NUMBER)]
    page_count: Annotated[int, Field(ge=1)]
    width: Annotated[int | None, Field(ge=1, le=EVIDENCE_PAGE_MAX_WIDTH)] = None
    height: _Pixels | None = None
    source_sha256: ContentDigest
    file_name: _FileName | None = None
    image_data_url: _ImageDataUrl | None = Field(default=None, repr=False)
    structured_invoice: EvidenceStructuredInvoiceV1 | None = None

    @model_validator(mode="after")
    def _page_is_within_the_document(self) -> Self:
        if self.page > self.page_count:
            raise ValueError("a shown page lies beyond its document")
        if self.file_name is not None and any(separator in self.file_name for separator in ("/", "\\")):
            raise ValueError("a page result names a file, never where it lies")
        _require_one_showing(self)
        return self


def _require_one_showing(projection: LedgerEvidencePageProjection) -> None:
    drawn = (projection.width, projection.height, projection.image_data_url)
    if projection.structured_invoice is None:
        if any(value is None for value in drawn) or projection.media_type is EvidencePageMediaType.XML:
            raise ValueError("a drawn page carries its image and the size it was drawn at")
    elif (
        any(value is not None for value in drawn)
        or projection.media_type is not EvidencePageMediaType.XML
        or projection.page_count != 1
    ):
        raise ValueError("a structured e-invoice is shown as its facts, as one page, and never drawn")


class LedgerEvidencePageExecutionResult(BaseModel):
    """Encrypted result wrapper correlated to one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidencePageProjection

    @model_validator(mode="after")
    def _profile_matches_result(self) -> Self:
        if self.profile_id != self.result.profile_id:
            raise ValueError("page result belongs to another profile")
        return self


__all__ = [
    "EVIDENCE_PAGE_DEFAULT_WIDTH",
    "EVIDENCE_PAGE_IMAGE_URL_PREFIX",
    "EVIDENCE_PAGE_MAX_IMAGE_BYTES",
    "EVIDENCE_PAGE_MAX_NUMBER",
    "EVIDENCE_PAGE_MAX_WIDTH",
    "EVIDENCE_PAGE_MIN_WIDTH",
    "EVIDENCE_STRUCTURED_FACT_KEYS",
    "EVIDENCE_STRUCTURED_LABEL_KEYS",
    "EVIDENCE_STRUCTURED_LINE_KEYS",
    "EVIDENCE_STRUCTURED_MAX_LINES",
    "EVIDENCE_STRUCTURED_MAX_TEXT_LENGTH",
    "EVIDENCE_STRUCTURED_TITLE_KEYS",
    "LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID",
    "EvidencePageMediaType",
    "EvidencePageRenderer",
    "EvidenceStructuredFactV1",
    "EvidenceStructuredInvoiceV1",
    "EvidenceStructuredLineV1",
    "LedgerEvidencePageExecutionResult",
    "LedgerEvidencePagePorts",
    "LedgerEvidencePageProjection",
    "LedgerEvidencePageRequest",
    "RenderedEvidencePage",
]
