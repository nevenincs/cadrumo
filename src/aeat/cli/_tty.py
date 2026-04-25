"""TTY and colour/progress helpers for the root CLI contract."""

from __future__ import annotations

import os
import sys

from ..errors import AeatError

_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


class NonTtyRefusedError(AeatError):
    """Raised when a command requires interactive stdin but stdin is piped."""

    def __init__(self, suggestion: str) -> None:
        """Initialise the refusal with a copy-paste-ready suggestion."""

        message = "Interactive stdin is unavailable on a non-TTY input stream."
        if suggestion.strip():
            message = f"{message} {suggestion.strip()}"
        super().__init__(message)
        self.suggestion: str = suggestion
        # TODO(#399, after #398): assign the registered REFUSED code here.


def _isatty(stream: object) -> bool:
    """Return ``True`` when ``stream`` exposes a truthy ``isatty()``."""

    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except OSError:
        return False


def _env_truthy(name: str) -> bool:
    """Return ``True`` when an environment variable is set truthy."""

    value = os.getenv(name, "")
    return value.strip().lower() in _TRUTHY_ENV_VALUES


def is_stdout_tty() -> bool:
    """Return whether stdout is attached to an interactive terminal."""

    return _isatty(sys.stdout)


def is_stderr_tty() -> bool:
    """Return whether stderr is attached to an interactive terminal."""

    return _isatty(sys.stderr)


def is_stdin_tty() -> bool:
    """Return whether stdin is attached to an interactive terminal."""

    return _isatty(sys.stdin)


def should_use_color(*, no_color: bool = False) -> bool:
    """Resolve whether ANSI colour should be enabled for this invocation.

    Args:
        no_color: CLI-level ``--no-color`` override from a future root
            callback. Phase 1 keeps the parameter optional so commands
            can adopt the helper before the global flag lands.
    """

    if no_color or bool(os.getenv("NO_COLOR", "").strip()):
        return False
    if _env_truthy("AEAT_FORCE_COLOR"):
        return True
    return is_stdout_tty()


def should_show_rich_progress(
    *,
    quiet: bool = False,
    json_mode: bool = False,
    no_progress: bool = False,
) -> bool:
    """Return whether interactive rich progress can render safely.

    When this returns ``False`` and the caller is neither ``quiet`` nor
    in ``json_mode``, the caller should fall back to line-based stderr
    progress instead of a live spinner/progress bar.
    """

    if quiet or json_mode or no_progress:
        return False
    return is_stdout_tty() and is_stderr_tty()


def refuse_if_stdin_non_tty(suggestion: str) -> None:
    """Raise a typed refusal when interactive stdin is unavailable.

    Args:
        suggestion: Copy-paste-ready recovery hint shown to the user.

    Raises:
        NonTtyRefusedError: If stdin is not a TTY.
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
