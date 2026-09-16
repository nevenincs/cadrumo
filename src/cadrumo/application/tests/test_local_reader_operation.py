"""The supervised local-reader operation: load, one-shot setup and request coherence.

Every run goes through the real registry, supervisor, journal and encrypted
operand store. The model runtime is a real loopback endpoint speaking the
Ollama wire shapes; only the process spawner, the installer and the text
fitness probe are injected ports, as production composition injects them.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

import pytest
from pydantic import ValidationError

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...core.config import Settings, override_settings
from ...core.model_catalogue import ModelRole, default_model_runtime_id
from ...core.operations import OperationEffect, OperationEventKind, OperationTerminalCondition
from ...tests.loopback_llm import SilentLoopbackHandler, read_json_body, serving_loopback, write_json_response
from ..local_reader import RoleFitnessOutcome, role_model_targets
from ..local_reader_operation import (
    LOCAL_READER_OPERATION_DEFINITION_ID,
    LocalReaderProvisionAction,
    LocalReaderProvisionOutcome,
    LocalReaderProvisionPublicResultV1,
    LocalReaderProvisionRequest,
    LocalReaderSetupStep,
    LocalReaderSetupStepState,
    build_local_reader_load_request,
    build_local_reader_operation_definition,
    build_local_reader_operation_registration,
    build_local_reader_setup_request,
    local_reader_fact_mapping,
    local_reader_public_verdict,
    local_reader_setup_phase,
    provision_local_reader,
)
from ..operations.composition import OperationComposedServices, compose_operation_services
from ..operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ..operations.models import OperationRequest
from ..operations.registry import OperationRegistry
from ..operations.tests.authority_test_support import unread_authority_operation
from ..provisioning_contracts import ProvisioningPreconditionCondition
from ..provisioning_host import RuntimeInstaller

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_VISION = default_model_runtime_id(ModelRole.VISION_TRANSCRIPTION)
_TEXT = default_model_runtime_id(ModelRole.TEXT_EXTRACTION)
_MAPPING = default_model_runtime_id(ModelRole.COLUMN_ROLE_MAPPING)


class _Runtime(SilentLoopbackHandler):
    """A loopback runtime whose inventory and resident set change as a real one's would."""

    installed: ClassVar[set[str]] = set()
    residents: ClassVar[set[str]] = set()
    pull_fails: ClassVar[bool] = False
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
        body = read_json_body(self)
        type(self).requests.append((self.path, body))
        model = str(body.get("model"))
        if self.path == "/api/pull":
            self._pull(model)
        elif self.path == "/api/generate":
            if model not in self.installed:
                write_json_response(self, {"error": "model not found"}, status=HTTPStatus.NOT_FOUND)
                return
            if "prompt" not in body:
                self.residents.add(model)
                write_json_response(self, {"done": True, "done_reason": "load"}, status=HTTPStatus.OK)
                return
            write_json_response(self, {"done": True, "response": "ok"}, status=HTTPStatus.OK)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _pull(self, model: str) -> None:
        if self.pull_fails:
            lines = [{"status": "pulling manifest"}, {"error": "registry unavailable"}]
        else:
            self.installed.add(model)
            lines = [{"status": "downloading", "completed": 512, "total": 1024}, {"status": "success"}]
        payload = "".join(json.dumps(line) + "\n" for line in lines).encode()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _target_models() -> set[str]:
    return {target.model for target in role_model_targets() if target.model is not None}


@contextmanager
def _runtime(*, installed: set[str], residents: set[str], pull_fails: bool = False) -> Generator[str]:
    _Runtime.installed = set(installed)
    _Runtime.residents = set(residents)
    _Runtime.pull_fails = pull_fails
    _Runtime.requests = []
    with (
        serving_loopback(_Runtime, path="/api/chat") as chat_url,
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_ollama_vision_model=_VISION,
            cadrumo_llm_ollama_text_model=_TEXT,
            cadrumo_llm_ollama_mapping_model=_MAPPING,
            # The loopback models are a few bytes; admission must not depend on
            # how busy the test host's memory happens to be.
            cadrumo_llm_contention_safety_margin_bytes=0,
            cadrumo_llm_contention_check_override=True,
        ),
    ):
        yield chat_url


