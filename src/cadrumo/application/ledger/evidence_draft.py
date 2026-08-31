"""On-host invoice-document reading into a typed draft.

Holds the draft record set -- :class:`InvoiceDraft` with its per-field
:class:`FieldProvenance` envelopes -- and the routing layer that decides which
reader a given document is handed to. It never persists an
:class:`~domain.invoices.Invoice` and never guesses a value no reader could
ground in the document: every field a reader could not recover is left ``None``
rather than fabricated (``no-silent-under-declaration`` in spirit: an unconfident
field is absent, not invented).

Three reading paths, chosen on the document's own shape rather than on its
stored MIME type:

- A **structured** e-invoice (Facturae, CII, UBL) is read exactly by
  :func:`~adapters.inbound.einvoice.parse_einvoice_document`. It reaches no model
  at all, so prompt injection is categorically impossible for that document
  rather than merely mitigated, and it is the only path that can recover the
  document's own line decomposition and per-rate breakdown.
- A **text-native PDF** is transcribed by
  :func:`~application.ledger.evidence_textlayer.transcribe_text_layer`, read semantically by
  :func:`~llm.extract_invoice_fields_from_text`, and then grounded against that
  same transcription by
  :func:`~application.ledger.grounded_reading.ground_draft_against_transcription`. The
  transcription is produced by a DIFFERENT reader than the one that proposes
  values, which is what makes the anchor check an external check rather than a
  model confirming itself.
- A **scan-only PDF or image** has nothing to transcribe, so it falls back to the
  on-host LOCAL vision reader (:mod:`~llm.evidence_draft_vision`) -- the same
  rasterise-then-read-with-Ollama transport
  :class:`~llm.vision_classifier.LocalVisionLLMClassifier` already uses for
  classification, gated by :attr:`~core.ServiceCapability.LLM_VISION` and never a
  cloud call.

The escalation is one-directional and the asymmetry is deliberate. A document
with no text layer genuinely needs a reader that works on pixels, so it escalates.
A readable document whose semantic reader is absent or unreachable is an
ENVIRONMENT failure, so it REFUSES in the operator's face rather than silently
running a heavier engine they did not ask for -- see
:func:`_refuse_a_text_read_with_no_reader`. A profile that has opted out of vision
reading likewise gets a typed, instructive refusal, never a silent empty draft.

Everything here runs on-host and in-memory only. The evidence bytes, the
transcription and the draft never touch disk and are never sent to a cloud
provider. This module performs no filesystem write.

:func:`~application.ledger.evidence_draft.extract_invoice_draft_from_evidence` is the CLI-facing
wiring layer: it resolves an already-stored ``purchase_invoice_evidence`` record
or a linked ``attachment_id`` to its in-memory bytes (through the private
evidence-input resolvers
:func:`~application.ledger.evidence_input.resolve_purchase_invoice_evidence_input`
and
:func:`~application.ledger.evidence_input.resolve_attachment_evidence_input`) and
routes them to one of the three readers above, so
``aeat app ledger evidence extract`` needs only a bucket id plus one of the two
reference ids.

:func:`~application.ledger.evidence_draft.confirm_invoice_draft_from_evidence` is the
non-interactive CONFIRM step that closes the review loop: it re-runs the on-host
extraction, applies any operator-supplied field overrides (extraction is
best-effort -- every field may be corrected), and delegates the actual write to
:func:`~application.invoices.create_catalogue_invoice` -- the sole sanctioned
:class:`~domain.invoices.Invoice` writer
(``aeat-architecture-boundaries``). A confirm keyed on the same
evidence/attachment reference and the same resolved fields is a guarded no-op
that returns the existing invoice rather than raising or duplicating
(``aeat-cli-contract``); a same-reference confirm
whose resolved fields genuinely differ from the already-stored invoice mints a
second, distinct invoice record (a different content-derived
:attr:`~domain.invoices.Invoice.invoice_id`) rather than silently
overwriting one filer's data with another's.

Confirming also auto-links the source evidence to the resulting invoice:
:func:`~domain.attachments.link_attachment_invoice` appends the invoice's id
to the backing :class:`~domain.attachments.Attachment`'s
:attr:`~domain.attachments.Attachment.linked_invoice_ids`, closing the
provenance loop in both directions (the invoice is discoverable from the
evidence, and the evidence is the invoice's traceable source). The link is
re-asserted on a guarded no-op confirm too, so a re-confirm never regresses a
provenance link that was never wired for older evidence, and the append itself
is idempotent (dedup on the linked-ids tuple).

See Also:
    :class:`~application.ledger.evidence_draft.InvoiceDraft`
        Public draft record returned before an invoice is persisted.
    :func:`~application.ledger.evidence_textlayer.transcribe_text_layer`
        Acquisition-stage primitive that turns a text-native PDF into the
        reading-order transcription the semantic reader is handed.
    :func:`~application.ledger.evidence_draft.extract_invoice_draft_from_evidence`
        CLI-facing resolver that loads stored evidence bytes and chooses the
        structured, text-native or on-host vision path.
    :func:`~application.ledger.evidence_draft.confirm_invoice_draft_from_evidence`
        Non-interactive confirm step that re-extracts, applies overrides, and
        delegates the catalogue write.
    :mod:`~llm.evidence_draft_vision`
        On-host vision fallback for scan-only PDFs and image attachments.
    :func:`~application.invoices.create_catalogue_invoice`
        Sole sanctioned writer for the resulting catalogue invoice.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Final, NamedTuple, NoReturn, Self

from pydantic import BaseModel, Field, PrivateAttr, model_validator

from ...adapters.inbound.einvoice import (
    EInvoiceXmlParseError,
    FacturaeInvoiceClass,
    parse_einvoice_document,
)
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.storage import AttachmentStore, secure_object_repository_for_bucket
from ...application.invoices import build_catalogue_invoice, create_catalogue_invoice, resolve_iva_rate_slot
from ...core import (
    PDF_CONTAINER_SHAPES,
    STRUCTURED_DOCUMENT_SHAPES,
    DraftDiscrepancyKind,
    ImageMediaType,
    ServiceCapability,
    detect_image_media_type,
)
from ...core.field_grounding import FieldGroundingOutcome
from ...core.optional_extras import MissingOptionalExtraError
from ...core.field_origin import FieldOrigin
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.aggregation import IntracomOperationType
from ...core.config import Settings
from ...core.config import load_settings as _load_settings
from ...core.external_constants import DEFAULT_CURRENCY, XML_MIME_TYPE
from ...core.identity import ContentDigest, TaxIdIdentityToken, same_tax_identifier
from ...core.logging import get_logger
from ...core.parsing import parse_iso8601_date
from ...domain.attachments.errors import AttachmentNotFoundError
from ...domain.attachments.models import normalize_media_type
from ...domain.attachments.service import link_attachment_invoice
from ...domain.currency.service import ExchangeRateProvider
from ...domain.invoices.enums import InvoiceClass
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.lookup import rate_kinds_for_declared_rate
from ...domain.iva.schema import EUMemberState, IvaCategory, IvaRateKind
from ...domain.iva.supply_nature import SupplyNature
from ...llm.errors import LLMPdfRasterisationError, LLMProviderError
from ...llm.models import MultimodalImageInput
from ...llm.providers.local import rasterise_pdf_pages_to_base64_png
from ..provisioning import probe_ollama_vision
from ..user_profile.capabilities import resolve_active_capability
from .document_transcription import DocumentTranscription
from .evidence import PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceService
from .evidence_input import (
    EvidenceInput,
    resolve_attachment_evidence_input,
    resolve_purchase_invoice_evidence_input,
)
from .evidence_reference import (
    EvidenceReferenceOutcome,
    classify_evidence_reference,
    find_bytes_bearing_evidence_record,
    refuse_reference_without_document_bytes,
    refuse_unresolved_evidence_reference,
)
from .evidence_textlayer import transcribe_text_layer
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

if TYPE_CHECKING:
    from ...llm.consent import EvidenceConsentToken
    from ...llm.models import LLMProvider
    from .confirm_establishment import ConfirmedEstablishment
    from .confirmation_gate import ConfirmationBlocker, FindingResolution
    from .confirmation_record import InvoiceConfirmationRecord

__all__ = [
    "CounterpartyDraftSide",
    "DraftDiscrepancyFinding",
    "FieldAmbiguityCandidate",
    "FieldProvenance",
    "InvoiceConfirmationResult",
    "InvoiceDraft",
    "InvoiceDraftLine",
    "InvoiceDraftRateBreakdown",
    "PrintedTotalDiscrepancy",
    "confirm_invoice_draft_from_evidence",
    "counterparty_draft_side",
    "extract_invoice_draft_from_evidence",
    "printed_total_discrepancy",
]


class InvoiceDraftLine(BaseModel):
    """One line item recovered from a structured invoice document.

    Only a structured reader can populate this: a text or vision reader
    recovers printed totals, not the document's own line decomposition. The
    rate is carried as a bare percentage :class:`~decimal.Decimal` (``21``, not
    ``0.21``) because the draft is pre-confirm operator-facing data; mapping it
    onto the closed ``IvaRate`` slot enum happens at the parse boundary, which
    refuses loudly rather than rounding to the nearest slot.

    Attributes:
        description: Line description as printed, or ``None``.
        quantity: Billed quantity, or ``None`` when the document omits it.
        unit_price: Price per unit before tax, or ``None``.
        taxable_base: Line taxable base before IVA.
        iva_rate: Line IVA percentage as a whole-number Decimal.
        iva_amount: Line IVA cuota, or ``None`` when the document states only
            the rate and lets the total carry the cuota.
        recargo_rate: Recargo de equivalencia percentage, or ``None``.
        recargo_amount: Recargo de equivalencia cuota, or ``None``.
    """

    model_config = STRICT_FROZEN_CONFIG

    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    recargo_rate: Decimal | None = None
    recargo_amount: Decimal | None = None


class InvoiceDraftRateBreakdown(BaseModel):
    """Per-rate tax subtotal as the document itself declares it.

    This is the field that makes the multi-rate silent collapse detectable. A
    draft carrying only the flat ``taxable_base`` / ``iva_rate`` /
    ``iva_amount`` triple structurally cannot represent an invoice charging
    two rates: the two bases sum into one figure and one of the rates is simply
    lost, producing an invoice whose printed total no longer reconciles with
    its declared cuota.

    Attributes:
        iva_rate: The rate this subtotal is charged at, as a whole-number
            percentage Decimal.
        taxable_base: Base charged at this rate.
        iva_amount: Cuota charged at this rate.
        recargo_rate: Recargo de equivalencia percentage for this rate.
        recargo_amount: Recargo de equivalencia cuota for this rate.
    """

    model_config = STRICT_FROZEN_CONFIG

    iva_rate: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    recargo_rate: Decimal | None = None
    recargo_amount: Decimal | None = None


class FieldAmbiguityCandidate(BaseModel):
    """One competing reading a grounding pass could not decide between.

    Recorded rather than resolved. An ambiguity collapsed by taking the first
    match is indistinguishable downstream from a fact, so the candidates travel
    to the operator, who is the only party with the document in front of them.

    Attributes:
        value: The candidate reading, as a string. Deliberately not the field's
            own type: a candidate exists precisely because the value could not
            be established, and coercing an undecided reading into a
            ``Decimal`` or a ``date`` would assert the parse that was in
            question.
        anchor: The verbatim printed form this candidate was read from, or
            ``None`` when the candidate is a normalisation of another reading
            rather than a distinct occurrence.
        note: Why this candidate competed, in operator-facing terms.
    """

    model_config = STRICT_FROZEN_CONFIG

    value: str
    anchor: str | None = None
    note: str = ""


class FieldProvenance(BaseModel):
    """The provenance envelope for exactly one field of a draft.

    Per FIELD, not per document. A draft is routinely assembled from several
    readers -- a structured record for the parties, an arithmetic derivation for
    a cuota, an operator correction at confirm -- so a single document-level
    stamp would claim one origin for values that did not share one. That is the
    laundering this record exists to prevent: an exactly-read value must stay
    distinguishable from a model-read one all the way to the operator's screen.

    Carries no numeric confidence, deliberately and permanently. See
    :class:`~core.FieldOrigin` and :class:`~core.FieldGroundingOutcome` for the
    two axes that are facts: how the value was obtained, and what checking it
    survived.

    Attributes:
        field: Name of the :class:`InvoiceDraft` field this envelope describes.
            Validated against the draft's own fields rather than a hand-listed
            enum, so a renamed or removed draft field invalidates its stale
            envelopes instead of leaving them pointing at nothing.
        origin: How the value was obtained.
        grounding: What verification the value passed, or failed.
        anchor: The verbatim printed form the value was read from, exactly as it
            appears in the source -- ``"1.234,56 €"``, not ``1234.56``. This is
            the whole anti-fabrication mechanism: a value nobody can point at in
            the document has ``None`` here and an ``UNANCHORED`` outcome, and
            the operator sees both.
        candidates: Competing readings, when the grounding outcome is
            ``AMBIGUOUS``. Empty otherwise.
        refused_anchor: The printed form the reader DID offer, kept here when the
            check looked for it and the document does not carry it. The anchor
            field is cleared on that outcome, deliberately -- a form the document
            does not print is not evidence, and every consumer reading
            :attr:`anchor` reads it as evidence. Clearing it alone, though,
            leaves a refused claim indistinguishable from an absent one, and the
            two are different operator situations: a reader that offered nothing
            is a reader limitation, while a reader that offered something the
            document does not carry is a possible misread or the wrong document
            entirely. So the refused form is preserved HERE, where nothing can
            mistake it for a corroborated one, and the operator surface can say
            which of the two happened. ``None`` whenever no check ran or the
            anchor was found.
        anchor_self_reported: ``True`` when the anchor was asserted by the same
            reader that produced the value, with nothing independent to check it
            against -- the vision lane, which reads image to fields in one call
            and has no transcription. Such an anchor is recorded because it is
            still useful to an operator, but it can never carry an ``ANCHORED``
            outcome; see the validator below.
        role_evidence: For an identity field, the printed context the reader
            copied that assigns this value to its party role -- a heading, a
            label, the line the identifier sits under. ``None`` where the
            document showed nothing that does, and on every field that names no
            party. This is a SECOND anchor rather than a note: it is a printed
            excerpt, so it is checkable against the transcription exactly the
            way :attr:`anchor` is, and it is only trusted once that check has
            run. The reader's own account of what it did ("I assigned this to
            supplier_tax_id") is not role evidence and must never be recorded
            here -- always-truthy text in this slot permanently satisfies the
            guard that exists to refuse an unevidenced identity, which is a
            measured defect rather than a hypothetical one.
        attribution_unverified: ``True`` when nothing checked WHICH PARTY this
            value belongs to. Party attribution is its own axis, distinct from
            whether the value was read correctly: a postal code can be copied
            perfectly off the page and still be filed under the wrong party,
            and every anchor check in this record would pass. Role evidence
            answers the attribution question for the identity fields, and the
            document's own record answers it for a structured read, where the
            element path names the party. For a model-read address value there
            is no such answer today -- the reader's assignment is final and
            unchecked -- so the value is stamped here and the operator is told.
            Per FIELD for the same reason everything else on this envelope is:
            one party's postal code may be attributed while their country is
            not, and a draft-level or party-level flag could not say so. When
            deterministic co-location lands, an attributed value simply stops
            carrying the stamp; nothing here changes shape.
        note: Operator-facing explanation, e.g. which identity contradicted the
            value.
    """

    model_config = STRICT_FROZEN_CONFIG

    field: str = Field(min_length=1)
    origin: FieldOrigin
    grounding: FieldGroundingOutcome
    anchor: str | None = None
    refused_anchor: str | None = None
    candidates: tuple[FieldAmbiguityCandidate, ...] = ()
    anchor_self_reported: bool = False
    derived_from: tuple[str, ...] = ()
    role_evidence: str | None = None
    attribution_unverified: bool = False
    note: str = ""

    @model_validator(mode="after")
    def _a_derived_value_cites_its_inputs_and_never_an_anchor(self) -> Self:
        """Tie ``DERIVED`` to the inputs it followed from, and bar it from ANCHORED.

        A derived value was never on the page, so there is nothing in the
        document to point at and an ``ANCHORED`` stamp would assert a printed
        form that does not exist. What an auditor needs instead is the input
        set: the derivation is deterministic, so naming its inputs makes the
        conclusion reproducible by hand, which is the derived equivalent of
        showing the anchor.

        Enforced in both directions, for the same reason the ambiguity rule is.
        A ``DERIVED`` envelope with no inputs claims a conclusion it cannot show
        its working for, and inputs recorded under any other origin describe a
        derivation that did not happen.
        """
        if self.origin is FieldOrigin.DERIVED:
            if self.grounding is FieldGroundingOutcome.ANCHORED:
                raise ValueError(
                    "a derived value cannot be ANCHORED: it was concluded from other values rather "
                    "than read from the document, so no printed form anchors it",
                )
            if not self.derived_from:
                raise ValueError("a derived value must record the inputs it was derived from")
        elif self.derived_from:
            raise ValueError(
                f"derived_from is only meaningful for a derived value; got origin={self.origin.value!r}",
            )
        return self

    @model_validator(mode="after")
    def _a_self_reported_anchor_can_never_read_as_verified(self) -> Self:
        """Refuse an ``ANCHORED`` outcome on an anchor nothing independent confirmed.

        The two reading lanes do not supply the same STRENGTH of evidence, and
        collapsing them is how an anti-fabrication check becomes decoration.

        On the text lane the anchor is matched against a transcription produced
        by a different reader than the one that proposed the value, so the match
        is a genuine external check. On the vision lane there is no transcription
        at all -- the model reads image to fields in one call -- so the anchor is
        the model's own claim about what it saw. Matching that claim against the
        model's own reply confirms only that the model is self-consistent, which
        a fabricating model also is.

        Enforcing the invariant HERE rather than in the checker means no reading
        path can launder a self-reported anchor into a verified-looking one, even
        by constructing the envelope directly. When a vision transcription stage
        lands, that path stops setting this flag and earns ``ANCHORED`` through
        the same check the text lane already passes -- no change to this rule.
        """
        if self.anchor_self_reported and self.grounding is FieldGroundingOutcome.ANCHORED:
            raise ValueError(
                "a self-reported anchor cannot be ANCHORED: the anchor was asserted by the same "
                "reader that produced the value, so nothing independent confirmed it",
            )
        return self

    @model_validator(mode="after")
    def _ambiguity_carries_its_candidates(self) -> Self:
        """Tie the ``AMBIGUOUS`` outcome to the candidates that justify it.

        Both directions are enforced. An ``AMBIGUOUS`` envelope with fewer than
        two candidates asserts an ambiguity it cannot show, and candidates under
        any other outcome record competing readings while claiming the field was
        decided -- each is a stamp that says something the record does not
        support.
        """
        if self.grounding is FieldGroundingOutcome.AMBIGUOUS:
            if len(self.candidates) < 2:
                raise ValueError("an ambiguous field must record at least two competing candidates")
        elif self.candidates:
            raise ValueError(
                f"candidates are only meaningful for an ambiguous field; got grounding={self.grounding.value!r}",
            )
        return self

    @model_validator(mode="after")
    def _anchor_matches_the_outcome(self) -> Self:
        """Refuse an ``ANCHORED`` claim with no anchor to show for it."""
        if self.grounding is FieldGroundingOutcome.ANCHORED and self.anchor is None:
            raise ValueError("an anchored field must carry the verbatim anchor it was anchored to")
        return self

    @model_validator(mode="after")
    def _a_refused_anchor_is_never_also_a_carried_one(self) -> Self:
        """Keep the refused form out of every slot a consumer reads as evidence.

        Both directions, for the reason the sibling rules are two-directional. An
        envelope carrying the same claim in both slots would let a consumer that
        reads :attr:`anchor` treat a refused form as a located one, which is the
        laundering clearing the anchor exists to prevent. And a refused anchor
        under a grounding outcome that means the check PASSED describes a
        verdict that did not happen: the check cannot both locate the form and
        report it absent.
        """
        if self.refused_anchor is None:
            return self
        if self.anchor is not None:
            raise ValueError(
                "an anchor cannot be both carried and refused: the refused form is recorded only "
                "because the check did not locate it, so nothing may read it as evidence",
            )
        if self.grounding in {FieldGroundingOutcome.ANCHORED, FieldGroundingOutcome.RECONCILED}:
            raise ValueError(
                f"a refused anchor cannot sit under grounding={self.grounding.value!r}: the check "
                "reported the printed form absent, so it did not corroborate the value",
            )
        return self


class DraftDiscrepancyFinding(BaseModel):
    """One deterministic check the read document failed.

    Distinct from :class:`PrintedTotalDiscrepancy`, which compares the document
    against the invoice that was actually WRITTEN and therefore only exists at
    confirm. This record is a finding about the document alone, available the
    moment it is read, so the operator meets it during review rather than after
    a record has been minted from it.

    Attributes:
        kind: Which identity failed.
        field: The draft field the finding is about, or ``None`` when the
            finding is about a relationship between several.
        detail: Operator-facing explanation naming the figures involved.
        expected: What the identity required, when the check is arithmetic.
        observed: What the document stated instead.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: DraftDiscrepancyKind
    field: str | None = None
    detail: str = ""
    expected: Decimal | None = None
    observed: Decimal | None = None


