"""Typed ``--json`` payload schemas for the ledger invoice/inventory/evidence sub-apps.

Extracted from :mod:`~entrypoints.cli._ledger_payloads` to keep that
module under its size budget (`aeat-architecture-boundaries`,
`aeat-architecture-boundaries`); follows the same split pattern the
module's own docstring documents for
:mod:`~entrypoints.cli._ledger_rule_payloads`,
:mod:`~entrypoints.cli._ledger_llm_payloads`, and
:mod:`~entrypoints.cli._ledger_catalogue_invoice_payloads`.
Covers two CLI sub-app payload families:

* P07 -- the ``inventory`` sub-app.
* P08 -- the purchase-invoice ``evidence`` sub-app.

The ``invoice`` noun-group is *not* here: every invoice payload lives in
:mod:`~entrypoints.cli._ledger_catalogue_invoice_payloads`, which projects the
sole invoice aggregate.

Each class is a strict :class:`~core.json_contract.OutputSchema`
subclass, decorated with :func:`~core.json_contract.register_schema`
so the JSON-contract test suite can enumerate the surface. Re-imported into
:mod:`~entrypoints.cli._ledger_payloads` so existing ``from ._ledger_payloads import
InventoryLedgerPayload`` (etc.) call sites keep resolving unchanged.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from pydantic import AfterValidator, Field

from ...core.identity import BucketId, InvoiceId, TaxIdIdentityToken
from ...core.json_contract import OutputSchema, register_schema
from ...domain.contribuyente.inventory import INVENTORY_SCHEMA_VERSION, MovementKind, ValuationMethod
from ._decimal_wire import bounded_decimal_wire_text
from ._wire_scalars import IsoDateText, enum_value_text

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")
_ONE = Decimal("1")

# The inventory transport is built by dumping the canonical InventoryLedger to
# JSON and re-validating the mapping, so every field below stays a string on
# the wire while carrying the canonical model's own bound.
_PositiveQuantity = bounded_decimal_wire_text(minimum=_ZERO, exclusive_minimum=True)
_NonNegativeAmount = bounded_decimal_wire_text(minimum=_ZERO)
_IvaRatePct = bounded_decimal_wire_text(minimum=_ZERO, maximum=_HUNDRED)
_DeductibleRatio = bounded_decimal_wire_text(minimum=_ZERO, maximum=_ONE)
_MovementKindText = enum_value_text(MovementKind)
_ValuationMethodText = enum_value_text(ValuationMethod)


def _validate_inventory_schema_version(value: str) -> str:
    """Refuse a schema version the canonical InventoryLedger would reject."""
    if value != INVENTORY_SCHEMA_VERSION:
        raise ValueError(f"unsupported inventory schema_version {value!r}; expected {INVENTORY_SCHEMA_VERSION!r}")
    return value


_InventorySchemaVersion = Annotated[str, AfterValidator(_validate_inventory_schema_version)]

if TYPE_CHECKING:
    from ...application.inventory import InventoryValuationPreviewResult as _AppInventoryValuationPreviewResult

# ---------------------------------------------------------------------------
# P07 — Inventory sub-app
# ---------------------------------------------------------------------------


class InventoryStockLayerPayload(OutputSchema):
    """One :class:`StockLayer` transport row."""

    sku: str = Field(default="default", min_length=1)
    quantity: _PositiveQuantity  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    unit_cost: _NonNegativeAmount  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    source_movement_id: str = Field(min_length=1)


class InventoryMovementPayload(OutputSchema):
    """One :class:`MovementRecord` transport row."""

    movement_id: str = Field(min_length=1)
    movement_date: IsoDateText
    kind: _MovementKindText  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    sku: str = Field(default="default", min_length=1)
    quantity: _PositiveQuantity  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    unit_cost: _NonNegativeAmount | None = None  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    taxable_base: _NonNegativeAmount | None = None  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    iva_rate: _IvaRatePct  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    iva_amount: _NonNegativeAmount | None = None  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    deductible_iva_ratio: _DeductibleRatio  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    schema_version: _InventorySchemaVersion


class InventoryLedgerPayload(OutputSchema):
    """One per-actividad inventory ledger record.

    Mirrors :class:`InventoryLedger`'s
    ``model_dump(mode='json')`` plus the ``bucket_event_ids`` field the
    CLI appends at the emit site.
    """

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    valuation_method: _ValuationMethodText  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    opening_stock: _NonNegativeAmount  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    opening_layers: list[InventoryStockLayerPayload] = []
    closing_stock: _NonNegativeAmount | None = None  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    period_movements: list[InventoryMovementPayload] = []
    schema_version: _InventorySchemaVersion
bucket_event_ids: list[str] = []


class InventoryListRowPayload(InventoryLedgerPayload):
    """One inventory summary row returned by the list command."""

    schema_version: str = "1"
    movement_count: int = 0


@register_schema("ledger.inventory.list")
class InventoryListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger inventory list``."""

    bucket_id: BucketId
    rows: list[InventoryListRowPayload]
    count: int