class _Ports:
    """Injected process and fitness ports that record every call."""

    def __init__(self) -> None:
        self.spawned: list[Path] = []
        self.installers: list[RuntimeInstaller] = []
        self.probed: list[str] = []

    def spawn(self, executable: Path, env: Mapping[str, str]) -> int:
        del env
        self.spawned.append(executable)
        return 1

    def install(self, installer: RuntimeInstaller, executable: Path, timeout_s: float) -> int:
        del executable, timeout_s
        self.installers.append(installer)
        return 0

    def probe(self, model: str, settings: Settings) -> RoleFitnessOutcome:
        del settings
        self.probed.append(model)
        return RoleFitnessOutcome(
            role=ModelRole.TEXT_EXTRACTION,
            model=model,
            fit=True,
            answer_parseable=True,
            grounded=True,
            answer_budget_tokens=1024,
            elapsed_ms=1,
        )


def _services(root: Path, ports: _Ports) -> tuple[OperationComposedServices, OperationJournalRepository]:
    definition = build_local_reader_operation_definition(
        spawn=ports.spawn, run_installer=ports.install, text_probe=ports.probe
    )
    journal = OperationJournalRepository(storage_root=root)
    services = compose_operation_services(
        registry=OperationRegistry(
            definitions=(definition,),
            public_registrations=(build_local_reader_operation_registration(definition),),
        ),
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
    )
    return services, journal


class _Run:
    def __init__(
        self,
        result: LocalReaderProvisionPublicResultV1,
        effect: OperationEffect,
        phases: tuple[str, ...],
    ) -> None:
        self.result = result
        self.effect = effect
        self.phases = phases


def _run(tmp_path: Path, ports: _Ports, request: OperationRequest[LocalReaderProvisionRequest]) -> _Run:
    async def run(root: Path) -> _Run:
        services, journal = _services(root, ports)
        try:
            submitted = await services.submission.submit(request, actor_ref="operator:local-reader-test")
            operation_id = submitted.receipt.operation_id
            await services.submission.start(operation_id)
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
                )
            )
        finally:
            await services.shutdown()
        assert isinstance(resolved, OperationResultProjectionSuccessV1)
        assert isinstance(resolved.projection, LocalReaderProvisionPublicResultV1)
        phases = tuple(event.phase_code for event in replay.events if event.kind is OperationEventKind.PHASE)
        return _Run(resolved.projection, terminal.effect, phases)

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        return asyncio.run(run(profile.storage_root))


def _states(result: LocalReaderProvisionPublicResultV1) -> dict[LocalReaderSetupStep, LocalReaderSetupStepState]:
    return {step.step: step.state for step in result.steps}


@pytest.mark.timeout(120)
def test_load_brings_a_pulled_model_into_memory_and_reports_it_resident(tmp_path: Path) -> None:
    ports = _Ports()
    with _runtime(installed={_TEXT}, residents=set()):
        run = _run(tmp_path, ports, build_local_reader_load_request(ModelRole.TEXT_EXTRACTION))

    assert run.result.action is LocalReaderProvisionAction.LOAD
    assert run.result.succeeded is True
    (item,) = run.result.models
    assert item.model == _TEXT
    assert item.resident is True
    assert item.already_satisfied is False
    assert run.effect is OperationEffect.UPDATED
    assert _TEXT in _Runtime.residents
    loads = [body for path, body in _Runtime.requests if path == "/api/generate"]
    assert loads == [{"model": _TEXT, "keep_alive": "30m", "stream": False}], "a load must not run inference"


