"""The supervised local-reader operation: every action, the one-shot setup and request coherence.

Every run goes through the real registry, supervisor, journal and encrypted
operand store. The model runtime is a real loopback endpoint speaking the
Ollama wire shapes; only the process spawner, the installer and the text
fitness probe are injected ports, as production composition injects them.
"""

from __future__ import annotations

import asyncio
import json
import socket
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from pydantic import ValidationError

from .....application.local_reader import role_model_targets
from .....application.local_reader_contracts import (
    LOCAL_READER_OPERATION_DEFINITION_ID,
    LocalReaderProvisionAction,
    LocalReaderProvisionOutcome,
    LocalReaderProvisionPublicResultV2,
    LocalReaderProvisionRequest,
    LocalReaderSetupStep,
    LocalReaderSetupStepState,
    build_local_reader_install_request,
    build_local_reader_load_request,
    build_local_reader_pull_request,
    build_local_reader_remove_request,
    build_local_reader_setup_request,
    build_local_reader_start_request,
    build_local_reader_verify_request,
    local_reader_fact_mapping,
    local_reader_public_verdict,
    local_reader_setup_phase,
)
from .....application.local_reader_operation import (
    LOCAL_READER_REQUEST_SCHEMA_VERSION,
    LOCAL_READER_RESULT_SCHEMA_VERSION,
)
from .....application.local_reader_provisioning import provision_local_reader
from .....application.operations.models import OperationIdentity, OperationRequest
from .....application.provisioning_contracts import ProvisioningPreconditionCondition
from .....application.provisioning_runtime import forget_runtime_unreachable
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.model_catalogue import ModelRole, candidates_for_role
from .....core.operations import OperationEffect
from .local_reader_operation_support import (
    MAPPING_MODEL,
    TEXT_MODEL,
    VISION_MODEL,
    LoopbackModelRuntime,
    ProvisioningPorts,
    SupervisedRun,
    loopback_model_runtime,
    provisioning_registry,
    run_supervised,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_REMOTE_ENDPOINT = "http://model-runtime.local-reader-test.invalid:11434/api/chat"
_BEYOND_ANY_HOST_BYTES = 1 << 60


def _target_models() -> set[str]:
    return {target.model for target in role_model_targets() if target.model is not None}


def _run(
    tmp_path: Path, ports: ProvisioningPorts, request: OperationRequest[LocalReaderProvisionRequest]
) -> SupervisedRun[LocalReaderProvisionPublicResultV2]:
    return run_supervised(tmp_path, ports, request, LocalReaderProvisionPublicResultV2)


def _states(result: LocalReaderProvisionPublicResultV2) -> dict[LocalReaderSetupStep, LocalReaderSetupStepState]:
    return {step.step: step.state for step in result.steps}


def _pulls() -> list[str]:
    return [str(body["model"]) for path, body in LoopbackModelRuntime.requests if path == "/api/pull"]


def test_load_brings_a_pulled_model_into_memory_and_reports_it_resident(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed={TEXT_MODEL}, residents=set()):
        run = _run(tmp_path, ports, build_local_reader_load_request(ModelRole.TEXT_EXTRACTION))

    assert run.result.action is LocalReaderProvisionAction.LOAD
    assert run.result.succeeded is True
    (item,) = run.result.models
    assert item.model == TEXT_MODEL
    assert item.resident is True
    assert item.already_satisfied is False
    assert run.effect is OperationEffect.UPDATED
    assert TEXT_MODEL in LoopbackModelRuntime.residents
    loads = [body for path, body in LoopbackModelRuntime.requests if path == "/api/generate"]
    assert loads == [{"model": TEXT_MODEL, "keep_alive": "30m", "stream": False}], "a load must not run inference"


def test_loading_a_resident_model_sends_nothing(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed={TEXT_MODEL}, residents={TEXT_MODEL}):
        run = _run(tmp_path, ports, build_local_reader_load_request(ModelRole.TEXT_EXTRACTION))

    (item,) = run.result.models
    assert item.succeeded is True
    assert item.already_satisfied is True
    assert run.effect is OperationEffect.NONE
    assert LoopbackModelRuntime.requests == []


def test_load_refuses_a_model_that_was_never_pulled_instead_of_fetching_it(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed=set(), residents=set()):
        run = _run(tmp_path, ports, build_local_reader_load_request(ModelRole.TEXT_EXTRACTION))

    (item,) = run.result.models
    assert run.result.succeeded is False
    assert item.failed_condition_id == ProvisioningPreconditionCondition.MODEL_INSTALLED
    verdict = local_reader_public_verdict(item.verdict_condition_id, item.verdict_facts)
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.MODEL_INSTALLED
    assert local_reader_fact_mapping(item.facts) == {"model": TEXT_MODEL, "model_installed": False}
    assert LoopbackModelRuntime.requests == [], "nothing may be pulled or loaded for an absent model"
    assert run.effect is OperationEffect.NONE


def test_pull_fetches_every_roles_model_once_by_default(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed=set(), residents=set()):
        models = _target_models()
        run = _run(tmp_path, ports, build_local_reader_pull_request())
        pulls = _pulls()

    assert run.result.action is LocalReaderProvisionAction.PULL
    assert run.result.succeeded is True
    assert sorted(pulls) == sorted(models), "each distinct model is fetched exactly once"
    assert {role for item in run.result.models for role in item.roles} == set(ModelRole)
    assert all(item.contention is None and item.bytes_fetched == 512 for item in run.result.models), (
        "the runtime's last progress report is the fetched figure"
    )
    assert run.effect is OperationEffect.UPDATED


def test_pull_of_a_named_model_fetches_that_model_for_the_named_role(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed=set(), residents=set()):
        run = _run(tmp_path, ports, build_local_reader_pull_request(ModelRole.TEXT_EXTRACTION, VISION_MODEL))
        pulls = _pulls()

    (item,) = run.result.models
    assert item.model == VISION_MODEL
    assert item.roles == (ModelRole.TEXT_EXTRACTION,)
    assert item.succeeded is True
    assert pulls == [VISION_MODEL]


def test_a_pull_the_host_cannot_admit_is_refused_before_any_bytes_move_with_its_measured_verdict(
    tmp_path: Path,
) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed=set(), residents=set(), required_headroom_bytes=_BEYOND_ANY_HOST_BYTES):
        # Naming the model is what reaches admission: a role resolved by
        # selection is already refused there for the same headroom.
        run = _run(tmp_path, ports, build_local_reader_pull_request(ModelRole.TEXT_EXTRACTION, TEXT_MODEL))
        pulls = _pulls()

    (item,) = run.result.models
    assert run.result.succeeded is False
    assert pulls == [], "an inadmissible load is never fetched"
    contention = item.contention
    assert contention is not None
    assert contention.model == TEXT_MODEL
    assert contention.admitted is False
    assert contention.required_bytes >= _BEYOND_ANY_HOST_BYTES
    assert contention.verdict_condition_id == item.verdict_condition_id == item.failed_condition_id
    verdict = local_reader_public_verdict(contention.verdict_condition_id, contention.verdict_facts)
    assert verdict is not None and verdict.failed_condition_id == contention.verdict_condition_id
    assert local_reader_fact_mapping(item.facts)["contention_condition"] == contention.verdict_condition_id
    assert run.effect is OperationEffect.NONE


