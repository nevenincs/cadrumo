"""Provider registry and file-format auto-detection."""

from __future__ import annotations

from pathlib import Path

from aeat.financial.providers._base import FinancialProvider
from aeat.financial.providers._csv import CsvProvider
from aeat.financial.providers._ofx import OfxProvider
from aeat.financial.providers._xlsx import XlsxProvider


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
    if suffix == ".xlsx":
        return (XlsxProvider(), CsvProvider(), OfxProvider())
    if suffix in {".ofx", ".qfx"}:
        return (OfxProvider(), CsvProvider(), XlsxProvider())
    if suffix in {".csv", ".txt"}:
        return (CsvProvider(), OfxProvider(), XlsxProvider())
    try:
        head = path.read_bytes()[:256]
    except OSError:
        return (CsvProvider(), XlsxProvider(), OfxProvider())
    upper_head = head.upper()
    if head.startswith(b"PK"):
        return (XlsxProvider(), CsvProvider(), OfxProvider())
    if b"<OFX>" in upper_head or b"<BANKTRANLIST>" in upper_head:
        return (OfxProvider(), CsvProvider(), XlsxProvider())
    return (CsvProvider(), XlsxProvider(), OfxProvider())
