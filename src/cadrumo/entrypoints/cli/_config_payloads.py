"""Typed ``--json`` payload schemas for core config CLI commands.

Every registered class is a strict :class:`OutputSchema` transport shape for a
config command result. Field sets match the production emit sites in
:mod:`_config` and its submodules; sequence fields use ``list`` so JSON-mode
pydantic dumps stay arrays. Application services remain authoritative for
profile, auth, apoderado, repair, diagnostics, and workflow semantics. Sandbox
payloads live in the cohesive sibling :mod:`_config_sandbox_payloads`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ConfigDict

from ._schemas import OutputSchema, register_schema

# The two wizard-owned profile result schemas register through the manifest's
# explicit lazy schema-owner table, NOT here: the `config` group imports this
# module at group-resolution time, so importing the wizard from here would pull
# its whole dependency tail into every `config` verb and redden the cold-start
# guard.

if TYPE_CHECKING:
    from ...application.auth import AuthConfigureResult
    from ...application.config_reset import ConfigResetOperation

# Shared sub-models (not registered — used as nested types)


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

    Mirrors :class:`WorkflowStateResetFingerprint`
    for ``config repair reset-progress``.  The fingerprint identifies the
    stored envelope's schema, write time, byte length, read-status reason, and
    recoverable bucket context without serialising the
    :class:`WorkflowState` plaintext.
    """

    schema_version: int | None = None
    written_at: str | None = None
    byte_length: int | None = None
    reason_class: str
    recovered_bucket_id: str | None = None


class ProfilePointerPayload(OutputSchema):
    """One active-profile pointer row in the config profile listing.

    Mirrors the :class:`ProfileBucketPointer`
    projection that links an operator-facing profile name to the immutable
    profile bucket id. The row deliberately carries no profile facts; detailed
    facts stay under
    :class:`ProfileFactPayload` in the
    profile-show envelope.

    ``status`` mirrors the manifest lifecycle marker
    (:class:`~cadrumo.domain.user_profile.UserProfileStatus` value) so the
    listing distinguishes a workable ``active`` profile from a
    ``setup_incomplete`` one still completing its interactive setup — the
    latter is listed and resumable but not yet workable.
    """

    name: str
    bucket_id: str
    active: bool
    status: str


class ProfileIssuePayload(OutputSchema):
    """One validation issue from :class:`ProfileValidationService`.

    The payload mirrors
    :class:`ProfileValidationIssue` as plain JSON
    so ``profile show`` and ``profile validate`` expose the same readiness
    diagnostics without importing domain records into the CLI layer.
    """

    severity: str
    code: str
    path: str | None = None
    message: str


class ProfileFactPayload(OutputSchema):
    """One schema-backed fact key/value pair in ``config profile show``.

    Values are the operator-display projection of profile facts, not the
    encrypted :class:`UserProfileRecord` itself.
    """

    path: str
    value: str


class ConfigHelpEntryPayload(OutputSchema):
    """One command row in the curated config help document."""

    command: str
    description: str


class ConfigHelpSectionPayload(OutputSchema):
    """One workflow-ordered section in the curated config help document."""

    title: str
    entries: list[ConfigHelpEntryPayload]


@register_schema("root.config")
class ConfigRootResult(OutputSchema):
    """JSON envelope for bare ``aeat config`` and ``aeat config --help``."""

    surface: str
    heading: str
    paragraphs: list[str]
    sections: list[ConfigHelpSectionPayload]
    footer: str


# P05 — repair verb result schemas


@register_schema("config.repair")
class ConfigRepairResult(OutputSchema):
    """JSON envelope for the composite ``aeat config repair`` report.

    The application diagnostics service owns the nested registry, setup,
    secure-object, and check records. This transport schema fixes the report's
    top-level contract while preserving those already validated nested DTOs.
    """

    overall: str
    package_name: str
    package_version: str
    python_version: str
    log_file: str
    registry: dict[str, object]
    setup: dict[str, object] | None
    secure_objects: dict[str, object]
    checks: list[dict[str, object]]


@register_schema("config.repair.logs")
class RepairLogsResult(OutputSchema):
    """JSON envelope for ``aeat config repair logs``.

    The payload is a bounded log-tail view: ``path`` identifies the log file
    rendered to the operator and ``lines`` contains the selected text lines.
    """

    path: str
    lines: list[str]


