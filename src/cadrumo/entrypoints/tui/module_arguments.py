"""The TUI's closed invocation grammar, independent of its hosting process."""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError

TUI_SELF_TEST_FLAG = "--self-test"
TUI_MODULE_ARGUMENT_ERROR_EXIT_CODE = 2


class TuiModuleArgumentError(CadrumoError):
    """Arguments outside the TUI's closed invocation surface."""


def headless_invocation(arguments: list[str]) -> bool:
    """Parse the TUI presentation option without starting or admitting a host."""
    if arguments not in ([], [TUI_SELF_TEST_FLAG]):
        raise TuiModuleArgumentError(f"unrecognised TUI module arguments: {arguments!r}")
    return arguments == [TUI_SELF_TEST_FLAG]
