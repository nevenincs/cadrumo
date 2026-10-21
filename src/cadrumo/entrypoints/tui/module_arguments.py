"""The TUI's closed invocation grammar, independent of its hosting process."""

from __future__ import annotations

from uuid import UUID

from ...core.errors.hierarchy import CadrumoError

TUI_SELF_TEST_FLAG = "--self-test"
TUI_MODULE_ARGUMENT_ERROR_EXIT_CODE = 2


class TuiModuleArgumentError(CadrumoError):
    """Arguments outside the TUI's closed invocation surface."""


def aeat_setup_profile(arguments: list[str]) -> UUID | None:
    """Parse one exact-profile setup target, never a command or credential."""
    if not arguments or arguments[0] != "--aeat-auth-profile":
        return None
    if len(arguments) != 2:
        raise TuiModuleArgumentError("AEAT setup requires one profile identifier")
    try:
        profile_id = UUID(arguments[1])
    except ValueError:
        raise TuiModuleArgumentError("invalid AEAT setup profile identifier") from None
    if str(profile_id) != arguments[1] or profile_id.int == 0:
        raise TuiModuleArgumentError("invalid AEAT setup profile identifier")
    return profile_id


def headless_invocation(arguments: list[str]) -> bool:
    """Parse the TUI presentation option without starting or admitting a host."""
    if arguments not in ([], [TUI_SELF_TEST_FLAG]):
        raise TuiModuleArgumentError(f"unrecognised TUI module arguments: {arguments!r}")
    return arguments == [TUI_SELF_TEST_FLAG]
