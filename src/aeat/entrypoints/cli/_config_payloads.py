"""Typed ``--json`` payload schemas for config CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every config-command surface this module covers.

Field sets match the production payload dicts constructed in
``_config/__init__.py`` at their emit sites. Optional fields cover
multi-branch payload shapes (e.g. repair.quarantine has a no-active-profile
branch, a dry-run preview branch, and a live branch; config.status has
several readiness states).

All sequence fields use ``list`` rather than ``tuple`` because
``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays.
"""

from __future__ import annotations

from pydantic import ConfigDict

from ._schemas import OutputSchema, register_schema

# ---------------------------------------------------------------------------
# Shared sub-models (not registered — used as nested types)
# ---------------------------------------------------------------------------


class QuarantineNamespacePayload(OutputSchema):
    """One namespace row in a quarantine report."""

    namespace: str
    readable: int
    unreadable: int


class WorkflowFingerprintPayload(OutputSchema):
    """Serialised workflow-state fingerprint nested in repair.reset_state."""

    schema_version: str | None = None
    written_at: str | None = None
    byte_length: int | None = None
    reason_class: str
    recovered_bucket_id: str | None = None


class ProfilePointerPayload(OutputSchema):
    """One profile entry in the config.list result."""

    name: str
    bucket_id: str
    active: bool


class ProfileIssuePayload(OutputSchema):
    """One validation issue from ProfileValidationService."""

    severity: str
    code: str
    path: str | None = None
    message: str


class ProfileFactPayload(OutputSchema):
    """One fact key/value pair in config.profile.show."""

    path: str
    value: str


# ---------------------------------------------------------------------------
# P05 — repair verb result schemas
# ---------------------------------------------------------------------------


@register_schema("config.repair.logs")
class RepairLogsResult(OutputSchema):
    """JSON envelope for ``aeat config repair logs``."""

    path: str
    lines: list[str]


@register_schema("config.repair.quarantine")
class RepairQuarantineResult(OutputSchema):
    """JSON envelope for ``aeat config repair quarantine``.

    Covers the no-active-profile guard, the dry-run preview path, and
    the live quarantine path. Optional fields accommodate each branch.
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


@register_schema("config.repair.reset_state")
class RepairResetStateResult(OutputSchema):
    """JSON envelope for ``aeat config repair reset-state``.

    Covers the no-active-profile guard, the dry-run preview path, and
    the live reset path.
    """

    # No-active-profile branch
    reset: bool | None = None
    reason: str | None = None
    # Dry-run / live branches
    dry_run: bool | None = None
    fingerprint: WorkflowFingerprintPayload | None = None


@register_schema("config.repair.connectivity")
class RepairConnectivityResult(OutputSchema):
    """JSON envelope for ``aeat config repair connectivity``."""

    target: str
    status: dict[str, object]


# ---------------------------------------------------------------------------
# P06 — config and profile verb result schemas
# ---------------------------------------------------------------------------


@register_schema("config.list")
class ConfigListResult(OutputSchema):
    """JSON envelope for ``aeat config profile list``.

    Note: ``config_list`` is registered on the ``profile list`` sub-command
    which maps to the CLI path ``config.list`` (the profile sub-app carries
    the list verb).
    """

    active_profile: str | None = None
    profiles: list[ProfilePointerPayload]


@register_schema("config.profile.switch")
class ConfigProfileSwitchResult(OutputSchema):
    """JSON envelope for ``aeat config profile switch``."""

    active_profile: str


@register_schema("config.profile.show")
class ConfigProfileShowResult(OutputSchema):
    """JSON envelope for ``aeat config profile show``.

    Covers the missing-record branch, the unreadable-record branch, and
    the success path. Optional fields accommodate each branch.
    """

    profile_id: str | None = None
    display_name: str | None = None
    status: str | None = None
    valid: bool | None = None
    schema_version: str | None = None
    issues: list[ProfileIssuePayload] | None = None
    facts: list[ProfileFactPayload] | None = None
    # Error / readiness branches
    registered_bucket: bool | None = None
    profile_record_present: bool | None = None
    configured: bool | None = None
    error: str | None = None
    next_action: str | None = None
    bucket_id: str | None = None


@register_schema("config.profile.delete")
class ConfigProfileDeleteResult(OutputSchema):
    """JSON envelope for ``aeat config profile delete``."""

    profile_id: str
    display_name: str
    status: str
    active_profile_cleared: bool


@register_schema("config.profile.duplicate")
class ConfigProfileDuplicateResult(OutputSchema):
    """JSON envelope for ``aeat config profile duplicate``."""

    source_profile_id: str
    target_profile_id: str
    display_name: str


@register_schema("config.status")
class ConfigStatusResult(OutputSchema):
    """JSON envelope for ``aeat config status``.

    Covers all readiness branches: none, dangling_pointer,
    missing/unreadable profile record, incomplete config, and ready.
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
    """JSON envelope for ``aeat config reset``."""

    scope: str
    removed_profile_ids: list[str]
    removed_auth_session: bool


