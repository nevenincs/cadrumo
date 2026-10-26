"""Authenticated CLI transport for the registered stored-document page read."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from uuid import UUID

import typer

from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error

from ...application.ledger.evidence_page_contracts import (
    EVIDENCE_PAGE_IMAGE_URL_PREFIX,
    LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID,
    LedgerEvidencePageProjection,
    LedgerEvidencePageRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import active_bucket_id_or_refuse

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True, slots=True)
class EvidencePageRead:
    """The page read's correlated projection and the PNG bytes its image URL carries."""

    projection: LedgerEvidencePageProjection
    png: bytes


def run_ledger_evidence_page(
    ctx: typer.Context,
    *,
    evidence_id: str | None,
    attachment_id: str | None,
    page: int,
    max_width: int,
) -> EvidencePageRead:
    """Draw one page of a stored document through the exact active-profile runtime frontend."""
    expected_profile_id = UUID(active_bucket_id_or_refuse())
    client = require_profile_client(ctx, expected_profile_id=expected_profile_id)
    request = LedgerEvidencePageRequest(
        profile_id=client.profile_id,
        evidence_id=evidence_id,
        attachment_id=attachment_id,
        page=page,
        max_width=max_width,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerEvidencePageProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or projection.profile_id != client.profile_id
        or projection.evidence_id != evidence_id
        or (attachment_id is not None and projection.attachment_id != attachment_id)
        or projection.page != page
        or projection.width > max_width
    ):
        raise invalid_completion_error(completed)
    try:
        png = base64.b64decode(projection.image_data_url.removeprefix(EVIDENCE_PAGE_IMAGE_URL_PREFIX), validate=True)
    except (binascii.Error, ValueError):
        raise invalid_completion_error(completed) from None
    if not png.startswith(_PNG_SIGNATURE):
        raise invalid_completion_error(completed)
    return EvidencePageRead(projection=projection, png=png)


__all__ = ["EvidencePageRead", "run_ledger_evidence_page"]
