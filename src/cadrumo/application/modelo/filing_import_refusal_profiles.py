"""Declared doors of the refusals that meet a filed declaration, receipt or local observation the operator brings in.

Each cause is one refusal family. An input the operator can state again opens the
filing-record import; a missing taxpayer identifier opens the profile edit; a
refusal no catalogued action repairs is the operator's decision; and a fault only
the caller or the stored data reaches is terminal, naming no command.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from ...core.operator_action_enums import NoRecoveryOutcome
from ..operator_actions.models import ActionReference
from ..operator_surface.models import ManifestActionProfile

IMPORT_LEAF: Final[str] = "modelo.filing_record.import"
LOCAL_OBSERVATION_LEAF: Final[str] = "modelo.filing_record.observe_local"
FILE_LEAF: Final[str] = "modelo.work.file"
IMPORT_ACTION_ID: Final[str] = "operator.modelo.filing_record.import"
PROFILE_EDIT_ACTION_ID: Final[str] = "operator.profile.edit"


class FilingImportRefusalCause(StrEnum):
    """One cause a brought-in declaration, receipt or local observation is refused for."""

    SOURCE_VALUES = "source_values"
    EVIDENCE_REFERENCE = "evidence_reference"
    JUSTIFICANTE_TARGET = "justificante"
    TAXPAYER_TAX_ID = "taxpayer_tax_id"
    WORK_UNIT = "work_unit"
    FILING_INSTANCE_EVIDENCE = "filing_instance_evidence"
    REVISION_DUPLICATE = "revision"
    RECONCILIATION = "reconciliation"
    JUSTIFICANTE_ARTIFACT = "justificante_artifact"
    REGISTER_REFERENCE = "register_reference"
    SOURCE_CONSISTENCY = "source"
    FILING_CHAIN = "filing_chain"
    AUDIT_TEXT = "audit_text"
    COORDINATE = "coordinate"
    OBSERVABLE_MODELO = "modelo"
    REVISION_AVAILABILITY = "revision_availability"
    OBSERVED_VALUES = "values"
    OBSERVED_CASILLAS = "casillas"
    OVERRIDE = "override"
    SOURCE_FILE = "source_file"
    OBSERVATION_STORAGE = "observation_storage"
    RESULT_DISPOSITION = "result_disposition"
    AUTHORITY = "authority"


@dataclass(frozen=True, slots=True)
class FilingImportRefusalSpec:
    """The declared leaf, condition, scenario and door of one cause."""

    leaf: str
    sound: str
    refused: str
    action_id: str | None
    outcome: NoRecoveryOutcome


_DECISION = NoRecoveryOutcome.OPERATOR_DECISION
_TERMINAL = NoRecoveryOutcome.TERMINAL
_CAUSE = FilingImportRefusalCause

FILING_IMPORT_REFUSAL_SPECS: Final[dict[FilingImportRefusalCause, FilingImportRefusalSpec]] = {
    cause: FilingImportRefusalSpec(leaf, sound, refused, action_id, outcome)
    for cause, leaf, sound, refused, action_id, outcome in (
        (_CAUSE.SOURCE_VALUES, IMPORT_LEAF, "usable", "unusable", IMPORT_ACTION_ID, _DECISION),
        (_CAUSE.EVIDENCE_REFERENCE, IMPORT_LEAF, "stated", "blank", IMPORT_ACTION_ID, _DECISION),
        (_CAUSE.JUSTIFICANTE_TARGET, IMPORT_LEAF, "matches_target", "mismatch", IMPORT_ACTION_ID, _DECISION),
        (_CAUSE.TAXPAYER_TAX_ID, IMPORT_LEAF, "declared", "missing", PROFILE_EDIT_ACTION_ID, _DECISION),
        (_CAUSE.WORK_UNIT, IMPORT_LEAF, "selectable", "unselectable", None, _DECISION),
        (_CAUSE.FILING_INSTANCE_EVIDENCE, IMPORT_LEAF, "supplied", "required", None, _DECISION),
        (_CAUSE.REVISION_DUPLICATE, IMPORT_LEAF, "new", "duplicate", None, _DECISION),
        (_CAUSE.RECONCILIATION, IMPORT_LEAF, "verifiable", "unverifiable", None, _DECISION),
        (_CAUSE.JUSTIFICANTE_ARTIFACT, IMPORT_LEAF, "stored", "unavailable", None, _DECISION),
        (_CAUSE.REGISTER_REFERENCE, IMPORT_LEAF, "consistent", "conflicting", None, _DECISION),
        (_CAUSE.SOURCE_CONSISTENCY, IMPORT_LEAF, "consistent", "inconsistent", None, _TERMINAL),
        (_CAUSE.FILING_CHAIN, IMPORT_LEAF, "consistent", "inconsistent", None, _TERMINAL),
        (_CAUSE.AUTHORITY, IMPORT_LEAF, "installed", "missing", None, _TERMINAL),
        (_CAUSE.AUDIT_TEXT, LOCAL_OBSERVATION_LEAF, "stated", "blank", None, _DECISION),
        (_CAUSE.COORDINATE, LOCAL_OBSERVATION_LEAF, "consistent", "inconsistent", None, _DECISION),
        (_CAUSE.OBSERVABLE_MODELO, LOCAL_OBSERVATION_LEAF, "observable", "refused", None, _DECISION),
        (_CAUSE.REVISION_AVAILABILITY, LOCAL_OBSERVATION_LEAF, "available", "unavailable", None, _DECISION),
        (_CAUSE.OBSERVED_VALUES, LOCAL_OBSERVATION_LEAF, "stated", "missing", None, _DECISION),
        (_CAUSE.OBSERVED_CASILLAS, LOCAL_OBSERVATION_LEAF, "accepted", "refused", None, _DECISION),
        (_CAUSE.OVERRIDE, LOCAL_OBSERVATION_LEAF, "present", "absent", None, _DECISION),
        (_CAUSE.SOURCE_FILE, LOCAL_OBSERVATION_LEAF, "readable", "unreadable", None, _DECISION),
        (_CAUSE.OBSERVATION_STORAGE, FILE_LEAF, "single_store", "split_store", None, _TERMINAL),
        (_CAUSE.RESULT_DISPOSITION, FILE_LEAF, "resolved", "unresolved", None, _TERMINAL),
    )
}
"""Every cause's declaration, keyed by cause."""


