"""Global TUI request policy over the canonical command graph."""

from __future__ import annotations

from typing import cast

import typer

from .command_spec import CommandSpec, TuiCapability


def tui_was_requested(ctx: typer.Context) -> bool:
    """Return the root-level frontend request without duplicating CLI options."""
    root_object = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return bool(root_object.get("tui_requested"))


def enforce_tui_request(ctx: typer.Context, *, spec: CommandSpec) -> bool:
    """Refuse an unenrolled request and report whether TUI was requested."""
    if not tui_was_requested(ctx):
        return False
    if spec.tui_capability is TuiCapability.NOT_IMPLEMENTED:
        from .errors import CliTuiNotImplementedError

        identity = spec.result_schema.identity or spec.key or "root"
        raise CliTuiNotImplementedError(command=identity)
    from ...application.flows.capability import detect_frontend_capability
    from ...application.flows.errors import FlowUnsupportedConsoleError
    from ...core.flows import FrontendCapability

    if detect_frontend_capability() is not FrontendCapability.FULL_SCREEN:
        raise FlowUnsupportedConsoleError(
            translated_message="flows.errors.unsupported_console",
        )
    return True


__all__ = ["enforce_tui_request", "tui_was_requested"]
