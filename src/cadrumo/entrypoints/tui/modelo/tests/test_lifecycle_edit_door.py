"""The workbench read admits edits, surfaces refusals, and the door renews before it submits.

Admission, renewal and preflight are the real application reads the profile
worker's registered operations run, over real encrypted storage; only the
operation submission is recorded, because what the operation then does is
proven by the executor's own suites.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from .....application.modelo.action_errors import ModeloEditBaselineStaleError
from .....application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from .....application.modelo.edit_models import (
    ModeloEditAdmittedV1,
    ModeloEditPreflightEvaluatedV1,
    ModeloEditRefusedV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloScalarEditIntentV1,
)
from .....application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from .....application.modelo.edit_preflight import OVERRIDES_SOURCE_VALUE
from .....application.modelo.work_lifecycle import discard_work_unit
from .....application.modelo.workbench_read import read_modelo_workbench_form
from .....core.casilla_id import validated_casilla_id
from .....core.external_constants import OutputLanguage
from ....adapter_composition import build_work_lifecycle_ports
from ....operation_composition import build_production_operation_registry
from ....tests.modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work
from ...tests.modelo_workbench_session import RecordedSubmissions, application_lifecycle_door, workbench_read_ports
from ..lifecycle import ModeloLifecycleActionUnavailableError, ModeloWorkspaceLifecycleDoor

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SET_06 = ModeloScalarEditIntentV1(
    address=ModeloEditScalarAddressV1(casilla_id=validated_casilla_id("06")),
    kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
    value="100",
)


def _door(work: SeededOperatorWork, submissions: RecordedSubmissions) -> ModeloWorkspaceLifecycleDoor:
    """Bind the door to the real reads the worker runs, for one seeded declaration."""
    return application_lifecycle_door(
        work_unit_id=work.work_unit_id,
        bucket_id=work.work_unit.bucket_id,
        ports=workbench_read_ports(work.work_unit.bucket_id, work.operation),
        operation=work.operation,
        contracts=build_production_operation_registry().public_contract_set,
        submissions=submissions,
        read=None,
    )


@pytest.mark.timeout(180)
def test_the_form_read_admits_an_edit_and_carries_a_refusal_as_the_typed_refusal(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        ports = workbench_read_ports(work.work_unit.bucket_id, work.operation)
        contracts = build_production_operation_registry().public_contract_set
        read = read_modelo_workbench_form(
            work.work_unit_id,
            bucket_id=work.work_unit.bucket_id,
            ports=ports,
            operation=work.operation,
            operation_contracts=contracts,
            language=OutputLanguage.EN,
        )
        discard_work_unit(
            work.work_unit_id,
            actor="test",
            ports=build_work_lifecycle_ports(bucket_id=work.work_unit.bucket_id),
            clock=SEEDED_AT,
        )
        refused = read_modelo_workbench_form(
            work.work_unit_id,
            bucket_id=work.work_unit.bucket_id,
            ports=ports,
            operation=work.operation,
            operation_contracts=contracts,
            language=OutputLanguage.EN,
        )

    assert isinstance(read.admission, ModeloEditAdmittedV1)
    assert read.load.form.work_unit_id == work.work_unit_id
    assert isinstance(refused.admission, ModeloEditRefusedV1)


@pytest.mark.timeout(180)
def test_an_expired_baseline_is_renewed_before_the_typed_intents_are_submitted(tmp_path: Path) -> None:
    submissions = RecordedSubmissions()
    with seeded_operator_work(tmp_path) as work:
        door = _door(work, submissions)
        admission = work.admit(issued_at=datetime.now(UTC) - timedelta(minutes=10))
        assert isinstance(admission, ModeloEditAdmittedV1)

        _controller, renewed = asyncio.run(door.apply_edits(baseline=admission.baseline, scalar_intents=(_SET_06,)))

    request = submissions.pop()
    payload = request.payload
    assert isinstance(payload, ModeloEditOperatorInputV2)
    submission = payload.submission.to_submission()
    assert isinstance(submission, ModeloEditSubmissionV1)
    assert submission.baseline.expires_at > datetime.now(UTC)
    assert submission.baseline == renewed
    assert submission.scalar_intents == (_SET_06,)


@pytest.mark.timeout(180)
def test_a_moved_declaration_is_refused_before_anything_is_submitted(tmp_path: Path) -> None:
    submissions = RecordedSubmissions()
    with seeded_operator_work(tmp_path) as work:
        door = _door(work, submissions)
        admission = work.admit()
        assert isinstance(admission, ModeloEditAdmittedV1)
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, record_operator_layer=True, clock=SEEDED_AT
        )

        with pytest.raises(ModeloEditBaselineStaleError):
            asyncio.run(door.apply_edits(baseline=admission.baseline, scalar_intents=(_SET_06,)))

    assert submissions.submitted == []


@pytest.mark.timeout(180)
def test_preflight_names_the_address_of_its_findings(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, record_operator_layer=True, clock=SEEDED_AT
        )
        door = _door(work, RecordedSubmissions())
        admission = work.admit()
        assert isinstance(admission, ModeloEditAdmittedV1)

        result = asyncio.run(door.preflight_edits(baseline=admission.baseline, scalar_intents=(_SET_06,)))
        without_editing = ModeloWorkspaceLifecycleDoor(
            work_unit_id=work.work_unit_id, submit_operation=RecordedSubmissions().submit
        )
        with pytest.raises(ModeloLifecycleActionUnavailableError):
            asyncio.run(without_editing.preflight_edits(baseline=admission.baseline, scalar_intents=(_SET_06,)))
        with pytest.raises(ModeloLifecycleActionUnavailableError):
            asyncio.run(without_editing.apply_edits(baseline=admission.baseline, scalar_intents=(_SET_06,)))

    assert isinstance(result, ModeloEditPreflightEvaluatedV1)
    assert [(finding.code, finding.address) for finding in result.findings] == [
        (OVERRIDES_SOURCE_VALUE, _SET_06.address)
    ]
