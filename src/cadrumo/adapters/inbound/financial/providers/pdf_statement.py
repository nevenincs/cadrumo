"""Bank statements in PDF form, in any bank's layout and language.

:class:`PdfStatementProvider` holds no knowledge of any bank. It reads each
page's text layer with ``pdfplumber``; a page that carries none is transcribed
by the on-host vision model instead. The on-host text model then proposes the
movements each page prints, as printed strings, and
:mod:`._statement_grounding` decides deterministically which of those
proposals the page really prints and whether they reconcile with the printed
balances. Only anchored, reconciled movements are emitted.

The model-backed stages are reached through the application port
:mod:`application.ledger.statement_reading`, which an outer composition root
binds. This adapter never imports the outbound model adapter. A host that has
not bound a reader declines every PDF with a stated reason, and a host whose
reader needs the uninstalled ``llm`` extra raises the typed missing-extra
refusal when it meets a PDF, while every other format keeps importing. A
reader whose local AI is not ready declines the PDF with the reader probe's
verdict, so the import refusal names the setup that would let it be read.

Reading a statement costs model calls, so one provider instance reads each
distinct source once: detection's validation and the following ingest share
the result, keyed by the content address of the bytes.
"""

from __future__ import annotations

import io
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import override

from .....application.dependency_wording import statement_reader_refusal_reason
from .....application.ledger.document_transcription import DocumentTranscription
from .....application.ledger.evidence_textlayer import text_layer_transcriber_identity
from .....application.ledger.import_ports import LedgerImportReaderUnavailableError
from .....application.ledger.statement_reading import (
    StatementReaderFactory,
    StatementReaderPort,
    statement_reader_factory,
)
from .....core.errors.error_codes import resolve_error_message
from .....core.errors.hierarchy import CadrumoError
from .....core.logging import get_logger
from .....core.optional_extras import MissingOptionalExtraError
from .....domain.transactions.raw_transaction import SourceFormat
from ...pdf.redaction import INPUT_PDF_SOURCE_LABEL as _INPUT_PDF_SOURCE_LABEL
from ._statement_grounding import GroundedStatement, StatementPageText, ground_statement
from .base import (
    FinancialProvider,
    FinancialProviderError,
    InvalidFinancialSourceError,
    ParsedLedgerRow,
    ProviderValidation,
    build_raw_transaction,
    default_currency,
    synthesize_transaction_id,
)

__all__ = ["PdfStatementProvider"]

_logger = get_logger(__name__)

#: Every PDF document opens with this signature.
_PDF_SIGNATURE = b"%PDF"

_NOT_A_PDF = "source is not a PDF document"
_NO_READER = "no statement reader is installed for PDF statements"


@dataclass(frozen=True, slots=True)
class _StatementRead:
    """One source's grounded statement and the stamp of the reader that proposed it."""

    statement: GroundedStatement
    decided_by: str
    page_count: int


