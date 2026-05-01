"""Provider registry and file-format auto-detection."""

from __future__ import annotations

from pathlib import Path

from ._base import FinancialProvider
from ._csv import CsvProvider
from ._ofx import OfxProvider
from ._pdf_n26 import PdfN26Provider
from ._xlsx import XlsxProvider


def detect_provider(path: Path) -> FinancialProvider | None:
    """Return the first provider that validates the source successfully."""
    providers = _ordered_candidates(path)
    for provider in providers:
        if provider.validate_source(path).is_valid:
            return provider
    return None


def _ordered_candidates(path: Path) -> tuple[FinancialProvider, ...]:
    """Order providers by extension hint, then fall back to content sniffing."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return (PdfN26Provider(), CsvProvider(), XlsxProvider(), OfxProvider())
    if suffix == ".xlsx":
        return (XlsxProvider(), CsvProvider(), OfxProvider(), PdfN26Provider())
    if suffix in {".ofx", ".qfx"}:
        return (OfxProvider(), CsvProvider(), XlsxProvider(), PdfN26Provider())
    if suffix in {".csv", ".txt"}:
        return (CsvProvider(), OfxProvider(), XlsxProvider(), PdfN26Provider())
    try:
        head = path.read_bytes()[:256]
    except OSError:
        return (CsvProvider(), XlsxProvider(), OfxProvider(), PdfN26Provider())
    upper_head = head.upper()
    if head.startswith(b"%PDF"):
        return (PdfN26Provider(), CsvProvider(), XlsxProvider(), OfxProvider())
    if head.startswith(b"PK"):
        return (XlsxProvider(), CsvProvider(), OfxProvider(), PdfN26Provider())
    if b"<OFX>" in upper_head or b"<BANKTRANLIST>" in upper_head:
        return (OfxProvider(), CsvProvider(), XlsxProvider(), PdfN26Provider())
    return (CsvProvider(), XlsxProvider(), OfxProvider(), PdfN26Provider())
