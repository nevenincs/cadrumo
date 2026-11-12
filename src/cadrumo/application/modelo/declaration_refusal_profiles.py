"""Declared doors of the refusals a declaration's comparison, resolution, solicitud and election meet.

Each cause is one refusal family. A profile the filer must state again, or a
calculation that must be made again, opens the catalogued action that does it.
A refusal of a value or choice the filer made in the call that no catalogued
action takes again is the operator's decision. A fault only the stored data,
the registry or the caller reaches is terminal and names no command.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from ...core.operator_action_enums import NoRecoveryOutcome
from ..operator_actions.models import ActionReference
from ..operator_surface.models import ManifestActionProfile

COMPARE_LEAF: Final[str] = "modelo.work.compare_taxation"
ACCEPT_LEAF: Final[str] = "modelo.work.accept_disagreement"
REVOKE_LEAF: Final[str] = "modelo.work.revoke_disagreement"
M360_DECLARE_LEAF: Final[str] = "modelo.m360.declare"
M360_REMOVE_LEAF: Final[str] = "modelo.m360.remove"
EXPORT_LEAF: Final[str] = "modelo.export"

CALCULATE_ACTION_ID: Final[str] = "operator.modelo.work.calculate"
STATUS_ACTION_ID: Final[str] = "operator.modelo.work.status"
PROFILE_EDIT_ACTION_ID: Final[str] = "operator.profile.edit"
FILED_PULL_ACTION_ID: Final[str] = "operator.live.filed.pull"


class DeclarationRefusalCause(StrEnum):
    """One cause a comparison, resolution, solicitud or prior-domiciliation election is refused for."""

    TAXATION_UNDECLARED = "taxation_declared"
    TAXATION_REVISION = "taxation_revision"
    TAXATION_CALCULATION = "taxation_calculation"
    TAXATION_ENTRIES = "taxation_entries"
    TAXATION_SPOUSE = "taxation_spouse"
    TAXATION_FAMILY_SITUATION = "taxation_family_situation"
    TAXATION_FAMILY_UNIT = "taxation_family_unit"
    TAXATION_BOXES = "taxation_boxes"
    CREDIT_FINDING_NAMED = "credit_finding_named"
    CREDIT_FINDING_READABLE = "credit_finding_readable"
    CREDIT_CALCULATION = "credit_calculation"
    CREDIT_ALREADY_RESOLVED = "credit_already_resolved"
    CREDIT_NOT_RESOLVED = "credit_not_resolved"
    CREDIT_RECORD_ACTIVE = "credit_record_active"
    SOLICITUD_ACCOUNT_REGISTERED = "solicitud_account_registered"
    SOLICITUD_ACCOUNT_OPEN = "solicitud_account_open"
    SOLICITUD_ACCOUNT_BIC = "solicitud_account_bic"
    SOLICITUD_ACCOUNT_VALID = "solicitud_account_valid"
    SOLICITUD_FACTS = "solicitud_facts"
    SOLICITUD_HOLDER = "solicitud_holder"
    SOLICITUD_DECLARED = "solicitud_declared"
    ELECTION_MODELO = "prior_domiciliation_modelo"
    ELECTION_AMENDMENT = "prior_domiciliation_amendment"
    ELECTION_BASELINE_TARGET = "prior_domiciliation_baseline_target"
    ELECTION_OBSERVATION = "prior_domiciliation_observation"
    ELECTION_OBSERVATION_REFERENCE = "prior_domiciliation_observation_reference"
    ELECTION_HEADER_COUNT = "prior_domiciliation_header_count"
    ELECTION_HEADER_VALUE = "prior_domiciliation_header_value"
    ELECTION_DISPOSITION = "prior_domiciliation_disposition"
    ELECTION_TYPE = "prior_domiciliation_type"
    ELECTION_MARKER_LAYOUT = "prior_domiciliation_marker_layout"


@dataclass(frozen=True, slots=True)
class DeclarationRefusalSpec:
    """The declared leaf, condition, scenario and door of one cause."""

    leaf: str
    sound: str
    refused: str
    action_id: str | None
    outcome: NoRecoveryOutcome


_DECISION = NoRecoveryOutcome.OPERATOR_DECISION
_TERMINAL = NoRecoveryOutcome.TERMINAL
_CAUSE = DeclarationRefusalCause

DECLARATION_REFUSAL_SPECS: Final[dict[DeclarationRefusalCause, DeclarationRefusalSpec]] = {
    cause: DeclarationRefusalSpec(leaf, sound, refused, action_id, outcome)
    for cause, leaf, sound, refused, action_id, outcome in (
        (_CAUSE.TAXATION_UNDECLARED, COMPARE_LEAF, "declared", "undeclared", None, _TERMINAL),
        (_CAUSE.TAXATION_REVISION, COMPARE_LEAF, "current", "outdated", None, _DECISION),
        (_CAUSE.TAXATION_CALCULATION, COMPARE_LEAF, "calculated", "uncalculated", CALCULATE_ACTION_ID, _DECISION),
        (_CAUSE.TAXATION_ENTRIES, COMPARE_LEAF, "recorded", "unrecorded", CALCULATE_ACTION_ID, _DECISION),
        (_CAUSE.TAXATION_SPOUSE, COMPARE_LEAF, "stated", "unstated", PROFILE_EDIT_ACTION_ID, _DECISION),
        (_CAUSE.TAXATION_FAMILY_SITUATION, COMPARE_LEAF, "stated", "unstated", PROFILE_EDIT_ACTION_ID, _DECISION),
        (_CAUSE.TAXATION_FAMILY_UNIT, COMPARE_LEAF, "family_unit", "not_family_unit", None, _DECISION),
        (_CAUSE.TAXATION_BOXES, COMPARE_LEAF, "resolved", "unresolved", None, _DECISION),
        (_CAUSE.CREDIT_FINDING_NAMED, ACCEPT_LEAF, "named", "unnamed", None, _DECISION),
        (_CAUSE.CREDIT_FINDING_READABLE, ACCEPT_LEAF, "readable", "unreadable", None, _TERMINAL),
        (_CAUSE.CREDIT_CALCULATION, ACCEPT_LEAF, "current", "stale", STATUS_ACTION_ID, _DECISION),
        (_CAUSE.CREDIT_ALREADY_RESOLVED, ACCEPT_LEAF, "unresolved", "resolved", None, _DECISION),
        (_CAUSE.CREDIT_NOT_RESOLVED, REVOKE_LEAF, "resolved", "unresolved", None, _DECISION),
        (_CAUSE.CREDIT_RECORD_ACTIVE, ACCEPT_LEAF, "active", "inactive", None, _TERMINAL),
        (_CAUSE.SOLICITUD_ACCOUNT_REGISTERED, M360_DECLARE_LEAF, "registered", "unregistered", None, _DECISION),
        (_CAUSE.SOLICITUD_ACCOUNT_OPEN, M360_DECLARE_LEAF, "open", "closed", None, _DECISION),
        (_CAUSE.SOLICITUD_ACCOUNT_BIC, M360_DECLARE_LEAF, "bic_held", "bic_missing", None, _DECISION),
        (_CAUSE.SOLICITUD_ACCOUNT_VALID, M360_DECLARE_LEAF, "valid", "invalid", None, _DECISION),
        (_CAUSE.SOLICITUD_FACTS, M360_DECLARE_LEAF, "valid", "invalid", None, _DECISION),
        (_CAUSE.SOLICITUD_HOLDER, M360_DECLARE_LEAF, "consistent", "mismatch", None, _DECISION),
        (_CAUSE.SOLICITUD_DECLARED, M360_REMOVE_LEAF, "declared", "undeclared", None, _DECISION),
        (_CAUSE.ELECTION_MODELO, EXPORT_LEAF, "supported_modelo", "unsupported_modelo", None, _DECISION),
        (_CAUSE.ELECTION_AMENDMENT, EXPORT_LEAF, "rectificativa", "not_rectificativa", None, _DECISION),
        (_CAUSE.ELECTION_BASELINE_TARGET, EXPORT_LEAF, "matches_target", "mismatch", None, _TERMINAL),
        (_CAUSE.ELECTION_OBSERVATION, EXPORT_LEAF, "captured", "uncaptured", FILED_PULL_ACTION_ID, _DECISION),
        (_CAUSE.ELECTION_OBSERVATION_REFERENCE, EXPORT_LEAF, "matches_evidence", "mismatch", None, _DECISION),
        (_CAUSE.ELECTION_HEADER_COUNT, EXPORT_LEAF, "single_header", "header_count", None, _TERMINAL),
        (_CAUSE.ELECTION_HEADER_VALUE, EXPORT_LEAF, "domiciliacion_header", "other_disposition", None, _DECISION),
        (_CAUSE.ELECTION_DISPOSITION, EXPORT_LEAF, "projected", "unprojected", None, _TERMINAL),
        (_CAUSE.ELECTION_TYPE, EXPORT_LEAF, "typed", "untyped", None, _TERMINAL),
        (_CAUSE.ELECTION_MARKER_LAYOUT, EXPORT_LEAF, "renders_marker", "lacks_marker", None, _TERMINAL),
    )
}
"""Every cause's declaration, keyed by cause."""


