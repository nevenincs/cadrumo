"""Active-profile health projection shared by status, auth, and repair surfaces.

:func:`assess_active_profile_health` reads the persisted
:class:`UserProfileRecord` from the active bucket and returns an
:class:`ActiveProfileHealth` verdict used by every operator status surface.
Confirmed pointer repairs coordinate mutation through the public
:func:`~cadrumo.application.user_profile.profile_pointer.active_profile_pointer_transaction` boundary.

See Also:
    :class:`~application.workflow.ProfileBucketPointer`
        Current committed-capsule projection resolved before secure profile
        records are loaded.
    :mod:`application.workflow.profile_bucket_scan`
        Resolves anchored current-capsule label projections without opening
        encrypted profile facts.
    :class:`~application.workflow.WorkflowState`
        Supplies the active profile record through the secure workflow-state
        repository when the active bucket is readable.
    :class:`~domain.user_profile.values.UserProfileRecord`
        Encrypted profile facts whose completeness determines the final health
        status.
    :class:`~application.state_projection.ProjectionActiveProfile`
        Operator-state projection that carries this redacted health verdict to
        status and diagnostics surfaces.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal, cast

from pydantic import BaseModel, PrivateAttr, ValidationError

from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.config import load_settings, override_settings
from ...core.errors.hierarchy import CadrumoError
from ...core.logging import get_logger
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ...core.profile_session import ProfileRecordUnavailability, ProfileSessionRefusalReason
from ..operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict
from ..operator_actions.preconditions import active_profile_pointer_repair_verdict, no_action_precondition_verdict
from ..profile_preconditions import inspect_active_profile_precondition, profile_session_failure_verdict
from ..user_profile.keys_validation import list_profile_key_records, validate_profile_values
from ..user_profile.profile_pointer import active_profile_pointer_transaction
from ..user_profile.profile_record_repository import profile_record_session_if_authenticated
from ..user_profile.projections import record_to_path_values
from .active_profile import ActiveProfileRecordResolution, resolve_active_profile_record
from .persistence import workflow_state_repository
from .profile_bucket_models import ProfileBucketPointer
from .profile_bucket_scan import list_profile_buckets, resolve_profile_bucket
from .state_models import WorkflowState


class ProfileHealthStatus(StrEnum):
    """Closed set of active-profile health verdicts.

    ``PROFILE_LOCKED`` is the ordinary benign member: the capsule is committed and its
    record is intact, and nobody has logged in, so the record is simply not knowable
    yet. It is deliberately distinct from ``MISSING_PROFILE_RECORD`` and
    ``PROFILE_RECORD_UNREADABLE``, which both assert something is WRONG with the
    record. Collapsing the three told an operator whose profile was merely locked that
    their financial records were gone.
    """

    NONE = "none"
    DANGLING_POINTER = "dangling_pointer"
    PROFILE_LOCKED = "profile_locked"
    MISSING_PROFILE_RECORD = "missing_profile_record"
    PROFILE_RECORD_UNREADABLE = "profile_record_unreadable"
    CAPSULE_UNREADABLE = "capsule_unreadable"
    INCOMPLETE = "incomplete"
    READY = "ready"


ProfileHealthStatusValue = Literal[
    ProfileHealthStatus.NONE,
    ProfileHealthStatus.DANGLING_POINTER,
    ProfileHealthStatus.PROFILE_LOCKED,
    ProfileHealthStatus.MISSING_PROFILE_RECORD,
    ProfileHealthStatus.PROFILE_RECORD_UNREADABLE,
    ProfileHealthStatus.CAPSULE_UNREADABLE,
    ProfileHealthStatus.INCOMPLETE,
    ProfileHealthStatus.READY,
]
"""The same verdicts for a strict CLI payload field."""

RECORD_FAULT_STATUSES: Final[frozenset[ProfileHealthStatus]] = frozenset(
    {
        ProfileHealthStatus.MISSING_PROFILE_RECORD,
        ProfileHealthStatus.PROFILE_RECORD_UNREADABLE,
    },
)
"""The verdicts asserting the active profile's record is WRONG.

Exactly the two the docstring above warns must never absorb ``PROFILE_LOCKED``. Written
out at three sites before this existed, so that warning was carried by prose at one site
and by three separate hand-written pairs everywhere else.
"""

UNREADABLE_PROFILE_STATUSES: Final[frozenset[ProfileHealthStatus]] = RECORD_FAULT_STATUSES | {
    ProfileHealthStatus.DANGLING_POINTER
}
"""Record faults plus a pointer that resolves to nothing.

