"""CLI log-level resolution for quiet/default/verbose/debug modes."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from enum import StrEnum

from ...core import logging as aeat_logging
from ...core.errors import AeatError


class LogLevelResolutionError(AeatError):
    """Raised when the requested CLI log-level inputs are contradictory."""


class LogLevel(StrEnum):
    """Stable CLI log-level names exposed through flags and env vars."""

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

    Args:
        quiet: ``--quiet`` flag.
        verbose: ``--verbose`` flag.
        debug: ``--debug`` flag.
        env: Optional environment mapping for deterministic tests.

    Returns:
        The effective :class:`LogLevel`.

    Raises:
        LogLevelResolutionError: If multiple verbosity flags are active
            or the environment value is invalid.
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
