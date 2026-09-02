"""Confirming a reviewed invoice draft into a persisted catalogue record.

The non-interactive CONFIRM step that closes the review loop: it re-runs the
on-host extraction through
:func:`~application.ledger.invoice_draft_extraction.extract_invoice_draft_from_evidence`,
applies any operator-supplied field overrides (extraction is best-effort, so
every field may be corrected), and delegates the actual write to
:func:`~application.invoices.create_catalogue_invoice` -- the sole sanctioned
:class:`~domain.invoices.Invoice` writer (``aeat-architecture-boundaries``).
This module never writes the :class:`InvoiceCatalogue` itself.

The confirm runs in three stages, each a function of its own so the guards
cannot be reordered by accident:

**Prepare.** Re-read the document, stamp a direction contradiction as an
ordinary resolvable finding, resolve the review gate's blockers, and resolve
both parties' establishment. **Build.** Resolve every persisted field from the
operator's statement layered over the reading, through the guards in
:mod:`~application.ledger.confirm_party_identity` and the resolvers in
:mod:`~application.ledger.confirmed_field_resolution`. **Persist.** Apply the
idempotency guards, link the evidence, and write the confirmation record.

Idempotent-guarded (``aeat-cli-contract``). Two distinct identities are checked,
in that order, and the order matters: DOCUMENT identity first -- the attachment
address is the SHA-256 of the bytes, so it answers "has this document already
been turned into a record" exactly -- then invoice identity, which folds only
the six resolved fields and therefore cannot answer it. A retry resolving every
compared field identically returns the existing invoice unchanged; a re-confirm
of one document that DIFFERS refuses, naming the divergent fields, rather than
minting a second catalogue record that would aggregate twice into Modelo 303,
347 and 390.

Confirming also auto-links the source evidence to the resulting invoice:
:func:`~domain.attachments.link_attachment_invoice` appends the invoice's id
to the backing :class:`~domain.attachments.Attachment`'s
:attr:`~domain.attachments.Attachment.linked_invoice_ids`, closing the
provenance loop in both directions. The link is re-asserted on a guarded no-op
confirm too, so a re-confirm never regresses a provenance link that was never
wired for older evidence, and the append itself is idempotent.

See Also:
    :func:`~application.ledger.invoice_draft_extraction.extract_invoice_draft_from_evidence`
        The reading stage this confirm re-runs.
    :func:`~application.ledger.evidence_draft.printed_total_discrepancy`
        The printed-versus-recorded cross-check carried on every result.
    :class:`~application.ledger.confirmation_record.InvoiceConfirmationRecord`
        The durable account of who confirmed what, written by every confirm.
    :func:`~application.invoices.create_catalogue_invoice`
        Sole sanctioned writer for the resulting catalogue invoice.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Final, NamedTuple, NoReturn

from pydantic import BaseModel, Field

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.storage.attachment import AttachmentStore
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...application.invoices.catalogue_creation import build_catalogue_invoice, create_catalogue_invoice
from ...core.aggregation import IntracomOperationType
from ...core.config import Settings
from ...core.config import load_settings as _load_settings
from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.parsing.dates import parse_iso8601_date
from ...domain.attachments.errors import AttachmentNotFoundError
from ...domain.attachments.service import link_attachment_invoice
from ...domain.currency.service import ExchangeRateProvider
from ...domain.invoices.enums import InvoiceClass
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.models import Invoice, InvoiceCatalogue
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.schema import IvaCategory
from ...domain.iva.supply_nature import SupplyNature
from .confirm_party_identity import (
    agreed_counterparty_tax_id,
    refuse_a_counterparty_that_is_the_filer,
    refuse_an_issued_document_the_filer_did_not_issue,
)
from .confirmed_field_resolution import (
    confirmed_counterparty_name,
    confirmed_currency,
    confirmed_lines_from_the_document,
    operator_restated_the_amounts,
    operator_value_or_reading,
    rate_tier_the_document_charged,
    require_confirmed_field,
    resolve_confirmed_invoice_date,
    resolve_invoice_class,
)
from .evidence import PurchaseInvoiceEvidenceService
from .evidence_draft import (
    PrintedTotalDiscrepancy,
    counterparty_draft_side,
    printed_total_discrepancy,
)
from .evidence_reference import find_bytes_bearing_evidence_record, refuse_reference_without_document_bytes
from .invoice_draft_extraction import extract_invoice_draft_from_evidence
from .invoice_draft_records import DraftDiscrepancyFinding, FieldProvenance, InvoiceDraft

if TYPE_CHECKING:
    from .confirm_establishment import ConfirmedEstablishment
    from .confirmation_gate import ConfirmationBlocker, FindingResolution
    from .confirmation_record import InvoiceConfirmationRecord

__all__ = ["InvoiceConfirmationResult", "confirm_invoice_draft_from_evidence"]


class InvoiceConfirmationResult(BaseModel):
    """Outcome of confirming a reviewed :class:`InvoiceDraft` into an :class:`Invoice`.

    Attributes:
        invoice: The persisted (or already-existing, on a guarded no-op)
            :class:`~domain.invoices.Invoice`.
        draft: The re-run on-host extraction the confirmation was based on
            (before overrides were applied), kept so the operator can see what
            was actually read from the document versus what they overrode.
        created: ``True`` when this call minted a new catalogue row;
            ``False`` when an invoice with the identical derived identity
            already existed and this call returned it unchanged (the guarded
            idempotent-retry no-op).
        total_discrepancy: Set when the document's printed total disagrees with
            the derived total now on record -- see
            :class:`PrintedTotalDiscrepancy` for why that is always worth
            surfacing. ``None`` when they agree or no total was readable. The
            field rides the RESULT rather than being recomputed by each caller
            so a consumer cannot silently omit the check.
        confirmation_id: Derived address of the persisted
            :class:`~application.ledger.confirmation_record.InvoiceConfirmationRecord` this confirm
            wrote -- who confirmed, when, which fields they asserted values for
            with the prior value and origin retained, which findings they
            answered and how, and the evidence and transcription content
            addresses it was taken against. The id rather than the record
            itself: the record is the durable answer and lives in the encrypted
            store, and a copy riding a transient result is a second account of
            one decision that can disagree with the first.
        establishment: Both parties' IVA territories as this confirm resolved
            them -- the counterparty's through the evidence ladder, the filer's
            own from their profile -- beside the classification criteria they
            were carried into and every territorial question left open. ``None``
            only where the resolution was not attempted. A resolved territory
            rides the RESULT rather than being recomputed per consumer for the
            same reason the printed-total discrepancy does: a second derivation
            is a second answer, and the two can disagree about a filing.
        confirmed_provenance: The draft's envelopes with every operator-asserted
            field re-stamped :attr:`~core.FieldOrigin.OPERATOR`. Carried BESIDE
            ``draft`` rather than replacing its envelopes, because a correction
            is an assertion and not an edit: ``draft.provenance`` stays the
            document's own account of itself, this is the confirmed view, and
            the confirmation record holds the pairing of the two.
    """

    model_config = STRICT_FROZEN_CONFIG

    invoice: Invoice
    draft: InvoiceDraft
    created: bool
    total_discrepancy: PrintedTotalDiscrepancy | None = None
    confirmation_id: str | None = Field(default=None, min_length=16, max_length=16)
    confirmed_provenance: tuple[FieldProvenance, ...] = ()
    establishment: ConfirmedEstablishment | None = None


def _with_direction_contradiction(draft: InvoiceDraft, *, kind: InvoiceKind) -> InvoiceDraft:
    """Return *draft* carrying a finding when the document contradicts *kind*.

    The consuming half of :func:`derive_invoice_kind_from_filer_role`. The
    reading stage asks which party's block prints the filer's own identifier and
    stamps the answer as a SUGGESTION; the operator states the direction on the
    confirm verb. Only here are both in hand, which is why the comparison lives
    at this boundary rather than on the reading path.

    Stamped as an ordinary :class:`DraftDiscrepancyFinding` rather than raised,
    and that is the ruling rather than an implementation convenience. Every
    discrepancy kind maps to a
    :class:`~core.ConfirmationBlockReason`, so the disagreement becomes a
    resolvable blocker the operator answers per-document with a stated reason --
    which is the right shape for a conflict between two honest readings. A
    refusal would leave an operator who is RIGHT, and a document whose layout
    misleads the derivation, with no way through at all.

    Silent when the document settled nothing. A derivation that reports
    ``None`` did not disagree with the operator; it declined to answer, and
    treating that as agreement or as conflict would both be inventions.

    Args:
        draft: The re-read draft, carrying the derivation's suggestion.
        kind: The direction the operator stated on the verb.

    Returns:
        The draft unchanged when the document settled nothing or agrees, or a
        copy carrying one additional
        :attr:`~core.DraftDiscrepancyKind.DIRECTION_CONTRADICTED` finding.
    """
    suggested = draft.suggested_kind
    if suggested is None or suggested is kind:
        return draft
    return draft.model_copy(
        update={
            "discrepancies": (
                *draft.discrepancies,
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.DIRECTION_CONTRADICTED,
                    field="suggested_kind",
                    detail=(
                        f"this document places the filer on the side that makes it {suggested.value}, but it "
                        f"is being confirmed as {kind.value}. Direction decides which informativa the record "
                        f"feeds and on which side, and AEAT reconciles the two counterparties' declarations "
                        f"against each other"
                    ),
                ),
            ),
        },
    )


# The fields a confirm does not author. Everything else on `Invoice` is written
# from the confirm's own resolved inputs, so a re-confirm that differs on any of
# them is a different statement about the document and must not be absorbed as a
# no-op (`aeat-cli-contract`: the match compares EVERY persisted field).
#
# Each exclusion is a field some LATER verb owns: the payment lifecycle stamps
# the first three, the ledger cross-reference the fourth, and the repository the
# record stamps. Comparing them would make an ordinary paid invoice refuse its
# own re-confirm. The set is named rather than inlined, and the comparison is
# derived from `Invoice.model_fields`, so a field added to the model joins the
# match automatically instead of silently falling outside it.
_INVOICE_FIELDS_A_CONFIRM_DOES_NOT_AUTHOR: Final = frozenset(
    {
        "created_at",
        "linked_transaction_ids",
        "payment_id",
        "payment_status",
        "updated_at",
    },
)


def _fields_a_reconfirm_would_change(candidate: Invoice, stored: Invoice) -> tuple[str, ...]:
    """Return every persisted field on which *candidate* disagrees with *stored*.

    Derived from the model rather than a hand-listed field set: the failure this
    exists to prevent is a match that omits a field, and a hand-listed set is
    exactly how that omission arrives. A new :class:`~domain.invoices.Invoice`
    field is compared the moment it is declared.
    """
    compared = candidate.model_dump(mode="json")
    against = stored.model_dump(mode="json")
    field_names = tuple(str(name) for name in Invoice.model_fields)
    return tuple(
        sorted(
            name
            for name in field_names
            if name not in _INVOICE_FIELDS_A_CONFIRM_DOES_NOT_AUTHOR and compared.get(name) != against.get(name)
        ),
    )


def _written_confirmation_record(
    *,
    bucket_id: str,
    invoice_id: str,
    evidence_id: str | None,
    attachment_id: str,
    draft: InvoiceDraft,
    confirmed_by: str,
    overrides: Mapping[str, object | None],
    blockers: tuple[ConfirmationBlocker, ...],
    resolutions: Sequence[FindingResolution],
    settings: Settings,
) -> InvoiceConfirmationRecord:
    """Build and persist the confirmation record for one confirmed invoice.

    Shared by the minting path and the guarded idempotent retry so both record
    the same provenance. A retry that skipped this would leave the second
    operator's assertion unrecorded while the first one's stood, which is the
    provenance regression the guard exists to prevent.
    """
    from .confirmation_record import build_confirmation_record, write_confirmation_record

    return write_confirmation_record(
        record=build_confirmation_record(
            bucket_id=bucket_id,
            invoice_id=invoice_id,
            evidence_reference=evidence_id or attachment_id,
            evidence_sha256=_evidence_content_address(
                bucket_id=bucket_id,
                evidence_id=evidence_id,
                settings=settings,
            ),
            draft=draft,
            extractor=_confirmed_extractor(draft),
            confirmed_by=confirmed_by,
            overrides=overrides,
            blockers=blockers,
            resolutions=resolutions,
        ),
        settings=settings,
    )


def _confirmed_extractor(draft: InvoiceDraft) -> str:
    """Return which reading lane produced *draft*, for the confirmation record.

    Read off the origins the draft's own envelopes carry rather than passed in
    by the caller: the caller does not know which lane ran, and a lane label a
    caller supplies is a claim rather than an observation. A draft carrying no
    envelope at all names the lane honestly as unrecorded instead of guessing
    the most likely one.
    """
    origins = sorted({envelope.origin.value for envelope in draft.provenance})
    return "+".join(origins) if origins else "unrecorded"


def _evidence_content_address(*, bucket_id: str, evidence_id: str | None, settings: Settings) -> str | None:
    """Return the content address of the confirmed evidence bytes, when known.

    Resolved from the ``purchase_invoice_evidence`` record's own
    ``source_sha256``. A confirm taken directly against an attachment id has no
    such record, and the address stays ``None`` rather than being invented from
    the id -- an id is a name for the bytes, not a fingerprint of them, and
    recording one as the other would let a later re-derivation believe it had
    proved something it never checked.
    """
    if evidence_id is None:
        return None
    record = find_bytes_bearing_evidence_record(
        evidence_id,
        evidence_records=PurchaseInvoiceEvidenceService(settings=settings).list_all(bucket_id=bucket_id),
    )
    return record.source_sha256 if record is not None else None


def _resolve_evidence_attachment_id(
    *,
    bucket_id: str,
    evidence_id: str | None,
    attachment_id: str | None,
    settings: Settings,
) -> str:
    """Return the in-store ``attachment_id`` backing one evidence reference.

    Mirrors the exactly-one-of resolution
    :func:`~application.ledger.invoice_draft_extraction.extract_invoice_draft_from_evidence` already
    enforces (that call already ran, so the invariant holds here too): when
    *attachment_id* is supplied directly it is returned unchanged; when
    *evidence_id* is supplied, the linked ``purchase_invoice_evidence`` record's own
    :attr:`~._evidence.PurchaseInvoiceEvidence.attachment_id` is looked up, which is
    a required field and so always names an in-store byte home.

    Resolves the reference through the same
    :func:`~application.ledger.evidence_reference.find_bytes_bearing_evidence_record`
    the extraction path used, so the confirm step cannot decide the id belongs to a
    different space than the extraction did.
    """
    if attachment_id is not None:
        return attachment_id
    if evidence_id is None:
        # The caller admits exactly one of attachment_id / evidence_id; reaching
        # here with neither means that guard and this resolver disagree.
        raise InvoiceValidationError(
            "evidence reference resolution requires either an attachment id or an evidence id",
        )
    record = find_bytes_bearing_evidence_record(
        evidence_id,
        evidence_records=PurchaseInvoiceEvidenceService(settings=settings).list_all(bucket_id=bucket_id),
    )
    if record is None:
        raise refuse_reference_without_document_bytes(evidence_id)
    return record.attachment_id


def _prior_invoices_this_document_minted(
    store: AttachmentStore,
    *,
    attachment_id: str,
    catalogue: InvoiceCatalogue,
    candidate_invoice_id: str,
) -> tuple[Invoice, ...]:
    """Return the catalogue records this same document already minted, bar the candidate.

    Document identity, resolved BEFORE invoice identity. The invoice id folds
    only six resolved fields, so it cannot answer "has this document already
    been turned into a record" -- a re-confirm resolving any of the six
    differently hashes to a new id and mints a duplicate that inflates every
    downstream modelo aggregation. The attachment address answers it exactly: it
    is the SHA-256 of the bytes, and the manifest already records what this
    document minted.
    """
    return tuple(
        stored
        for invoice_id in _invoice_ids_this_document_already_minted(store, attachment_id=attachment_id)
        if invoice_id != candidate_invoice_id and (stored := catalogue.get(invoice_id)) is not None
    )


def _invoice_ids_this_document_already_minted(
    store: AttachmentStore,
    *,
    attachment_id: str,
) -> tuple[str, ...]:
    """Return the invoices already minted from the document at *attachment_id*.

    Read off the attachment manifest's ``linked_invoice_ids``, which the confirm
    path itself writes through :func:`~domain.attachments.link_attachment_invoice`.
    No second index is introduced: the manifest already records the link, and the
    attachment id IS the SHA-256 of the document's bytes, so the identity is
    clock-free and the same file re-attached under a fresh evidence id resolves
    to the same address.

    A manifest that is not there yet answers "none": the document has certainly
    not been confirmed from a record that does not exist.
    """
    try:
        return store.load_manifest(attachment_id).linked_invoice_ids
    except AttachmentNotFoundError:
        return ()


def _refuse_a_divergent_reconfirm(
    *,
    candidate: Invoice,
    prior: Invoice,
    attachment_id: str,
) -> NoReturn:
    """Refuse a re-confirm of one document that does not match the record it made.

    Two shapes reach here and both are the same mistake. When the divergence is
    in one of the six fields the invoice id folds, the confirm would hash to a
    NEW id and mint a SECOND catalogue record from one document -- an operator
    correcting a mis-read number, a second reading lane rounding a total
    differently -- and both records then aggregate into Modelo 303, 347 and 390,
    which AEAT reconciles against the counterparty's own declaration. When the
    divergence is in any other field, the same-id guard would return the stored
    record and the correction would vanish with nothing surfaced, which is the
    worse of the two because nobody finds out.

    The refusal names the divergent fields rather than reporting a bare conflict,
    because the operator's next move depends entirely on which field moved: a
    corrected number means the stored record is wrong and should be removed, a
    different total means the two documents are not the same invoice.
    """
    divergent = _fields_a_reconfirm_would_change(candidate, prior)
    raise InvoiceValidationError(
        f"this document already confirmed invoice {prior.invoice_id} and this confirm differs on "
        f"{', '.join(divergent) or 'no compared field'}. Correct or remove the stored invoice rather "
        "than confirming the same document twice",
        translated_message="application.ledger.evidence.errors.document_already_confirmed",
        context={
            "attachment_id": attachment_id,
            "divergent_fields": ", ".join(divergent),
            "stored_invoice_id": prior.invoice_id,
        },
    )


class _InvoiceConfirmationPreparation(NamedTuple):
    """Validated draft state carried from extraction to catalogue persistence."""

    settings: Settings
    draft: InvoiceDraft
    blockers: tuple[ConfirmationBlocker, ...]
    attachment_id: str
    establishment: ConfirmedEstablishment
    operator_overrides: dict[str, object | None]
    operator_restated_amounts: bool


def _prepare_invoice_confirmation(
    *,
    bucket_id: str,
    kind: InvoiceKind,
    evidence_id: str | None,
    attachment_id: str | None,
    counterparty_country: str,
    taxable_base: Decimal | None,
    iva_rate: Decimal | None,
    iva_amount: Decimal | None,
    supply_nature: SupplyNature | None,
    settings: Settings | None,
    resolutions: Sequence[FindingResolution],
    counterparty_tax_id: str | None,
    counterparty_name: str | None,
    invoice_number: str | None,
    invoice_date: date | None,
    currency: str | None,
    retention_rate: Decimal | None,
    retention_amount: Decimal | None,
    recargo_amount: Decimal | None,
) -> _InvoiceConfirmationPreparation:
    """Extract, gate, and resolve the document-side confirmation authorities."""
    from .confirm_establishment import ConfirmedEstablishment, resolve_confirmed_establishment
    from .confirmation_gate import resolved_blockers

    # The result's establishment annotation is a forward reference because the
    # review gate imports this module. Rebuild it at the same deferred boundary.
    InvoiceConfirmationResult.model_rebuild(_types_namespace={"ConfirmedEstablishment": ConfirmedEstablishment})
    resolved_settings = settings or _load_settings()
    draft = extract_invoice_draft_from_evidence(
        bucket_id=bucket_id,
        evidence_id=evidence_id,
        attachment_id=attachment_id,
        settings=resolved_settings,
    )
    # A contradiction is a normal blocker, so it must be stamped before the gate.
    draft = _with_direction_contradiction(draft, kind=kind)
    blockers = resolved_blockers(draft=draft, resolutions=resolutions)
    resolved_attachment_id = _resolve_evidence_attachment_id(
        bucket_id=bucket_id,
        evidence_id=evidence_id,
        attachment_id=attachment_id,
        settings=resolved_settings,
    )
    counterparty_side = counterparty_draft_side(draft, kind=kind)
    operator_restated_amounts = operator_restated_the_amounts(
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
    )
    classification_date = invoice_date if invoice_date is not None else parse_iso8601_date(draft.invoice_date)
    establishment = resolve_confirmed_establishment(
        bucket_id=bucket_id,
        draft=draft,
        kind=kind,
        invoice_date=classification_date,
        rate_tier=rate_tier_the_document_charged(
            draft,
            invoice_date=classification_date,
            operator_restated_amounts=operator_restated_amounts,
        ),
        supply_nature=supply_nature,
    )
    operator_overrides: dict[str, object | None] = {
        counterparty_side.tax_id_field: counterparty_tax_id,
        counterparty_side.name_field: counterparty_name,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "taxable_base": taxable_base,
        "iva_rate": iva_rate,
        "iva_amount": iva_amount,
        "currency": currency,
        "recargo_amount": recargo_amount,
        "retencion_rate": retention_rate,
        "retencion_amount": retention_amount,
    }
    return _InvoiceConfirmationPreparation(
        settings=resolved_settings,
        draft=draft,
        blockers=blockers,
        attachment_id=resolved_attachment_id,
        establishment=establishment,
        operator_overrides=operator_overrides,
        operator_restated_amounts=operator_restated_amounts,
    )


def _build_confirmed_invoice_candidate(
    *,
    bucket_id: str,
    kind: InvoiceKind,
    counterparty_country: str,
    counterparty_tax_id: str | None,
    counterparty_name: str | None,
    invoice_number: str | None,
    invoice_date: date | None,
    taxable_base: Decimal | None,
    iva_rate: Decimal | None,
    iva_amount: Decimal | None,
    currency: str | None,
    iva_category: IvaCategory | None,
    operation_type: IntracomOperationType | None,
    operation_date: date | None,
    retention_rate: Decimal | None,
    retention_amount: Decimal | None,
    recargo_amount: Decimal | None,
    invoice_class: InvoiceClass | None,
    supply_nature: SupplyNature | None,
    series: str | None,
    rectifies_invoice_number: str | None,
    notes: str,
    rate_provider: ExchangeRateProvider | None,
    preparation: _InvoiceConfirmationPreparation,
) -> Invoice:
    """Resolve operator/document fields and build the exact catalogue candidate."""
    draft = preparation.draft
    counterparty_side = counterparty_draft_side(draft, kind=kind)
    resolved_counterparty_tax_id = require_confirmed_field(
        agreed_counterparty_tax_id(
            supplied=counterparty_tax_id,
            extracted=counterparty_side.tax_id,
            counterparty_country=counterparty_country,
        ),
        field="counterparty_tax_id",
    )
    refuse_an_issued_document_the_filer_did_not_issue(
        kind=kind,
        extracted_supplier_tax_id=draft.supplier_tax_id,
    )
    refuse_a_counterparty_that_is_the_filer(resolved_counterparty_tax_id)
    resolved_invoice_number = require_confirmed_field(
        operator_value_or_reading(invoice_number, draft.invoice_number),
        field="invoice_number",
    )
    resolved_invoice_date = resolve_confirmed_invoice_date(invoice_date, draft)
    resolved_taxable_base = require_confirmed_field(
        operator_value_or_reading(taxable_base, draft.taxable_base),
        field="taxable_base",
    )
    resolved_iva_rate = operator_value_or_reading(iva_rate, draft.iva_rate)
    resolved_currency = confirmed_currency(currency, draft.currency)
    resolved_counterparty_name = confirmed_counterparty_name(counterparty_name, counterparty_side.name)
    confirmed_lines = confirmed_lines_from_the_document(
        draft=draft,
        invoice_number=resolved_invoice_number,
        taxable_base=resolved_taxable_base,
        iva_rate=resolved_iva_rate,
        iva_amount=iva_amount,
        operator_overrode_the_amounts=preparation.operator_restated_amounts,
    )
    resolved_recargo_amount = (
        recargo_amount
        if preparation.operator_restated_amounts
        else operator_value_or_reading(recargo_amount, draft.recargo_amount)
    )
    resolved_iva_category = operator_value_or_reading(iva_category, preparation.establishment.category.category)
    resolved_rectifies = operator_value_or_reading(rectifies_invoice_number, draft.rectifies_invoice_number)
    resolved_series = operator_value_or_reading(series, draft.invoice_series)
    resolved_invoice_class = resolve_invoice_class(
        draft,
        invoice_class=invoice_class,
        rectifies_invoice_number=resolved_rectifies,
    )
    return build_catalogue_invoice(
        bucket_id=bucket_id,
        kind=kind,
        counterparty_name=resolved_counterparty_name,
        counterparty_tax_id=resolved_counterparty_tax_id,
        counterparty_country=counterparty_country,
        invoice_number=resolved_invoice_number,
        issued_at=resolved_invoice_date,
        taxable_base=resolved_taxable_base,
        iva_rate=resolved_iva_rate,
        currency=resolved_currency,
        notes=notes,
        iva_category=resolved_iva_category,
        operation_type=operation_type,
        operation_date=operation_date,
        retention_rate=retention_rate,
        retention_amount=retention_amount,
        invoice_class=resolved_invoice_class,
        series=resolved_series,
        rectifies_invoice_number=resolved_rectifies,
        recargo_amount=resolved_recargo_amount,
        lines=confirmed_lines,
        rate_provider=rate_provider,
    )


def _persist_confirmed_invoice(
    *,
    candidate: Invoice,
    preparation: _InvoiceConfirmationPreparation,
    bucket_id: str,
    evidence_id: str | None,
    confirmed_by: str,
    resolutions: Sequence[FindingResolution],
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None,
) -> InvoiceConfirmationResult:
    """Apply idempotency, link evidence, and persist the confirmation record."""
    from .confirmation_record import re_stamped_provenance

    repository = invoice_repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    attachment_store = AttachmentStore(objects=secure_object_repository_for_bucket(bucket_id, preparation.settings))
    catalogue = repository.load()
    already_minted = _prior_invoices_this_document_minted(
        attachment_store,
        attachment_id=preparation.attachment_id,
        catalogue=catalogue,
        candidate_invoice_id=candidate.invoice_id,
    )
    if already_minted:
        _refuse_a_divergent_reconfirm(
            candidate=candidate,
            prior=already_minted[0],
            attachment_id=preparation.attachment_id,
        )
    existing = catalogue.get(candidate.invoice_id)
    if existing is not None:
        if _fields_a_reconfirm_would_change(candidate, existing):
            _refuse_a_divergent_reconfirm(
                candidate=candidate,
                prior=existing,
                attachment_id=preparation.attachment_id,
            )
        link_attachment_invoice(
            attachment_store,
            attachment_id=preparation.attachment_id,
            invoice_id=existing.invoice_id,
        )
        existing_record = _written_confirmation_record(
            bucket_id=bucket_id,
            invoice_id=existing.invoice_id,
            evidence_id=evidence_id,
            attachment_id=preparation.attachment_id,
            draft=preparation.draft,
            confirmed_by=confirmed_by,
            overrides=preparation.operator_overrides,
            blockers=preparation.blockers,
            resolutions=resolutions,
            settings=preparation.settings,
        )
        return InvoiceConfirmationResult(
            invoice=existing,
            draft=preparation.draft,
            created=False,
            confirmation_id=existing_record.confirmation_id,
            confirmed_provenance=re_stamped_provenance(
                draft=preparation.draft,
                assertions=existing_record.assertions,
            ),
            total_discrepancy=printed_total_discrepancy(draft=preparation.draft, invoice=existing),
            establishment=preparation.establishment,
        )
    result = create_catalogue_invoice(invoice=candidate, repository=repository)
    link_attachment_invoice(
        attachment_store,
        attachment_id=preparation.attachment_id,
        invoice_id=result.invoice.invoice_id,
    )
    confirmation_record = _written_confirmation_record(
        bucket_id=bucket_id,
        invoice_id=result.invoice.invoice_id,
        evidence_id=evidence_id,
        attachment_id=preparation.attachment_id,
        draft=preparation.draft,
        confirmed_by=confirmed_by,
        overrides=preparation.operator_overrides,
        blockers=preparation.blockers,
        resolutions=resolutions,
        settings=preparation.settings,
    )
    return InvoiceConfirmationResult(
        invoice=result.invoice,
        draft=preparation.draft,
        created=True,
        total_discrepancy=printed_total_discrepancy(draft=preparation.draft, invoice=result.invoice),
        confirmation_id=confirmation_record.confirmation_id,
        confirmed_provenance=re_stamped_provenance(
            draft=preparation.draft,
            assertions=confirmation_record.assertions,
        ),
        establishment=preparation.establishment,
    )


def confirm_invoice_draft_from_evidence(
    *,
    bucket_id: str,
    kind: InvoiceKind,
    counterparty_country: str,
    evidence_id: str | None = None,
    attachment_id: str | None = None,
    counterparty_tax_id: str | None = None,
    counterparty_name: str | None = None,
    invoice_number: str | None = None,
    invoice_date: date | None = None,
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    currency: str | None = None,
    iva_amount: Decimal | None = None,
    iva_category: IvaCategory | None = None,
    operation_type: IntracomOperationType | None = None,
    operation_date: date | None = None,
    retention_rate: Decimal | None = None,
    retention_amount: Decimal | None = None,
    recargo_amount: Decimal | None = None,
    invoice_class: InvoiceClass | None = None,
    supply_nature: SupplyNature | None = None,
    series: str | None = None,
    rectifies_invoice_number: str | None = None,
    notes: str = "",
    resolutions: Sequence[FindingResolution] = (),
    confirmed_by: str = "operator",
    settings: Settings | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    rate_provider: ExchangeRateProvider | None = None,
) -> InvoiceConfirmationResult:
    """Re-extract one evidence reference and confirm it into a real :class:`Invoice`.

    Re-runs :func:`extract_invoice_draft_from_evidence` on-host (bytes and text
    stay in memory only), then layers any operator-supplied override on top of
    each extracted field -- extraction is best-effort, so every field may be
    corrected before the record is minted. The resulting identity fields are
    handed to :func:`~application.invoices.create_catalogue_invoice`, the
    single sanctioned :class:`Invoice` writer
    (``aeat-architecture-boundaries``); this function never
    writes the catalogue itself.

    Idempotent-guarded (``aeat-cli-contract``): the
    persisted :attr:`~domain.invoices.Invoice.invoice_id` is a stable hash of
    ``(kind, invoice_number, issued_at, counterparty_tax_id, currency,
    grand_total)`` — a confirm carrying identical resolved fields to an
    already-persisted invoice returns that invoice unchanged
    (``created=False``, no new bucket write); a confirm whose resolved fields
    genuinely differ mints a distinct invoice record rather than overwriting.

    Args:
        bucket_id: Active ledger bucket the evidence belongs to.
        kind: Invoice direction (``issued`` or ``received``). The operator's
            statement is the decision. The document is also asked -- the reading
            stage derives which party's block prints the filer's own identifier
            and stamps a suggestion -- and a document that settles a direction
            contradicting this one raises a resolvable
            :attr:`~core.DraftDiscrepancyKind.DIRECTION_CONTRADICTED` blocker
            rather than being overridden or silently accepted.
        counterparty_country: ISO 3166-1 alpha-2 counterparty country code.
            Defaults to ``"ES"``; override for a non-Spanish counterparty.
        evidence_id: A ``purchase_invoice_evidence`` record id, or ``None``.
        attachment_id: A linked attachment id, or ``None``. Exactly one of
            *evidence_id* / *attachment_id* must be supplied.
        counterparty_tax_id: Override for the extracted supplier tax id.
        counterparty_name: Override (there is no extraction heuristic for the
            counterparty's display name yet, so this is normally required).
        invoice_number: Override for the extracted invoice number.
        invoice_date: Override for the extracted invoice date.
        taxable_base: Override for the extracted taxable base.
        iva_rate: Override for the extracted IVA rate (``None`` resolves to
            the EXEMPT slot, matching :func:`build_catalogue_invoice`).
        currency: ISO-4217 currency code overriding the extracted one.
            When omitted, the currency printed on the document is used,
            falling back to euro only when the document shows none.
        iva_amount: The cuota PRINTED on the document, when it differs from
            base times rate. A printed figure is evidence and outranks a
            recomputed one, so supplying it makes the persisted line carry it
            exactly. The line invariants still apply, so a cuota the base and
            rate cannot support refuses rather than overriding them.
        iva_category: IVA treatment of the operation. Required for the renta
            income lane to ground the record.
        operation_type: Modelo 349 clave for an entrega intracomunitaria. The
            category alone cannot distinguish an ordinary supply (clave E) from
            one following an exempt importation (clave M, or H through a fiscal
            representative), and no document states which -- so the writer
            demands it and only the operator can answer. Without this the
            evidence path could confirm no intra-community invoice at all.
        operation_date: Date the operation was performed, when it differs from
            the issue date, letting the record reach a declared devengo rank.
        retention_rate: RIRPF art. 95 withholding fraction, settled OUTSIDE
            the invoice total.
        retention_amount: The withheld figure. Accepted alone; required
            whenever a rate is supplied.
        recargo_amount: Recargo de equivalencia (LIVA art. 161), which rides
            INSIDE the invoice total, unlike a retención.
        supply_nature: The operator's statement of whether the supply is goods
            or services. Demanded only where the law forks on it -- the
            cross-border and reverse-charge families -- so an ordinary domestic
            invoice never needs one, and supplying it there changes nothing.
            Until this parameter existed the classifier could REPORT that gap
            and the operator had no way to answer it, so a cross-border
            document with no printed statutory citation reached a category of
            ABSENT with no route forward.
        invoice_class: Invoice class. A rectificativa also needs
            ``rectifies_invoice_number``.
        series: Invoice numbering series, when the issuer uses one.
        rectifies_invoice_number: Number of the invoice a rectificativa
            corrects.
        notes: Free-text operator notes carried onto the invoice.
        resolutions: One explicit answer per blocking finding the document
            raises. A document with findings cannot be confirmed until every
            one is answered individually; there is no bulk flag, deliberately.
        confirmed_by: Who is confirming, recorded in the confirmation
            provenance record.
        settings: Resolved ``Settings``; ``load_settings()`` when ``None``.
        invoice_repository: Optional injected
            :class:`InvoiceCatalogueRepositoryProtocol` (testing seam).
        rate_provider: The euro-conversion rate source for a foreign-currency
            document. ``None`` uses the bundled ECB reference-rate provider,
            which is the production path. Injectable because confirming a
            foreign invoice otherwise reaches the ECB Data Portal over the
            network, so the conversion policy could not be exercised without
            it; a euro document never consults it at all.

    Returns:
        :class:`InvoiceConfirmationResult`: The persisted (or pre-existing)
        invoice, the re-run draft it was checked against, and whether this
        call minted a new record.

    Raises:
        PurchaseInvoiceEvidenceInputError: When neither or both of
            *evidence_id* / *attachment_id* are supplied, when *evidence_id*
            resolves outside the bytes-bearing evidence-record id space, when the
            resolved evidence has no usable text layer, or when a required field
            is ``None`` after overrides (extraction found nothing and the
            operator supplied no override).
        InvoiceValidationError: When the resolved fields fail invoice-model
            validation (e.g. an invalid counterparty tax id or IVA rate).
        ConfirmationBlockedError: When the document raises a blocking finding
            that carries no explicit per-finding resolution.
    """
    preparation = _prepare_invoice_confirmation(
        bucket_id=bucket_id,
        kind=kind,
        evidence_id=evidence_id,
        attachment_id=attachment_id,
        counterparty_country=counterparty_country,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        supply_nature=supply_nature,
        settings=settings,
        resolutions=resolutions,
        counterparty_tax_id=counterparty_tax_id,
        counterparty_name=counterparty_name,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        currency=currency,
        retention_rate=retention_rate,
        retention_amount=retention_amount,
        recargo_amount=recargo_amount,
    )
    candidate = _build_confirmed_invoice_candidate(
        bucket_id=bucket_id,
        kind=kind,
        counterparty_country=counterparty_country,
        counterparty_tax_id=counterparty_tax_id,
        counterparty_name=counterparty_name,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        currency=currency,
        iva_category=iva_category,
        operation_type=operation_type,
        operation_date=operation_date,
        retention_rate=retention_rate,
        retention_amount=retention_amount,
        recargo_amount=recargo_amount,
        invoice_class=invoice_class,
        supply_nature=supply_nature,
        series=series,
        rectifies_invoice_number=rectifies_invoice_number,
        notes=notes,
        rate_provider=rate_provider,
        preparation=preparation,
    )
    return _persist_confirmed_invoice(
        candidate=candidate,
        preparation=preparation,
        bucket_id=bucket_id,
        evidence_id=evidence_id,
        confirmed_by=confirmed_by,
        resolutions=resolutions,
        invoice_repository=invoice_repository,
    )
