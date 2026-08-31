"""The mapping table's gate: it must fit the product, cover the key, and bite.

Every assertion here runs against the real pinned corpus and the real
:class:`~application.ledger.invoice_draft_records.InvoiceDraft`, because a map proved against a fixture
is proved against its author's memory of the two things it sits between -- which
is the failure it exists to remove.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.application.ledger.invoice_draft_records import InvoiceDraft

from .._field_mapping import (
    KEY_FIELD_MAPPINGS,
    FieldMapping,
    MappingKind,
    MappingValidationError,
    expand_document_slots,
    project_emission,
    unmapped_slot_census,
    validate_mapping_targets,
)
from .._key import CorpusDocument, CorpusKey
from .._scoring import score_emission

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_DRAFT_FIELDS = frozenset(InvoiceDraft.model_fields)
_NON_SCORED = (MappingKind.OUT_OF_SCOPE, MappingKind.PRODUCT_GAP)


# ----------------------------------------------------------------------------
# The table fits the two things it sits between
# ----------------------------------------------------------------------------


def test_every_mapping_target_is_a_real_draft_field(key: CorpusKey) -> None:
    """The whole point: no entry may name a field the product does not have."""
    validate_mapping_targets(draft_fields=_DRAFT_FIELDS, key=key)


def test_a_typo_in_a_mapping_target_is_refused(key: CorpusKey) -> None:
    """PROOF: the validator bites.

    Without this, one misspelled target silently books every one of that field's
    slots as a miss -- reintroducing, invisibly, the exact defect the table
    removes.
    """
    with pytest.raises(MappingValidationError, match=r"not a field on the draft"):
        validate_mapping_targets(draft_fields=_DRAFT_FIELDS - {"taxable_base"}, key=key)


def test_the_table_covers_every_field_the_key_authors(key: CorpusKey) -> None:
    """A corpus that grows a field must fail loudly, not score it as a miss."""
    authored = {name for document in key.documents for name in document.ground_truth}
    assert authored == set(KEY_FIELD_MAPPINGS)


def test_every_unmapped_entry_states_why(key: CorpusKey) -> None:
    """An unmapped field with no reason is one nobody has looked at yet."""
    for _kind, field_name, count, rationale in unmapped_slot_census(key):
        assert rationale.strip(), f"{field_name} ({count} authored) is unmapped with no stated reason"


# ----------------------------------------------------------------------------
# Each kind is populated, so no branch is proved over an empty set
# ----------------------------------------------------------------------------


def test_every_mapping_kind_is_populated() -> None:
    """A branch with no members would pass every test below vacuously."""
    kinds = {mapping.kind for mapping in KEY_FIELD_MAPPINGS.values()}
    assert kinds == set(MappingKind)


def test_both_role_branches_are_non_empty_in_the_corpus(key: CorpusKey) -> None:
    """Both sides of the role split must exist, or one branch is untested."""
    roles = [document.ground_truth.get("counterparty_role") for document in key.documents]
    assert roles.count("supplier") == 173
    assert roles.count("customer") == 47


# ----------------------------------------------------------------------------
# Role resolution follows the document, not a guess
# ----------------------------------------------------------------------------


def test_a_supplier_role_document_reads_the_supplier_field(key: CorpusKey) -> None:
    """PROOF: the supplier branch resolves."""
    document = next(d for d in key.documents if d.ground_truth.get("counterparty_role") == "supplier")

    projected = project_emission(document, {"supplier_name": "S", "customer_name": "C"})

    assert projected["counterparty_name"] == "S"


def test_a_customer_role_document_reads_the_customer_field(key: CorpusKey) -> None:
    """PROOF: the customer branch resolves, and to the OTHER field."""
    document = next(d for d in key.documents if d.ground_truth.get("counterparty_role") == "customer")

    projected = project_emission(document, {"supplier_name": "S", "customer_name": "C"})

    assert projected["counterparty_name"] == "C"


def test_an_unresolvable_role_slot_is_dropped_rather_than_missed(key: CorpusKey) -> None:
    """A slot that cannot be resolved is not a failed read.

    Counting it as missed would charge the model for the corpus declining to say
    which side the counterparty is on.
    """
    document = next(
        d
        for d in key.documents
        if "counterparty_name" in d.ground_truth and d.ground_truth.get("counterparty_role") is None
    )

    assert "counterparty_name" not in expand_document_slots(document).ground_truth


# ----------------------------------------------------------------------------
# Composites score leaf by leaf
# ----------------------------------------------------------------------------


def test_a_composite_expands_to_one_slot_per_leaf(key: CorpusKey) -> None:
    """The denominator is slots, not key field names."""
    document = next(d for d in key.documents if isinstance(d.ground_truth.get("issuer"), dict))

    slots = expand_document_slots(document).ground_truth

    assert "issuer" not in slots
    assert {"issuer.name", "issuer.tax_id"} <= set(slots)


def test_the_country_leaf_is_scored_against_the_resolved_code(key: CorpusKey) -> None:
    """The interim exclusion is retired, and the leaf now measures a real capability.

    The corpus states the country as an ISO code and the reader reports a
    printed name; the reading path derives the code from the name through the
    same vocabulary the structured e-invoice lane uses, so the leaf scores
    against something the path produces rather than docking it for a capability
    it lacked. The mapping points at the RESOLVED code field, not at the printed
    name, because the name would never equal the corpus value.
    """
    document = next(d for d in key.documents if isinstance(d.ground_truth.get("issuer"), dict))

    slots = expand_document_slots(document).ground_truth

    assert "issuer.country" in slots
    assert "recipient.country" in slots
    assert KEY_FIELD_MAPPINGS["issuer"].leaves["country"] == "supplier_country_code"
    assert KEY_FIELD_MAPPINGS["recipient"].leaves["country"] == "customer_country_code"


def test_one_wrong_leaf_does_not_destroy_the_others(key: CorpusKey) -> None:
    """PROOF: the whole reason composites expand.

    Spans BOTH composites so the independence is shown across three slots rather
    than two. Scored a composite at a time, this emission would be one wrong
    answer that also destroyed a correct read of the issuer's name and told a
    reader nothing about which leaf failed.
    """
    document = next(
        d
        for d in key.documents
        if isinstance(d.ground_truth.get("issuer"), dict) and isinstance(d.ground_truth.get("recipient"), dict)
    )
    issuer = document.ground_truth["issuer"]
    recipient = document.ground_truth["recipient"]
    payload = {
        "supplier_name": issuer["name"],
        "supplier_tax_id": "WRONG-TAX-ID",
        "customer_name": recipient["name"],
        "customer_tax_id": recipient["tax_id"],
    }

    expanded = expand_document_slots(document)
    scoring = score_emission(document=expanded, emitted=project_emission(document, payload))
    verdicts = {outcome.field_name: outcome.verdict for outcome in scoring.outcomes}

    assert verdicts["issuer.name"].value == "matched"
    assert verdicts["issuer.tax_id"].value == "wrong"
    assert verdicts["recipient.name"].value == "matched"
    assert verdicts["recipient.tax_id"].value == "matched"


# ----------------------------------------------------------------------------
# Unmapped fields are never scored
# ----------------------------------------------------------------------------


def test_an_unmapped_field_never_becomes_a_miss(key: CorpusKey) -> None:
    """A product that cannot hold a field is not a model that failed to read it."""
    document = next(d for d in key.documents if d.ground_truth.get("known_defects") is not None)

    slots = expand_document_slots(document).ground_truth

    assert "known_defects" not in slots
    assert "line_count_exact" not in slots


# ----------------------------------------------------------------------------
# The two totals are opposite in the two systems
# ----------------------------------------------------------------------------


def _divergent_total_documents(key: CorpusKey) -> tuple[CorpusDocument, ...]:
    """Documents whose printed total disagrees with the computed identity."""
    return tuple(
        d
        for d in key.documents
        if d.ground_truth.get("printed_total") is not None
        and d.ground_truth.get("grand_total") is not None
        and Decimal(str(d.ground_truth["printed_total"])) != Decimal(str(d.ground_truth["grand_total"]))
    )


def test_the_divergent_total_documents_still_exist(key: CorpusKey) -> None:
    """The anti-vacuity guard for every assertion below.

    A test over the 27 agreeing documents passes under BOTH mappings and proves
    nothing. Only the divergent pair can tell the printed figure from the computed
    one, so their existence is pinned before they are relied on.
    """
    divergent = _divergent_total_documents(key)

    assert len(divergent) == 2
    for document in divergent:
        printed = Decimal(str(document.ground_truth["printed_total"]))
        computed = Decimal(str(document.ground_truth["grand_total"]))
        base = Decimal(str(document.ground_truth["base_total"]))
        iva = Decimal(str(document.ground_truth["iva_total"]))
        assert printed == Decimal("890.00")
        assert computed == base + iva == Decimal("927.22")


def test_a_divergent_document_scores_the_printed_figure_not_the_computed_one(key: CorpusKey) -> None:
    """PROOF: a reader that copied the page is scored correct, not wrong.

    The draft's ``grand_total`` is the PRINTED figure. Emitting what the page
    stated is exactly right, and the previous mapping scored it wrong on the only
    two documents that can tell the difference.
    """
    document = _divergent_total_documents(key)[0]
    expanded = expand_document_slots(document)

    scoring = score_emission(document=expanded, emitted=project_emission(document, {"grand_total": "890.00"}))
    verdicts = {outcome.field_name: outcome.verdict for outcome in scoring.outcomes}

    assert verdicts["printed_total"].value == "matched"
    assert "grand_total" not in verdicts, "the computed identity must not also claim the draft's printed slot"


def test_a_divergent_document_scores_the_computed_figure_wrong(key: CorpusKey) -> None:
    """The other side of the same proof: recomputing is not reading.

    Without this, a mapping that credited both figures would pass the case above
    while still being unable to tell them apart.
    """
    document = _divergent_total_documents(key)[0]
    expanded = expand_document_slots(document)

    scoring = score_emission(document=expanded, emitted=project_emission(document, {"grand_total": "927.22"}))
    verdicts = {outcome.field_name: outcome.verdict for outcome in scoring.outcomes}

    assert verdicts["printed_total"].value == "wrong"


def test_a_document_stating_no_printed_total_still_scores_its_total(key: CorpusKey) -> None:
    """The 184 documents that declare only the one total keep their slot.

    A plain swap of the two names would have dropped every one of them from the
    denominator, trading a fix on 2 documents for a loss of measurement on 184.
    """
    document = next(
        d
        for d in key.documents
        if d.ground_truth.get("grand_total") is not None and d.ground_truth.get("printed_total") is None
    )

    slots = expand_document_slots(document).ground_truth

    assert "grand_total" in slots
    assert "printed_total" not in slots


def test_the_unmapped_census_reports_both_groups_separately(key: CorpusKey) -> None:
    """The ruling is taken over this list, so it must carry counts AND kinds.

    Both groups must be non-empty: a census reporting one kind would let a
    coverage gap be read as a corpus annotation, or hide it entirely.
    """
    census = unmapped_slot_census(key)

    assert census, "no unscored fields enumerated; the census would be a vacuous report"
    by_kind = {kind: [name for k, name, _, _ in census if k is kind] for kind in _NON_SCORED}
    assert by_kind[MappingKind.OUT_OF_SCOPE], "no out-of-scope fields; that group is unproved"
    assert by_kind[MappingKind.PRODUCT_GAP], "no product-gap fields; that group is unproved"
    assert {name: count for _, name, count, _ in census}["counterparty_role"] == 220


def test_a_product_gap_is_never_reported_as_out_of_scope(key: CorpusKey) -> None:
    """The two groups must not pool: they are different findings.

    ``printed_total`` is the sharp case -- the corpus checks it against the
    computed total to catch a document whose printed figure disagrees with its
    own arithmetic, and the draft cannot hold it. Filing that under "corpus
    annotation" would bury a capability gap.
    """
    kinds = {name: kind for kind, name, _, _ in unmapped_slot_census(key)}

    assert kinds["issuer_address"] is MappingKind.PRODUCT_GAP
    assert kinds["known_defects"] is MappingKind.OUT_OF_SCOPE


# ----------------------------------------------------------------------------
# The projection moves values and does nothing else
# ----------------------------------------------------------------------------


def test_the_projection_does_not_normalise_a_malformed_value(key: CorpusKey) -> None:
    """A projection that tidied a value would convert a reading failure to a match."""
    document = next(d for d in key.documents if d.ground_truth.get("base_total") is not None)

    projected = project_emission(document, {"taxable_base": "  1.234,56  "})

    assert projected["base_total"] == "  1.234,56  "


def test_an_absent_draft_field_is_absent_from_the_projection(key: CorpusKey) -> None:
    """Not emitted must stay not emitted, so it scores as a miss and not a wrong."""
    document = next(d for d in key.documents if d.ground_truth.get("base_total") is not None)

    assert "base_total" not in project_emission(document, {})


# ----------------------------------------------------------------------------
# The mapping shape refuses to be half-filled
# ----------------------------------------------------------------------------


def test_a_direct_mapping_without_a_target_is_refused() -> None:
    """Each kind reads one set of fields; a half-filled entry would behave as another."""
    with pytest.raises(ValueError, match=r"must name draft_field"):
        FieldMapping(kind=MappingKind.DIRECT)


def test_a_role_mapping_with_only_one_branch_is_refused() -> None:
    """One branch named is the shape that would silently always pick that branch."""
    with pytest.raises(ValueError, match=r"both supplier_field and customer_field"):
        FieldMapping(kind=MappingKind.ROLE_DEPENDENT, supplier_field="supplier_name")


def test_a_composite_mapping_without_leaves_is_refused() -> None:
    """A composite with no leaves expands to nothing and scores nothing."""
    with pytest.raises(ValueError, match=r"must name its leaves"):
        FieldMapping(kind=MappingKind.COMPOSITE)


@pytest.mark.parametrize("kind", _NON_SCORED)
def test_an_unscored_entry_without_a_reason_is_refused(kind: MappingKind) -> None:
    """An unscored field with no reason is one nobody has looked at yet.

    Both kinds, because an exclusion is only reviewable if it says why, and a
    guard covering one of the two would leave the other free to be silent.
    """
    with pytest.raises(ValueError, match=r"must state why"):
        FieldMapping(kind=kind)


def test_a_non_direct_mapping_naming_draft_field_is_refused() -> None:
    """``draft_field`` on a composite would be read by nothing and mislead a reader."""
    with pytest.raises(ValueError, match=r"draft_field is not read for a composite"):
        FieldMapping(kind=MappingKind.COMPOSITE, leaves={"a": "b"}, draft_field="x")


def test_a_superseded_mapping_missing_either_half_is_refused() -> None:
    """Both halves are load-bearing: the slot it claims and the field that displaces it."""
    with pytest.raises(ValueError, match=r"both draft_field and superseded_by"):
        FieldMapping(kind=MappingKind.SUPERSEDED, draft_field="grand_total")


def test_superseded_by_on_a_direct_mapping_is_refused() -> None:
    """A field nothing reads would mislead the next reader into trusting it."""
    with pytest.raises(ValueError, match=r"superseded_by is not read for a direct"):
        FieldMapping(kind=MappingKind.DIRECT, draft_field="grand_total", superseded_by="printed_total")