def _facturae_invoice_class_findings(
    *,
    declared: FacturaeInvoiceClass | None,
    rectifies_invoice_number: str | None,
) -> tuple[DraftDiscrepancyFinding, ...]:
    """Report Facturae class gaps and contradictions without choosing a side."""
    if declared is None:
        return ()

    findings: list[DraftDiscrepancyFinding] = []
    if declared in {FacturaeInvoiceClass.ORIGINAL_SUMMARY, FacturaeInvoiceClass.COPY_SUMMARY}:
        findings.append(
            DraftDiscrepancyFinding(
                kind=DraftDiscrepancyKind.INVOICE_CLASS_UNMODELLED,
                detail=f"Facturae InvoiceClass {declared.value!r} declares recapitulativa, which is not modelled",
            ),
        )

    declares_correction = declared in {
        FacturaeInvoiceClass.ORIGINAL_CORRECTIVE,
        FacturaeInvoiceClass.COPY_CORRECTIVE,
    }
    carries_correction = rectifies_invoice_number is not None
    if declares_correction != carries_correction:
        findings.append(
            DraftDiscrepancyFinding(
                kind=DraftDiscrepancyKind.INVOICE_CLASS_CONTRADICTED,
                detail=(
                    f"Facturae InvoiceClass {declared.value!r} and Corrective/InvoiceNumber "
                    f"presence={carries_correction!r} disagree"
                ),
            ),
        )
    return tuple(findings)