Derived from :data:`RECORD_FAULT_STATUSES` rather than restated, so the two sets cannot
disagree about which record faults exist.
"""

type ProfileSource = Literal["none", "env_override", "pointer"]


class ActiveProfileHealth(BaseModel):
    """Redacted active-profile health snapshot returned by :func:`assess_active_profile_health`.

    The active profile's label is retained privately from the committed-capsule
    projection that this health assessment already resolved. Projection
    consumers use that snapshot value rather than re-reading discovery state
    after the health verdict has been computed. It is deliberately not a model
    field: repair payloads continue to expose only the redacted public health
    contract.
    """

    model_config = _STRICT_FROZEN

    active_profile: str | None
    source: ProfileSource
    status: ProfileHealthStatusValue
    registered_bucket: bool = False
    profile_record_present: bool = False
    profile_record_error: str = ""
    profile_present_keys: int = 0
    profile_total_keys: int = 0
    missing_required: tuple[str, ...] = ()
    repairable_by_clearing_pointer: bool = False
    precondition_verdict: PreconditionVerdict | None = None

    _active_profile_label: str | None = PrivateAttr(default=None)

    @property
    def active_profile_label(self) -> str | None:
        """Return the committed-capsule label captured with this health assessment.

        This is intentionally private to Pydantic serialisation. The label is
        an in-process snapshot witness for operator projections, not a new
        repair-result field.
        """
        return self._active_profile_label

    def with_active_profile_label(self, label: str | None) -> ActiveProfileHealth:
        """Attach the committed-capsule label captured during this health assessment."""
        self._active_profile_label = label
        return self


class ActiveProfileRepairResult(BaseModel):
    """Result of a safe active-profile pointer repair probe/action."""

    model_config = _STRICT_FROZEN

    dry_run: bool
    cleared_pointer: bool
    before: ActiveProfileHealth
    after: ActiveProfileHealth | None = None


_log = get_logger(__name__)

_CAPSULE_DISCOVERY_EXCEPTIONS = (
    OSError,
    ValidationError,
    TypeError,
    ValueError,
)


def _with_active_profile_label(health: ActiveProfileHealth, label: str | None) -> ActiveProfileHealth:
    """Attach the one committed-capsule label resolved during a health assessment.

    ``PrivateAttr`` preserves this transient witness through ``model_copy``
    while excluding it from ``model_dump`` and therefore from repair JSON.
    """
    return health.with_active_profile_label(label)


_HEALTH_CONDITIONS: dict[ProfileHealthStatus, str] = {
    ProfileHealthStatus.DANGLING_POINTER: "profile.active.pointer_registered",
    ProfileHealthStatus.MISSING_PROFILE_RECORD: "profile.active.record_present",
    ProfileHealthStatus.PROFILE_RECORD_UNREADABLE: "profile.active.record_readable",
    ProfileHealthStatus.CAPSULE_UNREADABLE: "profile.active.capsule_readable",
    ProfileHealthStatus.INCOMPLETE: "profile.configuration.complete",
}

_HEALTH_EVIDENCE_IDS: dict[ProfileHealthStatus, str] = {
    ProfileHealthStatus.DANGLING_POINTER: "profile.active.pointer.health",
    ProfileHealthStatus.MISSING_PROFILE_RECORD: "profile.active.record.presence",
    ProfileHealthStatus.PROFILE_RECORD_UNREADABLE: "profile.active.record.readability",
    ProfileHealthStatus.CAPSULE_UNREADABLE: "profile.active.capsule.readability",
    ProfileHealthStatus.INCOMPLETE: "profile.configuration.completeness",
}

#: Health status carried by each reason the active-profile record did not resolve.
#: Only a selector with no committed capsule is an ABSENT record; a locked
#: profile is benign and a mis-addressed session is a readability failure.
_UNAVAILABILITY_STATUSES: dict[ProfileRecordUnavailability, ProfileHealthStatus] = {
    ProfileRecordUnavailability.NO_LIVE_CAPSULE: ProfileHealthStatus.MISSING_PROFILE_RECORD,
    ProfileRecordUnavailability.SESSION_REQUIRED: ProfileHealthStatus.PROFILE_LOCKED,
    ProfileRecordUnavailability.SESSION_IDENTITY_MISMATCH: ProfileHealthStatus.PROFILE_RECORD_UNREADABLE,
}


def unavailable_profile_record_verdict(
    *,
    status: Literal[
        ProfileHealthStatus.MISSING_PROFILE_RECORD,
        ProfileHealthStatus.PROFILE_RECORD_UNREADABLE,
    ],
    source: ProfileSource,
    repairable_by_clearing_pointer: bool,
) -> PreconditionVerdict:
    """Classify an unreadable or absent profile record without CLI recovery prose.

    A pointer-backed broken active profile has one safe local recovery: clear
    that pointer after the operator supplies confirmation. An explicit profile
    override, or a non-active record being inspected, has no command we can
    honestly materialise from the observed facts, so it carries an explicit
    ``operator_decision`` outcome instead.
    """
    condition_id = _HEALTH_CONDITIONS[status]
    evidence = _health_evidence(
        condition_id=condition_id,
        evidence_id=_HEALTH_EVIDENCE_IDS[status],
        status=status,
        source=source,
        registered_bucket=True,
        profile_record_present=False,
        repairable_by_clearing_pointer=repairable_by_clearing_pointer,
    )
    if repairable_by_clearing_pointer:
        return active_profile_pointer_repair_verdict(
            condition_id=condition_id,
            evidence_id=evidence.evidence_id,
            facts=evidence.values,
            provenance=evidence.provenance,
        )
    return _operator_decision_verdict(condition_id=condition_id, evidence=evidence)


def _health_precondition_verdict(health: ActiveProfileHealth) -> PreconditionVerdict | None:
    """Return the one typed failed-condition outcome for a health snapshot."""
    if health.status == "ready":
        return None
    if health.status == "none":
        return _inactive_profile_precondition_verdict()
    if health.status == "profile_locked":
        return _locked_profile_precondition_verdict(health)
    if health.status in {"missing_profile_record", "profile_record_unreadable"}:
        return _unavailable_profile_precondition_verdict(health)

    return _degraded_profile_precondition_verdict(health)


def _inactive_profile_precondition_verdict() -> PreconditionVerdict:
    """Build the registration/login outcome for an unselected profile."""
    verdict = inspect_active_profile_precondition(
        active_profile_present=False,
        registered_profile_count=len(list_profile_buckets()),
    )
    if verdict is None:
        raise RuntimeError("inactive-profile health did not produce a precondition verdict")
    return verdict


def _locked_profile_precondition_verdict(health: ActiveProfileHealth) -> PreconditionVerdict:
    """Route a benign locked capsule to login using its committed label."""
    label = health.active_profile_label
    if label is None:
        raise RuntimeError("a locked active profile has no committed-capsule label to route its login")
    return profile_session_failure_verdict(ProfileSessionRefusalReason.ABSENT, profile_name=label)


def _unavailable_profile_precondition_verdict(health: ActiveProfileHealth) -> PreconditionVerdict:
    """Build the typed outcome for one of the two unavailable-record statuses."""
    status = cast(
        Literal[
            ProfileHealthStatus.MISSING_PROFILE_RECORD,
            ProfileHealthStatus.PROFILE_RECORD_UNREADABLE,
        ],
        health.status,
    )
    return unavailable_profile_record_verdict(
        status=status,
        source=health.source,
        repairable_by_clearing_pointer=health.repairable_by_clearing_pointer,
    )


def _degraded_profile_precondition_verdict(health: ActiveProfileHealth) -> PreconditionVerdict:
    """Build evidence and recovery policy for a degraded active-profile health state."""
    condition_id = _HEALTH_CONDITIONS[health.status]
    evidence = _health_evidence(
        condition_id=condition_id,
        evidence_id=_HEALTH_EVIDENCE_IDS[health.status],
        status=health.status,
        source=health.source,
        registered_bucket=health.registered_bucket,
        profile_record_present=health.profile_record_present,
        repairable_by_clearing_pointer=health.repairable_by_clearing_pointer,
        profile_present_keys=health.profile_present_keys,
        profile_total_keys=health.profile_total_keys,
        missing_required_count=len(health.missing_required),
    )
    if health.status in {"dangling_pointer", "capsule_unreadable"}:
        return _pointer_health_precondition_verdict(health, condition_id=condition_id, evidence=evidence)
    if health.status == "incomplete":
        return _incomplete_profile_precondition_verdict(health, condition_id=condition_id, evidence=evidence)
    raise RuntimeError(f"unsupported profile health status: {health.status}")


def _pointer_health_precondition_verdict(
    health: ActiveProfileHealth,
    *,
    condition_id: str,
    evidence: ConditionEvidence,
) -> PreconditionVerdict:
    """Choose pointer repair or operator decision for a degraded capsule."""
    if not health.repairable_by_clearing_pointer:
        return _operator_decision_verdict(condition_id=condition_id, evidence=evidence)
    return active_profile_pointer_repair_verdict(
        condition_id=condition_id,
        evidence_id=evidence.evidence_id,
        facts=evidence.values,
        provenance=evidence.provenance,
    )


def _incomplete_profile_precondition_verdict(
    health: ActiveProfileHealth,
    *,
    condition_id: str,
    evidence: ConditionEvidence,
) -> PreconditionVerdict:
    """Offer profile editing only when the committed label can be addressed."""
    profile_name = health.active_profile_label
    if profile_name is None:
        return _operator_decision_verdict(condition_id=condition_id, evidence=evidence)
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(evidence,),
        action=ActionReference(action_id="operator.profile.edit"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="profile_name",
                status=ActionArgumentStatus.RESOLVED,
                value=profile_name,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="profile_name",
            ),
        ),
        conditionality=ActionConditionality.IMMEDIATE,
    )


def _health_evidence(
    *,
    condition_id: str,
    evidence_id: str,
    status: ProfileHealthStatusValue,
    source: ProfileSource,
    registered_bucket: bool,
    profile_record_present: bool,
    repairable_by_clearing_pointer: bool,
    profile_present_keys: int = 0,
    profile_total_keys: int = 0,
    missing_required_count: int = 0,
) -> ConditionEvidence:
    """Build non-secret, non-identity evidence for one health condition."""
    return ConditionEvidence(
        condition_id=condition_id,
        evidence_id=evidence_id,
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        values={
            "health_status": status,
            "profile_present_keys": profile_present_keys,
            "profile_record_present": profile_record_present,
            "profile_source": source,
            "profile_total_keys": profile_total_keys,
            "registered_bucket": registered_bucket,
            "repairable_by_clearing_pointer": repairable_by_clearing_pointer,
            "required_fields_missing_count": missing_required_count,
        },
    )


def _operator_decision_verdict(*, condition_id: str, evidence: ConditionEvidence) -> PreconditionVerdict:
    """Return a terminal policy outcome when no command is honestly available."""
    return no_action_precondition_verdict(
        condition_id=condition_id,
        evidence_id=evidence.evidence_id,
        facts=evidence.values,
        provenance=evidence.provenance,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def _finalise_health(health: ActiveProfileHealth, *, label: str | None) -> ActiveProfileHealth:
    """Attach the snapshot label and one application-owned precondition verdict."""
    labelled = _with_active_profile_label(health, label)
    return labelled.model_copy(update={"precondition_verdict": _health_precondition_verdict(labelled)})


def _capsule_unreadable_health(
    *,
    active_profile: str | None,
    source: ProfileSource,
    total_keys: int,
    error: Exception,
    registered_bucket: bool = False,
    repairable_by_clearing_pointer: bool = False,
    label: str | None = None,
) -> ActiveProfileHealth:
    """Project a capsule-discovery failure without opening secure state."""
    return _finalise_health(
        ActiveProfileHealth(
            active_profile=active_profile,
            source=source,
            status=ProfileHealthStatus.CAPSULE_UNREADABLE,
            registered_bucket=registered_bucket,
            profile_record_error=_compact_error(error),
            profile_total_keys=total_keys,
            repairable_by_clearing_pointer=repairable_by_clearing_pointer,
        ),
        label=label,
    )


def _profile_record_unreadable_health(
    *,
    active_profile: str,
    source: ProfileSource,
    total_keys: int,
    label: str,
    error: Exception,
) -> ActiveProfileHealth:
    """Project a secure workflow/profile-record read failure as unreadable."""
    return _finalise_health(
        ActiveProfileHealth(
            active_profile=active_profile,
            source=source,
            status=ProfileHealthStatus.PROFILE_RECORD_UNREADABLE,
            registered_bucket=True,
            profile_record_error=_compact_error(error),
            profile_total_keys=total_keys,
            repairable_by_clearing_pointer=source == "pointer",
        ),
        label=label,
    )


def _assess_without_active_profile(source: ProfileSource, total_keys: int) -> ActiveProfileHealth:
    """Assess current capsule discovery when no profile selector is active."""
    try:
        len(list_profile_buckets())
    except _CAPSULE_DISCOVERY_EXCEPTIONS as exc:
        _log.debug("current capsule discovery unreadable without an active pointer", exc_info=exc)
        return _capsule_unreadable_health(
            active_profile=None,
            source=source,
            total_keys=total_keys,
            error=exc,
        )
    return _finalise_health(
        ActiveProfileHealth(
            active_profile=None,
            source=source,
            status=ProfileHealthStatus.NONE,
            profile_total_keys=total_keys,
        ),
        label=None,
    )


def _assess_selected_profile(
    identifier: str,
    source: ProfileSource,
    total_keys: int,
    state: WorkflowState | None,
) -> ActiveProfileHealth:
    """Resolve one selected profile through its committed capsule and record."""
    try:
        registered_pointer = resolve_profile_bucket(identifier)
    except _CAPSULE_DISCOVERY_EXCEPTIONS as exc:
        _log.debug(
            "active profile current capsule unreadable bucket_id=%s",
            identifier,
            exc_info=exc,
        )
        return _capsule_unreadable_health(
            active_profile=identifier,
            source=source,
            total_keys=total_keys,
            error=exc,
            registered_bucket=True,
            repairable_by_clearing_pointer=source == "pointer",
        )
    if registered_pointer is None:
        return _finalise_health(
            ActiveProfileHealth(
                active_profile=identifier,
                source=source,
                status=ProfileHealthStatus.DANGLING_POINTER,
                registered_bucket=False,
                profile_total_keys=total_keys,
                repairable_by_clearing_pointer=source == "pointer",
            ),
            label=None,
        )
    return _assess_registered_profile(registered_pointer, source, total_keys, state)


def _profile_record_session_is_missing(bucket_id: str) -> bool:
    """Probe custody before encrypted workflow access so locked stays benign."""
    with override_settings(cadrumo_active_profile=bucket_id):
        return profile_record_session_if_authenticated(bucket_id) is None


def _load_workflow_state_for_health(bucket_id: str, state: WorkflowState | None) -> None:
    """Open workflow state only when the caller did not already supply it."""
    if state is not None:
        return
    # Asked BEFORE the encrypted workflow state is opened. That store is locked
    # by the very session this is probing for, so loading it first refuses with
    # a storage error and reports a benign locked profile as an unreadable one
    # -- the same lie in a different spelling.
    with override_settings(cadrumo_active_profile=bucket_id):
        workflow_state_repository().load()


def _health_from_record_resolution(
    resolution: ActiveProfileRecordResolution,
    *,
    active_profile: str,
    source: ProfileSource,
    total_keys: int,
    label: str,
) -> ActiveProfileHealth:
    """Translate a resolved profile record or its typed unavailability reason."""
    record = resolution.record
    if record is None:
        # The reason travels with the absence, so each one reaches the operator
        # as itself. A session that vanished between the probe above and this
        # read lands here as a lock rather than as a missing record, and a lock
        # is not a broken pointer, so it offers no pointer repair.
        unavailability = resolution.unavailability
        if unavailability is None:
            raise RuntimeError("an absent profile record must carry the reason it is unavailable")
        locked = unavailability is ProfileRecordUnavailability.SESSION_REQUIRED
        return _finalise_health(
            ActiveProfileHealth(
                active_profile=active_profile,
                source=source,
                status=_UNAVAILABILITY_STATUSES[unavailability],
                registered_bucket=True,
                profile_total_keys=total_keys,
                repairable_by_clearing_pointer=source == "pointer" and not locked,
            ),
            label=label,
        )

    values = record_to_path_values(record)
    validation = validate_profile_values(values)
    status: ProfileHealthStatusValue = ProfileHealthStatus.READY if validation.valid else ProfileHealthStatus.INCOMPLETE
    return _finalise_health(
        ActiveProfileHealth(
            active_profile=active_profile,
            source=source,
            status=status,
            registered_bucket=True,
            profile_record_present=True,
            profile_present_keys=validation.present_keys,
            profile_total_keys=validation.total_keys,
            missing_required=validation.missing_required,
        ),
        label=label,
    )


def _assess_registered_profile(
    pointer: ProfileBucketPointer,
    source: ProfileSource,
    total_keys: int,
    state: WorkflowState | None,
) -> ActiveProfileHealth:
    """Assess the committed profile after discovery has established its identity."""
    active_profile = pointer.bucket_id
    if _profile_record_session_is_missing(active_profile):
        return _finalise_health(
            ActiveProfileHealth(
                active_profile=active_profile,
                source=source,
                status=ProfileHealthStatus.PROFILE_LOCKED,
                registered_bucket=True,
                profile_total_keys=total_keys,
            ),
            label=pointer.label,
        )

    try:
        _load_workflow_state_for_health(active_profile, state)
    except (CadrumoError, OSError) as exc:
        # CadrumoError: decryption, session, or domain failures loading the workflow state row.
        # OSError: filesystem I/O failure reading the encrypted database file.
        return _profile_record_unreadable_health(
            active_profile=active_profile,
            source=source,
            total_keys=total_keys,
            label=pointer.label,
            error=exc,
        )
    try:
        with override_settings(cadrumo_active_profile=active_profile):
            resolution = resolve_active_profile_record()
    except (CadrumoError, ValueError) as exc:
        # CadrumoError: domain or registry failures resolving the profile record.
        # ValueError (including pydantic ValidationError): stored record fails strict validation.
        return _profile_record_unreadable_health(
            active_profile=active_profile,
            source=source,
            total_keys=total_keys,
            label=pointer.label,
            error=exc,
        )
    return _health_from_record_resolution(
        resolution,
        active_profile=active_profile,
        source=source,
        total_keys=total_keys,
        label=pointer.label,
    )


def assess_active_profile_health(state: WorkflowState | None = None) -> ActiveProfileHealth:
    """Return a redacted, non-secret projection from current authenticated state.

    This is an observation boundary: it reads only the already-bound current
    profile-record or custody session; health assessment never unlocks a
    capsule or constructs a credential provider.

    An absent session is reported as ``profile_locked`` and routed to the
    login action for the capsule's own label. It is NOT an absent or unreadable
    record: the capsule is committed and the record is intact, and nothing
    about that record is knowable until someone logs in. Whether a record is
    genuinely gone is answered by the capsule projection above, which still
    refuses a selector with no committed capsule as ``dangling_pointer``, so
    real data loss keeps its own verdict rather than hiding behind the benign
    one.
    """
    settings = load_settings()
    override = (settings.cadrumo_active_profile or "").strip()
    active_profile = resolve_active_bucket_id()
    source: ProfileSource = "env_override" if override else ("pointer" if active_profile is not None else "none")
    total_keys = len(list_profile_key_records())
    if active_profile is None:
        return _assess_without_active_profile(source, total_keys)
    return _assess_selected_profile(active_profile, source, total_keys, state)


def repair_active_profile_pointer(*, clear_active: bool, confirmed: bool) -> ActiveProfileRepairResult:
    """Clear an eligible degraded pointer-file active profile after locked reassessment.

    The preliminary best-effort probe keeps cold, unconfirmed, and ineligible
    calls read-only. A confirmed repair candidate acquires the bounded pointer
    transaction, then performs an authoritative locked reassessment whose
    ``repairable_by_clearing_pointer`` flag is the sole eligibility authority.
    The returned ``before`` is that locked reassessment, and ``after`` is
    measured before releasing the transaction. Lock contention propagates
    without pointer mutation.
    """
    before = assess_active_profile_health()
    if not clear_active or not confirmed or not before.repairable_by_clearing_pointer:
        return ActiveProfileRepairResult(dry_run=True, cleared_pointer=False, before=before)

    root = load_settings().cadrumo_local_storage_root
    with active_profile_pointer_transaction(root) as pointer_transaction:
        before = assess_active_profile_health()
        if not before.repairable_by_clearing_pointer:
            return ActiveProfileRepairResult(dry_run=True, cleared_pointer=False, before=before)
        pointer_transaction.clear()
        after = assess_active_profile_health()
        return ActiveProfileRepairResult(
            dry_run=False,
            cleared_pointer=True,
            before=before,
            after=after,
        )


def _compact_error(exc: Exception) -> str:
    """Return a one-line diagnostic without SQL payload noise."""
    root = getattr(exc, "orig", None)
    if isinstance(root, Exception):
        exc = root
    message = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
    return f"{type(exc).__name__}: {message}"


__all__ = [
    "ActiveProfileHealth",
    "ActiveProfileRepairResult",
    "ProfileHealthStatus",
    "ProfileSource",
    "assess_active_profile_health",
    "repair_active_profile_pointer",
    "unavailable_profile_record_verdict",
]
