"""Typed ``--json`` payload schemas for ``aeat config check``.

The command is the workstation doctor: it reports every
:class:`ServiceCapability` resolved for the active profile beside the
external dependency probes that must be provisioned for opted-in capabilities.
These strict :class:`OutputSchema` subclasses
document only the transport shape registered with
:func:`register_schema` and emitted through
:class:`SchemaEnvelope` by
:func:`_emit_envelope`. Capability semantics live
in :mod:`user_profile`, and provisioning semantics live in
:mod:`provisioning`.
"""

from __future__ import annotations

from pydantic import Field

from ....application.preflight import HealthSeverity
from .._schemas import OutputSchema, register_schema


class CheckCapabilityPayload(OutputSchema):
    """One resolved capability posture for the active profile.

    ``capability`` is a :class:`ServiceCapability` value. ``enabled``
    and ``source`` mirror
    :class:`CapabilityDecision`, with the source
    rendered from :class:`CapabilitySource` so the
    doctor can distinguish profile facts, defaults, global settings, and safety
    floors without owning that resolution logic.
    """

    capability: str
    enabled: bool
    source: str


class CheckDependencyPayload(OutputSchema):
    """One external dependency availability row.

    Nested in
    :class:`ConfigCheckResult`
    and mirrors
    :class:`DependencyStatus` rows from
    :func:`probe_ollama_vision`,
    :func:`probe_subprocess_providers`,
    :func:`probe_playwright_browser`, and
    :func:`probe_optional_extras`. ``remediation``
    is populated only when the probe can name a concrete operator action.
    """

    service: str = Field(min_length=1)
    available: bool
    detail: str = ""
    remediation: str = ""


class CheckPreflightPayload(OutputSchema):
    """One workstation-preflight health row.

    Nested in
    :class:`ConfigCheckResult`
    and mirrors :class:`PreflightCheck` rows
    from :func:`run_preflight_checks`: the
    per-auth-provider certificate / Cl@ve Móvil configuration health, the
    secure-storage / bundled-corpus / configuration preflight, and the
    registry referential-integrity gate. ``check`` is the stable row id
    (e.g. ``auth-provider:certificate``, ``storage:local-root``,
    ``registry:referential-integrity``); ``severity`` renders the
    :class:`HealthSeverity` verdict
    (``ok`` / ``warn`` / ``error``); ``remediation`` names the concrete
    operator action when the row is not healthy. These rows are reported
    for operator visibility and do not, on their own, change the
    command's ``ok`` verdict — the capability/dependency contract owns
    the exit code.
    """

    check: str = Field(min_length=1)
    healthy: bool
    severity: HealthSeverity
    detail: str = ""
    remediation: str = ""


@register_schema("config.check")
class ConfigCheckResult(OutputSchema):
    """JSON envelope for ``aeat config check``.

    Combines :func:`resolve_active_capability`
    decisions in
    :class:`CheckCapabilityPayload`
    rows with
    :class:`DependencyStatus` projections in
    :class:`CheckDependencyPayload`
    rows. ``ok`` is false (and the command exits
    non-zero) when a capability the profile opted into has a missing dependency,
    meaning the operator asked for a service that is not provisioned. ``issues``
    names those capability/dependency gaps while ``dependencies`` still reports
    every probe row for diagnostics.
    """

    profile_id: str | None = None
    ok: bool
    capabilities: list[CheckCapabilityPayload] = []
    dependencies: list[CheckDependencyPayload] = []
    preflight: list[CheckPreflightPayload] = []
    issues: list[str] = []
