"""The verified frontend releases a result only after every framed page agrees."""

from __future__ import annotations

import base64
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import lru_cache
from threading import Condition
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import JsonValue

from ....application.operations.frontend_projection import OperationNoPendingInteractionV1, OperationPublicProjectionV1
from ....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationResultProjectionRequestV1,
)
from ....application.operations.persistence.replay import OperationReplayStatus
from ....application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicContractSetV1,
    OperationRegistry,
    OperationSchemaIdentityV1,
)
from ....application.runtime.contracts import (
    RuntimeClientHello,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from ....application.runtime.operation_access import RuntimeOperationPage, RuntimeOperationResultPage
from ....application.runtime.profile_access import RuntimeAccessRefusal, RuntimeRequest
from ....application.runtime.projection_pages import ProjectionPage, ProjectionPageRequest, project_document_page
from ....application.user_profile.access_contracts import AccessDenialCode
from ....application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from ....application.user_profile.view_operation import PROFILE_VIEW_OPERATION_DEFINITION_ID, ProfileViewPageKind
from ....core.hashing import canonical_json_bytes, sha256_hex
from ....core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ..framing import VerifiedRuntimeConnection, accept_runtime_handshake, read_document, write_document
from ..frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_PROFILE_ID = UUID("b1270000-0000-4000-8000-000000000001")
_SESSION_ID = UUID("b1270000-0000-4000-8000-000000000002")
_OPERATION_ID = "a" * 64
_DOCUMENT: dict[str, JsonValue] = {"message": "ñ" * 12_000, "changed": False}
_NOW = datetime(2026, 9, 28, tzinfo=UTC)


class MemoryChannel:
    """Peer-identified byte channel with synchronized in-memory frames."""

    def __init__(self) -> None:
        self._condition = Condition()
        self._data = bytearray()
        self._closed = False
        self._other: MemoryChannel | None = None
        self.peer = RuntimePeer(os_owner_id="synthetic-owner", process_id=1)

    def pair(self, other: MemoryChannel) -> None:
        self._other = other
        other._other = self

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        with self._condition:
            while len(self._data) < count:
                if self._closed or (self._other is not None and self._other._closed):
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                self._condition.wait(remaining)
            result = bytes(self._data[:count])
            del self._data[:count]
            return result

    def read_ready(self) -> bool:
        with self._condition:
            return bool(self._data) or self._closed or (self._other is not None and self._other._closed)

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        other = self._other
        if other is None or time.monotonic() >= deadline:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        with other._condition:
            if self._closed or other._closed:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            other._data.extend(payload)
            other._condition.notify_all()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        if self._other is not None:
            with self._other._condition:
                self._other._condition.notify_all()


def _result() -> OperationResultProjectionRequestV1:
    return OperationResultProjectionRequestV1(
        operation_id=_OPERATION_ID,
        terminal_revision=3,
        definition_contract_digest="c" * 64,
        result_schema=OperationSchemaIdentityV1(schema_id="test.result", schema_version=1, schema_fingerprint="d" * 64),
    )


type ReplyMaker = Callable[[RuntimeOperationResultPage, int, UUID, UUID], RuntimeOperationPage | RuntimeAccessRefusal]


def _exchange(
    replies: int, make_reply: ReplyMaker, *, read_one: bool = False
) -> tuple[RuntimeFrontendClient, object, list[RuntimeOperationResultPage]]:
    client_channel, server_channel = MemoryChannel(), MemoryChannel()
    client_channel.pair(server_channel)
    hello = RuntimeServerHello(product_version="page-test", storage_identity="e" * 64, boot_id=uuid4())
    connection_id = uuid4()
    requests: list[RuntimeOperationResultPage] = []

    def serve() -> None:
        try:
            accept_runtime_handshake(server_channel, identity=hello, deadline=time.monotonic() + 5)
            for index in range(replies):
                request = read_document(server_channel, RuntimeRequest, deadline=time.monotonic() + 5).root
                assert isinstance(request, RuntimeOperationResultPage)
                assert request.profile_id == _PROFILE_ID and request.session_id == _SESSION_ID
                requests.append(request)
                write_document(
                    server_channel,
                    make_reply(request, index, hello.boot_id, connection_id),
                    deadline=time.monotonic() + 5,
                )
        finally:
            server_channel.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        serving = pool.submit(serve)
        connection = VerifiedRuntimeConnection(
            client_channel,
            expected=RuntimeClientHello(product_version=hello.product_version, storage_identity=hello.storage_identity),
            deadline=time.monotonic() + 5,
        )
        client = RuntimeFrontendClient(connection, profile_id=_PROFILE_ID, frontend=OperationFrontendProjection.CLI)
        client._session_id = _SESSION_ID
        try:
            try:
                outcome: object = (
                    client.read_result_page(_result(), ProjectionPageRequest(), deadline=time.monotonic() + 5)
                    if read_one
                    else client.read_result_document(_result(), timeout=5)
                )
            except (RuntimeRefusalError, RuntimeFrontendRefusedError) as error:
                outcome = error
            serving.result(timeout=5)
            return client, outcome, requests
        finally:
            client.close()


def _page(request: RuntimeOperationResultPage, *, boot_id: UUID, connection_id: UUID) -> RuntimeOperationPage:
    return RuntimeOperationPage(
        request_id=request.request_id,
        runtime_boot_id=boot_id,
        connection_id=connection_id,
        operation_id=request.result.operation_id,
        page=project_document_page(_DOCUMENT, request.page),
    )


def test_frontend_reads_one_bound_result_page_without_collecting_full_document() -> None:
    def reply(
        request: RuntimeOperationResultPage, _index: int, boot_id: UUID, connection_id: UUID
    ) -> RuntimeOperationPage:
        return _page(request, boot_id=boot_id, connection_id=connection_id)

    _, result, requests = _exchange(1, reply, read_one=True)
    assert isinstance(result, ProjectionPage)
    assert result.offset == 0
    assert result.total_bytes == len(canonical_json_bytes(_DOCUMENT))
    assert result.decode() == canonical_json_bytes(_DOCUMENT)[:16_384]
    assert len(requests) == 1
    assert requests[0].result == _result()


@pytest.mark.parametrize("fault", ["operation", "offset"])
def test_frontend_refuses_one_page_with_wrong_binding(fault: str) -> None:
    def reply(
        request: RuntimeOperationResultPage, _index: int, boot_id: UUID, connection_id: UUID
    ) -> RuntimeOperationPage:
        correct = _page(request, boot_id=boot_id, connection_id=connection_id)
        if fault == "operation":
            return correct.model_copy(update={"operation_id": "f" * 64})
        return correct.model_copy(update={"page": correct.page.model_copy(update={"offset": 1})})

    _, result, requests = _exchange(1, reply, read_one=True)
    assert len(requests) == 1
    assert isinstance(result, RuntimeRefusalError)
    assert result.reason is RuntimeRefusalCode.INVALID_FRAME


@pytest.mark.parametrize(
    ("code", "expected_error"),
    (
        (RuntimeRefusalCode.DEADLINE_EXCEEDED, RuntimeRefusalError),
        (AccessDenialCode.PERIOD_DENIED, RuntimeFrontendRefusedError),
    ),
)
def test_frontend_preserves_received_wire_refusal_provenance(
    code: RuntimeRefusalCode | AccessDenialCode, expected_error: type[Exception]
) -> None:
    def reply(
        request: RuntimeOperationResultPage, _index: int, boot_id: UUID, connection_id: UUID
    ) -> RuntimeAccessRefusal:
        return RuntimeAccessRefusal(
            request_id=request.request_id,
            runtime_boot_id=boot_id,
            connection_id=connection_id,
            code=code,
        )

    _, result, requests = _exchange(1, reply, read_one=True)
    assert len(requests) == 1
    assert isinstance(result, expected_error)
    assert isinstance(result, RuntimeRefusalError | RuntimeFrontendRefusedError)
    assert result.reason == (code if isinstance(code, RuntimeRefusalCode) else code.value)
    with pytest.raises(expected_error):
        RuntimeFrontendClient._reply(reply(requests[0], 0, uuid4(), uuid4()), RuntimeOperationPage)


def test_frontend_reassembles_verified_multi_page_result() -> None:
    def reply(
        request: RuntimeOperationResultPage, _index: int, boot_id: UUID, connection_id: UUID
    ) -> RuntimeOperationPage:
        return _page(request, boot_id=boot_id, connection_id=connection_id)

    _, result, requests = _exchange(2, reply)
    assert result == _DOCUMENT
    assert requests[0].page == ProjectionPageRequest()
    assert requests[1].page.offset == 16_384
    assert requests[1].page.expected_digest == project_document_page(_DOCUMENT, ProjectionPageRequest()).document_digest
    assert len(canonical_json_bytes(result)) > 16_384


@pytest.mark.parametrize("fault", ["digest", "offset", "operation", "total"])
def test_frontend_refuses_inconsistent_page_without_releasing_partial_result(fault: str) -> None:
    def reply(
        request: RuntimeOperationResultPage, index: int, boot_id: UUID, connection_id: UUID
    ) -> RuntimeOperationPage:
        correct = _page(request, boot_id=boot_id, connection_id=connection_id)
        if (fault == "digest" and index == 1) or (fault != "digest" and index == 0):
            if fault == "digest":
                return correct.model_copy(
                    update={"page": correct.page.model_copy(update={"document_digest": "f" * 64})}
                )
            if fault == "total":
                return correct.model_copy(
                    update={"page": correct.page.model_copy(update={"total_bytes": correct.page.total_bytes + 1})}
                )
            if fault == "offset":
                return correct.model_copy(update={"page": correct.page.model_copy(update={"offset": 1})})
            return correct.model_copy(update={"operation_id": "b" * 64})
        return correct

    _, result, _ = _exchange(2 if fault in {"digest", "total"} else 1, reply)
    assert isinstance(result, RuntimeRefusalError)
    assert result.reason is RuntimeRefusalCode.INVALID_FRAME
    assert "ñ" not in str(result)


def test_frontend_discards_first_page_when_later_output_is_refused() -> None:
    def reply(
        request: RuntimeOperationResultPage, index: int, boot_id: UUID, connection_id: UUID
    ) -> RuntimeOperationPage | RuntimeAccessRefusal:
        if index:
            return RuntimeAccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=boot_id,
                connection_id=connection_id,
                code=AccessDenialCode.OPERATION_UNAVAILABLE,
            )
        return _page(request, boot_id=boot_id, connection_id=connection_id)

    _, result, requests = _exchange(2, reply)
    assert len(requests) == 2
    assert isinstance(result, RuntimeFrontendRefusedError)
    assert "ñ" not in str(result)


