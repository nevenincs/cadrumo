"""Closed request, result and port contracts for the stored-document page read.

The read draws one page of a document the profile holds, an evidence record's
source or an attachment, as a PNG image the person can look at while they
confirm what was read from it. The image travels in the result as a ``data:``
URL, so no frontend writes it anywhere or parses the document itself. The
result names the file and never where it came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Final, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.attachments.models import normalize_media_type

if TYPE_CHECKING:
    from .evidence_followup_contracts import AttachmentStoreFactory
    from .evidence_ports import LedgerEvidencePortsFactory

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

_EvidenceIdentity = Annotated[str, Field(min_length=1, max_length=64)]
_AttachmentId = Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
_FileName = Annotated[str, Field(min_length=1, max_length=1_024)]
_ImageDataUrl = Annotated[
    str,
    Field(
        min_length=len(EVIDENCE_PAGE_IMAGE_URL_PREFIX) + 4,
        max_length=_IMAGE_URL_MAX_LENGTH,
        pattern=r"^data:image/png;base64,[A-Za-z0-9+/]+={0,2}$",
        repr=False,
    ),
]
_Pixels = Annotated[int, Field(ge=1, le=EVIDENCE_PAGE_MAX_WIDTH * 16)]


class EvidencePageMediaType(StrEnum):
    """The document media types a page read can draw."""

    PDF = "application/pdf"
    JPEG = "image/jpeg"
    PNG = "image/png"

    @classmethod
    def of_declared(cls, mime_type: str) -> EvidencePageMediaType | None:
        """Return the member a stored manifest's declared MIME type names, or ``None`` for any other."""
        normalized = normalize_media_type(mime_type)
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
    the pixel or byte bound.
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
    """The capabilities the page read needs: the evidence catalogue, attachment custody and a renderer."""

    evidence_ports_factory: LedgerEvidencePortsFactory
    attachment_store_factory: AttachmentStoreFactory
    renderer: EvidencePageRenderer


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


class LedgerEvidencePageProjection(BaseModel):
    """One drawn page of a stored document, with the facts the person needs to place it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_id: _EvidenceIdentity | None = None
    attachment_id: Hex64Str
    media_type: EvidencePageMediaType
    page: Annotated[int, Field(ge=1, le=EVIDENCE_PAGE_MAX_NUMBER)]
    page_count: Annotated[int, Field(ge=1)]
    width: Annotated[int, Field(ge=1, le=EVIDENCE_PAGE_MAX_WIDTH)]
    height: _Pixels
    source_sha256: ContentDigest
    file_name: _FileName | None = None
    image_data_url: _ImageDataUrl

    @model_validator(mode="after")
    def _page_is_within_the_document(self) -> Self:
        if self.page > self.page_count:
            raise ValueError("a drawn page lies beyond its document")
        if self.file_name is not None and any(separator in self.file_name for separator in ("/", "\\")):
            raise ValueError("a page result names a file, never where it lies")
        return self


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
    "LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID",
    "EvidencePageMediaType",
    "EvidencePageRenderer",
    "LedgerEvidencePageExecutionResult",
    "LedgerEvidencePagePorts",
    "LedgerEvidencePageProjection",
    "LedgerEvidencePageRequest",
    "RenderedEvidencePage",
]
