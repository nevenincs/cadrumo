"""Typed ``--json`` payload schemas for config CLI commands.

Every registered class is a strict :class:`OutputSchema` transport shape for a
config command result. Field sets match the production emit sites in
:mod:`_config` and its submodules; sequence fields use ``list`` so JSON-mode
pydantic dumps stay arrays. Application services remain authoritative for
profile, auth, apoderado, repair, diagnostics, and workflow semantics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ConfigDict

from ._schemas import OutputSchema, register_schema

if TYPE_CHECKING:
    from ...application.auth import AuthConfigureResult

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
    """

    name: str
    bucket_id: str
    active: bool


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


# P05 — repair verb result schemas


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


@register_schema("config.switch")
class ConfigSwitchResult(OutputSchema):
    """JSON envelope for ``aeat config switch``.

    Reports the profile name that became the active bucket pointer after the
    workflow-state update; no profile facts are emitted on this mutation.
    """

    active_profile: str


@register_schema("config.rekey")
class ConfigRekeyResult(OutputSchema):
    """JSON envelope for ``aeat config rekey``.

    Reports the secure-store directory and whether local encrypted material was
    re-keyed. Key material and recovery phrases never enter this payload.
    """

    secret_store_dir: str
    rekeyed: bool


@register_schema("config.recover")
class ConfigRecoverResult(OutputSchema):
    """JSON envelope for ``aeat config recover``.

    Reports the recovery file used and the local secret-store directory that was
    recovered, without serialising the recovery secret itself.
    """

    recovery_path: str
    secret_store_dir: str
    recovered: bool


@register_schema("config.show_recovery")
class ConfigShowRecoveryResult(OutputSchema):
    """JSON envelope for ``aeat config show-recovery``.

    The mnemonic is optional and appears only when the command intentionally
    rotates or reveals recovery material. The path and enrolment flags remain
    the stable machine-readable status fields.
    """

    recovery_path: str
    recovery_enrolled: bool
    rotated: bool = False
    mnemonic: str | None = None


@register_schema("config.verify_recovery")
class ConfigVerifyRecoveryResult(OutputSchema):
    """JSON envelope for ``aeat config verify-recovery``.

    Confirms whether the supplied recovery material matched the encrypted local
    recovery record; the secret phrase is not echoed back.
    """

    recovery_path: str
    verified: bool


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


@register_schema("config.reset")
class ConfigResetResult(OutputSchema):
    """JSON envelope for ``aeat config reset``.

    Reports the reset scope, removed profile ids, and whether local auth session
    state was removed. It does not include deleted profile records or auth
    secrets.
    """

    scope: str
    removed_profile_ids: list[str]
    removed_auth_session: bool


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


@register_schema("config.bucket.history")
class BucketHistoryResult(OutputSchema):
    """JSON envelope for ``aeat config profile history``.

    The envelope token ``config.bucket.history`` is a stable machine API and
    is intentionally retained after the operator-facing verb moved from
    ``config bucket history`` to ``config profile history`` (D1 family).
    """

    operation: str
    bucket_id: str
    event_types: list[str] | None = None
    since: str | None = None
    until: str | None = None
    object_id: str | None = None
    actor: str | None = None
    events: list[dict[str, object]]


# Profile wizard / lifecycle verb result schemas


@register_schema("config.profile.create")
class ConfigProfileCreateResult(OutputSchema):
    """JSON envelope for ``aeat config profile create``.

    The post-create next-step hint is surfaced on the envelope ``notices``
    channel, not as a bespoke ``next`` field. The lifecycle mutation itself is
    owned by :class:`ProfileLifecycleService`.
    """

    profile_name: str
    status: str
    active_profile: str | None = None


