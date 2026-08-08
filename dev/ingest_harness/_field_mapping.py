"""The declared map from the corpus key's vocabulary to the product's draft fields.

The corpus key and :class:`~application.ledger.InvoiceDraft` name the same
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

:attr:`MappingKind.UNMAPPED`
    The key declares it and the draft has nowhere to put it. **Never scored, never
    pooled into ``missed``.** A product that cannot represent a field and a model
    that failed to read one are different findings, and averaging them together
    hides both. :func:`unmapped_slot_census` enumerates them for the record.

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

__all__ = [
    "COMPOSITE_LEAF_SEPARATOR",
    "KEY_FIELD_MAPPINGS",
    "FieldMapping",
    "MappingKind",
    "MappingValidationError",
    "expand_document_slots",
    "project_emission",
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

    UNMAPPED = "unmapped"
    """The draft cannot represent it. Reported, never scored."""


class FieldMapping(BaseModel):
    """One key field's route to the draft, or its declared absence.

    Attributes:
        rationale: Required on :attr:`MappingKind.UNMAPPED` only, where it states
            what the absence means. An unmapped field with no stated reason is
            indistinguishable from one nobody has looked at yet.
    """

    model_config = _STRICT

    kind: MappingKind
    draft_field: str | None = None
    supplier_field: str | None = None
    customer_field: str | None = None
    leaves: Mapping[str, str] = Field(default_factory=dict)
    rationale: str = ""

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
        if self.kind is MappingKind.UNMAPPED and not self.rationale.strip():
            raise ValueError("an unmapped field must state why it is unmapped")
        if self.kind is not MappingKind.DIRECT and self.draft_field:
            raise ValueError(f"draft_field is only read for a direct mapping, not {self.kind.value}")
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


def _unmapped(rationale: str) -> FieldMapping:
    return FieldMapping(kind=MappingKind.UNMAPPED, rationale=rationale)


KEY_FIELD_MAPPINGS: Final[Mapping[str, FieldMapping]] = MappingProxyType(
    {
        # ── Identical spellings. Listed rather than inferred, so the table is a
        # complete statement about the key's vocabulary instead of a diff of it.
        "grand_total": _direct("grand_total"),
        "invoice_number": _direct("invoice_number"),
        "currency": _direct("currency"),
        "iva_rate": _direct("iva_rate"),
        "recargo_amount": _direct("recargo_amount"),
        "lines": _direct("lines"),
        "iva_category": _direct("iva_category"),
        # ── Same concept, different spelling. Each verified against the corpus.
        "issue_date": _direct("invoice_date"),
        "iva_total": _direct("iva_amount"),
        "base_total": _direct("taxable_base"),
        "retention_amount": _direct("retencion_amount"),
        "retention_rate_pct": _direct("retencion_rate"),
        "suplido_amount": _direct("suplidos_amount"),
        "series": _direct("invoice_series"),
        "tax_breakdown": _direct("iva_breakdown"),
        "category": _direct("suggested_kind"),
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
        "issuer": FieldMapping(
            kind=MappingKind.COMPOSITE,
            leaves=MappingProxyType(
                {"name": "supplier_name", "tax_id": "supplier_tax_id", "country": "supplier_country_code"},
            ),
        ),
        "recipient": FieldMapping(
            kind=MappingKind.COMPOSITE,
            leaves=MappingProxyType(
                {"name": "customer_name", "tax_id": "customer_tax_id", "country": "customer_country_code"},
            ),
        ),
        # ── No draft counterpart. Each states what its absence means; whether a
        # given one is a product gap or out of scope is a ruling recorded
        # elsewhere, not a judgement this table makes silently.
        "counterparty_role": _unmapped("drives role resolution here; not itself an extraction target"),
        "line_count_exact": _unmapped("corpus assertion ABOUT the document, not a field printed on it"),
        "known_defects": _unmapped("corpus annotation listing planted defects; not a field on any invoice"),
        "doc_type_code": _unmapped("corpus taxonomy code; the draft carries no document-code field"),
        "document_type": _unmapped("document classification; no draft counterpart distinct from suggested_kind"),
        "printed_total": _unmapped("printed-versus-computed total; the draft has no printed-total field"),
        "issuer_address": _unmapped("issuer postal address; the draft carries only postal_code and country"),
        "amount_due": _unmapped("amount outstanding after prior payment; no draft counterpart"),
        "operation_date": _unmapped("date of operation where it differs from the invoice date; no draft field"),
        "reverse_charge": _unmapped("reverse-charge flag; the draft carries regime_legend, not a boolean"),
        "recargo_rate_pct": _unmapped("recargo rate; the draft carries recargo_amount but no rate field"),
        "other_withholding_amount": _unmapped("non-IRPF withholding amount; no draft counterpart"),
        "other_withholding_type_code": _unmapped("non-IRPF withholding type; no draft counterpart"),
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
        if mapping is None or mapping.kind is MappingKind.UNMAPPED:
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


def project_emission(document: CorpusDocument, draft_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Re-key a draft payload into the corpus's slot vocabulary.

    Moves values between names and does nothing else: no parsing, no coercion, no
    normalisation. A value that arrives malformed stays malformed and is scored
    wrong, which is the point -- a projection that tidied it would convert a
    reading failure into a match.
    """
    projected: dict[str, Any] = {}
    for key_field, mapping in KEY_FIELD_MAPPINGS.items():
        if mapping.kind is MappingKind.UNMAPPED:
            continue
        if mapping.kind is MappingKind.DIRECT:
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


def unmapped_slot_census(key: CorpusKey) -> tuple[tuple[str, int, str], ...]:
    """Enumerate every unmapped key field with the truth it carries corpus-wide.

    The report the ruling is taken over: each row is a field the product cannot
    represent, the number of documents that author a real value for it, and the
    stated reason. Ordered by weight, because a field with 220 authored values and
    one with a single value are not the same finding.

    Returns:
        ``(field_name, non_null_truth_count, rationale)`` per unmapped field.
    """
    rows: list[tuple[str, int, str]] = []
    for key_field, mapping in KEY_FIELD_MAPPINGS.items():
        if mapping.kind is not MappingKind.UNMAPPED:
            continue
        count = sum(1 for document in key.documents if document.ground_truth.get(key_field) is not None)
        rows.append((key_field, count, mapping.rationale))
    return tuple(sorted(rows, key=lambda row: (-row[1], row[0])))
