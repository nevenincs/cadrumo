"""An agent service admitted to a test-owned native runtime, answering its profile's model runs.

The runtime side is production: the installed descriptor declares model runs,
a person's password session admits the service connection, the service claims
its lease, and every run crosses the runtime's relay, fetch and completion
fences as secret frames. The service connection is the real installed-service
client. Two parts are test ports. Installed image verification is the
explicitly controlled verifier the service-record tests use, so this is not
native installed-service evidence. The agent-side answer behind the connection
is the caller's :class:`ModelRunAnswers`, standing in for the agent service's
run service and the cadrumo-agent process behind it.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Generator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from typing import Protocol
from uuid import UUID

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo_client.contracts.access_vocabulary import AccessScope
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunHeader,
    ModelRunLane,
    ModelRunOutcome,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
    ModelRunRequested,
    ModelRunRoleSelection,
    ModelRunServed,
    decode_model_run_body,
)
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.contracts.service_access import (
    InstalledServiceDescriptor,
    ServiceCapability,
    ServiceConnected,
)
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.service_client import InstalledServiceClient
from cadrumo_client.transport.transport_cleanup import TransportCleanup
from cadrumo_client.transport.windows import WindowsEndpoint

from ..test_profile_connections import login
from ..test_service_records import ControlledServiceVerifier

__all__ = [
    "MODEL_RUN_SERVICE_ID",
    "ModelRunAnswers",
    "admitted_model_run_service",
    "model_run_service_descriptor",
]

MODEL_RUN_SERVICE_ID = "synthetic-model-run-service"
_ANSWERING_THREADS = 4


class ModelRunAnswers(Protocol):
    """The agent-side answers to a profile's lane lookups, selection reads and runs."""

    def lookup(self, role: str) -> ModelRunLane | ModelRunRefusal:
        """Return the lane a run for ``role`` would use."""
        ...

    def selections(self) -> tuple[ModelRunRoleSelection, ...] | ModelRunRefusal:
        """Return every role's selection state."""
        ...

    def run(self, header: ModelRunHeader, body: ModelRunBody) -> ModelRunOutput | ModelRunRefusal:
        """Answer one run."""
        ...


def model_run_service_descriptor() -> InstalledServiceDescriptor:
    """Return the installed descriptor of a service that may answer model runs and holds no records."""
    return InstalledServiceDescriptor(
        service_id=MODEL_RUN_SERVICE_ID,
        launch_image=sys.executable,
        launch_module="synthetic.model_run_service",
        image_digest="1" * 64,
        descriptor_digest="4" * 64,
        record_capabilities=(),
        operation_scope=AccessScope(
            operations=frozenset(),
            actions=frozenset(),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        service_capabilities=(ServiceCapability.MODEL_RUN,),
    )


def _outcome(
    answers: ModelRunAnswers, role: str | None, header: ModelRunHeader | None, body: bytearray
) -> tuple[ModelRunOutcome, bytearray]:
    """Shape one answer as the agent service's relay returns it to the runtime."""
    if header is None:
        if role is None:
            states = answers.selections()
            if isinstance(states, ModelRunRefusal):
                return ModelRunOutcome(refusal=states.code), bytearray()
            return ModelRunOutcome(selections=states), bytearray()
        lane = answers.lookup(role)
        if isinstance(lane, ModelRunRefusal):
            return ModelRunOutcome(refusal=lane.code), bytearray()
        return ModelRunOutcome(lane=lane), bytearray()
    result = answers.run(header, decode_model_run_body(body))
    if isinstance(result, ModelRunRefusal):
        return ModelRunOutcome(refusal=result.code), bytearray()
    text = bytearray(result.text.encode("utf-8"))
    if not text:
        return ModelRunOutcome(refusal=ModelRunRefusalCode.OUTPUT_INVALID), bytearray()
    served = ModelRunServed(
        provider_id=result.provider_id,
        transport=result.transport,
        model=result.model,
        agent_version=result.agent_version,
    )
    return ModelRunOutcome(served=served, text_byte_count=len(text)), text


def _answer(service: InstalledServiceClient, answers: ModelRunAnswers, run_id: UUID) -> None:
    """Fetch, answer and complete one announced run, wiping both secret buffers."""
    fetched = service.model_run_fetch(run_id)
    if fetched is None:
        return
    reply, body = fetched
    try:
        outcome, text = _outcome(answers, reply.role, reply.header, body)
    finally:
        body[:] = bytes(len(body))
    try:
        service.model_run_complete(run_id, outcome, text)
    finally:
        text[:] = bytes(len(text))


def _connect(endpoint: WindowsEndpoint, product_version: str) -> VerifiedConnection:
    return VerifiedConnection(
        endpoint.connect(timeout=3),
        expected=ClientHello(product_version=product_version, storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


@contextmanager
def admitted_model_run_service(
    endpoint: WindowsEndpoint,
    *,
    product_version: str,
    verifier: ControlledServiceVerifier,
    profile_id: UUID,
    passphrase: str,
    answers: ModelRunAnswers,
) -> Generator[None]:
    """Sign a person in, admit one model-run service under that session and answer its runs.

    The runtime serving ``endpoint`` must hold :func:`model_run_service_descriptor`
    and ``verifier``, which is told to admit the service's connection only.
    """
    answering: list[Future[None]] = []
    with ExitStack() as scope:
        human = _connect(endpoint, product_version)
        scope.callback(TransportCleanup(human).close_now)
        signed_in = login(human, profile_id, "password", passphrase.encode())
        assert isinstance(signed_in, ProfileStatus), signed_in
        assert signed_in.status.denial is None and signed_in.status.session_id is not None, signed_in
        verifier.accept_next = True
        connection = _connect(endpoint, product_version)
        scope.callback(TransportCleanup(connection).close_now)
        service = InstalledServiceClient(connection, profile_id=profile_id, service_id=MODEL_RUN_SERVICE_ID)
        assert service.claim() is None
        assert service.connected is not None
        person = FrontendClient(human, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
        person._session_id = signed_in.status.session_id
        admitted = person.service_admission(service.connected.connection_id, MODEL_RUN_SERVICE_ID)
        assert isinstance(admitted, ServiceConnected), admitted
        assert service.claim() is not None
        # The event reader that delivers an announcement must not wait on itself.
        pool = ThreadPoolExecutor(max_workers=_ANSWERING_THREADS, thread_name_prefix="model-run-answer")
        scope.callback(pool.shutdown, wait=True, cancel_futures=True)

        def announced(event: ModelRunRequested) -> None:
            answering.append(pool.submit(_answer, service, answers, event.run_id))

        scope.callback(service.subscribe_model_runs(announced))
        yield
    # A failed answer surfaces here rather than only as a run that never settled.
    failures = [error for future in answering if not future.cancelled() and (error := future.exception()) is not None]
    if failures:
        raise BaseExceptionGroup("model-run answers failed", failures)
