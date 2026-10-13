"""The supervised reads of the local reader: its status, a fitness probe and the machine report.

Every run goes through the real registry, supervisor, journal and encrypted
operand store against a real loopback runtime. Each public result is compared
with what the application reads directly under the same settings, so the
operation is shown to publish the measurement and nothing else.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....application.local_reader import RoleFitnessState, read_local_reader_status
from .....application.local_reader_contracts import (
    LOCAL_READER_OPERATION_SUBJECT,
    local_reader_fact_mapping,
    local_reader_public_verdict,
)
from .....application.local_reader_report import (
    LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
    LocalReaderReportPublicResultV1,
    read_local_reader_report,
)
from .....application.local_reader_status_operation import (
    LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,
    LocalReaderStatusPublicResultV1,
)
from .....application.provisioning_contracts import ProvisioningPreconditionCondition
from .....application.provisioning_runtime import forget_runtime_unreachable
from .....application.tests.local_reader_operation_requests import (
    build_local_reader_report_request,
    build_local_reader_status_request,
)
from .....core.config import override_settings
from .....core.model_catalogue import ModelRole
from .....core.operations import OperationEffect
from .local_reader_operation_support import (
    TEXT_MODEL,
    VISION_MODEL,
    LoopbackModelRuntime,
    ProvisioningPorts,
    loopback_model_runtime,
    provisioning_registry,
    run_supervised,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_CLOSED_LOCAL_ENDPOINT = "http://127.0.0.1:1/api/chat"


def test_status_publishes_the_host_every_role_and_the_recorded_fitness_without_probing(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed={TEXT_MODEL}, residents={TEXT_MODEL}) as chat_url:
        run = run_supervised(
            tmp_path, ports, build_local_reader_status_request(probe=False), LocalReaderStatusPublicResultV1
        )
        direct = read_local_reader_status()
        requests = list(LoopbackModelRuntime.requests)

    status = run.result
    assert status.host.reachable is True
    assert status.host.version == "0.9.0"
    assert status.host.endpoint_url == chat_url
    assert status.host.endpoint_local is True
    assert status.host.verdict_condition_id is None and status.host.verdict_facts == ()
    assert local_reader_fact_mapping(status.host.facts) == dict(direct.host.facts)
    assert [row.role for row in status.roles] == list(ModelRole)
    rows = {row.role: row for row in status.roles}
    text = rows[ModelRole.TEXT_EXTRACTION]
    assert text.model == TEXT_MODEL
    assert text.installed is True and text.resident is True
    assert text.fitness is RoleFitnessState.NOT_VERIFIED, "no verdict is recorded, which is not unfitness"
    assert text.fit_for_role is None and text.ready is False
    assert text.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_VERIFIED
    vision = rows[ModelRole.VISION_TRANSCRIPTION]
    assert vision.model == VISION_MODEL
    assert vision.installed is False and vision.ready is False
    assert vision.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED
    assert status.extraction_ready is False
    assert status.document_readiness is direct.document_readiness
    assert status.text_layer_model_fill_available is False
    assert [(row.role, row.model, row.installed, row.resident, row.fitness, row.ready) for row in status.roles] == [
        (row.role, row.model, row.installed, row.resident, row.fitness, row.ready) for row in direct.roles
    ]
    assert ports.probed == [], "a status read never spends a model load"
    assert requests == [], "a status read changes nothing at the runtime"
    assert run.effect is OperationEffect.NONE
    assert run.phases == (LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,)


def test_a_probing_status_checks_the_text_models_fitness_now(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed={TEXT_MODEL, VISION_MODEL}, residents=set()):
        run = run_supervised(
            tmp_path, ports, build_local_reader_status_request(probe=True), LocalReaderStatusPublicResultV1
        )

    rows = {row.role: row for row in run.result.roles}
    text = rows[ModelRole.TEXT_EXTRACTION]
    assert ports.probed == [TEXT_MODEL]
    assert text.fitness is RoleFitnessState.FIT
    assert text.fit_for_role is True and text.ready is True
    assert text.failed_condition_id is None
    assert run.result.extraction_ready is True
    assert run.result.text_layer_model_fill_available is True
    assert run.effect is OperationEffect.NONE


def test_status_reports_an_unreachable_runtime_as_a_state_with_its_refusal(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_LOCAL_ENDPOINT):
        forget_runtime_unreachable()
        run = run_supervised(
            tmp_path, ports, build_local_reader_status_request(probe=True), LocalReaderStatusPublicResultV1
        )

    host = run.result.host
    assert host.reachable is False and host.version is None
    assert host.endpoint_local is True
    # Which refusal applies depends on whether this host has the runtime installed.
    assert host.verdict_condition_id in {
        ProvisioningPreconditionCondition.RUNTIME_INSTALLED,
        ProvisioningPreconditionCondition.RUNTIME_REACHABLE,
    }
    verdict = local_reader_public_verdict(host.verdict_condition_id, host.verdict_facts)
    assert verdict is not None
    assert local_reader_fact_mapping(host.verdict_facts) == local_reader_fact_mapping(host.facts)
    assert all(row.installed is None and row.resident is None and not row.ready for row in run.result.roles), (
        "an unreachable runtime has no inventory, which is not the same as nothing installed"
    )
    assert run.result.extraction_ready is False
    assert ports.probed == [], "there is no model to probe behind an unreachable runtime"


def test_the_report_publishes_the_measured_machine_and_each_roles_selection(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with loopback_model_runtime(installed={TEXT_MODEL}, residents={TEXT_MODEL}):
        run = run_supervised(tmp_path, ports, build_local_reader_report_request(), LocalReaderReportPublicResultV1)
        direct = read_local_reader_report()
        requests = list(LoopbackModelRuntime.requests)

    report = run.result
    assert report.runtime_reachable is True
    assert report.residents == (TEXT_MODEL,)
    assert report.accelerator is direct.accelerator
    assert report.total_vram_bytes == direct.total_vram_bytes
    assert report.total_system_memory_bytes == direct.total_system_memory_bytes
    assert [row.role for row in report.models] == list(ModelRole)
    assert [(row.role, row.model, row.selected, row.resident) for row in report.models] == [
        (row.role, row.model, row.selected, row.resident) for row in direct.models
    ]
    for published, measured in zip(report.models, direct.models, strict=True):
        verdict = local_reader_public_verdict(published.verdict_condition_id, published.verdict_facts)
        assert verdict == measured.precondition_verdict
    assert (report.contention is None) is (direct.contention is None)
    if report.contention is not None and direct.contention is not None:
        assert report.contention.model == direct.contention.model
        assert report.contention.required_bytes == direct.contention.required_bytes
    assert requests == [], "the report pulls nothing and loads nothing"
    assert run.effect is OperationEffect.NONE
    assert run.phases == (LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,)


def test_the_report_tells_an_unreachable_runtime_from_one_with_nothing_resident(tmp_path: Path) -> None:
    ports = ProvisioningPorts()
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_LOCAL_ENDPOINT):
        forget_runtime_unreachable()
        unreachable = run_supervised(
            tmp_path / "unreachable", ports, build_local_reader_report_request(), LocalReaderReportPublicResultV1
        )
    with loopback_model_runtime(installed=set(), residents=set()):
        idle = run_supervised(
            tmp_path / "idle", ports, build_local_reader_report_request(), LocalReaderReportPublicResultV1
        )

    assert unreachable.result.runtime_reachable is False
    assert idle.result.runtime_reachable is True
    assert unreachable.result.residents == idle.result.residents == ()


def test_both_reads_register_with_the_machines_fixed_subject() -> None:
    registry = provisioning_registry(ProvisioningPorts())

    for definition_id in (LOCAL_READER_STATUS_OPERATION_DEFINITION_ID, LOCAL_READER_REPORT_OPERATION_DEFINITION_ID):
        definition = registry.lookup(definition_id)
        assert definition.subject_reference.literal == LOCAL_READER_OPERATION_SUBJECT
        assert definition.capabilities.permitted_effects == {OperationEffect.NONE, OperationEffect.UNKNOWN}
        contract = registry.lookup_public_contract(definition_id)
        assert contract.request_schema.schema_version == 1
        assert contract.result_schema is not None and contract.result_schema.schema_version == 1
