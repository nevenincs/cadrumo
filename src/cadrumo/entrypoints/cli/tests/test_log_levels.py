"""Tests for root CLI log-level routing."""

from __future__ import annotations

import logging

import pytest

from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.errors.hierarchy import TerminalPreconditionErrorMixin
from ....core.logging import configure_logging, set_log_level
from .._log_levels import LogLevel, LogLevelResolutionError, apply_to_root_logger, resolve_log_level

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _restore_default_log_level():
    try:
        yield
    finally:
        apply_to_root_logger(LogLevel.DEFAULT)


def test_resolve_log_level_defaults_to_default_mode() -> None:
    assert resolve_log_level(env={}) is LogLevel.DEFAULT


def test_invalid_environment_level_has_the_exact_no_action_terminal_contract() -> None:
    with pytest.raises(LogLevelResolutionError) as raised:
        resolve_log_level(env={"CADRUMO_LOG_LEVEL": "not-a-level"})

    error = raised.value
    assert isinstance(error, TerminalPreconditionErrorMixin)
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.model_dump(mode="json") == {
        "failed_condition_id": "cli.log_level.environment_value.recognised",
        "evidence": [
            {
                "condition_id": "cli.log_level.environment_value.recognised",
                "evidence_id": "cli.log_level.environment_value.recognised.observation",
                "provenance": ActionEvidenceProvenance.RUNTIME_OBSERVATION.value,
                "values": {
                    "environment_variable": "CADRUMO_LOG_LEVEL",
                    "environment_value_recognised": False,
                },
            }
        ],
        "action": None,
        "argument_bindings": [],
        "missing_argument_names": [],
        "conditionality": "not_applicable",
        "no_recovery_outcome": NoRecoveryOutcome.OPERATOR_DECISION.value,
    }


def test_mutually_exclusive_verbosity_flags_remain_native_parse_validation() -> None:
    with pytest.raises(LogLevelResolutionError) as raised:
        resolve_log_level(quiet=True, verbose=True, env={})

    assert raised.value.terminal_precondition_verdict is None


def test_apply_log_level_updates_stderr_handlers() -> None:
    failures: list[str] = []
    for log_level, stderr_level in (
        (LogLevel.DEFAULT, logging.ERROR),
        (LogLevel.VERBOSE, logging.INFO),
    ):
        apply_to_root_logger(log_level)

        root_logger = logging.getLogger()
        stderr_handlers = [handler for handler in root_logger.handlers if not isinstance(handler, logging.FileHandler)]

        if not stderr_handlers:
            failures.append(f"{log_level.value}: no stderr handlers")
            continue
        for handler in stderr_handlers:
            if handler.level != stderr_level:
                failures.append(f"{log_level.value}: {handler!r} level {handler.level}, expected {stderr_level}")

    assert not failures, "\n".join(failures)


def test_set_log_level_configures_root_file_and_non_file_handlers() -> None:
    """Real-behavior test for :func:`cadrumo.core.logging.set_log_level`.

    Calls :func:`configure_logging` directly (mirroring the production path),
    then calls :func:`set_log_level`, and asserts the effective level on the
    root logger plus file and non-file handlers attached by dictConfig. No
    mocks; exercises real logger state.
    """
    configure_logging()
    set_log_level(logging.ERROR)
    root_logger = logging.getLogger()

    assert root_logger.level == logging.DEBUG
    file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
    assert file_handlers, "expected at least one FileHandler after configure_logging()"
    assert all(h.level == logging.DEBUG for h in file_handlers)
    non_file_handlers = [h for h in root_logger.handlers if not isinstance(h, logging.FileHandler)]
    assert non_file_handlers, "expected at least one non-file handler after configure_logging()"
    assert all(h.level == logging.ERROR for h in non_file_handlers)


def test_all_handlers_reflect_debug_level_after_call() -> None:
    """Every handler, root and otherwise, has a level consistent with a DEBUG call."""
    configure_logging()
    set_log_level(logging.DEBUG)
    root_logger = logging.getLogger()
    assert root_logger.handlers, "root logger must have handlers"
    for handler in root_logger.handlers:
        # All handlers must be reachable at DEBUG: file at DEBUG, non-file at
        # DEBUG because DEBUG was requested.
        assert handler.level == logging.DEBUG, f"handler {handler!r} level unexpected"


def test_multiple_set_log_level_calls_each_take_effect() -> None:
    """Successive set_log_level calls each update handler levels idempotently."""
    configure_logging()
    set_log_level(logging.ERROR)
    root_logger = logging.getLogger()
    non_file_before = [h for h in root_logger.handlers if not isinstance(h, logging.FileHandler)]
    assert all(h.level == logging.ERROR for h in non_file_before)

    set_log_level(logging.INFO)
    non_file_after = [h for h in root_logger.handlers if not isinstance(h, logging.FileHandler)]
    assert all(h.level == logging.INFO for h in non_file_after)
