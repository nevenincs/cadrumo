"""Doors of the lifecycle refusals met when a view the operator read is stale or a prerequisite is absent.

A stale view opens the catalogued action that reads the present state again,
bound to the work unit the refusal knows. An absent prerequisite opens the
action that supplies it. Each builder names a locale-neutral reason token and
states application observations only.
"""

from __future__ import annotations

from ...core.operator_action_enums import ActionEvidenceProvenance
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.preconditions import profile_required_facts_missing_verdict
from .refusal_door_verdicts import (
    DESCRIBE_ACTION_ID,
    FILING_RECORD_IMPORT_ACTION_ID,
    PROFILE_LIST_ACTION_ID,
    VERIFICATION_REPORT_LIST_ACTION_ID,
    WORK_CALCULATE_ACTION_ID,
    WORK_CREATE_ACTION_ID,
    WORK_LIST_ACTION_ID,
    WORK_REVISIONS_ACTION_ID,
    WORK_STATUS_ACTION_ID,
    WORK_VERIFY_ACTION_ID,
    FactValue,
    action_door_verdict,
)

_STORED = ActionEvidenceProvenance.PERSISTED_STATE


def _unit_action(action_id: str, reason: str, work_unit_id: str | None) -> PreconditionVerdict:
    facts: dict[str, FactValue] = {"reason": reason, "current": False}
    if work_unit_id is not None:
        facts["work_unit_id"] = work_unit_id
    return action_door_verdict(
        f"modelo.lifecycle.{reason}.current",
        action_id,
        facts=facts,
        arguments={"work_unit_id": work_unit_id},
        provenance=_STORED,
    )


def unit_status_verdict(reason: str, work_unit_id: str | None) -> PreconditionVerdict:
    """The work unit's status, which shows its present state, for a view that changed under the request."""
    return _unit_action(WORK_STATUS_ACTION_ID, reason, work_unit_id)


def unit_revisions_verdict(reason: str, work_unit_id: str | None) -> PreconditionVerdict:
    """The work unit's revisions, from which an existing one is named or its state read."""
    return _unit_action(WORK_REVISIONS_ACTION_ID, reason, work_unit_id)


def unit_verify_verdict(reason: str, work_unit_id: str | None) -> PreconditionVerdict:
    """The verification of the work unit, which settles a draft or an incomplete outcome."""
    return _unit_action(WORK_VERIFY_ACTION_ID, reason, work_unit_id)


def unit_calculate_verdict(reason: str, work_unit_id: str | None) -> PreconditionVerdict:
    """The calculation of the work unit, which records the evidence a revision lacks."""
    return _unit_action(WORK_CALCULATE_ACTION_ID, reason, work_unit_id)


def unit_filing_evidence_verdict(reason: str, work_unit_id: str | None) -> PreconditionVerdict:
    """The import of the filing evidence a work unit's revision was stored without."""
    return _unit_action(FILING_RECORD_IMPORT_ACTION_ID, reason, work_unit_id)


def work_list_verdict(reason: str) -> PreconditionVerdict:
    """The work list, from which the units that exist are read again."""
    return action_door_verdict(
        f"modelo.lifecycle.{reason}.current",
        WORK_LIST_ACTION_ID,
        facts={"reason": reason, "current": False},
        provenance=_STORED,
    )


def work_create_verdict(reason: str, *, modelo: str, filing_year: int | None = None) -> PreconditionVerdict:
    """The creation of a work unit, for a declaration that has none."""
    return action_door_verdict(
        f"modelo.lifecycle.{reason}.present",
        WORK_CREATE_ACTION_ID,
        facts={"reason": reason, "modelo": modelo, "present": False},
        arguments={"modelo": modelo, "year": filing_year},
        provenance=_STORED,
    )


def work_address_absent_verdict(
    *, modelo: str | None, filing_year: int | None, unit_id_stated: bool
) -> PreconditionVerdict:
    """Open creation for a stated declaration with no work unit, otherwise the work list."""
    if modelo is not None and not unit_id_stated:
        return work_create_verdict("work_address_absent", modelo=modelo, filing_year=filing_year)
    return work_list_verdict("work_address_absent")


def modelo_describe_verdict(reason: str, modelo: str) -> PreconditionVerdict:
    """The description of the declaration, which states the periods and revisions it accepts."""
    return action_door_verdict(
        f"modelo.lifecycle.{reason}.valid",
        DESCRIBE_ACTION_ID,
        facts={"reason": reason, "modelo": modelo, "valid": False},
        arguments={"modelo": modelo},
        provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
    )


def verification_reports_verdict(reason: str, calculation_revision_id: str) -> PreconditionVerdict:
    """The verification reports of a revision, from which the approving one is named."""
    return action_door_verdict(
        f"modelo.lifecycle.{reason}.present",
        VERIFICATION_REPORT_LIST_ACTION_ID,
        facts={"reason": reason, "calculation_revision_id": calculation_revision_id, "present": False},
        arguments={"calculation_revision_id": calculation_revision_id},
        provenance=_STORED,
    )


def no_active_profile_verdict(reason: str) -> PreconditionVerdict:
    """The profile list, from which the profile to work in is named."""
    return action_door_verdict(
        f"modelo.lifecycle.{reason}.present",
        PROFILE_LIST_ACTION_ID,
        facts={"reason": reason, "active_profile_present": False},
        provenance=_STORED,
    )


def iva_wallet_seed_verdict() -> PreconditionVerdict:
    """The wallet seed, which records the opening a correction needs to change."""
    return action_door_verdict(
        "modelo.iva_wallet.record.present",
        "operator.modelo.iva_wallet.seed",
        facts={"record_present": False},
        provenance=_STORED,
    )


def profile_facts_verdict(field_paths: tuple[str, ...], *, modelo: str | None = None) -> PreconditionVerdict:
    """The profile questions that state the facts the refused work needs."""
    return profile_required_facts_missing_verdict(modelo=modelo, field_paths=field_paths)


__all__ = [
    "iva_wallet_seed_verdict",
    "modelo_describe_verdict",
    "no_active_profile_verdict",
    "profile_facts_verdict",
    "unit_calculate_verdict",
    "unit_filing_evidence_verdict",
    "unit_revisions_verdict",
    "unit_status_verdict",
    "unit_verify_verdict",
    "verification_reports_verdict",
    "work_address_absent_verdict",
    "work_create_verdict",
    "work_list_verdict",
]