def test_frontend_refuses_digest_correct_but_noncanonical_json() -> None:
    encoded = b'{ "value": 1 }'

    def reply(
        request: RuntimeOperationResultPage, _index: int, boot_id: UUID, connection_id: UUID
    ) -> RuntimeOperationPage:
        return RuntimeOperationPage(
            request_id=request.request_id,
            runtime_boot_id=boot_id,
            connection_id=connection_id,
            operation_id=request.result.operation_id,
            page=ProjectionPage(
                offset=0,
                total_bytes=len(encoded),
                document_digest=sha256_hex(encoded),
                encoded=base64.b64encode(encoded).decode("ascii"),
            ),
        )

    _, result, _ = _exchange(1, reply)
    assert isinstance(result, RuntimeRefusalError)
    assert result.reason is RuntimeRefusalCode.INVALID_FRAME


def test_frontend_does_not_request_first_result_page_after_absolute_deadline() -> None:
    requests: list[object] = []

    def record_request(request: object, *, deadline: float) -> object:
        requests.append((request, deadline))
        raise AssertionError("expired deadline must be checked before the first page request")

    client = cast(RuntimeFrontendClient, SimpleNamespace(operation=record_request))

    with pytest.raises(RuntimeRefusalError) as raised:
        RuntimeFrontendClient.read_result_document(client, _result(), deadline=time.monotonic() - 1)

    assert raised.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    assert requests == []


