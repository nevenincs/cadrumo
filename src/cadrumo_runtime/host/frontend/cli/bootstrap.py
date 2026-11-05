"""State-free bootstrap for the ``aeat`` console script."""

from __future__ import annotations

import os
from typing import NoReturn


def main() -> None:
    """Defer file-backed logging until parsed CLI preflight authorizes it."""
    # Pydantic scans every installed distribution's entry points on its first
    # model build, which costs about a tenth of a second in a process that
    # builds models before it has parsed a command. Cadrumo declares no
    # pydantic plugin, and a third-party one would observe taxpayer models it
    # has no business seeing. ``setdefault`` leaves an operator's explicit
    # value alone.
    os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "__all__")

    from cadrumo.core.logging import defer_logging_configuration, resume_logging_configuration
    from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition

    defer_logging_configuration()
    try:
        from cadrumo.entrypoints.cli.main import main as cli_main

        from .app import aeat_cli_app

        # The console script is the host that decides conversions use the live
        # ECB reference rates.
        with live_exchange_rate_composition():
            cli_main(app=aeat_cli_app())
    except ModuleNotFoundError as exc:
        # Backstop for a missing optional package whose feature boundary did
        # not guard it: turn the deep-stack import failure into the same
        # actionable message `require_optional_extra` gives at a boundary.
        # A module outside the declared inventory is a broken installation,
        # not a configuration choice, so that failure is re-raised untouched.
        from cadrumo.core.optional_extras import optional_extra_for_module, require_optional_extra

        extra = optional_extra_for_module(exc.name or "")
        if extra is None:
            raise
        require_optional_extra(extra)
        raise
    finally:
        resume_logging_configuration()


def console_main() -> NoReturn:
    """Run ``aeat`` as the whole of its own process, then end that process once it has settled.

    Only the console script owns the process it runs in. :func:`main` stays the
    composable dispatch, so an in-process caller, including a test harness
    that keeps working after the command, keeps the interpreter's own exit.
    Any exception other than ``SystemExit`` propagates untouched, so the
    interpreter reports it and chooses its status as before.
    """
    from .console_exit import exit_settled_console_process

    try:
        main()
    except SystemExit as exit_request:
        code = exit_request.code
    else:
        code = None
    exit_settled_console_process(code)


__all__ = ["console_main", "main"]
