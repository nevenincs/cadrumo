"""Typed TUI application door for shared withholding evidence capture.

This module deliberately owns no Textual widgets, invoice or ledger repository,
or tax arithmetic.  A caller supplies the canonical invoice, or the addressed
ledger transaction read, that it obtained through the encrypted catalogue, and
this door turns that evidence into the established capture command before
calling the shared producer.  Composition stays with the TUI host so this
module can be exercised without a launcher.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from ....application.aggregation.invoice_retencion import (
    InvoiceWithholdingEvidenceError,
    InvoiceWithholdingEvidenceRequest,
    build_invoice_withholding_capture,
)
from ....application.aggregation.ledger_payment_withholding import (
    LedgerPaymentWithholdingEvidenceError,
    LedgerPaymentWithholdingEvidenceRequest,
    build_ledger_payment_withholding_capture,
    resolve_ledger_payment_transaction,
)
from ....application.aggregation.withholding_filing_cadence import (
    WithholdingFilerCadence,
    WithholdingFilingCadenceError,
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
from ....application.aggregation.withholding_recognition import WithholdingRecognitionError
from ....core.models import STRICT_FROZEN_CONFIG

if TYPE_CHECKING:
    from ....domain.invoices.models import Invoice
    from ....domain.transactions.models import TransactionCatalogue


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


@dataclass(frozen=True, slots=True)
class TuiLedgerPaymentWithholdingCaptureRequest:
    """Addressed ledger read plus the explicitly declared payroll evidence.

    The host reads ``transactions`` for the one requested id through the
    encrypted ledger catalogue, between two reads of the catalogue revision.
    ``catalogue_revision_id`` is ``None`` when no stable revision could be
    stated or it changed during the read; the door then refuses before any
    command exists.  An id the catalogue does not hold is simply absent from
    ``transactions`` and is refused by the shared resolver.
    """

    transactions: TransactionCatalogue
    catalogue_revision_id: str | None
    evidence: LedgerPaymentWithholdingEvidenceRequest
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

    def __init__(
        self,
        *,
        service: WithholdingObservationService,
        filer_cadence: Callable[[int], WithholdingFilerCadence],
    ) -> None:
        """Bind a TUI surface to the atomic service and the filer's schedule for a filing year."""
        self._service = service
        self._producer = WithholdingProducer(service=service)
        self._filer_cadence = filer_cadence

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
            cadence = self._filer_cadence(request.filing_year)
            prepared = build_invoice_withholding_capture(
                request.invoice,
                catalogue_revision_id=request.catalogue_revision_id,
                request=request.evidence,
                applicable_year=request.filing_year,
                cadence=cadence,
            )
            captured = self._producer.capture(prepared.command, cadence=cadence)
        except (
            InvoiceWithholdingEvidenceError,
            WithholdingFilingCadenceError,
            WithholdingProducerError,
            WithholdingObservationMutationError,
        ) as error:
            return TuiWithholdingCaptureOutcome(status="refused", refusal_code=error.refusal_code)
        except (WithholdingRecognitionError, ValueError):
            # Pydantic, validation-boundary and recognition errors have useful
            # developer messages but may include caller evidence.  They are
            # deliberately collapsed before they cross the presentation boundary.
            return TuiWithholdingCaptureOutcome(status="refused", refusal_code="invalid_withholding_evidence")
        if captured is None:  # pragma: no cover - the prepared command is never omitted
            raise AssertionError("prepared TUI invoice capture must mutate or replay")
        return _capture_outcome(captured)

    def capture_ledger_payment(
        self,
        request: TuiLedgerPaymentWithholdingCaptureRequest | None,
    ) -> TuiWithholdingCaptureOutcome:
        """Capture work-income evidence anchored to its paying ledger transaction.

        This is the TUI transport over the same builder and producer the
        aggregate CLI uses for a ledger payment; refusals surface only their
        bounded code, exactly as invoice capture does.
        """
        if request is None:
            return TuiWithholdingCaptureOutcome(status="omitted")
        try:
            if request.catalogue_revision_id is None:
                raise LedgerPaymentWithholdingEvidenceError("transaction_catalogue_revision_unavailable")
            cadence = self._filer_cadence(request.filing_year)
            prepared = build_ledger_payment_withholding_capture(
                resolve_ledger_payment_transaction(request.transactions, request.evidence.transaction_id),
                catalogue_revision_id=request.catalogue_revision_id,
                request=request.evidence,
                applicable_year=request.filing_year,
                cadence=cadence,
            )
            captured = self._producer.capture(prepared.command, cadence=cadence)
        except (
            LedgerPaymentWithholdingEvidenceError,
            WithholdingFilingCadenceError,
            WithholdingProducerError,
            WithholdingObservationMutationError,
        ) as error:
            return TuiWithholdingCaptureOutcome(status="refused", refusal_code=error.refusal_code)
        except (WithholdingRecognitionError, ValueError):
            return TuiWithholdingCaptureOutcome(status="refused", refusal_code="invalid_withholding_evidence")
        if captured is None:  # pragma: no cover - the prepared command is never omitted
            raise AssertionError("prepared TUI ledger payment capture must mutate or replay")
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
    "TuiLedgerPaymentWithholdingCaptureRequest",
    "TuiWithholdingCaptureOutcome",
    "TuiWithholdingDoor",
]
