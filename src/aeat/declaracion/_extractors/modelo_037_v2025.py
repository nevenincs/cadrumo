"""Modelo 037 v2025 extractor — Declaración censal simplificada.

Declaración censal simplificada — reduced version of Modelo 036 for
empresarios individuales meeting size thresholds (no IVA
intracomunitario, no operaciones con paraísos fiscales, no
exports/imports outside EU, no IS, etc.). Event-triggered.

Shares the named-field set with Modelo 036 (wave 27) — same régimen
IVA / IRPF / IAE fields — since 037 is a strict subset of 036's
registro.

Legal base: Orden EHA/1274/2007 (same Orden as Modelo 036, Anexo II).
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo037V2025Extractor(GenericDeclaracionExtractor):
    """Named-field extractor for Modelo 037."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="037",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = ()
    # Label-to-value separators on 037 PDFs use either ":" or whitespace
    # columns; the regex skips both, then captures the rest of the line
    # for multi-word régimen values (wave 33 H2 fix).
    named_field_patterns: ClassVar[dict[str, str]] = {
        "causa_presentacion": r"(?m)^[^\n]*?Causa\s+(?:de\s+)?presentaci[oó]n\s*:?\s*([^\s:][^\n]*?)\s*$",
        "regimen_iva": r"(?m)^[^\n]*?R[eé]gimen\s+(?:especial\s+)?IVA\s*:?\s*([^\s:][^\n]*?)\s*$",
        "regimen_irpf": r"(?m)^[^\n]*?R[eé]gimen\s+(?:estimaci[oó]n\s+)?IRPF\s*:?\s*([^\s:][^\n]*?)\s*$",
        "epigrafe_iae": r"(?m)^[^\n]*?(?:Ep[ií]grafe\s+IAE|IAE)\s*:?\s*(\d{3,4}(?:\.\d+)?)",
        "fecha_efectos": r"(?m)^[^\n]*?Fecha\s+(?:de\s+)?efectos\s*:?\s*(\d{4}-\d{2}-\d{2})",
    }


__all__ = ["Modelo037V2025Extractor"]
