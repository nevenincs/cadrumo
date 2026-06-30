"""Typed ``--json`` payload schemas for ``aeat config check``.

The command is the workstation doctor: it reports every
:class:`~aeat.core.ServiceCapability` resolved for the active profile beside the
external dependency probes that must be provisioned for opted-in capabilities.
These strict :class:`~aeat.entrypoints.cli._schemas.OutputSchema` subclasses
document only the transport shape registered with
:func:`~aeat.entrypoints.cli._schemas.register_schema` and emitted through
:class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope` by
:func:`~aeat.entrypoints.cli._common._emit_envelope`. Capability semantics live
in :mod:`~aeat.application.user_profile`, and provisioning semantics live in
:mod:`~aeat.application.provisioning`.
"""

from __future__ import annotations

from .._schemas import OutputSchema, register_schema


class CheckCapabilityPayload(OutputSchema):
    """One resolved capability posture for the active profile.

    ``capability`` is a :class:`~aeat.core.ServiceCapability` value. ``enabled``
    and ``source`` mirror
    :class:`~aeat.application.user_profile.CapabilityDecision`, with the source
    rendered from :class:`~aeat.application.user_profile.CapabilitySource` so the
    doctor can distinguish profile facts, defaults, global settings, and safety
    floors without owning that resolution logic.
    """

    capability: str
    enabled: bool
    source: str


class CheckDependencyPayload(OutputSchema):
    """One external dependency availability row.

    Nested in
    :class:`~aeat.entrypoints.cli._config._check_payloads.ConfigCheckResult`
    and mirrors
    :class:`~aeat.application.provisioning.DependencyStatus` rows from
    :func:`~aeat.application.provisioning.probe_ollama_vision`,
    :func:`~aeat.application.provisioning.probe_subprocess_providers`,
    :func:`~aeat.application.provisioning.probe_playwright_browser`, and
    :func:`~aeat.application.provisioning.probe_optional_extras`. ``remediation``
    is populated only when the probe can name a concrete operator action.
    """

    service: str
    available: bool
    detail: str = ""
    remediation: str = ""


@register_schema("config.check")
class ConfigCheckResult(OutputSchema):
    """JSON envelope for ``aeat config check``.

    Combines :func:`~aeat.application.user_profile.resolve_active_capability`
    decisions in
    :class:`~aeat.entrypoints.cli._config._check_payloads.CheckCapabilityPayload`
    rows with
    :class:`~aeat.application.provisioning.DependencyStatus` projections in
    :class:`~aeat.entrypoints.cli._config._check_payloads.CheckDependencyPayload`
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
    issues: list[str] = []
