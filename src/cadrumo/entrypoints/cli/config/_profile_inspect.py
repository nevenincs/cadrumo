"""Profile inspection verbs: ``view`` and ``validate``.

``view`` and ``validate`` render one authenticated runtime projection.
Their public behavior targets live here while CommandSpecs own the executable
shape.

Filing-context readiness is NOT reported here. ``app modelo readiness`` is the
one home for that question: it reports the same missing profile requirements
over the same gate, and adds the registry, binding and ledger axes this module
never covered.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import typer

from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....core.errors.hierarchy import InternalInvariantError
from ....core.external_constants import OutputLanguage as _OutputLanguage
from ..common import activate_subcommand_output_language as _activate_subcommand_output_language
from ..common import emit_envelope, no_active_profile_refusal
from ..errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ..runtime_profile_binding import require_profile_client
from .runtime_profile_view import project_profile_validate, project_profile_view

if TYPE_CHECKING:
    from ....application.workflow.profile_bucket_models import ProfileBucketPointer as _ProfileBucketPointer


def _resolve_show_pointer(
    name: str | None,
    *,
    ctx: typer.Context,
    resolve_active_profile_pointer: Callable[[], _ProfileBucketPointer | None],
) -> _ProfileBucketPointer:
    """Resolve the profile ``show`` inspects, by name or the active pointer.

    ``show`` is the inspect surface for a current committed capsule. The
    pointer supplies identity and label; setup state is read from the
    authenticated record below.
    """
    if name is None:
        pointer = resolve_active_profile_pointer()
        if pointer is None:
            raise no_active_profile_refusal()
        return pointer

    from .._profile_authentication_gate import resolved_command_profile_target

    pointer = resolved_command_profile_target(ctx)
    if pointer is not None:
        return pointer
    raise InternalInvariantError("explicit profile show target was not resolved by parsed dispatch")


def config_profile_view(
    ctx: typer.Context,
    name: str | None = None,
    output_language: _OutputLanguage | None = None,
) -> None:
    """Render one exact profile view and exit 2 for blocking record issues."""
    from uuid import UUID

    from ._profile_support import resolve_active_profile_pointer

    _activate_subcommand_output_language(ctx, output_language)
    pointer = _resolve_show_pointer(name, ctx=ctx, resolve_active_profile_pointer=resolve_active_profile_pointer)
    client = require_profile_client(ctx, expected_profile_id=UUID(str(pointer.bucket_id)))
    try:
        projected = project_profile_view(
            ctx,
            client,
            display_name=pointer.label,
            requested_output_language=output_language,
        )
    except RuntimeFrontendRefusedError as refusal:
        raise _CliRefusedBoundaryError(context={"reason": refusal.reason}) from refusal
    emit_envelope(
        ctx,
        command="config.profile.view",
        result=projected.result,
        lines=projected.lines,
        notices=projected.notices,
    )
    if projected.blocking:
        raise typer.Exit(code=2)


def _resolve_validate_target_pointer(
    name: str | None,
    *,
    ctx: typer.Context,
    resolve_active_profile_pointer: Callable[[], _ProfileBucketPointer | None],
) -> _ProfileBucketPointer:
    """Resolve the profile the validate verb targets, refusing clearly when it cannot.

    A named profile resolves through the shared label reader (tombstoned
    records included, because validating one is legitimate); an omitted name
    falls back to the active profile pointer.
    """
    if name is None:
        pointer = resolve_active_profile_pointer()
        if pointer is None:
            raise no_active_profile_refusal()
        return pointer
    from .._profile_authentication_gate import resolved_command_profile_target

    pointer = resolved_command_profile_target(ctx)
    if pointer is None:
        raise InternalInvariantError("explicit profile validate target was not resolved by parsed dispatch")
    return pointer


def config_profile_validate(
    ctx: typer.Context,
    name: str | None = None,
    output_language: _OutputLanguage | None = None,
) -> None:
    """Validate a profile against the loaded schema (defaults to the active profile).

    Exits with code ``2`` when blocking issues surface so operators discover
    schema-conformance failures via the shell exit status. Report-only
    companion to ``config_profile_view`` — same validator, narrower
    payload (no fact dump).
    """
    from uuid import UUID

    from ._profile_support import resolve_active_profile_pointer

    _activate_subcommand_output_language(ctx, output_language)

    pointer = _resolve_validate_target_pointer(
        name,
        ctx=ctx,
        resolve_active_profile_pointer=resolve_active_profile_pointer,
    )
    client = require_profile_client(ctx, expected_profile_id=UUID(str(pointer.bucket_id)))
    try:
        projected = project_profile_validate(
            ctx,
            client,
            display_name=pointer.label,
            requested_output_language=output_language,
        )
    except RuntimeFrontendRefusedError as refusal:
        raise _CliRefusedBoundaryError(context={"reason": refusal.reason}) from refusal
    emit_envelope(ctx, command="config.profile.validate", result=projected.result, lines=projected.lines)
    if projected.blocking:
        raise typer.Exit(code=2)


__all__ = ["config_profile_validate", "config_profile_view"]
