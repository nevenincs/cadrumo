"""The declared map from the corpus key's vocabulary to the product's draft fields.

The corpus key and :class:`~application.ledger.evidence_draft.InvoiceDraft` name the same
concepts differently. Measured over the pinned key: of the key's 33 field names
only 7 spell a draft field identically, so a scorer comparing by name alone
credits 711 of the corpus's 2873 non-null truth slots and books the rest as
misses. A pilot run scored 3 of 16 on a document whose figures the model had in
fact read correctly, which is a number about a dictionary rather than about a
model.

**The map is DATA, never translating code.** A function that "helpfully"
normalises a value on the way across converts a reading failure into a match and
does it invisibly; a table can only say which name stands for which. Nothing here
transforms a value -- :func:`project_emission` moves values between names and does
nothing else. Comparison stays where it already was, in
:mod:`~dev.ingest_harness._scoring`.

**The instrument adapts to the corpus, not the corpus to the instrument.** The
key is the external authority, and the product's vocabulary is a domain decision
grounded in AEAT concepts. So this map lives in the harness; growing a
corpus-shaped view inside the product would leave the harness measuring a shim.

Four kinds, because the concepts genuinely differ in kind and flattening them
loses a measurement each time:

:attr:`MappingKind.DIRECT`
    One key field, one draft field. Includes the seven that already agree.

:attr:`MappingKind.ROLE_DEPENDENT`
    ``counterparty_name`` and ``counterparty_tax_id`` resolve to the supplier or
    the customer field according to the document's own ``counterparty_role``. A
    rule, not a rename: 173 corpus documents are supplier-role and 47 are
    customer-role, so a map that picked one would be wrong 47 or 173 times.

:attr:`MappingKind.COMPOSITE`
    ``issuer`` and ``recipient`` are dicts in the key and three flat fields on the
    draft. Each leaf is scored as **its own slot**, so one wrong leaf cannot
    destroy a correct read of the other two -- and the report says which leaf
    failed. This RAISES the slot denominator: two composite fields become six
    slots, and :func:`expand_document_slots` is the only place that denominator
    is computed.

:attr:`MappingKind.OUT_OF_SCOPE` and :attr:`MappingKind.PRODUCT_GAP`
    Two reasons a key field is never scored, kept apart because they are two
    different findings. Out-of-scope is a corpus assertion ABOUT the document, so
    a reader declining to emit it is not wrong. A product gap is a real field of
    the document the draft cannot hold, so a reader cannot be scored on it and
    the absence is a fact about the PRODUCT.

    **Never pooled -- with each other, or into ``missed``.** One headline number
    over all three would hide a coverage gap inside a reading score.
    :func:`unmapped_slot_census` reports them separately.

See Also:
    :func:`~dev.ingest_harness.score_emission`
        Consumes the projection this module produces; the verdict logic is there.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._key import CorpusDocument, CorpusKey
from ._result import PipelineStage

__all__ = [
    "COMPOSITE_LEAF_SEPARATOR",
    "KEY_FIELD_MAPPINGS",
    "FieldMapping",
    "MappingKind",
    "MappingValidationError",
    "expand_document_slots",
    "project_emission",
    "slots_unavailable_at",
    "unmapped_slot_census",
    "validate_mapping_targets",
]

_STRICT = ConfigDict(frozen=True, strict=True, extra="forbid")

COMPOSITE_LEAF_SEPARATOR: Final = "."
"""Joins a composite key field to its leaf, as in ``issuer.tax_id``.

