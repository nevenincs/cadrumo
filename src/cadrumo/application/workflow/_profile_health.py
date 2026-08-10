"""Active-profile health projection shared by status, auth, and repair surfaces.

:func:`assess_active_profile_health` reads the persisted
:class:`UserProfileRecord` from the active bucket and returns an
:class:`ActiveProfileHealth` verdict used by every operator status surface.
Confirmed pointer repairs coordinate mutation through the public
:func:`~cadrumo.application.user_profile.active_profile_pointer_transaction` boundary.

See Also:
    :class:`~application.workflow.ProfileBucketPointer`
        Manifest-backed active-bucket pointer resolved before secure profile
        records are loaded.
    :mod:`application.workflow._profile_bucket_scan`
        Reads plaintext bucket manifests without opening encrypted storage.
    :class:`~application.workflow.WorkflowState`
        Supplies the active profile record through the secure workflow-state
        repository when the active bucket is readable.
    :class:`~domain.user_profile.UserProfileRecord`
        Encrypted profile facts whose completeness determines the final health
        status.
    :class:`~application.state_projection.ProjectionActiveProfile`
        Operator-state projection that carries this redacted health verdict to
        status and diagnostics surfaces.
"""

from __future__ import annotations

import tomllib
from typing import Literal

from pydantic import BaseModel, PrivateAttr, ValidationError

from ...adapters.persistence.storage import StorageValidationError
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import resolve_active_bucket_id
from ...core.config import load_settings, override_settings
from ...core.errors import CadrumoError
from ...core.logging import get_logger
from ..operator_actions import (
    ActionArgumentBinding,
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionReference,
    ConditionEvidence,
    ConditionEvidenceProvenance,
    NoRecoveryOutcome,
    PreconditionVerdict,
)
from ..profile_preconditions import inspect_active_profile_precondition
from ..user_profile import (
    active_profile_pointer_transaction,
    list_profile_key_records,
    record_to_path_values,
    validate_profile_values,
)
from ._models import WorkflowState
from ._persistence import workflow_state_repository
from ._profile_bucket_scan import list_profile_buckets, resolve_profile_bucket

ProfileHealthStatus = Literal[
    "none",
    "dangling_pointer",
    "missing_profile_record",
    "profile_record_unreadable",
    "manifest_unreadable",
    "incomplete",
    "ready",
]

ProfileSource = Literal["none", "env_override", "pointer"]


class ActiveProfileHealth(BaseModel):
    """Redacted active-profile health snapshot returned by :func:`assess_active_profile_health`.

    The active profile's label is retained privately from the manifest pointer
    that this health assessment already resolved. Projection consumers use that
    snapshot value rather than re-reading the manifest after the health verdict
    has been computed. It is deliberately not a model field: repair payloads
    continue to expose only the redacted public health contract.
    """

    model_config = _STRICT_FROZEN

    active_profile: str | None
    source: ProfileSource
    status: ProfileHealthStatus
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
        """Return the manifest label captured with this health assessment.

        This is intentionally private to Pydantic serialisation. The label is
        an in-process snapshot witness for operator projections, not a new
        repair-result field.
        """
        return self._active_profile_label

    def with_active_profile_label(self, label: str | None) -> ActiveProfileHealth:
        """Attach the manifest label captured during this health assessment."""
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

_MANIFEST_HEALTH_EXCEPTIONS = (
    OSError,
    StorageValidationError,
    ValidationError,
    tomllib.TOMLDecodeError,
    TypeError,
    ValueError,
)


def _with_active_profile_label(health: ActiveProfileHealth, label: str | None) -> ActiveProfileHealth:
    """Attach the one manifest label resolved during a health assessment.

    ``PrivateAttr`` preserves this transient witness through ``model_copy``
    while excluding it from ``model_dump`` and therefore from repair JSON.
    """
    return health.with_active_profile_label(label)


_HEALTH_CONDITIONS: dict[ProfileHealthStatus, str] = {
    "dangling_pointer": "profile.active.pointer_registered",
    "missing_profile_record": "profile.active.record_present",
    "profile_record_unreadable": "profile.active.record_readable",
    "manifest_unreadable": "profile.active.manifest_readable",
    "incomplete": "profile.configuration.complete",
}

_HEALTH_EVIDENCE_IDS: dict[ProfileHealthStatus, str] = {
    "dangling_pointer": "profile.active.pointer.health",
    "missing_profile_record": "profile.active.record.presence",
    "profile_record_unreadable": "profile.active.record.readability",
    "manifest_unreadable": "profile.active.manifest.readability",
    "incomplete": "profile.configuration.completeness",
}


