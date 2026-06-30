"""TTY, colour, and progress helpers for the root CLI contract.

Centralises the rules every CLI command uses to decide whether to
emit ANSI colour, render a rich progress widget, or refuse a request
that requires interactive stdin. Resolution merges three signals — the
active CLI flag context (via :func:`~aeat.entrypoints.cli._context`),
explicit per-call overrides, and the operator's environment
(``NO_COLOR``, ``AEAT_FORCE_COLOR``, surfaced through
:class:`~aeat.core.config.Settings`) — so call sites never need to re-implement the
precedence rules.

Environment variables flow through :class:`~aeat.core.config.Settings`
rather than direct ``os.environ`` reads: ``NO_COLOR`` populates
:attr:`~aeat.core.config.Settings.no_color`, and ``AEAT_FORCE_COLOR`` populates
:attr:`~aeat.core.config.Settings.aeat_force_color`. Pydantic-settings handles the
``.env`` + ``os.environ`` merge order; this module never reaches
into the process environment directly.
"""

from __future__ import annotations

import sys

from ...core.click_context import current_cli_flag
from ...core.config import Settings
from ...core.errors import AeatError


class NonTtyRefusedError(AeatError):
    """Raised when a command requires interactive stdin but stdin is piped.

    Carries the operator-facing recovery hint on
    :attr:`~aeat.entrypoints.cli._tty.NonTtyRefusedError.suggestion` so the
    renderer can append it to the standard refusal message.

    Attributes:
        suggestion: Copy-paste-ready recovery hint shown to the user.
    """

    def __init__(self, suggestion: str) -> None:
        """Initialise the refusal with a copy-paste-ready suggestion.

        The positional ``message`` is intentionally omitted so ``error.args``
        remains empty. The CLI renderer then falls through to the error
        registry's ``message_key="errors.refused.refused_cli_non_tty"`` for
        locale resolution rather than short-circuiting on ``args[0]``.

        Args:
            suggestion: Recovery hint to attach to the refusal message.
        """
        super().__init__(suggestion=suggestion.strip() or None)
        self.suggestion = suggestion


def _isatty(stream: object) -> bool:
    """Return ``True`` when ``stream`` exposes a truthy ``isatty()``."""
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except OSError:
        return False


def is_stdout_tty() -> bool:
    """Return whether stdout is attached to an interactive terminal."""
    return _isatty(sys.stdout)


def is_stderr_tty() -> bool:
    """Return whether stderr is attached to an interactive terminal."""
    return _isatty(sys.stderr)


def is_stdin_tty() -> bool:
    """Return whether stdin is attached to an interactive terminal."""
    return _isatty(sys.stdin)


def should_use_color(*, no_color: bool | None = None) -> bool:
    """Resolve whether ANSI colour should be enabled for this invocation.

    Precedence: explicit ``--no-color`` (via either the active CLI flag
    context or the ``no_color`` argument) and the standard ``NO_COLOR``
    environment variable both disable colour. ``AEAT_FORCE_COLOR``
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
    if settings.aeat_force_color:
        return True
    return is_stdout_tty()


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
    return is_stdout_tty() and is_stderr_tty()


def refuse_if_stdin_non_tty(suggestion: str) -> None:
    """Raise a typed refusal when interactive stdin is unavailable.

    Args:
        suggestion: Copy-paste-ready recovery hint shown to the user.

    Raises:
        NonTtyRefusedError: When stdin is not a TTY.
    """
    if not is_stdin_tty():
        raise NonTtyRefusedError(suggestion)


__all__ = [
    "NonTtyRefusedError",
    "is_stderr_tty",
    "is_stdin_tty",
    "is_stdout_tty",
    "refuse_if_stdin_non_tty",
    "should_show_rich_progress",
    "should_use_color",
]