Slot names stay readable in a report and stay distinct from every flat field
name, because no key field contains a dot.
"""

#: The role token naming the counterparty as the document's supplier.
_ROLE_SUPPLIER: Final = "supplier"
#: The role token naming the counterparty as the document's customer.
_ROLE_CUSTOMER: Final = "customer"


class MappingValidationError(RuntimeError):
    """The declared map does not fit the product it claims to map onto."""


class MappingKind(StrEnum):
    """How a key field reaches the draft, or that it does not."""

    DIRECT = "direct"
    """One key field, one draft field."""

    ROLE_DEPENDENT = "role_dependent"
    """Resolves to one of two draft fields by the document's ``counterparty_role``."""

    COMPOSITE = "composite"
    """A dict in the key; separate flat draft fields, each scored as its own slot."""

    SUPERSEDED = "superseded"
    """Maps to a draft field, but yields to a more specific key field when that
    field carries truth.

    Exists for the two totals, which are OPPOSITE in the two systems. The corpus
    key's ``grand_total`` is the COMPUTED identity (base plus tax) and its
    ``printed_total`` is WHAT THE PAGE STATES. The draft's ``grand_total`` is the
    PRINTED figure -- it is what ``printed_total_discrepancy`` reads as
    ``printed``. So the draft field holds the page's number, and only one corpus
    key may occupy it per document: ``printed_total`` where the corpus states one,
    ``grand_total`` everywhere else, where the two coincide.

    Measured over the pinned corpus: 213 documents author ``grand_total``, 29 of
    them also author ``printed_total``, and 2 of those DIVERGE -- a page printing
    890.00 against a base of 766.30 plus tax of 160.92 that sums to 927.22. Those
    two are the entire reason the corpus carries the field, and mapping the
    computed total onto the printed one scores a correct read as wrong on exactly
    them while staying invisible on the other 211.
    """

    OUT_OF_SCOPE = "out_of_scope"
    """A corpus assertion ABOUT the document, not a field printed on it.

    Excluded from the reading denominator and NAMED in the record. A reader is
    not wrong for failing to emit the corpus's own annotation, and a denominator
    that shrinks without saying so is the shape that has misled this campaign
    before.
    """

    PRODUCT_GAP = "product_gap"
    """A real field of the document that the draft has nowhere to hold.

    Excluded from the reading denominator and reported as a COVERAGE finding: a
    reader cannot be scored on a slot the product cannot represent, and the
    absence is a fact about the product rather than about the model.
    """


#: Kinds enumerated in the record but never entering a reading denominator. A
#: named set rather than a literal at each site: three places branch on it, and a
#: later non-scored kind added to only two of them would silently start counting
#: as a miss.
_NON_SCORED_KINDS: Final = frozenset({MappingKind.OUT_OF_SCOPE, MappingKind.PRODUCT_GAP})

#: Kinds that name a single draft field directly.
_DRAFT_FIELD_KINDS: Final = frozenset({MappingKind.DIRECT, MappingKind.SUPERSEDED})


class FieldMapping(BaseModel):
    """One key field's route to the draft, or its declared absence.

    Attributes:
        rationale: Required on the non-scored kinds only, where it states
            what the absence means. An unmapped field with no stated reason is
            indistinguishable from one nobody has looked at yet.
        available_from: The earliest pipeline stage whose output can carry this
            field at all. Defaults to extraction, which is where the reading
            contract's own fields appear.

            Declared because two of these fields are produced STAGES LATER than
            the rest, and the map could not say so: a capture taken at the
            extraction seam reads them as ``None`` for every document, which is
            indistinguishable from a reader that never produces them. That
            residual is on record as having motivated a proposal to route both
            through the LLM classifier -- replacing two deterministic
            authorities with probabilistic ones, to fix a measurement artefact.
    """

    model_config = _STRICT

    kind: MappingKind
    draft_field: str | None = None
    supplier_field: str | None = None
    customer_field: str | None = None
    leaves: Mapping[str, str] = Field(default_factory=dict)
    superseded_by: str | None = None
    rationale: str = ""
    available_from: PipelineStage = PipelineStage.S2_EXTRACTION

    @model_validator(mode="after")
    def _shape_matches_kind(self) -> Self:
        """Refuse a mapping whose payload does not match the kind it declares.

        Each kind reads exactly one set of fields, so a half-filled entry would
        silently behave as whichever kind the consumer happened to branch on.
        """
        if self.kind is MappingKind.DIRECT and not self.draft_field:
            raise ValueError("a direct mapping must name draft_field")
        if self.kind is MappingKind.ROLE_DEPENDENT and not (self.supplier_field and self.customer_field):
            raise ValueError("a role-dependent mapping must name both supplier_field and customer_field")
        if self.kind is MappingKind.COMPOSITE and not self.leaves:
            raise ValueError("a composite mapping must name its leaves")
        if self.kind is MappingKind.SUPERSEDED and not (self.draft_field and self.superseded_by):
            raise ValueError("a superseded mapping must name both draft_field and superseded_by")
        if self.kind in _NON_SCORED_KINDS and not self.rationale.strip():
            raise ValueError("an unscored field must state why it is not scored")
        if self.kind not in _DRAFT_FIELD_KINDS and self.draft_field:
            raise ValueError(f"draft_field is not read for a {self.kind.value} mapping")
        if self.kind is not MappingKind.SUPERSEDED and self.superseded_by:
            raise ValueError(f"superseded_by is not read for a {self.kind.value} mapping")
        return self

    def target_fields(self) -> tuple[str, ...]:
        """Every draft field this entry names, for validation against the model."""
        if self.kind is MappingKind.DIRECT and self.draft_field:
            return (self.draft_field,)
        if self.kind is MappingKind.ROLE_DEPENDENT:
            return tuple(name for name in (self.supplier_field, self.customer_field) if name)
        if self.kind is MappingKind.COMPOSITE:
            return tuple(self.leaves.values())
        return ()


