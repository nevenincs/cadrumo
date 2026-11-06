"""Populated confirmation record shared by the record suites."""

from __future__ import annotations

from datetime import UTC, datetime

from ....core.confirmation_gate import ConfirmationBlockReason, FindingResolutionAction
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ..confirmation_gate import ConfirmationBlocker, FindingResolution
from ..confirmation_record import (
    FieldAssertion,
    InvoiceConfirmationRecord,
    ResolvedFinding,
)
from ..invoice_draft_records import FieldAmbiguityCandidate

CONFIRMATION_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
CONFIRMATION_TRANSCRIPTION_SHA = "a" * 64
CONFIRMATION_EVIDENCE_SHA = "b" * 64
CONFIRMATION_INVOICE_ID = "c" * 64


def populated_confirmation_record() -> InvoiceConfirmationRecord:
    """A record with EVERY defaultable field populated off its default.

    ``evidence_sha256``, ``transcription_sha256``, ``assertions`` and
    ``resolutions`` all default; a fixture leaving any of them defaulted would
    roundtrip identically whether the store persisted it or dropped it.
    """
    blocker = ConfirmationBlocker(
        blocker_id="0123456789abcdef",
        reason=ConfirmationBlockReason.AMBIGUOUS_IDENTITY,
        field="supplier_tax_id",
        detail="two tax ids printed on the same document",
        candidates=(
            FieldAmbiguityCandidate(value="ESB00015016", anchor="NIF: ESB00015016", note="header block"),
            FieldAmbiguityCandidate(value="ESX0001500M", anchor="ESX0001500M", note="footer block"),
        ),
    )
    return InvoiceConfirmationRecord(
        confirmation_id="fedcba9876543210",
        bucket_id=CONFIRMATION_BUCKET_ID,
        invoice_id=CONFIRMATION_INVOICE_ID,
        evidence_reference="ev-structured-001",
        evidence_sha256=CONFIRMATION_EVIDENCE_SHA,
        transcription_sha256=CONFIRMATION_TRANSCRIPTION_SHA,
        extractor="exact_structured",
        confirmed_by="gestor@example.test",
        confirmed_at=datetime(2024, 11, 15, 9, 0, tzinfo=UTC),
        assertions=(
            FieldAssertion(
                field="taxable_base",
                asserted_value="150.00",
                prior_value="100.00",
                prior_origin=FieldOrigin.VISION,
                prior_grounding=FieldGroundingOutcome.ANCHORED,
            ),
        ),
        resolutions=(
            ResolvedFinding(
                blocker=blocker,
                resolution=FindingResolution(
                    blocker_id="0123456789abcdef",
                    action=FindingResolutionAction.CHOOSE_CANDIDATE,
                    value="ESX0001500M",
                    note="matched against the paper invoice header",
                ),
            ),
        ),
    )
