"""Refusal for a Modelo 100 whose inventory purchases do not say which ledger entry books them.

An inventory purchase reaches casilla 0181 through the book, and the ledger entry
that books the same purchase must leave the ledger expenses, or the purchase is
deducted twice. The calculation records two findings as notes: purchases that state
nothing about their ledger entry while their activity holds ledger expense entries,
and purchases whose claimed entry cannot stand. While the current calculation
carries one, checking, local filing and export refuse with one typed reason that
names the inventory command that corrects the purchase. The refusal never decides
for the filer whether a ledger entry books a purchase.

A calculation shown to the filer names the same door through :func:`inventory_purchase_claim_verdict`.

See Also:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
        The stored calculation head carrying the persisted notes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Final

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_sources import (
    CalculationNoteFact,
    CalculationNoteSentence,
    CalculationSourceIssue,
)
from ...domain.modelos.errors import ModeloError
from ..operator_actions.models import PreconditionVerdict
from .action_errors import ModeloPreconditionErrorMixin
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario

_SCENARIOS: Final[Mapping[CalculationNoteSentence, str]] = MappingProxyType(
    {
        CalculationNoteSentence.INVENTORY_PURCHASE_LEDGER_ROW_UNSTATED: "unstated",
        CalculationNoteSentence.INVENTORY_PURCHASE_CLAIM_REFUSED: "claim_refused",
    }
)
"""The declared scenario of each note sentence that sends the filer to the claim command."""

_OPERATOR_ARGUMENTS: Final[tuple[str, ...]] = ("actividad_id", "correction_id", "ledger_row", "movement_id")
"""What only the filer can state: which book, which purchase, and whether an entry books it.

The book is named by the filer's own identifier, which a stored calculation never keeps.
"""

_STAGE_LEAVES: Final[dict[str, str]] = {
    "verify": "modelo.work.verify",
    "file": "modelo.work.file",
    "export": "modelo.export",
}
"""The operator leaf each gated action refuses at."""

CALCULATE_LEAF: Final[str] = "modelo.work.calculate"
"""The leaf a calculation shown to the filer names the door at."""

REASON: Final[str] = "inventory_purchase_ledger_row"
"""The reason token the refusal's context carries."""


class ModeloInventoryPurchaseLedgerRowError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when an inventory purchase does not state a ledger entry that stands and the calculation is acted on."""


def _fact_value(fact: CalculationNoteFact, name: str) -> str | None:
    return next((value for key, value in fact.values if key == name), None)


def inventory_purchase_claim_notes(issues: Sequence[CalculationSourceIssue]) -> tuple[CalculationSourceIssue, ...]:
    """The notes among ``issues`` that report an inventory purchase's ledger entry as unstated or refused."""
    return tuple(issue for issue in issues if issue.fact is not None and issue.fact.sentence in _SCENARIOS)


def inventory_purchase_claim_failure(
    fact: CalculationNoteFact, *, leaf: str, provenance: ActionEvidenceProvenance
) -> ModeloPreconditionFailure | None:
    """The declared verdict that sends the filer to the claim command, or ``None`` for a fact this gate does not own."""
    scenario = _SCENARIOS.get(fact.sentence)
    year = _fact_value(fact, "year")
    count = _fact_value(fact, "count")
    if scenario is None or year is None or count is None:
        return None
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=leaf,
        scenario_id=f"{leaf}.{REASON}.{scenario}",
        evidence_id=f"{leaf}.{REASON}",
        evidence_values={"year": int(year), "purchases": int(count), "ledger_entry_stands": False},
        provenance=provenance,
        action_argument_values={"year": int(year)},
        missing_action_arguments=_OPERATOR_ARGUMENTS,
    )


def inventory_purchase_claim_verdict(fact: CalculationNoteFact | None) -> PreconditionVerdict | None:
    """The door a calculation names for a note about an inventory purchase's ledger entry, if the note is one."""
    if fact is None:
        return None
    failure = inventory_purchase_claim_failure(
        fact, leaf=CALCULATE_LEAF, provenance=ActionEvidenceProvenance.APPLICATION_STATE
    )
    return None if failure is None else failure.verdict


def inventory_purchase_claim_refusal(
    revision: CalculationRevision,
    issues: Sequence[CalculationSourceIssue],
    *,
    action: str,
) -> ModeloInventoryPurchaseLedgerRowError | None:
    """Build the typed refusal for ``action`` on ``revision``, or ``None`` where this gate does not decide it.

    The first such note names the refusal and its door; ``action`` is the gated verb
    (``verify``, ``file`` or ``export``).
    """
    leaf = _STAGE_LEAVES.get(action)
    notes = inventory_purchase_claim_notes(issues)
    if leaf is None or not notes or notes[0].fact is None:
        return None
    first = notes[0].fact
    failure = inventory_purchase_claim_failure(first, leaf=leaf, provenance=ActionEvidenceProvenance.PERSISTED_STATE)
    if failure is None:
        return None
    return ModeloInventoryPurchaseLedgerRowError(
        translated_message="errors.refused.refused_modelo_inventory_purchase_ledger_row",
        context={
            "action": action,
            "calculation_revision_id": revision.calculation_revision_id,
            "reason": REASON,
            "year": _fact_value(first, "year") or "",
            "count": _fact_value(first, "count") or "",
        },
        precondition_failure=failure,
    )


__all__ = [
    "CALCULATE_LEAF",
    "REASON",
    "ModeloInventoryPurchaseLedgerRowError",
    "inventory_purchase_claim_failure",
    "inventory_purchase_claim_notes",
    "inventory_purchase_claim_refusal",
    "inventory_purchase_claim_verdict",
]
