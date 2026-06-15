"""``aeat config profile capabilities`` — show and set per-profile service opt-in/out.

A capability is the operator's opt-in/opt-out of an external service (cloud
evidence upload, on-host LLM vision, Google export), stored as a boolean fact on
the active profile and resolved against the global safety posture by
:func:`resolve_active_capability` (``service-capabilities`` ADR). ``show`` reports
the resolved posture + source of every capability; ``set`` writes one capability
fact through the single-writer profile path.
"""

from __future__ import annotations

from enum import StrEnum

import typer

from ....core import ServiceCapability, resolve_active_bucket_id
from ....core.i18n import tr
from .._common import _bad, _emit_envelope
from .._errors import decorate_typer_app

# Eager import so the @register_schema decorators run when this module is imported
# on the CLI build path, keeping every capability leaf in the JSON-contract registry.
from ._capabilities_payloads import CapabilitiesShowResult, CapabilitySetResult


class _Toggle(StrEnum):
    """On/off argument for ``capabilities set``."""

    ON = "on"
    OFF = "off"


def _register_show(capabilities_app: typer.Typer) -> None:
    @capabilities_app.command("show", help=tr("cli.config.profile.capabilities.show_help"))
    def capabilities_show(ctx: typer.Context) -> None:
        """Report the resolved posture of every service capability for the active profile."""
        from ....application.user_profile import resolve_active_capability

        profile_id = resolve_active_bucket_id()
        rows: list[dict[str, object]] = []
        lines: list[str] = []
        for capability in ServiceCapability:
            decision = resolve_active_capability(capability)
            rows.append(
                {
                    "capability": capability.value,
                    "enabled": decision.enabled,
                    "source": decision.source.value,
                    "reason": decision.reason,
                },
            )
            state = tr(
                "cli.config.profile.capabilities.enabled"
                if decision.enabled
                else "cli.config.profile.capabilities.disabled"
            )
            lines.append(f"{capability.value}\t{state}\t{decision.source.value}\t{decision.reason}")
        result = CapabilitiesShowResult.model_validate({"profile_id": profile_id, "capabilities": rows})
        _emit_envelope(ctx, command="config.profile.capabilities.show", result=result, lines=lines)


def _register_set(capabilities_app: typer.Typer) -> None:
    @capabilities_app.command("set", help=tr("cli.config.profile.capabilities.set_help"))
    def capabilities_set(
        ctx: typer.Context,
        capability: ServiceCapability = typer.Argument(..., help=tr("cli.config.profile.capabilities.capability_help")),
        state: _Toggle = typer.Argument(..., help=tr("cli.config.profile.capabilities.state_help")),
    ) -> None:
        """Opt the active profile in or out of one service capability."""
        from ....application.user_profile import set_active_fields
        from ....application.workflow._persistence import workflow_state_repository
        from ....domain.user_profile import UserProfileFact

        profile_id = resolve_active_bucket_id()
        if profile_id is None:
            raise _bad(
                tr(
                    "cli.config.profile.capabilities.no_active_profile",
                    default=(
                        "No active profile; select one with 'aeat config switch <name>' before setting a capability."
                    ),
                ),
            )
        enabled = state is _Toggle.ON
        workflow_state_repository().update(
            lambda current: set_active_fields(
                current,
                (UserProfileFact(path=capability.schema_path, value=enabled),),
            ),
        )
        result = CapabilitySetResult.model_validate(
            {"profile_id": profile_id, "capability": capability.value, "enabled": enabled},
        )
        lines = [
            f"{tr('cli.config.profile.capabilities.capability_label', default='capability')}\t{capability.value}",
            f"{tr('cli.config.profile.capabilities.state_label', default='state')}\t{state.value}",
        ]
        _emit_envelope(ctx, command="config.profile.capabilities.set", result=result, lines=lines)


def register(profile_app: typer.Typer) -> None:
    """Attach the capabilities subgroup to ``profile_app``."""
    capabilities_app = typer.Typer(
        name="capabilities",
        help=tr(
            "cli.config.profile.capabilities.help",
            default="Opt this profile in or out of external services (cloud upload, LLM vision, Google export).",
        ),
        no_args_is_help=True,
    )
    _register_show(capabilities_app)
    _register_set(capabilities_app)
    decorate_typer_app(capabilities_app)
    profile_app.add_typer(capabilities_app, name="capabilities")


__all__ = ["register"]
