"""A work lifecycle request addressed by a stored record instead of its work unit settles refused, with a door.

Verify, file and amend take as subject the stored work unit owning the record
their payload names. Submitted under that record's id instead, each once ran
under the in-process supervisor and then never projected. Each now settles
REFUSED with no effect, served words and a door that opens the declaration the
record belongs to; the same request addressed by that work unit still runs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import BaseModel

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...application.modelo.work_amend_contracts import ModeloWorkAmendRequest
from ...application.modelo.work_filing_contracts import ModeloWorkFileRequest
from ...application.modelo.work_verification_contracts import ModeloWorkVerifyRequest
from ...application.operations.error_detail import OperationErrorDetailV1, operation_error_detail_schema
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.next_step import OperationOpenWorkStepV1
from ...core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .registered_executor_case_support import (
    OperationRuntimeCloseWitness,
    conformance_operation_runtime,
    family_environment_for_operation,
    seeded_conformance_operation_submission,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _wrong_subject(payload: BaseModel, *, operation: PinnedAuthorityOperation) -> tuple[str, str]:
    """The id of the stored record the payload names, and the work unit that owns it."""
    if isinstance(payload, ModeloWorkAmendRequest):
        baseline = payload.baseline.from_filing_record_id
        record = ModeloRecordCatalogueRepository().load().get(baseline)
        assert record is not None
        return baseline, record.work_unit_id
    if isinstance(payload, ModeloWorkFileRequest):
        revision_id = payload.approval.calculation_revision_id
    else:
        assert isinstance(payload, ModeloWorkVerifyRequest)
        revision_id = payload.calculation_revision_id
    revision = CalculationRevisionCatalogueRepository().load(operation=operation).get(revision_id)
    assert revision is not None
    return revision_id, revision.work_unit_id


@pytest.mark.parametrize("definition_id", ["modelo.work.verify", "modelo.work.file", "modelo.work.amend"])
def test_a_request_addressed_by_its_record_settles_refused_with_a_door_to_its_work_unit(
    tmp_path: Path, definition_id: str, *, operation: PinnedAuthorityOperation
) -> None:
    with (
        family_environment_for_operation(definition_id),
        conformance_operation_runtime(tmp_path / "runtime", cleanup=OperationRuntimeCloseWitness()) as (
            driver,
            registry,
            profile_id,
        ),
    ):
        submission = seeded_conformance_operation_submission(
            registry.lookup(definition_id), profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )
        record_id, work_unit_id = _wrong_subject(submission.payload, operation=operation)
        assert submission.subject_ref == work_unit_id
        assert record_id != work_unit_id

        _submitted, observed = asyncio.run(
            driver.run(definition_id=definition_id, subject_ref=record_id, payload=submission.payload)
        )
        contract = registry.lookup_public_contract(definition_id)
        resolved = asyncio.run(
            driver.services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=observed.projection.operation_id,
                    terminal_revision=observed.projection.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=operation_error_detail_schema(),
                ),
                OperationErrorDetailV1,
            )
        )
        _admitted, addressed = asyncio.run(
            driver.run(definition_id=definition_id, subject_ref=work_unit_id, payload=submission.payload)
        )

    projection = observed.projection
    assert projection.lifecycle is OperationLifecycle.TERMINAL
    assert projection.terminal_condition is OperationTerminalCondition.REFUSED
    assert projection.refusal_ref == "REFUSED_MODELO_OPERATION_SUBJECT_NOT_WORK_UNIT"
    assert projection.effect is OperationEffect.NONE
    assert projection.result_ref is None

    assert isinstance(resolved, OperationResultProjectionSuccessV1), resolved
    detail = resolved.projection
    assert isinstance(detail, OperationErrorDetailV1)
    assert detail.error_code == "REFUSED_MODELO_OPERATION_SUBJECT_NOT_WORK_UNIT"
    assert detail.refusal_words is not None and detail.refusal_words.strip()
    assert isinstance(detail.next_step, OperationOpenWorkStepV1)
    assert detail.next_step.work_unit_id == work_unit_id
    assert detail.next_step.words.strip()

    assert addressed.projection.refusal_ref != "REFUSED_MODELO_OPERATION_SUBJECT_NOT_WORK_UNIT"
    assert addressed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
