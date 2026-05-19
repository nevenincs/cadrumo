"""Divergence taxonomy for ModeloDraft vs Justificante reconciliation.

Defines :class:`FilingDivergenceKind`, the closed set of concrete
instance-level reasons a local :class:`aeat.domain.filing.ModeloDraft`
and its parsed AEAT :class:`aeat.domain.justificante.Justificante` can
disagree.

This taxonomy classifies per-instance mismatches between the operator's
local view of a filing and what AEAT has on file. Modelo and casilla
definition changes are governed by the registry backend, not by this
reconciliation surface.
"""

from __future__ import annotations

from enum import StrEnum


class FilingDivergenceKind(StrEnum):
    """Concrete divergence variants for a ModeloDraft vs Justificante compare.

    Each member identifies a single, mutually-exclusive reason why a
    local approved draft and the AEAT-side justificante can disagree.
    The taxonomy is consumed by :class:`FieldMismatch` and surfaced in
    :class:`ReconciliationReport`.

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
