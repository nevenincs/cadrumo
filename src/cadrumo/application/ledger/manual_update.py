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
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ...domain.currency.service import CurrencyNormalizationService
from ...domain.transactions.classification_origin import (
    CLASSIFICATION_DECISION_FIELDS,
    resolved_classification_origin,
    with_classification_origin,
)
from ...domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.lineage_models import (
    TransactionEditLineageEntry,
)
from ...domain.transactions.models import (
    Transaction,
    TransactionCatalogue,
)
from ..aggregation.ledger_filing_snapshot import row_fingerprint
from .action_ports import LedgerActionPorts
from .actions_common import (
    EventSpec,
    blocking_modelo_references,
    build_ledger_bucket_event,
    build_manual_ledger_result,
    command_changes_no_ledger_value,
    command_matches_current,
    derive_evidence_event_ids,
    is_evidence_only_command,
    ledger_values_differing_from_stored,
    merge_identifier_tuple,
    mutation_signature,
    normalise_attachment_patch_ids,
    normalise_timestamp,
    optional_decimal,
    optional_patched,
    primary_lineage_event_id,
    raise_finalized_modelo_blocked,
    replace_transaction,
    require_actor,
    require_source_command,
    require_transaction,
    required_patched,
    resolve_bucket_event_repository,
    resolve_transaction_repository,
    save_transaction_catalogue_and_events,
    transaction_modelo_source_ids,
    verify_evidence_references,
    verify_usage_ratio_reference,
)
from .actions_manual import (
    carry_forward_fx,
    carry_forward_invoice_link,
    event_payload,
    record_attachment_back_references,
    require_declared_iva_category,
    transaction_from_command,
    written_origin,
)
from .models import (
    LedgerRemovalBlocker,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)

# Evidence catalogue and provenance are mutated ONLY through the attach authority
# (`attach_manual_transaction_evidence`). The generic manual-field update door


def attach_manual_transaction_evidence(
    *,
    bucket_id: str,
    transaction_id: str,
    actor: str,
    purchase_invoice_evidence_id: str | None = None,
    attachment_ids: tuple[str, ...] = (),
    source_command: str = "aeat app ledger attach",
    ports: LedgerActionPorts,
    occurred_at: datetime | None = None,
    expected_current: Transaction | None = None,
) -> ManualLedgerTransactionResult:
    """Attach purchase evidence or supplementary attachments to one ledger transaction.

    ``expected_current`` pins an explicitly supplied opened row through the
    existing atomic transaction/event replacement guard.

    Returns a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`.
    """
    trimmed_actor = require_actor(actor, operation="ledger evidence attachment")
    trimmed_source_command = require_source_command(source_command, operation="ledger evidence attachment")
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=ports.transaction_repository)
    catalogue = repository.load()
    current = require_transaction(catalogue, transaction_id)
    normalized_purchase_evidence_id = (purchase_invoice_evidence_id or "").strip() or None
    normalized_attachment_ids = normalise_attachment_patch_ids(attachment_ids)
    if normalized_purchase_evidence_id is None and not normalized_attachment_ids:
        raise TransactionValidationError(
            "ledger evidence attachment requires purchase evidence or attachment ids",
            translated_message="application.ledger.errors.evidence_attachment_requires_ids",
        )
    if (
        normalized_purchase_evidence_id is not None
        and current.purchase_invoice_evidence_id is not None
        and current.purchase_invoice_evidence_id != normalized_purchase_evidence_id
    ):
        raise TransactionValidationError(
            "purchase invoice evidence is immutable once attached; remove the ledger "
            "transaction and re-add it with the correct evidence",
            translated_message="application.ledger.errors.purchase_evidence_already_set",
        )
    patch_values: dict[str, object] = {}
    if normalized_purchase_evidence_id is not None:
        patch_values["purchase_invoice_evidence_id"] = normalized_purchase_evidence_id
    if normalized_attachment_ids:
        patch_values["attachment_ids"] = merge_identifier_tuple(current.attachment_ids, normalized_attachment_ids)
    return update_manual_transaction_fields(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch.model_validate(patch_values),
        actor=trimmed_actor,
        source_command=trimmed_source_command,
        ports=ports,
        occurred_at=occurred_at,
        catalogue=catalogue,
        expected_current=expected_current,
        _evidence_authority=True,
    )


