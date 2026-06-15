"""Typed ``--json`` payload schemas for ``aeat config check`` (the workstation doctor).

Reports, for every external service, the active profile's capability posture, the
dependency availability, and the remediation for any gap. Strict
:class:`OutputSchema` subclasses registered with :func:`register_schema`.
"""

from __future__ import annotations

from .._schemas import OutputSchema, register_schema


class CheckCapabilityPayload(OutputSchema):
    """One capability's resolved posture for the active profile (nested)."""

    capability: str
    enabled: bool
    source: str


class CheckDependencyPayload(OutputSchema):
    """One external dependency's availability (nested)."""

    service: str
    available: bool
    detail: str = ""
    remediation: str = ""


@register_schema("config.check")
class ConfigCheckResult(OutputSchema):
    """JSON envelope for ``aeat config check``.

    ``ok`` is false (and the command exits non-zero) when a capability the profile
    opted into has a missing dependency — the operator asked for a service that is
    not provisioned. ``issues`` names each such gap with its fix.
    """

    profile_id: str | None = None
    ok: bool
    capabilities: list[CheckCapabilityPayload] = []
    dependencies: list[CheckDependencyPayload] = []
    issues: list[str] = []
