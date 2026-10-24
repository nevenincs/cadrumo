"""Provider registry and file-format auto-detection.

Exposes ``detect_provider``, the entry point the financial-ingest application
layer calls to pick a concrete
:class:`~adapters.inbound.financial.providers.base.FinancialProvider` for an
arbitrary path. The detection strategy combines extension hinting with
magic-byte sniffing so a misnamed file (a PDF saved as ``.csv``, an XLSX inside
a ``.txt``, etc.) still routes to the right parser.
"""

from __future__ import annotations

from pathlib import Path

from .....core.external_constants import PDF_EXTENSION, XLS_EXTENSION, XLSX_EXTENSION
from .....core.logging import get_logger
from ._constants import CSV_EXTENSIONS, OFX_EXTENSIONS
from ._mapped_tabular import MappedTabularProvider
from .base import FinancialProvider, require_admissible_source
from .csv import CsvProvider
from .ofx import OfxProvider
from .pdf_statement import PdfStatementProvider
from .xls import XlsProvider
from .xlsx import XlsxProvider

_logger = get_logger(__name__)

#: Every legacy ``.xls`` workbook is an OLE2 compound document.
_OLE2_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

#: Content sniffing reads only the leading signature bytes, so an oversized
#: source is never pulled into memory before a provider applies the shared
#: size ceiling.
_SNIFF_BYTES = 256


def _exact_layout_candidates(path: Path) -> tuple[FinancialProvider, ...]:
    """Order the exact fixed-layout providers by extension and content hint."""
    suffix = path.suffix.lower()
    if suffix == XLSX_EXTENSION:
        return (XlsxProvider(), XlsProvider(), CsvProvider(), OfxProvider())
    if suffix == XLS_EXTENSION:
        return (XlsProvider(), XlsxProvider(), CsvProvider(), OfxProvider())
    if suffix in OFX_EXTENSIONS:
        return (OfxProvider(), CsvProvider(), XlsxProvider(), XlsProvider())
    if suffix in CSV_EXTENSIONS:
        return (CsvProvider(), OfxProvider(), XlsxProvider(), XlsProvider())
    if suffix == PDF_EXTENSION:
        return (CsvProvider(), XlsxProvider(), XlsProvider(), OfxProvider())
    try:
        with path.open("rb") as handle:
            head = handle.read(_SNIFF_BYTES)
    except OSError:
        _logger.warning("detect_provider: cannot read file header for sniffing")
        return (CsvProvider(), XlsxProvider(), XlsProvider(), OfxProvider())
    return _header_layout_candidates(head)


def detect_provider(path: Path) -> FinancialProvider | None:
    """Return the first provider that validates the source successfully.

    Walks an extension- and content-prioritised candidate list and
    returns the first provider whose ``validate_source`` result is an
    ``is_valid`` :class:`~adapters.inbound.financial.providers.base.ProviderValidation`.
    The shared size and file-kind guard runs before any header sniff or
    provider probe reads the source.

    Args:
        path: Source document to classify.

    Returns:
        The matching :class:`FinancialProvider`, or ``None`` when no
        provider can interpret ``path``.

    Raises:
        InvalidFinancialSourceError: When the source is a symlink, missing,
            not a regular file, or over the ingest size ceiling.
    """
    require_admissible_source(path)
    providers = _ordered_candidates(path)
    for provider in providers:
        if provider.validate_source(path).is_valid:
            _logger.debug("detect_provider: matched %s for %s", provider.name, path.name)
            return provider
    _logger.warning("detect_provider: no provider matched %s", path.name)
    return None


def _ordered_candidates(path: Path) -> tuple[FinancialProvider, ...]:
    """Order providers by extension hint and content sniffing, inferred lanes last.

    The two inferred lanes are appended after every exact fixed-layout provider
    and never ahead of one. An exact layout match is a deterministic read of a
    known structure; an inferred lane's read depends on a model's proposal.
    Ordering an inferred lane earlier would let it shadow an exact provider on
    a known export, silently substituting an inferred parse for a deterministic
    one.

    :class:`PdfStatementProvider` precedes :class:`MappedTabularProvider`. It
    accepts only PDF content and declines anything else from its signature
    alone, so it shadows no tabular export, while a PDF never reaches the
    tabular lane's column-role mapping as if it were a delimited table.
    """
    return (*_exact_layout_candidates(path), PdfStatementProvider(), MappedTabularProvider())


def _header_layout_candidates(head: bytes) -> tuple[FinancialProvider, ...]:
    """Retain exact provider precedence for each supported content signature."""
    upper_head = head.upper()
    if head.startswith(b"PK"):
        return (XlsxProvider(), CsvProvider(), OfxProvider(), XlsProvider())
    if head.startswith(_OLE2_SIGNATURE):
        return (XlsProvider(), CsvProvider(), XlsxProvider(), OfxProvider())
    if b"<OFX>" in upper_head or b"<BANKTRANLIST>" in upper_head:
        return (OfxProvider(), CsvProvider(), XlsxProvider(), XlsProvider())
    return (CsvProvider(), XlsxProvider(), XlsProvider(), OfxProvider())
