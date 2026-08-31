"""CLI log-level resolution for quiet/default/verbose/debug modes.

Encapsulates the contract for translating the CLI's ``--quiet`` /
``--verbose`` / ``--debug`` flag triple plus the ``CADRUMO_LOG_LEVEL``
environment variable into a single
:class:`LogLevel` value, and applies that
value to the configured root logger via
:func:`apply_to_root_logger`. Every CLI
entrypoint funnels its verbosity decision through
:func:`resolve_log_level` so behaviour stays
consistent across commands.
"""

from __future__ import annotations

import logging  # LOGGING-STDLIB-CONSTANTS-ONLY-RATIONALE: constants-only; no logger instantiated.
from collections.abc import Mapping
from enum import StrEnum

from ...application.operator_actions.models import PreconditionVerdict
from ...core.config_state_root import FormerProductStateError
from ...core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin
from ...core.logging import set_log_level
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome


class LogLevelResolutionError(TerminalPreconditionErrorMixin[PreconditionVerdict], CadrumoError):
    """Raised when the requested CLI log-level inputs are contradictory.

    Examples include passing more than one of ``--quiet`` / ``--verbose``
    / ``--debug`` together, or setting ``CADRUMO_LOG_LEVEL`` to a value
    outside the :class:`LogLevel`
    vocabulary.
    """


class LogLevel(StrEnum):
    """Stable CLI log-level names exposed through flags and env vars.

    Attributes:
        QUIET: Suppress everything below :data:`~logging.ERROR`.
        DEFAULT: Standard verbosity at :data:`~logging.WARNING`.
        VERBOSE: Informational output at :data:`~logging.INFO`.
        DEBUG: Full diagnostics at :data:`~logging.DEBUG`.
    """

    QUIET = "quiet"
    DEFAULT = "default"
    VERBOSE = "verbose"
    DEBUG = "debug"


_STDERR_LOG_LEVEL_BY_CLI_LEVEL: dict[LogLevel, int] = {
    LogLevel.QUIET: logging.ERROR,
    LogLevel.DEFAULT: logging.ERROR,
    LogLevel.VERBOSE: logging.INFO,
    LogLevel.DEBUG: logging.DEBUG,
}


def _invalid_environment_log_level_error(*, allowed: str, value: str) -> LogLevelResolutionError:
    """Return the typed refusal for an unrecognised log-level environment value."""
    from ...application.operator_actions.preconditions import no_action_precondition_verdict

    return LogLevelResolutionError(
        translated_message="cli.log_levels.errors.invalid_env_value",
        context={"allowed": allowed, "value": value},
        precondition_verdict=no_action_precondition_verdict(
            condition_id="cli.log_level.environment_value.recognised",
            facts={
                "environment_variable": "CADRUMO_LOG_LEVEL",
                "environment_value_recognised": False,
            },
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )


def resolve_log_level(
    *,
    quiet: bool = False,
    verbose: bool = False,
    debug: bool = False,
    env: Mapping[str, str] | None = None,
) -> LogLevel:
    """Resolve the effective CLI log level from flags and environment.

    Flags take precedence over the environment in the order
    ``debug > verbose > quiet``. When no flag is set, ``CADRUMO_LOG_LEVEL``
    is consulted; an empty value falls back to
    :attr:`LogLevel.DEFAULT`.

    Args:
        quiet: Whether ``--quiet`` was passed.
        verbose: Whether ``--verbose`` was passed.
        debug: Whether ``--debug`` was passed.
        env: Optional environment mapping for deterministic tests; when
            ``None``, :func:`load_settings` is
            consulted (the single Cadrumo-config surface).

    Returns:
        The effective :class:`LogLevel`.

    Raises:
        LogLevelResolutionError: If more than one verbosity flag is
            active simultaneously, or if ``CADRUMO_LOG_LEVEL`` carries a
            value outside the
            :class:`LogLevel` vocabulary.
    """
    selected_flags = sum((quiet, verbose, debug))
    if selected_flags > 1:
        raise LogLevelResolutionError(
            translated_message="cli.log_levels.errors.flags_mutually_exclusive",
        )
    if debug:
        return LogLevel.DEBUG
    if verbose:
        return LogLevel.VERBOSE
    if quiet:
        return LogLevel.QUIET

    if env is not None:
        raw_value = env.get("CADRUMO_LOG_LEVEL", "").strip().lower()
    else:
        # No explicit env mapping: read via Settings (single Cadrumo-config surface).
        # The env parameter remains for tests that need to inject an isolated
        # mapping without going through Settings's os.environ + .env merge.
        from ...core.config import load_settings

        try:
            raw_value = load_settings().cadrumo_log_level.strip().lower()
        except (FormerProductStateError, KeyError, ValueError, AttributeError):
            raw_value = ""
    if not raw_value:
        return LogLevel.DEFAULT
    try:
        return LogLevel(raw_value)
    except ValueError as exc:
        allowed = ", ".join(level.value for level in LogLevel)
        raise _invalid_environment_log_level_error(allowed=allowed, value=raw_value) from exc


def apply_to_root_logger(level: LogLevel) -> None:
    """Apply the resolved CLI log level to the configured root logger.

    Delegates to :func:`set_log_level` which calls
    :func:`configure_logging` first so the
    project-wide logging contract is in place, then sets the level on
    the root logger and every attached handler.

    Args:
        level: Target CLI log level.
    """
    set_log_level(_STDERR_LOG_LEVEL_BY_CLI_LEVEL[level])


__all__ = ["LogLevel", "LogLevelResolutionError", "apply_to_root_logger", "resolve_log_level"]
