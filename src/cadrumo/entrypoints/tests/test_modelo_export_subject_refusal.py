"""An export addressed by its calculation revision rather than its work unit settles refused, with a door.

The export contract's subject is the stored work unit that owns the revision
the payload names. A submission whose subject is the revision id itself was
once run to success and then never projected, so the filer saw nothing. Under
the production supervisor it now settles REFUSED with no effect, served words
and a door that opens the declaration the revision belongs to; the same export
addressed by that work unit still runs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...application.modelo.work_export_contracts import ModeloExportRequest
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

_EXPORT = "modelo.export"


def test_an_export_addressed_by_its_revision_settles_refused_with_a_door_to_its_work_unit(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with (
        family_environment_for_operation(_EXPORT),
        conformance_operation_runtime(tmp_path / "runtime", cleanup=OperationRuntimeCloseWitness()) as (
            driver,
            registry,
            profile_id,
        ),
    ):
        submission = seeded_conformance_operation_submission(
            registry.lookup(_EXPORT), profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )
        assert isinstance(submission.payload, ModeloExportRequest)
        output = tmp_path / "exports" / "export.txt"
        output.parent.mkdir()
        payload = submission.payload.model_copy(update={"output_path": str(output)})
        revision = CalculationRevisionCatalogueRepository().load().get(payload.calculation_revision_id)
        assert revision is not None
        assert submission.subject_ref == revision.work_unit_id

        _submitted, observed = asyncio.run(
            driver.run(definition_id=_EXPORT, subject_ref=payload.calculation_revision_id, payload=payload)
        )
        contract = registry.lookup_public_contract(_EXPORT)
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
        refused_output_written = output.exists()

        _admitted, exported = asyncio.run(
            driver.run(definition_id=_EXPORT, subject_ref=revision.work_unit_id, payload=payload)
        )

    projection = observed.projection
    assert projection.lifecycle is OperationLifecycle.TERMINAL
    assert projection.terminal_condition is OperationTerminalCondition.REFUSED
    assert projection.refusal_ref == "REFUSED_MODELO_OPERATION_SUBJECT_NOT_WORK_UNIT"
    assert projection.effect is OperationEffect.NONE
    assert projection.result_ref is None
    assert not refused_output_written

    assert isinstance(resolved, OperationResultProjectionSuccessV1), resolved
    detail = resolved.projection
    assert isinstance(detail, OperationErrorDetailV1)
    assert detail.error_code == "REFUSED_MODELO_OPERATION_SUBJECT_NOT_WORK_UNIT"
    assert detail.refusal_words is not None and detail.refusal_words.strip()
    assert isinstance(detail.next_step, OperationOpenWorkStepV1)
    assert detail.next_step.work_unit_id == revision.work_unit_id
    assert detail.next_step.words.strip()

    assert exported.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
