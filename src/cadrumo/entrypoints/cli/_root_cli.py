"""Owned lazy handlers for the executable and ``app`` namespace roots.

The command graph binds its executable root callbacks to this defining module.
Keeping those callbacks on the package namespace would make their deferred
targets indistinguishable from package bootstrap and force the graph-import gate
to exempt them.  This module is the public behavior boundary resolved by the two
owning ``CommandSpec`` nodes; importing command authority never imports it.
"""

from __future__ import annotations

from typing import cast

import typer

from ...core.output_rendering import OutputFormat
from ._log_levels import resolve_log_level
from ._root_support import (
    activate_profile_override,
    emit_bare_invocation_and_exit,
    emit_root_help_and_exit,
    emit_version_report_and_exit,
    is_introspection_only_invocation,
    normalize_root_active_profile,
)
from .common import preserve_requested_cli_leaf


def root_command(
    ctx: typer.Context,
    language: str | None = None,
    profile: str | None = None,
    profile_secrets_stdin: bool = False,
    profile_secrets_fd: int | None = None,
    version: bool = False,
    detail: bool = False,
    help_: bool = False,
    format_: OutputFormat = OutputFormat.TEXT,
    quiet: bool = False,
    verbose: bool = False,
    debug: bool = False,
) -> None:
    """Capture root-level CLI flags into the Typer context."""
    if language is not None:
        from ...core.config import override_settings

        ctx.with_resource(override_settings(cadrumo_output_language=language))
    state = cast("dict[str, object]", ctx.ensure_object(dict))
    state["format"] = format_
    state["log_level"] = resolve_log_level(quiet=quiet, verbose=verbose, debug=debug)
    if version:
        emit_version_report_and_exit(detail=detail)
    if help_:
        emit_root_help_and_exit(ctx)
    if ctx.invoked_subcommand is not None and is_introspection_only_invocation(ctx):
        return
    from ..adapter_composition import profile_adapter_composition

    state["state_projection_read_ports"] = ctx.with_resource(profile_adapter_composition())
    preserve_requested_cli_leaf(ctx)
    state["profile_override"] = profile
    if ctx.invoked_subcommand is None:
        if profile is not None:
            activate_profile_override(ctx, profile)
        else:
            normalize_root_active_profile(ctx)
        emit_bare_invocation_and_exit(ctx)
    from ._profile_authentication_contract import ProfileSecretSourceOptions

    state["profile_secret_source"] = ProfileSecretSourceOptions(
        stdin=profile_secrets_stdin,
        descriptor=profile_secrets_fd,
    )


def app_root(ctx: typer.Context, help_: bool = False) -> None:
    """Render app-level workflow help when requested."""
    if help_ or ctx.invoked_subcommand is None:
        from ...application.operator_surface.help import build_help_document, render_help_text
        from ...core.json_contract import strict_round_trip
        from ._root_payloads import AppRootResult
        from .common import emit_envelope

        document = build_help_document("app")
        typed_app = strict_round_trip(AppRootResult, document)
        emit_envelope(ctx, command="root.app", result=typed_app, lines=render_help_text(document).splitlines())
        raise typer.Exit()


__all__ = ["app_root", "root_command"]
