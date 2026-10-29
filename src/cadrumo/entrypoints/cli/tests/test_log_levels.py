"""Tests for root CLI log-level routing."""

from __future__ import annotations

import logging
from typing import override

import pytest

from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS

from ....core.errors.hierarchy import TerminalPreconditionErrorMixin
from ....core.logging import configure_logging, flush_logging, get_logger, set_log_level
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.tests.log_sinks import delivery_sinks
from .._log_levels import LogLevel, LogLevelResolutionError, apply_to_root_logger, resolve_log_level

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROBE_LOGGER = "cadrumo.tests.log_levels"


@pytest.fixture(autouse=True)
def _restore_default_log_level():
    try:
        yield
    finally:
        apply_to_root_logger(LogLevel.DEFAULT)


def test_resolve_log_level_defaults_to_default_mode() -> None:
    assert resolve_log_level(env={}) is LogLevel.DEFAULT


@pytest.mark.parametrize("level", ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"))
def test_severity_environment_override_is_accepted_by_cli_children(level: str) -> None:
    assert resolve_log_level(env={"CADRUMO_LOG_LEVEL": f" {level} "}).value == level.lower()


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

        stderr_sinks = [sink for sink in delivery_sinks() if not isinstance(sink, logging.FileHandler)]

        if not stderr_sinks:
            failures.append(f"{log_level.value}: no stderr handlers")
            continue
        for sink in stderr_sinks:
            if sink.level != stderr_level:
                failures.append(f"{log_level.value}: {sink!r} level {sink.level}, expected {stderr_level}")

    assert not failures, "\n".join(failures)


class _LevelProbe(logging.Filter):
    """Notes the severities of the probe logger's records that reach a handler, and swallows them."""

    def __init__(self) -> None:
        super().__init__()
        self.reached: list[int] = []

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != _PROBE_LOGGER:
            return True
        self.reached.append(record.levelno)
        return False


@pytest.mark.parametrize(
    ("log_level", "reaching"),
    [
        pytest.param(LogLevel.DEFAULT, [logging.ERROR], id="default"),
        pytest.param(LogLevel.VERBOSE, [logging.INFO, logging.WARNING, logging.ERROR], id="verbose"),
    ],
)
def test_the_applied_level_decides_which_records_reach_the_stderr_handlers(
    log_level: LogLevel, reaching: list[int]
) -> None:
    logger = get_logger(_PROBE_LOGGER)
    apply_to_root_logger(log_level)
    # A NullHandler neither filters nor writes, so it has nothing to observe.
    probed = [
        (sink, _LevelProbe())
        for sink in delivery_sinks()
        if not isinstance(sink, logging.FileHandler | logging.NullHandler)
    ]
    assert probed, "expected at least one stderr handler after apply_to_root_logger()"
    for sink, probe in probed:
        sink.addFilter(probe)
    try:
        for level in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR):
            logger.log(level, "level probe")
        assert flush_logging(timeout=HANG_GUARD_SECONDS)
    finally:
        for sink, probe in probed:
            sink.removeFilter(probe)

    reached = [(repr(sink), probe.reached) for sink, probe in probed]
    assert all(severities == reaching for _, severities in reached), f"expected {reaching} at each handler: {reached}"


def test_set_log_level_configures_root_file_and_non_file_handlers() -> None:
    """Real-behavior test for :func:`cadrumo.core.logging.set_log_level`.

    Calls :func:`configure_logging` directly (mirroring the production path),
    then calls :func:`set_log_level`, and asserts the effective level on the
    root logger plus file and non-file handlers attached by configuration. The
    levels are those of the handlers that write: the root handlers are
    asynchronous wrappers whose sinks carry them. No mocks; exercises real
    logger state.
    """
    configure_logging()
    set_log_level(logging.ERROR)
    root_logger = logging.getLogger()
    sinks = delivery_sinks()

    assert root_logger.level == logging.DEBUG
    file_sinks = [sink for sink in sinks if isinstance(sink, logging.FileHandler)]
    assert file_sinks, "expected at least one FileHandler after configure_logging()"
    assert all(sink.level == logging.DEBUG for sink in file_sinks)
    non_file_sinks = [sink for sink in sinks if not isinstance(sink, logging.FileHandler)]
    assert non_file_sinks, "expected at least one non-file handler after configure_logging()"
    assert all(sink.level == logging.ERROR for sink in non_file_sinks)


def test_all_handlers_reflect_debug_level_after_call() -> None:
    """Every handler, root and otherwise, has a level consistent with a DEBUG call."""
    configure_logging()
    set_log_level(logging.DEBUG)
    sinks = delivery_sinks()
    assert sinks, "root logger must have handlers"
    for sink in sinks:
        # All handlers must be reachable at DEBUG: file at DEBUG, non-file at
        # DEBUG because DEBUG was requested.
        assert sink.level == logging.DEBUG, f"handler {sink!r} level unexpected"


def test_multiple_set_log_level_calls_each_take_effect() -> None:
    """Successive set_log_level calls each update handler levels idempotently."""
    configure_logging()
    set_log_level(logging.ERROR)
    non_file_before = [sink for sink in delivery_sinks() if not isinstance(sink, logging.FileHandler)]
    assert all(sink.level == logging.ERROR for sink in non_file_before)

    set_log_level(logging.INFO)
    non_file_after = [sink for sink in delivery_sinks() if not isinstance(sink, logging.FileHandler)]
    assert all(sink.level == logging.INFO for sink in non_file_after)
