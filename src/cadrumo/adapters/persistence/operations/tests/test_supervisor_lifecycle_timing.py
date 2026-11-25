"""Timing observes real committed transitions without becoming operation authority."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from time import time_ns
from typing import override

import pytest

from cadrumo.application.operations.models import OperationRequest
from cadrumo.core.logging import get_logger
from cadrumo.core.operations import OperationLifecycle, OperationTerminalCondition
from cadrumo.tests.log_records import delivered_records

from ...storage.tests.secure_sql import isolated_runtime_profile
from .supervision_support import run_to_settlement
from .supervisor_test_support import (
    ImmediateResultExecutor,
    RegisteredRefusalExecutor,
    UnregisteredSupervisorRequestRefinement,
    operation_repositories,
    operation_supervisor,
    supervisor_registry,
    supervisor_request,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LOGGER = "cadrumo.application.operations.lifecycle_timing"
_OPERATION_ID = "3" * 64
_DEFINITION = "operation.supervisor.test"
_TIMING = re.compile(
    r"operation timing stage=(admitted|running|settled) epoch_ms=(\d+) operation=([a-f0-9]{64}) definition=(\S+)"
)


@pytest.mark.parametrize(
    ("executor_type", "condition"),
    [
        (ImmediateResultExecutor, OperationTerminalCondition.SUCCEEDED),
        (RegisteredRefusalExecutor, OperationTerminalCondition.REFUSED),
    ],
)
def test_committed_transitions_have_wall_time_and_only_public_coordinates(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    executor_type: type[ImmediateResultExecutor] | type[RegisteredRefusalExecutor],
    condition: OperationTerminalCondition,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, caplog.at_level(logging.INFO, logger=_LOGGER):
        journal, leases, operands = operation_repositories(
            storage_root=tmp_path / "operations", profile_objects=profile.repository
        )
        supervisor = operation_supervisor(
            registry=supervisor_registry(executor_type=executor_type, build=executor_type),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        observed: list[tuple[int, int]] = []

        async def exercise() -> None:
            before = time_ns() // 1_000_000
            request = supervisor_request(subject_ref="private-subject-canary", idempotency_key="private-key-canary")
            operation_id = await supervisor.submit(request, operation_id=_OPERATION_ID)
            observed.append((before, time_ns() // 1_000_000))
            assert (await journal.load(operation_id)).lifecycle is OperationLifecycle.CREATED
            assert await supervisor.submit(request, operation_id="4" * 64) == operation_id
            before = time_ns() // 1_000_000
            running = await supervisor.start(operation_id)
            observed.append((before, time_ns() // 1_000_000))
            assert running.lifecycle is OperationLifecycle.RUNNING
            before = time_ns() // 1_000_000
            settled = await supervisor.settled(operation_id)
            observed.append((before, time_ns() // 1_000_000))
            assert settled.terminal_condition is condition
            assert (await journal.load(operation_id)).terminal_receipt == settled.terminal_receipt
            await supervisor.shutdown()

        asyncio.run(exercise())
        records = delivered_records(caplog, _LOGGER)

    assert len(records) == 3
    for record, stage, (before, after) in zip(records, ("admitted", "running", "settled"), observed, strict=True):
        match = _TIMING.fullmatch(record.getMessage())
        assert match is not None
        assert match[1] == stage
        assert before <= int(match[2]) <= after
        assert match[3] == _OPERATION_ID
        assert match[4] == _DEFINITION
        assert record.levelno == logging.INFO


def test_rejected_submission_emits_no_committed_transition(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, caplog.at_level(logging.INFO, logger=_LOGGER):
        journal, leases, operands = operation_repositories(
            storage_root=tmp_path / "operations", profile_objects=profile.repository
        )
        supervisor = operation_supervisor(
            registry=supervisor_registry(executor_type=ImmediateResultExecutor, build=ImmediateResultExecutor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )

        async def reject() -> None:
            request = OperationRequest(
                definition_id=_DEFINITION,
                subject_ref="private-subject-canary",
                payload=UnregisteredSupervisorRequestRefinement(value="private-payload-canary"),
            )
            with pytest.raises(ValueError, match="request payload does not match definition"):
                await supervisor.submit(request, operation_id=_OPERATION_ID)
            await supervisor.shutdown()

        asyncio.run(reject())
        assert delivered_records(caplog, _LOGGER) == []


class FailingTimingSink(logging.Handler):
    """An unavailable diagnostic output, independent of the operation journal."""

    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.attempts += 1
        raise OSError("timing sink unavailable")


def test_unavailable_timing_sink_does_not_change_settlement(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    logger = get_logger(_LOGGER)
    sink = FailingTimingSink()
    logger.addHandler(sink)
    try:
        with isolated_runtime_profile(tmp_path=tmp_path) as profile, caplog.at_level(logging.INFO, logger=_LOGGER):
            journal, leases, operands = operation_repositories(
                storage_root=tmp_path / "operations", profile_objects=profile.repository
            )
            supervisor = operation_supervisor(
                registry=supervisor_registry(executor_type=ImmediateResultExecutor, build=ImmediateResultExecutor),
                journal=journal,
                leases=leases,
                operands=operands,
                owner_id="1" * 64,
                token="2" * 64,
            )

            async def settle() -> None:
                operation_id = await supervisor.submit(supervisor_request(), operation_id=_OPERATION_ID)
                terminal = await run_to_settlement(supervisor, operation_id)
                assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert (await journal.load(operation_id)).terminal_receipt == terminal.terminal_receipt
                await supervisor.shutdown()

            asyncio.run(settle())
            delivered_records(caplog, _LOGGER)
            assert sink.attempts == 3
    finally:
        logger.removeHandler(sink)
        sink.close()