class InvoiceDraft(BaseModel):
    """Best-effort invoice fields extracted from an on-host PDF text layer.

    Every field is optional: a field the extractor cannot ground in the
    document's text is left ``None`` rather than guessed. The operator reviews
    this draft and supplies or corrects fields before any
    :class:`~domain.invoices.Invoice` is minted from it -- this model is
    never itself persisted as a filing-grade record.

    Attributes:
        supplier_tax_id: Canonical Spanish NIF / NIE / CIF recovered from the
            text, or ``None`` when no valid tax identifier was found.
        supplier_name: The issuing party's stated name, or ``None``.
        customer_tax_id: The receiving party's tax identifier, or ``None``.
            Populated only by a structured reader, which is the only one that
            can tell the two parties apart; a text or vision reader recovers a
            single identifier and cannot say whose it is.
        customer_name: The receiving party's stated name, or ``None``.
        supplier_postal_code: The postal code printed in the issuing party's
            address, copied verbatim, or ``None``. Transcriptive like every
            other copied field: it carries the printed code and never the
            territory read off it. That reading belongs to
            :func:`~domain.iva.territorial_scope_for_spanish_postal_code`,
            which is the deterministic evidence separating the three Spanish
            IVA territories -- the first two digits of a Spanish code are the
            province -- and which refuses an unreadable code rather than
            defaulting it to the peninsula.
        customer_postal_code: The same for the party billed by the invoice.
            Carried separately because establishment is asked of each party
            independently: an issuer in Las Palmas invoicing a customer in
            Madrid crosses a territorial boundary that one shared code could
            not express.
        supplier_country: The country NAME printed in the issuing party's
            address, copied verbatim in whatever language the document set it,
            or ``None``. Never an alpha-2 code: a country prints as
            "Alemania", "Deutschland" or "Allemagne", so recording a code would
            mean the reading stage translated, and translation is inference.
            The match against the bounded vocabulary belongs to
            :func:`~domain.iva.country_code_for_printed_country_name`, which is
            a deterministic lookup rather than a judgement.
        customer_country: The same for the party billed by the invoice, carried
            separately for the reason the postal codes are: an issuer in Las
            Palmas billing a customer in Berlin cannot be expressed by one
            shared field.
        supplier_country_code: The country code the issuing party's address
            states, as an ISO 3166-1 alpha-2 code, or ``None``. Populated only
            by the structured reader: a machine-readable record states the
            country as a CODE, where a printed document states it as a name and
            asking a reader for the code would be asking it to translate.
            Carried beside the postal code because the two answer different
            halves of one question -- the country says which State, the postal
            code separates the three Spanish IVA territories inside it.

            **Alpha-2 even where the document stated alpha-3.** Facturae states
            ``ESP`` and UBL states ``ES``; both arrive here in the single form
            every country surface downstream is keyed by, resolved through the
            registry correspondence in
            :func:`~domain.iva.country_code_for_stated_country_code`. Normalising
            at the boundary rather than downstream is what keeps a Facturae
            document from failing an alpha-2 shape check in silence, with its
            country element present, read, and establishing nothing.

            The translated form is deliberately NOT anchorable in a Facturae
            record, and that falls out rather than being asserted: the anchor
            check looks for the value as a whole token in the document's own
            text, and ``ES`` is not a token in a record that states ``ESP``. So
            a stated alpha-2 arrives ANCHORED and a translated one UNANCHORED,
            which is the honest distinction between what a document said and
            what was derived from it.
        customer_country_code: The same for the party billed by the invoice,
            carried separately for the reason the postal codes are: a supplier
            in Barcelona invoicing a customer in Lisbon states two countries.
        supplier_stated_country_code: The country token the issuing party's
            address element carries, EXACTLY as the record states it -- ``ESP``
            from Facturae, ``ES`` from UBL, ``THA`` from a Thai supplier's
            Facturae invoice -- or ``None`` where the record's country element
            was absent or empty.

            **This is the field that keeps "stated something we cannot place"
            distinguishable from "stated nothing".** The resolved code beside it
            is contracted alpha-2 and resolves only through the bundled
            vocabulary, so a token that vocabulary does not carry leaves it
            ``None`` -- byte-identical to a document with no country element at
            all. That collapse reached the operator: no value, no provenance
            envelope, and the country advisory reading an empty field and
            staying silent. A genuine Thai export therefore arrived carrying no
            country and nothing said so.

            Carried verbatim rather than normalised, and never coerced towards
            the alpha-2 contract: ``THA`` is not an alpha-2 code and putting it
            in a field typed as one would trade a silent absence for a silent
            lie. Consumers that need a country ask the resolved field; consumers
            that need to know what the DOCUMENT said ask this one.
        customer_stated_country_code: The same for the party billed by the
            invoice, carried separately for the reason every other party field
            is: each side states its own country and either may be the one the
            vocabulary cannot place.
        invoice_number: Invoice number recovered from a labelled line, or
            ``None``.
        invoice_series: The series half of the invoice's identity, stated
            separately by Facturae as ``InvoiceSeriesCode``, or ``None``. Kept
            beside the number rather than concatenated into it: composing the
            printed reference from the two is always possible, while splitting a
            composed string back into them is not.
        invoice_date: Day-first invoice date recovered from the text, or
            ``None``.
        taxable_base: Labelled "base imponible" amount, or ``None``.
        iva_rate: IVA percentage recovered from a "IVA NN%" label, expressed
            as a whole-number :class:`~decimal.Decimal` (e.g. ``21``), or
            ``None``.
        iva_amount: Labelled IVA cuota amount, or ``None``.
        grand_total: Labelled invoice total amount, or ``None``.
        regime_legend: The statutory mention the document prints to state that
            a special regime applies (RD 1619/2012 art. 6.1), copied verbatim,
            or ``None`` when the document prints none. Transcriptive and
            anchorable like every other copied field: it carries what the paper
            says, never a category derived from it. The derivation belongs to
            the deterministic classifier downstream, because an
            :class:`~domain.iva.IvaCategory` token is printed on no invoice and
            a reading stage asked for one would have to infer.
        currency: ISO-4217 code for the currency the amounts are printed in,
            or ``None`` when the document shows no currency marker. Left
            ``None`` rather than defaulted to euro: a foreign-currency
            invoice silently read as euro would carry its face value into a
            filing unconverted, so an absent marker must stay absent and be
            resolved by the operator.
        retencion_rate: IRPF retención percentage as a whole-number Decimal, or
            ``None``. Carried beside the amount rather than derived from it: a
            document may print either, and deriving the missing half would
            manufacture a figure the document does not state.
        retencion_amount: IRPF withheld at source. Subtracted from the total to
            reach the cash actually paid, so a draft that drops it reconciles
            against the wrong figure.
        suplidos_amount: Sums advanced on the customer's behalf. Outside the
            base imponible by law, so folding them into the base over-declares
            IVA on money that was never the issuer's revenue.
        suggested_kind: Which side of the invoice the filer is on, as the
            reading path SUGGESTS it. Never the decision: the draft is
            deliberately pre-direction data and the direction is decided by the
            operator at confirm, where ``--kind`` selects the counterparty side.
            A suggestion the operator does not act on has no effect.
        transcription_sha256: Content address of the stage-one transcription
            this draft was read from, tying the draft to the exact artefact that
            produced it. The address, never the text: a transcription holds the
            document's readable contents and has exactly one sanctioned durable
            route (:class:`~application.ledger.document_transcription.DocumentTranscription`), so
            embedding it here would open a second one.
        provenance: One :class:`FieldProvenance` envelope per field the reading
            path established. Absent for a field means no envelope was recorded,
            which is itself reviewable -- it never means the value was exact.
        discrepancies: Deterministic checks the document failed, available at
            read time rather than at confirm.
        raw_text_length: Length of the on-host extracted text, kept as an
            honest signal of how much source material the heuristics had to
            work with (zero means the PDF carried no usable text layer for
            this evidence and the operator should route to the on-host vision
            reader instead).
    """

    model_config = STRICT_FROZEN_CONFIG

    supplier_tax_id: TaxIdIdentityToken | None = None
    supplier_name: str | None = None
    customer_tax_id: TaxIdIdentityToken | None = None
    customer_name: str | None = None
    supplier_postal_code: str | None = None
    customer_postal_code: str | None = None
    supplier_country: str | None = None
    customer_country: str | None = None
    supplier_country_code: str | None = None
    customer_country_code: str | None = None
    supplier_stated_country_code: str | None = None
    customer_stated_country_code: str | None = None
    invoice_number: str | None = None
    invoice_series: str | None = None
    rectifies_invoice_number: str | None = None
    proposed_supply_nature: SupplyNature | None = None
    """A model's PROPOSAL about goods-or-services, for a person to accept or discard.

    Carried on the draft rather than inside the extracted fields because it is a
    JUDGEMENT and not a transcription: it has no printed form to anchor to, and
    the anchor check the extraction contract rests on would have nothing to
    point at. Folding it in would put an unanchorable value inside the model
    whose whole guarantee is that values are copied.

    ``None`` is the ordinary state. It is populated only when the operator asked
    for a proposal, and never reaches the classifier by itself -- the value that
    does is the one they state at confirm, which is why the classifier's inputs
    stay facts.
    """
    invoice_date: str | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    grand_total: Decimal | None = None
    currency: str | None = None
    regime_legend: str | None = None
    recargo_amount: Decimal | None = None
    retencion_rate: Decimal | None = None
    retencion_amount: Decimal | None = None
    suplidos_amount: Decimal | None = None
    lines: tuple[InvoiceDraftLine, ...] = ()
    iva_breakdown: tuple[InvoiceDraftRateBreakdown, ...] = ()
    iva_category: str | None = None
    suggested_kind: InvoiceKind | None = None
    transcription_sha256: ContentDigest | None = None
    provenance: tuple[FieldProvenance, ...] = ()
    discrepancies: tuple[DraftDiscrepancyFinding, ...] = ()
    raw_text_length: int = 0
    _facturae_invoice_class: FacturaeInvoiceClass | None = PrivateAttr(default=None)

    @property
    def facturae_invoice_class(self) -> FacturaeInvoiceClass | None:
        """Return the structured reader's document-class fact, when present."""
        return self._facturae_invoice_class

    def set_facturae_invoice_class(self, value: FacturaeInvoiceClass | None) -> None:
        """Attach the structured reader's document-class fact to this draft."""
        self._facturae_invoice_class = value

    @model_validator(mode="after")
    def _provenance_names_real_fields(self) -> Self:
        """Refuse an envelope naming a field this draft does not have.

        The provenance tuple is keyed by field NAME rather than by a parallel
        enum on purpose: an enum would be a second declaration of the draft's
        own shape and would drift the first time a field is renamed, leaving
        envelopes that validate while describing nothing. Validating against
        ``model_fields`` cannot drift, because there is only one declaration.

        Duplicates are refused for the same reason an ambiguity is: two
        envelopes for one field are two provenance claims, and nothing
        downstream can say which is the record's answer.
        """
        seen: set[str] = set()
        for envelope in self.provenance:
            if envelope.field not in type(self).model_fields:
                known = ", ".join(sorted(type(self).model_fields))
                raise ValueError(
                    f"provenance names unknown draft field {envelope.field!r}; known fields are: {known}",
                )
            if envelope.field in seen:
                raise ValueError(f"provenance carries two envelopes for field {envelope.field!r}")
            seen.add(envelope.field)
        return self


