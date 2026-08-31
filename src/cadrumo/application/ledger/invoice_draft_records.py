"""The invoice-draft record family, apart from the service that fills it.

These records are read by the on-host inference package, which holds no
repository handle of its own. Their previous home, ``evidence_draft``, also
wires :class:`~cadrumo.adapters.persistence.profile.invoices.InvoiceCatalogueRepository`
and :class:`~cadrumo.adapters.persistence.storage.AttachmentStore`, so importing
a draft record pulled the whole persistence subtree into every consumer that
only wanted the shape -- including ``cadrumo.llm``, whose distance from
persistence is what the operator's in-memory inference exemption rests on.

This module therefore imports neither persistence nor the inference package,
and must keep it that way. Every dependency below was checked to reach neither
before the split.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, PrivateAttr, model_validator

from ...adapters.inbound.einvoice.parsers import FacturaeInvoiceClass
from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.field_grounding import FieldGroundingOutcome
from ...core.field_origin import FieldOrigin
from ...core.identity import ContentDigest, TaxIdIdentityToken
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.supply_nature import SupplyNature

__all__ = [
    "DraftDiscrepancyFinding",
    "FieldAmbiguityCandidate",
    "FieldProvenance",
    "InvoiceDraft",
    "InvoiceDraftLine",
    "InvoiceDraftRateBreakdown",
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