@register_schema("config.profile.edit")
class ConfigProfileEditResult(OutputSchema):
    """JSON envelope for ``aeat config profile edit``.

    The post-edit next-step hint is surfaced on the envelope ``notices``
    channel, not as a bespoke ``next`` field. The payload reports only the
    edited profile name and mutation status; edited facts remain in secure
    profile storage.
    """

    profile_name: str
    status: str


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
    # bundle_schema_version is an int (SUPPORTED_BUNDLE_SCHEMA_VERSIONS
    # is `frozenset[int]`); the export handler passes it through verbatim.
    schema_version: int


@register_schema("config.profile.subject_access_request")
class ConfigProfileSubjectAccessRequestResult(OutputSchema):
    """JSON envelope for ``aeat config profile subject-access-request``.

    A GDPR right-of-access export: the same portable bundle
    ``config profile export`` produces, framed as the operator's own
    personal-data archive. Reports the profile identity, output path, bundle
    schema version, and the machine-readable catalogue of the personal-data
    categories the archive carries so the subject can see what is held.
    """

    profile_id: str
    display_name: str
    out: str
    schema_version: int
    data_categories: list[str]


@register_schema("config.profile.import")
class ConfigProfileImportResult(OutputSchema):
    """JSON envelope for ``aeat config profile import``.

    Projects :class:`ProfileImportResult` down to
    the imported profile identity, label, and bundle schema version.
    """

    profile_id: str
    display_name: str
    schema_version: int


@register_schema("config.profile.logout")
class ConfigProfileLogoutResult(OutputSchema):
    """JSON envelope for ``aeat config profile logout``.

    Confirms which profile's local session was logged out and echoes any
    remaining active pointer. ``session_warning`` carries local secure-storage
    advice without exposing session contents.
    """

    logged_out_profile: str
    active_profile: str | None = None
    session_warning: str


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
    registered, which backend holds it, and whether the call rotated an
    existing secret.
    """

    name: str
    backend: str = ""
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


class ProfileDescendientePayload(OutputSchema):
    """One declared descendant row in the ``config profile descendiente`` surface.

    Mirrors :class:`~cadrumo.domain.contribuyente.DescendantInfo` as plain JSON;
    ``index`` is the 0-based position :func:`~cadrumo.domain.contribuyente.descendant_list_from_facts`
    assigns, the same index ``descendiente remove`` addresses.
    """

    index: int
    birth_date: str
    adoption_date: str | None = None
    discapacidad_grado: int | None = None
    convive_con_contribuyente: bool
    custodia_compartida: bool
    nif: str | None = None


@register_schema("config.profile.descendiente.add")
class ConfigProfileDescendienteAddResult(OutputSchema):
    """JSON envelope for ``aeat config profile descendiente add``."""

    profile: str
    added: int
    total: int


@register_schema("config.profile.descendiente.list")
class ConfigProfileDescendienteListResult(OutputSchema):
    """JSON envelope for ``aeat config profile descendiente list``."""

    profile: str
    total: int
    descendientes: list[ProfileDescendientePayload] = []


@register_schema("config.profile.descendiente.remove")
class ConfigProfileDescendienteRemoveResult(OutputSchema):
    """JSON envelope for ``aeat config profile descendiente remove``."""

    profile: str
    removed_index: int
    total: int


@register_schema("config.profile.sandbox.create")
class ConfigProfileSandboxCreateResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox create``.

    Reports the new sandbox bucket identity and label; the sandbox is now the
    active profile. ``seeded_from`` names the live profile whose facts were
    copied in, or ``None`` when the sandbox started empty.
    """

    bucket_id: str
    label: str
    seeded_from: str | None = None


@register_schema("config.profile.sandbox.list")
class ConfigProfileSandboxListResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox list``.

    Reuses :class:`ProfilePointerPayload` rows, filtered to buckets whose
    label carries the reserved sandbox prefix.
    """

    active_profile: str | None = None
    sandboxes: list[ProfilePointerPayload]


@register_schema("config.profile.sandbox.use")
class ConfigProfileSandboxUseResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox use``.

    Same shape as :class:`ConfigSwitchResult`; registered under its own
    command path since ``sandbox use`` delegates to the canonical
    select-lifecycle-span primitive rather than the root ``config switch``
    command.
    """

    active_profile: str


