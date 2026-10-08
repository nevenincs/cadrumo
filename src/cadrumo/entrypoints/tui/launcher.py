"""Installed TUI launch boundary for authenticated runtime sessions."""

from __future__ import annotations

from collections.abc import Callable
from logging import ERROR
from typing import TYPE_CHECKING

from ...core.diagnostic_log import diagnostic_error_fields, diagnostic_event, diagnostic_process, diagnostic_scope
from ...core.errors.hierarchy import CadrumoError
from ...core.logging import get_logger

_LOGGER = get_logger(__name__)

if TYPE_CHECKING:
    from textual.app import AutopilotCallbackType

    from .account import AccountRecomposeRequiredV1
    from .app import RootBindingV1


async def run_precomposed_runtime_root_session(
    *,
    load_root: Callable[[], RootBindingV1],
    headless: bool,
    auto_pilot: AutopilotCallbackType | None,
) -> AccountRecomposeRequiredV1 | None:
    """Run an admitted root while its caller retains the runtime connection."""
    from .app import CadrumoTuiApp

    app = CadrumoTuiApp(load_root=load_root)
    return await app.run_async(headless=headless, auto_pilot=auto_pilot)


TUI_SELF_TEST_FLAG = "--self-test"
TUI_MODULE_ARGUMENT_ERROR_EXIT_CODE = 2


class TuiModuleArgumentError(CadrumoError):
    """Arguments outside the independent TUI root's closed invocation surface."""


def run_module(arguments: list[str]) -> int:
    """Start the installed session with only the optional self-test flag.

    The canonical error stays here so module execution does not change its
    qualified name in the error registry.
    """
    if arguments not in ([], [TUI_SELF_TEST_FLAG]):
        raise TuiModuleArgumentError(f"unrecognised TUI module arguments: {arguments!r}")
    return main(headless=arguments == [TUI_SELF_TEST_FLAG])


def main(
    *,
    headless: bool = False,
    auto_pilot: AutopilotCallbackType | None = None,
) -> int:
    """Start an installed session through the authenticated runtime boundary.

    Once the session ends in order, the process-shared registry authority is
    released, closing its database before the process exits.
    """
    from ...core.logging import configure_logging
    from ...domain.calculations.registry.authority import release_bundled_indexed_authority

    with diagnostic_process("tui"), diagnostic_scope():
        configure_logging()
        diagnostic_event(_LOGGER, "tui_process_started", fields={"headless": headless})
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
            )
        finally:
            # The scrubber may borrow shared authority; release after the final
            # orderly record, even when its sink interrupts the completed session.
            release_bundled_indexed_authority()
        return status


__all__ = [
    "TUI_MODULE_ARGUMENT_ERROR_EXIT_CODE",
    "TUI_SELF_TEST_FLAG",
    "TuiModuleArgumentError",
    "main",
    "run_module",
    "run_precomposed_runtime_root_session",
]
