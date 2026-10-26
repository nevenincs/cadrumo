"""Real supervision of the local-reader operations for tests.

Every run goes through the real registry, supervisor, journal and encrypted
operand store. The model runtime is a real loopback endpoint speaking the
Ollama wire shapes. Each role's lane is answered by an execution authority
standing in for the runtime host and the agent service, which have their own
tests; the supervisor binds the model-run port it offers exactly as it binds
the host's. Every model id is synthetic.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator, Mapping
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

from pydantic import BaseModel

from cadrumo_client.contracts.access_vocabulary import AccessAction
from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunHeader,
    ModelRunLane,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
    ModelRunRoleSelection,
)

from .....application.local_reader import RoleLane
from .....application.local_reader_report import (
    build_local_reader_report_definition,
    build_local_reader_report_registration,
)
from .....application.local_reader_status_operation import (
    build_local_reader_status_definition,
    build_local_reader_status_registration,
)
from .....application.operations.composition import OperationComposedServices, compose_operation_services
from .....application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from .....application.operations.models import OperationIdentity, OperationRequest
from .....application.operations.registry import OperationRegistry
from .....application.operations.tests.authority_test_support import unread_authority_operation
from .....core.config import override_settings
from .....core.model_roles import ModelRole
from .....core.operations import OperationEffect, OperationEventKind, OperationTerminalCondition
from .....tests.loopback_llm import SilentLoopbackHandler, read_json_body, serving_loopback, write_json_response
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..journal import OperationJournalRepository
from ..lease import OperationLeaseFilesystemRepository
from ..secure_references import operation_secure_reference_repository

__all__ = [
    "READER_LANES",
    "TEXT_MODEL",
    "VISION_MODEL",
    "LoopbackModelRuntime",
    "SupervisedRun",
    "loopback_model_runtime",
    "provisioning_registry",
    "run_supervised",
    "run_supervised_in",
]

VISION_MODEL = "synthetic-vision:small"
TEXT_MODEL = "synthetic-text:small"


def _on_host_lane(model: str) -> ModelRunLane:
    return ModelRunLane(
        provider_id="ollama",
        transport="api",
        model=model,
        reads_off_host=False,
        licence=None,
        size_bytes=1024,
        vision=None,
        context_length=None,
    )


#: The person's selection: both reader roles on the local lane, no other role selected.
READER_LANES: Mapping[ModelRole, RoleLane] = {
    ModelRole.TEXT_EXTRACTION: _on_host_lane(TEXT_MODEL),
    ModelRole.VISION_TRANSCRIPTION: _on_host_lane(VISION_MODEL),
    ModelRole.COLUMN_ROLE_MAPPING: ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION),
    ModelRole.SUPPLY_NATURE_PROPOSAL: ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION),
}


class _SelectionAuthority:
    """An execution authority that admits every operation and answers each role's lookup from ``lanes``."""

    def __init__(self, lanes: Mapping[ModelRole, RoleLane]) -> None:
        self._lanes = lanes

    async def require[Payload: BaseModel](
        self, *, identity: OperationIdentity, request: OperationRequest[Payload], action: AccessAction
    ) -> None:
        del identity, request, action

    @asynccontextmanager
    async def commit_guard(self, identity: OperationIdentity) -> AsyncGenerator[None]:
        del identity
        yield

    async def model_run_lookup(self, identity: OperationIdentity, role: str) -> ModelRunLane | ModelRunRefusal:
        del identity
        return self._lanes[ModelRole(role)]

    async def model_run_selections(
        self, identity: OperationIdentity
    ) -> tuple[ModelRunRoleSelection, ...] | ModelRunRefusal:
        del identity
        return ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE)

    async def model_run(
        self, identity: OperationIdentity, header: ModelRunHeader, body: ModelRunBody
    ) -> ModelRunOutput | ModelRunRefusal:
        del identity, header, body
        return ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED)


class LoopbackModelRuntime(SilentLoopbackHandler):
    """A loopback runtime answering its version, inventory and resident set, and recording anything sent to it."""

    installed: ClassVar[set[str]] = set()
    residents: ClassVar[set[str]] = set()
    requests: ClassVar[list[tuple[str, Mapping[str, object]]]] = []

    @override
    def do_GET(self) -> None:
        if self.path == "/api/version":
            write_json_response(self, {"version": "0.9.0"}, status=HTTPStatus.OK)
        elif self.path == "/api/tags":
            rows = [{"name": name, "size": 1024, "digest": f"sha256:{name}"} for name in sorted(self.installed)]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        elif self.path == "/api/ps":
            rows = [{"name": name, "size": 1024, "size_vram": 0} for name in sorted(self.residents)]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    @override
    def do_POST(self) -> None:
        # A read sends nothing; whatever arrives is recorded so a test can say so.
        type(self).requests.append((self.path, read_json_body(self)))
        self.send_error(HTTPStatus.NOT_FOUND)