class SandboxNamespacePayload(OutputSchema):
    """One secure-object namespace row in a sandbox discard preview.

    Mirrors :class:`~cadrumo.application.bucket_maintenance.SandboxNamespaceInventoryRow`:
    only the namespace name and stored-row count, never decrypted payload
    material.
    """

    namespace: str
    row_count: int


@register_schema("config.profile.sandbox.discard")
class ConfigProfileSandboxDiscardResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox discard``.

    Covers both the ``--dry-run`` preview branch (``dry_run=True``, no
    mutation — ``namespaces`` lists what would be removed) and the confirmed
    erase branch (``dry_run=False`` — ``previous_label`` reports the erased
    sandbox's prior label; ``namespaces`` stays empty).
    """

    dry_run: bool = False
    bucket_id: str
    previous_label: str | None = None
    namespaces: list[SandboxNamespacePayload] = []


@register_schema("config.profile.sandbox.prune")
class ConfigProfileSandboxPruneResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox prune``.

    Covers the ``--dry-run`` preview branch (``sandboxes`` names every
    sandbox that would be discarded, nothing removed) and the confirmed
    branch (``discarded`` names every sandbox actually erased). Both
    branches report the total count considered.
    """

    dry_run: bool = False
    total: int
    sandboxes: list[str] = []
    discarded: list[str] = []


@register_schema("config.profile.sandbox.archive")
class ConfigProfileSandboxArchiveResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox archive``.

    Reports the archived sandbox's bucket identity and label. Unlike
    ``discard``, the sandbox bucket, manifest, and encrypted record all
    survive intact — the sandbox merely drops off the live
    ``sandbox list`` surface until ``sandbox restore`` reactivates it.
    """

    bucket_id: str
    label: str


@register_schema("config.profile.sandbox.restore")
class ConfigProfileSandboxRestoreResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox restore``.

    Reports the restored sandbox's bucket identity and label. The
    symmetric inverse of ``sandbox archive``.
    """

    bucket_id: str
    label: str


class SandboxDiskUsageSubdirPayload(OutputSchema):
    """One on-disk subdirectory row in a sandbox disk-usage report.

    Mirrors :class:`~cadrumo.application.bucket_maintenance.BucketDiskUsageSubdirRow`:
    a fixed-layout subdirectory name (``db``, ``blobs``, ``audit``) plus its
    summed regular-file byte total and file count.
    """

    subdir: str
    total_bytes: int
    file_count: int


class SandboxDiskUsagePayload(OutputSchema):
    """One sandbox's disk-usage row within a ``sandbox usage`` report."""

    label: str
    bucket_id: str
    total_bytes: int
    subdirs: list[SandboxDiskUsageSubdirPayload]


@register_schema("config.profile.sandbox.usage")
class ConfigProfileSandboxUsageResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox usage``.

    Reports the on-disk footprint of one named sandbox, or of every sandbox
    at once when no name is given (``total_bytes`` then sums across every
    listed sandbox). The measurement reads only filesystem metadata — never
    decrypted secure-object content — via
    :meth:`~cadrumo.application.bucket_maintenance.BucketMaintenanceService`.disk_usage.
    """

    total_bytes: int
    sandboxes: list[SandboxDiskUsagePayload]


@register_schema("config.profile.sandbox.merge")
class ConfigProfileSandboxMergeResult(OutputSchema):
    """JSON envelope for ``aeat config profile sandbox merge``.

    Reports the promoted scope, the source sandbox and target profile
    labels, and the per-category row counts merged via
    :func:`~cadrumo.application.bucket_maintenance.merge_sandbox`. A re-run
    against unchanged sandbox content reports the same counts (an
    idempotent no-op write into the target, never a duplicate row).
    """

    scope: str
    source_label: str
    target_label: str
    merged_counts: dict[str, int]
