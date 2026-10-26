"""Exact-profile runtime submission of a local Modelo review-package build."""

from __future__ import annotations

from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from ...application.modelo.review_package_operation import (
    MODELO_REVIEW_PACKAGE_BUILD_OPERATION_DEFINITION_ID,
    ModeloReviewPackageBuildPublicResultV1,
    ModeloReviewPackageBuildRequest,
)
from ...core.operations import OperationEffect


def run_modelo_review_package_build(
    client: FrontendClient,
    request: ModeloReviewPackageBuildRequest,
    *,
    work_unit_id: str,
    timeout: float = 120,
) -> RegisteredOperationCompletion[ModeloReviewPackageBuildPublicResultV1]:
    """Return the canonical worker's complete package and export-event receipt."""
    if request.profile_id != client.profile_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_REVIEW_PACKAGE_BUILD_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        result_type=ModeloReviewPackageBuildPublicResultV1,
        request_version=1,
        result_version=1,
        timeout=timeout,
    )
    result = completed.projection
    if (
        not isinstance(result, ModeloReviewPackageBuildPublicResultV1)
        or result.manifest.bucket_id != str(client.profile_id)
        or result.manifest.work_unit_id != work_unit_id
        or result.manifest.calculation_revision_id != request.calculation_revision_id
        or result.output_path != request.output_path
        or completed.effect is not OperationEffect.UPDATED
    ):
        raise invalid_completion_error(completed)
    return completed


__all__ = ["run_modelo_review_package_build"]
