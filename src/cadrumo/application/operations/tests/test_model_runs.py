"""The model-run port bound to one running operation."""

from __future__ import annotations

import asyncio
import threading

import pytest

from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunHeader,
    ModelRunLane,
    ModelRunOutput,
    ModelRunRefusal,
)

from ....core.model_catalogue import ModelRole
from ..model_runs import current_model_run_port, operation_model_run_port, run_with_model_runs
from ..models import OperationIdentity

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_IDENTITY = OperationIdentity(operation_id="a" * 64, definition_id="ledger.evidence.extract", subject_ref="profile:x")
_LANE = ModelRunLane(provider_id="example", transport="cli", model="m")


class _Authority:
    """An execution authority that runs models, recording the loop and identity each call arrived on."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, OperationIdentity, int]] = []

    async def model_run_lookup(self, identity: OperationIdentity, role: str) -> ModelRunLane | ModelRunRefusal:
        self.calls.append(("lookup:" + role, identity, threading.get_ident()))
        return _LANE

    async def model_run(
        self, identity: OperationIdentity, header: ModelRunHeader, body: ModelRunBody
    ) -> ModelRunOutput | ModelRunRefusal:
        self.calls.append(("run:" + header.role, identity, threading.get_ident()))
        return ModelRunOutput(text=body.prompt, provider_id="example", transport="cli", model="m", agent_version="test")


class _NoModels:
    """An execution authority with no door to model runs."""


def test_an_authority_without_model_runs_binds_no_port() -> None:
    async def scenario() -> None:
        assert operation_model_run_port(_NoModels(), _IDENTITY) is None

    asyncio.run(scenario())


def test_the_port_is_bound_for_the_executor_and_gone_afterwards() -> None:
    authority = _Authority()

    async def executor() -> ModelRunLane | ModelRunRefusal:
        port = current_model_run_port()
        assert port is not None
        return await port.lookup(ModelRole.TEXT_EXTRACTION)

    async def scenario() -> None:
        port = operation_model_run_port(authority, _IDENTITY)
        assert await run_with_model_runs(port, executor()) == _LANE
        assert current_model_run_port() is None

    asyncio.run(scenario())
    assert [(name, identity) for name, identity, _ in authority.calls] == [("lookup:text_extraction", _IDENTITY)]


def test_work_on_another_loop_in_a_worker_thread_is_answered_on_the_operations_loop() -> None:
    """Model work often runs under ``asyncio.run`` in a thread; the call returns to the owner's loop."""
    authority = _Authority()
    header = ModelRunHeader(role=ModelRole.VISION_TRANSCRIPTION.value, deadline_seconds=5)
    body = ModelRunBody(prompt="read this page", max_output_tokens=16)

    def blocking_model_work() -> ModelRunOutput | ModelRunRefusal:
        port = current_model_run_port()
        assert port is not None
        return asyncio.run(port.run(header, body))

    async def executor() -> ModelRunOutput | ModelRunRefusal:
        return await asyncio.to_thread(blocking_model_work)

    async def scenario() -> tuple[ModelRunOutput | ModelRunRefusal, int]:
        port = operation_model_run_port(authority, _IDENTITY)
        return await run_with_model_runs(port, executor()), threading.get_ident()

    output, owner_thread = asyncio.run(scenario())

    assert isinstance(output, ModelRunOutput)
    assert output.text == "read this page"
    ((name, identity, answered_on),) = authority.calls
    assert (name, identity) == ("run:vision_transcription", _IDENTITY)
    assert answered_on == owner_thread
