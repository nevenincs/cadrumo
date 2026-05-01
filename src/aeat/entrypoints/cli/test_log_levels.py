"""Unit tests for the CLI log-level resolver."""

from __future__ import annotations

import logging
from collections.abc import Mapping

import pytest

from ... import cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


@pytest.mark.parametrize(
    ("quiet", "verbose", "debug", "env", "expected"),
    [
        (False, False, False, None, cli.LogLevel.DEFAULT),
        (True, False, False, None, cli.LogLevel.QUIET),
        (False, True, False, None, cli.LogLevel.VERBOSE),
        (False, False, True, None, cli.LogLevel.DEBUG),
        (False, False, False, {"AEAT_LOG_LEVEL": "quiet"}, cli.LogLevel.QUIET),
        (False, False, False, {"AEAT_LOG_LEVEL": "verbose"}, cli.LogLevel.VERBOSE),
        (False, False, False, {"AEAT_LOG_LEVEL": "debug"}, cli.LogLevel.DEBUG),
        (False, True, False, {"AEAT_LOG_LEVEL": "quiet"}, cli.LogLevel.VERBOSE),
    ],
)
def test_resolve_log_level_honors_flag_and_env_precedence(
    quiet: bool,
    verbose: bool,
    debug: bool,
    env: Mapping[str, str] | None,
    expected: cli.LogLevel,
) -> None:
    """Flags must override env, and env must override the default."""

    assert cli.resolve_log_level(quiet=quiet, verbose=verbose, debug=debug, env=env) is expected


def test_resolve_log_level_rejects_conflicting_flags() -> None:
    """Mutually-exclusive verbosity flags must fail deterministically."""

    with pytest.raises(cli.LogLevelResolutionError, match="mutually exclusive"):
        cli.resolve_log_level(quiet=True, debug=True)


def test_resolve_log_level_rejects_invalid_env_value() -> None:
    """Unexpected env values should fail loudly rather than guessing."""

    with pytest.raises(cli.LogLevelResolutionError, match="AEAT_LOG_LEVEL must be one of"):
        cli.resolve_log_level(env={"AEAT_LOG_LEVEL": "trace"})


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (cli.LogLevel.QUIET, logging.ERROR),
        (cli.LogLevel.DEFAULT, logging.WARNING),
        (cli.LogLevel.VERBOSE, logging.INFO),
        (cli.LogLevel.DEBUG, logging.DEBUG),
    ],
)
def test_apply_to_root_logger_updates_root_and_handlers(level: cli.LogLevel, expected: int) -> None:
    """Applying a CLI log level must update both root and handler levels."""

    root_logger = logging.getLogger()
    previous_root_level = root_logger.level
    previous_handler_levels = [handler.level for handler in root_logger.handlers]
    try:
        cli.apply_to_root_logger(level)
        assert root_logger.level == expected
        assert root_logger.handlers, "configure_logging() did not install a root handler"
        assert all(handler.level == expected for handler in root_logger.handlers)
    finally:
        root_logger.setLevel(previous_root_level)
        for handler, previous_level in zip(root_logger.handlers, previous_handler_levels, strict=False):
            handler.setLevel(previous_level)
