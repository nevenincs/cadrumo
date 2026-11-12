"""Declared doors of the refusals that a Modelo calculation raises for an unstated prior-carry family.

Each prior-carry family refuses the calculation while any of its carries holds
no value. The door is the statement the declaration's form serves, which the
command line stages as the same edit.
"""

from __future__ import annotations

from typing import Final

from ...domain.calculations.registry.binding_absence_attestation import PRIOR_CARRY_FAMILIES
from ..operator_actions.models import ActionReference
from ..operator_surface.models import ManifestActionProfile

PRIOR_CARRY_REFUSAL_PROFILES: Final[tuple[ManifestActionProfile, ...]] = tuple(
    ManifestActionProfile(
        subject_leaf_key="modelo.work.calculate",
        condition_id="modelo.work.calculate.prior_carries.stated",
        scenario_id=f"modelo.work.calculate.prior_carries.{family.value}_unstated",
        action=ActionReference(action_id="operator.modelo.work.attest_prior_carries"),
        no_recovery_outcome=None,
        alternative_actions=(),
    )
    for family in sorted(PRIOR_CARRY_FAMILIES)
)
"""One door per prior-carry family: state its carries, as nothing pending or with their amounts."""


__all__ = ["PRIOR_CARRY_REFUSAL_PROFILES"]