def _direct(draft_field: str) -> FieldMapping:
    return FieldMapping(kind=MappingKind.DIRECT, draft_field=draft_field)


def _out_of_scope(rationale: str) -> FieldMapping:
    return FieldMapping(kind=MappingKind.OUT_OF_SCOPE, rationale=rationale)


def _product_gap(rationale: str) -> FieldMapping:
    return FieldMapping(kind=MappingKind.PRODUCT_GAP, rationale=rationale)


KEY_FIELD_MAPPINGS: Final[Mapping[str, FieldMapping]] = MappingProxyType(
    {
        # ── Identical spellings. Listed rather than inferred, so the table is a
        # complete statement about the key's vocabulary instead of a diff of it.
        # The two totals are opposite in the two systems; see MappingKind.SUPERSEDED.
        # The key's grand_total is the COMPUTED identity, the draft's is the PRINTED
        # figure, and they coincide except where the corpus states a printed total
        # of its own -- so this one scores the draft field only while that is absent.
        "grand_total": FieldMapping(
            kind=MappingKind.SUPERSEDED,
            draft_field="grand_total",
            superseded_by="printed_total",
        ),
        # What the page states, which is exactly what the draft's grand_total holds.
        "printed_total": _direct("grand_total"),
        "invoice_number": _direct("invoice_number"),
        "currency": _direct("currency"),
        "iva_rate": _direct("iva_rate"),
        "recargo_amount": _direct("recargo_amount"),
        "lines": _direct("lines"),
        # Decided by the single classification authority at the CONFIRM
        # boundary, not by any reader. Nothing earlier can carry it.
        "iva_category": FieldMapping(
            kind=MappingKind.DIRECT,
            draft_field="iva_category",
            available_from=PipelineStage.S4_CLASSIFICATION,
        ),
        # ── Same concept, different spelling. Each verified against the corpus.
        "issue_date": _direct("invoice_date"),
        "iva_total": _direct("iva_amount"),
        "base_total": _direct("taxable_base"),
        "retention_amount": _direct("retencion_amount"),
        "retention_rate_pct": _direct("retencion_rate"),
        "suplido_amount": _direct("suplidos_amount"),
        "series": _direct("invoice_series"),
        "tax_breakdown": _direct("iva_breakdown"),
        # Derived deterministically by the grounding pass from the filer's own
        # tax identity, one stage after the reader returns. A reader is not
        # asked for it and cannot be scored on it.
        "category": FieldMapping(
            kind=MappingKind.DIRECT,
            draft_field="suggested_kind",
            available_from=PipelineStage.S3_GROUNDING,
        ),
        # ── Resolved by the document's own counterparty_role.
        "counterparty_name": FieldMapping(
            kind=MappingKind.ROLE_DEPENDENT,
            supplier_field="supplier_name",
            customer_field="customer_name",
        ),
        "counterparty_tax_id": FieldMapping(
            kind=MappingKind.ROLE_DEPENDENT,
            supplier_field="supplier_tax_id",
            customer_field="customer_tax_id",
        ),
        # ── Dicts in the key, flat fields on the draft. Scored leaf by leaf.
        # The country leaf scores against the RESOLVED code rather than the
        # printed name the reader reports, because the corpus states an alpha-2
        # code. The reading path now derives that code from the name through the
        # same vocabulary the structured lane uses, so the leaf measures a
        # capability the path has.
        "issuer": FieldMapping(
            kind=MappingKind.COMPOSITE,
            leaves=MappingProxyType(
                {
                    "name": "supplier_name",
                    "tax_id": "supplier_tax_id",
                    "country": "supplier_country_code",
                },
            ),
        ),
        "recipient": FieldMapping(
            kind=MappingKind.COMPOSITE,
            leaves=MappingProxyType(
                {
                    "name": "customer_name",
                    "tax_id": "customer_tax_id",
                    "country": "customer_country_code",
                },
            ),
        ),
        # ── No draft counterpart. Each states what its absence means; whether a
        # given one is a product gap or out of scope is a ruling recorded
        # elsewhere, not a judgement this table makes silently.
        # Corpus assertions ABOUT the document. A reader is not wrong for
        # declining to emit the corpus's own annotation.
        "known_defects": _out_of_scope("corpus annotation listing planted defects; not a field on any invoice"),
        "line_count_exact": _out_of_scope("corpus assertion that the line count is exact; not printed on the document"),
        "doc_type_code": _out_of_scope("corpus taxonomy code; not a figure a reader recovers from the page"),
        "counterparty_role": _out_of_scope(
            "consumed HERE as the role-resolution input; the product takes the counterparty side from the "
            "ledger's direction rather than reading it off the page, so scoring a reader on it would score "
            "it on an input the harness itself supplied",
        ),
        # Real fields of the document with nowhere on the draft to hold them.
        "issuer_address": _product_gap("issuer postal address; the draft carries only postal_code and country"),
        "amount_due": _product_gap("amount outstanding after prior payment; no draft counterpart"),
        "reverse_charge": _product_gap("reverse-charge flag; the draft carries regime_legend, not a boolean"),
        "document_type": _product_gap(
            "factura / simplificada / rectificativa / nota_de_adeudo -- a different axis from suggested_kind, "
            "which carries the purchase-versus-issued distinction. No product derivation produces it",
        ),
        "operation_date": _product_gap("date of operation where it differs from the invoice date; no draft field"),
        "recargo_rate_pct": _product_gap("recargo rate; the draft carries recargo_amount but no rate field"),
        "other_withholding_amount": _product_gap("non-IRPF withholding amount; no draft counterpart"),
        "other_withholding_type_code": _product_gap("non-IRPF withholding type; no draft counterpart"),
    },
)
"""Every field name the pinned key authors anywhere, mapped or declared unmapped.

Complete by construction rather than by diff: a key field absent from this table
is a :exc:`MappingValidationError` from :func:`validate_mapping_targets`, so a
corpus that grows a field fails loudly instead of scoring it as a miss.
"""


