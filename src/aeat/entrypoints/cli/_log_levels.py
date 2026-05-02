"""CLI log-level resolution for quiet/default/verbose/debug modes.

Encapsulates the contract for translating the CLI's ``--quiet`` /
``--verbose`` / ``--debug`` flag triple plus the ``AEAT_LOG_LEVEL``
environment variable into a single :class:`LogLevel` value, and applies
that value to the configured root logger via
:func:`apply_to_root_logger`. Every CLI entrypoint funnels its
verbosity decision through :func:`resolve_log_level` so behaviour stays
consistent across commands.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from enum import StrEnum

from ...core import logging as aeat_logging
from ...core.errors import AeatError


class LogLevelResolutionError(AeatError):
    """Raised when the requested CLI log-level inputs are contradictory.

    Examples include passing more than one of ``--quiet`` / ``--verbose``
    / ``--debug`` together, or setting ``AEAT_LOG_LEVEL`` to a value
    outside the :class:`LogLevel` vocabulary.
    """


class LogLevel(StrEnum):
    """Stable CLI log-level names exposed through flags and env vars.

    Attributes:
        QUIET: Suppress everything below :data:`logging.ERROR`.
        DEFAULT: Standard verbosity at :data:`logging.WARNING`.
        VERBOSE: Informational output at :data:`logging.INFO`.
        DEBUG: Full diagnostics at :data:`logging.DEBUG`.
    """

    QUIET = "quiet"
    DEFAULT = "default"
    VERBOSE = "verbose"
    DEBUG = "debug"


_PYTHON_LOG_LEVEL_BY_CLI_LEVEL: dict[LogLevel, int] = {
    LogLevel.QUIET: logging.ERROR,
    LogLevel.DEFAULT: logging.WARNING,
    LogLevel.VERBOSE: logging.INFO,
    LogLevel.DEBUG: logging.DEBUG,
}


def resolve_log_level(
    *,
    quiet: bool = False,
    verbose: bool = False,
    debug: bool = False,
    env: Mapping[str, str] | None = None,
) -> LogLevel:
    """Resolve the effective CLI log level from flags and environment.

    Flags take precedence over the environment in the order
    ``debug > verbose > quiet``. When no flag is set, ``AEAT_LOG_LEVEL``
    is consulted; an empty value falls back to :attr:`LogLevel.DEFAULT`.

    Args:
        quiet: Whether ``--quiet`` was passed.
        verbose: Whether ``--verbose`` was passed.
        debug: Whether ``--debug`` was passed.
        env: Optional environment mapping for deterministic tests; when
            :data:`None`, :data:`os.environ` is used.

    Returns:
        The effective :class:`LogLevel`.

    Raises:
        LogLevelResolutionError: If more than one verbosity flag is
            active simultaneously, or if ``AEAT_LOG_LEVEL`` carries a
            value outside the :class:`LogLevel` vocabulary.
    """

    selected_flags = sum((quiet, verbose, debug))
    if selected_flags > 1:
        raise LogLevelResolutionError("--quiet, --verbose, and --debug are mutually exclusive")
    if debug:
        return LogLevel.DEBUG
    if verbose:
        return LogLevel.VERBOSE
    if quiet:
        return LogLevel.QUIET

    source = os.environ if env is None else env
    raw_value = source.get("AEAT_LOG_LEVEL", "").strip().lower()
    if not raw_value:
        return LogLevel.DEFAULT
    try:
        return LogLevel(raw_value)
    except ValueError as exc:
        allowed = ", ".join(level.value for level in LogLevel)
        raise LogLevelResolutionError(f"AEAT_LOG_LEVEL must be one of: {allowed}; got {raw_value!r}") from exc


def apply_to_root_logger(level: LogLevel) -> None:
    """Apply the resolved CLI log level to the configured root logger.

    Calls :func:`aeat.core.logging.configure_logging` first so the
    project-wide logging contract is in place, then sets the level on
    the root logger and every attached handler.

    Args:
        level: Target CLI log level.
    """

    aeat_logging.configure_logging()
    python_level = _PYTHON_LOG_LEVEL_BY_CLI_LEVEL[level]
    root_logger = logging.getLogger()
    root_logger.setLevel(python_level)
    for handler in root_logger.handlers:
        handler.setLevel(python_level)


__all__ = ["LogLevel", "LogLevelResolutionError", "apply_to_root_logger", "resolve_log_level"]
