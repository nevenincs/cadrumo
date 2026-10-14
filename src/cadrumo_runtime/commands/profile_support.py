"""Profile pointer admission helpers for runtime configuration commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from cadrumo_client.commands.errors import CliRefusedBoundaryError

if TYPE_CHECKING:
    from cadrumo.application.workflow.profile_bucket_models import ProfileBucketPointer


def resolve_active_profile_pointer() -> ProfileBucketPointer | None:
    """Resolve the selected profile from committed manifest data."""
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket_by_id
    from cadrumo.core.bucket_pointer import resolve_active_bucket_id

    active = resolve_active_bucket_id()
    return None if active is None else read_profile_bucket_by_id(active)


def require_active_profile_pointer() -> ProfileBucketPointer:
    """Return the active profile or refuse with the stable runtime message."""
    pointer = resolve_active_profile_pointer()
    if pointer is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.no_active_profile")
    return pointer


def authority_operation(ctx: typer.Context):
    """Pin the bundled authority generation for one runtime command context."""
    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority

    root = ctx.find_root()
    state = root.ensure_object(dict)
    current = state.get("cadrumo.authority_operation")
    if isinstance(current, PinnedAuthorityOperation):
        return current
    operation = root.with_resource(bundled_indexed_authority().operation())
    state["cadrumo.authority_operation"] = operation
    return operation


__all__ = ["authority_operation", "require_active_profile_pointer", "resolve_active_profile_pointer"]
