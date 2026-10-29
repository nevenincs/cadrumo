"""Manual ledger transaction services and read projections.

The services build :class:`~cadrumo.domain.transactions.models.Transaction` records from
:class:`~cadrumo.application.ledger.models.ManualLedgerTransactionCommand`, persist them
in a loaded :class:`TransactionCatalogue`, append bucket events, and return
:class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult` values.
Evidence paths validate purchase-invoice, attachment, and
:class:`~cadrumo.domain.usage_ratios.model.UsageRatioProfile` references before
persistence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ...core.hashing import content_hash_hex

if TYPE_CHECKING:
    from ..invoices.transaction_linking import InvoiceTransactionLinkResult

from ...core.aggregation import BindingSourceKind
from ...core.decimal.formatting import format_decimal
from ...core.external_constants import CLASSIFIED_BY_MANUAL
from ...domain.attachments.protocols import AttachmentStoreProtocol as _AttachmentStoreProtocol
from ...domain.attachments.service import link_attachment_transaction
from ...domain.buckets.event import BucketEvent, BucketEventType
from ...domain.buckets.event_repository import bucket_event_history_write
from ...domain.calculations.registry.iva_category_catalogue import require_iva_category
from ...domain.calculations.registry.iva_deduction_catalogue import invoice_evidence_authority
from ...domain.currency.service import CurrencyNormalizationService
from ...domain.invoices.errors import InvoiceLinkError
from ...domain.iva.deduction_facts import IvaDeductionClassificationProvenance, required_deduction_evidence_authority
from ...domain.transactions.classification_origin import (
    ClassificationOrigin,
    with_classification_origin,
    written_classification_origin,
)
from ...domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.lineage_models import (
    TransactionEditLineageEntry,
    TransactionEvidenceProvenanceEntry,
    TransactionLifecycleLineageEntry,
)
from ...domain.transactions.models import (
    Transaction,
    TransactionCatalogue,
    derive_import_fingerprint,
)
from ...domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..operations.execution_actor import actor_label_is_automation
from .action_ports import LedgerActionPorts
from .actions_common import (
    build_ledger_bucket_event,
    build_manual_ledger_result,
    command_matches_current,
    normalise_timestamp,
    optional_decimal,
    require_actor,
    require_source_command,
    require_transaction,
    resolve_attachment_store,
    resolve_bucket_event_repository,
    resolve_invoice_repository,
    resolve_revision_guarded_transaction_repository,
    resolve_transaction_repository,
    save_transaction_catalogue_and_events,
    upsert_transaction,
    verify_evidence_references,
    verify_usage_ratio_reference,
)
from .actions_import import apply_fx_conversion as _apply_fx_conversion
from .evidence import PurchaseInvoiceEvidence
from .models import (
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionResult,
)
from .protocols import (
    BucketEventHistoryCoCommitWriterProtocol,
    RevisionGuardedTransactionCatalogueCoCommitWriterProtocol,
    TransactionCatalogueCoCommitWriterProtocol,
)

_MANUAL_PROVIDER_NAME = "manual-ledger"

#: Optional command fields the manual source hash folds in only when they carry a
#: value. That hash is recorded on every manual row's provenance and addresses
#: every keyless row through its provider id, so it is part of the row's
#: identity. A field added to the command after rows were first written would
#: otherwise enter the hash as ``null`` for every command that never uses it,
#: re-addressing ordinary movements whose content had not changed. Each field
#: listed here must default to ``None``, so omitting it when absent loses nothing
#: a present value would say.
_SOURCE_HASH_FIELDS_OMITTED_WHEN_ABSENT = frozenset({"investment_asset_id", "own_account_id"})


@dataclass(frozen=True, slots=True)
class PreparedManualTransaction:
    """A manual add that passed every refusal and has not written anything yet."""

    command: ManualLedgerTransactionCommand
    repository: TransactionCatalogueCoCommitWriterProtocol
    event_repository: BucketEventHistoryCoCommitWriterProtocol
    catalogue: TransactionCatalogue
    catalogue_revision: str | None
    transaction: Transaction
    event: BucketEvent


def prepare_manual_transaction(
    command: ManualLedgerTransactionCommand,
    *,
    ports: LedgerActionPorts,
    occurred_at: datetime | None = None,
    currency_normalizer: CurrencyNormalizationService | None = None,
    require_revision_guard: bool = False,
) -> PreparedManualTransaction | ManualLedgerTransactionResult:
    """Run every refusal of a manual add without writing, so a caller can tell a refusal from a write.

    Building the domain row is where its own invariants refuse (an IVA rate
    given as a percentage, a gross that is not base plus cuota), so a refusal
    raised here has provably written nothing. An idempotent retry of a stored
    row returns its unchanged result instead of a preparation.
    """
    now = normalise_timestamp(occurred_at)
    repository = resolve_transaction_repository(bucket_id=command.bucket_id, repository=ports.transaction_repository)
    event_repository = resolve_bucket_event_repository(
        bucket_id=command.bucket_id, repository=ports.bucket_event_repository
    )
    if require_revision_guard:
        guarded_repository = resolve_revision_guarded_transaction_repository(
            bucket_id=command.bucket_id,
            repository=repository,
        )
        catalogue, catalogue_revision = guarded_repository.load_revisioned()
    elif isinstance(repository, RevisionGuardedTransactionCatalogueCoCommitWriterProtocol):
        catalogue, catalogue_revision = repository.load_revisioned()
    else:
        catalogue = repository.load()
        catalogue_revision = None
    if command.idempotency_key is not None:
        # The idempotency key is authoritative for row identity: a keyed row
        # carries the clock-free provider id `manual:{bucket}:{key}` on
        # raw.provider_transaction_id. Scan by that provider id (NOT the
        # content-folding catalogue id from derive_transaction_id) so the same
        # key always names the same logical add regardless of which content
        # fields it carries.
        provider_id = _provider_transaction_id(command, occurred_at=now)
        existing = next(
            (row for row in catalogue.values() if row.raw.provider_transaction_id == provider_id),
            None,
        )
        if existing is not None:
            if command_matches_current(command, existing):
                # Guarded idempotent retry: same idempotency key, identical content.
                # Return the stored row unchanged with no new event (an empty
                # bucket_event_ids tuple is the structural no-op signal), mirroring
                # the create_work_unit existing-record contract.
                return build_manual_ledger_result(command.bucket_id, existing, ())
            raise TransactionValidationError(
                f"ledger add idempotency-key {command.idempotency_key!r} already names a stored "
                "transaction with different content; use a new idempotency key for a different "
                "movement, or omit --idempotency-key to append a deliberate duplicate",
                translated_message="application.ledger.errors.idempotency_key_conflict",
            )
    require_declared_iva_category(command, ports=ports)
    transaction_base = transaction_from_command(
        command,
        occurred_at=now,
        currency_normalizer=currency_normalizer,
        evidence_records=ports.purchase_invoice_evidence_records,
    )
    verify_evidence_references(
        command,
        transaction_id=transaction_base.transaction_id,
        invoice_repository=ports.invoice_repository,
        attachment_store=ports.attachment_store,
        evidence_records=ports.purchase_invoice_evidence_records,
    )
    verify_usage_ratio_reference(command, usage_ratio_profile=ports.usage_ratio_profile, operation=ports.operation)
    event = build_ledger_bucket_event(
        bucket_id=command.bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_CREATED,
        occurred_at=now,
        actor=command.actor,
        object_id=transaction_base.transaction_id,
        payload=event_payload(command),
    )
    transaction = transaction_from_command(
        command,
        occurred_at=now,
        bucket_event_id=event.event_id,
        currency_normalizer=currency_normalizer,
        evidence_records=ports.purchase_invoice_evidence_records,
    )
    return PreparedManualTransaction(
        command=command,
        repository=repository,
        event_repository=event_repository,
        catalogue=catalogue,
        catalogue_revision=catalogue_revision,
        transaction=transaction,
        event=event,
    )


def commit_manual_transaction(
    prepared: PreparedManualTransaction,
    *,
    ports: LedgerActionPorts,
) -> ManualLedgerTransactionResult:
    """Write a prepared manual add: the row and its event co-commit, then the attachment back-references."""
    transaction = prepared.transaction
    save_transaction_catalogue_and_events(
        transaction_repository=prepared.repository,
        event_repository=prepared.event_repository,
        catalogue=upsert_transaction(prepared.catalogue, transaction),
        events=(prepared.event,),
        expected_catalogue_revision=prepared.catalogue_revision,
    )
    record_attachment_back_references(transaction, attachment_store=ports.attachment_store)
    return build_manual_ledger_result(prepared.command.bucket_id, transaction, (prepared.event.event_id,))


def link_manual_transaction_invoice(
    *,
    bucket_id: str,
    transaction_id: str,
    invoice_id: str,
    actor: str = "operator",
    source_command: str = "aeat app ledger link",
    ports: LedgerActionPorts,
    occurred_at: datetime | None = None,
) -> InvoiceTransactionLinkResult:
    """Establish an atomic invoice-only relationship for one ledger transaction.

    This is the sole invoice-linkage writer. It resolves the transaction,
    enforces the invoice's missing and cross-bucket policy up front, then
    delegates the bidirectional catalogue mutation and persistence to
    :func:`~cadrumo.application.invoices.transaction_linking.link_invoice_transaction_repositories`.
    It never touches purchase evidence or attachments: evidence mutation is
    reserved for :func:`attach_manual_transaction_evidence`. Every rejection
    fires before any catalogue write, so a refused link leaves the transaction,
    invoice catalogue, and event history unchanged. The accepted path is
    equally all-or-nothing: the two catalogues and the
    :attr:`~cadrumo.domain.buckets.event.BucketEventType.LEDGER_TRANSACTION_INVOICE_LINKED`
    audit event are co-committed in one secure-object batch, so no failure can
    leave one side citing the other without being cited back, and no event can
    record a link that did not land.

    Returns an
    :class:`~cadrumo.application.invoices.transaction_linking.InvoiceTransactionLinkResult`.
    """
    from ..invoices.transaction_linking import link_invoice_transaction_repositories

    trimmed_actor = require_actor(actor, operation="ledger invoice linkage")
    trimmed_source_command = require_source_command(source_command, operation="ledger invoice linkage")
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=ports.transaction_repository)
    current = require_transaction(repository.load(), transaction_id)
    invoices_repo = resolve_invoice_repository(bucket_id=bucket_id, repository=ports.invoice_repository)
    invoice_record = invoices_repo.load().get(invoice_id)
    if invoice_record is None:
        raise InvoiceLinkError(
            "invoice_id not found in the active profile invoice catalogue",
            context={"invoice_id": invoice_id, "bucket_id": bucket_id},
        )
    if invoice_record.bucket_id not in (None, bucket_id):
        raise InvoiceLinkError(
            "invoice belongs to a different bucket than the active profile",
            context={
                "invoice_id": invoice_id,
                "command_bucket_id": bucket_id,
                "invoice_bucket_id": invoice_record.bucket_id or "",
            },
        )
    event_repository = resolve_bucket_event_repository(bucket_id=bucket_id, repository=ports.bucket_event_repository)
    event = build_ledger_bucket_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_INVOICE_LINKED,
        occurred_at=normalise_timestamp(occurred_at),
        actor=trimmed_actor,
        object_id=current.transaction_id,
        # Identifiers and the operator's verb only: invoice content (counterparty,
        # totals, tax id) never enters the event history.
        payload={
            "invoice_id": invoice_id,
            "source_command": trimmed_source_command,
            "mutation_kind": "invoice_linkage",
        },
    )
    # The event write rides the SAME batch as the two catalogues, so a crash
    # cannot record a linkage that did not land, nor land one silently.
    result = link_invoice_transaction_repositories(
        bucket_id=bucket_id,
        invoice_id=invoice_id,
        transaction_id=current.transaction_id,
        invoice_repository=invoices_repo,
        transaction_repository=repository,
        extra_writes=(bucket_event_history_write(event_repository, (event,)),),
    )
    return result.model_copy(update={"bucket_event_ids": (event.event_id,)})


def record_attachment_back_references(
    transaction: Transaction,
    *,
    attachment_store: _AttachmentStoreProtocol | None,
    attachment_ids: tuple[str, ...] | None = None,
) -> None:
    """Record the transaction on selected attachment manifests it cites.

    The transaction side of the link is written by the catalogue save above.
    Without this, the manifest side stayed empty, so
    :meth:`~domain.attachments.protocols.AttachmentStoreProtocol.iter_manifests` filtered by
    ``linked_to=<transaction_id>`` could not discover an attachment the
    transaction itself cites -- the manifest models the link and the evidence
    workflow documents the provenance as bidirectional.

    Runs after the transaction is durably persisted, so a failure here can only
    leave the manifest side behind, never a manifest pointing at a transaction
    that was never written. :func:`~domain.attachments.service.link_attachment_transaction`
    is idempotent, so a re-attach re-converges the pair rather than duplicating
    the reference.

    ``attachment_ids`` lets an update reconcile only newly introduced evidence
    after its transaction/event co-commit. Creation omits it and links every
    declared attachment.
    """
    target_attachment_ids = transaction.attachment_ids if attachment_ids is None else attachment_ids
    if not target_attachment_ids:
        return
    store = resolve_attachment_store(attachment_store)
    for attachment_id in target_attachment_ids:
        link_attachment_transaction(
            store,
            attachment_id=attachment_id,
            transaction_id=transaction.transaction_id,
        )


def written_origin(command: ManualLedgerTransactionCommand) -> ClassificationOrigin:
    """Return whose decision a classification written by ``command`` is."""
    return written_classification_origin(
        by_automation=actor_label_is_automation(command.actor),
        classified_by=command.classified_by_override or CLASSIFIED_BY_MANUAL,
    )


def event_payload(command: ManualLedgerTransactionCommand) -> dict[str, str]:
    """Build the recorded manual command event payload."""
    payload = {
        "source_command": command.source_command,
        "direction": command.direction.value,
        "amount": format_decimal(command.amount),
        "currency": command.currency,
    }
    if command.business_pct is not None:
        payload["business_pct"] = format_decimal(command.business_pct)
    if command.usage_ratio_id is not None:
        payload["usage_ratio_id"] = command.usage_ratio_id
    return payload


def _invoice_evidence_provenance(
    command: ManualLedgerTransactionCommand,
    *,
    evidence_records: tuple[PurchaseInvoiceEvidence, ...],
) -> IvaDeductionClassificationProvenance | None:
    """Derive the deduction's evidence pointer from its linked purchase invoice.

    The operator declares WHICH deduction this is (the taxonomy is documented
    as non-inferable, so ``deduction_fact_kind`` is carried, never guessed);
    the evidence pointer behind it is not a judgement and must not be typed by
    hand. It is read from the registered evidence record the row already links,
    whose content-addressed ``attachment_id`` is the immutable digest the
    provenance contract asks for.

    Only the invoice-evidence authority is derivable here. A customs
    declaration, an intra-EU self-assessment, a REAGP receipt or a
    bienes-inversion regularisation is established by a record this link cannot
    see, so those kinds resolve to ``None`` and refuse downstream rather than
    being stamped with an invoice digest that did not establish them.
    """
    if command.deduction_fact_kind is None or command.purchase_invoice_evidence_id is None:
        return None
    invoice_authority = invoice_evidence_authority()
    if required_deduction_evidence_authority(command.deduction_fact_kind) != invoice_authority:
        return None
    evidence_id = command.purchase_invoice_evidence_id
    record = next(
        (candidate for candidate in evidence_records if candidate.evidence_id == evidence_id),
        None,
    )
    if record is None:
        return None
    return IvaDeductionClassificationProvenance(
        authority=invoice_authority,
        source_locator=record.evidence_id,
        evidence_digest=record.attachment_id,
    )


def require_declared_iva_category(
    command: ManualLedgerTransactionCommand,
    *,
    ports: LedgerActionPorts,
) -> None:
    """Refuse a non-canonical IVA category before a ledger write is built."""
    if command.iva_category is not None:
        require_iva_category(
            command.iva_category,
            effective_date=command.booked_date,
            authority=ports.operation,
        )


def transaction_from_command(
    command: ManualLedgerTransactionCommand,
    *,
    occurred_at: datetime,
    provider_transaction_id: str | None = None,
    bucket_event_id: str | None = None,
    created_by: str | None = None,
    created_source_command: str | None = None,
    created_event_id: str | None = None,
    existing_evidence_provenance: tuple[TransactionEvidenceProvenanceEntry, ...] = (),
    existing_edit_lineage: tuple[TransactionEditLineageEntry, ...] = (),
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
    lifecycle_lineage: tuple[TransactionLifecycleLineageEntry, ...] = (),
    edit_lineage_entry: TransactionEditLineageEntry | None = None,
    evidence_event_ids: Mapping[tuple[str, str], str] | None = None,
    import_fingerprint: str | None = None,
    created_at: datetime | None = None,
    modified_at: datetime | None = None,
    currency_normalizer: CurrencyNormalizationService | None = None,
    evidence_records: tuple[PurchaseInvoiceEvidence, ...] = (),
    classification_predecessor: Transaction | None = None,
    classification_decided: bool = False,
) -> Transaction:
    """Build a transaction from a manual command and its provenance."""
    raw = RawTransaction(
        provider_transaction_id=provider_transaction_id or _provider_transaction_id(command, occurred_at=occurred_at),
        booked_date=command.booked_date,
        value_date=command.value_date,
        amount=command.amount,
        currency=command.currency,
        counterparty=command.counterparty,
        description=command.description,
        provenance=RawProvenance(
            source_path=Path.cwd() / ".cadrumo-manual-ledger",
            source_sha256=_source_sha256(command, occurred_at=occurred_at),
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=occurred_at,
            provider_name=_MANUAL_PROVIDER_NAME,
        ),
        raw_fields=_raw_fields(command),
    )
    payload: dict[str, object] = {
        "raw": raw,
        "direction": command.direction,
        "business_classification": command.business_classification,
        "business_pct": command.business_pct,
        "category_id": command.category_id,
        "taxable_base": command.taxable_base,
        "iva_rate": command.iva_rate,
        "iva_amount": command.iva_amount,
        "recargo_amount": command.recargo_amount,
        "irpf_category": command.irpf_category,
        "m210_income_classification": command.m210_income_classification,
        "usage_ratio_id": command.usage_ratio_id,
        "prorrata_reference": command.prorrata_reference,
        "art_104_tres_exclusion": command.art_104_tres_exclusion,
        "input_classification": command.input_classification,
        "prorrata_sector_id": command.prorrata_sector_id,
        "purchase_invoice_evidence_id": command.purchase_invoice_evidence_id,
        "attachment_ids": command.attachment_ids,
        "created_by": created_by or command.actor,
        "source_command": created_source_command or command.source_command,
        "created_event_id": created_event_id or bucket_event_id,
        "lifecycle_state": lifecycle_state,
        "lifecycle_lineage": lifecycle_lineage,
        "evidence_provenance": _evidence_provenance(
            command,
            occurred_at=occurred_at,
            bucket_event_id=bucket_event_id,
            existing=existing_evidence_provenance,
            evidence_event_ids=evidence_event_ids or {},
        ),
        "edit_lineage": (
            (*existing_edit_lineage, edit_lineage_entry) if edit_lineage_entry is not None else existing_edit_lineage
        ),
        # Stamp the content-only movement fingerprint on manual rows when the
        # caller does not carry one forward (every create path). Edits pass the
        # stored fingerprint verbatim. This lets a manually-entered movement
        # participate in the import-path duplicate/likely-duplicate advisory.
        "import_fingerprint": (
            import_fingerprint
            if import_fingerprint is not None
            else derive_import_fingerprint(raw, direction=command.direction, own_account_id=command.own_account_id)
        ),
        "notes": command.notes,
        "iva_category": command.iva_category,
        "deduction_fact_kind": command.deduction_fact_kind,
        "deduction_provenance": _invoice_evidence_provenance(command, evidence_records=evidence_records),
        "investment_asset_id": command.investment_asset_id,
        "counterparty_country": command.counterparty_country,
        "counterparty_identification_state": command.counterparty_identification_state,
        "source_jurisdiction": command.source_jurisdiction,
        "group_label": command.group_label,
        "own_account_id": command.own_account_id,
        # D6: created_at is stamped once (defaults to occurred_at on first
        # construction) and carried verbatim through edits; modified_at
        # re-stamps to occurred_at on every mutating construction.
        "created_at": created_at if created_at is not None else occurred_at,
        "modified_at": modified_at if modified_at is not None else occurred_at,
    }
    # Convert a foreign-currency manual row at entry, exactly as the file-import
    # path does. Without this the row persists with no value_in_eur and every
    # aggregation gate withholds it, so a manually-entered foreign invoice never
    # reaches the modelo at all.
    payload.update(_fx_conversion_fields(raw, currency_normalizer))
    payload.update(_classification_fields(command, occurred_at=occurred_at))
    # The stamp above is rewritten by every write to a classified row. Whose
    # decision the classification is changes only when this write changes it.
    return with_classification_origin(
        Transaction.model_validate(payload),
        replaces=classification_predecessor,
        written=written_origin(command),
        decided=classification_decided,
    )


def _fx_conversion_fields(
    raw: RawTransaction,
    currency_normalizer: CurrencyNormalizationService | None,
) -> dict[str, object]:
    """Project the converted foreign-currency fields, empty when no rate resolves."""
    fx_rate, value_in_eur, _rate_source, _rate_date_iso = _apply_fx_conversion(raw, currency_normalizer)
    if fx_rate is None or value_in_eur is None:
        return {}
    return {"fx_rate": fx_rate, "value_in_eur": value_in_eur}


def carry_forward_invoice_link(current: Transaction, replacement: Transaction) -> Transaction:
    """Keep an edited row's invoice link.

    The edit command carries no invoice reference, so the rebuilt row came back
    unlinked and every classify or update erased the transaction half of a
    link the invoice catalogue still held. Linking and unlinking are their own
    verbs; an edit never changes the association.
    """
    if replacement.invoice_id == current.invoice_id:
        return replacement
    return replacement.model_copy(update={"invoice_id": current.invoice_id})


def carry_forward_fx(current: Transaction, replacement: Transaction) -> Transaction:
    """Keep an edited row's euro value when the money behind it did not change.

    An edit rebuilds the row from the command, and the rebuild re-derives the
    foreign-currency conversion through :func:`_fx_conversion_fields`. That
    needs a :class:`CurrencyNormalizationService`, and no caller of
    :func:`update_manual_transaction` has one — so the projection returns an
    empty mapping and the replacement takes the model default of ``None``.

    The consequence is not a missing display field. ``summarize_manual_transactions``
    falls back to ``abs(raw.amount)`` when ``value_in_eur`` is absent, so a
    1000 USD row that had been converted at import is counted as 1000 EUR from
    the first unrelated edit onwards — a description fix silently restates the
    amount.

    Carried only when the amount AND the currency are untouched. If either
    moved, the stored euro value describes a different sum and reusing it would
    replace a lost figure with a wrong one; absence is the honest answer there,
    and it is what the row already gets today.
    """
    if replacement.value_in_eur is not None or current.value_in_eur is None:
        return replacement
    if replacement.raw.amount != current.raw.amount or replacement.raw.currency != current.raw.currency:
        return replacement
    return replacement.model_copy(update={"fx_rate": current.fx_rate, "value_in_eur": current.value_in_eur})


def _classification_fields(
    command: ManualLedgerTransactionCommand,
    *,
    occurred_at: datetime,
) -> dict[str, object]:
    """Project the classification stamp, empty while the row is unprocessed."""
    if command.business_classification is BusinessClassification.NOT_YET_PROCESSED:
        return {}
    return {
        "classified_at": occurred_at,
        "classified_by": command.classified_by_override or CLASSIFIED_BY_MANUAL,
        # #231: the operator's free-text rationale (the manual `classify
        # --reason` value, threaded through as `command.notes`) is the
        # real "why" behind the decision and takes precedence; the
        # invoking command name remains the fallback for classification
        # paths that carry no operator-supplied reason (e.g. bulk
        # `--file` rows with no `notes` column).
        "classification_reason": command.notes or command.source_command,
        "classification_confidence": Decimal("1"),
    }


def _evidence_provenance(
    command: ManualLedgerTransactionCommand,
    *,
    occurred_at: datetime,
    bucket_event_id: str | None,
    existing: tuple[TransactionEvidenceProvenanceEntry, ...],
    evidence_event_ids: Mapping[tuple[str, str], str],
) -> tuple[TransactionEvidenceProvenanceEntry, ...]:
    wanted: set[tuple[Literal["purchase_invoice_evidence", "attachment"], str]] = {
        ("attachment", attachment_id) for attachment_id in command.attachment_ids
    }
    if command.purchase_invoice_evidence_id is not None:
        wanted.add(("purchase_invoice_evidence", command.purchase_invoice_evidence_id))
    retained = tuple(entry for entry in existing if (entry.evidence_kind, entry.evidence_id) in wanted)
    seen = {(entry.evidence_kind, entry.evidence_id) for entry in retained}
    created: list[TransactionEvidenceProvenanceEntry] = []
    for evidence_kind, evidence_id in sorted(wanted - seen):
        typed_kind: Literal["purchase_invoice_evidence", "attachment"] = (
            "purchase_invoice_evidence" if evidence_kind == "purchase_invoice_evidence" else "attachment"
        )
        evidence_event_id = evidence_event_ids.get((typed_kind, evidence_id), bucket_event_id)
        created.append(
            TransactionEvidenceProvenanceEntry(
                evidence_kind=typed_kind,
                evidence_id=evidence_id,
                actor=command.actor,
                source_command=command.source_command,
                linked_at=occurred_at,
                bucket_event_id=evidence_event_id,
            ),
        )
    return (*retained, *created)


def _provider_transaction_id(command: ManualLedgerTransactionCommand, *, occurred_at: datetime) -> str:
    if command.idempotency_key is not None:
        return f"manual:{command.bucket_id}:{command.idempotency_key}"
    return f"manual:{command.bucket_id}:{occurred_at.isoformat()}:{_source_sha256(command, occurred_at=occurred_at)}"


def _source_sha256(command: ManualLedgerTransactionCommand, *, occurred_at: datetime) -> str:
    payload = {
        name: value
        for name, value in command.model_dump(mode="json").items()
        if value is not None or name not in _SOURCE_HASH_FIELDS_OMITTED_WHEN_ABSENT
    }
    payload["occurred_at"] = occurred_at.isoformat()
    return content_hash_hex(payload)


def _raw_field_values(command: ManualLedgerTransactionCommand) -> dict[str, str]:
    """Build raw fields that are present for every manual-ledger row."""
    return {
        "source_kind": BindingSourceKind.LEDGER_TRANSACTION,
        "source_command": command.source_command,
        "actor": command.actor,
        "business_classification": command.business_classification.value,
        "direction": command.direction.value,
        "taxable_base": optional_decimal(command.taxable_base),
        "iva_rate": optional_decimal(command.iva_rate),
        "iva_amount": optional_decimal(command.iva_amount),
        "recargo_amount": optional_decimal(command.recargo_amount),
        "irpf_category": command.irpf_category or "",
        "usage_ratio_id": command.usage_ratio_id or "",
        "prorrata_reference": command.prorrata_reference or "",
        "art_104_tres_exclusion": command.art_104_tres_exclusion.value
        if (command.art_104_tres_exclusion is not None and command.art_104_tres_exclusion)
        else "",
        "input_classification": command.input_classification.value
        if (command.input_classification is not None and command.input_classification)
        else "",
        "prorrata_sector_id": command.prorrata_sector_id or "",
        "purchase_invoice_evidence_id": command.purchase_invoice_evidence_id or "",
        "attachment_ids": ",".join(command.attachment_ids),
    }


def _optional_raw_field_values(command: ManualLedgerTransactionCommand) -> dict[str, str]:
    """Build optional raw fields while retaining their historical insertion order."""
    values: dict[str, str] = {}
    if command.business_pct is not None:
        values["business_pct"] = format_decimal(command.business_pct)
    if command.category_id is not None:
        values["category_id"] = command.category_id
    if command.idempotency_key is not None:
        values["idempotency_key"] = command.idempotency_key
    return values


def _raw_fields(command: ManualLedgerTransactionCommand) -> Mapping[str, str]:
    """Build the canonical raw-field projection for a manual transaction."""
    return {**_raw_field_values(command), **_optional_raw_field_values(command)}
