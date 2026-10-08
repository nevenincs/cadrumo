"""Publish one saved calculation after exact readable-export disclosure.

:class:`OutputSchema` defines the public result envelope.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

import typer

from ...application.export.google_review_operation_contracts import (
    GOOGLE_REVIEW_OPERATION_DEFINITION_ID,
    GOOGLE_REVIEW_RESPONSE_SCHEMA_BINDING,
    GOOGLE_REVIEW_REVIEW_SCHEMA_BINDING,
    GoogleReviewProjection,
    GoogleReviewRequest,
    GoogleReviewResult,
)
from ...application.export.publication_receipt import ReadablePayloadCategory
from ...application.operations.frontend_projection import OperationReviewProjectionReferenceV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.i18n.render import tr
from ...core.json_contract import OutputSchema
from ...core.operations import profile_operation_subject
from .common import emit_envelope
from .registered_operation_contracts import RegisteredOperationCompletion, RegisteredOperationReviewHandler
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


class GoogleReviewPublicationResult(OutputSchema):
    """A confirmed native review publication, not a template or local export."""

    publication: GoogleReviewResult


def _require_google_review_reference(
    review: GoogleReviewProjection, reference: OperationReviewProjectionReferenceV1
) -> None:
    """Refuse a disclosure from another invocation or revision before readable publication."""
    if review.identity.operation_id != reference.operation_id or review.revision != reference.revision:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def accept_google_review(request: GoogleReviewRequest, review: GoogleReviewProjection) -> Literal["apply"]:
    """Accept only the requested calculation and the runtime's exact readable destination."""
    if (
        review.profile_id != request.profile_id
        or review.publication_id != request.publication_id
        or review.calculation_revision_id != request.calculation_revision_id
        or review.filing_record_id != request.filing_record_id
        or review.identity.definition_id != GOOGLE_REVIEW_OPERATION_DEFINITION_ID
        or review.identity.subject_ref != profile_operation_subject(str(request.profile_id))
        or not review.root_folder_id.strip()
        or not review.readable_by_authorized_users
        or ReadablePayloadCategory.CALCULATION not in review.payload_categories
        or not set(review.payload_categories) <= {ReadablePayloadCategory.CALCULATION, ReadablePayloadCategory.LEDGER}
    ):
        raise ValueError("review does not match the selected readable spreadsheet publication")
    return "apply"


def publish_google_review_cli(
    ctx: typer.Context,
    calculation_revision_id: str,
    publication_id: str | None = None,
    accept_readable_export: bool = False,
    filing_record_id: str | None = None,
) -> None:
    """Publish the exact saved revision only after destination disclosure is accepted."""
    if not accept_readable_export:
        raise typer.BadParameter(tr("cli.app.modelo.spreadsheet.publish.accept_readable_export_help"))
    client = bound_profile_client(ctx)
    request = GoogleReviewRequest(
        profile_id=client.profile_id,
        calculation_revision_id=calculation_revision_id,
        filing_record_id=filing_record_id,
        publication_id=UUID(publication_id) if publication_id else uuid4(),
    )

    reviewed: GoogleReviewProjection | None = None

    def decide(review: GoogleReviewProjection) -> Literal["apply"]:
        nonlocal reviewed
        decision = accept_google_review(request, review)
        reviewed = review
        return decision

    completed = run_registered_operation(
        client,
        request,
        definition_id=GOOGLE_REVIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=GoogleReviewResult,
        request_version=1,
        result_version=1,
        timeout=120,
        settlement_timeout=600,
        review=RegisteredOperationReviewHandler(
            review_type=GoogleReviewProjection,
            review_schema=GOOGLE_REVIEW_REVIEW_SCHEMA_BINDING.identity,
            response_schema=GOOGLE_REVIEW_RESPONSE_SCHEMA_BINDING.identity,
            decide=decide,
            validate_reference=_require_google_review_reference,
        ),
    )
    if not isinstance(completed, RegisteredOperationCompletion):
        raise typer.BadParameter("Readable export requires --accept-readable-export for the selected revision.")
    result = completed.projection
    if (
        result.profile_id != request.profile_id
        or result.publication_id != request.publication_id
        or reviewed is None
        or result.snapshot_digest != reviewed.snapshot_digest
        or result.root_folder_id != reviewed.root_folder_id
        or completed.operation_id != reviewed.identity.operation_id
    ):
        raise ValueError("publication receipt does not match the request")
    emit_envelope(
        ctx,
        command="modelo.spreadsheet.publish",
        result=GoogleReviewPublicationResult(publication=result),
        lines=(f"spreadsheet_url\t{result.spreadsheet_url}",),
    )
