"""The supervised local-reader operation: load, verify and request coherence.

Every run goes through the real registry, supervisor, journal and encrypted
operand store. The model runtime is a real loopback endpoint speaking the
Ollama wire shapes; only the text fitness probe is an injected port, as
production composition injects it.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....application.local_reader import role_model_targets
from .....application.local_reader_contracts import (
    LOCAL_READER_OPERATION_DEFINITION_ID,
    LocalReaderProvisionAction,
    LocalReaderProvisionOutcome,
    LocalReaderProvisionPublicResultV3,
    LocalReaderProvisionRequest,
    build_local_reader_load_request,
    local_reader_fact_mapping,
    local_reader_public_verdict,
)
from .....application.local_reader_operation import (
    LOCAL_READER_REQUEST_SCHEMA_VERSION,
    LOCAL_READER_RESULT_SCHEMA_VERSION,
)
from .....application.local_reader_provisioning import provision_local_reader
from .....application.operations.models import OperationRequest
from .....application.provisioning_contracts import ProvisioningPreconditionCondition
from .....application.tests.local_reader_operation_requests import build_local_reader_verify_request
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.model_catalogue import ModelRole, candidates_for_role
from .....core.operations import OperationEffect
from .local_reader_operation_support import (
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

_BEYOND_ANY_HOST_BYTES = 1 << 60


def _target_models() -> set[str]:
    return {target.model for target in role_model_targets() if target.model is not None}


def _run(
    tmp_path: Path, ports: ProvisioningPorts, request: OperationRequest[LocalReaderProvisionRequest]
) -> SupervisedRun[LocalReaderProvisionPublicResultV3]:
    return run_supervised(tmp_path, ports, request, LocalReaderProvisionPublicResultV3)


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


def test_a_load_the_host_cannot_admit_sends_nothing_and_carries_its_measured_verdict(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(
        installed={TEXT_MODEL}, residents=set(), required_headroom_bytes=_BEYOND_ANY_HOST_BYTES
    ):
        run = _run(tmp_path, ports, build_local_reader_load_request(ModelRole.TEXT_EXTRACTION, TEXT_MODEL))
        loads = [body for path, body in LoopbackModelRuntime.requests if path == "/api/generate"]

    (item,) = run.result.models
    assert run.result.succeeded is False
    assert loads == [], "an inadmissible load is never sent"
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


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"action": "start"}, "action"),
        ({"action": "remove", "model": "qwen3:1.7b"}, "action"),
        ({"action": LocalReaderProvisionAction.LOAD, "consent": True}, "consent"),
        ({"action": "pull"}, "action"),
        ({"action": "install"}, "action"),
        ({"action": "setup"}, "action"),
    ],
)
def test_incoherent_requests_are_refused_at_the_boundary(values: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        LocalReaderProvisionRequest.model_validate(values)


@pytest.mark.parametrize(
    "action",
    [
        LocalReaderProvisionAction.LOAD,
        LocalReaderProvisionAction.VERIFY,
    ],
)
def test_every_model_action_accepts_a_named_model(action: LocalReaderProvisionAction) -> None:
    request = LocalReaderProvisionRequest(action=action, model="qwen3:1.7b")

    assert request.model == "qwen3:1.7b"


def test_the_published_schemas_are_immutable_versioned_and_register() -> None:
    registry = provisioning_registry(ProvisioningPorts())
    contract = registry.lookup_public_contract(LOCAL_READER_OPERATION_DEFINITION_ID)

    assert contract.request_schema.schema_version == LOCAL_READER_REQUEST_SCHEMA_VERSION == 3
    assert contract.result_schema is not None
    assert contract.result_schema.schema_version == LOCAL_READER_RESULT_SCHEMA_VERSION == 3
    schema = json.dumps(LocalReaderProvisionPublicResultV3.model_json_schema(mode="validation"))
    assert '"additionalProperties": {' not in schema, "a published mapping would be mutable"


def _essence(result: LocalReaderProvisionPublicResultV3 | LocalReaderProvisionOutcome) -> tuple[object, ...]:
    return (
        result.action,
        result.succeeded,
        result.failed_condition_id,
        tuple(
            (item.model, item.roles, item.succeeded, item.already_satisfied, item.failed_condition_id)
            for item in result.models
        ),
    )


@pytest.mark.parametrize("installed", [False, True])
def test_the_direct_call_and_the_supervised_operation_settle_identically(tmp_path: Path, installed: bool) -> None:
    request = build_local_reader_load_request(ModelRole.TEXT_EXTRACTION)
    models = {TEXT_MODEL} if installed else set()
    with loopback_model_runtime(installed=models, residents=set()):
        supervised = _run(tmp_path, ProvisioningPorts(), request)
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed=models, residents=set()):
        direct = asyncio.run(provision_local_reader(request.payload, text_probe=ports.probe))

    assert _essence(direct) == _essence(supervised.result)
    assert direct.succeeded is installed


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