def test_verify_of_a_named_model_checks_that_model_and_probes_the_text_role(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed={VISION_MODEL}, residents={VISION_MODEL}):
        run = _run(tmp_path, ports, build_local_reader_verify_request(ModelRole.TEXT_EXTRACTION, VISION_MODEL))
        generated = [body for path, body in LoopbackModelRuntime.requests if path == "/api/generate"]

    assert run.result.action is LocalReaderProvisionAction.VERIFY
    (item,) = run.result.models
    assert item.model == VISION_MODEL
    assert item.roles == (ModelRole.TEXT_EXTRACTION,)
    assert item.succeeded is True and item.resident is True and item.answered is True
    assert [body["model"] for body in generated] == [VISION_MODEL]
    assert ports.probed == [VISION_MODEL], "the text role's fitness is part of its readiness"
    assert run.effect is OperationEffect.NONE


def test_verify_of_an_absent_model_names_the_missing_pull_and_loads_nothing(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed=set(), residents=set()):
        run = _run(tmp_path, ports, build_local_reader_verify_request(ModelRole.TEXT_EXTRACTION))

    (item,) = run.result.models
    assert run.result.succeeded is False
    assert item.failed_condition_id == ProvisioningPreconditionCondition.MODEL_INSTALLED
    assert LoopbackModelRuntime.requests == []
    assert ports.probed == []


