"""``aeat config profile capabilities`` — show and set per-profile service opt-in/out.

A capability is the operator's opt-in/opt-out of an external service (cloud
evidence upload, on-host LLM vision, Google export), stored as a boolean fact on
the active profile and resolved against the global safety posture by
:func:`resolve_active_capability`. ``show`` reports
the resolved posture + source of every capability; ``set`` writes one capability
fact through the single-writer profile path.
"""

from __future__ import annotations

import typer

from ....core import ServiceCapability
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.i18n import tr
from .._common import bad, emit_envelope

# on the CLI build path, keeping every capability leaf in the JSON-contract registry.
from ._capabilities_payloads import CapabilitiesViewResult, CapabilitySetResult


def capabilities_view(ctx: typer.Context) -> None:
    """Report the resolved posture of every service capability for the active profile."""
    from ....application.user_profile.capabilities import resolve_active_capability

    profile_id = resolve_active_bucket_id()
    rows: list[dict[str, object]] = []
    lines: list[str] = []
    for capability in ServiceCapability:
        decision = resolve_active_capability(capability)
        rows.append(
            {
                "capability": capability,
                "enabled": decision.enabled,
                "source": decision.source,
                "reason": decision.reason,
            },
        )
        state = tr(
            "cli.config.profile.capabilities.enabled"
            if decision.enabled
            else "cli.config.profile.capabilities.disabled"
        )
        lines.append(f"{capability.value}\t{state}\t{decision.source.value}\t{decision.reason}")
    result = CapabilitiesViewResult.model_validate({"profile_id": profile_id, "capabilities": rows})
    emit_envelope(ctx, command="config.profile.capabilities.show", result=result, lines=lines)


def capabilities_set(ctx: typer.Context, capability: ServiceCapability, state: str) -> None:
    """Opt the active profile in or out of one service capability."""
    from ....application.user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
    from ....domain.user_profile.values import UserProfileFact

    profile_id = resolve_active_bucket_id()
    if profile_id is None:
        raise bad(
            tr(
                "cli.config.profile.capabilities.no_active_profile",
            ),
        )
    enabled = state == "on"
    apply_profile_fact_changes(
        profile_id=profile_id,
        changes=(UserProfileFact(path=capability.schema_path, value=enabled),),
        door=ProfileFactWriteDoor.CLI_CAPACIDAD,
    )
    result = CapabilitySetResult.model_validate(
        {"profile_id": profile_id, "capability": capability, "enabled": enabled},
    )
    lines = [
        f"{tr('cli.config.profile.capabilities.capability_label')}\t{capability.value}",
        f"{tr('cli.config.profile.capabilities.state_label')}\t{state}",
    ]
    emit_envelope(ctx, command="config.profile.capabilities.set", result=result, lines=lines)


__all__ = ["capabilities_set", "capabilities_view"]