def validate_mapping_targets(*, draft_fields: frozenset[str], key: CorpusKey) -> None:
    """Refuse a map that does not fit the draft or does not cover the key.

    The typo guard. A mapping entry naming a draft field that does not exist
    would project nothing and book every one of that field's slots as a miss --
    exactly the defect this table was written to remove, silently reintroduced by
    one misspelling.

    Args:
        draft_fields: Field names actually declared on the product's draft model.
        key: The pinned corpus key, whose authored field names must all be covered.

    Raises:
        MappingValidationError: When an entry names an absent draft field, or the
            key authors a field the table does not mention.
    """
    problems: list[str] = []
    for key_field, mapping in KEY_FIELD_MAPPINGS.items():
        for target in mapping.target_fields():
            if target not in draft_fields:
                problems.append(f"{key_field}: maps to {target!r}, which is not a field on the draft")

    authored = {name for document in key.documents for name in document.ground_truth}
    for missing in sorted(authored - set(KEY_FIELD_MAPPINGS)):
        problems.append(f"{missing}: authored by the key but absent from the mapping table")
    for stale in sorted(set(KEY_FIELD_MAPPINGS) - authored):
        problems.append(f"{stale}: in the mapping table but authored by no document in this key")

    if problems:
        raise MappingValidationError(
            "the declared field map does not fit what it maps between:\n  " + "\n  ".join(problems),
        )