def test_start_of_an_answering_runtime_spawns_nothing(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed=set(), residents=set()):
        run = _run(tmp_path, ports, build_local_reader_start_request())

    assert run.result.action is LocalReaderProvisionAction.START
    assert run.result.succeeded is True
    assert run.result.already_running is True
    assert run.result.runtime_started is False
    assert run.result.started_pid is None
    assert ports.spawned == []
    assert run.effect is OperationEffect.NONE


def test_start_refuses_an_endpoint_on_another_machine_instead_of_spawning_a_server_here(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with override_settings(cadrumo_llm_ollama_chat_url=_REMOTE_ENDPOINT):
        run = _run(tmp_path, ports, build_local_reader_start_request())

    assert run.result.succeeded is False
    assert run.result.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_ENDPOINT_LOCAL
    assert local_reader_fact_mapping(run.result.facts) == {"runtime_url": _REMOTE_ENDPOINT, "endpoint_local": False}
    verdict = local_reader_public_verdict(run.result.verdict_condition_id, run.result.verdict_facts)
    assert verdict is not None
    assert ports.spawned == []
    assert run.effect is OperationEffect.NONE


def _installed_runtime_and_idle_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    """Make this host look like one with the runtime installed and not running; return its idle port."""
    programs = tmp_path / "programs"
    programs.mkdir()
    executable = programs / ("ollama.cmd" if sys.platform == "win32" else "ollama")
    executable.write_text("", encoding="ascii")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(programs))
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        return int(reserved.getsockname()[1])


def test_start_asks_the_owning_process_and_reports_the_server_it_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = _installed_runtime_and_idle_endpoint(tmp_path, monkeypatch)
    asked: list[OperationIdentity] = []
    servers: list[ThreadingHTTPServer] = []

    async def owner_start(identity: OperationIdentity) -> int | None:
        asked.append(identity)
        server = ThreadingHTTPServer(("127.0.0.1", port), LoopbackModelRuntime)
        servers.append(server)
        Thread(target=server.serve_forever, daemon=True).start()
        return 4242

    ports = ProvisioningPorts(owner_start=owner_start)
    try:
        with override_settings(cadrumo_llm_ollama_chat_url=f"http://127.0.0.1:{port}/api/chat"):
            forget_runtime_unreachable()
            run = _run(tmp_path / "profile", ports, build_local_reader_start_request())
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()

    assert run.result.succeeded is True
    assert run.result.runtime_started is True and run.result.already_running is False
    assert run.result.started_pid == 4242
    assert [(identity.definition_id, identity.subject_ref) for identity in asked] == [
        (LOCAL_READER_OPERATION_DEFINITION_ID, "local-reader:runtime")
    ]
    assert ports.spawned == [], "a process bound to its owner never starts the server itself"
    assert run.effect is OperationEffect.UPDATED


def test_start_is_refused_when_the_owning_process_started_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = _installed_runtime_and_idle_endpoint(tmp_path, monkeypatch)

    async def owner_start(identity: OperationIdentity) -> int | None:
        del identity
        return None

    ports = ProvisioningPorts(owner_start=owner_start)
    with override_settings(cadrumo_llm_ollama_chat_url=f"http://127.0.0.1:{port}/api/chat"):
        forget_runtime_unreachable()
        run = _run(tmp_path / "profile", ports, build_local_reader_start_request())

    assert run.result.succeeded is False
    assert run.result.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_START_SUCCEEDED
    facts = local_reader_fact_mapping(run.result.facts)
    assert facts["spawned"] is False and facts["start_error_type"] == "OSError"
    assert ports.spawned == []
    assert run.effect is OperationEffect.NONE


def test_install_without_consent_never_runs_the_installer(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed=set(), residents=set()):
        run = _run(tmp_path, ports, build_local_reader_install_request(consent=False))

    install = run.result.install
    assert install is not None
    assert install.consented is False
    assert install.installer_exit_code is None
    assert ports.installers == []
    assert run.effect is OperationEffect.NONE
    if install.installed:
        # This host already has the runtime; the action reports it and runs nothing.
        assert install.already_installed is True and run.result.succeeded is True
    else:
        assert run.result.failed_condition_id in {
            ProvisioningPreconditionCondition.RUNTIME_INSTALL_CONSENTED,
            ProvisioningPreconditionCondition.RUNTIME_INSTALLER_AVAILABLE,
        }


