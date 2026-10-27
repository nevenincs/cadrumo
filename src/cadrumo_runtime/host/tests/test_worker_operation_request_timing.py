"""Each operation-channel request leaves a start record and an elapsed record naming only its closed type.

The dispatch loop runs for real; the channel read and the handler are replaced
so the timing and the fields it logs are decided here and nowhere else.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.tests.log_records import delivered_records
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_runtime.contracts.profile_worker import (
    ProfileWorkerContractRequest,
    ProfileWorkerRequest,
    ProfileWorkerSubmitRequest,
)

from ...adapters.worker_transport import WorkerChannel
from .. import worker_operation_requests
from ..operation_host import ProfileWorkerOperationHost
from ..worker_submission_staging import WorkerSubmissionStaging

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOGGER_NAME = worker_operation_requests.__name__
_PRIVATE_PAYLOAD = "synthetic-private-payload-canary"
_PRIVATE_KEY = "synthetic-private-idempotency-canary"


class _Channel:
    def __init__(self) -> None:
        self.written: list[bytes] = []

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        assert deadline > 0
        self.written.append(bytes(payload))


def _identity() -> ProfileWorkerIdentity:
    return ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )


def _contract_request() -> ProfileWorkerContractRequest:
    return ProfileWorkerContractRequest(request_id=uuid4(), session_id=uuid4(), definition_id="ledger.rule.add")


async def _serve(
    monkeypatch: pytest.MonkeyPatch,
    request: ProfileWorkerContractRequest | ProfileWorkerSubmitRequest,
    handler: Callable[..., Awaitable[None]],
    *,
    channel: _Channel | None = None,
) -> None:
    """Run the real loop for one received request, then end it with a cancellation at the next read."""
    received = False

    async def receive(*_args: object, **_keywords: object) -> ProfileWorkerRequest:
        nonlocal received
        if received:
            raise asyncio.CancelledError
        received = True
        return ProfileWorkerRequest(request)

    monkeypatch.setattr(worker_operation_requests, "receive", receive)
    monkeypatch.setattr(worker_operation_requests, "_dispatch_request", handler)
    uploads = WorkerSubmissionStaging()
    operations = SimpleNamespace(custody=SimpleNamespace(identity=_identity()))
    try:
        with ThreadPoolExecutor(max_workers=2) as input_executor:
            await worker_operation_requests.operate(
                cast(WorkerChannel, channel or _Channel()),
                cast(ProfileWorkerOperationHost, operations),
                asyncio.Event(),
                uploads,
                asyncio.Event(),
                input_executor,
            )
    finally:
        uploads.close()


def _records(caplog: pytest.LogCaptureFixture, name: str) -> list[logging.LogRecord]:
    return [record for record in delivered_records(caplog, _LOGGER_NAME) if record.getMessage() == name]


@pytest.mark.asyncio
async def test_a_prompt_request_logs_its_closed_type_and_definition_at_debug(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def handler(*_args: object) -> None:
        return None

    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME), pytest.raises(asyncio.CancelledError):
        await _serve(monkeypatch, _contract_request(), handler)

    (started,) = _records(caplog, "profile_worker_operation_request_started")
    (elapsed,) = _records(caplog, "profile_worker_operation_request_elapsed")
    for record in (started, elapsed):
        assert record.levelno == logging.DEBUG
        assert record.__dict__["request_type"] == "ProfileWorkerContractRequest"
        assert record.__dict__["definition_id"] == "ledger.rule.add"
    assert started.__dict__["outcome"] == "started"
    assert elapsed.__dict__["outcome"] == "completed"
    assert 0 <= elapsed.__dict__["elapsed_seconds"] < worker_operation_requests._OPERATION_REQUEST_SLOW_SECONDS
    assert elapsed.__dict__["budget_seconds"] == worker_operation_requests._OPERATION_REQUEST_SLOW_SECONDS


@pytest.mark.asyncio
async def test_a_request_past_the_slow_bound_is_logged_at_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(worker_operation_requests, "_OPERATION_REQUEST_SLOW_SECONDS", 0.05)

    async def handler(*_args: object) -> None:
        await asyncio.sleep(0.15)

    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME), pytest.raises(asyncio.CancelledError):
        await _serve(monkeypatch, _contract_request(), handler)

    (started,) = _records(caplog, "profile_worker_operation_request_started")
    (elapsed,) = _records(caplog, "profile_worker_operation_request_elapsed")
    assert started.levelno == logging.DEBUG
    assert elapsed.levelno == logging.WARNING
    assert elapsed.__dict__["elapsed_seconds"] >= 0.1
    assert elapsed.__dict__["budget_seconds"] == 0.05


@pytest.mark.asyncio
async def test_a_refused_request_is_answered_and_logged_as_refused(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    channel = _Channel()

    async def handler(*_args: object) -> None:
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)

    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME), pytest.raises(asyncio.CancelledError):
        await _serve(monkeypatch, _contract_request(), handler, channel=channel)

    (elapsed,) = _records(caplog, "profile_worker_operation_request_elapsed")
    assert elapsed.__dict__["outcome"] == "refused"
    assert len(channel.written) == 1


@pytest.mark.asyncio
async def test_a_request_that_fails_the_worker_is_logged_as_raised_and_the_failure_propagates(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def handler(*_args: object) -> None:
        raise RuntimeError("synthetic handler failure")

    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME), pytest.raises(RuntimeError, match="synthetic handler"):
        await _serve(monkeypatch, _contract_request(), handler)

    (elapsed,) = _records(caplog, "profile_worker_operation_request_elapsed")
    assert elapsed.__dict__["outcome"] == "raised"


@pytest.mark.asyncio
async def test_no_payload_or_identifier_beyond_the_type_and_definition_reaches_a_record(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    request = ProfileWorkerSubmitRequest(
        request_id=uuid4(),
        session_id=uuid4(),
        frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
        definition_id="ledger.rule.add",
        subject_ref="profile:exact",
        payload_json='{"note":"' + _PRIVATE_PAYLOAD + '"}',
        idempotency_key=_PRIVATE_KEY,
    )

    async def handler(*_args: object) -> None:
        return None

    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME), pytest.raises(asyncio.CancelledError):
        await _serve(monkeypatch, request, handler)

    records = _records(caplog, "profile_worker_operation_request_started") + _records(
        caplog, "profile_worker_operation_request_elapsed"
    )
    assert len(records) == 2
    carried = {
        "request_type": "ProfileWorkerSubmitRequest",
        "definition_id": "ledger.rule.add",
    }
    for record in records:
        assert {name: record.__dict__[name] for name in carried} == carried
        assert not {"request_id", "session_id", "subject_ref", "payload_json", "idempotency_key"}.intersection(
            record.__dict__
        )
        rendered = repr(record.__dict__) + record.getMessage()
        assert _PRIVATE_PAYLOAD not in rendered and _PRIVATE_KEY not in rendered
        assert str(request.session_id) not in rendered and str(request.request_id) not in rendered
