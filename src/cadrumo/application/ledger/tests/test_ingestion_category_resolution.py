"""One authority decides an ingested record's IVA category, and says what decided it.

The confirm path once carried two rival deciding surfaces and consulted the rule
table through neither. The convergence keeps both evidences and moves only the
deciding: the document's declared UNTDID 5305 code arrives as a supplied FACT on
:class:`~application.ledger.classification_assembly.DeclaredFacts`, the charged rate arrives as the
criteria's own ``rate_tier`` axis, and
:func:`~application.ledger.classification_assembly.resolve_ingestion_iva_category` weighs them.

**What is asserted here is the adjudication contract, never a tax figure.** No
test below claims a category is the legally correct treatment of a synthetic
operation -- that claim needs an AEAT worked example, and manufacturing one from
the same rule table under test would be tautological. These pin which input wins,
which conflict refuses, and that a refusal carries a reason a person can act on.
The one legally-grounded end-to-end claim -- that a declared reverse charge
survives to the persisted record -- is proved against a bundled corpus document
in its own module, where the asserted value is the code the document states.

The contradiction cases matter most. A document declaring one treatment while
its own evidence points at another is the shape that silently picks a filing:
the reverse-charge, exempt and zero-rated populations all print a base and no
cuota, so whichever side is taken decides whether self-assessed output IVA is
ever declared. This resolution takes neither and says so.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....core import ClassifierInputSource, IvaCategoryOutcome
from ....domain.iva.classification import CustomerTaxStatus, InvoiceKind, IvaTerritorialScope
from ....domain.iva.establishment import record_country_code_status, stated_country_code_status
from ....domain.iva.schema import IvaCategory, IvaRateKind
from ....domain.iva.supply_nature import SupplyNature
from ....tests.country_vocabulary_specimens import an_uncatalogued_alpha2, an_uncatalogued_alpha3
from ..classification_assembly import (
    DeclaredFact,
    DeclaredFacts,
    assemble_classification_criteria,
    declared_category_from_document_record,
    resolve_ingestion_iva_category,
)
from ..classifier_inputs import collect_classifier_inputs
from ..evidence_draft import InvoiceDraft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ES = IvaTerritorialScope.ES_MAINLAND
_WHEN = date(2026, 3, 1)


def _fact[T](value: T) -> DeclaredFact[T]:
    """Wrap a value as an operator assertion, the sanctioned supply route."""
    return DeclaredFact(value=value, source=ClassifierInputSource.OPERATOR_ASSERTION)


def _facts(*, established: bool, stated: IvaCategory | None = None) -> DeclaredFacts:
    """Build the supplied facts for an operation the table can or cannot place.

    ``established=True`` supplies both territories, the customer's status and the
    supply nature, which is everything the table needs for a domestic operation.
    ``established=False`` supplies none of them, which is the ordinary shape of a
    domestic invoice printing no country -- the population the table refuses.
    """
    stated_fact = None if stated is None else _fact(stated)
    if not established:
        return DeclaredFacts(stated_category=stated_fact)
    return DeclaredFacts(
        issuer_scope=_fact(_ES),
        customer_scope=_fact(_ES),
        customer_tax_status=_fact(CustomerTaxStatus.B2B_IVA_REGISTERED),
        supply_nature=_fact(SupplyNature.GOODS),
        stated_category=stated_fact,
    )


def _resolve(
    *,
    established: bool,
    stated: IvaCategory | None = None,
    rate_tier: IvaRateKind | None = None,
):
    """Assemble and resolve through the real production path, with no doubles.

    The assembly, the rule table behind it and the resolution are all the shipped
    ones; only the evidence is supplied, which is what the declared-facts channel
    exists to accept.
    """
    declared = _facts(established=established, stated=stated)
    assembly = assemble_classification_criteria(
        transaction_date=_WHEN,
        direction=InvoiceKind.RECEIVED,
        inputs=collect_classifier_inputs(InvoiceDraft(), profile=None),
        declared=declared,
        rate_tier=rate_tier,
    )
    return resolve_ingestion_iva_category(assembly, declared=declared, rate_tier=rate_tier)


# --------------------------------------------------------------------------
# The supplied-fact reader: the one place a category is built from a token.
# --------------------------------------------------------------------------


def test_a_declared_code_is_read_into_a_fact_carrying_its_attribution() -> None:
    """The code becomes a fact beside WHO established it, not a bare value.

    The attribution travels with the value because they are one claim: a
    classification resting on the document's own record must be distinguishable
    later from one resting on an operator's assertion.
    """
    fact = declared_category_from_document_record(IvaCategory.DOMESTIC_REVERSE_CHARGE.value)

    assert fact is not None
    assert fact.value is IvaCategory.DOMESTIC_REVERSE_CHARGE
    assert fact.source is ClassifierInputSource.DOCUMENT_EVIDENCE


@pytest.mark.parametrize("printed", [None, "", "   ", "not-a-category-token"])
def test_an_absent_blank_or_unrecognised_code_establishes_nothing(printed: str | None) -> None:
    """Four shapes of "the document declared no special category", all silent.

    A standard-rated supply states the code for "standard rate", which by design
    carries no special treatment, so it arrives blank. An unrecognised token
    resolves to nothing rather than raising: refusing the whole confirm over a
    label the operator can supply would block a filing the rest of the record
    fully supports.
    """
    assert declared_category_from_document_record(printed) is None


# --------------------------------------------------------------------------
# Adjudication: which input decides, and when neither may.
# --------------------------------------------------------------------------


def test_an_unplaceable_operation_with_no_evidence_resolves_to_nothing() -> None:
    """The honest blank. No territory, no code, no tier settles anything."""
    resolution = _resolve(established=False)

    assert resolution.outcome is IvaCategoryOutcome.UNRESOLVED
    assert resolution.category is None


def test_a_declared_code_survives_an_operation_the_table_cannot_place() -> None:
    """The convergence's load-bearing case: the structured signal is NOT lost.

    A reverse charge is the population that costs a declaration. The table
    refuses it -- its reverse-charge kinds carry legal consequences a printed
    goods-or-services reading cannot establish -- so before this channel existed
    the only surface carrying the code was the one being removed. Losing it makes
    a domestic reverse charge, an exempt supply and a zero-rated supply
    indistinguishable.
    """
    resolution = _resolve(established=False, stated=IvaCategory.DOMESTIC_REVERSE_CHARGE)

    assert resolution.outcome is IvaCategoryOutcome.DECLARED
    assert resolution.category is IvaCategory.DOMESTIC_REVERSE_CHARGE
    assert resolution.declared is not None


def test_the_rule_table_decides_when_it_can_place_the_operation() -> None:
    """A fully-established operation is classified by the table, not by the rate.

    Asserted on the OUTCOME rather than on which category came back: the claim
    is that the deciding moved to the table, and asserting the category here
    against a synthetic operation would be a number derived from the table under
    test.
    """
    resolution = _resolve(established=True, rate_tier=IvaRateKind.GENERAL)

    assert resolution.outcome is IvaCategoryOutcome.CLASSIFIED
    assert resolution.category is not None
    assert resolution.category is resolution.classified


def test_the_table_and_an_agreeing_code_corroborate() -> None:
    """Two independent routes reaching one answer is the strongest state.

    The declared code is taken from the table's own verdict for this operation
    so the two genuinely agree; what is asserted is that agreement is RECORDED
    as such rather than silently collapsing into the single-source outcome.
    """
    verdict = _resolve(established=True, rate_tier=IvaRateKind.GENERAL).category
    assert verdict is not None

    resolution = _resolve(established=True, stated=verdict, rate_tier=IvaRateKind.GENERAL)

    assert resolution.outcome is IvaCategoryOutcome.CORROBORATED
    assert resolution.category is verdict
    assert resolution.declared is not None


def test_a_code_disagreeing_with_the_table_takes_neither_side() -> None:
    """The silent-filing-pick, refused and explained.

    Both halves are named in the note because the operator is the only party who
    can say which is wrong, and a refusal pointing at one of them would have
    already picked. No category is carried, on the same terms the legend axis
    withholds one: a caller holding the value would use it while ignoring the
    conflict.
    """
    verdict = _resolve(established=True, rate_tier=IvaRateKind.GENERAL).category
    assert verdict is not None
    rival = next(c for c in (IvaCategory.DOMESTIC_REVERSE_CHARGE, IvaCategory.DOMESTIC_EXEMPT) if c is not verdict)

    resolution = _resolve(established=True, stated=rival, rate_tier=IvaRateKind.GENERAL)

    assert resolution.outcome is IvaCategoryOutcome.CONTRADICTED
    assert resolution.category is None, "a contradicted document must not hand a caller either side"
    assert resolution.classified is verdict
    assert rival.value in resolution.note and verdict.value in resolution.note


def test_a_declared_domestic_code_disagreeing_with_the_tier_charged_contradicts() -> None:
    """The corroboration the rate evidence now performs, in place of deriving.

    The document declares the super-reducido treatment while its lines charge the
    general tier. That is the document disagreeing with ITSELF -- a question the
    rule table cannot answer, because the declared code never enters the
    criteria -- so it is the one check the rate half still owns.
    """
    resolution = _resolve(
        established=False,
        stated=IvaCategory.DOMESTIC_SUPER_REDUCED,
        rate_tier=IvaRateKind.GENERAL,
    )

    assert resolution.outcome is IvaCategoryOutcome.CONTRADICTED
    assert resolution.category is None
    assert "general" in resolution.note and "super_reduced" in resolution.note


def test_the_tier_corroboration_is_silent_on_a_category_carrying_no_tier() -> None:
    """A reverse charge beside a charged tier is not a tier mismatch.

    The domestic-category/rate-tier correspondence answers ``None`` for
    intra-community, export, import, reverse-charge and recargo treatments, and
    that is the honest answer rather than a disagreement: those categories carry
    no tier derivable from the category alone. Reading it as a mismatch would
    fire on the very population the declared code exists to preserve.
    """
    resolution = _resolve(
        established=False,
        stated=IvaCategory.DOMESTIC_REVERSE_CHARGE,
        rate_tier=IvaRateKind.GENERAL,
    )

    assert resolution.outcome is IvaCategoryOutcome.DECLARED
    assert resolution.category is IvaCategory.DOMESTIC_REVERSE_CHARGE


def test_an_unplaceable_operation_charging_a_registered_tier_stays_declarable() -> None:
    """The commonest document must not fall out of the declaration.

    A domestic Spanish invoice frequently prints no country at all, so the table
    refuses it. Leaving those records with no treatment is not neutral: the
    invoice decomposition contract refuses an undeclared record, and the renta
    income path then contributes the row's bank cash instead of its ingresos
    íntegros, dropping the base, the cuota and the retención.

    The outcome is named rather than folded into ``CLASSIFIED`` precisely so a
    later reader can enumerate the records resting on the inference.
    """
    resolution = _resolve(established=False, rate_tier=IvaRateKind.GENERAL)

    assert resolution.outcome is IvaCategoryOutcome.RATE_INFERRED
    assert resolution.category is IvaCategory.DOMESTIC_GENERAL
    assert resolution.classified is None, "nothing was classified; the tier alone carried this"


def test_a_domestic_case_derives_with_the_supply_nature_unknown_and_asks_nothing() -> None:
    """The laziness rule, exercised rather than described.

    The rule table consults the supply kind ONLY to route the three
    reverse-charge kinds and the exempt immovable supply, and the customer's
    status only for the same branches -- none of which a printed
    goods-or-services reading can produce. So on an ordinary domestic invoice
    every value of both axes reaches the identical category, and demanding
    either would ask the operator a question with no consequence on the
    commonest document there is.

    Asserted as a fixture because the laziness otherwise ships as prose: the
    ``missing`` list must be EMPTY, not merely short. A regression that started
    demanding the nature would still return a category here and would only be
    visible as an operator prompt nobody could answer from the page.
    """
    declared = DeclaredFacts(issuer_scope=_fact(_ES), customer_scope=_fact(_ES))
    assembly = assemble_classification_criteria(
        transaction_date=_WHEN,
        direction=InvoiceKind.RECEIVED,
        inputs=collect_classifier_inputs(InvoiceDraft(), profile=None),
        declared=declared,
        rate_tier=IvaRateKind.GENERAL,
    )
    resolution = resolve_ingestion_iva_category(assembly, declared=declared, rate_tier=IvaRateKind.GENERAL)

    assert [gap.field for gap in assembly.missing] == [], (
        "a domestic operation asked the operator for an axis its treatment cannot turn on"
    )
    assert assembly.assembled
    assert resolution.outcome is IvaCategoryOutcome.CLASSIFIED, (
        "the domestic case must reach the rule table, not fall back to the tier inference"
    )
    assert resolution.category is not None


def test_the_inference_never_displaces_a_verdict_or_a_declaration() -> None:
    """Anti-vacuity for the fallback: it is reached only when nothing else answers.

    A fallback that fired while a stronger input was present would silently
    overwrite the rule table's own verdict, which is the failure the convergence
    exists to end rather than to relocate. Both stronger inputs are checked
    against the SAME tier that would otherwise have inferred a category.
    """
    with_verdict = _resolve(established=True, rate_tier=IvaRateKind.GENERAL)
    with_declaration = _resolve(
        established=False,
        stated=IvaCategory.DOMESTIC_REVERSE_CHARGE,
        rate_tier=IvaRateKind.GENERAL,
    )

    assert with_verdict.outcome is IvaCategoryOutcome.CLASSIFIED
    assert with_declaration.outcome is IvaCategoryOutcome.DECLARED
    assert with_declaration.category is IvaCategory.DOMESTIC_REVERSE_CHARGE, (
        "the tier inference displaced the document's own declaration, which is the "
        "signal only a structured reader recovers"
    )


# --------------------------------------------------------------------------
# A declared relief resting on an establishment nothing established.
# --------------------------------------------------------------------------


def _relief(
    stated: IvaCategory,
    *,
    country_code: str | None = None,
    direction: InvoiceKind = InvoiceKind.ISSUED,
):
    """Resolve a declared relief claim through the real assembly and resolver."""
    declared = _facts(established=False, stated=stated)
    assembly = assemble_classification_criteria(
        transaction_date=_WHEN,
        direction=direction,
        inputs=collect_classifier_inputs(InvoiceDraft(), profile=None),
        declared=declared,
    )
    return resolve_ingestion_iva_category(
        assembly,
        declared=declared,
        # Which party the counterparty IS, which is what says which residency
        # slot the catalogue-gap exemption may forgive. Without it the exemption
        # forgives nothing: a caller that cannot name the counterparty cannot
        # claim our vocabulary is what failed.
        direction=direction,
        # The RECORD authority, which is the one the confirm path uses. The
        # printed-value sibling beside it answers differently for an alpha-3
        # token -- measured, 'ESP' is catalogued to this one and unresolved to
        # that one -- so deriving the status here through the other authority
        # would gate this guard on a value production never hands it.
        counterparty_country_status=record_country_code_status(country_code),
    )


@pytest.mark.parametrize(
    "stated",
    [IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED, IvaCategory.INTRA_COMMUNITY_SUPPLY],
)
def test_a_declared_relief_is_withheld_when_no_establishment_was_reached(stated: IvaCategory) -> None:
    """The gap the DECLARED branch left open, closed for both relieving codes.

    Each relieves the supply of Spanish output IVA purely on where the
    counterparty is -- LIVA art. 25 for the intra-community supply, art. 21 for
    the export. Nothing else in the resolution catches this: the tier
    corroboration is silent on every non-domestic category by construction, and
    there is no rule-table verdict to disagree with precisely BECAUSE the
    establishment is missing. So the claim passed every other rung.
    """
    resolution = _relief(stated)

    assert resolution.outcome is IvaCategoryOutcome.UNSUPPORTED_RELIEF
    assert resolution.category is None, "a relieved category was honoured for a party nobody could place"
    assert resolution.declared is not None, "the document's own claim must survive on the record"
    assert stated.value in resolution.note


def test_the_withheld_relief_is_not_reported_as_a_contradiction() -> None:
    """Absent establishment does not make the document wrong, and must not say so.

    A contradiction sends the operator to decide which half to believe; this
    sends them to supply the establishment. Collapsing the two would send them
    to re-read a page that was never the problem -- the document may be entirely
    correct and the evidence simply does not reach its claim.
    """
    resolution = _relief(IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED)

    assert resolution.outcome is not IvaCategoryOutcome.CONTRADICTED
    assert "not established by this document" in resolution.note
    assert "does not disprove the claim" in resolution.note


def test_a_resolved_export_to_a_genuine_third_country_is_honoured() -> None:
    """The other direction: the guard must not reject real exports.

    A guard that fires on the legitimate population is worse than none, because
    an operator meeting false refusals stops reading them. Here both territories
    resolve, so no residency gap is recorded and the claim stands untouched.
    """
    declared = DeclaredFacts(
        issuer_scope=_fact(_ES),
        customer_scope=_fact(IvaTerritorialScope.THIRD_COUNTRY),
        stated_category=_fact(IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED),
    )
    assembly = assemble_classification_criteria(
        transaction_date=_WHEN,
        direction=InvoiceKind.ISSUED,
        inputs=collect_classifier_inputs(InvoiceDraft(), profile=None),
        declared=declared,
    )
    resolution = resolve_ingestion_iva_category(
        assembly,
        declared=declared,
        counterparty_country_status=stated_country_code_status("US"),
    )

    assert resolution.outcome is IvaCategoryOutcome.DECLARED
    assert resolution.category is IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED


def test_a_country_our_vocabulary_does_not_carry_forgives_that_partys_slot() -> None:
    """Our data gap must not be charged to the taxpayer -- and ONLY our gap is forgiven.

    The specimen is measured, not hypothetical, and it is DERIVED rather than
    named: the shipped country vocabulary classifies it UNCATALOGUED, so the
    scope resolver answers nothing and the establishment is recorded as a gap --
    while the document printed a well-formed code naming a real third country.
    Refusing on THAT rejects a legitimate export over a row we have not written.

    **The exemption is scoped to that one slot, and this fixture is why the
    scoping matters.** It establishes neither party, so the filer's own residency
    is outstanding too -- an unfinished profile rather than a hole in our data,
    which the document under review cannot fix and which the counterparty's
    excuse does not cover. So the claim is still withheld and the REASON narrows
    to the filer alone. Forgiving the whole set honoured a zero-rated export with
    NEITHER party established, which is the under-declaration direction, and it
    became reachable the moment the counterparty's stated token started arriving
    here at all.

    Asserting the narrowed reason rather than an honoured claim is deliberate: it
    shows the exemption fired without requiring it to prove more than it should.
    That the claim STANDS once no other residency is outstanding is gated where a
    document can supply the country and a profile can supply the filer.

    The control below makes this attributable to the STATUS rather than to a
    guard that had simply stopped naming the counterparty: with no country
    printed, both slots are named.
    """
    forgiven = _relief(IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED, country_code=an_uncatalogued_alpha2())

    assert forgiven.outcome is IvaCategoryOutcome.UNSUPPORTED_RELIEF
    assert "issuer_residency" in forgiven.note
    assert "customer_residency" not in forgiven.note

    refused = _relief(IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED, country_code=None)
    assert refused.outcome is IvaCategoryOutcome.UNSUPPORTED_RELIEF, (
        "positive control: with no country printed the same claim must still be refused, "
        "or the narrowing above proves nothing about the status axis"
    )
    assert "customer_residency" in refused.note, (
        "and the counterparty's slot must be NAMED when nothing excused it, or the narrowing "
        "above is a guard that stopped mentioning it rather than an exemption that fired"
    )


@pytest.mark.parametrize("country_code", ["XX", "E1"])
def test_a_code_naming_no_country_does_not_spare_the_claim(country_code: str) -> None:
    """The sparing is narrow: only a well-formed UNCATALOGUED code earns it.

    ``XX`` sits in the ISO 3166-1 user-assigned range, which names no country by
    construction, and ``E1`` is not a two-letter code at all. Neither can name a
    jurisdiction our vocabulary merely lacks, so neither is our data gap and
    neither establishes anything about where the party is.
    """
    resolution = _relief(IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED, country_code=country_code)

    assert resolution.outcome is IvaCategoryOutcome.UNSUPPORTED_RELIEF


@pytest.mark.parametrize(
    "stated",
    [IvaCategory.DOMESTIC_REVERSE_CHARGE, IvaCategory.DOMESTIC_EXEMPT, IvaCategory.OPERACION_NO_SUJETA],
)
def test_a_declared_code_that_rests_on_no_establishment_is_untouched(stated: IvaCategory) -> None:
    """The guard is scoped to the two relieving categories and nothing else.

    A domestic reverse charge also prints no cuota, but it OBLIGES the recipient
    to self-assess output IVA, so mis-honouring it over-declares rather than
    under-declares and is not this hazard. Widening the set to every zero-cuota
    code would withhold the reverse-charge treatment this guard exists to
    preserve.
    """
    resolution = _relief(stated)

    assert resolution.outcome is IvaCategoryOutcome.DECLARED
    assert resolution.category is stated


def _record_relief(
    stated: IvaCategory,
    *,
    country_token: str | None = None,
    direction: InvoiceKind = InvoiceKind.ISSUED,
):
    """Resolve a relief claim the way a STRUCTURED record reaches the guard.

    Two things differ from :func:`_relief`, and both are needed for a case that
    can spare at all.

    The status axis. ``stated_country_code_status`` answers only about alpha-2,
    which is right for a value transcribed off a printed page, so a helper built
    on it cannot present an alpha-3 token to the guard: every case would arrive
    as ``None``. The confirm path classifies the record's own token with
    ``record_country_code_status``, so this does too.

    The filer's own territory is supplied. It is a PROFILE fact in production,
    known independently of the document, so leaving it out models a state a
    confirm does not reach -- and the catalogue-gap exemption forgives only the
    counterparty's slot, so with the filer also unplaced nothing can ever be
    spared and every assertion below would hold for any status whatsoever.
    """
    declared = DeclaredFacts(issuer_scope=_fact(_ES), stated_category=_fact(stated))
    assembly = assemble_classification_criteria(
        transaction_date=_WHEN,
        direction=direction,
        inputs=collect_classifier_inputs(InvoiceDraft(), profile=None),
        declared=declared,
    )
    return resolve_ingestion_iva_category(
        assembly,
        declared=declared,
        counterparty_country_status=record_country_code_status(country_token),
        # Which party the counterparty IS, which is what says which residency
        # slot the catalogue-gap exemption may forgive.
        direction=direction,
    )


@pytest.mark.parametrize("reserved", ["ZZZ", "QMA", "XAA"])
@pytest.mark.parametrize(
    "stated",
    [IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED, IvaCategory.INTRA_COMMUNITY_SUPPLY],
)
def test_a_reserved_alpha3_does_not_spare_a_declared_relief(stated: IvaCategory, reserved: str) -> None:
    """The alpha-2 half of this rule was gated; the alpha-3 half was not.

    Facturae states the alpha-3 spelling, so a reserved three-letter token is a
    shape a real Spanish document can present -- and the failure direction is
    the bad one. A reserved code mistaken for a catalogue gap would be SPARED,
    honouring a relief claimed on a token with no referent, which is the
    sparing-a-relief direction rather than the refusing-a-real-export one.

    These codes are NAMED rather than derived, the opposite of the
    catalogue-gap specimen's treatment and correct for the opposite reason. ISO
    reserves ``QMA``-``QZZ``, ``XAA``-``XZZ`` and ``ZZA``-``ZZZ`` for private
    use, so no vocabulary will ever admit them and there is no boundary here to
    track. The spared case below is derived, because THAT boundary moves every
    time a country is enrolled.
    """
    resolution = _record_relief(stated, country_token=reserved)

    assert resolution.outcome is IvaCategoryOutcome.UNSUPPORTED_RELIEF, (
        f"{reserved} names no country by construction, yet it spared a declared {stated.value}"
    )
    assert resolution.category is None, "a relief was honoured on a code with no referent"


def test_the_alpha3_sparing_boundary_runs_where_the_vocabulary_does() -> None:
    """The positive control, without which the refusals above prove nothing.

    A helper that could never spare would pass every reserved case while saying
    nothing about reserved-ness -- which is exactly what this control caught
    when the filer's own territory was left unsupplied. This is the same claim
    through the same helper, differing only in that the token names a real
    jurisdiction the bundled vocabulary has not enrolled.
    """
    spared = _record_relief(
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        country_token=an_uncatalogued_alpha3(),
    )

    assert spared.outcome is IvaCategoryOutcome.DECLARED, (
        "an alpha-3 naming a country our vocabulary omits is OUR gap and must be spared; "
        "if this refuses, the reserved-code assertions above are vacuous"
    )
    assert spared.category is IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED


def test_a_catalogued_alpha3_export_is_honoured_outright() -> None:
    """The legitimate population, stated the way Facturae states it.

    ``USA`` places the counterparty in a third country, so no residency gap is
    recorded and the claim never reaches the guard. A fix that refused this
    would trade an under-declaration for an over-payment, which nothing in this
    apparatus watches.
    """
    declared = DeclaredFacts(
        issuer_scope=_fact(_ES),
        customer_scope=_fact(IvaTerritorialScope.THIRD_COUNTRY),
        stated_category=_fact(IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED),
    )
    assembly = assemble_classification_criteria(
        transaction_date=_WHEN,
        direction=InvoiceKind.ISSUED,
        inputs=collect_classifier_inputs(InvoiceDraft(), profile=None),
        declared=declared,
    )
    resolution = resolve_ingestion_iva_category(
        assembly,
        declared=declared,
        counterparty_country_status=record_country_code_status("USA"),
        direction=InvoiceKind.ISSUED,
    )

    assert resolution.outcome is IvaCategoryOutcome.DECLARED
    assert resolution.category is IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED


def _counterparty_only_relief(
    *,
    country_code: str | None,
    direction: InvoiceKind = InvoiceKind.ISSUED,
):
    """Resolve a declared export where ONLY the counterparty's slot is outstanding.

    **The first fixture on this path that settles the filer.** Every other one
    leaves both residencies unsupplied, which is the ordinary shape of a
    domestic invoice printing no country -- and it is why a spelling
    independence assertion had no home: with the filer's slot outstanding too,
    the scoped exemption forgives one slot and the other still refuses, so every
    spelling reaches the same refusal and an assertion over them holds WITHOUT
    THE EXEMPTION EVER FIRING.

    Settling the filer is what makes the exemption the only thing left deciding
    the outcome. It should be useful past this one assertion: any question about
    what the catalogue-gap carve-out does, rather than about what the filer's
    unfinished profile does, needs exactly this shape.

    The filer is the ISSUER on an issued invoice, so the issuer's scope is
    supplied and the customer's is not -- the party whose country the record
    states and our catalogue may fail to place.
    """
    declared = DeclaredFacts(
        issuer_scope=_fact(_ES),
        customer_tax_status=_fact(CustomerTaxStatus.B2B_IVA_REGISTERED),
        supply_nature=_fact(SupplyNature.GOODS),
        stated_category=_fact(IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED),
    )
    assembly = assemble_classification_criteria(
        transaction_date=_WHEN,
        direction=direction,
        inputs=collect_classifier_inputs(InvoiceDraft(), profile=None),
        declared=declared,
    )
    return resolve_ingestion_iva_category(
        assembly,
        declared=declared,
        direction=direction,
        counterparty_country_status=record_country_code_status(country_code),
    )


def test_the_counterparty_only_fixture_actually_fires_the_exemption() -> None:
    """The non-vacuity proof the spelling assertion below rests on.

    Without this, the assertion beneath could hold because every spelling
    refuses for the filer's sake, which is the vacuous shape this fixture was
    built to escape. Two things must be true of the fixture: the exemption must
    SPARE an uncatalogued counterparty, and it must still REFUSE where the
    catalogue places the country, so the sparing is the carve-out doing work
    rather than the guard being inert.
    """
    spared = _counterparty_only_relief(country_code=an_uncatalogued_alpha2())
    refused = _counterparty_only_relief(country_code="US")

    assert spared.outcome is IvaCategoryOutcome.DECLARED, (
        "the counterparty-only fixture must let the catalogue-gap exemption fire, "
        "or every assertion resting on it passes for the filer's reason instead"
    )
    assert refused.outcome is IvaCategoryOutcome.UNSUPPORTED_RELIEF, (
        "a country the catalogue places must still refuse here, or the fixture spares "
        "everything and proves nothing about the carve-out"
    )


def test_the_catalogue_gap_is_forgiven_whichever_spelling_the_record_states() -> None:
    """A Spanish structured record states its country as alpha-3.

    The exemption's warrant is that OUR catalogue failed to place the party, and
    that is a fact about the country rather than about the code system it was
    written in. If the alpha-3 spelling of an uncatalogued country refused where
    its alpha-2 spelling is spared, the carve-out would depend on which format
    the issuing system happens to emit -- and Facturae, the Spanish national
    format, emits the one that would lose.
    """
    alpha2 = _counterparty_only_relief(country_code=an_uncatalogued_alpha2())
    alpha3 = _counterparty_only_relief(country_code=an_uncatalogued_alpha3())

    assert alpha2.outcome is IvaCategoryOutcome.DECLARED
    assert alpha3.outcome is alpha2.outcome, (
        "the same catalogue gap reached a different outcome under a different spelling, "
        "so the carve-out depends on the code system rather than on our data"
    )
