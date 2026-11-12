"""Failed-precondition carriers of the work lookup, selector, mutation and revision-state refusals."""

from __future__ import annotations

from collections.abc import Mapping

from ...core.operator_action_enums import ActionEvidenceProvenance
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario
from .work_lifecycle_refusal_profiles import (
    AMEND_LEAF,
    AMENDMENT_DUPLICATE_SCENARIO,
    AMENDMENT_UNCHANGED_SCENARIO,
    CEDED_MODELO_SCENARIO,
    CREATE_LEAF,
    LIST_LEAF,
    MUTATION_STALE_SCENARIO,
    REVISION_STATE_SCENARIO,
    REVISIONS_LEAF,
    SELECTOR_CONTRADICTORY_SCENARIO,
    SELECTOR_INCOHERENT_SCENARIO,
    STATUS_LEAF,
    UNIT_ABSENT_SCENARIO,
)


def _work_unit_id(context: Mapping[str, object] | None) -> str | None:
    value = None if context is None else context.get("work_unit_id")
    return value if isinstance(value, str) and value else None


def _unit_arguments(context: Mapping[str, object] | None) -> tuple[dict[str, str] | None, tuple[str, ...]]:
    """The bound work unit, or the argument only the operator can then supply."""
    work_unit_id = _work_unit_id(context)
    if work_unit_id is None:
        return None, ("work_unit_id",)
    return {"work_unit_id": work_unit_id}, ()


def work_unit_absent_failure() -> ModeloPreconditionFailure:
    """The work list, from which an existing unit can be addressed."""
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=LIST_LEAF,
        scenario_id=UNIT_ABSENT_SCENARIO,
        evidence_id="modelo.work.lookup.unit",
        evidence_values={"present": False},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )


def selector_contradiction_failure() -> ModeloPreconditionFailure:
    """The work list, from which the unit's own coordinates can be read and stated again."""
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=LIST_LEAF,
        scenario_id=SELECTOR_CONTRADICTORY_SCENARIO,
        evidence_id="modelo.work.selector.coordinates",
        evidence_values={"consistent": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )


def selector_incoherent_failure() -> ModeloPreconditionFailure:
    """A selection the application resolved incoherently, which no input of the operator changes."""
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=LIST_LEAF,
        scenario_id=SELECTOR_INCOHERENT_SCENARIO,
        evidence_id="modelo.work.selector.resolution",
        evidence_values={"coherent": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )


def mutation_stale_failure(context: Mapping[str, object] | None) -> ModeloPreconditionFailure:
    """The unit's status, from which its present state is read before the mutation is asked again."""
    values, missing = _unit_arguments(context)
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=STATUS_LEAF,
        scenario_id=MUTATION_STALE_SCENARIO,
        evidence_id="modelo.work.mutation.baseline",
        evidence_values={"current": False},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_argument_values=values,
        missing_action_arguments=missing,
    )


def ceded_modelo_failure(modelo: str) -> ModeloPreconditionFailure:
    """A modelo whose tax another administration manages, so no work unit is created here."""
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=CREATE_LEAF,
        scenario_id=CEDED_MODELO_SCENARIO,
        evidence_id="modelo.work.create.jurisdiction",
        evidence_values={"state_administered": False, "modelo": modelo},
        provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
    )


def revision_state_failure(context: Mapping[str, object] | None) -> ModeloPreconditionFailure:
    """The unit's revisions, from which the revision's state is read."""
    values, missing = _unit_arguments(context)
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=REVISIONS_LEAF,
        scenario_id=REVISION_STATE_SCENARIO,
        evidence_id="modelo.work.revision.state",
        evidence_values={"admitted": False},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_argument_values=values,
        missing_action_arguments=missing,
    )


def amendment_unchanged_failure() -> ModeloPreconditionFailure:
    """An amendment that states the values the filed revision already holds."""
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=AMEND_LEAF,
        scenario_id=AMENDMENT_UNCHANGED_SCENARIO,
        evidence_id="modelo.work.amend.content",
        evidence_values={"distinct": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )


def amendment_duplicate_failure() -> ModeloPreconditionFailure:
    """An amendment whose revision is already stored."""
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=AMEND_LEAF,
        scenario_id=AMENDMENT_DUPLICATE_SCENARIO,
        evidence_id="modelo.work.amend.content",
        evidence_values={"new": False},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )
