"""Typed ``--json`` payload schemas for ``aeat config check``.

The command is the workstation doctor: it reports every
:class:`ServiceCapability` resolved for the active profile beside the
external dependency probes that must be provisioned for opted-in capabilities.
These strict :class:`OutputSchema` subclasses
document only the transport shape referenced by production-authored CommandSpec
as deferred public schema targets and emitted through
:class:`SchemaEnvelope` by
:func:`emit_envelope`. Capability semantics live
in :mod:`user_profile`, and provisioning semantics live in
:mod:`provisioning`.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import Field, model_validator

from ....application.preflight import HealthSeverity
from ....core.identity import ProfileId
from ....core.json_contract import OutputSchema, ResolvedPreconditionAction

ProvisioningFactPayload = Mapping[str, str | int | bool]
"""Locale-neutral scalar facts projected from a provisioning outcome."""


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
    :func:`probe_playwright_browser`, and
    :func:`probe_optional_extras`. The application-owned facts and verdict are
    the full dependency explanation; this boundary resolves the verdict against
    the live action surface without recreating a command string.
    """

    service: str = Field(min_length=1)
    available: bool
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


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
    (``ok`` / ``warn`` / ``error``). Machine facts are preserved without
    forwarding producer prose. Until S66 gives these rows typed verdicts, an
    unhealthy row carries an explicit no-recovery outcome. These rows are reported
    for operator visibility and do not, on their own, change the
    command's ``ok`` verdict — the capability/dependency contract owns
    the exit code.
    """

    check: str = Field(min_length=1)
    healthy: bool
    severity: HealthSeverity
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None

    @model_validator(mode="after")
    def _unhealthy_rows_have_one_outcome(self) -> CheckPreflightPayload:
        if self.healthy and self.precondition_action is not None:
            raise ValueError("healthy preflight rows cannot carry a recovery projection")
        if not self.healthy and self.precondition_action is None:
            raise ValueError("unhealthy preflight rows require one resolved precondition outcome")
        return self


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

    profile_id: ProfileId | None = None
    ok: bool
    capabilities: list[CheckCapabilityPayload] = []
    dependencies: list[CheckDependencyPayload] = []
    preflight: list[CheckPreflightPayload] = []
    issues: list[str] = []
