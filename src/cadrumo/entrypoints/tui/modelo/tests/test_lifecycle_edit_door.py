"""The lifecycle door admits edits lazily, surfaces refusals, and renews before it submits.

The door's admission, renewal and preflight are the real application
services over real encrypted storage, bound exactly as the launcher binds
them; only the operation submission seam is captured, because what the
operation then does is proven by the executor's own suites.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel

from .....application.modelo.action_errors import ModeloEditBaselineStaleError
from .....application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from .....application.modelo.edit_admission import admit_modelo_edit_baseline
from .....application.modelo.edit_models import (
    ModeloEditAdmittedV1,
    ModeloEditPreflightEvaluatedV1,
    ModeloEditRefusedV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloScalarEditIntentV1,
)
from .....application.modelo.edit_preflight import OVERRIDES_SOURCE_VALUE, preflight_modelo_edit
from .....application.modelo.operation_definitions import ModeloEditApplyOperationRequestV1
from .....application.operations.models import OperationRequest
from .....core.casilla_id import validated_casilla_id
from .....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ....operation_composition import build_production_operation_registry
from ....tests.modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work
from ..lifecycle import ModeloLifecycleActionUnavailableError, ModeloWorkspaceLifecycleDoor

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SET_06 = ModeloScalarEditIntentV1(
    address=ModeloEditScalarAddressV1(casilla_id=validated_casilla_id("06")),
    kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
    value="100",
)


@pytest.fixture
def submitted(monkeypatch: pytest.MonkeyPatch) -> list[OperationRequest[BaseModel]]:
    """Capture the door's operation submission seam instead of opening an operation."""
    captured: list[OperationRequest[BaseModel]] = []

    async def capture_submit(_door: ModeloWorkspaceLifecycleDoor, request: OperationRequest[BaseModel]) -> object:
        captured.append(request)
        return request

    monkeypatch.setattr(ModeloWorkspaceLifecycleDoor, "_submit", capture_submit)
    return captured


def _door(work: SeededOperatorWork) -> ModeloWorkspaceLifecycleDoor:
    """Bind the door to the real services the launcher binds, for one seeded declaration."""
    return ModeloWorkspaceLifecycleDoor(
        services=cast(Any, object()),
        work_unit_id=work.work_unit_id,
        edit_admission=work.admit,
        edit_renewal=work.renew,
        edit_preflight=lambda submission: preflight_modelo_edit(
            submission,
            work_catalogue=work.ports.work_unit_repository.load(),
            calculation_catalogue=work.ports.calculation_repository.load(),
            tax_id_format=runtime_tax_id_format(authority=work.operation),
        ),
    )


@pytest.mark.timeout(180)
def test_admission_happens_when_asked_and_its_refusal_is_returned(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        door = _door(work)
        admitted = asyncio.run(door.admit_edit_baseline())
        refusing = ModeloWorkspaceLifecycleDoor(
            services=cast(Any, object()),
            work_unit_id="f" * 64,
            edit_admission=lambda: admit_modelo_edit_baseline(
                work_unit_id="f" * 64,
                work_catalogue=work.ports.work_unit_repository.load(),
                calculation_catalogue=work.ports.calculation_repository.load(),
                operation=work.operation,
                operation_contracts=build_production_operation_registry().public_contract_set,
            ),
        )
        refused = asyncio.run(refusing.admit_edit_baseline())

    assert isinstance(admitted, ModeloEditAdmittedV1)
    assert isinstance(refused, ModeloEditRefusedV1)


def test_a_door_without_editing_says_so() -> None:
    door = ModeloWorkspaceLifecycleDoor(services=cast(Any, object()), work_unit_id="a" * 64)

    with pytest.raises(ModeloLifecycleActionUnavailableError):
        asyncio.run(door.admit_edit_baseline())


@pytest.mark.timeout(180)
def test_an_expired_baseline_is_renewed_before_the_typed_intents_are_submitted(
    tmp_path: Path, submitted: list[OperationRequest[BaseModel]]
) -> None:
    with seeded_operator_work(tmp_path) as work:
        door = _door(work)
        admission = work.admit(issued_at=datetime.now(UTC) - timedelta(minutes=10))
        assert isinstance(admission, ModeloEditAdmittedV1)

        asyncio.run(door.apply_edits(baseline=admission.baseline, scalar_intents=(_SET_06,)))

    (request,) = submitted
    payload = request.payload
    assert isinstance(payload, ModeloEditApplyOperationRequestV1)
    submission = payload.submission.to_submission()
    assert isinstance(submission, ModeloEditSubmissionV1)
    assert submission.baseline.expires_at > datetime.now(UTC)
    assert submission.scalar_intents == (_SET_06,)


@pytest.mark.timeout(180)
def test_a_moved_declaration_is_refused_before_anything_is_submitted(
    tmp_path: Path, submitted: list[OperationRequest[BaseModel]]
) -> None:
    with seeded_operator_work(tmp_path) as work:
        door = _door(work)
        admission = asyncio.run(door.admit_edit_baseline())
        assert isinstance(admission, ModeloEditAdmittedV1)
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, record_operator_layer=True, clock=SEEDED_AT
        )

        with pytest.raises(ModeloEditBaselineStaleError):
            asyncio.run(door.apply_edits(baseline=admission.baseline, scalar_intents=(_SET_06,)))

    assert submitted == []


@pytest.mark.timeout(180)
def test_preflight_names_the_address_of_its_findings(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, record_operator_layer=True, clock=SEEDED_AT
        )
        door = _door(work)
        admission = asyncio.run(door.admit_edit_baseline())
        assert isinstance(admission, ModeloEditAdmittedV1)

        result = asyncio.run(door.preflight_edits(baseline=admission.baseline, scalar_intents=(_SET_06,)))

    assert isinstance(result, ModeloEditPreflightEvaluatedV1)
    assert [(finding.code, finding.address) for finding in result.findings] == [
        (OVERRIDES_SOURCE_VALUE, _SET_06.address)
    ]
