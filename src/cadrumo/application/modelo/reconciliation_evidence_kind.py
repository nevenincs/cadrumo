"""Evidence-kind vocabulary shared by reconciliation inputs and records."""

from enum import StrEnum


class ModeloReconciliationEvidenceKind(StrEnum):
    """Closed external-evidence labels accepted by reconciliation commands.

    ``DECLARATION`` performs casilla-level reconciliation for modelos enrolled under
    :data:`cadrumo.application.modelo.reconciliation._DECLARATION_RECONCILE_ROLE`; other modelos raise
    :class:`ReconciliationDeclaracionSourceUnsupportedError`.
    """

    JUSTIFICANTE = "justificante"
    DECLARATION = "declaration"
