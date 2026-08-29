"""Typed ``--json`` payload schemas for core config CLI commands.

Every graph-declared class is a strict :class:`OutputSchema` transport shape for a
config command result. Field sets match the production emit sites in
:mod:`_config` and its submodules; sequence fields use ``list`` so JSON-mode
pydantic dumps stay arrays. Application services remain authoritative for
profile, auth, apoderado, repair, diagnostics, and workflow semantics.

A few keys here declare a schema for a verb the tree does not expose. Those are
not oversights: each is listed in
:data:`~cadrumo.entrypoints.cli._verb_input_schema.DECLARED_UNIMPLEMENTED_SURFACES`
with the reason it is held, because deleting the declaration would erase the only
visible evidence that a capability lost its door. A declaration with no verb and
no entry there is residue and should go.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import ConfigDict, Field, NonNegativeInt, field_validator, model_validator

from ...application.auth.catalogue import AuthProviderListing
from ...application.auth.diagnostics import AuthDiagnosticDetail, AuthDiagnosticPhoneState, AuthDiagnosticSummary
from ...application.auth.operator_results import AuthLoginResult, AuthStatusResult, AuthTestResult
from ...application.auth.probes import ProviderProbeResult
from ...application.bucket_maintenance import BucketDeletionFingerprint
from ...application.config_reset import (
    ConfigResetOperationStatus,
    ConfigResetPauseReason,
    ConfigResetTargetPhase,
)
from ...application.user_profile.aggregate import ProfileRestoreAuthority
from ...application.user_profile.bundle_export_contracts import ProfileBundleExportPurpose, ProfileBundleExportTransport
from ...application.workflow.profile_health import ProfileHealthStatus, ProfileSource
from ...core import Hex64Str
from ...core.errors import BaseSeverity
from ...core.identity import BucketId, ProfileId, ProfileLabel
from ...core.json_contract import OutputSchema, ResolvedPreconditionAction
from ...core.text_bounds import NonEmptyStr, PositiveCount
from ...core.time import validate_utc_aware
from ...domain.auth.apoderamientos.catalogue import ApoderadoScopeCode, ApoderadoScopeName
from ...domain.user_profile.values import ProfileSetupState

# The two wizard-owned profile result schemas are deferred public targets owned
# by their production CommandSpec declarations, NOT here: the `config` group imports this
# module at group-resolution time, so importing the wizard from here would pull
# its whole dependency tail into every `config` verb and redden the cold-start
# guard.

if TYPE_CHECKING:
    from ...application.auth.operator_results import AuthConfigureResult
    from ...application.config_reset import ConfigResetOperation

# Shared nested models (not direct CommandSpec schema targets)


class QuarantineNamespacePayload(OutputSchema):
    """One secure-object namespace row in a repair quarantine report.

    Projects the per-namespace counts carried by
    :class:`SecureObjectIntegrityReport` and its
    secure-object integrity rows.  It reports only namespace and
    decryptability counts; object keys, ciphertext, plaintext payload bytes,
    taxpayer identifiers, and bucket identifiers stay out of the CLI payload.
    """

    namespace: str
    readable: int
    unreadable: int


class WorkflowFingerprintPayload(OutputSchema):
    """Metadata fingerprint for encrypted workflow progress state.

    Projects :class:`WorkflowStateResetFingerprint`
    for ``config repair reset-progress`` at the same bounds the canonical
    record enforces: a schema version of at least 1, a non-negative byte
    length, an aware ``written_at`` timestamp, and a non-empty, length-bounded
    ``reason_class``. Identifies the stored envelope's schema, write time,
    byte length, read-status reason, and recoverable bucket context without
    serialising the :class:`WorkflowState` plaintext.
    """

    schema_version: int | None = Field(default=None, ge=1)
    written_at: datetime | None = None
    byte_length: NonNegativeInt | None = None
    reason_class: str = Field(min_length=1, max_length=64)
    recovered_bucket_id: BucketId | None = None


class ProfileIssuePayload(OutputSchema):
    """One validation issue from :class:`ProfileValidationService`.

    The payload mirrors
    :class:`ProfileValidationIssue` as plain JSON
    so ``profile view`` and ``profile validate`` expose the same readiness
    diagnostics without importing domain records into the CLI layer.
    """

    severity: BaseSeverity
    code: str
    path: str | None = None
    message: str


class ProfileFactPayload(OutputSchema):
    """One schema-backed fact key/value pair in ``config profile view``.

    Values are the operator-display projection of profile facts, not the
    encrypted :class:`UserProfileRecord` itself.
    """

    path: str
    value: str


# P05 — repair verb result schemas


class ConfigRepairRegistryPayload(OutputSchema):
    """JSON-safe projection of the config-repair registry summary."""

    available: bool
    registry_root: str
    modelo_count: int
    revision_count: int
    casilla_count: int
    formula_count: int
    revision_ids: list[str]
    error: str | None = None


class ConfigRepairSetupPayload(OutputSchema):
    """JSON-safe projection of the active-profile readiness summary."""

    active_profile: str | None
    profile_ready: bool
    identity_ready: bool
    enrolment_ready: bool
    missing_required: list[str]
    missing_enrolment: list[str]
    profile_present_keys: NonNegativeInt
    profile_total_keys: NonNegativeInt
    auth_provider: str
    login_ready: bool


class ConfigRepairNamespacePayload(OutputSchema):
    """One secure-object namespace row in the config-repair report."""

    namespace: NonEmptyStr
    readable: NonNegativeInt
    unreadable: NonNegativeInt


class ConfigRepairSecureObjectsPayload(OutputSchema):
    """JSON-safe projection of secure-object integrity totals."""

    namespaces: list[ConfigRepairNamespacePayload]
    readable_total: NonNegativeInt
    unreadable_total: NonNegativeInt


class ConfigRepairFindingPayload(OutputSchema):
    """One concrete explanatory finding nested in a repair check."""

    summary: str
    detail: str | None = None
    requirement: Literal["required", "optional"] | None = None


class ConfigRepairCheckPayload(OutputSchema):
    """JSON-safe projection of one actionable config-repair check."""

    name: str
    status: Literal["ok", "warn", "fail"]
    summary: str
    detail: str | None = None
    precondition_action: ResolvedPreconditionAction | None = None
    audience: Literal["operator", "internal"]
    findings: list[ConfigRepairFindingPayload]


class ConfigRepairResult(OutputSchema):
    """JSON envelope for the composite ``aeat config repair`` report.

    The application diagnostics service owns the nested registry, setup,
    secure-object, and check records. This transport schema fixes the report's
    top-level contract while preserving those already validated nested DTOs.
    """

    overall: Literal["ok", "warn", "fail"]
    package_name: str
    package_version: str
    python_version: str
    log_file: str
    registry: ConfigRepairRegistryPayload
    setup: ConfigRepairSetupPayload | None
    secure_objects: ConfigRepairSecureObjectsPayload
    checks: list[ConfigRepairCheckPayload]


class RepairLogsResult(OutputSchema):
    """JSON envelope for ``aeat config repair logs``.

    The payload is a bounded log-tail view: ``path`` identifies the log file
    rendered to the operator and ``lines`` contains the selected text lines.
    """

    path: str
    lines: list[str]


class RepairQuarantineResult(OutputSchema):
    """JSON envelope for ``aeat config repair quarantine``.

    Covers the no-active-profile guard, the dry-run preview path, and
    the confirmed quarantine path.  Dry-run rows come from
    :func:`preview_quarantine_unreadable_secure_objects`
    and mutate nothing; confirmed rows come from
    :func:`quarantine_unreadable_secure_objects`.
    Both branches expose aggregate
    :class:`QuarantineNamespacePayload`
    counts
    rather than secure-object payload material.
    """

    dry_run: bool
    # No-active-profile branch
    quarantined: int | None = None
    retained: int | None = None
    reason: str | None = None
    # Preview/live branches (from the quarantine report model)
    unreadable_total: int | None = None
    readable_total: int | None = None
    namespaces: list[QuarantineNamespacePayload] | None = None
    # would_quarantine / would_retain are aliases on the preview branch
    # These are derived by the display layer; the JSON payload carries
    # unreadable_total / readable_total from the report directly.


class RepairResetProgressResult(OutputSchema):
    """JSON envelope for ``aeat config repair reset-progress``.

    Covers the no-active-profile guard, the dry-run preview path, and
    the confirmed reset path.  Dry-run calls
    :func:`fingerprint_workflow_state`; confirmed
    reset calls :func:`reset_workflow_state`.  The
    optional
    :class:`WorkflowFingerprintPayload`
    is a metadata summary of the
    encrypted progress envelope, not the saved workflow contents.
    """

    # No-active-profile branch
    reset: bool | None = None
    reason: str | None = None
    # Dry-run / live branches
    dry_run: bool | None = None
    fingerprint: WorkflowFingerprintPayload | None = None


class RepairConnectivityResult(OutputSchema):
    """Read-only connectivity probe result for ``aeat config repair connectivity``.

    Wraps the browser/Sede status produced by
    :func:`probe_browser_connectivity` for the
    :class:`SchemaEnvelope` surface.  The
    command reports adapter health only; it does not authenticate, file, or
    mutate local configuration.
    """

    target: str
    status: dict[str, object]


# P06 — config and profile verb result schemas


class ConfigLoginResult(OutputSchema):
    """JSON envelope for ``aeat config login``.

    Reports the authenticated profile's immutable identity, its operator
    label and the two session deadlines. ``session_persisted`` is ``False`` on a host with no
    usable OS keychain, where the login is process-scoped only.
    ``already_authenticated`` marks the idempotent no-op that resumed a
    still-valid session without re-prompting, and
    ``closed_previous_profile`` names the profile a cross-profile handover
    signed out. No passphrase, key material, or session-key bytes enter
    this payload.
    """

    profile_id: BucketId
    active_profile: str
    authenticated_at: datetime
    idle_deadline: datetime
    absolute_deadline: datetime
    session_persisted: bool
    already_authenticated: bool
    closed_previous_profile: str | None = None


class ConfigPassphraseChangeResult(OutputSchema):
    """Non-secret outcome of one active-profile passphrase rotation."""

    profile_id: BucketId
    changed: bool
    password_generation: int = Field(ge=2)
    dek_epoch_preserved: bool
    recovery_enrollment_retained: bool


class ConfigProfileArchiveExportResult(OutputSchema):
    """JSON envelope for ``aeat config profile archive export``.

    Reports one sealed backup written to disk.

    ``recovery_enrolled`` is reported to the operator who asked for the backup
    and is deliberately NOT inferable from the archive file: the recovery slot
    is constant-width whether or not the profile enrolled, so someone holding a
    copy cannot learn it. Telling the requester is safe; publishing it in the
    bytes would not be.

    No password, recovery phrase, key material or label enters this payload.
    """

    bucket_id: BucketId
    target: str
    archive_schema_version: int
    recovery_enrolled: bool


class ConfigProfileArchiveInspectResult(OutputSchema):
    """JSON envelope for ``aeat config profile archive inspect``.

    Exactly the archive's plaintext header, which is what anyone holding the
    file can read without a key. Nothing may be added here that is a fact about
    the OPERATOR rather than about the archive -- the label is absent for that
    reason, not by oversight.

    ``manifest_digest`` is carried by the header and verified by the reader at
    the application layer, not by the archive transport, which treats its
    payload as opaque bytes.
    """

    product: str
    bucket_id: BucketId
    archive_schema_version: int
    created_at: datetime
    manifest_digest: str


class ConfigProfileArchiveImportResult(OutputSchema):
    """JSON envelope for ``aeat config profile archive import``.

    Reports one completed restore of a capsule the operator held on disk.

    ``authority`` names which door proved the key rather than leaving it
    implicit in which flags were passed, so a caller reading a stored envelope
    later can tell a password restore from a recovery-artifact one.

    ``recovery_enrolled`` is reported on every restore because a restore IS a
    publication, and publication is the only moment a recovery wrapper can be
    installed. A restored profile carrying ``false`` has permanently lost its
    second door, and an operator who is not told cannot act on it.

    ``password_unchanged`` is the recovery door's honest limit: that door
    republishes the capsule under its EXISTING password envelope, so it
    recovers the records without recovering the credential. It is a field
    rather than only a notice so a machine caller can branch on it.

    No password, recovery phrase, key material or wrapper bytes enter this
    payload.
    """

    profile_id: ProfileId
    label: str
    authority: ProfileRestoreAuthority
    recovery_enrolled: bool
    password_unchanged: bool


class ConfigLogoutResult(OutputSchema):
    """JSON envelope for ``aeat config logout``.

    Reports which profile the strong close signed out, or ``None`` when
    nothing was signed in. ``already_logged_out`` marks that idempotent
    no-op, so a retry is distinguishable from a first close without
    parsing prose.
    """

    logged_out_profile: str | None = None
    already_logged_out: bool


class ConfigProfileViewResult(OutputSchema):
    """JSON envelope for ``aeat config profile view``.

    Covers the missing-record branch, the unreadable-record branch, and
    the success path. Optional fields accommodate each branch. Successful rows
    project :class:`UserProfileRecord` facts through
    :class:`ProfileFactPayload`, bounded exactly as the canonical record's
    ``profile_id`` / ``setup_state`` / ``schema_version``. Failures report
    pointer and record readiness without dumping encrypted profile contents;
    ``status`` is reserved for the readiness-branch
    ``profile_record_unreadable`` sentinel.
    """

    profile_id: ProfileId | None = None
    display_name: ProfileLabel | None = None
    setup_state: ProfileSetupState | None = None
    status: Literal["profile_record_unreadable"] | None = None
    valid: bool | None = None
    schema_version: int | None = Field(default=None, ge=1)
    issues: list[ProfileIssuePayload] | None = None
    facts: list[ProfileFactPayload] | None = None
    # Error / readiness branches
    registered_bucket: bool | None = None
    profile_record_present: bool | None = None
    configured: bool | None = None
    error: str | None = None
    precondition_action: ResolvedPreconditionAction | None = None
    bucket_id: BucketId | None = None
    # Readiness / repair branches (raised when profile record cannot be loaded).
    readiness: str | None = None
    profile_record: str | None = None


class ConfigProfileAddRowResult(OutputSchema):
    """Result of one application-owned repeatable profile-row mutation."""

    profile_id: ProfileId
    section: NonEmptyStr
    row_index: NonNegativeInt
    record_revision: PositiveCount
    content_digest: NonEmptyStr


class ConfigProfileValidateResult(OutputSchema):
    """JSON envelope for ``aeat config profile validate``.

    Report-only surface: same
    :class:`ProfileValidationService` outcome
    that ``aeat config profile view`` exposes inline, but as the primary
    payload with no fact dump so the operator can audit a profile's schema
    conformance independent of its data view. Exit code is ``0`` when no
    blocking issues exist and ``2`` when any error-severity issue surfaces.
    """

    profile_id: ProfileId
    display_name: ProfileLabel
    setup_state: ProfileSetupState
    valid: bool
    schema_version: PositiveCount
    issues: list[ProfileIssuePayload]


class ConfigStatusResult(OutputSchema):
    """JSON envelope for ``aeat config profile status``.

    Covers all readiness branches: none, dangling_pointer,
    missing/unreadable profile record, incomplete config, and ready. The ready
    branch summarises the active profile's canonical tax/activity fields; error
    branches keep pointer and record diagnostics separate so an unreadable
    encrypted profile is not mistaken for an unregistered profile.
    """

    active_profile: str | None = None
    # none / dangling_pointer branch
    registered_profile: bool | None = None
    configured: bool | None = None
    # missing / unreadable record branch
    profile_record_present: bool | None = None
    profile_record_error: str | None = None
    # Incomplete branch
    tax_id_present: bool | None = None
    activity_present: bool | None = None
    # Ready branch
    profile_id: ProfileId | None = None
    iva_regime: str | None = None
    tax_residence_ccaa: str | None = None
    precondition_action: ResolvedPreconditionAction | None = None


class ConfigResetTargetPayload(OutputSchema):
    """Secret-free phase projection for one reset target."""

    bucket_id: BucketId
    label: ProfileLabel | None = None
    setup_state_at_snapshot: ProfileSetupState | None = None
    exists_at_snapshot: bool
    phase: ConfigResetTargetPhase
    retention_blocks_erase: bool | None
    retention_override_approved: bool | None
    completed_at: str | None

    @model_validator(mode="after")
    def _validate_completed_at(self) -> ConfigResetTargetPayload:
        if self.completed_at is not None:
            validate_utc_aware(datetime.fromisoformat(self.completed_at))
        return self


class ConfigResetSummaryPayload(OutputSchema):
    """Reconciled completion counts for one reset operation."""

    target_count: NonNegativeInt
    deleted_count: NonNegativeInt
    already_absent_count: NonNegativeInt
    retention_override_count: NonNegativeInt
    completed_at: str

    @model_validator(mode="after")
    def _validate_summary(self) -> ConfigResetSummaryPayload:
        validate_utc_aware(datetime.fromisoformat(self.completed_at))
        if self.deleted_count + self.already_absent_count != self.target_count:
            raise ValueError("reset summary target counts do not reconcile")
        if self.retention_override_count > self.target_count:
            raise ValueError("retention override count cannot exceed target count")
        return self


class ConfigResetOperationPayload(OutputSchema):
    """Credential-free operator projection of one durable reset journal."""

    operation_id: Hex64Str
    status: ConfigResetOperationStatus
    started_at: str
    updated_at: str
    pause_reason: ConfigResetPauseReason | None
    paused_target_ids: list[str]
    targets: list[ConfigResetTargetPayload]
    summary: ConfigResetSummaryPayload | None

    @model_validator(mode="after")
    def _validate_operation(self) -> ConfigResetOperationPayload:
        started_at = datetime.fromisoformat(self.started_at)
        updated_at = datetime.fromisoformat(self.updated_at)
        validate_utc_aware(started_at)
        validate_utc_aware(updated_at)
        if updated_at < started_at:
            raise ValueError("reset journal updated_at precedes started_at")
        paused = self.status is ConfigResetOperationStatus.PAUSED
        if paused != (self.pause_reason is not None):
            raise ValueError("paused reset operation requires exactly one pause reason")
        if paused != bool(self.paused_target_ids):
            raise ValueError("paused reset operation requires one or more paused target ids")
        if self.paused_target_ids != sorted(set(self.paused_target_ids)):
            raise ValueError("paused reset target ids must be unique and sorted")
        target_ids = {target.bucket_id for target in self.targets}
        if any(target_id not in target_ids for target_id in self.paused_target_ids):
            raise ValueError("paused target ids must belong to the reset target set")
        if (self.status is ConfigResetOperationStatus.COMPLETE) != (self.summary is not None):
            raise ValueError("complete reset operation requires exactly one summary")
        if self.status is ConfigResetOperationStatus.COMPLETE:
            self._validate_completion_reconciliation()
        return self

    def _validate_completion_reconciliation(self) -> None:
        assert self.summary is not None
        if any(target.phase is not ConfigResetTargetPhase.DELETED for target in self.targets):
            raise ValueError("complete reset operation requires every target to be deleted")
        expected_deleted_count = sum(target.exists_at_snapshot for target in self.targets)
        expected_already_absent_count = len(self.targets) - expected_deleted_count
        expected_override_count = sum(bool(target.retention_override_approved) for target in self.targets)
        if self.summary.target_count != len(self.targets):
            raise ValueError("complete reset summary target count does not match targets")
        if self.summary.deleted_count != expected_deleted_count:
            raise ValueError("complete reset summary deleted count does not match targets")
        if self.summary.already_absent_count != expected_already_absent_count:
            raise ValueError("complete reset summary absent count does not match targets")
        if self.summary.retention_override_count != expected_override_count:
            raise ValueError("complete reset summary retention override count does not match targets")
        if self.summary.completed_at != self.updated_at:
            raise ValueError("complete reset summary timestamp must match operation update timestamp")

    @classmethod
    def from_operation(cls, operation: ConfigResetOperation) -> ConfigResetOperationPayload:
        """Project the application journal without fingerprints or deletion witnesses."""
        targets = [
            ConfigResetTargetPayload(
                bucket_id=target.bucket_id,
                label=target.label,
                setup_state_at_snapshot=target.setup_state_at_snapshot,
                exists_at_snapshot=target.exists_at_snapshot,
                phase=target.phase,
                retention_blocks_erase=(target.retention.blocks_erase if target.retention is not None else None),
                retention_override_approved=(
                    target.retention.override_approved if target.retention is not None else None
                ),
                completed_at=(target.completed_at.isoformat() if target.completed_at is not None else None),
            )
            for target in operation.targets
        ]
        summary = operation.summary
        return cls(
            operation_id=operation.operation_id,
            status=operation.status,
            started_at=operation.started_at.isoformat(),
            updated_at=operation.updated_at.isoformat(),
            pause_reason=operation.pause_reason,
            paused_target_ids=list(operation.paused_target_ids),
            targets=targets,
            summary=(
                ConfigResetSummaryPayload(
                    target_count=summary.target_count,
                    deleted_count=summary.deleted_count,
                    already_absent_count=summary.already_absent_count,
                    retention_override_count=summary.retention_override_count,
                    completed_at=summary.completed_at.isoformat(),
                )
                if summary is not None
                else None
            ),
        )


class ConfigResetStartResult(OutputSchema):
    """JSON envelope for starting one durable all-profile reset."""

    operation: ConfigResetOperationPayload


class ConfigResetStatusResult(OutputSchema):
    """JSON envelope for read-only durable reset status."""

    operation: ConfigResetOperationPayload | None


class ConfigResetResumeResult(OutputSchema):
    """JSON envelope for resuming one exact durable reset journal."""

    operation: ConfigResetOperationPayload


# P07 — auth and bucket verb result schemas


class AuthProvidersResult(OutputSchema):
    """JSON envelope for ``aeat config auth providers``.

    Wraps :class:`AuthProvidersReport`; each row IS the canonical
    :class:`AuthProviderListing`, preserving implemented and reserved provider
    slots from the auth catalogue.

    The rows were redeclared as ``list[dict[str, object]]``, so the envelope
    accepted a shape the report it wraps rejects outright: an empty row, an
    empty label, ``implemented="yes"``, or an unknown provider id all passed
    the shell while the canonical model refused each. Nesting the canonical
    listing makes the envelope's contract the report's contract by
    construction rather than by the projection remembering to agree.
    """

    providers: list[AuthProviderListing]


class AuthConfigurePayload(OutputSchema):
    """JSON envelope for ``aeat config auth configure``.

    Field set mirrors :class:`AuthConfigureResult` from
    the application layer, whose fields are non-nullable with empty/false
    defaults; this envelope reconciles to the same nullability.
    ``status`` is the one CLI-only display field with no application
    counterpart.
    """

    provider: str
    file: str
    status: str | None = None
    complete: bool
    incomplete_reason: str = ""
    profile_tax_id_present: bool = False
    provider_identity_present: bool = False
    identity_alignment: str = ""
    identity_alignment_detail: str = ""
    precondition_action: ResolvedPreconditionAction | None = None

    @classmethod
    def from_result(
        cls,
        result: AuthConfigureResult,
        *,
        precondition_action: ResolvedPreconditionAction | None,
    ) -> AuthConfigurePayload:
        """Project the application auth result into this CLI envelope.

        Explicit field projection: the envelope derives its values from
        the application :class:`AuthConfigureResult`
        instead of the command handler re-declaring the field map inline.
        ``status`` is a CLI-only display field left to its default.

        Returns:
            The projected
            :class:`AuthConfigurePayload`
            instance.
        """
        if (result.precondition_verdict is None) is not (precondition_action is None):
            raise ValueError("auth configuration precondition action must match the application verdict")
        return cls(
            provider=result.provider,
            file=result.file,
            complete=result.complete,
            incomplete_reason=result.incomplete_reason,
            profile_tax_id_present=result.profile_tax_id_present,
            provider_identity_present=result.provider_identity_present,
            identity_alignment=result.identity_alignment,
            identity_alignment_detail=result.identity_alignment_detail,
            precondition_action=precondition_action,
        )


class AuthStatusPayload(OutputSchema):
    """JSON envelope for ``aeat config auth status``.

    The application result's precondition verdict is resolved into the canonical
    wire action at this CLI boundary. The payload is a local readiness projection
    and never performs live AEAT contact.
    """

    provider: str = ""
    configured: bool = False
    authenticated: bool = False
    available: bool = False
    active_profile: str = ""
    active_profile_status: str = ""
    active_profile_registered: bool = False
    active_profile_record_present: bool = False
    active_profile_precondition_action: ResolvedPreconditionAction | None = None
    backend_configured: bool = False
    backend_available: bool = False
    certificate_path: str = ""
    health_severity: str = ""
    health_summary: str = ""

    @classmethod
    def from_result(
        cls,
        result: AuthStatusResult,
        *,
        active_profile_precondition_action: ResolvedPreconditionAction | None,
    ) -> AuthStatusPayload:
        """Project the application readiness result onto the CLI wire contract."""
        if (result.active_profile_precondition_verdict is None) is not (active_profile_precondition_action is None):
            raise ValueError("auth status precondition action must match the application verdict")
        return cls(
            provider=result.provider,
            configured=result.configured,
            authenticated=result.authenticated,
            available=result.available,
            active_profile=result.active_profile,
            active_profile_status=result.active_profile_status,
            active_profile_registered=result.active_profile_registered,
            active_profile_record_present=result.active_profile_record_present,
            active_profile_precondition_action=active_profile_precondition_action,
            backend_configured=result.backend_configured,
            backend_available=result.backend_available,
            certificate_path=result.certificate_path,
            health_severity=result.health_severity,
            health_summary=result.health_summary,
        )


class AuthTestPayload(AuthStatusPayload):
    """JSON envelope for ``aeat config auth test``.

    The command tests local readiness and persisted-session metadata; it does not
    submit to AEAT. Its inherited action field is the same resolved wire DTO as
    ``config.auth.status``.
    """

    persisted_session_present: bool = False
    persisted_session_expired: bool | None = None
    persisted_session_state: str = ""
    probe_summary: str = ""
    probe_result: ProviderProbeResult | None = None

    @classmethod
    def from_test_result(
        cls,
        result: AuthTestResult,
        *,
        active_profile_precondition_action: ResolvedPreconditionAction | None,
    ) -> AuthTestPayload:
        """Project the deeper application probe onto the CLI wire contract."""
        if (result.active_profile_precondition_verdict is None) is not (active_profile_precondition_action is None):
            raise ValueError("auth test precondition action must match the application verdict")
        return cls(
            provider=result.provider,
            configured=result.configured,
            authenticated=result.authenticated,
            available=result.available,
            active_profile=result.active_profile,
            active_profile_status=result.active_profile_status,
            active_profile_registered=result.active_profile_registered,
            active_profile_record_present=result.active_profile_record_present,
            active_profile_precondition_action=active_profile_precondition_action,
            backend_configured=result.backend_configured,
            backend_available=result.backend_available,
            certificate_path=result.certificate_path,
            health_severity=result.health_severity,
            health_summary=result.health_summary,
            persisted_session_present=result.persisted_session_present,
            persisted_session_expired=result.persisted_session_expired,
            persisted_session_state=result.persisted_session_state,
            probe_summary=result.probe_summary,
            probe_result=result.probe_result,
        )


class AuthLoginPayload(OutputSchema, AuthLoginResult):
    """JSON envelope for ``aeat config auth login``.

    Reuses the application-owned :class:`AuthLoginResult` field set and strict
    validation directly. Session cookies, tokens, QR payloads, and certificate
    material stay outside the JSON result.
    """


class AuthLogoutPayload(OutputSchema):
    """Secret-free JSON envelope for ``aeat config auth logout``."""

    bucket_id: BucketId
    providers: list[str]
    removed_sessions: int
    cleared_session_state: bool


class AuthResetPayload(OutputSchema):
    """Secret-free JSON envelope for ``aeat config auth reset``."""

    bucket_id: BucketId
    providers: list[str]
    removed_sessions: int
    cleared_provider_configuration: bool
    cleared_locks: int
    removed_certificate_sources: int
    removed_certificate_secrets: int


class ApoderadoCheckResult(OutputSchema):
    """JSON envelope for ``aeat config auth apoderado check``.

    Mirrors the read-only :class:`ApoderadoStatus`
    projection once live verification is wired. Until then the command refuses
    at the application boundary instead of pretending stored configuration is a
    live AEAT check.
    """

    bucket_id: BucketId
    configured: bool
    represented_nif: str | None = Field(default=None, min_length=1, max_length=16)
    granted_scopes: list[str] | None = None


# Profile wizard / lifecycle verb result schemas
#
# ``config.profile.create`` / ``config.profile.edit`` are declared at their real
# producer in :mod:`application.wizard.results`, which sits below this package in
# the hexagonal direction and cannot construct a class defined up here. They
# are referenced there by production CommandSpec. There is NO wizard import HERE:
# the ``config`` group must not pull the wizard dependency tail into every
# ``config`` verb.


class ConfigProfileExportReconcileFailurePayload(OutputSchema):
    """JSON-safe projection of :class:`ProfileBundleExportReconcileFailure`.

    One crash-recovery operation the pre-publication sweep could not
    finalise. ``destination`` is ``None`` when the journal itself could not
    be read; ``reason`` is the refusing error's class name.
    """

    journal_id: NonEmptyStr
    destination: str | None = None
    reason: NonEmptyStr


class ConfigProfileDeleteResult(OutputSchema):
    """JSON envelope for ``aeat config profile delete``.

    One schema serves both postures of the verb, discriminated by ``deleted``:
    the default preflight reports what WOULD be destroyed and leaves the bytes
    in place, and the confirmed run reports the same observation plus the
    instant the capsule was destroyed. Reporting them through one shape is
    deliberate — a caller comparing a preflight against the run that followed it
    compares field for field, and cannot mistake one envelope for the other
    because ``completed_at`` is populated on exactly one of them.

    ``fingerprint`` nests the canonical
    :class:`~cadrumo.application.bucket_maintenance.BucketDeletionFingerprint`
    rather than restating its three facts as loose fields, so the envelope's
    contract is the observation's contract by construction.

    The retention pair is carried on the SUCCESS envelope and not only on the
    refusal: a preflight that reports zero retained records is the operator's
    evidence that the destruction is lawful, and an envelope that reported
    retention only when it blocked would make its absence ambiguous between
    "nothing retained" and "not assessed".

    ``setup_state`` is deliberately absent. It lives inside the encrypted
    profile record, the deletion assessment runs against a profile it has NOT
    unlocked, and a schema declaring a field no production path can populate
    invites a fixture to fill it.
    """

    profile_id: BucketId
    display_name: ProfileLabel
    deleted: bool
    fingerprint: BucketDeletionFingerprint | None = None
    retained_record_count: NonNegativeInt
    earliest_safe_erase_date: str | None = None
    completed_at: str | None = None


class ConfigProfileRenameResult(OutputSchema):
    """JSON envelope retained for profile-label-change evidence.

    Reports the immutable profile id plus the previous and new display labels;
    profile identity and bucket storage remain unchanged.
    """

    profile_id: BucketId
    previous_display_name: ProfileLabel
    display_name: ProfileLabel


class ConfigProfileExportResult(OutputSchema):
    """JSON envelope retained for profile-bundle export evidence.

    Projects :class:`~cadrumo.application.user_profile.ProfileBundleExportResult`:
    the exported profile id, display label, output path, portable bundle
    schema version, operator purpose, wire transport, the personal-data
    categories the bundle carries and deliberately omits, and any
    crash-recovery journal the pre-publication sweep could not finalise.
    Bundle contents are written to ``out`` rather than embedded in the CLI
    envelope.
    """

    profile_id: ProfileId
    display_name: str
    out: str
    # bundle_schema_version is an int; the export handler passes the current
    # version through verbatim.
    schema_version: int
    purpose: ProfileBundleExportPurpose
    transport: ProfileBundleExportTransport
    data_categories: list[str]
    excluded_data_categories: list[str] = []
    reconcile_failures: list[ConfigProfileExportReconcileFailurePayload] = []


class ConfigProfileSubjectAccessRequestResult(OutputSchema):
    """JSON envelope retained for a profile subject-access archive.

    A GDPR right-of-access export: the same portable bundle produced by the
    retired profile-bundle export surface, framed as the operator's own
    personal-data archive. Reports the profile identity, output path, bundle
    schema version, operator purpose, wire transport, the machine-readable
    catalogue of the personal-data categories the archive carries so the
    subject can see what is held, and any crash-recovery journal the
    pre-publication sweep could not finalise.

    ``excluded_data_categories`` is reported alongside, never omitted. The
    bundle ships under the structured custody profile, so whole namespaces --
    attachment blobs, purchase invoice evidence, the bucket event history --
    stay in encrypted storage. Publishing only what the archive carries would
    make the catalogue read as a completeness claim it cannot support.
    """

    profile_id: ProfileId
    display_name: str
    out: str
    schema_version: int
    purpose: ProfileBundleExportPurpose
    transport: ProfileBundleExportTransport
    data_categories: list[str]
    excluded_data_categories: list[str] = []
    reconcile_failures: list[ConfigProfileExportReconcileFailurePayload] = []


class ConfigProfileImportResult(OutputSchema):
    """JSON envelope retained for profile-bundle import evidence.

    Projects :class:`ProfileImportResult` down to
    the imported profile identity, label, and bundle schema version.
    """

    profile_id: ProfileId
    display_name: str
    schema_version: int


# Sealed bucket-archive result schemas (backup / restore / inspect)


# Repair verb result schemas (profile / integrity sub-app)


class ActiveProfileHealthPayload(OutputSchema):
    """JSON-mode projection of :class:`~cadrumo.application.workflow.ActiveProfileHealth`.

    Mirrors the canonical health verdict field-for-field so a malformed
    ``status`` or ``source`` is refused rather than forwarded as an arbitrary
    key. ``missing_required`` projects the canonical ``tuple`` as a ``list``
    per this module's JSON-mode sequence-field convention.
    """

    active_profile: str | None
    source: ProfileSource
    status: ProfileHealthStatus
    registered_bucket: bool = False
    profile_record_present: bool = False
    profile_record_error: str = ""
    profile_present_keys: NonNegativeInt = 0
    profile_total_keys: NonNegativeInt = 0
    missing_required: list[str] = []
    repairable_by_clearing_pointer: bool = False
    precondition_action: ResolvedPreconditionAction | None = None


class RepairProfileResult(OutputSchema):
    """JSON envelope for ``aeat config repair profile``.

    Covers the inspection branch (operator-readable profile-record status)
    and the ``--clear-active`` pointer-repair branch. The pointer-repair
    branch projects the canonical
    :class:`~cadrumo.application.workflow.ActiveProfileHealth` verdict (the
    same typed model :class:`ActiveProfileRepairResult` carries as
    ``before``/``after``) through :class:`ActiveProfileHealthPayload`, so a
    malformed ``status`` or ``source`` is refused rather than forwarded as an
    arbitrary extra key. The two branches populate disjoint field sets; each
    branch's fields default to ``None`` on the other. The payload is a
    pointer/record repair projection and does not dump encrypted profile
    contents.
    """

    # Pointer-repair branch (from ActiveProfileRepairResult)
    dry_run: bool | None = None
    cleared_pointer: bool | None = None
    before: ActiveProfileHealthPayload | None = None
    after: ActiveProfileHealthPayload | None = None
    # Profile-record-status branch
    profile_id: ProfileId | None = None
    bucket_id: BucketId | None = None
    display_name: str | None = None
    registered_bucket: bool | None = None
    profile_record_present: bool | None = None
    setup_state: ProfileSetupState | None = None
    status: Literal["missing_profile_record", "profile_record_unreadable"] | None = None
    error: str | None = None
    precondition_action: ResolvedPreconditionAction | None = None


class RepairIntegrityCheckPayload(OutputSchema):
    """The pass/fail verdict ``repair integrity objects`` emits for its sweep.

    Narrower than the full :class:`~cadrumo.application.diagnostics.DiagnosticCheck`
    used by ``config repair`` (which requires a check ``name`` and a
    next-action/dead-end contract): this command reports only the aggregate
    unreadable-row verdict and its summary.
    """

    status: Literal["ok", "fail"]
    summary: str


class RepairIntegrityObjectsResult(OutputSchema):
    """JSON envelope for ``aeat config repair integrity objects``.

    Projects the per-namespace
    :class:`~cadrumo.application.diagnostics.SecureObjectIntegrityReport`
    (via the shared :class:`ConfigRepairNamespacePayload` rows, bounded
    exactly as the canonical
    :class:`~cadrumo.adapters.persistence.storage.SecureObjectNamespaceIntegrity`
    row) plus the aggregate pass/fail verdict for the unreadable-row count.
    """

    namespaces: list[ConfigRepairNamespacePayload]
    readable_total: NonNegativeInt
    unreadable_total: NonNegativeInt
    check: RepairIntegrityCheckPayload


class RepairIntegrityRegistryResult(OutputSchema):
    """JSON envelope for ``aeat config repair integrity registry``.

    Mirrors
    :class:`RegistryIntegrityReport`
    ``model_dump(mode='json')``.
    ``extra="allow"`` forwards the typed sub-models without re-declaring
    the registry / diagnostic-check shapes locally.
    """

    model_config = ConfigDict(extra="allow")


# Apoderado verb result schemas


class ApoderadoStatusResult(OutputSchema):
    """JSON envelope for ``aeat config auth apoderado status``.

    Mirrors :class:`ApoderadoStatus`. ``extra="allow"``
    lets the application model evolve without breaking the envelope contract
    here. This is the offline encrypted-configuration read, not a live AEAT
    verification.
    """

    bucket_id: BucketId
    configured: bool
    represented_nif: str | None = Field(default=None, min_length=1, max_length=16)
    granted_scopes: list[str] = []
    catalogue_version: NonEmptyStr | None = None
    configured_at: datetime | None = None


class ApoderadoConfigureResult(OutputSchema):
    """JSON envelope for ``aeat config auth apoderado configure``.

    Projects :class:`ApoderadoConfiguration` after scope
    validation against the apoderamientos catalogue. The represented NIF is
    stored encrypted by the application service; the CLI only emits the chosen
    configuration summary.
    """

    bucket_id: BucketId
    represented_nif: str = Field(min_length=1, max_length=16)
    granted_scopes: list[str] = []
    catalogue_version: NonEmptyStr
    configured_at: datetime
    notes: str = Field(default="", max_length=500)


class ApoderadoClearResult(OutputSchema):
    """JSON envelope for ``aeat config auth apoderado clear``.

    Reports the bucket whose encrypted apoderado configuration was removed and
    whether a record existed to clear.
    """

    bucket_id: BucketId
    cleared: bool


class ApoderadoScopePayload(OutputSchema):
    """One representative-scope row, mirroring :class:`ApoderadoScope`.

    Carries the same bounds and the same uppercase/alphanumeric ``code``
    invariant the domain catalogue enforces, so a malformed scope entry is
    refused rather than forwarded.
    """

    code: ApoderadoScopeCode
    name_es: ApoderadoScopeName
    name_en: ApoderadoScopeName
    modelo_codes: list[str] = []

    @field_validator("code")
    @classmethod
    def _code_is_uppercase_alnum(cls, value: str) -> str:
        if not value.isupper():
            raise ValueError(f"scope code must be uppercase, got {value!r}")
        if not value.replace("_", "").isalnum():
            raise ValueError(f"scope code must be alphanumeric (underscores allowed), got {value!r}")
        return value


class ApoderadoScopesListResult(OutputSchema):
    """JSON envelope for ``aeat config auth apoderado scopes list``.

    Projects the apoderado scope catalogue payload from
    :class:`ApoderamientosCatalogue` -- the non-blank ``catalogue_version``
    and every :class:`ApoderadoScopePayload` row -- instead of forwarding an
    arbitrary dumped shape.
    """

    catalogue_version: NonEmptyStr
    scopes: list[ApoderadoScopePayload]


# Certificate source registry verb result schemas


class CertificateSourcePayloadEntry(OutputSchema):
    """One registered certificate source row.

    Mirrors :class:`application.auth.CertificateSourcePayload`; nested in
    :class:`CertificateSourceListPayload`, not a direct CommandSpec schema target.
    """

    name: str
    certificate_path: str
    friendly_name: str = ""
    active: bool = False
    registered_at: str = ""


class CertificateSourceMutationPayload(OutputSchema):
    """JSON envelope for ``certificate register`` / ``select`` / ``remove``.

    Field set is 1:1 with the application
    :class:`application.auth.CertificateSourceMutationResult`. The same
    schema class is referenced under the three distinct command paths
    below because ``register``, ``select``, and ``remove`` all emit the
    identical mutation-result shape.
    """

    name: str
    certificate_path: str = ""
    active: bool = False
    removed: bool = False


class CertificateSourceListPayload(OutputSchema):
    """JSON envelope for ``aeat config auth certificate list``.

    Mirrors :class:`application.auth.CertificateSourceListResult`.
    """

    sources: list[CertificateSourcePayloadEntry] = []
    active_source: str = ""


class CertificateSourceCheckEntryPayload(OutputSchema):
    """One certificate source's expiry/rotation verdict row.

    Mirrors :class:`application.auth.CertificateSourceCheckEntry`; nested
    in :class:`CertificateSourceCheckPayload`, not a direct CommandSpec schema target.
    """

    name: str
    certificate_path: str
    friendly_name: str = ""
    active: bool = False
    result: str = ""
    summary: str = ""
    days_until_expiry: int | None = None


class CertificateSourceCheckPayload(OutputSchema):
    """JSON envelope for ``aeat config auth certificate check``.

    Mirrors :class:`application.auth.CertificateSourceCheckReport`.
    """

    entries: list[CertificateSourceCheckEntryPayload] = []
    has_warnings: bool = False


class CertificateSourceSecretMutationPayload(OutputSchema):
    """JSON envelope for ``certificate secret set`` / ``certificate secret remove``.

    Mirrors :class:`application.auth.CertificateSourceSecretMutationResult`.
    Never carries the secret value itself — only whether one is now
    registered and whether the call rotated an existing secret. Named
    certificate secrets have exactly one storage authority (encrypted
    secure storage), so no backend descriptor is projected.
    """

    name: str
    has_secret: bool = False
    rotated: bool = False
    removed: bool = False


# Auth diagnostics verb result schemas


class AuthDiagnosticsListResult(OutputSchema):
    """JSON envelope for ``aeat config auth diagnostics list``.

    Nests the real :class:`AuthDiagnosticSummary` rows so a malformed
    nested row (an unknown phone-state token, a non-datetime capture
    time, an out-of-band extra field) the canonical summary already
    refuses is refused here too, instead of forwarding an unvalidated
    ``dict[str, object]``.
    """

    row_count: int
    rows: list[AuthDiagnosticSummary] = []


class AuthDiagnosticsViewResult(OutputSchema, AuthDiagnosticDetail):
    """JSON envelope for ``aeat config auth diagnostics view``.

    Reuses :class:`AuthDiagnosticDetail`'s own field set and validation
    directly (multiple inheritance merges the strict/frozen configs of
    both bases) instead of an ``extra="allow"`` shell that forwarded
    every field unvalidated.
    """


class AuthDiagnosticsReportResult(OutputSchema):
    """JSON envelope for ``aeat config auth diagnostics report``.

    Projects :class:`AuthDiagnosticReportResult` after an
    operator records the phone-state outcome for an encrypted auth diagnostic.
    """

    diagnostic_id: NonEmptyStr
    phone_state: AuthDiagnosticPhoneState
    reported_at: datetime
