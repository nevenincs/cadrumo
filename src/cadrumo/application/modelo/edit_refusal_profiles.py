"""Declared doors of a Modelo edit refused at its commit point.

An edit refused at its commit point changed nothing: a refused value is stated
again, a form that changed since it was read is read again, an edit kind not
yet applied is the operator's decision, and an edit made under a contract this
version does not accept is beyond the operator.
"""

from __future__ import annotations

from typing import Final

from ...core.operator_action_enums import NoRecoveryOutcome
from ..operator_actions.models import ActionReference
from ..operator_surface.models import ManifestActionProfile

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


EDIT_REFUSAL_PROFILES: Final[tuple[ManifestActionProfile, ...]] = (
    _edit_profile(
        "value", "admitted", "refused", "operator.modelo.work.set_value", NoRecoveryOutcome.OPERATOR_DECISION
    ),
    _edit_profile("baseline", "current", "stale", "operator.modelo.work.status", NoRecoveryOutcome.OPERATOR_DECISION),
    _edit_profile("intent", "supported", "unsupported", None, NoRecoveryOutcome.OPERATOR_DECISION),
    _edit_profile("contract", "compatible", "incompatible", None, NoRecoveryOutcome.TERMINAL),
)
"""The edit refusal families' declarations, enrolled in the Modelo precondition profiles."""

__all__ = ["EDIT_REFUSAL_PROFILES"]