#: Key fields that displace another key field from its draft slot when they carry
#: truth. Derived from the table rather than hand-listed, so a second superseding
#: pair cannot be added on one side only.
_SUPERSEDING_FIELDS: Final = frozenset(
    mapping.superseded_by
    for mapping in KEY_FIELD_MAPPINGS.values()
    if mapping.kind is MappingKind.SUPERSEDED and mapping.superseded_by
)


def _claims_draft_slot(key_field: str, document: CorpusDocument) -> bool:
    """Whether this key field occupies its draft slot for THIS document.

    Exactly one member of a superseding pair may occupy one draft field, or the
    two would contradict each other: the superseding field's ``null`` truth would
    declare a fabrication trap on the very field its partner is being scored on.

    The superseding field wins wherever it carries truth. Where it carries
    ``null`` -- 96 corpus documents state no separate printed total -- it yields
    entirely, trap included, because its ``null`` means "no figure distinct from
    the computed one" rather than "this document has no total".
    """
    mapping = KEY_FIELD_MAPPINGS[key_field]
    if mapping.kind is MappingKind.SUPERSEDED and mapping.superseded_by:
        return document.ground_truth.get(mapping.superseded_by) is None
    if key_field in _SUPERSEDING_FIELDS:
        return document.ground_truth.get(key_field) is not None
    return True


def _resolved_role_target(mapping: FieldMapping, document: CorpusDocument) -> str | None:
    """Resolve a role-dependent mapping against the document's own role fact."""
    role = document.ground_truth.get("counterparty_role")
    if role == _ROLE_SUPPLIER:
        return mapping.supplier_field
    if role == _ROLE_CUSTOMER:
        return mapping.customer_field
    return None


def expand_document_slots(document: CorpusDocument) -> CorpusDocument:
    """Return the document with its truth expanded into scorable SLOTS.

    Composite fields become one slot per leaf, so a wrong leaf costs one slot
    rather than three; unmapped fields are dropped entirely, so they can never be
    counted as misses. **This is the only place the slot denominator is set**, and
    it is deliberately not the count of key field names.

    A role-dependent field whose document declares no usable role is dropped too:
    the slot cannot be resolved, and an unresolvable slot is not a failed read.
    """
    slots: dict[str, Any] = {}
    for key_field, truth in document.ground_truth.items():
        mapping = KEY_FIELD_MAPPINGS.get(key_field)
        if mapping is None or mapping.kind in _NON_SCORED_KINDS:
            continue
        if not _claims_draft_slot(key_field, document):
            continue
        if mapping.kind is MappingKind.COMPOSITE:
            if not isinstance(truth, Mapping):
                continue
            for leaf in mapping.leaves:
                slots[f"{key_field}{COMPOSITE_LEAF_SEPARATOR}{leaf}"] = truth.get(leaf)
            continue
        if mapping.kind is MappingKind.ROLE_DEPENDENT and _resolved_role_target(mapping, document) is None:
            continue
        slots[key_field] = truth
    return document.model_copy(update={"ground_truth": slots})


#: Stages in pipeline order, so "can this stage reach that one" is a comparison
#: rather than a hand-maintained set of pairs. The two lane stages are absent
#: deliberately: ``TABULAR_MAPPING`` is its own lane rather than a point on this
#: line, and ``END_TO_END`` runs the whole pipeline, so both can carry every
#: field and neither is ordered against the seams.
_STAGE_ORDER: Final[tuple[PipelineStage, ...]] = (
    PipelineStage.S1_TRANSCRIPTION,
    PipelineStage.S2_EXTRACTION,
    PipelineStage.S3_GROUNDING,
    PipelineStage.S4_CLASSIFICATION,
)