def extract_invoice_draft_from_evidence(
    *,
    bucket_id: str,
    evidence_id: str | None = None,
    attachment_id: str | None = None,
    settings: Settings | None = None,
    off_host_provider: LLMProvider | None = None,
    consent_token: EvidenceConsentToken | None = None,
) -> InvoiceDraft:
    """Resolve one stored evidence reference to bytes and extract its :class:`InvoiceDraft`.

    The CLI-facing wiring layer over the three readers: given
    either a ``purchase_invoice_evidence`` id (looked up through
    :class:`PurchaseInvoiceEvidenceService`) or a linked ``attachment_id``,
    reads the evidence's bytes from secure storage into memory
    (the private evidence-input resolvers
    :func:`~application.ledger.evidence_input.resolve_purchase_invoice_evidence_input`
    and
    :func:`~application.ledger.evidence_input.resolve_attachment_evidence_input`)
    and routes them to the reader the document's shape selects. Exactly one of *evidence_id* /
    *attachment_id* must be supplied.

    Nothing is written to disk and nothing leaves the host: the resolved
    bytes and the extracted text stay in process memory for the duration of
    this call (``sensitive-financial-data-secure-storage-only``).

    Args:
        bucket_id: Active ledger bucket the evidence or attachment belongs to.
        evidence_id: A ``purchase_invoice_evidence`` record id, or ``None``.
        attachment_id: A linked attachment id, or ``None``.
        settings: Resolved ``Settings``. When ``None``, ``load_settings()`` is
            used so test overrides via ``override_settings()`` are honoured.
        off_host_provider: Provider to route the MODEL-BEARING stages at, or
            ``None`` for the on-host default. Widening this signature does not
            widen the boundary: the refusal lives below this function, at the
            client's single dispatch point, so a caller naming a cloud provider
            without a token is refused there rather than trusted here.
        consent_token: Per-invocation off-host consent proof, minted through
            :func:`~llm.mint_evidence_consent_token`. ``None`` is correct for
            every on-host read.

    Returns:
        :class:`InvoiceDraft`: The best-effort extracted fields, for operator
        review. Never itself persisted as an :class:`~domain.invoices.Invoice`.

    Raises:
        PurchaseInvoiceEvidenceInputError: When neither or both of
            *evidence_id* / *attachment_id* are supplied, when *evidence_id*
            resolves outside the bytes-bearing evidence-record id space (a
            catalogue-invoice id carries fiscal totals, not a document), when the
            resolved evidence's media type is unsupported, or when a scan-only
            PDF / image falls back to the on-host vision reader and that reader
            is disabled for the profile or the local Ollama runtime is
            unreachable.
    """
    if (evidence_id is None) == (attachment_id is None):
        raise PurchaseInvoiceEvidenceInputError(
            translated_message="errors.refused.refused_ledger_evidence_input",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_ATTACHMENT_SELECTION_VALID,
                facts={"exactly_one_evidence_source_supplied": False},
            ),
        )

    resolved_settings = settings or _load_settings()
    # Resolved HERE, once, and handed down. The filer's own identifier is a
    # PROFILE fact, never read off the invoice, and both consumers of it live at
    # the far end of the reading chain: the counterparty role resolution excludes
    # it from candidacy, and the direction derivation asks which party's block
    # prints it. Neither could reach it before, so both were structurally
    # unreachable on the live path however completely they were built.
    filer_tax_id = _active_filer_tax_id()
    store = AttachmentStore(objects=secure_object_repository_for_bucket(bucket_id, resolved_settings))
    if evidence_id is not None:
        # Both id spaces are consulted so the refusal can be precise: only the
        # evidence-record space carries document bytes, but a catalogue-invoice id is
        # a legitimate reference that simply has no document behind it, and must not
        # be reported as a missing record.
        reference = classify_evidence_reference(
            evidence_id,
            bucket_id=bucket_id,
            evidence_records=PurchaseInvoiceEvidenceService(settings=resolved_settings).list_all(bucket_id=bucket_id),
            invoices=InvoiceCatalogueRepository(bucket_id=bucket_id).load(),
        )
        if reference.outcome is EvidenceReferenceOutcome.UNRESOLVED:
            raise refuse_unresolved_evidence_reference(evidence_id)
        if reference.record is None:
            raise refuse_reference_without_document_bytes(evidence_id)
        evidence_input = resolve_purchase_invoice_evidence_input(reference.record, store=store)
    else:
        assert attachment_id is not None  # narrowed by the exactly-one guard above
        evidence_input = resolve_attachment_evidence_input(attachment_id, store=store)

    # Routing order, and the order is itself a control rather than an
    # optimisation: a document carrying a STRUCTURED record is read exactly and
    # reaches no model at all, which makes prompt injection categorically
    # impossible for that document rather than merely mitigated. The decision is
    # made on DocumentShape -- derived from the bytes -- because the stored MIME
    # type answers "pdf" for a ZUGFeRD invoice and a photograph alike, which is
    # how the most machine-readable document in the corpus ended up on the least
    # exact path.
    if evidence_input.document_shape in STRUCTURED_DOCUMENT_SHAPES:
        try:
            return _extract_invoice_fields_from_structured_record(evidence_input)
        except EInvoiceXmlParseError:
            # A malformed structured record refuses rather than yielding a
            # partial one; fall through so a document whose embedded payload is
            # broken can still be read by the text or vision path.
            pass
    _refuse_an_unrecognised_xml_document(evidence_input)
    if evidence_input.document_shape in PDF_CONTAINER_SHAPES:
        # The `try` wraps ONLY the transcription, and that scoping is the whole
        # asymmetry rather than a formatting choice. A failure to transcribe is a
        # statement about the DOCUMENT -- no text layer, scan-only, XFA -- so
        # escalating to a reader that works on pixels is right. Everything after
        # it is a statement about the ENVIRONMENT and must refuse in the
        # operator's face.
        #
        # Wrapping the whole chain instead is a live defect this code already
        # had: the reader refusal raises `PurchaseInvoiceEvidenceInputError`, so
        # a broader `except` swallowed it and silently ran vision on a document
        # whose text layer was perfectly readable -- the exact escalation the
        # refusal exists to prevent, reported to the operator as a vision
        # failure on a text PDF.
        try:
            transcription = transcribe_text_layer(evidence_input)
        except PurchaseInvoiceEvidenceInputError:
            transcription = None
        if transcription is not None:
            return _read_transcription_semantically(
                evidence_input,
                transcription,
                settings=resolved_settings,
                off_host_provider=off_host_provider,
                consent_token=consent_token,
                taxpayer_tax_id=filer_tax_id,
            )
    return _extract_invoice_fields_via_vision(
        evidence_input,
        settings=resolved_settings,
        off_host_provider=off_host_provider,
        consent_token=consent_token,
        taxpayer_tax_id=filer_tax_id,
    )


def _refuse_a_text_read_with_no_reader(exc: Exception) -> NoReturn:
    """Refuse a text-native document the semantic reader could not be run for.

    Deliberately a refusal rather than a fallback, and the distinction is a
    decision rather than an artefact of which exception type happens to be
    caught above.

    A missing or unreachable reader is a statement about the ENVIRONMENT, not
    about the document. Silently escalating to the vision reader would run a
    heavier engine the operator did not ask for, on a document whose text layer
    was perfectly readable -- and would do it invisibly, so the operator could
    not tell why an extract that used to be cheap became slow. The one case
    where escalation IS right is the opposite one, handled above: a document
    with no text layer genuinely needs a reader that works on pixels.

    The refusal carries only application-observed machine facts. Recovery is
    resolved later from the canonical action catalogue; this boundary neither
    invents a command nor copies dependency-owned presentation prose.

    Args:
        exc: The provider or dependency failure that prevented the read.

    Raises:
        PurchaseInvoiceEvidenceInputError: Always.
    """
    _refuse_with_unavailable_reader(exc, availability_fact="semantic_reader_available")


def _refuse_with_unavailable_reader(exc: Exception, *, availability_fact: str) -> NoReturn:
    """Preserve a reader refusal as typed facts, without presentation prose."""
    if isinstance(exc, MissingOptionalExtraError):
        facts: dict[str, str | bool] = {
            "extra": exc.extra.extra,
            "import_name": exc.extra.import_name,
            "importable": False,
        }
    else:
        facts = {
            availability_fact: False,
            "reader_error_type": exc.__class__.__name__,
        }
    raise PurchaseInvoiceEvidenceInputError(
        context=facts,
        precondition_verdict=ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE,
            facts=facts,
        ),
    ) from exc


def _active_filer_tax_id() -> str | None:
    """Return the active profile's own tax identifier, or ``None``.

    Answers ``None`` for every reason a profile might not yield one -- none
    active, none declared, the workflow state unreadable -- rather than
    propagating. That direction is deliberate and it is the conservative one:
    without the identifier the counterparty role resolution declines to run and
    the direction derivation reports that it was never supplied, which is
    exactly the behaviour that shipped before either existed. Letting a profile
    gap raise here would refuse to READ a document over a fact the document does
    not contain.
    """
    # Both imported at call time: the workflow package reaches this one, and the
    # filer-fact reader reaches the user-profile package which reaches back. The
    # sanctioned cycle breaks, read as if written at module scope.
    from ..workflow.persistence import workflow_state_repository
    from .filer_establishment import resolve_filer_tax_id

    try:
        state = workflow_state_repository().load()
    except Exception:
        return None
    return resolve_filer_tax_id(profile_record=state.active_profile_record())


def _proposed_supply_nature(
    transcription: DocumentTranscription,
    *,
    settings: Settings,
) -> SupplyNature | None:
    """Return a model's proposal about goods-or-services, or ``None``.

    Advisory throughout. The proposal reaches a person on the review item that
    already asks them to state the nature; the value that reaches the classifier
    is the one they type at confirm, so nothing model-derived enters it.

    Never raises into the read. A proposal that could fail an extraction would
    make an optional convenience able to lose a document, so every failure --
    an absent extra, an unreachable provider, a reply that did not survive
    containment -- yields no proposal and leaves the operator asked exactly as
    they were.
    """
    try:
        from ...llm.supply_nature_proposal import SupplyNatureProposer

        return SupplyNatureProposer(settings=settings).propose(transcription.text.splitlines()).nature
    except Exception:
        get_logger(__name__).info("supply-nature proposal unavailable; the operator is asked as before")
        return None