@pytest.mark.timeout(120)
def test_loading_a_resident_model_sends_nothing(tmp_path: Path) -> None:
    ports = _Ports()
    with _runtime(installed={_TEXT}, residents={_TEXT}):
        run = _run(tmp_path, ports, build_local_reader_load_request(ModelRole.TEXT_EXTRACTION))

    (item,) = run.result.models
    assert item.succeeded is True
    assert item.already_satisfied is True
    assert run.effect is OperationEffect.NONE
    assert _Runtime.requests == []


@pytest.mark.timeout(120)
def test_load_refuses_a_model_that_was_never_pulled_instead_of_fetching_it(tmp_path: Path) -> None:
    ports = _Ports()
    with _runtime(installed=set(), residents=set()):
        run = _run(tmp_path, ports, build_local_reader_load_request(ModelRole.TEXT_EXTRACTION))

    (item,) = run.result.models
    assert run.result.succeeded is False
    assert item.failed_condition_id == ProvisioningPreconditionCondition.MODEL_INSTALLED
    verdict = local_reader_public_verdict(item.verdict_condition_id, item.verdict_facts)
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.MODEL_INSTALLED
    assert local_reader_fact_mapping(item.facts) == {"model": _TEXT, "model_installed": False}
    assert _Runtime.requests == [], "nothing may be pulled or loaded for an absent model"
    assert run.effect is OperationEffect.NONE


@pytest.mark.timeout(180)
def test_setup_pulls_loads_and_verifies_every_role_in_order(tmp_path: Path) -> None:
    ports = _Ports()
    with _runtime(installed=set(), residents=set()):
        models = _target_models()
        run = _run(tmp_path, ports, build_local_reader_setup_request(consent=False))
        installed_after = set(_Runtime.installed)
        residents_after = set(_Runtime.residents)

    assert run.result.succeeded is True, run.result
    assert run.result.stopped_step is None
    assert _states(run.result) == {
        LocalReaderSetupStep.INSTALL: LocalReaderSetupStepState.UNCHANGED,
        LocalReaderSetupStep.START: LocalReaderSetupStepState.UNCHANGED,
        LocalReaderSetupStep.PULL: LocalReaderSetupStepState.CHANGED,
        LocalReaderSetupStep.LOAD: LocalReaderSetupStepState.CHANGED,
        LocalReaderSetupStep.VERIFY: LocalReaderSetupStepState.UNCHANGED,
    }
    assert [step.step for step in run.result.steps] == list(LocalReaderSetupStep)
    assert installed_after == models
    assert residents_after == models
    step_phases = tuple(phase for phase in run.phases if ".step." in phase)
    assert step_phases == tuple(local_reader_setup_phase(step) for step in LocalReaderSetupStep)
    assert run.effect is OperationEffect.UPDATED
    assert ports.spawned == []
    assert ports.installers == []
    assert _TEXT in ports.probed


@pytest.mark.timeout(180)
def test_setup_over_a_ready_reader_redoes_nothing(tmp_path: Path) -> None:
    ports = _Ports()
    with override_settings(
        cadrumo_llm_ollama_vision_model=_VISION,
        cadrumo_llm_ollama_text_model=_TEXT,
        cadrumo_llm_ollama_mapping_model=_MAPPING,
    ):
        models = _target_models()
    with _runtime(installed=models, residents=models):
        run = _run(tmp_path, ports, build_local_reader_setup_request(consent=False))
        pulls = [path for path, _ in _Runtime.requests if path == "/api/pull"]
        loads = [body for path, body in _Runtime.requests if path == "/api/generate" and "prompt" not in body]

    assert run.result.succeeded is True
    assert set(_states(run.result).values()) == {LocalReaderSetupStepState.UNCHANGED}
    assert pulls == []
    assert loads == []
    assert run.effect is OperationEffect.NONE
    assert all(item.already_satisfied for item in run.result.models if item.step is LocalReaderSetupStep.PULL)


