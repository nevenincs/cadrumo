"""Canonical profile capability and workstation health report assembly.

Dependency, capability, contention and preflight services retain their algorithms.
This report runs inside the authenticated profile worker and only reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from ..core.bucket_pointer import require_active_bucket_id
from ..core.capabilities import ServiceCapability
from .auth.operator_probe_ports import OperatorProbePorts
from .preflight import PreflightCheck, run_preflight_checks
from .provisioning import DependencyStatus, HardwareProfile
from .provisioning_runtime import ContentionSnapshot
from .user_profile.access_contracts import AccessDenialCode
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
    *, profile_id: UUID, operator_probe_ports: OperatorProbePorts, object_path_suffix_length: int
) -> WorkstationCheckReport:
    """Assemble the existing report for exactly the authenticated profile."""
    capabilities: list[CapabilityDecision] = []
    for capability in ServiceCapability:
        require_workstation_profile(profile_id)
        capabilities.append(resolve_active_capability(capability))
    enabled = {row.capability.value: row.enabled for row in capabilities}
    require_workstation_profile(profile_id)
    dependencies, vision_reader, extras = _probe_dependency_statuses()
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
        issues=tuple(_check_issues(capabilities=enabled, vision_reader=vision_reader, extras=extras)),
    )


def _assess_selected_model_load(profile: HardwareProfile) -> ContentionSnapshot | None:
    """Return the contention verdict for the model this machine would load, or ``None``.

    Answers the question the operator actually has -- "could I load the model
    this machine would pick?" -- rather than asking about a model named here,
    which would report on something the product would never load.

    ``None`` when selection resolves to no candidate: there is then no load to
    assess, and inventing a requirement to assess against would report a
    shortfall against a model that does not exist.

    Reads only. Selection, the hardware profile and the runtime's resident set
    are all measurements; nothing on this path loads or pulls a model.
    """
    from ..core.model_catalogue import ModelRole
    from .provisioning import select_model_for_role
    from .provisioning_runtime import assess_model_load_contention

    assessable = select_model_for_role(ModelRole.VISION_TRANSCRIPTION, profile=profile).assessable_load
    if assessable is None:
        return None
    runtime_id, required_bytes = assessable
    return assess_model_load_contention(runtime_id, required_bytes, profile=profile)


def _probe_dependency_statuses() -> tuple[
    tuple[DependencyStatus, ...],
    DependencyStatus,
    tuple[DependencyStatus, ...],
]:
    from ..core.model_catalogue import ModelRole
    from .local_reader import EXTRACTION_READER_ROLES, probe_local_reader
    from .provisioning import (
        probe_hardware_profile,
        probe_local_inference_hardware,
        probe_local_model_provisioning,
        probe_model_runtime_hardware_floor,
        probe_optional_extras,
    )
    from .provisioning_browser import probe_playwright_browser
    from .provisioning_runtime import read_installed_models
    from .workstation_contention import contention_row

    # The same per-role reader probe `config provision status` and the ingestion
    # lanes consult, over ONE inventory read, so the doctor cannot report a
    # reader ready that the status surface reports missing.
    inventory = read_installed_models()
    readers = tuple(probe_local_reader(role, installed=inventory) for role in EXTRACTION_READER_ROLES)
    vision_reader = next(
        status
        for role, status in zip(EXTRACTION_READER_ROLES, readers, strict=True)
        if role is ModelRole.VISION_TRANSCRIPTION
    )
    hardware_floor = probe_model_runtime_hardware_floor()
    # Probed ONCE and threaded into both rows. Two probes would read the
    # machine at two moments and could disagree, so the profile the
    # contention verdict was computed against is the profile reported
    # beside it.
    profile = probe_hardware_profile()
    hardware = probe_local_inference_hardware(profile)
    contention = contention_row(_assess_selected_model_load(profile))
    playwright = probe_playwright_browser()
    provisioning = probe_local_model_provisioning()
    extras = probe_optional_extras()
    statuses = (*readers, hardware_floor, hardware, contention, provisioning, playwright, *extras)
    return statuses, vision_reader, extras


def _check_issues(
    *,
    capabilities: dict[str, bool],
    vision_reader: DependencyStatus,
    extras: tuple[DependencyStatus, ...],
) -> list[str]:
    from ..core.config import load_settings

    extra_available = {status.service: status.available for status in extras}
    issues: list[str] = []
    if capabilities[ServiceCapability.LLM_VISION.value] and not vision_reader.available:
        issues.append(vision_reader.service)
    if capabilities[ServiceCapability.GOOGLE_EXPORT.value] and not extra_available.get("extra:google", False):
        issues.append("extra:google")
    # The eligibility bar's own row. Reported in the SAME shape as the two
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
