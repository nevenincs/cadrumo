"""``aeat config check`` — the workstation doctor.

For every external service, reports the active profile's capability posture, the
dependency availability (from the typed probes), and the exact remediation for any
gap. Exits non-zero when a capability the profile opted into has a missing
dependency — the operator asked for a service that is not provisioned. Named
``check`` because the older ``doctor`` command path is retired.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from ....core import ServiceCapability, resolve_active_bucket_id

if TYPE_CHECKING:
    from ....application.provisioning import ContentionSnapshot, HardwareProfile
from ....core.i18n import tr
from .._common import _emit_envelope

# Eager import so the @register_schema decorator runs on the CLI build path.
from ._check_payloads import ConfigCheckResult


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
    from ....core import ModelRole

    selection = select_model_for_role(ModelRole.VISION_TRANSCRIPTION, profile=profile)
    if not selection.selected or selection.runtime_id is None or selection.candidate is None:
        return None
    return assess_model_load_contention(
        selection.runtime_id,
        selection.candidate.memory_requirement_bytes,
        profile=profile,
    )


def register(app: typer.Typer) -> None:
    """Attach the ``check`` command to the config ``app``."""

    @app.command("check", help=tr("cli.config.check.help"))
    def config_check(ctx: typer.Context) -> None:
        """Report external-dependency availability + the active profile's capability posture."""
        from ....adapters.outbound.storage import windows_worst_case_object_path_suffix_length
        from ....application.preflight import run_preflight_checks
        from ....application.provisioning import (
            probe_hardware_profile,
            probe_local_inference_hardware,
            probe_model_runtime_hardware_floor,
            probe_ollama_vision,
            probe_optional_extras,
            probe_playwright_browser,
        )
        from ....application.user_profile import resolve_active_capability
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
        extras = probe_optional_extras()
        dependencies = [d.model_dump() for d in (ollama, hardware_floor, hardware, contention, playwright, *extras)]
        # Per-provider cert/clave health, storage/corpus/env preflight, and
        # registry referential integrity. Report-only: a red preflight row is
        # surfaced for operator visibility but does not, on its own, flip the
        # capability/dependency exit contract below.
        # The worst-case object-path suffix is measured from the on-disk grammar the
        # storage adapter owns, so it is supplied here at the composition root rather
        # than reached for from the application layer.
        preflight = [
            row.model_dump(mode="python")
            for row in run_preflight_checks(
                object_path_suffix_length=windows_worst_case_object_path_suffix_length(),
            )
        ]
        extra_available = {status.service: status.available for status in extras}

        issues: list[str] = []
        if cap_enabled[ServiceCapability.LLM_VISION.value] and not ollama.available:
            issues.append(f"llm_vision is on but {ollama.detail}: {ollama.remediation}")
        if cap_enabled[ServiceCapability.GOOGLE_EXPORT.value] and not extra_available.get("extra:google", False):
            issues.append("google_export is on but the 'google' extra is not installed (pip install cadrumo[google])")

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
        lines = [f"{tr('cli.config.check.profile_label', default='profile')}\t{profile_id or '-'}"]
        for cap in capabilities:
            state = tr(
                "cli.config.profile.capabilities.enabled"
                if cap["enabled"]
                else "cli.config.profile.capabilities.disabled"
            )
            lines.append(f"capability\t{cap['capability']}\t{state}\t{cap['source']}")
        for dep in dependencies:
            mark = tr("cli.config.check.available" if dep["available"] else "cli.config.check.missing")
            tail = f"\t{dep['remediation']}" if dep["remediation"] else ""
            lines.append(f"dependency\t{dep['service']}\t{mark}{tail}")
        for row in preflight:
            tail = f"\t{row['remediation']}" if row["remediation"] else ""
            lines.append(f"preflight\t{row['check']}\t{row['severity']}\t{row['detail']}{tail}")
        for issue in issues:
            lines.append(f"{tr('cli.config.check.issue_label', default='issue')}\t{issue}")
        _emit_envelope(ctx, command="config.check", result=result, lines=tuple(lines))
        if not ok:
            raise typer.Exit(code=2)


__all__ = ["register"]
