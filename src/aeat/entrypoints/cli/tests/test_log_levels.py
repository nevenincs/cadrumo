"""Tests for root CLI log-level routing."""

from __future__ import annotations

import logging

import pytest

from ....core.logging import configure_logging, set_log_level
from .._log_levels import LogLevel, apply_to_root_logger, resolve_log_level

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


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


class TestSetLogLevel:
    """Real-behavior tests for :func:`aeat.core.logging.set_log_level`.

    Each test calls :func:`configure_logging` directly (mirroring the
    production path), then calls :func:`set_log_level`, and asserts the
    effective level on the root logger *and* every handler attached by
    dictConfig.  No mocks; exercises real logger state.
    """

    def test_root_logger_level_is_always_debug_regardless_of_target(self) -> None:
        """Root logger must allow every record through; handlers gate individually."""
        configure_logging()
        set_log_level(logging.WARNING)
        assert logging.getLogger().level == logging.DEBUG

    def test_file_handlers_receive_debug_by_default(self) -> None:
        configure_logging()
        set_log_level(logging.ERROR)
        root_logger = logging.getLogger()
        file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
        assert file_handlers, "expected at least one FileHandler after configure_logging()"
        assert all(h.level == logging.DEBUG for h in file_handlers)

    def test_non_file_handlers_receive_requested_level(self) -> None:
        configure_logging()
        set_log_level(logging.INFO)
        root_logger = logging.getLogger()
        non_file_handlers = [h for h in root_logger.handlers if not isinstance(h, logging.FileHandler)]
        assert non_file_handlers, "expected at least one non-file handler after configure_logging()"
        assert all(h.level == logging.INFO for h in non_file_handlers)

    def test_all_handlers_reflect_level_after_call(self) -> None:
        """Every handler — root and otherwise — has a level consistent with the call."""
        configure_logging()
        set_log_level(logging.DEBUG)
        root_logger = logging.getLogger()
        assert root_logger.handlers, "root logger must have handlers"
        for handler in root_logger.handlers:
            # All handlers must be reachable at DEBUG — file at DEBUG,
            # non-file at DEBUG (since we requested DEBUG).
            assert handler.level == logging.DEBUG, f"handler {handler!r} level unexpected"

    def test_multiple_calls_each_take_effect(self) -> None:
        """Successive set_log_level calls each update handler levels idempotently."""
        configure_logging()
        set_log_level(logging.ERROR)
        root_logger = logging.getLogger()
        non_file_before = [h for h in root_logger.handlers if not isinstance(h, logging.FileHandler)]
        assert all(h.level == logging.ERROR for h in non_file_before)

        set_log_level(logging.INFO)
        non_file_after = [h for h in root_logger.handlers if not isinstance(h, logging.FileHandler)]
        assert all(h.level == logging.INFO for h in non_file_after)
