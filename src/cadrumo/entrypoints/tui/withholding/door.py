"""Typed TUI application door for shared withholding evidence capture.

This module deliberately owns no Textual widgets, invoice repository, or tax
arithmetic.  A caller supplies the canonical invoice it read through the
encrypted catalogue and this door turns that evidence into the established
invoice capture command before calling the shared producer.  Composition stays
with the TUI host so this module can be exercised without a launcher.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from ....application.aggregation.invoice_retencion import (
    InvoiceWithholdingEvidenceError,
    InvoiceWithholdingEvidenceRequest,
    build_invoice_withholding_capture,
)
from ....application.aggregation.withholding_observation_service import (
    WithholdingGenerationAudit,
    WithholdingObservationMutationError,
    WithholdingObservationService,
    WithholdingWindowScope,
    WithholdingWindowState,
)
from ....application.aggregation.withholding_producer import (
    WithholdingEvidenceCaptureResult,
    WithholdingProducer,
    WithholdingProducerError,
)
from ....core.models import STRICT_FROZEN_CONFIG

if TYPE_CHECKING:
    from ....domain.invoices.models import Invoice


@dataclass(frozen=True, slots=True)
class TuiInvoiceWithholdingCaptureRequest:
    """Canonical invoice plus the explicitly supplied withholding evidence.

    The host reads ``invoice`` and its ``catalogue_revision_id`` through the
    encrypted catalogue boundary.  The request intentionally reuses the
    established evidence type: it admits property evidence and Modelo 190
    fields, but no caller-authored recognition date or liability cap.
    """

    invoice: Invoice
    catalogue_revision_id: str
    evidence: InvoiceWithholdingEvidenceRequest
    filing_year: int


class TuiWithholdingCaptureOutcome(BaseModel):
    """Payload-safe TUI result for one capture attempt."""

    model_config = STRICT_FROZEN_CONFIG

    status: Literal["captured", "replayed", "refused", "omitted"]
    scope: WithholdingWindowScope | None = None
    generation_id: str | None = Field(default=None, min_length=64, max_length=64)
    refusal_code: str | None = Field(default=None, min_length=1, max_length=128)


class TuiWithholdingDoor:
    """Small TUI-facing port onto the shared withholding application services."""

    def __init__(self, *, service: WithholdingObservationService) -> None:
        """Bind a TUI surface to the already composed atomic service."""
        self._service = service
        self._producer = WithholdingProducer(service=service)

    def capture(
        self,
        request: TuiInvoiceWithholdingCaptureRequest | None,
    ) -> TuiWithholdingCaptureOutcome:
        """Capture invoice-backed evidence without surfacing financial payloads.

        ``None`` represents omission and leaves the service untouched.  Every
        refusal is converted to its bounded code so presentation does not echo
        invoice, recipient, or monetary content in an exception message.
        """
        if request is None:
            return TuiWithholdingCaptureOutcome(status="omitted")
        try:
            prepared = build_invoice_withholding_capture(
                request.invoice,
                catalogue_revision_id=request.catalogue_revision_id,
                request=request.evidence,
                applicable_year=request.filing_year,
            )
            captured = self._producer.capture(prepared.command)
        except (
            InvoiceWithholdingEvidenceError,
            WithholdingProducerError,
            WithholdingObservationMutationError,
        ) as error:
            return TuiWithholdingCaptureOutcome(status="refused", refusal_code=error.code)
        except ValueError:
            # Pydantic and validation-boundary errors have useful developer
            # messages but may include caller evidence.  They are deliberately
            # collapsed before they cross the presentation boundary.
            return TuiWithholdingCaptureOutcome(status="refused", refusal_code="invalid_withholding_evidence")
        if captured is None:  # pragma: no cover - the prepared command is never omitted
            raise AssertionError("prepared TUI invoice capture must mutate or replay")
        return _capture_outcome(captured)

    def read_window(self, scope: WithholdingWindowScope) -> WithholdingWindowState:
        """Inspect the persisted active evidence and its exact baseline."""
        return self._service.read_window(scope)

    def read_generation(
        self,
        scope: WithholdingWindowScope,
        generation_id: str,
    ) -> WithholdingGenerationAudit | None:
        """Inspect correction history without altering the active evidence."""
        return self._service.read_generation(scope, generation_id)


def _capture_outcome(captured: WithholdingEvidenceCaptureResult) -> TuiWithholdingCaptureOutcome:
    """Project safe shared-service metadata for the TUI presenter."""
    return TuiWithholdingCaptureOutcome(
        status="replayed" if captured.mutation.replayed else "captured",
        scope=captured.scope,
        generation_id=captured.mutation.baseline.generation_id,
    )


__all__ = [
    "TuiInvoiceWithholdingCaptureRequest",
    "TuiWithholdingCaptureOutcome",
    "TuiWithholdingDoor",
]