# ---------------------------------------------------------------------------
# P07 — auth and bucket verb result schemas
# ---------------------------------------------------------------------------


@register_schema("config.auth.providers")
class AuthProvidersResult(OutputSchema):
    """JSON envelope for ``aeat config auth providers``."""

    providers: list[dict[str, object]]


@register_schema("config.auth.configure")
class AuthConfigureResult(OutputSchema):
    """JSON envelope for ``aeat config auth configure``.

    Field set mirrors :class:`AuthConfigureReport` from the application layer.
    All optional fields accommodate conditional display branches (e.g.
    clave_movil identity alignment fields).
    """

    provider: str
    file: str
    status: str | None = None
    complete: bool
    incomplete_reason: str | None = None
    active_profile: str | None = None
    profile_tax_id_present: bool | None = None
    provider_identity_present: bool | None = None
    identity_alignment: str | None = None
    identity_alignment_detail: str | None = None
    next_action: str | None = None


@register_schema("config.auth.status")
class AuthStatusResult(OutputSchema):
    """JSON envelope for ``aeat config auth status``.

    The application ``AuthStatusResult`` model evolves independently;
    ``extra="allow"`` ensures any additional fields pass through without
    re-declaring every provider-specific key here.
    """

    model_config = ConfigDict(extra="allow")  # type: ignore[assignment]


@register_schema("config.auth.test")
class AuthTestResult(OutputSchema):
    """JSON envelope for ``aeat config auth test``.

    Thin envelope; the application model carries all provider-specific
    fields. ``extra="allow"`` forwards them without re-declaration.
    """

    model_config = ConfigDict(extra="allow")  # type: ignore[assignment]


@register_schema("config.auth.login")
class AuthLoginResult(OutputSchema):
    """JSON envelope for ``aeat config auth login``.

    Thin envelope; the application model carries provider-specific
    login fields. ``extra="allow"`` forwards them without re-declaration.
    """

    model_config = ConfigDict(extra="allow")  # type: ignore[assignment]


@register_schema("config.auth.clear")
class AuthClearResult(OutputSchema):
    """JSON envelope for ``aeat config auth clear``."""

    removed_sessions: int
    cleared_workflow_state: bool
    cleared_locks: int


@register_schema("config.apoderado.check")
class ApoderadoCheckResult(OutputSchema):
    """JSON envelope for ``aeat config apoderado check``."""

    bucket_id: str
    configured: bool
    represented_nif: str | None = None
    granted_scopes: list[str] | None = None


@register_schema("config.bucket.history")
class BucketHistoryResult(OutputSchema):
    """JSON envelope for ``aeat config bucket history``."""

    operation: str
    bucket_id: str
    event_types: list[str] | None = None
    since: str | None = None
    until: str | None = None
    object_id: str | None = None
    actor: str | None = None
    events: list[dict[str, object]]
