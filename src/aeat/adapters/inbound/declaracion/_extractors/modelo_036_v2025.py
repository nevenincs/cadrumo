"""Modelo 036 v2025 extractor — Declaración censal completa.

Declaración censal de alta, modificación o baja en el Censo de
Empresarios, Profesionales y Retenedores. Completa (~8 pages, all
obligados tributarios regardless of size/régimen). Event-triggered —
filed within 1 month of the hecho censal (article 10 RD 1065/2007).

Captures the most-used censal decisions via the named-field primitive:

- causa de presentación (alta / modificación / baja).
- régimen IVA (general, simplificado, agricultura, recargo de
  equivalencia, exento).
- régimen IRPF (directa, objetiva, atribución).
- actividad económica (IAE epígrafe).
- fecha de efectos.

Legal base: Orden EHA/1274/2007, modified through HAC/1634/2022.
"""

from __future__ import annotations

from typing import ClassVar

from .._generic_extractor import GenericDeclaracionExtractor
from .._schema import TemplateRevision


class Modelo036V2025Extractor(GenericDeclaracionExtractor):
    """Named-field extractor for Modelo 036 (Declaración censal completa).

    Uses :class:`aeat.adapters.inbound.declaracion._generic_extractor.GenericDeclaracionExtractor`'s
    named-field primitive — Modelo 036 prints censal decisions as
    ``label : value`` pairs rather than numbered casillas, so
    :attr:`casilla_ids` is empty and :attr:`named_field_patterns`
    carries the regex map.

    Attributes:
        template_revision: Pinned to ``("036", 2025, "2025.01")``.
        casilla_ids: Empty — Modelo 036 has no numbered casillas.
        named_field_patterns: Label regex map keyed by canonical field
            name (``causa_presentacion``, ``regimen_iva``,
            ``regimen_irpf``, ``epigrafe_iae``, ``fecha_efectos``).
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="036",
        año=2025,
        revision="2025.01",
    )
    casilla_ids: ClassVar[tuple[str, ...]] = ()
    # Label-to-value separators on 036 PDFs use either ":" or whitespace
    # columns; the regex skips both, then captures the rest of the line
    # (fix — multi-word régimen values like "Recargo de
    # equivalencia" or "Estimación directa simplificada" were previously
    # truncated to the first token). Trailing whitespace is stripped.
    named_field_patterns: ClassVar[dict[str, str]] = {
        "causa_presentacion": r"(?m)^[^\n]*?Causa\s+(?:de\s+)?presentaci[oó]n\s*:?\s*([^\s:][^\n]*?)\s*$",
        "regimen_iva": r"(?m)^[^\n]*?R[eé]gimen\s+(?:especial\s+)?IVA\s*:?\s*([^\s:][^\n]*?)\s*$",
        "regimen_irpf": r"(?m)^[^\n]*?R[eé]gimen\s+(?:estimaci[oó]n\s+)?IRPF\s*:?\s*([^\s:][^\n]*?)\s*$",
        "epigrafe_iae": r"(?m)^[^\n]*?(?:Ep[ií]grafe\s+IAE|IAE)\s*:?\s*(\d{3,4}(?:\.\d+)?)",
        "fecha_efectos": r"(?m)^[^\n]*?Fecha\s+(?:de\s+)?efectos\s*:?\s*(\d{4}-\d{2}-\d{2})",
    }


__all__ = ["Modelo036V2025Extractor"]
