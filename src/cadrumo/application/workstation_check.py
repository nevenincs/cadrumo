"""Canonical profile capability and workstation health report assembly.

Dependency, capability and preflight services retain their algorithms.
This report runs inside the authenticated profile worker and only reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ..core.bucket_pointer import require_active_bucket_id
from ..core.capabilities import ServiceCapability
from .auth.operator_probe_ports import OperatorProbePorts
from .preflight import PreflightCheck, run_preflight_checks
from .workstation_probes import DependencyStatus
from .user_profile.access_errors import ProfileAccessRefusedError
from .user_profile.capabilities import CapabilityDecision, resolve_active_capability


@dataclass(frozen=True, slots=True)
class WorkstationCheckReport:
    """Complete canonical facts before their frontend-specific presentation."""

    profile_id: UUID
    capabilities: tuple[CapabilityDecision, ...]
    dependencies: tuple[DependencyStatus, ...]
    preflight: tuple[PreflightCheck, ...]
    issues: tuple[str, ...]


def require_workstation_profile(profile_id: UUID) -> None:
    """Require the exact immutable worker profile before a private report stage."""
    if require_active_bucket_id() != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def run_workstation_check(
    *,
    profile_id: UUID,
    operator_probe_ports: OperatorProbePorts,
    object_path_suffix_length: int,
) -> WorkstationCheckReport:
    """Assemble the existing report for exactly the authenticated profile."""
    capabilities: list[CapabilityDecision] = []
    for capability in ServiceCapability:
        require_workstation_profile(profile_id)
        capabilities.append(resolve_active_capability(capability))
    enabled = {row.capability.value: row.enabled for row in capabilities}
    require_workstation_profile(profile_id)
    dependencies, extras = _probe_dependency_statuses()
    require_workstation_profile(profile_id)
    preflight = tuple(
        run_preflight_checks(
            object_path_suffix_length=object_path_suffix_length, operator_probe_ports=operator_probe_ports
        )
    )
    require_workstation_profile(profile_id)
    return WorkstationCheckReport(
        profile_id=profile_id,
        capabilities=tuple(capabilities),
        dependencies=dependencies,
        preflight=preflight,
        issues=tuple(_check_issues(capabilities=enabled, extras=extras)),
    )


def _probe_dependency_statuses() -> tuple[tuple[DependencyStatus, ...], tuple[DependencyStatus, ...]]:
    from .browser_location import probe_playwright_browser
    from .workstation_probes import (
        probe_hardware_profile,
        probe_local_inference_hardware,
        probe_optional_extras,
    )

    # Every role reads with the model the person picked, which the agent
    # service answers; whether a load fits is the agent's answer when it loads
    # the model. The hardware row reports what was measured and judges nothing.
    hardware = probe_local_inference_hardware(probe_hardware_profile())
    playwright = probe_playwright_browser()
    extras = probe_optional_extras()
    statuses = (hardware, playwright, *extras)
    return statuses, extras


def _check_issues(
    *,
    capabilities: dict[str, bool],
    extras: tuple[DependencyStatus, ...],
) -> list[str]:
    from ..core.config import load_settings

    extra_available = {status.service: status.available for status in extras}
    issues: list[str] = []
    if capabilities[ServiceCapability.GOOGLE_EXPORT.value] and not extra_available.get("extra:google", False):
        issues.append("extra:google")
    # The eligibility bar's own row. Reported in the SAME shape as the one
    # above -- the capability is on, but the layer beneath it refuses -- so
    # an operator who turned the bar on and expected off-host reading to
    # work is told which of the two switches is still closed, rather than
    # meeting a per-invocation refusal with no explanation. The capability's
    # posture itself is rendered by the capability loop; this is the
    # inconsistency between it and the deployment flag.
    if capabilities[ServiceCapability.CLOUD_EVIDENCE_UPLOAD.value] and not (
        load_settings().cadrumo_evidence_cloud_upload_permitted
    ):
        issues.append("cloud_evidence_upload:deployment_permission")
    return issues