def _read_transcription_semantically(
    evidence: EvidenceInput,
    transcription: DocumentTranscription,
    *,
    settings: Settings,
    off_host_provider: LLMProvider | None = None,
    consent_token: EvidenceConsentToken | None = None,
    taxpayer_tax_id: str | None = None,
    propose_supply_nature: bool = False,
) -> InvoiceDraft:
    """Read a text-native PDF through the transcribe-extract-ground chain.

    The three stages, and why the order is not arbitrary:

    **Transcribe.** :func:`~application.ledger.evidence_textlayer.transcribe_text_layer` produces the
    document's reading-order text with printed forms preserved verbatim. It is
    produced by a DIFFERENT reader than the one that proposes values, which is
    exactly what makes the anchor check in stage three an external check rather
    than a model verifying itself.

    **Extract semantically.** The reading model proposes values in their declared
    form beside the printed anchor each was read from, and stamps every envelope
    ``UNANCHORED`` -- an honest under-claim, because it holds no transcription to
    check its own claims against.

    **Ground.** :func:`~application.ledger.grounded_reading.ground_draft_against_transcription`
    holds the transcription, so it runs the check the reader could not, upgrading
    each envelope to the outcome the evidence supports and appending the
    arithmetic-closure findings.

    Args:
        evidence: Resolved in-memory evidence bytes.
        transcription: The already-produced acquisition-stage text. Taken as an
            ARGUMENT rather than produced here so the caller's fallback ``try``
            can wrap the transcription alone. That scoping is what separates a
            DOCUMENT failure (no text layer -- escalate to vision) from an
            ENVIRONMENT failure (no reader -- refuse), and it has to be
            structural: when one ``try`` wrapped both, the refusal below raised
            the same exception type the fallback catches and was silently
            swallowed into a vision run.
        settings: Resolved settings, passed down rather than reloaded so the
            caller's overrides govern the model this stage resolves.
        off_host_provider: Provider to route the SEMANTIC stage at, or ``None``
            for the on-host default.
        consent_token: Per-invocation off-host consent proof, or ``None``.
        taxpayer_tax_id: The filer's own identifier, resolved once at the public
            entry from the active profile. Handed down rather than looked up
            here so one read of one document consults one profile, and so this
            function stays a pure reader of what it was given.
        propose_supply_nature: Whether to ask a model to PROPOSE goods-or-services
            from this transcription. Off by default and never consulted by the
            classifier: the proposal reaches a person, and the value that reaches
            the classifier is the one they state at confirm.

    Returns:
        The grounded draft.

    Raises:
        PurchaseInvoiceEvidenceInputError: When the semantic reader cannot be
            run. Deliberately OUTSIDE the caller's fallback ``try`` -- see
            :func:`_refuse_a_text_read_with_no_reader`.
    """
    # Both imports are function-local by necessity, not preference, and both are
    # cycle-breaks rather than lazy-loading:
    #
    # `cadrumo.llm` imports `InvoiceDraft` from this package, and
    # `_grounded_reading` reaches this module through `_closure_findings`. A
    # module-level import of either closes a loop through this file.
    #
    # The llm target names the OWNING PACKAGE'S PUBLIC FACADE, which is what the
    # import rule requires of a deferred import; the second is intra-package and
    # so may name its private module directly. Read both exactly as if they were
    # written at module scope.
    import httpx

    from ...llm.evidence_draft_text import TextInvoiceFieldExtractor, extract_invoice_fields_from_text
    from .grounded_reading import ground_draft_against_transcription
    from .invoice_extraction_authority import (
        default_invoice_extraction_period,
        resolve_invoice_extraction_authority_values,
    )

    # Resolved HERE, once, and handed down. The rates, the statutory retención
    # figures and the no-printed-tax category set are regulatory values, so this
    # layer determines them and the reading adapter receives them; the adapter
    # holds no authority of its own and cannot print a rate this call did not
    # produce. Resolving once per document also means both branches below read
    # under the same values, which a per-prompt resolution does not guarantee.
    authority_values = resolve_invoice_extraction_authority_values(period=default_invoice_extraction_period())

    try:
        # The pinned wrapper stays the on-host route and is left untouched: its
        # pin is a stated confidentiality property, and widening it with a
        # pass-through provider would open the off-host route for every caller
        # with no diff line that looks like a confidentiality change. An
        # explicitly-consented read constructs the extractor DIRECTLY instead,
        # so the reach-around gate keeps the wrapper as its target.
        if off_host_provider is None:
            read = extract_invoice_fields_from_text(transcription, authority_values=authority_values)
        else:
            read = TextInvoiceFieldExtractor(
                provider=off_host_provider,
                model=settings.cadrumo_llm_cloud_text_model,
                settings=settings,
                authority_values=authority_values,
                consent_token=consent_token,
            ).extract(transcription=transcription)
    except (MissingOptionalExtraError, LLMProviderError, httpx.HTTPError) as exc:
        # The reader is absent or unreachable. See the refusal's own docstring
        # for why this does not fall through to vision.
        _refuse_a_text_read_with_no_reader(exc)
    grounded_input = read.model_copy(
        update={
            "transcription_sha256": transcription.source_content_sha256,
            # Proposed HERE because the transcription is still in hand. A later
            # verb would re-run the whole reading stage to recover text this
            # call already holds, spending a document read to answer a question
            # worth one short call. Off unless asked: a read that silently
            # reaches a second model changes what the verb costs and what
            # leaves the host.
            "proposed_supply_nature": (
                _proposed_supply_nature(transcription, settings=settings) if propose_supply_nature else None
            ),
        },
    )
    return ground_draft_against_transcription(
        draft=grounded_input,
        transcription=transcription,
        taxpayer_tax_id=taxpayer_tax_id,
    )


def _refuse_an_unrecognised_xml_document(evidence: EvidenceInput) -> None:
    """Refuse an XML document whose syntax no structured reader recognises.

    XML must never reach the text-layer or vision fallbacks. Those exist for
    documents whose content is RENDERED -- a PDF's text layer, a photograph of a
    receipt -- and an XML file is neither: extracting prose from markup yields
    tag soup, and rasterising it to read with a vision model is incoherent as
    well as expensive.

    This became reachable only when ``.xml`` was admitted at the evidence gate.
    Before that a structured document could not be ingested at all, so the
    fallback chain was never handed one. Admitting the extension without closing
    the chain would route every unrecognised XML -- a SII or VERI*FACTU record,
    a TicketBAI record, any XML at all -- to the on-host vision model, whose
    capability is ON by default.

    The refusal names the syntaxes that ARE read, so an operator holding a
    document we do not support learns which ones we do rather than watching a
    model fail to read their markup.
    """
    if normalize_media_type(evidence.mime_type) != XML_MIME_TYPE:
        return
    if evidence.document_shape in STRUCTURED_DOCUMENT_SHAPES:
        # Self-contained rather than relying on call position. Today the
        # structured branch returns before reaching here, so this is
        # unreachable in the live routing -- which is precisely why it is
        # asserted: a later refactor that moves this call earlier would
        # otherwise refuse every Facturae, CII and UBL document, and the guard
        # would look correct while removing the capability it protects.
        return
    raise PurchaseInvoiceEvidenceInputError(
        translated_message="errors.refused.refused_ledger_evidence_input",
        precondition_verdict=ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_XML_INVOICE_SUPPORTED,
            facts={"xml_invoice_syntax_recognized": False},
        ),
    )


def _extract_invoice_fields_from_structured_record(evidence: EvidenceInput) -> InvoiceDraft:
    """Read a structured e-invoice exactly into the line-carrying draft.

    No model, no rasterisation, no network. The per-rate breakdown and the line
    set come from the document's own record, which is the whole reason the
    draft grew them: a flat base/rate/cuota triple structurally cannot hold a
    two-rate invoice.
    """
    # Function-local for the same cycle-break reason the grounding import in the
    # semantic path is: the findings module reaches back into this one for the
    # draft and finding types. Read it exactly as if it were written at module
    # scope.
    from .deterministic_findings import deterministic_findings
    from .grounding_anchor import (
        country_code_value,
        resolved_country_code,
        stated_country_code,
        structured_provenance,
    )

    parsed = parse_einvoice_document(evidence.data)
    # Resolved once and used twice: the draft carries these values and their
    # provenance envelopes describe them, so grounding the parser's verbatim
    # string instead would attach an envelope to a value the draft does not hold.
    country_codes: dict[str, tuple[str, str] | None] = {
        f"{side}_country_code": resolved_country_code(getattr(parsed, f"{side}_country_code"))
        for side in ("supplier", "customer")
    }
    draft = InvoiceDraft(
        supplier_tax_id=parsed.supplier_tax_id,
        supplier_name=parsed.supplier_name,
        customer_tax_id=parsed.customer_tax_id,
        customer_name=parsed.customer_name,
        # Both sides, because which party is the counterparty is not decided
        # until confirm. A country code cannot separate Spain's three IVA
        # territories, so these codes are the only thing that settles where
        # either party is established -- and the exact reader was the one path
        # that recovered neither, leaving the most machine-readable documents in
        # the corpus unable to answer a question a text-read document could.
        supplier_postal_code=parsed.supplier_postal_code,
        customer_postal_code=parsed.customer_postal_code,
        # The country half of the same question, resolved to the one code system
        # everything downstream is keyed by. The formats disagree about which
        # system they state: UBL states alpha-2 and Facturae states alpha-3, so
        # carrying the record's own string through would hand `ESP` to a resolver
        # that shape-checks for two letters and returns nothing -- the country
        # element present, read, and establishing nothing, with the postal rung
        # it gates staying shut for the entire Spanish national format.
        supplier_country_code=country_code_value(country_codes["supplier_country_code"]),
        customer_country_code=country_code_value(country_codes["customer_country_code"]),
        # The record's own token, carried whether or not the line above could
        # place it. This is what keeps an unplaceable country visible: the
        # resolved field goes empty for `THA` exactly as it does for a document
        # with no address block, and every surface downstream -- the review row,
        # the provenance envelope, the country advisory -- read that emptiness
        # and said nothing. A Thai export is an ordinary document, not a
        # malformed one, and it must not arrive looking like a silent absence.
        supplier_stated_country_code=stated_country_code(parsed.supplier_country_code),
        customer_stated_country_code=stated_country_code(parsed.customer_country_code),
        invoice_number=parsed.invoice_number,
        invoice_series=parsed.invoice_series,
        # Read and DISCARDED until now. A rectificativa is a different class
        # of invoice under RD 1619/2012 art. 15, and a confirm that cannot say
        # so mints one as ordinaria -- so the Invoice model's own rectificativa
        # invariants never fire, because nothing ever states the class.
        rectifies_invoice_number=parsed.rectifies_invoice_number,
        invoice_date=parsed.invoice_date,
        taxable_base=parsed.taxable_base,
        iva_amount=parsed.iva_amount,
        grand_total=parsed.grand_total,
        currency=parsed.currency,
        recargo_amount=parsed.recargo_amount,
        # The other two terms of the closure identity, which the structured
        # reader recovers from the format's own dedicated elements. Carried here
        # or the read is unreachable: the identity is checked on the DRAFT, so a
        # parser that recovers a suplido the draft drops leaves the check
        # computing a total short by exactly it -- which is the shape this
        # mapping exists to close rather than to reproduce one field along.
        retencion_amount=parsed.retencion_amount,
        suplidos_amount=parsed.suplidos_amount,
        iva_category=parsed.iva_category,
        # The mention the document prints, carried on the model-free path too.
        # It was reaching the operator only from the reading model, so the one
        # path that recovers it EXACTLY -- no model, no anchor check needed,
        # because the text is the record -- was the one that dropped it.
        regime_legend=parsed.regime_legend,
        lines=tuple(
            InvoiceDraftLine(
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                taxable_base=line.taxable_base,
                iva_rate=line.iva_rate,
                iva_amount=line.iva_amount,
            )
            for line in parsed.lines
        ),
        iva_breakdown=tuple(
            InvoiceDraftRateBreakdown(iva_rate=rate, taxable_base=base, iva_amount=cuota)
            for rate, base, cuota in parsed.iva_breakdown
        ),
        raw_text_length=len(evidence.data),
        provenance=structured_provenance(parsed=parsed, evidence=evidence, derived=country_codes),
    )
    draft.set_facturae_invoice_class(parsed.facturae_invoice_class)

    # Exactness is not correctness, and conflating the two is what left this path
    # unchecked. Reaching no model makes prompt injection categorically
    # impossible for this document -- it says nothing about whether its
    # arithmetic closes, or whether the regime it prints in words matches the tax
    # it charged. Those are questions about the ISSUER's document, not about the
    # reader, and an exactly-read wrong invoice is still a wrong invoice.
    return draft.model_copy(
        update={
            "discrepancies": (
                *deterministic_findings(draft),
                *_facturae_invoice_class_findings(
                    declared=parsed.facturae_invoice_class,
                    rectifies_invoice_number=parsed.rectifies_invoice_number,
                ),
            ),
        },
    )