@register_schema("ledger.inventory.create")
class InventoryCreateResult(InventoryLedgerPayload):
    """JSON envelope for ``aeat app ledger inventory create``."""


@register_schema("ledger.inventory.movement.add")
class InventoryMovementAddResult(InventoryLedgerPayload):
    """JSON envelope for ``aeat app ledger inventory movement add``."""


@register_schema("ledger.inventory.valuation.preview")
class InventoryValuationPreviewPayload(OutputSchema):
    """JSON envelope for ``aeat app ledger inventory valuation preview``.

    Distinct from the application wrapper
    :class:`InventoryValuationPreviewResult`: this envelope *flattens* that wrapper, projecting its inner
    ``preview`` (:class:`InventoryValuationPreview`)
    fields and lifting the wrapper's ``bucket_event_ids`` to the top level.
    Derive via
    :meth:`~entrypoints.cli._ledger_business_payloads.InventoryValuationPreviewPayload.from_result`.
    """

    actividad_id: str
    year: int
    valuation_method: str
    closing_stock: str
    cogs: str
    bucket_event_ids: list[str] = []

    @classmethod
    def from_result(cls, result: _AppInventoryValuationPreviewResult) -> InventoryValuationPreviewPayload:
        """Flatten the application preview wrapper into this CLI envelope.

        The wrapper carries an inner ``preview`` plus ``bucket_event_ids``;
        ``model_dump(mode="json")`` on the inner preview performs the
        enum/Decimal coercion, and the event ids are lifted onto the same level.

        Returns:
            :class:`InventoryValuationPreviewPayload`:
            Flattened CLI JSON envelope.
        """
        data = result.preview.model_dump(mode="json")
        data["bucket_event_ids"] = list(result.bucket_event_ids)
        return cls.model_validate(data)


# ---------------------------------------------------------------------------
# P08 — Purchase-invoice evidence sub-app
# ---------------------------------------------------------------------------


class EvidenceRecordPayload(OutputSchema):
    """One purchase-invoice evidence record.

    Mirrors ``PurchaseInvoiceEvidence.model_dump(mode='json')`` plus the
    ``bucket_event_ids`` field the CLI appends at the emit site (defaults
    to empty for read verbs).
    """

    evidence_id: str
    bucket_id: BucketId
    source_path: str
    source_sha256: str
    attachment_id: str | None = None
    media_kind: str
    supplier: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None
    notes: str = ""
    created_at: str
    updated_at: str
    bucket_event_ids: list[str] = []


@register_schema("ledger.evidence.add")
class EvidenceAddResult(EvidenceRecordPayload):
    """JSON envelope for ``aeat app ledger evidence add``."""


@register_schema("ledger.evidence.view")
class EvidenceViewResult(EvidenceRecordPayload):
    """JSON envelope for ``aeat app ledger evidence view``."""


@register_schema("ledger.evidence.update")
class EvidenceUpdateResult(EvidenceRecordPayload):
    """JSON envelope for ``aeat app ledger evidence update``."""


@register_schema("ledger.evidence.remove")
class EvidenceRemoveResult(EvidenceRecordPayload):
    """JSON envelope for ``aeat app ledger evidence remove``."""


@register_schema("ledger.evidence.list")
class EvidenceListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger evidence list``."""

    bucket_id: BucketId
    count: int
    rows: list[EvidenceRecordPayload]


class AttachmentReviewPayload(OutputSchema):
    """Review-safe provenance for one encrypted attachment."""

    attachment_id: str
    sha256: str
    mime_type: str
    bytes_size: int
    source: str
    provider_locator: str
    captured_at: str
    linked_invoice_ids: list[str] = []
    pending_review: bool


@register_schema("ledger.evidence.attachment_queue")
class AttachmentReviewQueueResult(OutputSchema):
    """Pending Drive attachments awaiting explicit invoice confirmation."""

    bucket_id: BucketId
    count: int
    rows: list[AttachmentReviewPayload] = []


@register_schema("ledger.evidence.attachment_view")
class AttachmentReviewViewResult(AttachmentReviewPayload):
    """One stored attachment's non-secret metadata and provenance."""

    bucket_id: BucketId


