"""``aeat config check`` — the workstation doctor.

For every external service, reports the active profile's capability posture and
the typed dependency outcome. A rejected condition is resolved against the live
action catalogue or carries an explicit closed outcome. The command exits
non-zero when a capability the profile opted into has a missing dependency.
Named ``check`` because the older ``doctor`` command path is retired.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import typer

from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.capabilities import ServiceCapability

if TYPE_CHECKING:
    from ....application.provisioning import ContentionSnapshot, DependencyStatus, HardwareProfile
from ....core.i18n import tr
from .._common import emit_envelope, resolve_cli_precondition_action
from ._check_payloads import CheckDependencyPayload, CheckPreflightPayload, ConfigCheckResult
from .status_rendering import precondition_action_lines


def _dependency_payload(status: DependencyStatus) -> CheckDependencyPayload:
    """Project an application dependency outcome through the one CLI resolver."""
    return CheckDependencyPayload(
        service=status.service,
        available=status.available,
        facts=status.facts,
        precondition_action=(
            resolve_cli_precondition_action(status.precondition_verdict)
            if status.precondition_verdict is not None
            else None
        ),
    )


def _dependency_text_lines(payload: CheckDependencyPayload) -> tuple[str, ...]:
    """Render one dependency DTO from its facts and resolved outcome."""
    mark = tr("cli.config.check.available" if payload.available else "cli.config.check.missing")
    lines = [f"{tr('cli.config.check.dependency_label')}\t{payload.service}\t{mark}"]
    lines.extend(
        f"{payload.service}.facts.{key}\t{json.dumps(value, ensure_ascii=False, sort_keys=True)}"
        for key, value in sorted(payload.facts.items())
    )
    lines.extend(f"{payload.service}.{line}" for line in precondition_action_lines(payload.precondition_action))
    return tuple(lines)


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
    from ....application.provisioning import assess_model_load_contention, select_model_for_role
    from ....core.model_catalogue import ModelRole

    assessable = select_model_for_role(ModelRole.VISION_TRANSCRIPTION, profile=profile).assessable_load
    if assessable is None:
        return None
    runtime_id, required_bytes = assessable
    return assess_model_load_contention(runtime_id, required_bytes, profile=profile)


def config_check(ctx: typer.Context) -> None:
    """Report external-dependency availability + the active profile's capability posture."""
    from ....adapters.outbound.storage.path_budget import windows_worst_case_object_path_suffix_length
    from ....application.preflight import run_preflight_checks
    from ....application.provisioning import (
        probe_hardware_profile,
        probe_local_inference_hardware,
        probe_local_model_provisioning,
        probe_model_runtime_hardware_floor,
        probe_ollama_vision,
        probe_optional_extras,
        probe_playwright_browser,
    )
    from ....application.user_profile.capabilities import resolve_active_capability
    from ....core.config import load_settings
    from ._check_hardware_rows import contention_row

    profile_id = resolve_active_bucket_id()

    capabilities = []
    for cap in ServiceCapability:
        decision = resolve_active_capability(cap)
        capabilities.append(
            {"capability": cap.value, "enabled": decision.enabled, "source": decision.source.value},
        )
    cap_enabled = {row["capability"]: row["enabled"] for row in capabilities}

    ollama = probe_ollama_vision()
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
    dependency_payloads = tuple(
        _dependency_payload(status)
        for status in (ollama, hardware_floor, hardware, contention, provisioning, playwright, *extras)
    )
    # Keep the nested strict DTO instances intact until the one final
    # envelope serialization. A JSON dump here turns tuple/enum action
    # fields into primitives before ConfigCheckResult validates them.
    dependencies = list(dependency_payloads)
    # Per-provider cert/clave health, storage/corpus/env preflight, and
    # registry referential integrity. Report-only: a red preflight row is
    # surfaced for operator visibility but does not, on its own, flip the
    # capability/dependency exit contract below.
    # The worst-case object-path suffix is measured from the on-disk grammar the
    # storage adapter owns, so it is supplied here at the composition root rather
    # than reached for from the application layer.
    preflight = [
        CheckPreflightPayload(
            check=row.check,
            healthy=row.healthy,
            severity=row.severity,
            facts=row.facts,
            precondition_action=(
                resolve_cli_precondition_action(row.precondition_verdict)
                if row.precondition_verdict is not None
                else None
            ),
        )
        for row in run_preflight_checks(
            object_path_suffix_length=windows_worst_case_object_path_suffix_length(),
        )
    ]
    extra_available = {status.service: status.available for status in extras}

    issues: list[str] = []
    if cap_enabled[ServiceCapability.LLM_VISION.value] and not ollama.available:
        issues.append(ollama.service)
    if cap_enabled[ServiceCapability.GOOGLE_EXPORT.value] and not extra_available.get("extra:google", False):
        issues.append("extra:google")
    # The eligibility bar's own row. Reported in the SAME shape as the two
    # above -- the capability is on, but the layer beneath it refuses -- so
    # an operator who turned the bar on and expected off-host reading to
    # work is told which of the two switches is still closed, rather than
    # meeting a per-invocation refusal with no explanation. The capability's
    # posture itself is already rendered by the loop above; this is the
    # inconsistency between it and the deployment flag.
    if cap_enabled[ServiceCapability.CLOUD_EVIDENCE_UPLOAD.value] and not (
        load_settings().cadrumo_evidence_cloud_upload_permitted
    ):
        issues.append("cloud_evidence_upload:deployment_permission")

    ok = not issues
    result = ConfigCheckResult.model_validate(
        {
            "profile_id": profile_id,
            "ok": ok,
            "capabilities": capabilities,
            "dependencies": dependencies,
            "preflight": preflight,
            "issues": issues,
        },
    )
    lines = [f"{tr('cli.config.check.profile_label')}\t{profile_id or '-'}"]
    capability_label = tr("cli.config.check.capability_label")
    preflight_label = tr("cli.config.check.preflight_label")
    for cap in capabilities:
        state = tr(
            "cli.config.profile.capabilities.enabled" if cap["enabled"] else "cli.config.profile.capabilities.disabled"
        )
        lines.append(f"{capability_label}\t{cap['capability']}\t{state}\t{cap['source']}")
    for dependency in dependency_payloads:
        lines.extend(_dependency_text_lines(dependency))
    for row in preflight:
        lines.append(f"{preflight_label}\t{row.check}\t{row.severity}")
        action = row.precondition_action
        if action is not None:
            lines.extend(f"{row.check}.{line}" for line in precondition_action_lines(action))
    for issue in issues:
        lines.append(f"{tr('cli.config.check.issue_label')}\t{issue}")
    emit_envelope(ctx, command="config.check", result=result, lines=tuple(lines))
    if not ok:
        raise typer.Exit(code=2)


__all__ = ["config_check"]
