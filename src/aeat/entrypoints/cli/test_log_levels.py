"""Tests for root CLI log-level routing."""

from __future__ import annotations

import logging

import pytest

from ._log_levels import LogLevel, apply_to_root_logger, resolve_log_level

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _restore_default_log_level():
    try:
        yield
    finally:
        apply_to_root_logger(LogLevel.DEFAULT)


def test_resolve_log_level_defaults_to_default_mode() -> None:
    assert resolve_log_level(env={}) is LogLevel.DEFAULT


def test_apply_default_log_level_keeps_stderr_at_error() -> None:
    apply_to_root_logger(LogLevel.DEFAULT)

    root_logger = logging.getLogger()
    stderr_handlers = [handler for handler in root_logger.handlers if not isinstance(handler, logging.FileHandler)]

    assert stderr_handlers
    assert all(handler.level == logging.ERROR for handler in stderr_handlers)


def test_apply_verbose_log_level_opts_stderr_back_into_info() -> None:
    apply_to_root_logger(LogLevel.VERBOSE)

    root_logger = logging.getLogger()
    stderr_handlers = [handler for handler in root_logger.handlers if not isinstance(handler, logging.FileHandler)]

    assert stderr_handlers
    assert all(handler.level == logging.INFO for handler in stderr_handlers)