def _extract_invoice_fields_via_vision(
    evidence: EvidenceInput,
    *,
    settings: Settings,
    off_host_provider: LLMProvider | None = None,
    consent_token: EvidenceConsentToken | None = None,
    taxpayer_tax_id: str | None = None,
) -> InvoiceDraft:
    """Rasterise/encode *evidence*, TRANSCRIBE it with the on-host vision model, then read it.

    Two stages, not one, and the split is what earns this path its grounding.
    The vision model produces a :class:`DocumentTranscription` and interprets
    nothing; the same semantic reader and the same anchor check the text lane
    uses then run over that text
    (:func:`_read_transcription_semantically`). Because the transcription is
    produced by a different call than the one that proposes values, the anchor
    check is an external check here exactly as it is on the text lane -- which
    it structurally could not be while one call went image-to-fields and the
    only thing an anchor could be compared against was the reply that asserted
    it.

    Gated by :attr:`~core.ServiceCapability.LLM_VISION` -- an operator who has
    opted out gets a typed refusal naming the capability toggle, never a silent
    empty draft. A missing/unreachable local Ollama runtime, or an unrasterisable
    PDF, is converted to the same instructive refusal the classification vision
    path uses (:func:`~application.provisioning.probe_ollama_vision`). An absent
    ``llm`` extra is reported separately as typed dependency facts, so a
    dependency gap is never mistaken for a daemon-reachability problem.
    """
    import httpx

    if not resolve_active_capability(ServiceCapability.LLM_VISION, settings=settings).enabled:
        facts = {"llm_vision_enabled": False}
        raise PurchaseInvoiceEvidenceInputError(
            context=facts,
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_VISION_CAPABILITY_ENABLED,
                facts=facts,
            ),
        )

    try:
        from ...llm.evidence_draft_vision import LocalVisionDocumentTranscriber, transcribe_document_images

        if evidence.document_shape in PDF_CONTAINER_SHAPES:
            images = tuple(
                MultimodalImageInput.from_base64(page, ImageMediaType.PNG)
                for page in rasterise_pdf_pages_to_base64_png(evidence.data)
            )
        else:
            import base64

            # An attachment is whatever format the operator supplied, so the type is
            # detected from the bytes; an unsupported one refuses here rather than
            # travelling to a provider under a guessed label.
            images = (
                MultimodalImageInput.from_base64(
                    base64.b64encode(evidence.data).decode("ascii"),
                    detect_image_media_type(evidence.data),
                ),
            )
        # Content-addressed to the SOURCE bytes, never to the renders: the same
        # document rasterised at another resolution is one document, and hashing
        # the images would split it into two cache entries that can never hit.
        #
        # The consented route reaches stage ONE as well as stage two, and that
        # is deliberate rather than thorough: on a scan-only document the pixels
        # ARE the evidence, so a consent that covered only the semantic stage
        # would take an operator's acknowledgement and then leave the read
        # entirely on-host -- an acknowledgement that changes nothing, which is
        # worse than not asking.
        if off_host_provider is None:
            transcription = transcribe_document_images(
                images,
                source_content_sha256=evidence.content_sha256,
                settings=settings,
            )
        else:
            transcription = LocalVisionDocumentTranscriber(
                provider=off_host_provider,
                model=settings.cadrumo_llm_cloud_vision_model,
                settings=settings,
                consent_token=consent_token,
            ).transcribe(
                evidence_images=images,
                source_content_sha256=evidence.content_sha256,
            )
    except MissingOptionalExtraError as exc:
        # Ordered ahead of the runtime-failure branch deliberately. A missing
        # `llm` extra is a dependency problem, not a reachability problem: the
        # branch below probes runtime reachability, which is a different failed
        # condition and must not replace the dependency identity.
        _refuse_with_unavailable_reader(exc, availability_fact="vision_reader_available")
    except (httpx.HTTPError, LLMProviderError, LLMPdfRasterisationError) as exc:
        status = probe_ollama_vision(settings)
        if status.precondition_verdict is not None:
            raise PurchaseInvoiceEvidenceInputError(precondition_verdict=status.precondition_verdict) from exc
        facts: dict[str, str | bool] = {
            "vision_reader_available": False,
            "vision_reader_probe_available": True,
            "vision_reader_error_type": exc.__class__.__name__,
        }
        raise PurchaseInvoiceEvidenceInputError(
            context=facts,
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE,
                facts=facts,
            ),
        ) from exc

    # OUTSIDE the try, deliberately, and for the same reason the text lane's
    # semantic read sits outside its transcription try: a failure here is a
    # statement about the semantic READER, and converting it into "vision
    # reading failed" would send the operator to restart a daemon that read the
    # page perfectly well.
    return _read_transcription_semantically(
        evidence,
        transcription,
        settings=settings,
        off_host_provider=off_host_provider,
        consent_token=consent_token,
        taxpayer_tax_id=taxpayer_tax_id,
    )


class CounterpartyDraftSide(BaseModel):
    """The side of a read document that is the COUNTERPARTY, once direction is known.

    A draft is pre-direction by construction: it records what each party's block
    said without deciding which of them the filer is. Direction settles that, and
    settles it the same way for every consumer -- which is why this is a record
    produced once rather than a pair of field lookups each caller repeats.

    Attributes:
        tax_id: The counterparty's identifier as the document printed it, or
            ``None`` when the reader recovered none.
        name: The counterparty's stated name, or ``None``.
        postal_code: The postal code printed in the counterparty's address, or
            ``None``.
        country: The country NAME printed in the counterparty's address, or
            ``None``. A name rather than a code, because that is what an address
            block prints; the match against the bounded vocabulary is the
            establishment ladder's own second rung.
        country_code: The ISO 3166-1 alpha-2 country code a structured record
            stated for the counterparty, or ``None``. Carried beside the printed
            NAME rather than instead of it: the two are the same ladder rung
            reached from different readers, and a document states one or the
            other, never both.
        stated_country_token: The token the record's country element carries,
            verbatim, or ``None`` where it stated none. Carried beside the
            resolved code rather than folded into it, because the two answer
            different questions and only this one can answer the second: the
            resolved field is empty both for a document that stated no country
            AND for one stating a token the bundled vocabulary does not carry,
            so a consumer asking "did the document state a country" off that
            field gets the same answer for an unplaceable export and for an
            invoice with no address block. A consumer deciding whether an
            unestablished counterparty is the DOCUMENT's gap or OURS depends on
            telling those apart.

            **Named a TOKEN, and not a country CODE, deliberately.**
            The establishment ladder's ``resolved_country_code`` parameter wants
            the RESOLVED alpha-2 -- which is ``country_code`` above, and
            which is what this object's one ladder call site correctly passes.
            Two same-shaped attributes on one object, one safe in that slot and
            one not, is a swap that type-checks: both are ``str | None``, and
            feeding an alpha-3 into an alpha-2 parameter on a tax-territory path
            fails to place the country and reintroduces exactly the silence this
            field exists to remove. The name is the guard, because nothing else
            here is.
        tax_id_field: Which draft field ``tax_id`` was taken from. Carried so an
            operator override is recorded against the reading it displaced
            rather than against whichever field shares the option's name.
        name_field: The same for ``name``.
    """

    model_config = STRICT_FROZEN_CONFIG

    tax_id: str | None = None
    name: str | None = None
    postal_code: str | None = None
    country: str | None = None
    country_code: str | None = None
    stated_country_token: str | None = None
    tax_id_field: str = Field(min_length=1)
    name_field: str = Field(min_length=1)


def counterparty_draft_side(draft: InvoiceDraft, *, kind: InvoiceKind) -> CounterpartyDraftSide:
    """Select the counterparty's side of a draft from the document's direction.

    On an invoice the filer ISSUED, the counterparty is the customer; on one
    they RECEIVED, it is the supplier.

    **The selection is total, with no fall-back to the other side, and that is
    the load-bearing part.** This once read the customer side "if it is set,
    otherwise the supplier", and because the text and vision readers cannot
    populate a customer at all, every issued document silently resolved to the
    supplier -- who, on a document the filer issued, IS the filer. The value is
    checksum-valid, so every identity check downstream passes it, and it is
    bound for the Modelo 347 / 349 totals AEAT reconciles against the other
    party's own declaration.

    Two guards elsewhere do catch that today, but both load the taxpayer profile
    and both return without refusing when it carries no tax id, so the
    protection was only ever as present as the profile. Selecting one side and
    stopping makes the property structural instead: an unread counterparty stays
    ``None`` and is refused as a missing field, naming the override that supplies
    it, which is the same outcome an operator already gets for any other field
    the reader could not recover.

    Args:
        draft: The pre-direction reading of the document.
        kind: Which side of the invoice the filer is on, as the operator settled
            it at confirm. Never the reader's suggestion.

    Returns:
        :class:`CounterpartyDraftSide`: the selected side, and which draft
        fields it came from.
    """
    if kind is InvoiceKind.ISSUED:
        return CounterpartyDraftSide(
            tax_id=draft.customer_tax_id,
            name=draft.customer_name,
            country_code=draft.customer_country_code,
            stated_country_token=draft.customer_stated_country_code,
            postal_code=draft.customer_postal_code,
            country=draft.customer_country,
            tax_id_field="customer_tax_id",
            name_field="customer_name",
        )
    return CounterpartyDraftSide(
        tax_id=draft.supplier_tax_id,
        name=draft.supplier_name,
        country_code=draft.supplier_country_code,
        stated_country_token=draft.supplier_stated_country_code,
        postal_code=draft.supplier_postal_code,
        country=draft.supplier_country,
        tax_id_field="supplier_tax_id",
        name_field="supplier_name",
    )


class PrintedTotalDiscrepancy(BaseModel):
    """The document's printed total disagreeing with the total actually recorded.

    The confirm path never persists a model-read or text-read figure as the
    invoice total: ``grand_total`` is DERIVED from the taxable base and the
    registry-resolved rate slot
    (:func:`~application.invoices.build_catalogue_invoice`). That derivation is
    the correct behaviour and this record does not change it -- the printed
    figure stays an advisory cross-check and never overwrites the derived value,
    exactly as the evidence-reading discipline requires.

    What this record adds is the other half of that same discipline: when the
    two disagree, say so. A disagreement is never noise, because the derived
    total is arithmetically fixed at ``base + cuota``; anything the document
    prints beyond that is a component the record could not represent, or a
    misread of one it could:

    - A **recargo de equivalencia** invoice (LIVA art. 161) prints
      ``base + cuota + recargo``. The recargo has nowhere to go on this path,
      so the record silently understates the document by exactly that surcharge.
    - An **unread rate** resolves to :attr:`~domain.invoices.IvaRate.EXEMPT`
      (``iva_rate=None`` is the base-only slot), minting a zero-cuota invoice
      whose printed total still shows the cuota that was charged.
    - A **misread base** propagates into the derived total and diverges from the
      printed one.

    All three are silent under-declarations that the printed total detects for
    free, having already been read. Discarding it unexamined is what let them
    through.

    Attributes:
        printed_total: The total actually printed on the document, as recovered
            by the on-host reader.
        recorded_total: The total derived from the confirmed base and rate slot,
            i.e. what the persisted invoice carries.
        difference: ``printed_total - recorded_total``. Positive means the
            document totals MORE than the record -- the under-declaration
            direction, and the one a recargo produces.
    """

    model_config = STRICT_FROZEN_CONFIG

    printed_total: Decimal
    recorded_total: Decimal
    difference: Decimal


def printed_total_discrepancy(*, draft: InvoiceDraft, invoice: Invoice) -> PrintedTotalDiscrepancy | None:
    """Return the printed-vs-recorded total disagreement, or ``None`` when they agree.

    Compares only when the reader actually recovered a total: a document whose
    total could not be read grounds no cross-check, and reporting a discrepancy
    against an absent figure would manufacture an alert out of missing data
    rather than out of conflicting data.

    Args:
        draft: The extraction the confirmation was based on.
        invoice: The invoice that was persisted (or matched on a guarded no-op).

    Returns:
        :class:`PrintedTotalDiscrepancy` when the document printed a total that
        differs from the recorded one, else ``None``.
    """
    printed = draft.grand_total
    if printed is None:
        return None
    if printed == invoice.grand_total:
        return None
    return PrintedTotalDiscrepancy(
        printed_total=printed,
        recorded_total=invoice.grand_total,
        difference=printed - invoice.grand_total,
    )


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