def test_remove_deletes_the_roles_model_and_reports_the_bytes_freed(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed={TEXT_MODEL, VISION_MODEL}, residents=set()):
        run = _run(tmp_path, ports, build_local_reader_remove_request(ModelRole.TEXT_EXTRACTION))
        installed_after = set(LoopbackModelRuntime.installed)

    assert run.result.action is LocalReaderProvisionAction.REMOVE
    (item,) = run.result.models
    assert item.model == TEXT_MODEL
    assert item.succeeded is True and item.was_installed is True
    assert item.freed_bytes == 1024
    assert installed_after == {VISION_MODEL}
    assert run.effect is OperationEffect.UPDATED


def test_remove_never_deletes_a_model_cadrumo_did_not_select(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed={TEXT_MODEL, "someone-elses:7b"}, residents=set()):
        run = _run(tmp_path, ports, build_local_reader_remove_request(model="someone-elses:7b"))
        installed_after = set(LoopbackModelRuntime.installed)

    (item,) = run.result.models
    assert item.succeeded is False
    assert item.failed_condition_id == ProvisioningPreconditionCondition.MODEL_SELECTED_BY_CADRUMO
    assert item.freed_bytes is None
    assert installed_after == {TEXT_MODEL, "someone-elses:7b"}
    assert run.effect is OperationEffect.NONE


def test_a_licence_advisory_is_written_in_the_language_the_request_names(tmp_path: Path) -> None:
    restricted = next(
        row for row in candidates_for_role(ModelRole.VISION_TRANSCRIPTION) if not row.licence.commercial_use_permitted
    )
    advisories: dict[OutputLanguage, tuple[str, ...]] = {}
    for language in (OutputLanguage.EN, OutputLanguage.HU):
        with loopback_model_runtime(installed=set(), residents=set()), override_settings(cadrumo_output_language="es"):
            run = _run(
                tmp_path / language.value,
                ProvisioningPorts(),
                build_local_reader_verify_request(
                    ModelRole.VISION_TRANSCRIPTION, restricted.runtime_id, output_language=language
                ),
            )
        (item,) = run.result.models
        advisories[language] = item.licence_advisories

    for rendered in advisories.values():
        (message,) = rendered
        assert restricted.runtime_id in message and restricted.licence.name in message
    assert advisories[OutputLanguage.EN] != advisories[OutputLanguage.HU]


def test_setup_pulls_loads_and_verifies_every_role_in_order(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed=set(), residents=set()):
        models = _target_models()
        run = _run(tmp_path, ports, build_local_reader_setup_request(consent=False))
        installed_after = set(LoopbackModelRuntime.installed)
        residents_after = set(LoopbackModelRuntime.residents)

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
    assert TEXT_MODEL in ports.probed