def condition_id(cause: DeclarationRefusalCause) -> str:
    """Return the declared sound-condition identity of ``cause``."""
    spec = DECLARATION_REFUSAL_SPECS[cause]
    return f"{spec.leaf}.{cause.value}.{spec.sound}"


def scenario_id(cause: DeclarationRefusalCause) -> str:
    """Return the declared refused-scenario identity of ``cause``."""
    spec = DECLARATION_REFUSAL_SPECS[cause]
    return f"{spec.leaf}.{cause.value}.{spec.refused}"


def _profile(cause: DeclarationRefusalCause, spec: DeclarationRefusalSpec) -> ManifestActionProfile:
    return ManifestActionProfile(
        subject_leaf_key=spec.leaf,
        condition_id=condition_id(cause),
        scenario_id=scenario_id(cause),
        action=None if spec.action_id is None else ActionReference(action_id=spec.action_id),
        no_recovery_outcome=spec.outcome if spec.action_id is None else None,
    )


DECLARATION_REFUSAL_PROFILES: Final[tuple[ManifestActionProfile, ...]] = tuple(
    _profile(cause, spec) for cause, spec in DECLARATION_REFUSAL_SPECS.items()
)
"""The comparison, resolution, solicitud and election refusal declarations, enrolled in the Modelo profiles."""

__all__ = [
    "ACCEPT_LEAF",
    "CALCULATE_ACTION_ID",
    "COMPARE_LEAF",
    "DECLARATION_REFUSAL_PROFILES",
    "DECLARATION_REFUSAL_SPECS",
    "EXPORT_LEAF",
    "FILED_PULL_ACTION_ID",
    "M360_DECLARE_LEAF",
    "M360_REMOVE_LEAF",
    "PROFILE_EDIT_ACTION_ID",
    "REVOKE_LEAF",
    "STATUS_ACTION_ID",
    "DeclarationRefusalCause",
    "DeclarationRefusalSpec",
    "condition_id",
    "scenario_id",
]