def unavailable_profile_record_verdict(
    *,
    status: Literal["missing_profile_record", "profile_record_unreadable"],
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
        return _pointer_repair_verdict(condition_id=condition_id, evidence=evidence)
    return _operator_decision_verdict(condition_id=condition_id, evidence=evidence)


def _health_precondition_verdict(health: ActiveProfileHealth) -> PreconditionVerdict | None:
    """Return the one typed failed-condition outcome for a health snapshot."""
    if health.status == "ready":
        return None
    if health.status == "none":
        verdict = inspect_active_profile_precondition(
            active_profile_present=False,
            registered_profile_count=len(list_profile_buckets()),
        )
        if verdict is None:
            raise RuntimeError("inactive-profile health did not produce a precondition verdict")
        return verdict
    if health.status == "missing_profile_record":
        return unavailable_profile_record_verdict(
            status=health.status,
            source=health.source,
            repairable_by_clearing_pointer=health.repairable_by_clearing_pointer,
        )
    if health.status == "profile_record_unreadable":
        return unavailable_profile_record_verdict(
            status=health.status,
            source=health.source,
            repairable_by_clearing_pointer=health.repairable_by_clearing_pointer,
        )

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
    if health.status in {"dangling_pointer", "manifest_unreadable"}:
        if health.repairable_by_clearing_pointer:
            return _pointer_repair_verdict(condition_id=condition_id, evidence=evidence)
        return _operator_decision_verdict(condition_id=condition_id, evidence=evidence)
    if health.status == "incomplete":
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
    raise RuntimeError(f"unsupported profile health status: {health.status}")


def _health_evidence(
    *,
    condition_id: str,
    evidence_id: str,
    status: ProfileHealthStatus,
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
        provenance=ConditionEvidenceProvenance.APPLICATION_STATE,
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


def _pointer_repair_verdict(*, condition_id: str, evidence: ConditionEvidence) -> PreconditionVerdict:
    """Return the confirm-required repair action for a broken active pointer."""
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(evidence,),
        action=ActionReference(action_id="operator.profile.repair_active_pointer"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="clear_active",
                status=ActionArgumentStatus.RESOLVED,
                value=True,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="clear_active",
            ),
            ActionArgumentBinding(argument_name="yes", status=ActionArgumentStatus.MISSING),
        ),
        missing_argument_names=("yes",),
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )


def _operator_decision_verdict(*, condition_id: str, evidence: ConditionEvidence) -> PreconditionVerdict:
    """Return a terminal policy outcome when no command is honestly available."""
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(evidence,),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def _finalise_health(health: ActiveProfileHealth, *, label: str | None) -> ActiveProfileHealth:
    """Attach the snapshot label and one application-owned precondition verdict."""
    labelled = _with_active_profile_label(health, label)
    return labelled.model_copy(update={"precondition_verdict": _health_precondition_verdict(labelled)})


def assess_active_profile_health(state: WorkflowState | None = None) -> ActiveProfileHealth:
    """Return a redacted, non-secret :class:`ActiveProfileHealth` projection for the active profile."""
    settings = load_settings()
    override = (settings.cadrumo_active_profile or "").strip()
    active_profile = resolve_active_bucket_id()
    source: ProfileSource = "env_override" if override else ("pointer" if active_profile is not None else "none")
    total_keys = len(list_profile_key_records())
    if active_profile is None:
        return _finalise_health(
            ActiveProfileHealth(
                active_profile=None,
                source=source,
                status="none",
                profile_total_keys=total_keys,
            ),
            label=None,
        )

    try:
        registered_pointer = resolve_profile_bucket(active_profile)
    except _MANIFEST_HEALTH_EXCEPTIONS as exc:
        _log.debug(
            "active profile manifest unreadable bucket_id=%s",
            active_profile,
            exc_info=exc,
        )
        return _finalise_health(
            ActiveProfileHealth(
                active_profile=active_profile,
                source=source,
                status="manifest_unreadable",
                registered_bucket=True,
                profile_record_error=_compact_error(exc),
                profile_total_keys=total_keys,
                repairable_by_clearing_pointer=source == "pointer",
            ),
            label=None,
        )
    registered = registered_pointer is not None
    if not registered:
        return _finalise_health(
            ActiveProfileHealth(
                active_profile=active_profile,
                source=source,
                status="dangling_pointer",
                registered_bucket=False,
                profile_total_keys=total_keys,
                repairable_by_clearing_pointer=source == "pointer",
            ),
            label=None,
        )
    active_profile = registered_pointer.bucket_id

    try:
        with override_settings(cadrumo_active_profile=registered_pointer.bucket_id):
            resolved_state = state or workflow_state_repository().load()
    except (CadrumoError, OSError) as exc:
        # CadrumoError: decryption, session, or domain failures loading the workflow state row.
        # OSError: filesystem I/O failure reading the encrypted database file.
        return _finalise_health(
            ActiveProfileHealth(
                active_profile=active_profile,
                source=source,
                status="profile_record_unreadable",
                registered_bucket=True,
                profile_record_error=_compact_error(exc),
                profile_total_keys=total_keys,
                repairable_by_clearing_pointer=source == "pointer",
            ),
            label=registered_pointer.label,
        )
    try:
        with override_settings(cadrumo_active_profile=registered_pointer.bucket_id):
            record = resolved_state.active_profile_record()
    except (CadrumoError, ValueError) as exc:
        # CadrumoError: domain or registry failures resolving the profile record.
        # ValueError (including pydantic ValidationError): stored record fails strict validation.
        return _finalise_health(
            ActiveProfileHealth(
                active_profile=active_profile,
                source=source,
                status="profile_record_unreadable",
                registered_bucket=True,
                profile_record_error=_compact_error(exc),
                profile_total_keys=total_keys,
                repairable_by_clearing_pointer=source == "pointer",
            ),
            label=registered_pointer.label,
        )
    if record is None:
        return _finalise_health(
            ActiveProfileHealth(
                active_profile=active_profile,
                source=source,
                status="missing_profile_record",
                registered_bucket=True,
                profile_total_keys=total_keys,
                repairable_by_clearing_pointer=source == "pointer",
            ),
            label=registered_pointer.label,
        )

    values = record_to_path_values(record)
    validation = validate_profile_values(values)
    status: ProfileHealthStatus = "ready" if validation.valid else "incomplete"
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
        label=registered_pointer.label,
    )


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
    before = assess_active_profile_health_with_session()
    if not clear_active or not confirmed or not before.repairable_by_clearing_pointer:
        return ActiveProfileRepairResult(dry_run=True, cleared_pointer=False, before=before)

    root = load_settings().cadrumo_local_storage_root
    with active_profile_pointer_transaction(root) as pointer_transaction:
        before = assess_active_profile_health_with_session()
        if not before.repairable_by_clearing_pointer:
            return ActiveProfileRepairResult(dry_run=True, cleared_pointer=False, before=before)
        pointer_transaction.clear()
        after = assess_active_profile_health_with_session()
        return ActiveProfileRepairResult(
            dry_run=False,
            cleared_pointer=True,
            before=before,
            after=after,
        )