@register_schema("config.repair.quarantine")
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


@register_schema("config.repair.reset_progress")
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


@register_schema("config.repair.connectivity")
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


@register_schema("config.profile.list")
class ConfigListResult(OutputSchema):
    """JSON envelope for ``aeat config profile list``.

    Note: ``config_list`` is registered on the ``profile list`` sub-command
    which maps to the CLI path ``config.list`` (the profile sub-app carries
    the list verb). Each
    :class:`ProfilePointerPayload` row
    identifies a
    registered bucket, while ``active_profile`` names the current pointer.
    """

    active_profile: str | None = None
    profiles: list[ProfilePointerPayload]


@register_schema("config.login")
class ConfigLoginResult(OutputSchema):
    """JSON envelope for ``aeat config login``.

    Reports the authenticated profile's immutable identity, its operator
    label, the custody backend that performed the unwrap, and the two
    session deadlines. ``session_persisted`` is ``False`` on a host with no
    usable OS keychain, where the login is process-scoped only.
    ``already_authenticated`` marks the idempotent no-op that resumed a
    still-valid session without re-prompting, and
    ``closed_previous_profile`` names the profile a cross-profile handover
    signed out. No passphrase, key material, or session-key bytes enter
    this payload.
    """

    profile_id: str
    active_profile: str
    backend_kind: str
    authenticated_at: str
    idle_deadline: str
    absolute_deadline: str
    session_persisted: bool
    already_authenticated: bool
    closed_previous_profile: str | None = None


@register_schema("config.logout")
class ConfigLogoutResult(OutputSchema):
    """JSON envelope for ``aeat config logout``.

    Reports which profile the strong close signed out, or ``None`` when
    nothing was signed in. ``already_logged_out`` marks that idempotent
    no-op, so a retry is distinguishable from a first close without
    parsing prose.
    """

    logged_out_profile: str | None = None
    already_logged_out: bool


@register_schema("config.passphrase.change")
class ConfigPassphraseChangeResult(OutputSchema):
    """JSON envelope for ``aeat config passphrase change``.

    Reports the secure-store directory and whether the passphrase was rotated.
    Neither the current nor the new passphrase, key material, nor recovery
    phrases ever enter this payload.
    """

    secret_store_dir: str
    changed: bool


@register_schema("config.recover")
class ConfigRecoverResult(OutputSchema):
    """JSON envelope for ``aeat config recover``.

    Reports the recovery file used and the local secret-store directory that was
    recovered, without serialising the recovery secret itself.
    """

    recovery_path: str
    secret_store_dir: str
    recovered: bool


@register_schema("config.recovery.status")
class ConfigRecoveryStatusResult(OutputSchema):
    """JSON envelope for ``aeat config recovery status``.

    Reports enrollment and the non-secret recovery fingerprint only; the
    recovery words are never serialised on any envelope.
    """

    recovery_path: str
    recovery_enrolled: bool
    recovery_fingerprint: str | None = None


@register_schema("config.recovery.create")
class ConfigRecoveryCreateResult(OutputSchema):
    """JSON envelope for ``aeat config recovery create``.

    The candidate recovery words were written to the controlling terminal and
    retype-confirmed before commit; only the non-secret fingerprint of the
    installed envelope rides here.
    """

    recovery_path: str
    recovery_fingerprint: str
    rotated: bool


@register_schema("config.recovery.rotate")
class ConfigRecoveryRotateResult(OutputSchema):
    """JSON envelope for ``aeat config recovery rotate``.

    Same non-secret shape as the create envelope; ``rotated`` is true because
    a prior enrollment was replaced.
    """

    recovery_path: str
    recovery_fingerprint: str
    rotated: bool


@register_schema("config.recovery.verify")
class ConfigRecoveryVerifyResult(OutputSchema):
    """JSON envelope for ``aeat config recovery verify``.

    Confirms whether the supplied recovery material matched the encrypted local
    recovery record; the secret phrase is not echoed back.
    """

    recovery_path: str
    verified: bool
    recovery_fingerprint: str | None = None


