"""Owned lazy handlers for the executable and ``app`` namespace roots.

The CLI package facade assembles the command graph.  Keeping executable root
callbacks on that facade made their deferred targets indistinguishable from
package bootstrap and forced the graph-import gate to exempt them.  This module
is the public behavior boundary resolved by the two owning ``CommandSpec``
nodes; importing command authority never imports it.
"""

from __future__ import annotations

from typing import cast

import typer

from ...core.output_rendering import OutputFormat
from ._common import preserve_requested_cli_leaf
from ._log_levels import resolve_log_level
from ._root_support import (
    _activate_profile_override,
    _emit_bare_invocation_and_exit,
    _emit_root_help_and_exit,
    _emit_version_report_and_exit,
    _is_introspection_only_invocation,
    _normalize_root_active_profile,
)


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
    tui: bool = False,
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
    state["tui_requested"] = tui
    state["log_level"] = resolve_log_level(quiet=quiet, verbose=verbose, debug=debug)
    if version:
        _emit_version_report_and_exit(detail=detail)
    if help_:
        _emit_root_help_and_exit(ctx)
    if ctx.invoked_subcommand is not None and _is_introspection_only_invocation(ctx):
        return
    from ...adapters.persistence.storage import build_profile_custody_port, build_profile_login_session_port
    from ...adapters.persistence.workflow import build_workflow_persistence_port
    from ...application.user_profile.custody_ports import bind_profile_custody_port
    from ...application.user_profile.login_session_port import bind_profile_login_session_port
    from ...application.workflow.persistence import bind_workflow_persistence_port

    ctx.with_resource(bind_profile_custody_port(build_profile_custody_port()))
    ctx.with_resource(bind_profile_login_session_port(build_profile_login_session_port()))
    ctx.with_resource(bind_workflow_persistence_port(build_workflow_persistence_port()))
    preserve_requested_cli_leaf(ctx)
    state["profile_override"] = profile
    if ctx.invoked_subcommand is None:
        from ._command_specs import COMMAND_GRAPH
        from ._tui_policy import enforce_tui_request

        enforce_tui_request(ctx, spec=COMMAND_GRAPH.by_key()["root"])
        if profile is not None:
            _activate_profile_override(ctx, profile)
        else:
            _normalize_root_active_profile(ctx)
        _emit_bare_invocation_and_exit(ctx)
    from ._profile_authentication_contract import ProfileSecretSourceOptions

    state["profile_secret_source"] = ProfileSecretSourceOptions(
        stdin=profile_secrets_stdin,
        descriptor=profile_secrets_fd,
    )


def app_root(ctx: typer.Context, help_: bool = False) -> None:
    """Render app-level workflow help when requested."""
    if help_ or ctx.invoked_subcommand is None:
        from ._command_specs import COMMAND_GRAPH
        from ._tui_policy import enforce_tui_request

        enforce_tui_request(ctx, spec=COMMAND_GRAPH.by_key()["app"])
        from ...application.operator_surface import build_help_document, render_help_text
        from ...core.json_contract import strict_round_trip
        from ._common import emit_envelope
        from ._root_payloads import AppRootResult

        document = build_help_document("app")
        typed_app = strict_round_trip(AppRootResult, document)
        emit_envelope(ctx, command="root.app", result=typed_app, lines=render_help_text(document).splitlines())
        raise typer.Exit()


__all__ = ["app_root", "root_command"]
