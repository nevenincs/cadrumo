"""Typed refusal outcomes owned by the ledger application boundary."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import cast

from ...core import ActionEvidenceProvenance, NoRecoveryOutcome
from ..operator_actions import PreconditionVerdict, no_action_precondition_verdict


class LedgerPreconditionCondition(StrEnum):
    """Closed failed-condition identities for evidence and ledger refusals."""

    CONFIRMATION_BLOCKERS_RESOLVED = "ledger.confirmation.blockers_resolved"
    EVIDENCE_ATTACHMENT_SELECTION_VALID = "ledger.evidence.attachment_selection_valid"
    EVIDENCE_BYTES_READABLE = "ledger.evidence.bytes_readable"
    EVIDENCE_COUNTERPARTY_VALID = "ledger.evidence.counterparty_valid"
    EVIDENCE_DOCUMENT_BYTES_AVAILABLE = "ledger.evidence.document_bytes_available"
    EVIDENCE_FILE_EXTENSION_SUPPORTED = "ledger.evidence.file_extension_supported"
    EVIDENCE_FILE_READABLE = "ledger.evidence.file_readable"
    EVIDENCE_IDEMPOTENCY_KEY_UNIQUE = "ledger.evidence.idempotency_key_unique"
    EVIDENCE_INVOICE_DATE_AVAILABLE = "ledger.evidence.invoice_date_available"
    EVIDENCE_REQUIRED_FIELD_AVAILABLE = "ledger.evidence.required_field_available"
    EVIDENCE_REFERENCE_RESOLVES = "ledger.evidence.reference_resolves"
    EVIDENCE_READER_AVAILABLE = "ledger.evidence.reader_available"
    EVIDENCE_TEXT_LAYER_AVAILABLE = "ledger.evidence.text_layer_available"
    EVIDENCE_VISION_CAPABILITY_ENABLED = "ledger.evidence.vision_capability_enabled"
    EVIDENCE_XML_INVOICE_SUPPORTED = "ledger.evidence.xml_invoice_supported"
    FILER_POSTCODE_VALID = "ledger.filer.postcode_valid"
    COUNTERPARTY_IDENTIFIER_VALID = "ledger.counterparty.identifier_valid"
    CONSENT_REDERIVATION_ARTEFACT_AVAILABLE = "ledger.consent_rederivation.artefact_available"
    CONSENT_REDERIVATION_TRANSCRIPTION_AVAILABLE = "ledger.consent_rederivation.transcription_available"
    CONSENT_REDERIVATION_ON_HOST = "ledger.consent_rederivation.on_host"


class LedgerPreconditionErrorMixin:
    """Attach one typed terminal refusal to an existing registered error."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        precondition_verdict: PreconditionVerdict | None = None,
    ) -> None:
        """Keep a domain verdict without retaining a presentation suggestion."""
        parent_init = cast(Callable[..., None], super().__init__)
        parent_init(message, context=context, translated_message=translated_message)
        self._terminal_precondition_verdict = precondition_verdict

    @property
    def terminal_precondition_verdict(self) -> PreconditionVerdict | None:
        """Return the exact application-owned refusal for later projection."""
        return self._terminal_precondition_verdict


def ledger_no_recovery_verdict(
    condition: LedgerPreconditionCondition,
    *,
    facts: Mapping[str, str | int | bool],
    outcome: NoRecoveryOutcome = NoRecoveryOutcome.OPERATOR_DECISION,
) -> PreconditionVerdict:
    """Return the exact ledger fact and explicit absence of a bound recovery.

    Ledger services can identify their failed condition but cannot derive a
    safe executable action from those facts.  Keeping the result typed makes
    that boundary explicit without retaining a copy-paste command string.
    """
    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=outcome,
    )


__all__ = ["LedgerPreconditionCondition", "LedgerPreconditionErrorMixin", "ledger_no_recovery_verdict"]