@register_schema("config.profile.show")
class ConfigProfileShowResult(OutputSchema):
    """JSON envelope for ``aeat config profile show``.

    Covers the missing-record branch, the unreadable-record branch, and
    the success path. Optional fields accommodate each branch. Successful rows
    project :class:`UserProfileRecord` facts through
    :class:`ProfileFactPayload`;
    failures report pointer and record readiness
    without dumping encrypted profile contents.
    """

    profile_id: str | None = None
    display_name: str | None = None
    status: str | None = None
    valid: bool | None = None
    schema_version: int | None = None
    issues: list[ProfileIssuePayload] | None = None
    facts: list[ProfileFactPayload] | None = None
    # Error / readiness branches
    registered_bucket: bool | None = None
    profile_record_present: bool | None = None
    configured: bool | None = None
    error: str | None = None
    next_action: str | None = None
    bucket_id: str | None = None
    # Readiness / repair branches (raised when profile record cannot be loaded).
    readiness: str | None = None
    profile_record: str | None = None


@register_schema("config.profile.validate")
class ConfigProfileValidateResult(OutputSchema):
    """JSON envelope for ``aeat config profile validate``.

    Report-only surface: same
    :class:`ProfileValidationService` outcome
    that ``aeat config profile show`` exposes inline, but as the primary
    payload with no fact dump so the operator can audit a profile's schema
    conformance independent of its data view. Exit code is ``0`` when no
    blocking issues exist and ``2`` when any error-severity issue surfaces.
    """

    profile_id: str
    display_name: str
    status: str
    valid: bool
    schema_version: int
    issues: list[ProfileIssuePayload]


class ProfilePreflightMissingPayload(OutputSchema):
    """One missing-required-field row inside the profile preflight result.

    Nested in
    :class:`ConfigProfilePreflightResult`
    and mirrors :class:`ProfilePreflightRequirement`
    so the CLI can name the missing selector, schema section, and field key for
    a concrete modelo/revision/period context.
    """

    selector: str
    section_key: str
    field_key: str


@register_schema("config.profile.preflight")
class ConfigProfilePreflightResult(OutputSchema):
    """JSON envelope for ``aeat config profile preflight``.

    Reports which profile fields a given ``(modelo, revision_id, filing_year,
    period)`` filing context requires that the active profile does not yet
    carry. ``ready=true`` when no required field is missing; exit code is
    ``0`` when ready and ``2`` when missing fields surface so operators
    discover the gap via the shell exit status. The application authority is
    :class:`ProfilePreflightReport`.
    """

    profile_id: str
    modelo: str
    revision_id: str
    filing_year: int
    period: str
    ready: bool
    missing: list[ProfilePreflightMissingPayload]


@register_schema("config.profile.delete")
class ConfigProfileDeleteResult(OutputSchema):
    """JSON envelope for ``aeat config profile delete``.

    Reports the tombstoned profile id and display label plus whether the active
    profile pointer had to be cleared.
    """

    profile_id: str
    display_name: str
    status: str
    active_profile_cleared: bool


@register_schema("config.profile.duplicate")
class ConfigProfileDuplicateResult(OutputSchema):
    """JSON envelope for ``aeat config profile duplicate``.

    Projects the source and new immutable profile ids produced by the profile
    lifecycle service; the copied fact set is not expanded in this mutation
    result.
    """

    source_profile_id: str
    target_profile_id: str
    display_name: str


@register_schema("config.profile.status")
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
    profile_id: str | None = None
    iva_regime: str | None = None
    tax_residence_ccaa: str | None = None
    next_action: str | None = None


class ConfigResetTargetPayload(OutputSchema):
    """Secret-free phase projection for one reset target."""

    bucket_id: str
    label: str | None
    status_at_snapshot: str | None
    exists_at_snapshot: bool
    phase: str
    retention_blocks_erase: bool | None
    retention_override_approved: bool | None
    completed_at: str | None


class ConfigResetSummaryPayload(OutputSchema):
    """Reconciled completion counts for one reset operation."""

    target_count: int
    deleted_count: int
    already_absent_count: int
    retention_override_count: int
    completed_at: str


