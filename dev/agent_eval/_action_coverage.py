"""Production-derived leaf-condition-scenario coverage for operator evaluation.

The evaluator consumes resolved production declarations rather than storing a
second action expectation in a scenario fixture.  A matrix row keeps the
resolved manifest profile intact: the profile owns the failed-condition and
scenario identity, the canonical action catalogue owns an action identifier,
and the operator-surface reconciliation owns live command and input-schema
evidence.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cadrumo.application.operator_surface.manifest import (
    ManifestActionResolution,
    ResolvedManifestActionProfile,
)

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class LeafConditionScenario(BaseModel):
    """One resolved production precondition outcome at one callable leaf.

    ``profile`` is the resolved production declaration, not an evaluator-owned
    copy of its action or no-recovery outcome.  Consumers must observe action
    behaviour through that profile, which keeps scenario fixtures from becoming
    an alternate action catalogue.
    """

    model_config = _STRICT_FROZEN

    profile: ResolvedManifestActionProfile

    @property
    def identity(self) -> tuple[str, str, str]:
        """Return the declared live-leaf, failed-condition, scenario identity."""
        return self.profile.declaration.identity

    @property
    def subject_leaf_key(self) -> str:
        """Return the live leaf whose guard declared this outcome."""
        return self.profile.subject_leaf.live_leaf.subject_leaf_key

    @property
    def condition_id(self) -> str:
        """Return the production failed-condition identity."""
        return self.profile.declaration.condition_id

    @property
    def scenario_id(self) -> str:
        """Return the production scenario identity."""
        return self.profile.declaration.scenario_id


class LeafConditionScenarioMatrix(BaseModel):
    """Deterministic matrix of all resolved production precondition outcomes."""

    model_config = _STRICT_FROZEN

    rows: tuple[LeafConditionScenario, ...] = Field(min_length=1)

    @field_validator("rows")
    @classmethod
    def _require_unique_sorted_identities(
        cls,
        value: tuple[LeafConditionScenario, ...],
    ) -> tuple[LeafConditionScenario, ...]:
        identities = tuple(row.identity for row in value)
        if len(set(identities)) != len(identities):
            raise ValueError("leaf-condition-scenario matrix identities must be unique")
        return tuple(sorted(value, key=lambda row: row.identity))

    def row_for(self, identity: tuple[str, str, str]) -> LeafConditionScenario:
        """Return one resolved production row or fail closed on an unknown identity."""
        for row in self.rows:
            if row.identity == identity:
                return row
        raise KeyError(f"unknown leaf-condition-scenario identity: {identity!r}")


def leaf_condition_scenario_matrix(
    resolution: ManifestActionResolution,
) -> LeafConditionScenarioMatrix:
    """Project resolved manifest declarations into one evaluator coverage matrix.

    ``ManifestActionResolution`` is accepted as the sole input deliberately:
    its construction has already joined the live operator surface to the one
    canonical action catalogue.  Accepting action ids, command keys, schemas,
    or evaluator expectations here would recreate one of those authorities.
    """
    return LeafConditionScenarioMatrix(
        rows=tuple(LeafConditionScenario(profile=profile) for profile in resolution.profiles),
    )


def production_leaf_condition_scenario_matrix() -> LeafConditionScenarioMatrix:
    """Build the current matrix from live CLI surface and production declarations."""
    from cadrumo.application.modelo._preconditions import MODELO_PRECONDITION_PROFILES
    from cadrumo.application.operator_actions._catalogue import OPERATOR_ACTION_CATALOGUE
    from cadrumo.application.operator_surface.manifest import resolve_manifest_action_profiles
    from cadrumo.entrypoints.cli import current_operator_surface_reconciliation

    resolution = resolve_manifest_action_profiles(
        profiles=MODELO_PRECONDITION_PROFILES,
        catalogue=OPERATOR_ACTION_CATALOGUE,
        reconciliation=current_operator_surface_reconciliation(),
    )
    return leaf_condition_scenario_matrix(resolution)


__all__ = [
    "LeafConditionScenario",
    "LeafConditionScenarioMatrix",
    "leaf_condition_scenario_matrix",
    "production_leaf_condition_scenario_matrix",
]
