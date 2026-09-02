"""Provider registry and file-format auto-detection.

Exposes ``detect_provider``, the entry point the financial-ingest application
layer calls to pick a concrete
:class:`~adapters.inbound.financial.providers.FinancialProvider` for an
arbitrary path. The detection strategy combines extension hinting with
magic-byte sniffing so a misnamed file (a PDF saved as ``.csv``, an XLSX inside
a ``.txt``, etc.) still routes to the right parser.
"""

from __future__ import annotations

from pathlib import Path

from .....core.logging import get_logger
from ._constants import CSV_EXTENSIONS, OFX_EXTENSIONS, PDF_EXTENSION, XLSX_EXTENSION
from ._mapped_tabular import MappedTabularProvider
from .base import FinancialProvider
from .csv import CsvProvider
from .ofx import OfxProvider
from .pdf_n26 import PdfN26Provider
from .xlsx import XlsxProvider

_logger = get_logger(__name__)


def _exact_layout_candidates(path: Path) -> tuple[FinancialProvider, ...]:
    """Order the exact fixed-layout providers by extension and content hint."""
    suffix = path.suffix.lower()
    if suffix == PDF_EXTENSION:
        return (PdfN26Provider(), CsvProvider(), XlsxProvider(), OfxProvider())
    if suffix == XLSX_EXTENSION:
        return (XlsxProvider(), CsvProvider(), OfxProvider(), PdfN26Provider())
    if suffix in OFX_EXTENSIONS:
        return (OfxProvider(), CsvProvider(), XlsxProvider(), PdfN26Provider())
    if suffix in CSV_EXTENSIONS:
        return (CsvProvider(), OfxProvider(), XlsxProvider(), PdfN26Provider())
    try:
        head = path.read_bytes()[:256]
    except OSError:
        _logger.warning("detect_provider: cannot read file header for sniffing path=%s", path, exc_info=True)
        return (CsvProvider(), XlsxProvider(), OfxProvider(), PdfN26Provider())
    upper_head = head.upper()
    if head.startswith(b"%PDF"):
        return (PdfN26Provider(), CsvProvider(), XlsxProvider(), OfxProvider())
    if head.startswith(b"PK"):
        return (XlsxProvider(), CsvProvider(), OfxProvider(), PdfN26Provider())
    if b"<OFX>" in upper_head or b"<BANKTRANLIST>" in upper_head:
        return (OfxProvider(), CsvProvider(), XlsxProvider(), PdfN26Provider())
    return (CsvProvider(), XlsxProvider(), OfxProvider(), PdfN26Provider())


def provider_for_extension(path: Path) -> FinancialProvider | None:
    """Return a :class:`FinancialProvider` keyed strictly off ``path``'s suffix.

    Cheap fallback used by CLI command surfaces when content-aware
    detection (:func:`detect_provider`) returns ``None`` but the path's
    suffix is unambiguous. Unlike :func:`detect_provider` this does not
    open the file or sniff its bytes.

    Returns ``None`` for every extension the project does not recognise
    (PDF among them — :class:`PdfN26Provider` requires content-aware
    detection because the bare ``.pdf`` suffix carries no statement
    flavour information).
    """
    suffix = path.suffix.lower()
    if suffix in CSV_EXTENSIONS:
        return CsvProvider()
    if suffix == XLSX_EXTENSION:
        return XlsxProvider()
    if suffix in OFX_EXTENSIONS:
        return OfxProvider()
    return None


def detect_provider(path: Path) -> FinancialProvider | None:
    """Return the first provider that validates the source successfully.

    Walks an extension- and content-prioritised candidate list and
    returns the first provider whose ``validate_source`` result is an
    ``is_valid`` :class:`~adapters.inbound.financial.providers.ProviderValidation`.

    Args:
        path: Source document to classify.

    Returns:
        The matching :class:`FinancialProvider`, or ``None`` when no
        provider can interpret ``path``.
    """
    providers = _ordered_candidates(path)
    for provider in providers:
        if provider.validate_source(path).is_valid:
            _logger.debug("detect_provider: matched %s for %s", provider.name, path.name)
            return provider
    _logger.warning("detect_provider: no provider matched %s", path.name)
    return None


def _ordered_candidates(path: Path) -> tuple[FinancialProvider, ...]:
    """Order providers by extension hint and content sniffing, mapping lane last.

    :class:`MappedTabularProvider` is appended after every exact fixed-layout
    provider and never ahead of one. An exact layout match is a deterministic
    read of a known structure; the mapping lane's read depends on a per-file
    column-role mapping. Ordering the fallback earlier would let it shadow an
    exact provider on a known bank export, silently substituting an inferred
    parse for a deterministic one.
    """
    return (*_exact_layout_candidates(path), MappedTabularProvider())
