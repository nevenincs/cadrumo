"""A read the worker cannot serve is answered, and the worker every session shares serves the next call.

The runtime, the native transport, the session authority, the profile worker
and the encrypted profile store are real. A work unit is made to vanish by
this process writing the store directly, because nothing a frontend can do
removes one: discarding a unit keeps its record.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from cadrumo.application.modelo.action_errors import WorkUnitNotFoundError
from cadrumo.application.modelo.operation_definitions import (
    MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
)
from cadrumo.application.modelo.query_read_operation import MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.work_change_contracts import (
    ModeloWorkDiscardBaseline,
    ModeloWorkDiscardRequest,
    ModeloWorkRenamePublicResultV2,
    ModeloWorkRenameRequest,
)
from cadrumo.application.operations.frontend_projection import OperationReviewProjectionReferenceV1
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResponseControlRequestV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationReviewProjectionRequestV1,
)
from cadrumo.application.operations.models import OperationId
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationContract,
    RuntimeOperationContractReply,
    RuntimeOperationControl,
    RuntimeOperationManage,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationPage,
    RuntimeOperationProjected,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationResult,
    RuntimeOperationResultPage,
    RuntimeOperationReview,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileStatus
from cadrumo.application.runtime.projection_pages import ProjectionPageRequest
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import build_error_envelope
from cadrumo.core.operations import OperationTerminalCondition, profile_operation_subject
from cadrumo.core.request_faults import RequestFault
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections
from .stored_sign_in_runtime import stored_sign_in_runtime
from .test_modelo_metadata import _admit, _connect, _LoginObservation, _seed_periods, _submit

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_UNKNOWN_OPERATION = "ab" * 32
_NO_INTERACTION = "cd" * 32

type _Answer = RuntimeOperationReply | RuntimeAccessRefusal


@dataclass(slots=True)
class _Session:
    """One admitted session and the reads it can ask of an operation."""

    connection: VerifiedRuntimeConnection
    profile_id: UUID
    session_id: UUID

    def ask(self, build: Callable[..., RuntimeOperationRequest], **members: object) -> _Answer:
        request = build(request_id=uuid4(), profile_id=self.profile_id, session_id=self.session_id, **members)
        return self.connection.operation(request, deadline=time.monotonic() + 30)

    def contract(self, definition_id: str) -> RuntimeOperationContractReply:
        """Read a contract: a call the worker serves, so it also says the worker is still there."""
        reply = self.ask(RuntimeOperationContract, definition_id=definition_id)
        assert isinstance(reply, RuntimeOperationContractReply), reply
        return reply

    def observe(self, operation_id: OperationId) -> _Answer:
        return self.ask(
            RuntimeOperationObserve,
            observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32),
        )

    def settled(self, operation_id: OperationId) -> OperationObservationSuccessV1:
        deadline = time.monotonic() + 30
        while True:
            observed = self.observe(operation_id)
            assert isinstance(observed, RuntimeOperationObserved), observed
            assert isinstance(observed.observation, OperationObservationSuccessV1), observed
            if observed.observation.projection.terminal_condition is not None:
                return observed.observation
            assert time.monotonic() < deadline
            time.sleep(0.05)

    def reads(
        self, operation_id: OperationId, contract: RuntimeOperationContractReply, revision: int
    ) -> dict[str, Callable[[], _Answer]]:
        """Return every read of one operation: its observation, result, result page, review and review inspection."""
        schema = contract.contract.result_schema
        assert schema is not None
        digest = contract.contract.definition_contract_digest
        result = OperationResultProjectionRequestV1(
            operation_id=operation_id,
            terminal_revision=revision,
            definition_contract_digest=digest,
            result_schema=schema,
        )
        review = OperationReviewProjectionRequestV1(
            reference=OperationReviewProjectionReferenceV1(
                operation_id=operation_id,
                interaction_id=_NO_INTERACTION,
                revision=revision,
                review_projection_schema=schema,
                definition_contract_digest=digest,
                expires_at=None,
            )
        )
        inspection = OperationResponseControlRequestV1(
            operation_id=operation_id,
            interaction_id=_NO_INTERACTION,
            revision=revision,
            actor_ref=f"session:{self.session_id}",
        )
        return {
            "observe": lambda: self.observe(operation_id),
            "result": lambda: self.ask(RuntimeOperationResult, result=result),
            "result_page": lambda: self.ask(RuntimeOperationResultPage, result=result, page=ProjectionPageRequest()),
            "review": lambda: self.ask(RuntimeOperationReview, review=review),
            "inspect": lambda: self.ask(RuntimeOperationManage, management=inspection),
        }


def _refusal_codes(answers: dict[str, _Answer]) -> dict[str, object]:
    return {
        name: answer.code if isinstance(answer, RuntimeAccessRefusal) else type(answer).__name__
        for name, answer in answers.items()
    }


@pytest.mark.anyio
async def test_a_read_of_an_operation_that_does_not_exist_or_is_another_sessions_is_answered_and_the_worker_serves_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    definition_id = MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):

        def admitted(frontend: OperationFrontendProjection) -> _Session:
            connection = runtime.connect()
            reply = runtime.resume(connection, frontend)
            assert isinstance(reply, RuntimeProfileStatus), reply
            assert reply.status.session_id is not None
            return _Session(connection, runtime.profile_id, reply.status.session_id)

        owner, other = admitted(OperationFrontendProjection.MCP), admitted(OperationFrontendProjection.TUI)
        contract = owner.contract(definition_id)
        submitted = owner.ask(
            RuntimeOperationSubmit,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(runtime.profile_id)),
            payload_json=json.dumps({"profile_id": str(runtime.profile_id), "catalogue_only": True}),
        )
        assert isinstance(submitted, RuntimeOperationSubmitted), submitted

        unknown: dict[str, _Answer] = {}
        for name, read in owner.reads(_UNKNOWN_OPERATION, contract, 0).items():
            unknown[name] = read()
            owner.contract(definition_id)
        foreign: dict[str, _Answer] = {}
        for name, read in other.reads(submitted.receipt.operation_id, contract, 0).items():
            foreign[name] = read()
            other.contract(definition_id)

    assert _refusal_codes(unknown) == {
        "observe": AccessDenialCode.OPERATION_UNAVAILABLE,
        "result": AccessDenialCode.OPERATION_UNAVAILABLE,
        "result_page": AccessDenialCode.OPERATION_UNAVAILABLE,
        "review": AccessDenialCode.OPERATION_UNAVAILABLE,
        "inspect": AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED,
    }
    # Sessions of one profile are the same person's: another of them reads what this one submitted.
    assert _refusal_codes(foreign) == {
        "observe": RuntimeOperationObserved.__name__,
        "result": RuntimeOperationProjected.__name__,
        "result_page": RuntimeOperationPage.__name__,
        "review": AccessDenialCode.OPERATION_DENIED,
        "inspect": AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED,
    }


@dataclass(slots=True)
class _ServedUnits:
    """A running runtime over a profile that holds two work units, and the way to make them vanish."""

    session: _Session
    first: WorkUnit
    second: WorkUnit
    remove_every_unit: Callable[[], None]

    def rename(self, unit: WorkUnit, new_name: str) -> OperationId:
        submitted = _submit(
            self.session.connection,
            self.session.profile_id,
            self.session.session_id,
            definition_id=MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
            subject_ref=unit.work_unit_id,
            payload_json=ModeloWorkRenameRequest(
                work_unit_id=unit.work_unit_id,
                new_name=new_name,
                observed_name=unit.name,
                observed_updated_at=unit.updated_at,
                actor="synthetic-operator",
            ).model_dump_json(),
        )
        assert isinstance(submitted, RuntimeOperationSubmitted), submitted
        return submitted.receipt.operation_id

    def run(self, operation_id: OperationId) -> OperationObservationSuccessV1:
        started = self.session.ask(RuntimeOperationControl, action="operation_start", operation_id=operation_id)
        assert not isinstance(started, RuntimeAccessRefusal), started
        settled = self.session.settled(operation_id)
        assert settled.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED, settled
        return settled


@contextmanager
def _served_units(tmp_path: Path) -> Generator[_ServedUnits]:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    try:
        installation = runtime_installation(
            storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
        )
        with administration_subject(
            tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
        ) as subject:
            profile_id = subject.store.binding.profile_id
            first, second = _seed_periods(profile_id)
            # This process keeps its own view of the store open, to write it behind the worker later.
            catalogue = WorkUnitCatalogueRepository(
                bucket_id=str(profile_id), objects=secure_object_repository_for_active_bucket()
            )

            def remove_every_unit() -> None:
                catalogue.save(WorkUnitCatalogue())
                assert len(catalogue.load()) == 0

            stop, boot = Event(), uuid4()
            profiles = RuntimeProfileConnections(
                storage_root=root,
                storage_identity=endpoint.storage_identity,
                runtime_boot_id=boot,
                stop=stop,
                capture_login=lambda _channel: _LoginObservation(),
                secret_store=lambda: subject.native,
            )
            profiles.prepare_registry()
            server = RetainedRuntimeTransportServer(
                endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
            )
            with ThreadPoolExecutor(max_workers=1) as pool:
                running = pool.submit(server.serve)
                try:
                    assert server.ready.wait(3)
                    connection = _connect(endpoint)
                    try:
                        session_id = _admit(connection, profile_id, method="password", proof=PROFILE_INPUT.encode())
                        yield _ServedUnits(
                            _Session(connection, profile_id, session_id), first, second, remove_every_unit
                        )
                    finally:
                        connection.close()
                finally:
                    primary = sys.exception()
                    close_active_bucket_session()
                    stop.set()
                    try:
                        running.result(timeout=20)
                    except Exception:
                        if primary is None:
                            raise
    finally:
        endpoint.close()


def test_a_read_after_its_work_unit_was_discarded_is_served_because_a_discard_keeps_the_unit(tmp_path: Path) -> None:
    with _served_units(tmp_path) as served:
        session = served.session
        contract = session.contract(MODELO_WORK_RENAME_OPERATION_DEFINITION_ID)
        renamed = served.rename(served.second, "synthetic renamed unit")
        settled = served.run(renamed)
        reads = session.reads(renamed, contract, settled.projection.revision)
        result = reads["result"]()
        assert isinstance(result, RuntimeOperationProjected), result
        unit = (
            OperationResultProjectionSuccessV1[ModeloWorkRenamePublicResultV2]
            .model_validate_json(json.dumps(result.document))
            .projection.unit
        )
        discarded = _submit(
            session.connection,
            session.profile_id,
            session.session_id,
            definition_id=MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
            subject_ref=unit.work_unit_id,
            payload_json=ModeloWorkDiscardRequest(
                baseline=ModeloWorkDiscardBaseline(
                    work_unit_id=unit.work_unit_id, name=unit.name, observed_updated_at=unit.updated_at
                ),
                reason="synthetic discard",
                actor="synthetic-operator",
            ).model_dump_json(),
        )
        assert isinstance(discarded, RuntimeOperationSubmitted), discarded
        served.run(discarded.receipt.operation_id)

        after = {name: reads[name]() for name in ("observe", "result", "result_page")}
        session.contract(MODELO_WORK_RENAME_OPERATION_DEFINITION_ID)

    assert _refusal_codes(after) == {
        "observe": RuntimeOperationObserved.__name__,
        "result": RuntimeOperationProjected.__name__,
        "result_page": RuntimeOperationPage.__name__,
    }


def test_a_read_after_its_work_unit_has_gone_is_refused_with_the_registered_error_and_the_worker_serves_on(
    tmp_path: Path,
) -> None:
    with _served_units(tmp_path) as served:
        session = served.session
        contract = session.contract(MODELO_WORK_RENAME_OPERATION_DEFINITION_ID)
        settled_rename = served.rename(served.second, "synthetic settled rename")
        settled = served.run(settled_rename)
        waiting_rename = served.rename(served.first, "synthetic waiting rename")
        served.remove_every_unit()

        answers: dict[str, _Answer] = {}
        for name, read in session.reads(settled_rename, contract, settled.projection.revision).items():
            answers[f"{name} of a settled operation"] = read()
            session.contract(MODELO_WORK_RENAME_OPERATION_DEFINITION_ID)
        for name, read in session.reads(waiting_rename, contract, 0).items():
            answers[f"{name} of a waiting operation"] = read()
            session.contract(MODELO_WORK_RENAME_OPERATION_DEFINITION_ID)

    def gone(unit: WorkUnit) -> tuple[AutomationCustodyCode, tuple[RequestFault, ...]]:
        # The error the resolver raises for a unit the store no longer holds, as the command line prints it.
        printed = build_error_envelope(
            WorkUnitNotFoundError(
                translated_message="application.modelo.errors.work_unit_not_found",
                context={"work_unit_id": unit.work_unit_id},
            )
        )
        assert printed.code == "ERROR_MODELO_WORK_UNIT_NOT_FOUND"
        return AutomationCustodyCode.INVALID, (RequestFault(location=(), type=printed.code, message=printed.message),)

    told = {
        name: (answer.code, answer.request_faults) if isinstance(answer, RuntimeAccessRefusal) else answer
        for name, answer in answers.items()
    }
    reads = ("observe", "result", "result_page", "review", "inspect")
    assert told == {
        **{f"{name} of a settled operation": gone(served.second) for name in reads},
        **{f"{name} of a waiting operation": gone(served.first) for name in reads},
    }
