"""Declared doors of a Modelo edit refused at its commit point, and of a refused binding value.

An edit refused at its commit point changed nothing: a refused value is stated
again, a form that changed since it was read is read again, an edit kind not
yet applied is the operator's decision, and an edit made under a contract this
version does not accept is beyond the operator. A carry statement whose
withdrawal cannot leave the declaration uncalculated is replaced by the
carried figures, or, on a declaration recorded as filed, amended. A figure
stated for an earlier return the application holds is refused, since that
return decides it, and the filer opens it among the declarations.

A binding value the preview call carried and the pinned contract refuses is
stated again in that call, which no catalogued action takes, so it is the
operator's decision. A binding whose pinned contract has no official value
grammar can accept no value from anyone, so it is terminal.
"""

from __future__ import annotations

from typing import Final

from ...core.operator_action_enums import NoRecoveryOutcome
from ..operator_actions.models import ActionReference
from ..operator_surface.models import ManifestActionProfile
from .declaration_refusal_profiles import DECLARATION_REFUSAL_PROFILES
from .work_lifecycle_refusal_profiles import WORK_LIFECYCLE_REFUSAL_PROFILES

_EDIT_LEAF: Final[str] = "modelo.work.set_value"


def _edit_profile(
    condition: str, sound: str, refused: str, action_id: str | None, outcome: NoRecoveryOutcome
) -> ManifestActionProfile:
    return ManifestActionProfile(
        subject_leaf_key=_EDIT_LEAF,
        condition_id=f"modelo.work.edit.{condition}.{sound}",
        scenario_id=f"modelo.work.edit.{condition}.{refused}",
        action=None if action_id is None else ActionReference(action_id=action_id),
        no_recovery_outcome=outcome if action_id is None else None,
    )


_BINDING_LEAF: Final[str] = "modelo.bindings.resolve"

EDIT_REFUSAL_PROFILES: Final[tuple[ManifestActionProfile, ...]] = (
    _edit_profile(
        "value", "admitted", "refused", "operator.modelo.work.set_value", NoRecoveryOutcome.OPERATOR_DECISION
    ),
    _edit_profile("baseline", "current", "stale", "operator.modelo.work.status", NoRecoveryOutcome.OPERATOR_DECISION),
    _edit_profile("intent", "supported", "unsupported", None, NoRecoveryOutcome.OPERATOR_DECISION),
    _edit_profile("contract", "compatible", "incompatible", None, NoRecoveryOutcome.TERMINAL),
    # A carry statement whose withdrawal would discard the filer's other values is replaced by the
    # carried figures; one on a declaration recorded as filed is corrected by amendment.
    _edit_profile(
        "carry_withdrawal",
        "admitted",
        "keeps_entries",
        "operator.modelo.work.attest_prior_value",
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
    _edit_profile(
        "carry_withdrawal", "admitted", "filed", "operator.modelo.work.amend", NoRecoveryOutcome.OPERATOR_DECISION
    ),
    # A figure stated for an earlier return the application holds would hide that return, so the
    # filer opens it among the declarations.
    _edit_profile(
        "prior_value", "admitted", "source_held", "operator.modelo.work.list", NoRecoveryOutcome.OPERATOR_DECISION
    ),
    ManifestActionProfile(
        subject_leaf_key=_BINDING_LEAF,
        condition_id="modelo.bindings.value.admitted",
        scenario_id="modelo.bindings.value.refused",
        no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    ),
    ManifestActionProfile(
        subject_leaf_key=_BINDING_LEAF,
        condition_id="modelo.bindings.value_contract.supported",
        scenario_id="modelo.bindings.value_contract.unsupported",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    ),
    *WORK_LIFECYCLE_REFUSAL_PROFILES,
    *DECLARATION_REFUSAL_PROFILES,
)
"""The edit refusal families' declarations, enrolled in the Modelo precondition profiles."""

__all__ = ["EDIT_REFUSAL_PROFILES"]
