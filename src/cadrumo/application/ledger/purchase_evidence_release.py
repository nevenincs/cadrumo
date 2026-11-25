"""Release the purchase evidence linked to one ledger movement.

A movement's purchase-evidence slot is set once by the attach authority and is
otherwise immutable, so a person who linked the wrong document, or a document
that is not a purchase invoice, had no way back short of removing the movement.
This service is that way back, in two forms:

* ``detach`` clears the slot. The evidence record and its bytes stay in the
  profile, so the document can be linked elsewhere.
* ``keep_as_document`` clears the slot and keeps the evidence's stored document
  on the movement as an ordinary attachment, so the movement still shows it but
  no calculation reads it as a purchase invoice.

Both go through the one manual-update writer, so the replacement row, its
``PURCHASE_INVOICE_EVIDENCE_DETACHED`` event (and, for ``keep_as_document``, its
``ATTACHMENT_LINKED`` event) commit together. Every reason the release cannot go
ahead is a typed refusal naming its cause and the next step, decided before
anything is written.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal

from ...core.errors.hierarchy import CadrumoError
from ...domain.attachments.errors import AttachmentNotFoundError
from ...domain.transactions.classification_effects import takes_changes
from ...domain.transactions.models import Transaction
from .action_ports import LedgerActionPorts
from .actions_common import (
    blocking_modelo_references,
    merge_identifier_tuple,
    require_actor,
    require_source_command,
    require_transaction,
    resolve_invoice_repository,
    resolve_transaction_repository,
    transaction_modelo_source_ids,
)
from .evidence_reference import EvidenceReferenceOutcome, classify_evidence_reference
from .manual_update import command_from_patch, update_manual_transaction
from .models import (
    LedgerRemovalBlocker,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)

__all__ = [
    "PurchaseEvidenceDisposition",
    "PurchaseEvidenceReleaseCause",
    "PurchaseEvidenceReleaseNextStep",
    "PurchaseEvidenceReleaseRefusedError",
    "release_manual_transaction_purchase_evidence",
]

PurchaseEvidenceDisposition = Literal["detach", "keep_as_document"]
"""What becomes of the released evidence: unlinked, or kept on the movement as an ordinary document."""


class PurchaseEvidenceReleaseCause(StrEnum):
    """Why a release of linked purchase evidence was refused."""

    TRANSACTION_NOT_FOUND = "transaction_not_found"
    """No movement of the profile has the identity the person named."""

    NO_LINKED_PURCHASE_EVIDENCE = "no_linked_purchase_evidence"
    """The movement carries no purchase evidence, or other evidence than the person saw."""

    TRANSACTION_CHANGED = "transaction_changed"
    """The movement changed after the person opened it."""

    TRANSACTION_NOT_EDITABLE = "transaction_not_editable"
    """The movement is archived, stashed or split and takes no change."""

    FINALIZED_CALCULATION_REFERENCE = "finalized_calculation_reference"
    """A finalized calculation cites the movement, and the evidence is part of what it sealed."""

    EVIDENCE_CONFIRMED_INTO_INVOICE = "evidence_confirmed_into_invoice"
    """The evidence was confirmed into a canonical invoice the movement is not linked to."""

    REFERENCE_HAS_NO_STORED_DOCUMENT = "reference_has_no_stored_document"
    """The slot names a catalogue invoice, which has no stored document to keep on the movement."""


class PurchaseEvidenceReleaseNextStep(StrEnum):
    """What the person can do about a refused release."""

    REOPEN_TRANSACTION = "reopen_transaction"
    """Reopen the movement to see its current evidence, then decide again."""

    RESTORE_TRANSACTION = "restore_transaction"
    """Restore the movement to active before changing its evidence."""

    REOPEN_FINALIZED_CALCULATION = "reopen_finalized_calculation"
    """Reopen or amend the finalized calculation that cites the movement first."""

    LINK_MOVEMENT_TO_INVOICE = "link_movement_to_invoice"
    """Link the movement to the confirmed invoice first, so the release orphans nothing."""

    DETACH_INSTEAD = "detach_instead"
    """Detach the reference instead; there is no document to keep."""


_NEXT_STEP: dict[PurchaseEvidenceReleaseCause, PurchaseEvidenceReleaseNextStep] = {
    PurchaseEvidenceReleaseCause.TRANSACTION_NOT_FOUND: PurchaseEvidenceReleaseNextStep.REOPEN_TRANSACTION,
    PurchaseEvidenceReleaseCause.NO_LINKED_PURCHASE_EVIDENCE: PurchaseEvidenceReleaseNextStep.REOPEN_TRANSACTION,
    PurchaseEvidenceReleaseCause.TRANSACTION_CHANGED: PurchaseEvidenceReleaseNextStep.REOPEN_TRANSACTION,
    PurchaseEvidenceReleaseCause.TRANSACTION_NOT_EDITABLE: PurchaseEvidenceReleaseNextStep.RESTORE_TRANSACTION,
    PurchaseEvidenceReleaseCause.FINALIZED_CALCULATION_REFERENCE: (
        PurchaseEvidenceReleaseNextStep.REOPEN_FINALIZED_CALCULATION
    ),
    PurchaseEvidenceReleaseCause.EVIDENCE_CONFIRMED_INTO_INVOICE: (
        PurchaseEvidenceReleaseNextStep.LINK_MOVEMENT_TO_INVOICE
    ),
    PurchaseEvidenceReleaseCause.REFERENCE_HAS_NO_STORED_DOCUMENT: PurchaseEvidenceReleaseNextStep.DETACH_INSTEAD,
}


class PurchaseEvidenceReleaseRefusedError(CadrumoError):
    """A release of linked purchase evidence refused before any write."""

    def __init__(
        self,
        cause: PurchaseEvidenceReleaseCause,
        *,
        blockers: tuple[LedgerRemovalBlocker, ...] = (),
        invoice_ids: tuple[str, ...] = (),
    ) -> None:
        """Keep the typed cause, its next step and the facts that name what blocks it."""
        super().__init__(
            f"purchase evidence release refused: {cause.value}",
            context={"cause": cause.value, "next_step": _NEXT_STEP[cause].value},
        )
        self.cause = cause
        self.next_step = _NEXT_STEP[cause]
        self.blockers = blockers
        self.invoice_ids = invoice_ids


@dataclass(frozen=True, slots=True)
class _ReleasePlan:
    attachment_id: str | None
    """The evidence's stored document, or ``None`` when the slot names a catalogue invoice."""