@pytest.mark.timeout(180)
def test_setup_stops_at_the_failing_step_and_names_why(tmp_path: Path) -> None:
    ports = _Ports()
    with _runtime(installed=set(), residents=set(), pull_fails=True):
        run = _run(tmp_path, ports, build_local_reader_setup_request(consent=False))
        loads = [path for path, body in _Runtime.requests if path == "/api/generate"]

    assert run.result.succeeded is False
    assert run.result.stopped_step is LocalReaderSetupStep.PULL
    states = _states(run.result)
    assert states[LocalReaderSetupStep.PULL] is LocalReaderSetupStepState.FAILED
    assert states[LocalReaderSetupStep.LOAD] is LocalReaderSetupStepState.NOT_REACHED
    assert states[LocalReaderSetupStep.VERIFY] is LocalReaderSetupStepState.NOT_REACHED
    failed = next(step for step in run.result.steps if step.step is LocalReaderSetupStep.PULL)
    assert failed.failed_condition_id == ProvisioningPreconditionCondition.MODEL_PULL_SUCCEEDED
    assert run.result.failed_condition_id == ProvisioningPreconditionCondition.MODEL_PULL_SUCCEEDED
    assert loads == [], "no step after the failure may run"
    assert local_reader_setup_phase(LocalReaderSetupStep.LOAD) not in run.phases


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"action": LocalReaderProvisionAction.PULL, "consent": True}, "consent"),
        ({"action": LocalReaderProvisionAction.VERIFY, "model": "qwen3:1.7b"}, "explicit model"),
        ({"action": LocalReaderProvisionAction.REMOVE}, "role or a model"),
        ({"action": LocalReaderProvisionAction.START, "role": ModelRole.TEXT_EXTRACTION}, "not on a role"),
    ],
)
def test_incoherent_requests_are_refused_at_the_boundary(values: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        LocalReaderProvisionRequest.model_validate(values)


def test_the_published_result_schema_is_immutable_and_registers() -> None:
    ports = _Ports()
    definition = build_local_reader_operation_definition(
        spawn=ports.spawn, run_installer=ports.install, text_probe=ports.probe
    )
    registration = build_local_reader_operation_registration(definition)
    OperationRegistry(definitions=(definition,), public_registrations=(registration,))

    assert registration.contract.definition_id == LOCAL_READER_OPERATION_DEFINITION_ID
    assert registration.contract.result_schema is not None
    schema = json.dumps(LocalReaderProvisionPublicResultV1.model_json_schema(mode="validation"))
    assert '"additionalProperties": {' not in schema, "a published mapping would be mutable"


def _essence(result: LocalReaderProvisionPublicResultV1 | LocalReaderProvisionOutcome) -> tuple[object, ...]:
    return (
        result.action,
        result.succeeded,
        result.stopped_step,
        result.failed_condition_id,
        tuple((step.step, step.state, step.failed_condition_id) for step in result.steps),
        tuple(
            (item.step, item.model, item.roles, item.succeeded, item.already_satisfied, item.failed_condition_id)
            for item in result.models
        ),
    )


@pytest.mark.timeout(180)
@pytest.mark.parametrize("pull_fails", [False, True])
def test_the_direct_call_and_the_supervised_operation_settle_identically(tmp_path: Path, pull_fails: bool) -> None:
    request = build_local_reader_setup_request(consent=False)
    with _runtime(installed=set(), residents=set(), pull_fails=pull_fails):
        supervised = _run(tmp_path, _Ports(), request)
    ports = _Ports()
    with _runtime(installed=set(), residents=set(), pull_fails=pull_fails):
        direct = asyncio.run(
            provision_local_reader(
                request.payload, spawn=ports.spawn, run_installer=ports.install, text_probe=ports.probe
            )
        )

    assert _essence(direct) == _essence(supervised.result)
    assert direct.succeeded is not pull_fails