def assess_active_profile_health_with_session() -> ActiveProfileHealth:
    """Assess profile health, opening a missing active-bucket session when possible.

    Long-running processes can observe a profile that a sibling process just
    created or selected. In that case the pointer and manifest are current but
    no bucket session exists in this process yet. This projection retries only
    that explicit cold-session failure under the canonical master-key provider;
    every other degraded status remains unchanged.
    """
    before = assess_active_profile_health()
    cold_session_error = (
        "NoActiveBucketSessionError" in before.profile_record_error
        or "no active bucket session" in before.profile_record_error
    )
    if before.status != "profile_record_unreadable" or not cold_session_error:
        return before
    try:
        from ...adapters.persistence.storage import active_bucket_session_serves, get_master_key_provider

        # Resolve the target BEFORE asking about the ambient session: a session
        # bound to some other bucket does not make this profile's record
        # readable, and returning early on its mere presence reports a
        # recoverable cold-session miss as an unreadable profile record.
        registered_pointer = resolve_profile_bucket(before.active_profile or "")
        if registered_pointer is None:
            return before
        if active_bucket_session_serves(registered_pointer.bucket_id):
            return before
        with (
            override_settings(cadrumo_active_profile=registered_pointer.bucket_id),
            get_master_key_provider(),
        ):
            reassessed = assess_active_profile_health()
        updates: dict[str, object] = {"source": before.source}
        if reassessed.status in {
            "dangling_pointer",
            "missing_profile_record",
            "profile_record_unreadable",
            "manifest_unreadable",
        }:
            repairable = before.source == "pointer"
            updates["repairable_by_clearing_pointer"] = repairable
        refreshed = reassessed.model_copy(update=updates)
        return refreshed.model_copy(update={"precondition_verdict": _health_precondition_verdict(refreshed)})
    except (CadrumoError, OSError, ImportError) as exc:
        # CadrumoError: keyring/master-key domain failures.
        # OSError: filesystem-backed secret-store I/O failures.
        # ImportError: defensive guard; the dynamic import of storage internals may fail.
        return before.model_copy(
            update={
                "profile_record_error": _compact_error(exc),
                "repairable_by_clearing_pointer": False,
                "precondition_verdict": _operator_decision_verdict(
                    condition_id="profile.secret_store.available",
                    evidence=ConditionEvidence(
                        condition_id="profile.secret_store.available",
                        evidence_id="profile.secret_store.access",
                        provenance=ConditionEvidenceProvenance.RUNTIME_OBSERVATION,
                        values={
                            "profile_record_present": before.profile_record_present,
                            "profile_source": before.source,
                            "secret_store_accessible": False,
                        },
                    ),
                ),
            }
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
    "assess_active_profile_health",
    "assess_active_profile_health_with_session",
    "repair_active_profile_pointer",
    "unavailable_profile_record_verdict",
]
