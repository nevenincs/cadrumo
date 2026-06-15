"""``aeat config check`` — the workstation doctor.

For every external service, reports the active profile's capability posture, the
dependency availability (from the typed probes), and the exact remediation for any
gap. Exits non-zero when a capability the profile opted into has a missing
dependency — the operator asked for a service that is not provisioned
(``dependency-provisioning`` ADR). Named ``check`` because ``config doctor`` is a
retired command path.
"""

from __future__ import annotations

import typer

from ....core import ServiceCapability, resolve_active_bucket_id
from ....core.i18n import tr
from .._common import _emit_envelope

# Eager import so the @register_schema decorator runs on the CLI build path.
from ._check_payloads import ConfigCheckResult


def register(app: typer.Typer) -> None:
    """Attach the ``check`` command to the config ``app``."""

    @app.command("check", help=tr("cli.config.check.help"))
    def config_check(ctx: typer.Context) -> None:
        """Report external-dependency availability + the active profile's capability posture."""
        from ....application.provisioning import (
            probe_ollama_vision,
            probe_playwright_browser,
            probe_subprocess_providers,
        )
        from ....application.user_profile import resolve_active_capability

        profile_id = resolve_active_bucket_id()

        capabilities = []
        for cap in ServiceCapability:
            decision = resolve_active_capability(cap)
            capabilities.append(
                {"capability": cap.value, "enabled": decision.enabled, "source": decision.source.value},
            )
        cap_enabled = {row["capability"]: row["enabled"] for row in capabilities}

        ollama = probe_ollama_vision()
        providers = probe_subprocess_providers()
        playwright = probe_playwright_browser()
        dependencies = [d.model_dump() for d in (ollama, *providers, playwright)]
        any_provider = any(p.available for p in providers)

        issues: list[str] = []
        if cap_enabled[ServiceCapability.LLM_VISION.value] and not ollama.available:
            issues.append(f"llm_vision is on but {ollama.detail}: {ollama.remediation}")
        if cap_enabled[ServiceCapability.CLOUD_EVIDENCE_UPLOAD.value] and not any_provider:
            issues.append("cloud_evidence_upload is on but no cloud LLM provider CLI is on PATH (claude / agy / codex)")

        ok = not issues
        result = ConfigCheckResult.model_validate(
            {
                "profile_id": profile_id,
                "ok": ok,
                "capabilities": capabilities,
                "dependencies": dependencies,
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
        for issue in issues:
            lines.append(f"{tr('cli.config.check.issue_label', default='issue')}\t{issue}")
        _emit_envelope(ctx, command="config.check", result=result, lines=lines)
        if not ok:
            raise typer.Exit(code=2)


__all__ = ["register"]