def test_frontend_zero_timeout_keeps_deadline_refusal_without_requesting_a_page() -> None:
    requests: list[object] = []

    def record_request(request: object, *, deadline: float) -> object:
        requests.append((request, deadline))
        raise AssertionError("zero timeout must be refused before the first page request")

    client = cast(RuntimeFrontendClient, SimpleNamespace(operation=record_request))

    with pytest.raises(RuntimeRefusalError) as raised:
        RuntimeFrontendClient.read_result_document(client, _result(), timeout=0)

    assert raised.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    assert requests == []


@lru_cache(maxsize=1)
def _profile_view_contracts() -> OperationPublicContractSetV1:
    definition = next(
        definition
        for definition in build_user_profile_operation_definitions()
        if definition.definition_id == PROFILE_VIEW_OPERATION_DEFINITION_ID
    )
    registration = next(
        registration
        for registration in build_user_profile_operation_registrations((definition,))
        if registration.contract.definition_id == PROFILE_VIEW_OPERATION_DEFINITION_ID
    )
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)).public_contract_set


def test_profile_view_terminal_refusal_exposes_registered_refusal_code_without_requesting_result() -> None:
    contracts = _profile_view_contracts()
    contract = contracts.definitions[0]
    profile_id = uuid4()
    refusal_code = "REFUSED_PROFILE_ACCESS"
    projection = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=PROFILE_VIEW_OPERATION_DEFINITION_ID,
        subject_ref=f"profile:{profile_id}",
        revision=1,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=contracts.contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        phase_code=None,
        started_at=_NOW,
        updated_at=_NOW,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=False,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref=None,
        refusal_ref=refusal_code,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    observation = OperationObservationSuccessV1(
        projection=projection,
        event_page=OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=0,
            requested_cursor=0,
            status=OperationReplayStatus.CAUGHT_UP,
            events=(),
            next_cursor=0,
            restart_cursor=None,
        ),
    )
    submitted: list[object] = []
    started: list[object] = []
    observed: list[object] = []

    def contract_lookup(definition_id: str, *, deadline: float) -> object:
        del deadline
        assert definition_id == PROFILE_VIEW_OPERATION_DEFINITION_ID
        return contract

    def submit(request: object, *, deadline: float) -> str:
        del deadline
        submitted.append(request)
        return _OPERATION_ID

    def start(operation_id: str, *, deadline: float) -> None:
        del deadline
        started.append(operation_id)

    def observe(operation_id: str, *, deadline: float) -> OperationObservationSuccessV1:
        del deadline
        observed.append(operation_id)
        return observation

    def result(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a refused terminal projection must not request its result")

    client = cast(
        RuntimeFrontendClient,
        SimpleNamespace(
            profile_id=profile_id,
            contract=contract_lookup,
            submit=submit,
            start=start,
            observe=observe,
            result=result,
        ),
    )

    with pytest.raises(RuntimeFrontendRefusedError) as raised:
        RuntimeFrontendClient.read_profile_view(client, (ProfileViewPageKind.FACTS,))

    assert raised.value.reason == refusal_code
    assert len(submitted) == len(started) == len(observed) == 1
    assert started == observed == [_OPERATION_ID]
