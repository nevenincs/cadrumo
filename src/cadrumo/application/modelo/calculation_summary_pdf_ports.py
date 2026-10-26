"""The contract between the calculation summary and the PDF adapter that draws it.

The application decides what a calculation summary says and signs it; an outbound
adapter lays the pages out, tags them and assembles the archival container. This
module is the seam: the request the writer receives, the certifier it calls back
once the page layer is final, the contents a reader returns for verification, and
the fixed names of the embedded files every summary carries.

The certifier is a callback rather than an input because the statement it signs
binds a digest of the finished page layer, which only exists once the adapter has
drawn and tagged the pages. The adapter never sees a private key: it hands the
digest over and receives signed bytes back.

Reading is a separate port from writing because verifying a summary must not need
the optional ``pdf`` extra: the reader runs on the core PDF libraries alone.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, Protocol

from pydantic import BaseModel, Field

from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import BINARY_MIME_TYPE, CSV_MIME_TYPE, JSON_MIME_TYPE
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.utc import UtcInstant
from .calculation_report_certification import CalculationReportCertification
from .calculation_summary_presentation import CalculationSummaryPresentation

CALCULATION_SUMMARY_XMP_NAMESPACE: Final[str] = "https://github.com/nevenincs/cadrumo/ns/calculation-report/1/"
"""Namespace of the product properties a summary's document metadata carries.

Its presence is what marks a PDF as a Cadrumo calculation summary.
"""

CALCULATION_SUMMARY_XMP_PREFIX: Final[str] = "cdrmcr"
"""Preferred prefix the writer declares for :data:`CALCULATION_SUMMARY_XMP_NAMESPACE`."""

REPORT_ATTACHMENT_NAME: Final[str] = "cadrumo-calculation-report.json"
CSV_ATTACHMENT_NAME: Final[str] = "cadrumo-calculation-report.csv"
STATEMENT_ATTACHMENT_NAME: Final[str] = "cadrumo-report-certification.json"
SIGNATURE_ATTACHMENT_NAME: Final[str] = "cadrumo-report-certification.sig"


class CalculationSummaryAttachment(BaseModel):
    """How one embedded file of a summary is named, typed and related to it.

    ``relationship`` is the PDF associated-file relationship: ``Data`` for the
    authoritative report, ``Supplement`` for the CSV derived from it, and
    ``Unspecified`` for the statement and its signature, which neither derive the
    page nor represent it. ``description`` is fixed product text that names what
    the file is and nothing about whose it is.
    """

    model_config = STRICT_FROZEN_CONFIG

    name: str = Field(min_length=1)
    mime_type: str = Field(min_length=1)
    relationship: str = Field(min_length=1)
    description: str = Field(min_length=1)


CALCULATION_SUMMARY_ATTACHMENTS: Final[tuple[CalculationSummaryAttachment, ...]] = (
    CalculationSummaryAttachment(
        name=REPORT_ATTACHMENT_NAME,
        mime_type=JSON_MIME_TYPE,
        relationship="Data",
        description="Canonical calculation report: the authoritative data this summary renders.",
    ),
    CalculationSummaryAttachment(
        name=CSV_ATTACHMENT_NAME,
        mime_type=CSV_MIME_TYPE,
        relationship="Supplement",
        description="Casilla table derived from the calculation report.",
    ),
    CalculationSummaryAttachment(
        name=STATEMENT_ATTACHMENT_NAME,
        mime_type=JSON_MIME_TYPE,
        relationship="Unspecified",
        description="Certification statement binding the report, the CSV and the page layer.",
    ),
    CalculationSummaryAttachment(
        name=SIGNATURE_ATTACHMENT_NAME,
        mime_type=BINARY_MIME_TYPE,
        relationship="Unspecified",
        description="Ed25519 signature over the domain-separated digest of the certification statement.",
    ),
)
"""Every file a summary embeds, in the order it embeds them."""


class CalculationSummaryPdfRequest(BaseModel):
    """What the PDF writer lays out and embeds.

    ``report_bytes`` and ``csv_bytes`` are embedded verbatim, so the digests the
    statement binds are the digests of what a recipient extracts. The
    presentation carries every visible string; the writer adds none.
    """

    model_config = STRICT_FROZEN_CONFIG

    presentation: CalculationSummaryPresentation
    report_bytes: bytes
    report_sha256: ContentDigest
    csv_bytes: bytes
    exported_at: UtcInstant


class CalculationSummaryCertifier(Protocol):
    """Sign the statement for a summary whose page layer is final."""

    def __call__(self, visible_layer_sha256: str, /) -> CalculationReportCertification:
        """Return the signed statement binding ``visible_layer_sha256``."""
        ...


class CalculationSummaryPdfWriter(Protocol):
    """Render, tag, certify and assemble one calculation summary."""

    def __call__(self, request: CalculationSummaryPdfRequest, /, *, certify: CalculationSummaryCertifier) -> bytes:
        """Return the finished summary's bytes."""
        ...


class CalculationSummaryPdfUnreadableError(CadrumoError):
    """The bytes are not a PDF the reader can open."""


class CalculationSummaryPdfContents(BaseModel):
    """What a reader recovers from a summary for verification.

    ``product_metadata`` holds the document-metadata properties in
    :data:`CALCULATION_SUMMARY_XMP_NAMESPACE`, keyed by local name, and is
    ``None`` when the document carries no property in that namespace at all.
    ``visible_layer_overlays`` names every page feature the renderer never emits
    -- an annotation, a resource other than a font -- because such a feature can
    change what a page shows without changing the digested content.
    """

    model_config = STRICT_FROZEN_CONFIG

    attachments: Mapping[str, bytes]
    product_metadata: Mapping[str, str] | None
    visible_layer_sha256: ContentDigest
    visible_layer_overlays: tuple[str, ...]
    page_text: str


class CalculationSummaryPdfReader(Protocol):
    """Recover a summary's embedded files, metadata, page digest and text."""

    def __call__(self, payload: bytes, /) -> CalculationSummaryPdfContents:
        """Read ``payload``.

        Raises:
            CalculationSummaryPdfUnreadableError: ``payload`` is not a readable PDF.
        """
        ...


__all__ = [
    "CALCULATION_SUMMARY_ATTACHMENTS",
    "CALCULATION_SUMMARY_XMP_NAMESPACE",
    "CALCULATION_SUMMARY_XMP_PREFIX",
    "CSV_ATTACHMENT_NAME",
    "REPORT_ATTACHMENT_NAME",
    "SIGNATURE_ATTACHMENT_NAME",
    "STATEMENT_ATTACHMENT_NAME",
    "CalculationSummaryAttachment",
    "CalculationSummaryCertifier",
    "CalculationSummaryPdfContents",
    "CalculationSummaryPdfReader",
    "CalculationSummaryPdfRequest",
    "CalculationSummaryPdfUnreadableError",
    "CalculationSummaryPdfWriter",
]
