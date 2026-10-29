"""The supervised reads of the local reader: its status and the machine report.

Every run goes through the real registry, supervisor, journal and encrypted
operand store, with the local AI program's row decoded from the components
role's recorded output and the person's selection answered through the
operation's model-run port. Each public result is compared with what the
application reads directly from the same inputs, so the operation is shown to
publish the judgement and nothing else. Nothing asks a local AI server.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....application.dependency_contracts import DependencyState
from .....application.local_reader import read_local_reader_status
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
from .....application.probe_outcomes import LOCAL_AI_PROVISION_ACTION_ID, ProbePreconditionCondition
from .....application.tests.local_reader_operation_requests import (
    build_local_reader_report_request,
    build_local_reader_status_request,
)
from .....core.model_roles import ModelRole
from .....core.operations import OperationEffect
from ....outbound.components.tests.recorded_rows import recorded_absent_row
from .local_reader_operation_support import (
    READER_LANES,
    SET_UP_PROGRAM,
    TEXT_MODEL,
    VISION_MODEL,
    provisioning_registry,
    run_supervised,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]


def test_status_publishes_the_program_and_every_role_without_loading_a_model(tmp_path: Path) -> None:
    run = run_supervised(tmp_path, build_local_reader_status_request(), LocalReaderStatusPublicResultV1)
    direct = read_local_reader_status(READER_LANES, SET_UP_PROGRAM)

    status = run.result
    assert status.program.state is DependencyState.READY
    assert status.program.available is True
    assert status.program.version == direct.program.version
    assert status.program.verdict_condition_id is None and status.program.verdict_facts == ()
    assert local_reader_fact_mapping(status.program.facts) == dict(direct.program.facts)
    assert [row.role for row in status.roles] == list(ModelRole)
    rows = {row.role: row for row in status.roles}
    text = rows[ModelRole.TEXT_EXTRACTION]
    assert text.model == TEXT_MODEL
    assert text.installed is True
    assert text.ready is True
    assert text.failed_condition_id is None
    vision = rows[ModelRole.VISION_TRANSCRIPTION]
    assert vision.model == VISION_MODEL
    assert vision.installed is False and vision.ready is False
    assert vision.failed_condition_id == ProbePreconditionCondition.ROLE_MODEL_INSTALLED
    assert status.extraction_ready is False
    assert status.document_readiness is direct.document_readiness
    assert status.text_layer_model_fill_available is True
    assert [(row.role, row.model, row.installed, row.ready) for row in status.roles] == [
        (row.role, row.model, row.installed, row.ready) for row in direct.roles
    ]
    assert run.effect is OperationEffect.NONE
    assert run.phases == (LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,)


def test_status_reports_an_absent_program_as_a_state_with_its_setup(tmp_path: Path) -> None:
    run = run_supervised(
        tmp_path,
        build_local_reader_status_request(),
        LocalReaderStatusPublicResultV1,
        program=recorded_absent_row("local_ai"),
    )

    program = run.result.program
    assert program.state is DependencyState.ABSENT
    assert program.available is False and program.version is None
    assert program.verdict_condition_id == ProbePreconditionCondition.RUNTIME_INSTALLED
    assert program.verdict_action_id == LOCAL_AI_PROVISION_ACTION_ID
    verdict = local_reader_public_verdict(
        program.verdict_condition_id, program.verdict_facts, program.verdict_action_id
    )
    assert verdict is not None
    assert verdict.action is not None and verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert local_reader_fact_mapping(program.verdict_facts) == local_reader_fact_mapping(program.facts)
    on_host = [row for row in run.result.roles if row.model is not None]
    assert on_host, "the selection names models that load on this computer"
    assert all(
        not row.ready and row.failed_condition_id == ProbePreconditionCondition.RUNTIME_INSTALLED
        for row in on_host
    )
    assert run.result.extraction_ready is False


def test_status_reports_a_role_that_cannot_answer_as_unknown_with_no_setup(tmp_path: Path) -> None:
    run = run_supervised(tmp_path, build_local_reader_status_request(), LocalReaderStatusPublicResultV1, program=None)

    program = run.result.program
    assert program.state is None
    assert program.available is False
    assert program.verdict_condition_id == ProbePreconditionCondition.RUNTIME_INSTALLED
    assert program.verdict_action_id is None
    assert local_reader_fact_mapping(program.facts) == {"local_ai_state": "unknown"}


def test_the_report_publishes_the_measured_machine_and_each_roles_selection(tmp_path: Path) -> None:
    run = run_supervised(tmp_path, build_local_reader_report_request(), LocalReaderReportPublicResultV1)
    direct = read_local_reader_report(READER_LANES)

    report = run.result
    assert report.accelerator is direct.accelerator
    assert report.total_vram_bytes == direct.total_vram_bytes
    assert report.total_system_memory_bytes == direct.total_system_memory_bytes
    assert [row.role for row in report.models] == list(ModelRole)
    assert [(row.role, row.model, row.selected) for row in report.models] == [
        (row.role, row.model, row.selected) for row in direct.models
    ]
    for published, measured in zip(report.models, direct.models, strict=True):
        verdict = local_reader_public_verdict(published.verdict_condition_id, published.verdict_facts)
        assert verdict == measured.precondition_verdict
    assert run.effect is OperationEffect.NONE
    assert run.phases == (LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,)


def test_both_reads_register_with_the_machines_fixed_subject() -> None:
    registry = provisioning_registry()

    for definition_id in (LOCAL_READER_STATUS_OPERATION_DEFINITION_ID, LOCAL_READER_REPORT_OPERATION_DEFINITION_ID):
        definition = registry.lookup(definition_id)
        assert definition.subject_reference.literal == LOCAL_READER_OPERATION_SUBJECT
        assert definition.capabilities.permitted_effects == {OperationEffect.NONE, OperationEffect.UNKNOWN}
        contract = registry.lookup_public_contract(definition_id)
        assert contract.request_schema.schema_version == 1
        assert contract.result_schema is not None and contract.result_schema.schema_version == 1