class PdfStatementProvider(FinancialProvider):
    """Ingest bank movements from a PDF statement of any layout.

    Attributes:
        reader_factory: Builds the statement reader when a PDF needs one.
            Defaults to the factory the composition root bound; tests and
            callers holding their own reader pass it directly.
    """

    name = "PDF provider"
    source_format = SourceFormat.PDF
    # The bundled statement PDFs exercising this provider are synthetic
    # documents generated from sanitised, published statement text, and the
    # model reading them is not measured against real operator statements.
    verification_source = "synthetic_from_bank_published_text"
    provisional_pending_specimen = True

    def __init__(self, reader_factory: StatementReaderFactory | None = None) -> None:
        """Bind the factory supplying this provider's statement reader."""
        self.reader_factory: StatementReaderFactory | None = (
            reader_factory if reader_factory is not None else statement_reader_factory()
        )
        self._reads: dict[str, _StatementRead] = {}

    @override
    def validate_source(self, path: Path) -> ProviderValidation:
        """Read the statement and report every movement that was not accepted.

        Validation is the full read: every dropped proposal and every
        reconciliation finding is reported here, so the operator sees the whole
        picture before ingest. The source is valid when at least one movement
        is anchored and nothing refuses the statement. A statement whose
        reader could not be asked is invalid and carries the reader's verdict,
        so detection keeps this provider and the import names the setup.

        Raises:
            MissingOptionalExtraError: When the source is a PDF and the bound
                reader needs the uninstalled ``llm`` extra.
        """
        try:
            source_bytes = self._read_source_bytes(path)
        except InvalidFinancialSourceError as exc:
            return ProviderValidation(is_valid=False, warnings=(resolve_error_message(exc),))
        if not source_bytes.startswith(_PDF_SIGNATURE):
            return ProviderValidation(is_valid=False, warnings=(_NOT_A_PDF,))
        if self.reader_factory is None:
            return ProviderValidation(is_valid=False, warnings=(_NO_READER,))
        try:
            read = self._read(source_bytes)
        except InvalidFinancialSourceError as exc:
            return ProviderValidation(is_valid=False, warnings=(resolve_error_message(exc),))
        except LedgerImportReaderUnavailableError as exc:
            verdict = exc.terminal_precondition_verdict
            if verdict is None:
                raise
            return ProviderValidation(
                is_valid=False,
                warnings=(statement_reader_refusal_reason(verdict),),
                reader_unavailable_verdict=verdict,
            )
        statement = read.statement
        return ProviderValidation(
            is_valid=statement.importable,
            warnings=(*statement.warnings, *statement.refusals),
            detected_encoding="pdfplumber",
            detected_dialect=(
                f"pages={read.page_count};movements={len(statement.movements)};"
                f"reconciliation={statement.reconciliation.value}"
            ),
        )

    @override
    def ingest(self, path: Path) -> Iterator[ParsedLedgerRow]:
        """Yield one :class:`ParsedLedgerRow` per anchored, reconciled movement.

        Raises:
            InvalidFinancialSourceError: The source is not a PDF, no reader is
                bound, the PDF cannot be read, or the statement is refused.
            LedgerImportReaderUnavailableError: The local AI the bound reader
                needs is not ready; the verdict names its setup.
            MissingOptionalExtraError: The bound reader needs the uninstalled
                ``llm`` extra.
        """
        source_bytes = self._read_source_bytes(path)
        if not source_bytes.startswith(_PDF_SIGNATURE):
            raise InvalidFinancialSourceError(_NOT_A_PDF)
        if self.reader_factory is None:
            raise InvalidFinancialSourceError(_NO_READER)
        source_sha256 = self._compute_sha256(source_bytes)
        read = self._read(source_bytes)
        if not read.statement.importable:
            raise InvalidFinancialSourceError(
                "the PDF statement cannot be imported: " + "; ".join(read.statement.refusals),
            )
        for source_row_index, movement in enumerate(read.statement.movements, start=1):
            yield build_raw_transaction(
                provider=self,
                path=path,
                source_sha256=source_sha256,
                source_row_index=source_row_index,
                provider_transaction_id=synthesize_transaction_id(
                    provider_name=self.name,
                    source_sha256=source_sha256,
                    source_row_index=source_row_index,
                ),
                booked_date=movement.booked_date,
                value_date=movement.value_date,
                amount=movement.signed_amount,
                currency=movement.currency,
                counterparty=movement.counterparty,
                description=movement.description,
                raw_fields={**movement.printed, "read_by": read.decided_by},
            )

    def _read(self, source_bytes: bytes) -> _StatementRead:
        """Transcribe, read and ground one source once per provider instance."""
        source_sha256 = self._compute_sha256(source_bytes)
        cached = self._reads.get(source_sha256)
        if cached is not None:
            return cached
        factory = self.reader_factory
        if factory is None:
            raise InvalidFinancialSourceError(_NO_READER)
        page_texts = _extract_page_texts(source_bytes)
        try:
            reader = factory()
            transcriptions = _transcribe(reader, source_bytes, source_sha256, page_texts)
            pages = tuple(
                StatementPageText(
                    page_number=page_number,
                    text=transcription.text,
                    proposal=reader.propose_page(transcription),
                    transcribed_by=transcription.transcriber.name,
                )
                for page_number, transcription in sorted(transcriptions.items())
            )
        except (MissingOptionalExtraError, FinancialProviderError, LedgerImportReaderUnavailableError):
            raise
        except CadrumoError as exc:
            raise InvalidFinancialSourceError(
                f"the statement reader could not read the PDF: {resolve_error_message(exc)}",
            ) from exc
        statement = ground_statement(pages, default_currency=default_currency())
        unread = tuple(number for number in range(1, len(page_texts) + 1) if number not in transcriptions)
        if unread:
            statement = replace(
                statement,
                refusals=(
                    *statement.refusals,
                    f"page(s) {', '.join(str(number) for number in unread)} carry no text layer and could not be "
                    "transcribed, so the statement would be imported incomplete",
                ),
            )
        read = _StatementRead(statement=statement, decided_by=reader.decided_by, page_count=len(page_texts))
        self._reads[source_sha256] = read
        return read


def _transcribe(
    reader: StatementReaderPort,
    source_bytes: bytes,
    source_sha256: str,
    page_texts: tuple[str, ...],
) -> Mapping[int, DocumentTranscription]:
    """Return one transcription per readable page, text layer first, vision for the rest."""
    identity = text_layer_transcriber_identity()
    transcriptions: dict[int, DocumentTranscription] = {
        page_number: DocumentTranscription(
            text=text,
            page_count=1,
            source_content_sha256=source_sha256,
            transcriber=identity,
        )
        for page_number, text in enumerate(page_texts, start=1)
        if text
    }
    scanned = tuple(number for number in range(1, len(page_texts) + 1) if number not in transcriptions)
    if scanned:
        transcriptions.update(
            reader.transcribe_scanned_pages(
                source_bytes,
                page_numbers=scanned,
                source_content_sha256=source_sha256,
            ),
        )
    return transcriptions


def _extract_page_texts(source_bytes: bytes) -> tuple[str, ...]:
    """Return each page's text layer in page order; a page without one keeps an empty slot."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise InvalidFinancialSourceError("pdfplumber is not installed") from exc
    try:
        with pdfplumber.open(io.BytesIO(source_bytes)) as pdf:
            pages = tuple((page.extract_text() or "").strip() for page in pdf.pages)
    # pdfplumber raises OSError, ValueError and struct.error from its PDF parser,
    # and that surface grows with library versions, so every failure is
    # converted to the provider's own refusal here.
    except Exception as exc:
        _logger.debug(
            "pdf_statement_provider: failed to parse PDF file %s: %s",
            _INPUT_PDF_SOURCE_LABEL,
            type(exc).__name__,
        )
        raise InvalidFinancialSourceError(
            f"could not parse PDF file: {_INPUT_PDF_SOURCE_LABEL}",
            translated_message="adapters.inbound.financial.providers.pdf_statement.errors.parse_failed",
            context={"source": _INPUT_PDF_SOURCE_LABEL},
        ) from exc
    if not pages:
        raise InvalidFinancialSourceError("PDF file contains no pages")
    return pages