def test_setup_over_a_ready_reader_redoes_nothing(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with override_settings(
        cadrumo_llm_ollama_vision_model=VISION_MODEL,
        cadrumo_llm_ollama_text_model=TEXT_MODEL,
        cadrumo_llm_ollama_mapping_model=MAPPING_MODEL,
    ):
        models = _target_models()
    with loopback_model_runtime(installed=models, residents=models):
        run = _run(tmp_path, ports, build_local_reader_setup_request(consent=False))
        pulls = _pulls()
        loads = [
            body for path, body in LoopbackModelRuntime.requests if path == "/api/generate" and "prompt" not in body
        ]

    assert run.result.succeeded is True
    assert set(_states(run.result).values()) == {LocalReaderSetupStepState.UNCHANGED}
    assert pulls == []
    assert loads == []
    assert run.effect is OperationEffect.NONE
    assert all(item.already_satisfied for item in run.result.models if item.step is LocalReaderSetupStep.PULL)


def test_setup_stops_at_the_failing_step_and_names_why(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed=set(), residents=set(), pull_fails=True):
        run = _run(tmp_path, ports, build_local_reader_setup_request(consent=False))
        loads = [path for path, body in LoopbackModelRuntime.requests if path == "/api/generate"]

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
        ({"action": LocalReaderProvisionAction.START, "model": "qwen3:1.7b"}, "explicit model"),
        ({"action": LocalReaderProvisionAction.SETUP, "model": "qwen3:1.7b"}, "explicit model"),
        ({"action": LocalReaderProvisionAction.REMOVE}, "role or a model"),
        ({"action": LocalReaderProvisionAction.START, "role": ModelRole.TEXT_EXTRACTION}, "not on a role"),
    ],
)
def test_incoherent_requests_are_refused_at_the_boundary(values: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        LocalReaderProvisionRequest.model_validate(values)


@pytest.mark.parametrize(
    "action",
    [
        LocalReaderProvisionAction.PULL,
        LocalReaderProvisionAction.LOAD,
        LocalReaderProvisionAction.VERIFY,
        LocalReaderProvisionAction.REMOVE,
    ],
)
def test_every_model_action_accepts_a_named_model(action: LocalReaderProvisionAction) -> None:
    request = LocalReaderProvisionRequest(action=action, model="qwen3:1.7b")

    assert request.model == "qwen3:1.7b"


def test_the_published_schemas_are_immutable_versioned_and_register() -> None:
    registry = provisioning_registry(ProvisioningPorts())
    contract = registry.lookup_public_contract(LOCAL_READER_OPERATION_DEFINITION_ID)

    assert contract.request_schema.schema_version == LOCAL_READER_REQUEST_SCHEMA_VERSION == 2
    assert contract.result_schema is not None
    assert contract.result_schema.schema_version == LOCAL_READER_RESULT_SCHEMA_VERSION == 2
    schema = json.dumps(LocalReaderProvisionPublicResultV2.model_json_schema(mode="validation"))
    assert '"additionalProperties": {' not in schema, "a published mapping would be mutable"


def _essence(result: LocalReaderProvisionPublicResultV2 | LocalReaderProvisionOutcome) -> tuple[object, ...]:
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


@pytest.mark.parametrize("pull_fails", [False, True])
def test_the_direct_call_and_the_supervised_operation_settle_identically(tmp_path: Path, pull_fails: bool) -> None:
    request = build_local_reader_setup_request(consent=False)
    with loopback_model_runtime(installed=set(), residents=set(), pull_fails=pull_fails):
        supervised = _run(tmp_path, ProvisioningPorts(), request)
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed=set(), residents=set(), pull_fails=pull_fails):
        direct = asyncio.run(
            provision_local_reader(
                request.payload, spawn=ports.spawn, run_installer=ports.install, text_probe=ports.probe
            )
        )

    assert _essence(direct) == _essence(supervised.result)
    assert direct.succeeded is not pull_fails


def test_a_resident_model_of_another_size_does_not_count_as_loaded(tmp_path: Path) -> None:
    family_sibling = TEXT_MODEL.split(":", 1)[0] + ":8b"
    assert family_sibling != TEXT_MODEL
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed={TEXT_MODEL, family_sibling}, residents={family_sibling}):
        run = _run(tmp_path, ports, build_local_reader_load_request(ModelRole.TEXT_EXTRACTION))
        residents = set(LoopbackModelRuntime.residents)

    (item,) = run.result.models
    assert item.succeeded is True
    assert item.already_satisfied is False, "a different tag is a different model"
    assert residents == {TEXT_MODEL, family_sibling}


def test_load_refuses_when_only_another_size_is_pulled(tmp_path: Path) -> None:
    family_sibling = TEXT_MODEL.split(":", 1)[0] + ":8b"
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed={family_sibling}, residents=set()):
        run = _run(tmp_path, ports, build_local_reader_load_request(ModelRole.TEXT_EXTRACTION))
        loads = [body for path, body in LoopbackModelRuntime.requests if path == "/api/generate"]

    (item,) = run.result.models
    assert item.succeeded is False
    assert item.failed_condition_id == ProvisioningPreconditionCondition.MODEL_INSTALLED
    assert loads == []


def test_an_untagged_model_name_means_latest(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed={"qwen3:latest"}, residents={"qwen3:latest"}):
        run = _run(tmp_path, ports, build_local_reader_load_request(ModelRole.TEXT_EXTRACTION, "qwen3"))

    (item,) = run.result.models
    assert item.succeeded is True
    assert item.already_satisfied is True
    assert LoopbackModelRuntime.requests == []
