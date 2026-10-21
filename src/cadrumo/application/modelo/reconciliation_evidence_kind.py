"""Evidence-kind vocabulary shared by reconciliation inputs and records."""

from enum import StrEnum


class ModeloReconciliationEvidenceKind(StrEnum):
    """Closed external-evidence labels accepted by reconciliation commands.

    ``DECLARATION`` performs casilla-level reconciliation for modelos in
    :data:`_DECLARATION_CASILLA_RECONCILE_MODELOS`; other modelos raise
    :class:`ReconciliationDeclaracionSourceUnsupportedError`.
    """

    JUSTIFICANTE = "justificante"
    DECLARATION = "declaration"