def _without_own_country_prefix(value: str, *, country: str) -> str:
    """Return *value* with a leading prefix naming *country* removed.

    Only that country's own prefix, never any alpha-2. A German-prefixed number
    on a counterparty recorded in Spain keeps its prefix and therefore keeps
    disagreeing, which is the outcome that must survive: the point is to stop
    refusing two spellings of ONE bearer, not to stop distinguishing two.
    """
    token = value.strip().upper()
    head = country.strip().upper()
    if len(head) == 2 and token.startswith(head) and len(token) > 2:
        return token[2:]
    return token


def _same_bearer_allowing_own_country_prefix(left: str, right: str, *, country: str) -> bool:
    """Whether two spellings name one bearer, discounting this country's prefix.

    Delegates to the canonical same-bearer predicate rather than reimplementing
    it, so the separator rule stays in one place and this function adds exactly
    one axis on top of it.
    """
    if same_tax_identifier(left, right):
        return True
    return same_tax_identifier(
        _without_own_country_prefix(left, country=country),
        _without_own_country_prefix(right, country=country),
    )


def _agreed_counterparty_tax_id(
    *,
    supplied: str | None,
    extracted: str | None,
    counterparty_country: str,
) -> str | None:
    """Resolve the counterparty tax id, refusing a supplied/extracted disagreement.

    Every other field here layers an operator value over the extracted one and
    lets the operator win silently. This one does not, because the extracted
    value is the only field on the draft that nothing else checks: the
    counterparty NAME is supplied by the operator, so a misread name is caught
    by them typing it, while a misread tax id was accepted unseen.

    That matters past tidiness. A received invoice's supplier tax id drives
    deductibility and feeds Modelo 347 per counterparty, so a wrong one reaches
    a filing a human submits. The checksum on
    :func:`~core.identity.validate_spanish_tax_id` is the PRIMARY
    defence and it is a strong one -- a transposed digit breaks the check
    character and is refused outright. What it cannot catch is a misread that
    happens to be a different VALID identifier, which belongs to a different
    real taxpayer. This closes that residue.

    Supplying the value is therefore an ASSERTION rather than an override, and
    the difference is what makes it safe: typing to CHECK is not typing to SET.
    A typo here produces a refusal, never a wrong value on a filing -- unlike
    the transcription hazard that was removed from the extract hint, where what
    the operator typed silently became the data.

    Neither value is named in the refusal. The operator already knows the one
    they typed, and the machine only has to answer whether the extractor agrees;
    printing either would put a tax identity into a pasteable artefact for no
    gain.

    Comparison is on :func:`~cadrumo.core.identity.same_tax_identifier`, the
    canonical "are these the same identifier" predicate. It deliberately asserts
    no checksum -- a counterparty may be non-resident and carry a foreign
    identifier -- which is exactly right here: this answers "same identifier?",
    and the separate validation gate on the invoice model answers "valid Spanish
    identifier?".

    The axis that matters on THIS path is separators, not case. One side is
    whatever an on-host extractor read off a printed document, and printed
    identifiers carry hyphens and spaces routinely, so the comparison must
    normalise them away: ``B-1234567-4`` and ``B12345674`` are one identifier.
    :func:`~cadrumo.core.identity.tax_id_identity_token` would NOT match those
    two -- it stays trim-and-uppercase because it keys stored objects and must
    never merge two characters-differ identifiers into one row. Keying and
    comparing are different questions, and this one is comparing.

    A blank on either side answers "not the same" and refuses, because an
    invoice cannot be confirmed against an identity nothing supplied.

    **The second axis is the COUNTRY PREFIX, and it is handled here rather than
    in the shared predicate.** A document routinely states an identifier in its
    IVA form while an operator supplies the bare national form -- ``ESB12345674``
    against ``B12345674`` -- and those name one bearer. The shared predicate
    cannot know that: stripping a leading alpha-2 from both sides unconditionally
    would merge bearers ACROSS States, since the same national body can exist
    under two different prefixes, and that predicate is also consumed by the
    identity-role resolver and the direction deriver, where a looser rule would
    silently change who counts as the taxpayer on every document.

    So the prefix is stripped only when it names THIS counterparty's own country,
    which is a fact this call site has and the predicate does not. One side
    carrying ``DE`` against a counterparty recorded in Spain still disagrees, and
    must.

    Args:
        supplied: The operator's ``--counterparty-nif``, or ``None``.
        extracted: What the on-host extractor read, or ``None``.
        counterparty_country: The alpha-2 country recorded for this
            counterparty, which decides which prefix may be discounted.

    Returns:
        The value to confirm with, or ``None`` when neither side has one.

    Raises:
        PurchaseInvoiceEvidenceInputError: When both sides carry a value and
            they are not the same identifier.
    """
    if supplied is None:
        return extracted
    if extracted is None:
        # Extraction found nothing, so there is nothing to disagree with and
        # the operator's value is authoritative. This is the override case the
        # flag has always served, and it stays.
        return supplied
    if not _same_bearer_allowing_own_country_prefix(supplied, extracted, country=counterparty_country):
        raise PurchaseInvoiceEvidenceInputError(
            translated_message="errors.refused.refused_ledger_evidence_input",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_COUNTERPARTY_VALID,
                facts={"counterparty_tax_id_matches_document": False},
            ),
        )
    return supplied


def _refuse_a_counterparty_that_is_the_filer(counterparty_tax_id: str) -> None:
    """Refuse an invoice recording the taxpayer as their own counterparty.

    The reader no longer scans for the first checksum-valid tax id, and the
    field contract now asks for both parties separately by role, so the
    mechanism that first exposed this is gone. The exposure is not. On an ISSUED
    invoice the issuer IS the filer, so the supplier slot legitimately holds the
    filer's own identifier -- the document is right and the reading is right --
    and any path taking that side as the counterparty records the taxpayer
    against themselves. The value is checksum-valid, so every downstream
    identity check passes it, and it is bound for the Modelo 347 / 349
    counterparty totals AEAT reconciles against what the counterparty declared.

    Refusing is right rather than advisory: unlike an amount that is merely
    doubtful, a self-naming counterparty is wrong under every reading this
    codebase can represent (see
    :func:`~application.invoices.counterparty_is_the_filer` for the autoconsumo
    scope note). Minting the record and warning about it would put a fabricated
    counterparty identity in the catalogue.

    The profile carries the identity to compare against, so a bucket whose
    profile is absent or carries no tax id cannot be checked. That case returns
    without refusing -- a guard that cannot run must not block a path it cannot
    judge -- which does mean the protection is only as present as the profile.
    Every real bucket carries one; setup requires the tax id.

    Args:
        counterparty_tax_id: The identifier about to be recorded.

    Raises:
        PurchaseInvoiceEvidenceInputError: When the identifier is the filer's
            own.
    """
    from ..invoices import counterparty_is_the_filer
    from ..wizard.status import WizardStatusError, load_active_taxpayer_profile
    from ..workflow.persistence import workflow_state_repository

    try:
        profile = load_active_taxpayer_profile(workflow_state_repository().load())
    except WizardStatusError:
        return
    if not counterparty_is_the_filer(counterparty_tax_id=counterparty_tax_id, profile=profile):
        return
    raise PurchaseInvoiceEvidenceInputError(
        translated_message="errors.refused.refused_ledger_evidence_input",
        precondition_verdict=ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_COUNTERPARTY_VALID,
            facts={"counterparty_is_filer": True},
        ),
    )


def _require_confirmed_field(value: Decimal | str | None, *, field: str) -> Decimal | str:
    if value is None:
        raise PurchaseInvoiceEvidenceInputError(
            translated_message="errors.refused.refused_ledger_evidence_input",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_REQUIRED_FIELD_AVAILABLE,
                facts={"required_field_available": False},
            ),
        )
    return value


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


def _refuse_an_issued_document_the_filer_did_not_issue(
    *,
    kind: InvoiceKind,
    extracted_supplier_tax_id: str | None,
) -> None:
    """Refuse a document confirmed as ISSUED that someone else issued.

    The sibling guard refuses a counterparty that names the filer. This one
    catches the opposite mis-direction: a supplier's invoice TO the taxpayer,
    confirmed as issued BY them. There the counterparty is a real third party,
    so the sibling guard sees nothing wrong -- the record is internally
    coherent and simply describes the wrong direction.

    The evidence itself settles it. On a genuinely issued document the printed
    supplier IS the filer, so an extracted supplier identity that is somebody
    else is positive evidence the document was issued by that somebody else.

    Direction is not cosmetic. It decides which informativa the record feeds
    and on which side: a received invoice booked as issued moves a purchase
    into the sales column, inverts the cuota's meaning between soportado and
    repercutido, and reaches Modelo 347 as an operation the counterparty will
    have declared with the opposite sign. AEAT reconciles those two
    declarations against each other.

    Refusing rather than warning, for the same reason the sibling guard does:
    the direction is wrong under every reading, not merely doubtful.

    The guard declines to judge where it cannot. An absent extracted supplier
    means the scan found no issuer identity, which is silence rather than
    evidence, and a bucket whose profile carries no tax id gives nothing to
    compare against. Both return without refusing -- a guard that cannot run
    must not block a path it cannot judge.

    Args:
        kind: The direction the operator is confirming the document as.
        extracted_supplier_tax_id: Issuer identity recovered from the document,
            or ``None`` when the scan found none.

    Raises:
        PurchaseInvoiceEvidenceInputError: The document names an issuer who is
            not the filer, yet is being confirmed as issued by the filer.
    """
    if kind is not InvoiceKind.ISSUED or extracted_supplier_tax_id is None:
        return

    from ..invoices import counterparty_is_the_filer
    from ..wizard.status import WizardStatusError, load_active_taxpayer_profile
    from ..workflow.persistence import workflow_state_repository

    try:
        profile = load_active_taxpayer_profile(workflow_state_repository().load())
    except WizardStatusError:
        return
    # The loader raises rather than returning None, and that failure is already
    # handled by the except clause above, so the former None guard was unreachable.
    if counterparty_is_the_filer(counterparty_tax_id=extracted_supplier_tax_id, profile=profile):
        return
    raise PurchaseInvoiceEvidenceInputError(
        "this document names another issuer, so it cannot be confirmed as issued by you; "
        "confirm it as received, or correct the document reference",
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


def _operator_value_or_reading[T](supplied: T | None, read: T) -> T:
    """Return the operator's value when they supplied one, else the document's.

    The layering rule every confirmable field follows, named once rather than
    restated per field. Extraction is best-effort, so an explicit operator value
    always outranks the reading; a field that quietly inverted the order would
    prefer a misread document over the person confirming it.
    """
    return supplied if supplied is not None else read


def _confirmed_currency(supplied: str | None, read: str | None) -> str:
    """Return the ISO-4217 code the invoice is minted in.

    Same override-on-extraction layering as every other field: an explicit
    operator value wins, else the currency actually printed on the document,
    else euro. Preferring the extracted code over the euro default is what stops
    a foreign-currency invoice being minted at its face value in euro. Falsy
    rather than ``None`` handling is deliberate here -- an empty printed code
    carries no more information than an absent one.
    """
    return (supplied or read or DEFAULT_CURRENCY).strip().upper()


def _confirmed_counterparty_name(supplied: str | None, read: str | None) -> str:
    """Return the counterparty display name, refusing when neither side states one.

    Unlike the tax id there is no extraction heuristic strong enough to stand
    alone, so a document naming nobody plus an operator supplying nothing is a
    refusal rather than an empty name reaching the catalogue.
    """
    resolved = (supplied or read or "").strip()
    if not resolved:
        raise PurchaseInvoiceEvidenceInputError(
            translated_message="errors.refused.refused_ledger_evidence_input",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_REQUIRED_FIELD_AVAILABLE,
                facts={"counterparty_name_available": False},
            ),
        )
    return resolved


