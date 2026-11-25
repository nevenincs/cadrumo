"""Doors of the refusals met while a calculation or an amendment takes its inputs.

An identifier or value the operator supplied that the registry refuses opens the
listing or the edit that states it again, with the work unit's coordinates bound.
A choice the call made that the rules refuse, and that no catalogued action
changes, is the operator's decision. A fault only the registry, the stored
evidence or the calling code reaches is terminal.
"""

from __future__ import annotations

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.modelos.work_unit import WorkUnit
from ..operator_actions.models import PreconditionVerdict
from .refusal_door_verdicts import (
    BINDINGS_ACTION_ID,
    CASILLAS_ACTION_ID,
    FILING_RECORD_LIST_ACTION_ID,
    PROFILE_EDIT_ACTION_ID,
    WORK_CREATE_ACTION_ID,
    FactValue,
    action_door_verdict,
    decision_door_verdict,
    terminal_door_verdict,
)

_REGISTRY = ActionEvidenceProvenance.REGISTRY_RECORD
_STORED = ActionEvidenceProvenance.PERSISTED_STATE


def _coordinates(work_unit: WorkUnit) -> dict[str, FactValue]:
    return {
        "modelo": str(work_unit.modelo),
        "year": work_unit.filing_year,
        "period": work_unit.period.registry_token,
    }


def calculate_decimal_input_verdict(flag: str, key: str) -> PreconditionVerdict:
    """The value edit of a casilla, or the decision on a binding or relation value, whose decimal text was refused."""
    condition = "modelo.calculate.decimal_input.canonical"
    facts: dict[str, FactValue] = {"flag": flag, "key": key, "canonical": False}
    if flag == "--casilla":
        return action_door_verdict(
            condition,
            "operator.modelo.work.set_value",
            facts=facts,
            arguments={"casilla_id": key},
            provenance=_REGISTRY,
        )
    if flag == "--binding":
        return action_door_verdict(
            condition,
            "operator.modelo.work.override",
            facts=facts,
            arguments={"binding_id": key},
            provenance=_REGISTRY,
        )
    return decision_door_verdict(condition, facts=facts)


def calculate_detail_rows_verdict(reason: str) -> PreconditionVerdict:
    """The decision on detail rows the call supplied and the rules refuse."""
    return decision_door_verdict("modelo.calculate.detail_rows.admitted", facts={"reason": reason, "admitted": False})


def calculate_shortcut_group_verdict() -> PreconditionVerdict:
    """The decision to state a whole shortcut group or none of it."""
    return decision_door_verdict("modelo.calculate.shortcut_group.complete", facts={"complete": False})


def calculate_binding_not_overridable_verdict(key: str, *, reason: str) -> PreconditionVerdict:
    """The profile edit behind a profile-derived binding, or the decision on a date-sourced one."""
    condition = "modelo.calculate.binding.overridable"
    facts: dict[str, FactValue] = {"binding_id": key, "reason": reason, "overridable": False}
    if reason == "profile_derived":
        return action_door_verdict(condition, PROFILE_EDIT_ACTION_ID, facts=facts, provenance=_REGISTRY)
    return decision_door_verdict(condition, facts=facts, provenance=_REGISTRY)


def calculate_relation_unknown_verdict(key: str) -> PreconditionVerdict:
    """The decision on a relation identifier the revision does not declare."""
    return decision_door_verdict(
        "modelo.calculate.relation.declared", facts={"relation_id": key, "declared": False}, provenance=_REGISTRY
    )


def calculate_casilla_reference_verdict(key: str, work_unit: WorkUnit) -> PreconditionVerdict:
    """The casilla listing of the revision, for an identifier it declares only in another spelling."""
    return action_door_verdict(
        "modelo.calculate.casilla.canonical",
        CASILLAS_ACTION_ID,
        facts={"casilla_id": key, "canonical": False},
        arguments=_coordinates(work_unit),
        provenance=_REGISTRY,
    )


def semantic_role_missing_verdict(semantic_role: str, work_unit: WorkUnit) -> PreconditionVerdict:
    """The casilla listing, for a semantic role the revision attaches to no casilla."""
    return action_door_verdict(
        "modelo.calculate.semantic_role.declared",
        CASILLAS_ACTION_ID,
        facts={"semantic_role": semantic_role, "declared": False},
        arguments=_coordinates(work_unit),
        provenance=_REGISTRY,
    )


