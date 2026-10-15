"""Installed TUI launch boundary for authenticated runtime sessions."""

from __future__ import annotations

from collections.abc import Callable
from logging import DEBUG, ERROR
from typing import TYPE_CHECKING

from cadrumo.core.diagnostic_log import diagnostic_error_fields, diagnostic_event, diagnostic_process, diagnostic_scope
from cadrumo.core.logging import get_logger
from cadrumo.entrypoints.tui.module_arguments import (
    headless_invocation,
)

_LOGGER = get_logger(__name__)

if TYPE_CHECKING:
    from textual.app import AutopilotCallbackType

    from cadrumo.entrypoints.tui.account import AccountRecomposeRequiredV1
    from cadrumo.entrypoints.tui.app import RootBindingV1


async def run_precomposed_runtime_root_session(
    *,
    load_root: Callable[[], RootBindingV1],
    headless: bool,
    auto_pilot: AutopilotCallbackType | None,
) -> AccountRecomposeRequiredV1 | None:
    """Run an admitted root while its caller retains the runtime connection."""
    from cadrumo.entrypoints.tui.app import CadrumoTuiApp

    app = CadrumoTuiApp(load_root=load_root)
    return await app.run_async(headless=headless, auto_pilot=auto_pilot)


def run_module(arguments: list[str]) -> int:
    """Parse the product arguments before starting the installed session."""
    return main(headless=headless_invocation(arguments))


def main(
    *,
    headless: bool = False,
    auto_pilot: AutopilotCallbackType | None = None,
) -> int:
    """Start an installed session through the authenticated runtime boundary.

    Once the session ends in order, the process-shared registry authority is
    released, closing its database before the process exits.
    """
    from cadrumo.core.logging import configure_logging, register_first_party_logger
    from cadrumo.domain.calculations.registry.authority import release_bundled_indexed_authority
    from cadrumo_client.logging import register_client_logging_namespace

    with diagnostic_process("tui"), diagnostic_scope():
        register_first_party_logger("cadrumo")
        register_client_logging_namespace()
        configure_logging()
        diagnostic_event(_LOGGER, "tui_process_started", fields={"headless": headless}, level=DEBUG)
        try:
            from .installed_session import run_installed_workbench_session

            status = run_installed_workbench_session(headless=headless, auto_pilot=auto_pilot)
        except BaseException as error:
            diagnostic_event(
                _LOGGER,
                "tui_process_failed",
                fields={**diagnostic_error_fields(error), "reason_code": "tui_session_failed", "outcome": "failed"},
                level=ERROR,
                primary_error=error,
            )
            raise
        try:
            diagnostic_event(
                _LOGGER,
                "tui_process_exited",
                fields={"exit_code": status, "outcome": "completed" if status == 0 else "refused"},
                level=DEBUG if status == 0 else ERROR,
            )
        finally:
            # The scrubber may borrow shared authority; release after the final
            # orderly record, even when its sink interrupts the completed session.
            release_bundled_indexed_authority()
        return status


__all__ = [
    "main",
    "run_module",
    "run_precomposed_runtime_root_session",
]