def _operator_restated_the_amounts(
    *,
    taxable_base: Decimal | None,
    iva_rate: Decimal | None,
    iva_amount: Decimal | None,
) -> bool:
    """Return whether the operator restated the invoice totals themselves.

    Any one of the three is a statement about the WHOLE invoice, which is why
    this single predicate gates both the rate tier the establishment ladder is
    handed and the per-rate line split. Two disagreeing authorities on the same
    figures is exactly the condition it exists to prevent, so the two decisions
    must never drift onto separately-derived answers.
    """
    return taxable_base is not None or iva_rate is not None or iva_amount is not None


def _rate_tier_the_document_charged(
    draft: InvoiceDraft,
    *,
    invoice_date: date | None,
    operator_restated_amounts: bool,
) -> IvaRateKind | None:
    """Return the domestic rate tier to hand the establishment ladder, or ``None``.

    Resolved here and handed in, rather than left for the classification
    apparatus to re-read: which tier a document charged is the reading stage's
    business, and re-deciding it inside the classifier would be a second
    authority on the same lines. Skipped when the operator restated the amounts,
    for the same reason the per-rate split is -- their figures are the
    authority, not the reader's -- and skipped when no date resolves, because
    the tier is only meaningful against the rates in force on a given day.
    """
    if operator_restated_amounts or invoice_date is None:
        return None
    return domestic_rate_tier_from_the_document(draft, invoice_date=invoice_date)


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
    operator_restated_amounts = _operator_restated_the_amounts(
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
        rate_tier=_rate_tier_the_document_charged(
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


def _resolved_invoice_class(
    draft: InvoiceDraft,
    *,
    invoice_class: InvoiceClass | None,
    rectifies_invoice_number: str | None,
) -> InvoiceClass:
    """Resolve Facturae class, preserving explicit operator and rectification facts."""
    declared_class = draft.facturae_invoice_class
    if declared_class in {FacturaeInvoiceClass.ORIGINAL, FacturaeInvoiceClass.COPY}:
        return InvoiceClass.ORDINARIA
    if declared_class in {
        FacturaeInvoiceClass.ORIGINAL_CORRECTIVE,
        FacturaeInvoiceClass.COPY_CORRECTIVE,
    }:
        return InvoiceClass.RECTIFICATIVA
    if invoice_class is not None:
        # Recapitulativa has no domain member; preserve the operator's statement.
        return invoice_class
    return InvoiceClass.RECTIFICATIVA if rectifies_invoice_number is not None else InvoiceClass.ORDINARIA


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
    resolved_counterparty_tax_id = _require_confirmed_field(
        _agreed_counterparty_tax_id(
            supplied=counterparty_tax_id,
            extracted=counterparty_side.tax_id,
            counterparty_country=counterparty_country,
        ),
        field="counterparty_tax_id",
    )
    assert isinstance(resolved_counterparty_tax_id, str)
    _refuse_an_issued_document_the_filer_did_not_issue(
        kind=kind,
        extracted_supplier_tax_id=draft.supplier_tax_id,
    )
    _refuse_a_counterparty_that_is_the_filer(resolved_counterparty_tax_id)
    resolved_invoice_number = _require_confirmed_field(
        _operator_value_or_reading(invoice_number, draft.invoice_number),
        field="invoice_number",
    )
    assert isinstance(resolved_invoice_number, str)
    resolved_invoice_date = _resolve_confirmed_invoice_date(invoice_date, draft)
    resolved_taxable_base = _require_confirmed_field(
        _operator_value_or_reading(taxable_base, draft.taxable_base),
        field="taxable_base",
    )
    assert isinstance(resolved_taxable_base, Decimal)
    resolved_iva_rate = _operator_value_or_reading(iva_rate, draft.iva_rate)
    resolved_currency = _confirmed_currency(currency, draft.currency)
    resolved_counterparty_name = _confirmed_counterparty_name(counterparty_name, counterparty_side.name)
    confirmed_lines = _confirmed_lines_from_the_document(
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
        else _operator_value_or_reading(recargo_amount, draft.recargo_amount)
    )
    resolved_iva_category = _operator_value_or_reading(iva_category, preparation.establishment.category.category)
    resolved_rectifies = _operator_value_or_reading(rectifies_invoice_number, draft.rectifies_invoice_number)
    resolved_series = _operator_value_or_reading(series, draft.invoice_series)
    resolved_invoice_class = _resolved_invoice_class(
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


def domestic_rate_tier_from_the_document(draft: InvoiceDraft, *, invoice_date: date) -> IvaRateKind | None:
    """Return the domestic rate tier the document's own lines charged, or ``None``.

    **A tier, not a category.** This resolution used to end in a domestic
    :class:`~domain.iva.IvaCategory`, which made it a second classifier sitting
    ahead of the rule table and reaching it never -- and it reached that
    category through :func:`~domain.iva.domestic_categories_by_rate_kind`, the
    exact mapping the table's own ``R05`` rule consults. Stopping at the tier
    keeps every one of the declines below and hands the answer to the table as
    a criteria axis, so the mapping is applied once, where the law is.

    :func:`~domain.iva.rate_kinds_for_declared_rate` answers which tier a
    declared rate WAS on a given date, against the registered rate records; it
    returns a tuple because that question can legitimately have more than one
    answer, so a caller detects ambiguity instead of picking one.

    The date is load-bearing and is the invoice's own issue date, not today's.
    A tier's rate changes by statute, so resolving a 2024 document against
    today's table would answer about a rate it was never charged at.

    Declines, rather than approximating, in three cases:

    - **More than one rate.** One invoice carries one category field and a
      two-tier document has two answers. Picking either declares part of the
      base under a rate it was not charged at, and picking by size is an
      invention. Which tier a multi-rate invoice takes is a modelling
      decision this resolution does not make.
    - **A recargo de equivalencia.** The rate resolves cleanly, but a supply
      carrying a recargo may belong to the ordinary domestic tier or to the
      recargo category, and the decomposition contract accepts BOTH -- so a
      wrong pick would be caught nowhere downstream. That is exactly the shape
      that must not be guessed.
    - **An unregistered or ambiguous rate.** A rate that was not a registered
      Spanish rate on the issue date is a real refusal rather than a lookup
      failure, and a rate matching two tiers is the ambiguity the tuple exists
      to surface.

    Declining is visible: the criteria carry no tier, the rule table refuses the
    domestic branch that needs one, and the resolution reports the operation
    unresolved. A guess would not be.

    Args:
        draft: The re-run extraction being confirmed.
        invoice_date: The resolved issue date the rate must be read against.

    Returns:
        The resolved :class:`~domain.iva.IvaRateKind`, or ``None`` when the
        document does not settle it unambiguously.
    """
    if len(draft.iva_breakdown) != 1:
        return None
    entry = draft.iva_breakdown[0]
    if entry.iva_rate is None:
        return None
    if entry.recargo_amount is not None or draft.recargo_amount is not None:
        return None
    # The lookup takes the rate as a FRACTION, matching how a transaction stores
    # it; the draft carries the bare percentage the document prints.
    tiers = rate_kinds_for_declared_rate(EUMemberState.ES, entry.iva_rate / Decimal("100"), invoice_date)
    if len(tiers) != 1:
        return None
    return tiers[0]


def _confirmed_lines_from_the_document(
    *,
    draft: InvoiceDraft,
    invoice_number: str,
    taxable_base: Decimal,
    iva_rate: Decimal | None,
    iva_amount: Decimal | None,
    operator_overrode_the_amounts: bool,
) -> tuple[InvoiceLine, ...] | None:
    """Build the confirmed lines from what the document itself declared.

    Returns ``None`` when nothing better than the writer's own base-times-rate
    derivation is available, which is the correct outcome for a text or vision
    reader: those recover printed totals, not a tax breakdown.

    The per-rate breakdown is used whenever the document states one, at ANY
    length. A single entry is not the harmless case it looks like: the
    structured readers populate the breakdown and never the draft's flat
    ``iva_rate``, so a one-rate structured document reached the writer with no
    rate at all and resolved to the base-only EXEMPT slot -- minting a
    zero-cuota invoice out of a document that plainly charged one. Reading the
    breakdown at length one is what recovers that rate; reading it at length two
    or more is additionally what preserves WHICH part of the base carried which
    rate, since Modelo 303 sums cuota devengada per tier.

    Args:
        draft: The re-run extraction being confirmed.
        invoice_number: Resolved invoice number, used to label the lines.
        taxable_base: Resolved taxable base the lines must sum back to.
        iva_rate: Resolved IVA percentage, or ``None``.
        iva_amount: The operator-supplied printed cuota, or ``None``.
        operator_overrode_the_amounts: Whether the operator restated any of the
            base, rate or cuota.

    Returns:
        The lines to hand the writer, or ``None`` to let it derive one line.
    """
    if draft.iva_breakdown and not operator_overrode_the_amounts:
        # Every entry must state both halves of its subtotal. A partial
        # breakdown is not silently completed here: deriving the missing cuota
        # would put this function's arithmetic in place of the document's own
        # figure, which is the opposite of reading the record exactly. The
        # fall-through keeps the pre-existing behaviour, and the printed-total
        # cross-check still reports the shortfall.
        # Pair each entry with its narrowed amounts in one pass, so the guard and
        # the use are the same expression. An `all(...)` check ahead of a
        # comprehension proves the same thing to a reader but not to a checker,
        # which then cannot tell this from a genuine optional dereference.
        priced = [
            (entry, entry.taxable_base, entry.iva_amount)
            for entry in draft.iva_breakdown
            if entry.taxable_base is not None and entry.iva_amount is not None
        ]
        if len(priced) == len(draft.iva_breakdown):
            return tuple(
                InvoiceLine(
                    description=f"{invoice_number or 'Invoice'} - IVA {entry.iva_rate}%",
                    quantity=Decimal("1"),
                    unit_price=taxable_base,
                    subtotal=taxable_base,
                    iva_rate=resolve_iva_rate_slot(entry.iva_rate),
                    iva_amount=iva_amount,
                )
                for entry, taxable_base, iva_amount in priced
            )
    if iva_amount is not None:
        return (
            InvoiceLine(
                description=invoice_number or "Invoice",
                quantity=Decimal("1"),
                unit_price=taxable_base,
                subtotal=taxable_base,
                # The SAME resolver the writer applies to the same value, so an
                # unrepresentable percentage refuses identically whether or not
                # the document printed a cuota.
                iva_rate=resolve_iva_rate_slot(iva_rate),
                iva_amount=iva_amount,
            ),
        )
    return None


def _resolve_confirmed_invoice_date(invoice_date: date | None, draft: InvoiceDraft) -> date:
    if invoice_date is not None:
        return invoice_date
    if draft.invoice_date is not None:
        parsed = parse_iso8601_date(draft.invoice_date)
        if parsed is not None:
            return parsed
    raise PurchaseInvoiceEvidenceInputError(
        translated_message="errors.refused.refused_ledger_evidence_input",
        precondition_verdict=ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_INVOICE_DATE_AVAILABLE,
            facts={"invoice_date_available": False},
        ),
    )


def _resolve_evidence_attachment_id(
    *,
    bucket_id: str,
    evidence_id: str | None,
    attachment_id: str | None,
    settings: Settings,
) -> str:
    """Return the in-store ``attachment_id`` backing one evidence reference.

    Mirrors the exactly-one-of resolution
    :func:`~application.ledger.evidence_draft.extract_invoice_draft_from_evidence` already
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
    assert evidence_id is not None  # narrowed by the caller's exactly-one guard
    record = find_bytes_bearing_evidence_record(
        evidence_id,
        evidence_records=PurchaseInvoiceEvidenceService(settings=settings).list_all(bucket_id=bucket_id),
    )
    if record is None:
        raise refuse_reference_without_document_bytes(evidence_id)
    return record.attachment_id