class ConsentedDispatchPayload(OutputSchema):
    """One recorded off-host dispatch on the consent surface."""

    evidence_content_address: str
    provider: str
    model: str
    surface: str
    recorded_at: str


class CloudDerivedArtefactPayload(OutputSchema):
    """One artefact a withdrawal marks as derived from an off-host read."""

    evidence_reference: str
    provenance_stamp: str
    transport: str | None = None
    drafted_at: str
    rederivable_on_host: bool | None = None


@register_schema("ledger.evidence.consent.list")
class EvidenceConsentListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger evidence consent list``.

    ``transmitted_bytes_are_unrecallable`` is carried in the payload rather than
    only in the rendered text. A caveat that exists only in prose is invisible
    to the agent or script consuming this envelope, and this is the one caveat
    on this surface that must never be missed.
    """

    bucket_id: BucketId
    transmitted_bytes_are_unrecallable: bool
    consented_dispatches: list[ConsentedDispatchPayload]
    cloud_derived_artefacts: list[CloudDerivedArtefactPayload]


@register_schema("ledger.evidence.consent.rederive")
class EvidenceConsentRederiveResult(OutputSchema):
    """JSON envelope for ``aeat app ledger evidence consent rederive``.

    Both stamps are carried because the operation's whole meaning is their
    difference, and because the superseded stamp is not deleted anywhere: this
    records a new derivation rather than a relabelling of the old one.
    """

    bucket_id: BucketId
    evidence_reference: str
    previous_provenance_stamp: str
    provenance_stamp: str
    transcription_reused: bool
    transmitted_bytes_are_unrecallable: bool


class EvidenceDraftLinePayload(OutputSchema):
    """One extracted invoice line on the reviewable draft."""

    description: str | None = None
    quantity: str | None = None
    unit_price: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None
    recargo_rate: str | None = None
    recargo_amount: str | None = None


class EvidenceDraftRateBreakdownPayload(OutputSchema):
    """One per-rate subtotal extracted from a multi-rate invoice."""

    iva_rate: str | None = None
    taxable_base: str | None = None
    iva_amount: str | None = None
    recargo_rate: str | None = None
    recargo_amount: str | None = None


class EvidenceFieldAmbiguityCandidatePayload(OutputSchema):
    """One competing reading a grounding pass could not decide between."""

    value: str
    anchor: str | None = None
    note: str = ""


class EvidenceFieldProvenancePayload(OutputSchema):
    """How ONE draft field was obtained and what checking it survived.

    At parity with casilla grounding (``aeat-calculation-grounding``): the
    provenance the reading path established travels all the way to the operator
    rather than stopping at the application boundary. Without it the operator
    sees a value and cannot tell whether a parser read it out of the document's
    own machine-readable record or a vision model read it off a rendered page --
    and those warrant different scrutiny before a filing is built on them.

    Carries no numeric confidence, and none may be added: a model's estimate of
    its own output is not evidence about that output. ``origin`` and
    ``grounding`` are facts about what ran.
    """

    field: str
    origin: str
    grounding: str
    anchor: str | None = None
    # Mirrors FieldProvenance.refused_anchor. The printed form the reader DID
    # offer, on a field whose anchor the check looked for and did not find. It
    # rides beside the cleared anchor rather than in it, because the operator
    # needs to tell "the reader offered nothing" from "the reader offered
    # something this document does not carry" -- a reader limitation against a
    # possible misread or the wrong document, which are different next steps.
    refused_anchor: str | None = None
    candidates: list[EvidenceFieldAmbiguityCandidatePayload] = []
    # Whether the anchor was asserted by the reader that produced the value. The
    # operator MUST be able to tell the two apart: an anchor matched against an
    # independently produced transcription is evidence, while one a model
    # reported about its own output is a claim. Both are worth showing; showing
    # them identically is what would make the check decoration.
    anchor_self_reported: bool = False
    # Mirrors FieldProvenance.derived_from. A DERIVED value cites the inputs it
    # was computed from in place of an anchor, so the operator can see what a
    # derivation stood on rather than only that it happened.
    derived_from: list[str] = []
    # Mirrors FieldProvenance.role_evidence. For an identity field this is the
    # printed heading or label that assigns the identifier to a party, already
    # checked against the document's transcription. It reaches the operator
    # because it is the answer to the question the anchor cannot answer: two tax
    # identifiers on one invoice have the same printed shape, so knowing WHERE a
    # number was printed says nothing about WHOSE it is.
    role_evidence: str | None = None
    # Mirrors FieldProvenance.attribution_unverified. Whether anything checked
    # WHICH PARTY this value belongs to -- a different question from whether it
    # was read correctly, and one every anchor check is silent on. Per field
    # rather than per party because two values of one party can differ: a postal
    # code may be attributed while the country beside it is not.
    #
    # The territory such a value would establish is deliberately NOT here. This
    # surface prints what the paper said and leaves the regulatory reading to the
    # domain; the territory reaches the operator through the review envelope's
    # notice channel, which quotes the domain rather than giving the boundary a
    # second home on a payload.
    attribution_unverified: bool = False
    note: str = ""


class EvidenceDraftDiscrepancyPayload(OutputSchema):
    """One deterministic check the read document failed, shown at review time."""

    kind: str
    field: str | None = None
    detail: str = ""
    expected: str | None = None
    observed: str | None = None


@register_schema("ledger.evidence.extract")
class EvidenceExtractResult(OutputSchema):
    """JSON envelope for ``aeat app ledger evidence extract``.

    Mirrors ``InvoiceDraft.model_dump(mode='json')`` (the on-host best-effort
    extraction) plus the resolved reference id the operator supplied. This is a
    reviewable draft only: extracting never mints or persists an
    ``cadrumo.domain.invoices.Invoice`` -- the operator confirms the fields (via
    ``aeat app ledger invoice add`` / ``invoice add``) before any
    invoice record is created.
    """

    bucket_id: BucketId
    evidence_id: str | None = None
    attachment_id: str | None = None
    supplier_tax_id: TaxIdIdentityToken | None = None
    # Both parties, not just the supplier. A structured record names each side,
    # and which one is the counterparty depends on the direction of the invoice:
    # on one the filer issued it is the customer. Surfacing only the supplier
    # showed the operator their OWN identifier where the counterparty belongs.
    supplier_name: str | None = None
    customer_tax_id: TaxIdIdentityToken | None = None
    customer_name: str | None = None
    # The postal code each party's address prints, carried verbatim. The
    # operator sees the printed code, never the territory read off it: the
    # first two digits are province-coded, so Canarias, Ceuta and Melilla are
    # separable from the peninsula deterministically -- but that reading is the
    # domain's, and surfacing it here would put a second copy of a regulatory
    # boundary on the review surface.
    supplier_postal_code: str | None = None
    customer_postal_code: str | None = None
    # The country name each party's address prints, verbatim and in the
    # document's own language. Surfaced beside the postal code because the two
    # answer the same question at different resolutions: the country separates
    # Member States, the Spanish code separates Canarias and Ceuta y Melilla
    # from the peninsula. Neither reading is done here -- the operator sees what
    # the paper said, and the territory stays the domain's to resolve.
    supplier_country: str | None = None
    customer_country: str | None = None
    # The country CODE each party's record states, for the structured readers,
    # which state a code where a printed document prints a name. Carried beside
    # the name rather than folded into it: a document states one or the other,
    # and collapsing them would leave the operator unable to tell what the paper
    # actually carried. Always the ISO alpha-2 form even where the record stated
    # alpha-3 -- Facturae states `ESP` -- with the form the document itself
    # states recoverable from the field's provenance anchor.
    supplier_country_code: str | None = None
    customer_country_code: str | None = None
    # The token each party's record actually states, before the correspondence
    # above places it. Surfaced rather than left to the provenance anchor,
    # because the anchor exists only where a value was produced: a token the
    # bundled vocabulary does not carry -- `THA` for a Thai supplier -- leaves
    # the resolved field empty, and empty is what a document with no address
    # block leaves too. Carrying the stated form is what keeps those two
    # documents distinguishable on the operator's own surface.
    supplier_stated_country_code: str | None = None
    customer_stated_country_code: str | None = None
    invoice_number: str | None = None
    invoice_series: str | None = None
    rectifies_invoice_number: str | None = None
    proposed_supply_nature: str | None = None
    invoice_date: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None
    grand_total: str | None = None
    currency: str | None = None
    # Mirrors the rest of the draft the extractor produces. Omitting these left
    # the operator reviewing a total with no visible per-line or per-rate
    # breakdown -- and a recargo de equivalencia (LIVA art. 161) invisible at
    # the confirm step, which is where the operator is meant to catch it.
    recargo_amount: str | None = None
    # Retención, suplidos and the direction suggestion are read from the
    # document and were previously discarded on the way to this payload. A
    # retención the operator cannot see is a figure they cannot subtract to
    # reach the cash actually paid, and suplidos folded into the base
    # over-declare IVA on money that was never the issuer's revenue.
    retencion_rate: str | None = None
    retencion_amount: str | None = None
    suplidos_amount: str | None = None
    lines: list[EvidenceDraftLinePayload] = []
    iva_breakdown: list[EvidenceDraftRateBreakdownPayload] = []
    iva_category: str | None = None
    # The statutory mention the document PRINTS, carried verbatim. Transcriptive
    # evidence rather than a classification: the printed legend is on the page
    # and can be anchored, while the IVA category it implies is an internal
    # token no invoice prints. The operator sees the phrase and can disagree
    # with what was made of it.
    regime_legend: str | None = None
    # A SUGGESTION, never the decision. Direction is decided by the operator at
    # confirm through --kind; surfacing the reading path's reading of it lets
    # them disagree with something specific instead of guessing unaided.
    suggested_kind: str | None = None
    transcription_sha256: str | None = None
    provenance: list[EvidenceFieldProvenancePayload] = []
    discrepancies: list[EvidenceDraftDiscrepancyPayload] = []
    raw_text_length: int = 0
    # Recorded ONCE per read rather than per field, because consent is granted
    # per invocation and not per value: every field of one read shares one
    # transport, and a per-field copy would invite a reader to believe they
    # could differ.
    #
    # ``None`` on the default on-host route, which is the overwhelming majority
    # of reads -- an absent pair says "this never left the host", and saying it
    # by absence rather than by the word "local" keeps the affirmative case the
    # only one that carries a claim.
    #
    # What these record is the AUTHORISATION, not a confirmation that bytes
    # reached a vendor: they are populated from a token that could not have been
    # minted had the deployment posture, the profile bar or the acknowledgement
    # refused. A dispatch can still fail after that, and this pair does not
    # claim otherwise.
    off_host_provider: str | None = None
    off_host_acknowledged_surface: str | None = None


@register_schema("ledger.evidence.confirm")
class EvidenceConfirmResult(OutputSchema):
    """JSON envelope for ``aeat app ledger evidence extract --confirm``.

    Reports the persisted (or already-existing, on a guarded no-op) rich
    catalogue :class:`~domain.invoices.Invoice` -- mirroring
    ``CatalogueInvoiceRecordPayload`` -- plus the resolved evidence reference
    and a ``created`` flag distinguishing a fresh write
    (``aeat-cli-contract``) from a same-identity
    guarded retry.
    """

    bucket_id: BucketId
    evidence_id: str | None = None
    attachment_id: str | None = None
    created: bool
    invoice_id: InvoiceId
    kind: str
    invoice_number: str
    issued_at: str
    counterparty_name: str
    counterparty_tax_id: TaxIdIdentityToken
    counterparty_country: str
    base_total: str
    iva_total: str
    grand_total: str
    currency: str
    payment_status: str
    linked_transaction_ids: list[str] = []
    notes: str = ""
    # The IVA treatment this confirm recorded and the rung that established it.
    # Both ``None`` where no resolution was attempted; ``iva_category`` alone is
    # ``None`` where the resolution ran and withheld a treatment, which the
    # outcome then names. Carried as a pair deliberately: a category placed by
    # the rule table and one settled by the rate the lines charged are the same
    # string, and only the outcome distinguishes them at rest.
    iva_category: str | None = None
    iva_category_outcome: str | None = None
    # The euro conversion stamp and the euro projection of the totals, at
    # parity with the catalogue surface through the shared field tuple. Every
    # one is ``None`` on a euro invoice, and the eur trio is ``None`` on a
    # foreign invoice no rate could be resolved for -- so the operator sees the
    # unconverted state at confirm, which is where they can still act on it.
    fx_rate: str | None = None
    fx_rate_date: str | None = None
    fx_rate_source: str | None = None
    base_total_eur: str | None = None
    iva_total_eur: str | None = None
    grand_total_eur: str | None = None
    # The provenance of the DRAFT the confirmation was based on, carried onto
    # the confirm surface too. The persisted invoice above is the operator's
    # decision; these say what the document was read to say and how, so a later
    # reader can tell an exactly-parsed figure from a model-read one without
    # re-running the extraction (D5: nothing launders a vision read into an
    # exact-looking one).
    provenance: list[EvidenceFieldProvenancePayload] = []
    discrepancies: list[EvidenceDraftDiscrepancyPayload] = []
    # The same envelopes with every operator-asserted field re-stamped OPERATOR.
    # Carried BESIDE `provenance` rather than replacing it: a correction is an
    # assertion, so the record must still answer what the document said.
    confirmed_provenance: list[EvidenceFieldProvenancePayload] = []
    # Address of the persisted confirmation provenance record -- who confirmed,
    # which fields they asserted, which findings they answered and how.
    confirmation_id: str | None = None


class EvidenceReviewFieldPayload(OutputSchema):
    """One reviewable field: what was read, how, from where, and how sure.

    The review row the human review gate is built around. A field row that
    showed only the value would make an exactly-parsed structured figure and a
    vision model's guess look identical at exactly the moment a person is
    deciding whether to accept it.

    ``value`` is the reading as printed, and ``anchor`` is the verbatim form it
    was read from -- ``"1.234,56 EUR"`` against a ``1234.56`` value. A field with
    no anchor and an ``unanchored`` outcome is the anti-fabrication signal
    reaching the operator intact: nobody can point at it in the document.

    ``refused_anchor`` is what keeps that signal from meaning two things at once.
    A blank anchor is reached both by a reader that offered nothing and by a
    reader whose offered form the check could not find, and this is the row where
    an operator reads a field's grounding -- so without the refusal beside the
    blank, the two arrive here identical and the operator cannot tell a reader
    limitation from a possible misread.
    """

    field: str
    value: str | None = None
    origin: str | None = None
    grounding: str | None = None
    anchor: str | None = None
    refused_anchor: str | None = None
    anchor_self_reported: bool = False
    candidates: list[EvidenceFieldAmbiguityCandidatePayload] = []
    # The printed context assigning an identity field to its party role, shown
    # on the review row for the same reason the anchor is: a person deciding
    # whether to accept a counterparty identifier needs to see what on the page
    # said it was the counterparty's, not only that it verified.
    role_evidence: str | None = None
    note: str = ""


class EvidenceReviewBlockerPayload(OutputSchema):
    """One finding that must be answered before this document may be confirmed.

    ``blocker_id`` is the address a resolution names. It is derived from what
    the blocker IS and never from the clock, so an operator can read a listing,
    inspect the document, and resolve the finding later against ids that have
    not moved.
    """

    blocker_id: str
    reason: str
    field: str | None = None
    detail: str = ""
    candidates: list[EvidenceFieldAmbiguityCandidatePayload] = []


class EvidenceReviewRowPayload(OutputSchema):
    """One pending draft in the review queue."""

    evidence_reference: str
    extractor: str
    drafted_at: str
    blocking_count: int = 0
    reasons: list[str] = []
    # The queue's non-blocking half. A row carrying no blocker and two advisories
    # is a document nothing stops and something is wrong with, which the blocking
    # columns alone render identical to a clean one. Primary queue data rather
    # than a diagnostic: it is what the verb exists to report, per row, and the
    # channel carrying the operator's instruction about it is still `notices`.
    advisory_count: int = 0
    advisories: list[str] = []


@register_schema("ledger.evidence.review.list")
class EvidenceReviewListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger evidence review list``.

    The queue, never a confirmation surface. Every row is a document a person
    still has to look at; the filters narrow which ones, and narrowing to zero
    is an honest empty queue rather than a claim that nothing is pending.
    """

    bucket_id: BucketId
    filters: list[str] = []
    rows: list[EvidenceReviewRowPayload] = []


@register_schema("ledger.evidence.review.show")
class EvidenceReviewShowResult(OutputSchema):
    """JSON envelope for ``aeat app ledger evidence review show``.

    Everything the review gate requires a person to have in front of them for
    one document: every field with its value, origin, verbatim anchor, grounding
    outcome and any competing candidates; every deterministic finding; the
    direction the reading path SUGGESTS with the basis it read that from; and
    the blocking findings that must each be answered before confirm.

    The typed lists are the contract. The flat ``fields`` view is for
    readability and is never the thing a consumer should parse for provenance.
    """

    bucket_id: BucketId
    evidence_reference: str
    extractor: str
    drafted_at: str
    transcription_sha256: str | None = None
    suggested_kind: str | None = None
    suggested_kind_basis: str = ""
    fields: list[EvidenceReviewFieldPayload] = []
    discrepancies: list[EvidenceDraftDiscrepancyPayload] = []
    blockers: list[EvidenceReviewBlockerPayload] = []