def detach_manual_transaction_attachments(
    *,
    bucket_id: str,
    transaction_id: str,
    actor: str,
    attachment_ids: tuple[str, ...],
    source_command: str = "aeat app ledger detach",
    ports: LedgerActionPorts,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Detach named supplementary attachments from one ledger transaction.

    The inverse of :func:`attach_manual_transaction_evidence` for the axis that
    can express it. ``attachment_ids`` is a whole-tuple patch, so the remaining
    ids are computed here and written as the new set -- the attach path merges
    into the same field, and both go through the one
    :func:`update_manual_transaction_fields` writer rather than editing the
    catalogue directly.

    PURCHASE EVIDENCE IS DELIBERATELY OUT OF SCOPE and refuses in
    :func:`attach_manual_transaction_evidence` instead of being cleared here.
    ``ManualLedgerTransactionPatch`` cannot express the difference between
    "clear this field" and "leave it unchanged": ``purchase_invoice_evidence_id``
    is an optional text field whose validator normalises an empty string to
    ``None``, which is also the patch's own "no change" value. Clearing it needs
    a sentinel the patch model does not have, and inventing one here -- rather
    than deciding it once for every optional field on that model -- would put a
    second clearing convention into the ledger command shape.

    Detaching does NOT delete the attachment's bytes. The attachment is a
    content-addressed secure object that other transactions and finalized
    revisions may reference; this removes one transaction's reference to it, and
    the stale-revision notices the caller already surfaces report where a
    finalized revision used what is now detached.

    Returns a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`.
    """
    trimmed_actor = require_actor(actor, operation="ledger evidence detachment")
    trimmed_source_command = require_source_command(source_command, operation="ledger evidence detachment")
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=ports.transaction_repository)
    catalogue = repository.load()
    current = require_transaction(catalogue, transaction_id)
    requested = normalise_attachment_patch_ids(attachment_ids)
    if not requested:
        raise TransactionValidationError(
            "ledger evidence detachment requires at least one attachment id",
            translated_message="application.ledger.errors.evidence_detachment_requires_ids",
        )
    attached = tuple(current.attachment_ids)
    unknown = tuple(identifier for identifier in requested if identifier not in attached)
    if unknown:
        raise TransactionValidationError(
            f"ledger transaction does not carry attachment(s) {unknown!r}",
            translated_message="application.ledger.errors.evidence_detachment_unknown_attachment",
            context={"attachment_ids": ", ".join(unknown)},
        )
    remaining = tuple(identifier for identifier in attached if identifier not in set(requested))
    return update_manual_transaction_fields(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch.model_validate({"attachment_ids": remaining}),
        actor=trimmed_actor,
        source_command=trimmed_source_command,
        ports=ports,
        occurred_at=occurred_at,
        catalogue=catalogue,
        _evidence_authority=True,
    )


def update_manual_transaction(
    *,
    transaction_id: str,
    command: ManualLedgerTransactionCommand,
    ports: LedgerActionPorts,
    occurred_at: datetime | None = None,
    catalogue: TransactionCatalogue | None = None,
    expected_current: Transaction | None = None,
    decides_classification: bool = False,
    _evidence_authority: bool = False,
) -> ManualLedgerTransactionResult:
    """Replace one manual ledger transaction from a validated command payload.

    The replacement is built from
    :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionCommand` and saved
    as a new :class:`~cadrumo.domain.transactions.models.Transaction` revision.

    ``decides_classification`` says the caller set a tax-bearing fact of the
    row, whether or not its value moved. A person who restates what a rule, a
    model or an automation gave the row has accepted it: the row becomes theirs,
    and that alone is a change this service writes and records.

    ``_evidence_authority`` is a private flag threaded only by the evidence
    attach authority (:func:`attach_manual_transaction_evidence`) and the
    evidence-driven split inheritance. When it is :data:`False` (every generic
    manual-field update) the command MUST NOT change
    ``purchase_invoice_evidence_id`` or ``attachment_ids``; evidence catalogue and
    provenance mutation are reserved for ``aeat app ledger attach``.

    ``catalogue`` is the snapshot a caller in the same action has
    already decrypted; nothing writes between that load and this replacement,
    so decrypting the whole catalogue again would only repeat the read.

    When supplied, ``expected_current`` is the immutable transaction snapshot
    the caller opened for editing. It must still equal the loaded record before
    this service admits the replacement. The persistence adapter retains its
    own write-time concurrency guard.

    Returns a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`.

    Core types:
    :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
    """
    now = normalise_timestamp(occurred_at)
    repository = resolve_transaction_repository(bucket_id=command.bucket_id, repository=ports.transaction_repository)
    event_repository = resolve_bucket_event_repository(
        bucket_id=command.bucket_id, repository=ports.bucket_event_repository
    )
    if catalogue is None:
        catalogue = repository.load()
    current = require_transaction(catalogue, transaction_id)
    _require_expected_current_transaction(current=current, expected_current=expected_current)
    blockers, evidence_only = _manual_update_preconditions(
        current=current,
        command=command,
        ports=ports,
        transaction_id=transaction_id,
        evidence_authority=_evidence_authority,
    )
    prepared = prepare_manual_transaction_update(
        current=current,
        command=command,
        previous_transaction_id=transaction_id,
        now=now,
        ports=ports,
        decides_classification=decides_classification,
        finalized_blockers=blockers,
        evidence_only=evidence_only,
    )
    if prepared is None:
        raise TransactionValidationError(
            "manual ledger update must change at least one ledger field",
            context={"transaction_id": transaction_id},
        )
    replacement, events = prepared
    save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=replace_transaction(catalogue, old_transaction_id=transaction_id, replacement=replacement),
        events=events,
        expected_current=expected_current,
        replacement=replacement,
    )
    new_attachment_ids = tuple(
        attachment_id for attachment_id in replacement.attachment_ids if attachment_id not in current.attachment_ids
    )
    # Existing manifests were validated before the atomic catalogue/event commit.
    # Re-reading them after that commit would let an unrelated attachment-store
    # failure report this already-durable edit as unsuccessful.
    record_attachment_back_references(
        replacement,
        attachment_store=ports.attachment_store,
        attachment_ids=new_attachment_ids,
    )
    return build_manual_ledger_result(
        command.bucket_id,
        replacement,
        tuple(event.event_id for event in events),
        stale_finalized_revisions=blockers if evidence_only else (),
    )


def _manual_update_preconditions(
    *,
    current: Transaction,
    command: ManualLedgerTransactionCommand,
    ports: LedgerActionPorts,
    transaction_id: str,
    evidence_authority: bool,
) -> tuple[tuple[LedgerRemovalBlocker, ...], bool]:
    if current.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        raise TransactionValidationError(
            "only active ledger transactions can be edited; archived, stashed, and split-parent rows are immutable",
            context={
                "transaction_id": transaction_id,
                "lifecycle_state": current.lifecycle_state.value,
            },
        )
    if not evidence_authority and (
        command.purchase_invoice_evidence_id != current.purchase_invoice_evidence_id
        or command.attachment_ids != current.attachment_ids
    ):
        raise TransactionValidationError(
            "purchase evidence and attachments are managed only by `aeat app ledger attach`; "
            "a generic ledger transaction update must not change purchase_invoice_evidence_id or attachment_ids",
            context={"transaction_id": transaction_id},
        )
    blockers = blocking_modelo_references(
        bucket_id=command.bucket_id,
        transaction_ids=transaction_modelo_source_ids(current),
        work_unit_repository=ports.work_unit_repository,
        calculation_repository=ports.calculation_repository,
    )
    # An evidence-only attachment cannot disturb a finalized revision (stable
    # transaction id, unchanged row fingerprint, frozen bundled evidence), so it
    # is exempt from the write guard — otherwise the documented remedy for an
    # export evidence refusal would itself be blocked by the calculation that
    # raised it. The cited revisions are reported back as stale so the operator
    # is told to recalculate; the exemption never widens past evidence fields.
    # The guard itself is held where the replacement is built, because what
    # it protects is read from the replacement.
    return blockers, is_evidence_only_command(command, current)


def _require_expected_current_transaction(
    *,
    current: Transaction,
    expected_current: Transaction | None,
) -> None:
    """Refuse a detail edit whose opened transaction no longer matches storage."""
    if expected_current is not None and current != expected_current:
        raise TransactionValidationError(
            "transaction changed since it was opened; reopen it before editing",
            context={"transaction_id": current.transaction_id},
        )


def _changed_sealed_write(
    blockers: tuple[LedgerRemovalBlocker, ...],
    evidence_only: bool,
    command: ManualLedgerTransactionCommand,
    current: Transaction,
) -> bool:
    return bool(blockers) and not evidence_only and not command_changes_no_ledger_value(command, current)


def prepare_manual_transaction_update(
    *,
    current: Transaction,
    command: ManualLedgerTransactionCommand,
    previous_transaction_id: str,
    now: datetime,
    currency_normalizer: CurrencyNormalizationService | None = None,
    ports: LedgerActionPorts,
    decides_classification: bool = False,
    finalized_blockers: tuple[LedgerRemovalBlocker, ...] = (),
    evidence_only: bool = False,
) -> tuple[Transaction, tuple[BucketEvent, ...]] | None:
    """Build a replacement transaction and bucket events for one in-memory edit.

    Returns ``None`` when the command is a field-for-field no-op that also
    leaves whose decision the classification is as it was (the caller decides
    whether that is an error or a skip). A person restating the classification
    another party gave the row changes that, so it is built and recorded with
    a classification event. Verifies evidence and usage-ratio
    references but performs **no** persistence and **no** catalogue load - the
    caller owns a single load/save so a batch re-encrypts the catalogue once
    rather than per row (the ``bulk_classify_from_csv`` load-once/save-once
    contract). The lifecycle guard remains the caller's responsibility before
    invoking this builder.

    ``finalized_blockers`` are the finalized revisions the caller found citing
    the row. A write that would disturb one is refused here, for single and
    bulk writes alike, once the replacement it would store is known.

    A write whose every value compares equal to the stored one stores the
    stored row itself, with only the origin and the stamp of the
    restatement replaced. Equal values can be written differently (``500``
    for ``500.00``), a finalized revision's fingerprint hashes the written
    form, and a confirmation must not make a sealed revision read as stale.
    """
    if _changed_sealed_write(finalized_blockers, evidence_only, command, current):
        # A command that differs from the stored row in a value is a changed write, refused
        # before anything is built from it. One that compares equal is not admitted on that:
        # it is judged below, on the row it would store.
        _refuse_write_to_a_sealed_row(
            current, finalized_blockers, changed_fields=ledger_values_differing_from_stored(command, current)
        )
    require_declared_iva_category(command, ports=ports)
    replacement = transaction_from_command(
        command,
        occurred_at=now,
        provider_transaction_id=current.raw.provider_transaction_id if command.idempotency_key is None else None,
        currency_normalizer=currency_normalizer,
        created_by=current.created_by,
        created_source_command=current.source_command,
        created_event_id=current.created_event_id,
        existing_evidence_provenance=current.evidence_provenance,
        existing_edit_lineage=current.edit_lineage,
        lifecycle_state=current.lifecycle_state,
        lifecycle_lineage=current.lifecycle_lineage,
        import_fingerprint=current.import_fingerprint,
        created_at=current.created_at,
        modified_at=now,
        evidence_records=ports.purchase_invoice_evidence_records,
        classification_predecessor=current,
        classification_decided=decides_classification,
    )
    replacement = carry_forward_invoice_link(current, carry_forward_fx(current, replacement))
    restated = mutation_signature(current) == mutation_signature(replacement)
    if restated and not _origin_changed(current, replacement):
        return None
    if restated:
        replacement = _stored_row_restated(current, replacement)
    _require_finalized_revisions_undisturbed(
        current, replacement, blockers=finalized_blockers, evidence_only=evidence_only, restated=restated
    )
    verify_evidence_references(
        command,
        transaction_id=replacement.transaction_id,
        invoice_repository=ports.invoice_repository,
        attachment_store=ports.attachment_store,
        evidence_records=ports.purchase_invoice_evidence_records,
    )
    verify_usage_ratio_reference(command, usage_ratio_profile=ports.usage_ratio_profile, operation=ports.operation)
    event_specs = _update_event_specs(
        current=current,
        replacement=replacement,
        command=command,
        previous_transaction_id=previous_transaction_id,
    )
    events = tuple(
        build_ledger_bucket_event(
            bucket_id=command.bucket_id,
            event_type=event_type,
            occurred_at=now,
            actor=command.actor,
            object_type=object_type,
            object_id=object_id,
            payload=payload,
        )
        for event_type, object_type, object_id, payload in event_specs
    )
    primary_event_id = primary_lineage_event_id(events)
    evidence_event_ids = derive_evidence_event_ids(events)
    replacement = transaction_from_command(
        command,
        occurred_at=now,
        provider_transaction_id=current.raw.provider_transaction_id if command.idempotency_key is None else None,
        currency_normalizer=currency_normalizer,
        created_by=current.created_by,
        created_source_command=current.source_command,
        created_event_id=current.created_event_id,
        existing_evidence_provenance=current.evidence_provenance,
        existing_edit_lineage=current.edit_lineage,
        lifecycle_state=current.lifecycle_state,
        lifecycle_lineage=current.lifecycle_lineage,
        edit_lineage_entry=TransactionEditLineageEntry(
            previous_transaction_id=previous_transaction_id,
            actor=command.actor,
            source_command=command.source_command,
            edited_at=now,
            bucket_event_id=primary_event_id,
        ),
        bucket_event_id=primary_event_id,
        evidence_event_ids=evidence_event_ids,
        import_fingerprint=current.import_fingerprint,
        created_at=current.created_at,
        modified_at=now,
        evidence_records=ports.purchase_invoice_evidence_records,
        classification_predecessor=current,
        classification_decided=decides_classification,
    )
    replacement = carry_forward_invoice_link(current, carry_forward_fx(current, replacement))
    if restated:
        replacement = _stored_row_restated(current, replacement)
    return replacement, events


_EVIDENCE_PATCH_FIELDS = frozenset({"purchase_invoice_evidence_id", "attachment_ids"})
_RESTATEMENT_RECORD_FIELDS = (
    "classification_origin",
    "classified_by",
    "classified_at",
    "classification_reason",
    "classification_confidence",
    "edit_lineage",
    "modified_at",
)


def _stored_row_restated(current: Transaction, rebuilt: Transaction) -> Transaction:
    """Return the stored row carrying what the restatement records and nothing else of ``rebuilt``.

    Every value keeps the object and the written form it was stored with.
    """
    return current.model_copy(update={field: getattr(rebuilt, field) for field in _RESTATEMENT_RECORD_FIELDS})


def _require_finalized_revisions_undisturbed(
    current: Transaction,
    replacement: Transaction,
    *,
    blockers: tuple[LedgerRemovalBlocker, ...],
    evidence_only: bool,
    restated: bool,
) -> None:
    """Refuse a write to a row a finalized revision cites, unless it leaves what the revision sealed.

    A restatement is admitted when the row it would store keeps the identity
    the revision cites and the fingerprint the revision sealed: that is what
    this guard protects, so that is what the exemption is read from. Every
    other write but an evidence-only one is refused.
    """
    if not blockers or evidence_only:
        return
    if (
        restated
        and replacement.transaction_id == current.transaction_id
        and row_fingerprint(replacement) == row_fingerprint(current)
    ):
        return
    _refuse_write_to_a_sealed_row(current, blockers)


def _refuse_write_to_a_sealed_row(
    current: Transaction, blockers: tuple[LedgerRemovalBlocker, ...], *, changed_fields: tuple[str, ...] = ()
) -> None:
    raise_finalized_modelo_blocked(
        operation="ledger transaction update",
        transaction_ids=transaction_modelo_source_ids(current),
        blockers=blockers,
        changed_fields=changed_fields,
    )


def update_manual_transaction_fields(
    *,
    bucket_id: str,
    transaction_id: str,
    patch: ManualLedgerTransactionPatch,
    actor: str,
    source_command: str,
    classified_by_override: str | None = None,
    reaffirm: bool = False,
    ports: LedgerActionPorts,
    occurred_at: datetime | None = None,
    catalogue: TransactionCatalogue | None = None,
    expected_current: Transaction | None = None,
    _evidence_authority: bool = False,
) -> ManualLedgerTransactionResult:
    """Apply a typed field patch to one active bucket-scoped ledger transaction.

    The patch is a
    :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionPatch` converted
    into a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionCommand`
    before the same replacement path used by
    :func:`~cadrumo.application.ledger.manual_update.update_manual_transaction`.

    When ``reaffirm`` is :data:`True` the automatic re-affirmation no-op guard
    is bypassed and the command is forced through even if the patched fields are
    field-for-field identical to the stored transaction. This is the explicit
    operator-driven counterpart to the automatic silent no-op.

    ``catalogue`` is the bucket :class:`TransactionCatalogue` a caller in the
    same action has already decrypted (e.g. the CLI resolving an id prefix, or
    :func:`~cadrumo.application.ledger.manual_update.attach_manual_transaction_evidence`),
    passed through so the whole catalogue is not decrypted a second time. The
    caller must not write between its load and this call, so the view is current.

    ``expected_current`` optionally carries a detail screen's opened snapshot.
    It is compared before command construction, so even a would-be
    re-affirmation no-op refuses when the screen is stale.

    Returns a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`
    reflecting the updated transaction state after the patch is applied.
    """
    if not _evidence_authority and patch.model_fields_set & _EVIDENCE_PATCH_FIELDS:
        raise TransactionValidationError(
            "purchase evidence and attachments are managed only by `aeat app ledger attach`; "
            "a generic ledger field update must not set purchase_invoice_evidence_id or attachment_ids",
            context={
                "transaction_id": transaction_id,
                "evidence_fields": ",".join(sorted(patch.model_fields_set & _EVIDENCE_PATCH_FIELDS)),
            },
        )
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=ports.transaction_repository)
    if catalogue is None:
        catalogue = repository.load()
    current = require_transaction(catalogue, transaction_id)
    _require_expected_current_transaction(current=current, expected_current=expected_current)
    command = command_from_patch(
        bucket_id=bucket_id,
        current=current,
        patch=patch,
        actor=actor,
        source_command=source_command,
        classified_by_override=classified_by_override,
    )
    # Re-affirmation: operator supplied the same ``business_classification`` the record already
    # carries.  ``command_from_patch`` produces a command identical to the stored transaction,
    # which would trigger the mutation-required guard in ``update_manual_transaction``.  Treat
    # field-for-field-identical commands originating from a ``business_classification`` patch as
    # confirmed no-ops rather than errors (the deliberate direction chosen for this guard).
    # When ``reaffirm`` is True the operator explicitly requests re-application; skip the guard.
    # A person restating a classification another party decided is not a no-op: it makes the
    # row theirs, so it goes on to be written.
    decides_classification = bool(_fields_set_to_a_value(patch) & CLASSIFICATION_DECISION_FIELDS)
    if (
        not reaffirm
        and "business_classification" in patch.model_fields_set
        and command_matches_current(command, current)
        and not _unchanged_write_takes_the_row(current, command, decides_classification=decides_classification)
    ):
        return build_manual_ledger_result(bucket_id, current, ())
    return update_manual_transaction(
        transaction_id=transaction_id,
        command=command,
        ports=ports,
        occurred_at=occurred_at,
        catalogue=catalogue,
        expected_current=expected_current,
        decides_classification=decides_classification,
        _evidence_authority=_evidence_authority,
    )


def _fields_set_to_a_value(patch: ManualLedgerTransactionPatch) -> set[str]:
    """Return the fields ``patch`` sets, less a purchase evidence link set to nothing.

    A link that names no evidence links nothing, so it decides nothing about
    how the row is taxed.
    """
    fields = set(patch.model_fields_set)
    if patch.purchase_invoice_evidence_id is None:
        fields.discard("purchase_invoice_evidence_id")
    return fields


def _origin_changed(current: Transaction, replacement: Transaction) -> bool:
    return resolved_classification_origin(current) is not resolved_classification_origin(replacement)


def _unchanged_write_takes_the_row(
    current: Transaction, command: ManualLedgerTransactionCommand, *, decides_classification: bool
) -> bool:
    """Return whether a write of ``command`` that moves no value still changes whose row it is."""
    restated = with_classification_origin(
        current, replaces=current, written=written_origin(command), decided=decides_classification
    )
    return _origin_changed(current, restated)


def command_from_patch(
    *,
    bucket_id: str,
    current: Transaction,
    patch: ManualLedgerTransactionPatch,
    actor: str,
    source_command: str,
    classified_by_override: str | None = None,
) -> ManualLedgerTransactionCommand:
    """Merge explicit patch fields with the stored transaction."""
    raw = current.raw
    patch_fields = patch.model_fields_set
    booked_date = required_patched(patch, patch_fields, "booked_date", raw.booked_date)
    amount = required_patched(patch, patch_fields, "amount", raw.amount)
    currency = required_patched(patch, patch_fields, "currency", raw.currency)
    direction = required_patched(patch, patch_fields, "direction", current.direction)
    description = required_patched(patch, patch_fields, "description", raw.description)
    business_classification = required_patched(
        patch,
        patch_fields,
        "business_classification",
        current.business_classification,
    )
    business_pct = optional_patched(patch, patch_fields, "business_pct", current.business_pct)
    category_id = optional_patched(patch, patch_fields, "category_id", current.category_id)
    taxable_base = optional_patched(patch, patch_fields, "taxable_base", current.taxable_base)
    iva_rate = optional_patched(patch, patch_fields, "iva_rate", current.iva_rate)
    iva_amount = optional_patched(patch, patch_fields, "iva_amount", current.iva_amount)
    recargo_amount = optional_patched(patch, patch_fields, "recargo_amount", current.recargo_amount)
    irpf_category = optional_patched(patch, patch_fields, "irpf_category", current.irpf_category)
    m210_income_classification = optional_patched(
        patch,
        patch_fields,
        "m210_income_classification",
        current.m210_income_classification,
    )
    usage_ratio_id = optional_patched(patch, patch_fields, "usage_ratio_id", current.usage_ratio_id)
    prorrata_reference = optional_patched(patch, patch_fields, "prorrata_reference", current.prorrata_reference)
    if "business_classification" in patch_fields and business_classification is not BusinessClassification.MIXED:
        business_pct = None
        usage_ratio_id = None
    if "business_classification" in patch_fields and business_classification not in {
        BusinessClassification.BUSINESS,
        BusinessClassification.MIXED,
    }:
        category_id = None
        taxable_base = None
        iva_rate = None
        iva_amount = None
        recargo_amount = None
        irpf_category = None
        m210_income_classification = None
        prorrata_reference = None
    notes = required_patched(patch, patch_fields, "notes", current.notes)
    attachment_ids = required_patched(patch, patch_fields, "attachment_ids", current.attachment_ids)
    iva_category = optional_patched(patch, patch_fields, "iva_category", current.iva_category)
    deduction_fact_kind = optional_patched(
        patch,
        patch_fields,
        "deduction_fact_kind",
        current.deduction_fact_kind,
    )
    investment_asset_id = optional_patched(
        patch,
        patch_fields,
        "investment_asset_id",
        current.investment_asset_id,
    )
    counterparty_country = optional_patched(
        patch,
        patch_fields,
        "counterparty_country",
        current.counterparty_country,
    )
    counterparty_identification_state = optional_patched(
        patch,
        patch_fields,
        "counterparty_identification_state",
        current.counterparty_identification_state,
    )
    group_label = optional_patched(patch, patch_fields, "group_label", current.group_label)
    own_account_id = optional_patched(patch, patch_fields, "own_account_id", current.own_account_id)
    # Preserve the three add-time prorrata declarations during reclassification.
    art_104_tres_exclusion = optional_patched(
        patch,
        patch_fields,
        "art_104_tres_exclusion",
        current.art_104_tres_exclusion,
    )
    input_classification = optional_patched(
        patch,
        patch_fields,
        "input_classification",
        current.input_classification,
    )
    prorrata_sector_id = optional_patched(
        patch,
        patch_fields,
        "prorrata_sector_id",
        current.prorrata_sector_id,
    )
    return ManualLedgerTransactionCommand(
        bucket_id=bucket_id,
        booked_date=booked_date,
        value_date=patch.value_date if "value_date" in patch_fields else raw.value_date,
        amount=amount,
        currency=currency,
        direction=direction,
        counterparty=patch.counterparty if "counterparty" in patch_fields else raw.counterparty,
        description=description,
        business_classification=business_classification,
        business_pct=business_pct,
        category_id=category_id,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        recargo_amount=recargo_amount,
        irpf_category=irpf_category,
        m210_income_classification=m210_income_classification,
        usage_ratio_id=usage_ratio_id,
        prorrata_reference=prorrata_reference,
        purchase_invoice_evidence_id=(
            patch.purchase_invoice_evidence_id
            if "purchase_invoice_evidence_id" in patch_fields
            else current.purchase_invoice_evidence_id
        ),
        attachment_ids=attachment_ids,
        notes=notes,
        iva_category=iva_category,
        deduction_fact_kind=deduction_fact_kind,
        investment_asset_id=investment_asset_id,
        counterparty_country=counterparty_country,
        counterparty_identification_state=counterparty_identification_state,
        source_jurisdiction=(
            patch.source_jurisdiction if "source_jurisdiction" in patch_fields else current.source_jurisdiction
        ),
        group_label=group_label,
        own_account_id=own_account_id,
        art_104_tres_exclusion=art_104_tres_exclusion,
        input_classification=input_classification,
        prorrata_sector_id=prorrata_sector_id,
        actor=actor,
        source_command=source_command,
        classified_by_override=classified_by_override,
    )


def _update_event_specs(
    *,
    current: Transaction,
    replacement: Transaction,
    command: ManualLedgerTransactionCommand,
    previous_transaction_id: str,
) -> tuple[EventSpec, ...]:
    common_payload = {
        **event_payload(command),
        "previous_transaction_id": previous_transaction_id,
    }
    specs: list[EventSpec] = []
    if _core_edit_changed(current, replacement):
        specs.append(
            (
                BucketEventType.LEDGER_TRANSACTION_UPDATED,
                BucketEventObjectType.LEDGER_TRANSACTION,
                replacement.transaction_id,
                {**common_payload, "mutation_kind": "edit"},
            ),
        )
    classification_spec: EventSpec = (
        BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
        BucketEventObjectType.LEDGER_TRANSACTION,
        replacement.transaction_id,
        {
            **common_payload,
            "classification": replacement.business_classification.value,
            "category_id": replacement.category_id or "",
            "mutation_kind": "classification",
        },
    )
    if _classification_changed(current, replacement):
        specs.append(classification_spec)
    if _allocation_changed(current, replacement):
        specs.append(
            (
                BucketEventType.LEDGER_TRANSACTION_ALLOCATED,
                BucketEventObjectType.LEDGER_TRANSACTION,
                replacement.transaction_id,
                {
                    **common_payload,
                    "business_pct": optional_decimal(replacement.business_pct),
                    "usage_ratio_id": replacement.usage_ratio_id or "",
                    "prorrata_reference": replacement.prorrata_reference or "",
                    "mutation_kind": "allocation",
                },
            ),
        )
    specs.extend(_evidence_event_specs(current=current, replacement=replacement, common_payload=common_payload))
    if not specs and _origin_changed(current, replacement):
        # Nothing moved but whose decision the classification is: the person accepted what the
        # row carried, and the history shows that as the classification it is.
        specs.append(classification_spec)
    if not specs:
        specs.append(
            (
                BucketEventType.LEDGER_TRANSACTION_UPDATED,
                BucketEventObjectType.LEDGER_TRANSACTION,
                replacement.transaction_id,
                {**common_payload, "mutation_kind": "correction"},
            ),
        )
    return tuple(specs)


def _core_edit_changed(current: Transaction, replacement: Transaction) -> bool:
    return any(
        getattr(current.raw, field) != getattr(replacement.raw, field)
        for field in ("booked_date", "value_date", "amount", "currency", "counterparty", "description")
    ) or any(
        getattr(current, field) != getattr(replacement, field)
        for field in ("direction", "taxable_base", "iva_rate", "iva_amount", "irpf_category", "notes")
    )


def _classification_changed(current: Transaction, replacement: Transaction) -> bool:
    return any(
        getattr(current, field) != getattr(replacement, field)
        for field in ("business_classification", "category_id", "classification_reason")
    )


def _allocation_changed(current: Transaction, replacement: Transaction) -> bool:
    return any(
        getattr(current, field) != getattr(replacement, field)
        for field in ("business_pct", "usage_ratio_id", "prorrata_reference")
    )


def _evidence_event_specs(
    *,
    current: Transaction,
    replacement: Transaction,
    common_payload: Mapping[str, str],
) -> tuple[EventSpec, ...]:
    specs: list[EventSpec] = []
    if current.purchase_invoice_evidence_id != replacement.purchase_invoice_evidence_id:
        if current.purchase_invoice_evidence_id is not None:
            specs.append(
                (
                    BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
                    BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
                    current.purchase_invoice_evidence_id,
                    {
                        **common_payload,
                        "transaction_id": replacement.transaction_id,
                        "mutation_kind": "purchase_invoice_evidence_detached",
                    },
                ),
            )
        if replacement.purchase_invoice_evidence_id is not None:
            specs.append(
                (
                    (
                        BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED
                        if current.purchase_invoice_evidence_id is not None
                        else BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED
                    ),
                    BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
                    replacement.purchase_invoice_evidence_id,
                    {
                        **common_payload,
                        "transaction_id": replacement.transaction_id,
                        "mutation_kind": "purchase_invoice_evidence_attached",
                    },
                ),
            )
    current_attachments = set(current.attachment_ids)
    replacement_attachments = set(replacement.attachment_ids)
    for attachment_id in sorted(replacement_attachments - current_attachments):
        specs.append(
            (
                BucketEventType.ATTACHMENT_LINKED,
                BucketEventObjectType.ATTACHMENT,
                attachment_id,
                {
                    **common_payload,
                    "transaction_id": replacement.transaction_id,
                    "linked": "true",
                    "mutation_kind": "attachment_linked",
                },
            ),
        )
    for attachment_id in sorted(current_attachments - replacement_attachments):
        specs.append(
            (
                BucketEventType.ATTACHMENT_REMOVED,
                BucketEventObjectType.ATTACHMENT,
                attachment_id,
                {
                    **common_payload,
                    "transaction_id": replacement.transaction_id,
                    "linked": "false",
                    "mutation_kind": "attachment_removed",
                },
            ),
        )
    return tuple(specs)