class ConfigResetOperationPayload(OutputSchema):
    """Credential-free operator projection of one durable reset journal."""

    operation_id: str
    status: str
    started_at: str
    updated_at: str
    pause_reason: str | None
    paused_target_ids: list[str]
    targets: list[ConfigResetTargetPayload]
    summary: ConfigResetSummaryPayload | None

    @classmethod
    def from_operation(cls, operation: ConfigResetOperation) -> ConfigResetOperationPayload:
        """Project the application journal without fingerprints or deletion witnesses."""
        targets = [
            ConfigResetTargetPayload(
                bucket_id=target.bucket_id,
                label=target.label,
                status_at_snapshot=(target.status_at_snapshot.value if target.status_at_snapshot is not None else None),
                exists_at_snapshot=target.exists_at_snapshot,
                phase=target.phase.value,
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
            status=operation.status.value,
            started_at=operation.started_at.isoformat(),
            updated_at=operation.updated_at.isoformat(),
            pause_reason=(operation.pause_reason.value if operation.pause_reason is not None else None),
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


@register_schema("config.reset.start")
class ConfigResetStartResult(OutputSchema):
    """JSON envelope for starting one durable all-profile reset."""

    operation: ConfigResetOperationPayload


@register_schema("config.reset.status")
class ConfigResetStatusResult(OutputSchema):
    """JSON envelope for read-only durable reset status."""

    operation: ConfigResetOperationPayload | None


@register_schema("config.reset.resume")
class ConfigResetResumeResult(OutputSchema):
    """JSON envelope for resuming one exact durable reset journal."""

    operation: ConfigResetOperationPayload


# P07 — auth and bucket verb result schemas


@register_schema("config.auth.providers")
class AuthProvidersResult(OutputSchema):
    """JSON envelope for ``aeat config auth providers``.

    Wraps :class:`AuthProvidersReport`; each row is the
    JSON form of :class:`AuthProviderListing`, preserving
    implemented and reserved provider slots from the auth catalogue.
    """

    providers: list[dict[str, object]]


@register_schema("config.auth.configure")
class AuthConfigurePayload(OutputSchema):
    """JSON envelope for ``aeat config auth configure``.

    Field set mirrors :class:`AuthConfigureResult` from
    the application layer, whose fields are non-nullable with empty/false
    defaults; this envelope reconciles to the same nullability (DB-26 S50).
    ``status`` is the one CLI-only display field with no application
    counterpart.
    """

    provider: str
    file: str
    status: str | None = None
    complete: bool
    incomplete_reason: str = ""
    active_profile: str = ""
    profile_tax_id_present: bool = False
    provider_identity_present: bool = False
    identity_alignment: str = ""
    identity_alignment_detail: str = ""
    next_action: str = ""

    @classmethod
    def from_result(cls, result: AuthConfigureResult) -> AuthConfigurePayload:
        """Project the application auth result into this CLI envelope.

        Explicit field projection (DB-26 S50): the envelope derives its values from
        the application :class:`AuthConfigureResult`
        instead of the command handler re-declaring the field map inline.
        ``status`` is a CLI-only display field left to its default.

        Returns:
            The projected
            :class:`AuthConfigurePayload`
            instance.
        """
        return cls(
            provider=result.provider,
            file=result.file,
            complete=result.complete,
            incomplete_reason=result.incomplete_reason,
            active_profile=result.active_profile,
            profile_tax_id_present=result.profile_tax_id_present,
            provider_identity_present=result.provider_identity_present,
            identity_alignment=result.identity_alignment,
            identity_alignment_detail=result.identity_alignment_detail,
            next_action=result.next_action,
        )


@register_schema("config.auth.status")
class AuthStatusPayload(OutputSchema):
    """JSON envelope for ``aeat config auth status``.

    The application :class:`AuthStatusResult` model
    evolves independently; ``extra="allow"`` ensures any additional fields pass
    through without re-declaring every provider-specific key here. The payload is
    a local readiness projection and never performs live AEAT contact.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = ConfigDict(extra="allow")  # type: ignore[assignment]


@register_schema("config.auth.test")
class AuthTestPayload(OutputSchema):
    """JSON envelope for ``aeat config auth test``.

    Thin envelope over :class:`AuthTestResult`; the
    application model carries all provider-specific probe fields.
    ``extra="allow"`` forwards them without re-declaration. The command tests
    local readiness and persisted-session metadata; it does not submit to AEAT.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = ConfigDict(extra="allow")  # type: ignore[assignment]


@register_schema("config.auth.login")
class AuthLoginPayload(OutputSchema):
    """JSON envelope for ``aeat config auth login``.

    Thin envelope over :class:`AuthLoginResult`; the
    application model carries provider-specific live-login fields.
    ``extra="allow"`` forwards them without re-declaration. Session cookies,
    tokens, QR payloads, and certificate material stay outside the JSON result.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = ConfigDict(extra="allow")  # type: ignore[assignment]


@register_schema("config.auth.logout")
class AuthLogoutPayload(OutputSchema):
    """Secret-free JSON envelope for ``aeat config auth logout``."""

    bucket_id: str
    providers: list[str]
    removed_sessions: int
    cleared_session_state: bool


@register_schema("config.auth.reset")
class AuthResetPayload(OutputSchema):
    """Secret-free JSON envelope for ``aeat config auth reset``."""

    bucket_id: str
    providers: list[str]
    removed_sessions: int
    cleared_provider_configuration: bool
    cleared_locks: int
    removed_certificate_sources: int
    removed_certificate_secrets: int


@register_schema("config.auth.apoderado.check")
class ApoderadoCheckResult(OutputSchema):
    """JSON envelope for ``aeat config auth apoderado check``.

    Mirrors the read-only :class:`ApoderadoStatus`
    projection once live verification is wired. Until then the command refuses
    at the application boundary instead of pretending stored configuration is a
    live AEAT check.
    """

    bucket_id: str
    configured: bool
    represented_nif: str | None = None
    granted_scopes: list[str] | None = None


# Profile wizard / lifecycle verb result schemas
#
# ``config.profile.create`` / ``config.profile.edit`` are declared at their real
# producer in :mod:`application.wizard._results`, which sits below this package in
# the hexagonal direction and cannot construct a class defined up here. They
# register through the manifest's lazy canonical-owner table. There is NO
# wizard import HERE: the ``config`` group must not pull the wizard dependency
# tail into every ``config`` verb.


@register_schema("config.profile.export")
class ConfigProfileExportResult(OutputSchema):
    """JSON envelope for ``aeat config profile export``.

    Reports the exported profile id, display label, output path, and portable
    bundle schema version. Bundle contents are written to ``out`` rather than
    embedded in the CLI envelope.
    """

    profile_id: str
    display_name: str
    out: str
    # bundle_schema_version is an int; the export handler passes the current
    # version through verbatim.
    schema_version: int


@register_schema("config.profile.subject_access_request")
class ConfigProfileSubjectAccessRequestResult(OutputSchema):
    """JSON envelope for ``aeat config profile subject-access-request``.

    A GDPR right-of-access export: the same portable bundle
    ``config profile export`` produces, framed as the operator's own
    personal-data archive. Reports the profile identity, output path, bundle
    schema version, and the machine-readable catalogue of the personal-data
    categories the archive carries so the subject can see what is held.

    ``excluded_data_categories`` is reported alongside, never omitted. The
    bundle ships under the structured custody profile, so whole namespaces --
    attachment blobs, purchase invoice evidence, the bucket event history --
    stay in encrypted storage. Publishing only what the archive carries would
    make the catalogue read as a completeness claim it cannot support.
    """

    profile_id: str
    display_name: str
    out: str
    schema_version: int
    data_categories: list[str]
    excluded_data_categories: list[str] = []


@register_schema("config.profile.import")
class ConfigProfileImportResult(OutputSchema):
    """JSON envelope for ``aeat config profile import``.

    Projects :class:`ProfileImportResult` down to
    the imported profile identity, label, and bundle schema version.
    """

    profile_id: str
    display_name: str
    schema_version: int


@register_schema("config.profile.rename")
class ConfigProfileRenameResult(OutputSchema):
    """JSON envelope for ``aeat config profile rename``.

    Reports the immutable profile id plus the previous and new display labels;
    profile identity and bucket storage remain unchanged.
    """

    profile_id: str
    previous_display_name: str
    display_name: str


# Sealed bucket-archive result schemas (backup / restore / inspect)


@register_schema("config.profile.archive.export")
class ConfigProfileArchiveExportResult(OutputSchema):
    """JSON envelope for ``aeat config profile archive export``.

    Reports the exported profile id, the written archive path, the manifest
    digest recorded in the archive header, and whether the archive is sealed
    under a recovery passphrase rather than the active bucket key. Unlike
    ``config profile export`` this archive is a full, AEAD-encrypted backup:
    it carries attachment evidence bytes, the audit trail, and the
    cross-period calculation inputs.
    """

    profile_id: str
    display_name: str
    out: str
    manifest_digest: str
    recovery_wrap_present: bool


@register_schema("config.profile.archive.import")
class ConfigProfileArchiveImportResult(OutputSchema):
    """JSON envelope for ``aeat config profile archive import``.

    Reports the restored profile id, the manifest digest authenticated at
    decryption, and the archive schema version. The profile identity is
    preserved verbatim from the archive (same ``bucket_id`` the archive was
    exported from); a colliding existing profile is refused unless
    ``--force`` is supplied.
    """

    profile_id: str
    manifest_digest: str
    archive_schema_version: int


@register_schema("config.profile.archive.inspect")
class ConfigProfileArchiveInspectResult(OutputSchema):
    """JSON envelope for ``aeat config profile archive inspect``.

    A read-only preview of a sealed archive's plaintext header plus the
    on-disk file size: the profile id it holds, when it was written, its
    manifest digest, whether it requires a recovery passphrase, and its
    archive schema version. The encrypted payload is never opened, so no
    per-store contents are reported here.
    """

    profile_id: str
    manifest_digest: str
    recovery_wrap_present: bool
    archive_schema_version: int
    created_at: str
    size_bytes: int


# Repair verb result schemas (profile / integrity sub-app)


@register_schema("config.repair.profile")
class RepairProfileResult(OutputSchema):
    """JSON envelope for ``aeat config repair profile``.

    Covers the inspection branch (operator-readable profile-record status),
    and the ``--clear-active`` pointer-repair branch. The application layer
    model evolves independently across these branches; ``extra="allow"`` keeps
    the envelope shape stable without re-declaring every field. The payload is
    a pointer/record repair projection and does not dump encrypted profile
    contents.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = ConfigDict(extra="allow")  # type: ignore[assignment]


@register_schema("config.repair.integrity.objects")
class RepairIntegrityObjectsResult(OutputSchema):
    """JSON envelope for ``aeat config repair integrity objects``.

    Covers the no-active-profile guard branch (``readable``/``unreadable``
    counts with ``reason``) and the live-probe branch (full report with
    nested namespace breakdown). ``extra="allow"`` forwards the
    :class:`RepairIntegrityReport` payload
    without re-declaring every sub-model.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = ConfigDict(extra="allow")  # type: ignore[assignment]


@register_schema("config.repair.integrity.registry")
class RepairIntegrityRegistryResult(OutputSchema):
    """JSON envelope for ``aeat config repair integrity registry``.

    Mirrors
    :class:`RegistryIntegrityReport`
    ``model_dump(mode='json')``.
    ``extra="allow"`` forwards the typed sub-models without re-declaring
    the registry / diagnostic-check shapes locally.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = ConfigDict(extra="allow")  # type: ignore[assignment]


# Apoderado verb result schemas


@register_schema("config.auth.apoderado.status")
class ApoderadoStatusResult(OutputSchema):
    """JSON envelope for ``aeat config auth apoderado status``.

    Mirrors :class:`ApoderadoStatus`. ``extra="allow"``
    lets the application model evolve without breaking the envelope contract
    here. This is the offline encrypted-configuration read, not a live AEAT
    verification.
    """

    bucket_id: str
    configured: bool
    represented_nif: str | None = None
    granted_scopes: list[str] = []
    catalogue_version: str | None = None
    configured_at: str | None = None


@register_schema("config.auth.apoderado.configure")
class ApoderadoConfigureResult(OutputSchema):
    """JSON envelope for ``aeat config auth apoderado configure``.

    Projects :class:`ApoderadoConfiguration` after scope
    validation against the apoderamientos catalogue. The represented NIF is
    stored encrypted by the application service; the CLI only emits the chosen
    configuration summary.
    """

    bucket_id: str
    represented_nif: str
    granted_scopes: list[str] = []
    catalogue_version: str
    configured_at: str
    notes: str = ""


@register_schema("config.auth.apoderado.clear")
class ApoderadoClearResult(OutputSchema):
    """JSON envelope for ``aeat config auth apoderado clear``.

    Reports the bucket whose encrypted apoderado configuration was removed and
    whether a record existed to clear.
    """

    bucket_id: str
    cleared: bool


@register_schema("config.auth.apoderado.scopes.list")
class ApoderadoScopesListResult(OutputSchema):
    """JSON envelope for ``aeat config auth apoderado scopes list``.

    Mirrors the apoderado scope catalogue payload from
    :class:`ApoderamientosCatalogue`.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = ConfigDict(extra="allow")  # type: ignore[assignment]


# Certificate source registry verb result schemas


class CertificateSourcePayloadEntry(OutputSchema):
    """One registered certificate source row.

    Mirrors :class:`application.auth.CertificateSourcePayload`; nested in
    :class:`CertificateSourceListPayload`, not registered independently.
    """

    name: str
    certificate_path: str
    friendly_name: str = ""
    active: bool = False
    registered_at: str = ""


@register_schema("config.auth.certificate.register")
class CertificateSourceMutationPayload(OutputSchema):
    """JSON envelope for ``certificate register`` / ``select`` / ``remove``.

    Field set is 1:1 with the application
    :class:`application.auth.CertificateSourceMutationResult`. The same
    schema class is registered under the three distinct command paths
    below because ``register``, ``select``, and ``remove`` all emit the
    identical mutation-result shape.
    """

    name: str
    certificate_path: str = ""
    active: bool = False
    removed: bool = False


register_schema("config.auth.certificate.select")(CertificateSourceMutationPayload)
register_schema("config.auth.certificate.remove")(CertificateSourceMutationPayload)


@register_schema("config.auth.certificate.list")
class CertificateSourceListPayload(OutputSchema):
    """JSON envelope for ``aeat config auth certificate list``.

    Mirrors :class:`application.auth.CertificateSourceListResult`.
    """

    sources: list[CertificateSourcePayloadEntry] = []
    active_source: str = ""


class CertificateSourceCheckEntryPayload(OutputSchema):
    """One certificate source's expiry/rotation verdict row.

    Mirrors :class:`application.auth.CertificateSourceCheckEntry`; nested
    in :class:`CertificateSourceCheckPayload`, not registered
    independently.
    """

    name: str
    certificate_path: str
    friendly_name: str = ""
    active: bool = False
    result: str = ""
    summary: str = ""
    days_until_expiry: int | None = None


@register_schema("config.auth.certificate.check")
class CertificateSourceCheckPayload(OutputSchema):
    """JSON envelope for ``aeat config auth certificate check``.

    Mirrors :class:`application.auth.CertificateSourceCheckReport`.
    """

    entries: list[CertificateSourceCheckEntryPayload] = []
    has_warnings: bool = False


@register_schema("config.auth.certificate.secret.set")
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


register_schema("config.auth.certificate.secret.remove")(CertificateSourceSecretMutationPayload)


# Auth diagnostics verb result schemas


@register_schema("config.auth.diagnostics.list")
class AuthDiagnosticsListResult(OutputSchema):
    """JSON envelope for ``aeat config auth diagnostics list``.

    Mirrors :class:`AuthDiagnosticListReport`
    ``model_dump(mode='json')``. ``extra="allow"`` forwards the per-row
    :class:`AuthDiagnosticSummary` fields without
    re-declaring the sub-model.
    """

    row_count: int
    rows: list[dict[str, object]] = []


@register_schema("config.auth.diagnostics.show")
class AuthDiagnosticsShowResult(OutputSchema):
    """JSON envelope for ``aeat config auth diagnostics show``.

    Mirrors :class:`AuthDiagnosticDetail`
    ``model_dump(mode='json')`` with fingerprint fields. ``extra="allow"``
    forwards every redacted diagnostic field without re-declaring the
    application model locally.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = ConfigDict(extra="allow")  # type: ignore[assignment]


@register_schema("config.auth.diagnostics.report")
class AuthDiagnosticsReportResult(OutputSchema):
    """JSON envelope for ``aeat config auth diagnostics report``.

    Projects :class:`AuthDiagnosticReportResult` after an
    operator records the phone-state outcome for an encrypted auth diagnostic.
    """

    diagnostic_id: str
    phone_state: str
    reported_at: str


# Descendiente verb result schemas


class CensoFileFactPayload(OutputSchema):
    """One candidate censal fact projected from the G313 certificate.

    ``source`` carries the non-official artefact provenance token, never
    an AEAT-verified stamp.
    """

    path: str
    value: str
    source: str


@register_schema("config.profile.censo.file")
class CensoFileIngestResult(OutputSchema):
    """Result of ``config profile censo file``: previewed or enrolled facts."""

    applied: bool
    facts: tuple[CensoFileFactPayload, ...] = ()
