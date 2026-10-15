"""Command-line entrypoint for runtime-owned configuration operations."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from typer import Exit as TyperExit
from typer._click.exceptions import ClickException as TyperClickException
from typer.main import get_command

from cadrumo.core.click_context import argv_requests_json, context_chain_requests_json
from cadrumo.core.errors.error_codes import (
    get_error_exit_code,
    get_registered_error_code,
    render_error_json,
    render_error_text,
)
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo_client.commands.compiler import build_command_app
from cadrumo_client.commands.errors import CliRefusedBoundaryError, CliUnexpectedBoundaryError
from cadrumo_client.commands.output import write_stderr
from cadrumo_client.commands.stdio import configure_stdio_for_utf8, disable_rich_cli_rendering
from cadrumo_client.logging import register_client_logging_namespace

from .command_specs import RUNTIME_COMMAND_GRAPH
from .lifecycle import dispatch_runtime_behavior
from .presentation import precondition_action_lines, resolve_cli_precondition_action, runtime_error_context


def main(arguments: Sequence[str] | None = None) -> int:
    """Run one runtime configuration command without entering the daemon server."""
    argv = list(sys.argv[1:] if arguments is None else arguments)
    register_client_logging_namespace()
    configure_stdio_for_utf8()
    disable_rich_cli_rendering()
    app = build_command_app(RUNTIME_COMMAND_GRAPH, dispatcher=dispatch_runtime_behavior)
    command = get_command(app)
    try:
        command.main(args=argv, prog_name="cadrumo-runtime", standalone_mode=False)
    except TyperExit as exit_request:
        return exit_request.exit_code
    except TyperClickException as error:
        boundary = CliRefusedBoundaryError(
            translated_message="errors.refused.refused_cli_validation_boundary",
            context={"boundary_error_type": type(error).__name__},
        )
        return _emit_error(boundary, argv, click_context=getattr(error, "ctx", None))
    except CadrumoError as error:
        return _emit_error(error, argv)
    except Exception as error:
        boundary = CliUnexpectedBoundaryError(error)
        return _emit_error(boundary, argv)
    return 0


def _emit_error(error: CadrumoError, arguments: Sequence[str], *, click_context: object | None = None) -> int:
    """Render one runtime command failure through the shared error envelope."""
    from contextlib import nullcontext

    from cadrumo.core.config import override_settings

    captured = runtime_error_context(error)
    language_scope = (
        override_settings(cadrumo_output_language=captured.output_language) if captured is not None else nullcontext()
    )
    with language_scope:
        return _render_error(error, arguments, click_context=click_context)


def _render_error(error: CadrumoError, arguments: Sequence[str], *, click_context: object | None = None) -> int:
    """Render while the invocation's captured language is active."""
    from cadrumo.application.cli_exception_preconditions import nested_terminal_precondition_verdict

    captured = runtime_error_context(error)
    verdict = nested_terminal_precondition_verdict(error)
    action = None if verdict is None else resolve_cli_precondition_action(verdict)
    context_requests_json = False
    if click_context is not None:
        try:
            context_requests_json = context_chain_requests_json(click_context)
        except (AttributeError, TypeError):
            context_requests_json = False
    as_json = (
        (captured is not None and captured.output_format == "json")
        or context_requests_json
        or argv_requests_json(list(arguments))
    )
    code = get_registered_error_code(error)
    if as_json:
        write_stderr(
            render_error_json(
                error,
                action=action,
                active_profile=None if captured is None else captured.active_profile,
                command=None if captured is None else captured.command,
                notices=() if captured is None else captured.notices,
            )
        )
    else:
        text = render_error_text(error)
        if action is not None:
            text = "\n".join((text.rstrip("\n"), *precondition_action_lines(action))) + "\n"
        write_stderr(text)
    return get_error_exit_code(code.category)


__all__ = ["main"]
