"""FilingDivergenceKind enum for FilingDraft ↔ Justificante compare.

Disjoint from :class:`aeat.application.sync._divergence.DivergenceKind` (which is
schema-level and baked into auto-heal decision tables). The variants
here are instance-level: one per concrete reason a FilingDraft and
its AEAT justificante can disagree.
"""

from __future__ import annotations

from enum import StrEnum


class FilingDivergenceKind(StrEnum):
    """Concrete divergence taxonomy for a FilingDraft ↔ Justificante compare.

    Attributes:
        FILING_NOT_YET_FOUND: AEAT has no matching justificante at all
            for this ``(modelo, period)`` on the authenticated sede.
        MODELO_MISMATCH: Draft and justificante disagree on modelo code.
        PERIOD_MISMATCH: Draft and justificante disagree on period label.
        TAX_ID_MISMATCH: Draft's ``profile_tax_id`` and justificante's
            ``tax_id`` disagree.
        TOTAL_INGRESAR_MISMATCH: AEAT-recorded ``total_a_ingresar``
            differs from the draft's derived ingresar figure.
        TOTAL_DEVOLVER_MISMATCH: AEAT-recorded ``total_a_devolver``
            differs from the draft's derived devolver figure.
        PRESENTATION_ID_MISMATCH: ``número de justificante`` on the
            PDF differs from what the draft recorded at submission.
    """

    FILING_NOT_YET_FOUND = "filing_not_yet_found"
    MODELO_MISMATCH = "modelo_mismatch"
    PERIOD_MISMATCH = "period_mismatch"
    TAX_ID_MISMATCH = "tax_id_mismatch"
    TOTAL_INGRESAR_MISMATCH = "total_ingresar_mismatch"
    TOTAL_DEVOLVER_MISMATCH = "total_devolver_mismatch"
    PRESENTATION_ID_MISMATCH = "presentation_id_mismatch"


__all__ = ["FilingDivergenceKind"]