def release_manual_transaction_purchase_evidence(
    *,
    bucket_id: str,
    transaction_id: str,
    expected_purchase_invoice_evidence_id: str,
    expected_modified_at: datetime,
    disposition: PurchaseEvidenceDisposition,
    actor: str,
    source_command: str,
    ports: LedgerActionPorts,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Clear one movement's purchase-evidence slot, optionally keeping its document on the movement.

    ``expected_purchase_invoice_evidence_id`` and ``expected_modified_at`` are the
    evidence and revision the person saw; a movement that differs from them is
    refused rather than changed.

    Raises:
        PurchaseEvidenceReleaseRefusedError: For every refusal, before any write.
    """
    trimmed_actor = require_actor(actor, operation="ledger purchase evidence release")
    trimmed_source_command = require_source_command(source_command, operation="ledger purchase evidence release")
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=ports.transaction_repository)
    catalogue = repository.load()
    current = require_transaction(catalogue, transaction_id)
    plan = _release_plan(
        current,
        bucket_id=bucket_id,
        expected_purchase_invoice_evidence_id=expected_purchase_invoice_evidence_id,
        expected_modified_at=expected_modified_at,
        disposition=disposition,
        ports=ports,
    )
    command = _release_command(
        current,
        bucket_id=bucket_id,
        plan=plan,
        disposition=disposition,
        actor=trimmed_actor,
        source_command=trimmed_source_command,
    )
    return update_manual_transaction(
        transaction_id=current.transaction_id,
        command=command,
        ports=ports,
        occurred_at=occurred_at,
        catalogue=catalogue,
        expected_current=current,
        _evidence_authority=True,
    )


def _release_plan(
    current: Transaction,
    *,
    bucket_id: str,
    expected_purchase_invoice_evidence_id: str,
    expected_modified_at: datetime,
    disposition: PurchaseEvidenceDisposition,
    ports: LedgerActionPorts,
) -> _ReleasePlan:
    """Decide every refusal from the stored movement, its evidence and its citing calculations."""
    evidence_id = current.purchase_invoice_evidence_id
    if evidence_id is None or evidence_id != expected_purchase_invoice_evidence_id:
        raise PurchaseEvidenceReleaseRefusedError(PurchaseEvidenceReleaseCause.NO_LINKED_PURCHASE_EVIDENCE)
    if current.modified_at != expected_modified_at:
        raise PurchaseEvidenceReleaseRefusedError(PurchaseEvidenceReleaseCause.TRANSACTION_CHANGED)
    if not takes_changes(current.lifecycle_state):
        raise PurchaseEvidenceReleaseRefusedError(PurchaseEvidenceReleaseCause.TRANSACTION_NOT_EDITABLE)
    blockers = blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=transaction_modelo_source_ids(current),
        work_unit_repository=ports.work_unit_repository,
        calculation_repository=ports.calculation_repository,
    )
    if blockers:
        # The link is hashed into a sealed revision's row fingerprint and a
        # recalculation takes the row's base and cuota from it, so releasing it
        # under a finalized revision would change what that revision sealed.
        raise PurchaseEvidenceReleaseRefusedError(
            PurchaseEvidenceReleaseCause.FINALIZED_CALCULATION_REFERENCE, blockers=blockers
        )
    invoices = resolve_invoice_repository(bucket_id=bucket_id, repository=ports.invoice_repository).load()
    reference = classify_evidence_reference(
        evidence_id,
        bucket_id=bucket_id,
        evidence_records=ports.purchase_invoice_evidence_records,
        invoices=invoices,
    )
    if reference.outcome is not EvidenceReferenceOutcome.PURCHASE_INVOICE_EVIDENCE or reference.record is None:
        if disposition == "keep_as_document":
            raise PurchaseEvidenceReleaseRefusedError(PurchaseEvidenceReleaseCause.REFERENCE_HAS_NO_STORED_DOCUMENT)
        return _ReleasePlan(attachment_id=None)
    attachment_id = reference.record.attachment_id
    confirmed = _confirmed_invoice_ids(attachment_id, ports=ports, catalogue_invoice_ids=frozenset(invoices.invoices))
    if disposition == "detach" and confirmed and current.invoice_id not in confirmed:
        # The document was confirmed into a canonical invoice. Kept as an
        # ordinary document it still leads there; detached outright, the movement
        # would lose its only tie to the invoice its own document became.
        raise PurchaseEvidenceReleaseRefusedError(
            PurchaseEvidenceReleaseCause.EVIDENCE_CONFIRMED_INTO_INVOICE, invoice_ids=confirmed
        )
    return _ReleasePlan(attachment_id=attachment_id)


def _confirmed_invoice_ids(
    attachment_id: str,
    *,
    ports: LedgerActionPorts,
    catalogue_invoice_ids: frozenset[str],
) -> tuple[str, ...]:
    """Return the catalogue invoices this evidence's document was confirmed into."""
    try:
        manifest = ports.attachment_store.load_manifest(attachment_id)
    except AttachmentNotFoundError:
        return ()
    return tuple(invoice_id for invoice_id in manifest.linked_invoice_ids if invoice_id in catalogue_invoice_ids)


def _release_command(
    current: Transaction,
    *,
    bucket_id: str,
    plan: _ReleasePlan,
    disposition: PurchaseEvidenceDisposition,
    actor: str,
    source_command: str,
) -> ManualLedgerTransactionCommand:
    """Return the stored row's command with the slot cleared, and its document kept when asked.

    The patch tells an explicitly set ``None`` from an omitted field, so naming
    both evidence fields clears the slot and states the attachments in full.
    """
    attachment_ids = current.attachment_ids
    if disposition == "keep_as_document" and plan.attachment_id is not None:
        attachment_ids = merge_identifier_tuple(current.attachment_ids, (plan.attachment_id,))
    return command_from_patch(
        bucket_id=bucket_id,
        current=current,
        patch=ManualLedgerTransactionPatch.model_validate(
            {"purchase_invoice_evidence_id": None, "attachment_ids": attachment_ids}
        ),
        actor=actor,
        source_command=source_command,
    )
