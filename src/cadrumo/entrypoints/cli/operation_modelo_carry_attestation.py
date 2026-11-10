"""Exact-profile registered reads and edit of a declaration's form from the CLI.

The command line makes the statement that no earlier-ejercicio carry is pending
through the same three registered operations the window uses: the form read
that admits the edit baseline and serves the statement, the edit preflight that
checks the staged intents, and the guarded edit apply. The staged intents travel
as volatile operator input, converted by the worker and never journaled.
"""

from __future__ import annotations

from uuid import UUID

from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.transport.frontend_client import FrontendClient

from ...application.modelo.edit_apply_contracts import ModeloEditApplyPublicResultV1, ModeloEditApplySubmissionV1
from ...application.modelo.edit_models import ModeloEditSubmissionV1
from ...application.modelo.edit_operation_requests import (
    ModeloEditApplyOperationRequestV2,
    ModeloEditPreflightRequestV2,
)
from ...application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from ...application.modelo.operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID
from ...application.modelo.workbench_operations import (
    MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloEditPreflightProjectionV1,
    ModeloWorkbenchFormRequest,
)
from ...application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1
from ...core.external_constants import OutputLanguage
from ...core.operations import OperationEffect

#: An apply calculates the declaration again, which can take as long as a calculation.
_APPLY_SETTLEMENT_SECONDS = 1800.0


def _belongs_to(profile_id: UUID, work_unit_id: str, *, result_profile_id: UUID, result_work_unit_id: str) -> bool:
    return result_profile_id == profile_id and result_work_unit_id == work_unit_id


def read_modelo_work_form_for_cli(
    client: FrontendClient, *, work_unit_id: str, language: OutputLanguage, timeout: float = 120
) -> ModeloWorkbenchFormProjectionV1:
    """Read one declaration's form, with the edit baseline the read admitted, in ``language``."""
    completed = run_registered_operation(
        client,
        ModeloWorkbenchFormRequest(profile_id=client.profile_id, work_unit_id=work_unit_id, output_language=language),
        definition_id=MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        result_type=ModeloWorkbenchFormProjectionV1,
        request_version=1,
        result_version=1,
        timeout=timeout,
    )
    projection = completed.projection
    if not _belongs_to(
        client.profile_id,
        work_unit_id,
        result_profile_id=projection.profile_id,
        result_work_unit_id=projection.work_unit_id,
    ):
        raise invalid_completion_error(completed)
    return projection


def _operator_input(submission: ModeloEditSubmissionV1, language: OutputLanguage) -> ModeloEditOperatorInputV2:
    return ModeloEditOperatorInputV2(
        submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=language
    )


def preflight_modelo_edit_for_cli(
    client: FrontendClient, submission: ModeloEditSubmissionV1, *, language: OutputLanguage, timeout: float = 120
) -> ModeloEditPreflightProjectionV1:
    """Check the staged intents against the declaration without applying them; the review the window shows."""
    work_unit_id = submission.baseline.work_unit_id
    completed = run_registered_operation(
        client,
        _operator_input(submission, language),
        definition_id=MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        result_type=ModeloEditPreflightProjectionV1,
        request_version=2,
        result_version=1,
        timeout=timeout,
        financial_request_type=ModeloEditPreflightRequestV2,
    )
    projection = completed.projection
    if not _belongs_to(
        client.profile_id,
        work_unit_id,
        result_profile_id=projection.profile_id,
        result_work_unit_id=projection.work_unit_id,
    ):
        raise invalid_completion_error(completed)
    return projection


def apply_modelo_edit_for_cli(
    client: FrontendClient,
    submission: ModeloEditSubmissionV1,
    *,
    language: OutputLanguage,
    timeout: float = 120,
    settlement_timeout: float = _APPLY_SETTLEMENT_SECONDS,
) -> RegisteredOperationCompletion[ModeloEditApplyPublicResultV1]:
    """Apply the staged intents through the guarded edit; a refusal settles as its registered error."""
    work_unit_id = submission.baseline.work_unit_id
    completed = run_registered_operation(
        client,
        _operator_input(submission, language),
        definition_id=MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        result_type=ModeloEditApplyPublicResultV1,
        request_version=2,
        result_version=1,
        timeout=timeout,
        settlement_timeout=settlement_timeout,
        pending_check_command=f"aeat app modelo work revisions {work_unit_id}",
        financial_request_type=ModeloEditApplyOperationRequestV2,
    )
    if completed.effect is not OperationEffect.UPDATED:
        raise invalid_completion_error(completed)
    return completed


__all__ = ["apply_modelo_edit_for_cli", "preflight_modelo_edit_for_cli", "read_modelo_work_form_for_cli"]