def slots_unavailable_at(document: CorpusDocument, stage: PipelineStage) -> tuple[str, ...]:
    """Return the document's scorable slots that *stage* structurally cannot carry.

    A slot the stage cannot produce is not a failed read. Scoring it books a
    guaranteed miss against the reader and inflates the denominator with a
    question the capture point never asked, and the resulting residual reads
    exactly like a reader that never produces the field. Two fields on the
    pinned key are produced after extraction -- one by the grounding pass, one
    by the classification authority at confirm -- so a capture at the extraction
    seam mismeasures both, on every document that authors them.

    Measured over the pinned key: of 302 documents, **221** author at least one
    slot the extraction seam cannot carry, and 29 still do at the grounding
    seam. None do at classification. So this is not a corner -- a capture at
    extraction mismeasured most of the corpus, and the residual it produced was
    read as a product gap rather than as an artefact of where the capture was
    taken.

    Returns the slot names in key order, empty when the stage can carry every
    slot the document authors. A stage outside the seam ordering
    (``TABULAR_MAPPING``, ``END_TO_END``) reaches everything and yields nothing.

    Reads the document's truth as given rather than expanding it, so it is
    correct for a raw document AND for one already through
    :func:`expand_document_slots` -- a caller has usually expanded before
    scoring, and expanding again would drop every composite leaf, whose slot
    name is not a key field. The composite prefix is split off before the
    lookup for the same reason.
    """
    if stage not in _STAGE_ORDER:
        return ()
    reached = _STAGE_ORDER.index(stage)
    unavailable: list[str] = []
    for slot in document.scorable_fields:
        key_field = slot.split(COMPOSITE_LEAF_SEPARATOR, 1)[0]
        mapping = KEY_FIELD_MAPPINGS.get(key_field)
        if mapping is None or mapping.available_from not in _STAGE_ORDER:
            continue
        if _STAGE_ORDER.index(mapping.available_from) > reached:
            unavailable.append(slot)
    return tuple(unavailable)


def project_emission(document: CorpusDocument, draft_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Re-key a draft payload into the corpus's slot vocabulary.

    Moves values between names and does nothing else: no parsing, no coercion, no
    normalisation. A value that arrives malformed stays malformed and is scored
    wrong, which is the point -- a projection that tidied it would convert a
    reading failure into a match.
    """
    projected: dict[str, Any] = {}
    for key_field, mapping in KEY_FIELD_MAPPINGS.items():
        if mapping.kind in _NON_SCORED_KINDS or not _claims_draft_slot(key_field, document):
            continue
        if mapping.kind in _DRAFT_FIELD_KINDS:
            direct = mapping.draft_field
            if direct is not None and direct in draft_payload:
                projected[key_field] = draft_payload[direct]
        elif mapping.kind is MappingKind.ROLE_DEPENDENT:
            target = _resolved_role_target(mapping, document)
            if target is not None and target in draft_payload:
                projected[key_field] = draft_payload[target]
        elif mapping.kind is MappingKind.COMPOSITE:
            for leaf, target in mapping.leaves.items():
                if target in draft_payload:
                    projected[f"{key_field}{COMPOSITE_LEAF_SEPARATOR}{leaf}"] = draft_payload[target]
    return projected


def unmapped_slot_census(key: CorpusKey) -> tuple[tuple[MappingKind, str, int, str], ...]:
    """Enumerate every unmapped key field with the truth it carries corpus-wide.

    The report the ruling is taken over: each row is a field the product cannot
    represent, the number of documents that author a real value for it, and the
    stated reason. Ordered by weight, because a field with 220 authored values and
    one with a single value are not the same finding.

    Carries the KIND, so a caller cannot render one total over both groups: a
    coverage gap and a corpus annotation are different findings, and a single
    "excluded" figure would hide the first inside the second.

    Returns:
        ``(kind, field_name, non_null_truth_count, rationale)`` per unscored field.
    """
    rows: list[tuple[MappingKind, str, int, str]] = []
    for key_field, mapping in KEY_FIELD_MAPPINGS.items():
        if mapping.kind not in _NON_SCORED_KINDS:
            continue
        count = sum(1 for document in key.documents if document.ground_truth.get(key_field) is not None)
        rows.append((mapping.kind, key_field, count, mapping.rationale))
    return tuple(sorted(rows, key=lambda row: (row[0].value, -row[2], row[1])))