@contextmanager
def loopback_model_runtime(
    *, installed: set[str], residents: set[str], required_headroom_bytes: int | None = None
) -> Generator[str]:
    """Serve the loopback runtime and point the reader's settings at it.

    Admission is overridden open by default, so it does not depend on how busy
    the test host's memory happens to be. ``required_headroom_bytes`` instead
    enforces admission with that safety margin.
    """
    LoopbackModelRuntime.installed = set(installed)
    LoopbackModelRuntime.residents = set(residents)
    LoopbackModelRuntime.requests = []
    with (
        serving_loopback(LoopbackModelRuntime, path="/api/chat") as chat_url,
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_contention_safety_margin_bytes=required_headroom_bytes or 0,
            cadrumo_llm_contention_check_override=required_headroom_bytes is None,
        ),
    ):
        yield chat_url


def provisioning_registry() -> OperationRegistry:
    """Register the two local-reader operations."""
    status = build_local_reader_status_definition()
    report = build_local_reader_report_definition()
    return OperationRegistry(
        definitions=(report, status),
        public_registrations=(
            build_local_reader_report_registration(report),
            build_local_reader_status_registration(status),
        ),
    )


def _services(
    root: Path, registry: OperationRegistry, lanes: Mapping[ModelRole, RoleLane]
) -> tuple[OperationComposedServices, OperationJournalRepository]:
    journal = OperationJournalRepository(storage_root=root)
    services = compose_operation_services(
        registry=registry,
        authority_operation=unread_authority_operation(),
        journal=journal,
        reader=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=operation_secure_reference_repository(),
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=5),
        execution_timeout=timedelta(seconds=60),
        cleanup_timeout=timedelta(seconds=5),
        execution_authority=_SelectionAuthority(lanes),
    )
    return services, journal


@dataclass(frozen=True, slots=True)
class SupervisedRun[ResultT: BaseModel]:
    """One settled operation: its public result, committed effect and published phases."""

    result: ResultT
    effect: OperationEffect
    phases: tuple[str, ...]


def run_supervised[RequestT: BaseModel, ResultT: BaseModel](
    tmp_path: Path,
    request: OperationRequest[RequestT],
    result_type: type[ResultT],
    *,
    lanes: Mapping[ModelRole, RoleLane] = READER_LANES,
) -> SupervisedRun[ResultT]:
    """Settle ``request`` with ``lanes`` selected and resolve its public result as a frontend would."""
    return run_supervised_in(tmp_path, provisioning_registry(), request, result_type, lanes=lanes)


def run_supervised_in[RequestT: BaseModel, ResultT: BaseModel](
    tmp_path: Path,
    registry: OperationRegistry,
    request: OperationRequest[RequestT],
    result_type: type[ResultT],
    *,
    lanes: Mapping[ModelRole, RoleLane] = READER_LANES,
) -> SupervisedRun[ResultT]:
    """Submit, start and settle ``request`` in ``registry``, then resolve its public result as a frontend would."""

    async def run(root: Path) -> SupervisedRun[ResultT]:
        services, journal = _services(root, registry, lanes)
        try:
            submitted = await services.submission.submit(request, actor_ref="operator:local-reader-test")
            operation_id = submitted.receipt.operation_id
            await services.submission.start(operation_id)
            await services.submission.settled(operation_id)
            terminal = await journal.load(operation_id)
            replay = await journal.read_after(operation_id, 0, limit=64)
            observed = await services.observation.observe(
                OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=64)
            )
            assert isinstance(observed, OperationObservationSuccessV1)
            projection = observed.projection
            assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
            schema = projection.definition_contract.result_schema
            assert schema is not None
            resolved = await services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=projection.revision,
                    definition_contract_digest=projection.definition_contract.definition_contract_digest,
                    result_schema=schema,
                ),
                result_type,
            )
        finally:
            await services.shutdown()
        assert isinstance(resolved, OperationResultProjectionSuccessV1)
        assert isinstance(resolved.projection, result_type)
        phases = tuple(event.phase_code for event in replay.events if event.kind is OperationEventKind.PHASE)
        return SupervisedRun(resolved.projection, terminal.effect, phases)

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        return asyncio.run(run(profile.storage_root))
