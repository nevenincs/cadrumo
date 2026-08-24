"""Application-owned profile and taxpayer precondition verdicts.

The shared CLI boundary observes profile-selection, session, and filing facts,
but it does not decide what those facts mean.  This module owns that policy:
each failed condition becomes a strict :class:`PreconditionVerdict` referencing
one canonical operator action or an explicit no-recovery outcome.

The records contain no localized text and no executable CLI strings.  Human
rendering and live command-schema projection remain entrypoint concerns.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from ..core import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
    ProfileSessionRefusalReason,
)
from .operator_actions import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
    no_action_precondition_verdict,
)


class ProfilePreconditionCondition(StrEnum):
    """Stable identities for shared profile and taxpayer preconditions."""

    ACTIVE_PROFILE_AVAILABLE = "profile.active.available"
    PROFILE_SELECTION_NONBLANK = "profile.selection.nonblank"
    PROFILE_SELECTION_KNOWN = "profile.selection.known"
    PROFILE_SELECTION_UNAMBIGUOUS = "profile.selection.unambiguous"
    PROFILE_SELECTION_LIVE = "profile.selection.live"
    SESSION_LOGGED_IN = "profile.session.logged_in"
    SESSION_CURRENT = "profile.session.current"
    SESSION_SCHEMA_CURRENT = "profile.session.schema_current"
    SESSION_WELL_FORMED = "profile.session.well_formed"
    SESSION_INTEGRITY_VALID = "profile.session.integrity_valid"
    TAX_ID_DECLARED = "taxpayer.identity.tax_id.declared"
    FORMER_PRODUCT_STATE_ABSENT = "storage.former_product_state.absent"


class ProfilePreconditionEvidence(StrEnum):
    """Stable evidence identities emitted by profile precondition policy."""

    ACTIVE_PROFILE_STATE = "profile.active.state"
    PROFILE_SELECTION = "profile.selection.resolution"
    PROFILE_SESSION = "profile.session.resume"
    TAXPAYER_IDENTITY = "taxpayer.identity.declaration"
    FORMER_PRODUCT_STATE = "storage.former_product_state.detection"


class ProfileSelectionFailure(StrEnum):
    """Application meanings for failed profile selection facts."""

    BLANK = "blank"
    UNKNOWN = "unknown"
    AMBIGUOUS = "ambiguous"
    INACTIVE = "inactive"


class FormerProductDetectionScope(StrEnum):
    """Where refusal-only former-product state was detected."""

    ROOT_PROFILE_NORMALISATION = "root_profile_normalisation"
    STARTUP = "startup"


def inspect_active_profile_precondition(
    *,
    active_profile_present: bool,
    registered_profile_count: int,
) -> PreconditionVerdict | None:
    """Return the recovery verdict when no active profile is selected."""
    if registered_profile_count < 0:
        raise ValueError("registered_profile_count cannot be negative")
    if active_profile_present:
        return None

    condition_id = ProfilePreconditionCondition.ACTIVE_PROFILE_AVAILABLE.value
    evidence = _evidence(
        condition_id=condition_id,
        evidence_id=ProfilePreconditionEvidence.ACTIVE_PROFILE_STATE.value,
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        values={
            "active_profile_present": False,
            "registered_profile_count": registered_profile_count,
        },
    )
    if registered_profile_count == 0:
        return PreconditionVerdict(
            failed_condition_id=condition_id,
            evidence=(evidence,),
            action=ActionReference(action_id="operator.profile.create"),
            argument_bindings=(_missing_argument("profile_name"),),
            missing_argument_names=("profile_name",),
            conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
        )
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(evidence,),
        action=ActionReference(action_id="operator.profile.login"),
        argument_bindings=(_missing_argument("name"),),
        missing_argument_names=("name",),
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )


def inspect_filing_taxpayer_identity_precondition(
    *,
    declared_tax_id: str,
    profile_name: str | None,
) -> PreconditionVerdict | None:
    """Return the profile-edit verdict when filing identity is undeclared."""
    if declared_tax_id:
        return None

    condition_id = ProfilePreconditionCondition.TAX_ID_DECLARED.value
    binding = _verdict_context_argument("profile_name", profile_name)
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            _evidence(
                condition_id=condition_id,
                evidence_id=ProfilePreconditionEvidence.TAXPAYER_IDENTITY.value,
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                values={
                    "declared_tax_id_present": False,
                    "missing_selector": "tax.id",
                    "profile_name_available": profile_name is not None,
                },
            ),
        ),
        action=ActionReference(action_id="operator.profile.edit"),
        argument_bindings=(binding,),
        missing_argument_names=("profile_name",) if binding.status is ActionArgumentStatus.MISSING else (),
        conditionality=(
            ActionConditionality.REQUIRES_ARGUMENTS
            if binding.status is ActionArgumentStatus.MISSING
            else ActionConditionality.IMMEDIATE
        ),
    )


def profile_selection_failure_verdict(
    failure: ProfileSelectionFailure,
    *,
    requested_profile: str,
    lifecycle_status: str | None = None,
) -> PreconditionVerdict:
    """Return the canonical outcome for one failed profile selection."""
    condition_by_failure = {
        ProfileSelectionFailure.BLANK: ProfilePreconditionCondition.PROFILE_SELECTION_NONBLANK,
        ProfileSelectionFailure.UNKNOWN: ProfilePreconditionCondition.PROFILE_SELECTION_KNOWN,
        ProfileSelectionFailure.AMBIGUOUS: ProfilePreconditionCondition.PROFILE_SELECTION_UNAMBIGUOUS,
        ProfileSelectionFailure.INACTIVE: ProfilePreconditionCondition.PROFILE_SELECTION_LIVE,
    }
    condition_id = condition_by_failure[failure].value
    values: dict[str, str | bool] = {
        "profile_selection_resolved": False,
        "requested_profile": requested_profile,
        "selection_failure": failure.value,
    }
    if lifecycle_status is not None:
        values["profile_lifecycle_status"] = lifecycle_status
    evidence = _evidence(
        condition_id=condition_id,
        evidence_id=ProfilePreconditionEvidence.PROFILE_SELECTION.value,
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        values=values,
    )

    if failure is not ProfileSelectionFailure.INACTIVE:
        return PreconditionVerdict(
            failed_condition_id=condition_id,
            evidence=(evidence,),
            action=ActionReference(action_id="operator.profile.list"),
            conditionality=ActionConditionality.IMMEDIATE,
        )

    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(evidence,),
        action=ActionReference(action_id="operator.profile.repair_clear_active"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="clear_active",
                status=ActionArgumentStatus.RESOLVED,
                value=True,
                source=ActionArgumentSource.REQUEST_CONTEXT,
                source_key="clear_active",
            ),
            ActionArgumentBinding(
                argument_name="profile",
                status=ActionArgumentStatus.RESOLVED,
                value=requested_profile,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="profile",
            ),
            _missing_argument("yes"),
        ),
        missing_argument_names=("yes",),
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )


def profile_session_failure_verdict(
    reason: ProfileSessionRefusalReason,
    *,
    profile_name: str,
) -> PreconditionVerdict:
    """Return the login action for one fail-closed session-resume outcome."""
    match reason:
        case ProfileSessionRefusalReason.ABSENT | ProfileSessionRefusalReason.KEYCHAIN_ENTRY_MISSING:
            condition = ProfilePreconditionCondition.SESSION_LOGGED_IN
        case ProfileSessionRefusalReason.EXPIRED_IDLE | ProfileSessionRefusalReason.EXPIRED_ABSOLUTE:
            condition = ProfilePreconditionCondition.SESSION_CURRENT
        case ProfileSessionRefusalReason.CUSTODY_CHANGED:
            condition = ProfilePreconditionCondition.SESSION_CURRENT
        case ProfileSessionRefusalReason.KEYRING_UNAVAILABLE:
            condition = ProfilePreconditionCondition.SESSION_LOGGED_IN
        case ProfileSessionRefusalReason.SCHEMA_VERSION_MISMATCH:
            condition = ProfilePreconditionCondition.SESSION_SCHEMA_CURRENT
        case ProfileSessionRefusalReason.MALFORMED:
            condition = ProfilePreconditionCondition.SESSION_WELL_FORMED
        case ProfileSessionRefusalReason.TAMPERED:
            condition = ProfilePreconditionCondition.SESSION_INTEGRITY_VALID

    condition_id = condition.value
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            _evidence(
                condition_id=condition_id,
                evidence_id=ProfilePreconditionEvidence.PROFILE_SESSION.value,
                provenance=ActionEvidenceProvenance.PERSISTED_STATE,
                values={
                    "profile_name": profile_name,
                    "session_resumed": False,
                    "session_refusal_reason": reason.value,
                },
            ),
        ),
        action=ActionReference(action_id="operator.profile.login"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="name",
                status=ActionArgumentStatus.RESOLVED,
                value=profile_name,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="name",
            ),
        ),
        conditionality=ActionConditionality.IMMEDIATE,
    )


def former_product_state_verdict(scope: FormerProductDetectionScope) -> PreconditionVerdict:
    """Return the safety refusal for state Cadrumo deliberately cannot adopt."""
    condition_id = ProfilePreconditionCondition.FORMER_PRODUCT_STATE_ABSENT.value
    return no_action_precondition_verdict(
        condition_id=condition_id,
        evidence_id=ProfilePreconditionEvidence.FORMER_PRODUCT_STATE.value,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        facts={"detection_scope": scope.value, "former_product_state_detected": True},
        outcome=NoRecoveryOutcome.SAFETY,
    )


def _missing_argument(argument_name: str) -> ActionArgumentBinding:
    return ActionArgumentBinding(
        argument_name=argument_name,
        status=ActionArgumentStatus.MISSING,
    )


def _verdict_context_argument(argument_name: str, value: str | None) -> ActionArgumentBinding:
    if value is None:
        return _missing_argument(argument_name)
    return ActionArgumentBinding(
        argument_name=argument_name,
        status=ActionArgumentStatus.RESOLVED,
        value=value,
        source=ActionArgumentSource.VERDICT_CONTEXT,
        source_key=argument_name,
    )


def _evidence(
    *,
    condition_id: str,
    evidence_id: str,
    provenance: ActionEvidenceProvenance,
    values: Mapping[str, str | int | bool],
) -> ConditionEvidence:
    return ConditionEvidence(
        condition_id=condition_id,
        evidence_id=evidence_id,
        provenance=provenance,
        values=values,
    )


__all__ = [
    "FormerProductDetectionScope",
    "ProfilePreconditionCondition",
    "ProfilePreconditionEvidence",
    "ProfileSelectionFailure",
    "former_product_state_verdict",
    "inspect_active_profile_precondition",
    "inspect_filing_taxpayer_identity_precondition",
    "profile_selection_failure_verdict",
    "profile_session_failure_verdict",
]
