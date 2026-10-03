"""Runtime-authorized profile capability view and fact mutation."""

from __future__ import annotations

from uuid import UUID

import typer

from ....adapters.local_runtime.frontend_client import ProfileViewCollection, RuntimeFrontendClient
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.user_profile.capabilities import resolve_capability_from_values
from ....application.user_profile.operations import ProfileFieldMutationOperationRequest
from ....application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from ....core.capabilities import ServiceCapability
from ....core.config import load_settings
from ....core.i18n.render import tr
from ..common import emit_envelope
from ..errors import CliRefusedBoundaryError
from ..runtime_profile_binding import require_profile_client
from ._profile_support import resolve_active_profile_pointer
from ._runtime_profile_mutation import execute_profile_mutation, mutation_deadline, read_mutation_baseline
from .capabilities_payloads import CapabilitiesViewResult, CapabilitySetResult


def _target(ctx: typer.Context) -> tuple[UUID, RuntimeFrontendClient]:
    pointer = resolve_active_profile_pointer()
    if pointer is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.capabilities.no_active_profile")
    profile_id = UUID(str(pointer.bucket_id))
    return profile_id, require_profile_client(ctx, expected_profile_id=profile_id)


def _facts(collection: ProfileViewCollection) -> dict[str, str]:
    items = collection.items(ProfileViewPageKind.FACTS)
    if not all(isinstance(item, ProfileViewFactItem) for item in items):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    values = {item.path: item.value for item in items if isinstance(item, ProfileViewFactItem)}
    if len(values) != len(items):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return values


def _read_facts(client: RuntimeFrontendClient, *, deadline: float) -> dict[str, str]:
    baseline = read_mutation_baseline(client, deadline=deadline)
    if baseline.profile_id != client.profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return _facts(baseline)


def capabilities_view(ctx: typer.Context) -> None:
    """Report resolved capabilities from one authenticated profile revision."""
    profile_id, client = _target(ctx)
    values = _read_facts(client, deadline=mutation_deadline())
    settings = load_settings()
    rows: list[dict[str, object]] = []
    lines: list[str] = []
    for capability in ServiceCapability:
        decision = resolve_capability_from_values(capability, profile_values=values, settings=settings)
        rows.append(
            {
                "capability": capability,
                "enabled": decision.enabled,
                "source": decision.source,
                "reason": decision.reason,
            }
        )
        state = tr(
            "cli.config.profile.capabilities.enabled"
            if decision.enabled
            else "cli.config.profile.capabilities.disabled"
        )
        lines.append(f"{capability.value}\t{state}\t{decision.source.value}\t{decision.reason}")
    result = CapabilitiesViewResult.model_validate({"profile_id": str(profile_id), "capabilities": rows})
    emit_envelope(ctx, command="config.profile.capabilities.show", result=result, lines=lines)


def capabilities_set(ctx: typer.Context, capability: ServiceCapability, state: str) -> None:
    """Write one capability fact through the profile's registered CAS operation."""
    profile_id, client = _target(ctx)
    enabled = state == "on"
    deadline = mutation_deadline()
    baseline = read_mutation_baseline(client, deadline=deadline)
    if baseline.profile_id != profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    completed, current = execute_profile_mutation(
        client,
        ProfileFieldMutationOperationRequest(
            profile_id=profile_id,
            expected_revision=baseline.record_revision,
            expected_content_digest=baseline.content_digest,
            path=capability.schema_path,
            value=str(enabled).lower(),
        ),
        deadline=deadline,
    )
    try:
        if current.profile_id != profile_id or _facts(current).get(capability.schema_path) != str(enabled).lower():
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    except RuntimeRefusalError as error:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.mutation.committed_view_unavailable",
            context={
                "operation_id": str(completed.operation_id),
                "commit_state": "succeeded",
                "record_revision": completed.projection.record_revision,
                "read_state": "unavailable",
            },
        ) from error
    result = CapabilitySetResult.model_validate(
        {"profile_id": str(profile_id), "capability": capability, "enabled": enabled},
    )
    lines = [
        f"{tr('cli.config.profile.capabilities.capability_label')}\t{capability.value}",
        f"{tr('cli.config.profile.capabilities.state_label')}\t{state}",
    ]
    emit_envelope(ctx, command="config.profile.capabilities.set", result=result, lines=lines)


__all__ = ["capabilities_set", "capabilities_view"]