def semantic_role_ambiguous_verdict(semantic_role: str) -> PreconditionVerdict:
    """The terminal verdict of a registry that attaches one semantic role to several casillas."""
    return terminal_door_verdict(
        "modelo.registry.semantic_role.unique",
        facts={"semantic_role": semantic_role, "unique": False},
        provenance=_REGISTRY,
    )


def cleared_casilla_source_fed_verdict(casilla_ids: str) -> PreconditionVerdict:
    """The decision on clearing a casilla that a source also feeds."""
    return decision_door_verdict(
        "modelo.calculation.cleared_casilla.unfed", facts={"casilla_ids": casilla_ids, "unfed": False}
    )


def casilla_provenance_missing_verdict(origin: str) -> PreconditionVerdict:
    """The terminal verdict of a calculated casilla the revision does not declare."""
    return terminal_door_verdict(
        "modelo.calculation.casilla_provenance.declared",
        facts={"origin": origin, "declared": False},
        provenance=_REGISTRY,
    )


def work_unit_revision_divergence_verdict(work_unit: WorkUnit) -> PreconditionVerdict:
    """The creation of the work unit again under the revision the law now selects."""
    return action_door_verdict(
        "modelo.work_unit.revision.current",
        WORK_CREATE_ACTION_ID,
        facts={"work_unit_id": work_unit.work_unit_id, "current": False},
        arguments=_coordinates(work_unit),
        provenance=_STORED,
    )


def amendment_baseline_record_verdict(reason: str) -> PreconditionVerdict:
    """The filing-record listing, for an amendment target that is absent or no longer in force."""
    return action_door_verdict(
        "modelo.amendment.target.in_force",
        FILING_RECORD_LIST_ACTION_ID,
        facts={"reason": reason, "in_force": False},
        provenance=_STORED,
    )


def amendment_evidence_missing_verdict(work_unit: WorkUnit) -> PreconditionVerdict:
    """The import of the filing evidence an amended M303 return was stored without."""
    return action_door_verdict(
        "modelo.amendment.filing_instance_evidence.present",
        "operator.modelo.filing_record.import",
        facts={"work_unit_id": work_unit.work_unit_id, "present": False},
        arguments={"work_unit_id": work_unit.work_unit_id},
        provenance=_STORED,
    )


def modelo_description_verdict(reason: str, modelo: str) -> PreconditionVerdict:
    """The description of a modelo, which lists the revisions and periods its registry declares."""
    return action_door_verdict(
        f"modelo.registry.{reason}.declared",
        "operator.modelo.describe",
        facts={"reason": reason, "modelo": modelo, "declared": False},
        arguments={"modelo": modelo},
        provenance=_REGISTRY,
    )


def amendment_casillas_listing_verdict(modelo: str, filing_year: int, period: str) -> PreconditionVerdict:
    """The casilla listing of the revision, for an amendment that states too few of its required casillas."""
    return action_door_verdict(
        "modelo.amendment.required_casillas.stated",
        CASILLAS_ACTION_ID,
        facts={"modelo": modelo, "stated": False},
        arguments={"modelo": modelo, "year": filing_year, "period": period},
        provenance=_REGISTRY,
    )


def missing_input_listing_verdict(work_unit: WorkUnit) -> PreconditionVerdict:
    """The binding listing of the revision, from which the input a calculation lacks is named."""
    return action_door_verdict(
        "modelo.calculation.input.stated",
        BINDINGS_ACTION_ID,
        facts={"work_unit_id": work_unit.work_unit_id, "stated": False},
        arguments=_coordinates(work_unit),
        provenance=_REGISTRY,
    )


def amendment_choice_verdict(reason: str) -> PreconditionVerdict:
    """The decision on an amendment kind, motive or row set the rules refuse."""
    return decision_door_verdict("modelo.amendment.choice.admitted", facts={"reason": reason, "admitted": False})


__all__ = [
    "amendment_baseline_record_verdict",
    "amendment_casillas_listing_verdict",
    "amendment_choice_verdict",
    "amendment_evidence_missing_verdict",
    "calculate_binding_not_overridable_verdict",
    "calculate_casilla_reference_verdict",
    "calculate_decimal_input_verdict",
    "calculate_detail_rows_verdict",
    "calculate_relation_unknown_verdict",
    "calculate_shortcut_group_verdict",
    "casilla_provenance_missing_verdict",
    "cleared_casilla_source_fed_verdict",
    "missing_input_listing_verdict",
    "modelo_description_verdict",
    "semantic_role_ambiguous_verdict",
    "semantic_role_missing_verdict",
    "work_unit_revision_divergence_verdict",
]
