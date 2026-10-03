"""Registered exact-profile execution for review-package exchange commands."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import UUID

import typer
from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.modelo.review_package_exchange_operation import (
    MODELO_REVIEW_PACKAGE_COUNTER_SIGN_OPERATION_DEFINITION_ID,
    MODELO_REVIEW_PACKAGE_DECRYPT_OPERATION_DEFINITION_ID,
    MODELO_REVIEW_PACKAGE_ENCRYPT_FEEDBACK_OPERATION_DEFINITION_ID,
    MODELO_REVIEW_PACKAGE_ENCRYPT_FOR_RECIPIENT_OPERATION_DEFINITION_ID,
    MODELO_REVIEW_PACKAGE_IMPORT_FEEDBACK_OPERATION_DEFINITION_ID,
    MODELO_REVIEW_PACKAGE_SIGN_OPERATION_DEFINITION_ID,
    ModeloReviewPackageCounterSignProjection,
    ModeloReviewPackageCounterSignRequest,
    ModeloReviewPackageDecryptProjection,
    ModeloReviewPackageDecryptRequest,
    ModeloReviewPackageEncryptFeedbackProjection,
    ModeloReviewPackageEncryptFeedbackRequest,
    ModeloReviewPackageEncryptForRecipientProjection,
    ModeloReviewPackageEncryptForRecipientRequest,
    ModeloReviewPackageImportFeedbackProjection,
    ModeloReviewPackageImportFeedbackRequest,
    ModeloReviewPackageSignProjection,
    ModeloReviewPackageSignRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client, require_profile_client
from .runtime_registered_operation import run_registered_operation


def _client(ctx: typer.Context, bucket_id: str | None) -> RuntimeFrontendClient:
    """Use only the authenticated target and reject a conflicting legacy selector."""
    client = bound_profile_client(ctx)
    if bucket_id is not None and bucket_id.strip():
        try:
            requested_profile_id = UUID(bucket_id.strip())
        except ValueError:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
        if requested_profile_id != client.profile_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return client


def _submit_from_context[ProjectionT: BaseModel](
    ctx: typer.Context,
    client: RuntimeFrontendClient,
    request: BaseModel,
    *,
    definition_id: str,
    result_type: type[ProjectionT],
) -> RegisteredOperationCompletion[ProjectionT]:
    bound = require_profile_client(ctx, expected_profile_id=client.profile_id)
    if bound is not client:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return run_registered_operation(
        bound,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(bound.profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
    )


def _correlate[ProjectionT: BaseModel](
    completed: RegisteredOperationCompletion[ProjectionT],
    *,
    profile_id: UUID,
    expected_effect: OperationEffect | frozenset[OperationEffect],
) -> ProjectionT:
    projection = completed.projection
    effects = expected_effect if isinstance(expected_effect, frozenset) else frozenset({expected_effect})
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect not in effects
        or completed.refusal_code is not None
        or getattr(projection, "profile_id", None) != profile_id
        or getattr(projection, "effect", None) is not completed.effect
    ):
        raise invalid_completion_error(completed)
    return projection


def run_review_package_sign(
    ctx: typer.Context,
    *,
    package: Path,
    output: Path,
    bucket_id: str | None = None,
) -> ModeloReviewPackageSignProjection:
    """Sign a package through the registered exact-profile worker."""
    client = _client(ctx, bucket_id)
    request = ModeloReviewPackageSignRequest(profile_id=client.profile_id, package=package, output=output)
    completed = _submit_from_context(
        ctx,
        client,
        request,
        definition_id=MODELO_REVIEW_PACKAGE_SIGN_OPERATION_DEFINITION_ID,
        result_type=ModeloReviewPackageSignProjection,
    )
    projection = _correlate(completed, profile_id=client.profile_id, expected_effect=OperationEffect.UPDATED)
    if (
        projection.package_path != str(request.package)
        or projection.signature_path != str(request.output)
        or projection.bucket_id != str(client.profile_id)
    ):
        raise invalid_completion_error(completed)
    return projection


def run_review_package_counter_sign(
    ctx: typer.Context,
    *,
    package: Path,
    signature: Path,
    output: Path,
    note: str = "",
    bucket_id: str | None = None,
) -> ModeloReviewPackageCounterSignProjection:
    """Counter-sign a package through the registered exact-profile worker."""
    client = _client(ctx, bucket_id)
    request = ModeloReviewPackageCounterSignRequest(
        profile_id=client.profile_id,
        package=package,
        signature=signature,
        output=output,
        note=note,
    )
    completed = _submit_from_context(
        ctx,
        client,
        request,
        definition_id=MODELO_REVIEW_PACKAGE_COUNTER_SIGN_OPERATION_DEFINITION_ID,
        result_type=ModeloReviewPackageCounterSignProjection,
    )
    projection = _correlate(completed, profile_id=client.profile_id, expected_effect=OperationEffect.UPDATED)
    if (
        projection.package_path != str(request.package)
        or projection.signature_path != str(request.signature)
        or projection.receipt_path != str(request.output)
        or projection.bucket_id != str(client.profile_id)
        or projection.note != request.note
    ):
        raise invalid_completion_error(completed)
    return projection


def run_review_package_encrypt_for_recipient(
    ctx: typer.Context,
    *,
    package: Path,
    recipient_id: str,
    output: Path,
    review_only: bool = False,
    valid_for_days: int | None = None,
    bucket_id: str | None = None,
) -> ModeloReviewPackageEncryptForRecipientProjection:
    """Encrypt for the registered recipient through the profile worker."""
    client = _client(ctx, bucket_id)
    request = ModeloReviewPackageEncryptForRecipientRequest(
        profile_id=client.profile_id,
        package=package,
        recipient_id=recipient_id,
        output=output,
        review_only=review_only,
        valid_for_days=valid_for_days,
    )
    completed = _submit_from_context(
        ctx,
        client,
        request,
        definition_id=MODELO_REVIEW_PACKAGE_ENCRYPT_FOR_RECIPIENT_OPERATION_DEFINITION_ID,
        result_type=ModeloReviewPackageEncryptForRecipientProjection,
    )
    projection = _correlate(completed, profile_id=client.profile_id, expected_effect=OperationEffect.UPDATED)
    if (
        projection.package_path != str(request.package)
        or projection.output_path != str(request.output)
        or projection.recipient_id != request.recipient_id
        or projection.review_only is not request.review_only
        or (valid_for_days is None and projection.valid_until is not None)
        or (
            valid_for_days is not None
            and (
                projection.valid_until is None
                or projection.valid_until - projection.issued_at != timedelta(days=valid_for_days)
            )
        )
    ):
        raise invalid_completion_error(completed)
    return projection


def run_review_package_decrypt(
    ctx: typer.Context,
    *,
    envelope_path: Path,
    output: Path,
    bucket_id: str | None = None,
) -> ModeloReviewPackageDecryptProjection:
    """Decrypt to the operator-requested final path through the profile worker."""
    client = _client(ctx, bucket_id)
    request = ModeloReviewPackageDecryptRequest(
        profile_id=client.profile_id,
        envelope_path=envelope_path,
        output=output,
    )
    completed = _submit_from_context(
        ctx,
        client,
        request,
        definition_id=MODELO_REVIEW_PACKAGE_DECRYPT_OPERATION_DEFINITION_ID,
        result_type=ModeloReviewPackageDecryptProjection,
    )
    projection = _correlate(completed, profile_id=client.profile_id, expected_effect=OperationEffect.UPDATED)
    if (
        projection.envelope_path != str(request.envelope_path)
        or projection.output_path != str(request.output)
        or projection.bucket_id != str(client.profile_id)
    ):
        raise invalid_completion_error(completed)
    return projection


def run_review_package_encrypt_feedback(
    ctx: typer.Context,
    *,
    originator_id: str,
    work_unit_id: str,
    calculation_revision_id: str,
    submitted_by: str,
    output: Path,
    note: str = "",
    receipt: Path | None = None,
    bucket_id: str | None = None,
) -> ModeloReviewPackageEncryptFeedbackProjection:
    """Seal feedback through the registered exact-profile worker."""
    client = _client(ctx, bucket_id)
    request = ModeloReviewPackageEncryptFeedbackRequest(
        profile_id=client.profile_id,
        originator_id=originator_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        submitted_by=submitted_by,
        output=output,
        note=note,
        receipt=receipt,
    )
    completed = _submit_from_context(
        ctx,
        client,
        request,
        definition_id=MODELO_REVIEW_PACKAGE_ENCRYPT_FEEDBACK_OPERATION_DEFINITION_ID,
        result_type=ModeloReviewPackageEncryptFeedbackProjection,
    )
    projection = _correlate(completed, profile_id=client.profile_id, expected_effect=OperationEffect.UPDATED)
    if (
        projection.output_path != str(request.output)
        or projection.originator_id != request.originator_id
        or projection.work_unit_id != request.work_unit_id
        or projection.calculation_revision_id != request.calculation_revision_id
        or projection.has_counter_sign is not (request.receipt is not None)
        or projection.valid_until is not None
    ):
        raise invalid_completion_error(completed)
    return projection


def run_review_package_import_feedback(
    ctx: typer.Context,
    *,
    envelope_path: Path,
    package: Path,
    operator_public_key_hex: str,
    counter_signer_public_key_hex: str | None = None,
    bucket_id: str | None = None,
) -> ModeloReviewPackageImportFeedbackProjection:
    """Verify and import feedback through the registered exact-profile worker."""
    client = _client(ctx, bucket_id)
    request = ModeloReviewPackageImportFeedbackRequest(
        profile_id=client.profile_id,
        envelope_path=envelope_path,
        package=package,
        operator_public_key_hex=operator_public_key_hex,
        counter_signer_public_key_hex=counter_signer_public_key_hex,
    )
    completed = _submit_from_context(
        ctx,
        client,
        request,
        definition_id=MODELO_REVIEW_PACKAGE_IMPORT_FEEDBACK_OPERATION_DEFINITION_ID,
        result_type=ModeloReviewPackageImportFeedbackProjection,
    )
    projection = _correlate(
        completed,
        profile_id=client.profile_id,
        expected_effect=frozenset({OperationEffect.NONE, OperationEffect.UPDATED}),
    )
    if (
        projection.envelope_path != str(request.envelope_path)
        or projection.bucket_id != str(client.profile_id)
        or projection.counter_signature_verified not in {None, True}
        or projection.attached_to_journal is not (projection.counter_signature_verified is True)
        or (projection.attached_to_journal and projection.effect is not OperationEffect.UPDATED)
    ):
        raise invalid_completion_error(completed)
    return projection


__all__ = [
    "run_review_package_counter_sign",
    "run_review_package_decrypt",
    "run_review_package_encrypt_feedback",
    "run_review_package_encrypt_for_recipient",
    "run_review_package_import_feedback",
    "run_review_package_sign",
]