def scenario_id(cause: FilingImportRefusalCause) -> str:
    """Return the declared scenario identity of ``cause``."""
    spec = FILING_IMPORT_REFUSAL_SPECS[cause]
    return f"{spec.leaf}.{cause.value}.{spec.refused}"


def _profile(cause: FilingImportRefusalCause, spec: FilingImportRefusalSpec) -> ManifestActionProfile:
    return ManifestActionProfile(
        subject_leaf_key=spec.leaf,
        condition_id=f"{spec.leaf}.{cause.value}.{spec.sound}",
        scenario_id=scenario_id(cause),
        action=None if spec.action_id is None else ActionReference(action_id=spec.action_id),
        no_recovery_outcome=spec.outcome if spec.action_id is None else None,
    )


FILING_IMPORT_REFUSAL_PROFILES: Final[tuple[ManifestActionProfile, ...]] = tuple(
    _profile(cause, spec) for cause, spec in FILING_IMPORT_REFUSAL_SPECS.items()
)
"""The brought-in filing and local observation refusal declarations, enrolled in the Modelo precondition profiles."""

__all__ = [
    "FILE_LEAF",
    "FILING_IMPORT_REFUSAL_PROFILES",
    "FILING_IMPORT_REFUSAL_SPECS",
    "IMPORT_ACTION_ID",
    "IMPORT_LEAF",
    "LOCAL_OBSERVATION_LEAF",
    "PROFILE_EDIT_ACTION_ID",
    "FilingImportRefusalCause",
    "FilingImportRefusalSpec",
    "scenario_id",
]
