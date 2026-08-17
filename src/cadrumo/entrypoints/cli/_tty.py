"""TTY, colour, and progress helpers for the root CLI contract.

Centralises the rules every CLI command uses to decide whether to
emit ANSI colour, render a rich progress widget, or refuse a request
that requires interactive stdin. Resolution merges three signals — the
active CLI flag context (via :func:`current_cli_flag`),
explicit per-call overrides, and the operator's environment
(``NO_COLOR``, ``CADRUMO_FORCE_COLOR``, surfaced through
:class:`Settings`) — so call sites never need to re-implement the
precedence rules.

Environment variables flow through :class:`Settings`
rather than direct ``os.environ`` reads: ``NO_COLOR`` populates
:attr:`Settings.no_color`, and ``CADRUMO_FORCE_COLOR`` populates
:attr:`Settings.cadrumo_force_color`. Pydantic-settings handles the
``.env`` + ``os.environ`` merge order; this module never reaches
into the process environment directly.
"""

from __future__ import annotations

from ...core.click_context import current_cli_flag
from ...core.config import Settings
from ...core.errors import CadrumoError
from ...core.tty import stderr_is_tty, stdin_is_tty, stdout_is_tty


class NonTtyRefusedError(CadrumoError):
    """Raised when a command requires interactive stdin but stdin is piped."""

    def __init__(self) -> None:
        """Initialise a translated refusal without a recovery command template."""
        super().__init__()


def should_use_color(*, no_color: bool | None = None) -> bool:
    """Resolve whether ANSI colour should be enabled for this invocation.

    Precedence: explicit ``--no-color`` (via either the active CLI flag
    context or the ``no_color`` argument) and the standard ``NO_COLOR``
    environment variable both disable colour. ``CADRUMO_FORCE_COLOR``
    forces colour on even outside a TTY. Otherwise colour is enabled
    only when stdout is interactive.

    Args:
        no_color: Optional per-call override mirroring the
            ``--no-color`` CLI flag. Kept optional so commands can
            adopt the helper before any global flag is wired.

    Returns:
        ``True`` when colour output is appropriate.
    """
    settings = Settings()
    resolved_no_color = current_cli_flag("no_color") or bool(no_color)
    if resolved_no_color or settings.no_color:
        return False
    if settings.cadrumo_force_color:
        return True
    return stdout_is_tty()


def should_show_rich_progress(
    *,
    quiet: bool | None = None,
    json_mode: bool | None = None,
    no_progress: bool | None = None,
) -> bool:
    """Return whether an interactive rich progress widget can render safely.

    When this returns ``False`` and the caller is neither ``quiet``
    nor in ``json_mode``, the caller should fall back to line-based
    stderr progress instead of a live spinner or progress bar.

    Args:
        quiet: Optional per-call override mirroring ``--quiet``.
        json_mode: Optional per-call override mirroring ``--json``.
        no_progress: Optional per-call override mirroring
            ``--no-progress``.

    Returns:
        ``True`` when both stdout and stderr are interactive and no
        suppressing flag is active.
    """
    resolved_quiet = current_cli_flag("quiet") or bool(quiet)
    resolved_json_mode = current_cli_flag("json") or bool(json_mode)
    resolved_no_progress = current_cli_flag("no_progress") or bool(no_progress)
    if resolved_quiet or resolved_json_mode or resolved_no_progress:
        return False
    return stdout_is_tty() and stderr_is_tty()


def refuse_if_stdin_non_tty() -> None:
    """Raise a typed refusal when interactive stdin is unavailable.

    Raises:
        NonTtyRefusedError: When stdin is not a TTY.
    """
    if not stdin_is_tty():
        raise NonTtyRefusedError()


__all__ = [
    "NonTtyRefusedError",
    "refuse_if_stdin_non_tty",
    "should_show_rich_progress",
    "should_use_color",
]
