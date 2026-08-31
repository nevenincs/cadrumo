"""Assemble the criteria the IVA rule table consumes, or refuse and say what is missing.

The rule table in :mod:`domain.iva` has always been complete and has never been
reachable: its criteria record was constructed nowhere in production — only in
its own docstring example and in tests — so no real document ever met it. This
module is the missing producer.

**It refuses far more often than it answers, and that is the deliverable.** An
unreachable classifier replaced by one that answers on incomplete evidence
would be a worse product, not a better one: the gap stops being visible and
starts being a number on a filing. So every input the table needs is either
established or named as missing, and a refusal lists exactly which authority
would settle it.

Two of those authorities are absent by design rather than by omission:

**Registration status needs VIES.** A printed IVA identifier establishes that
someone is acting as a taxable person, not that their number is registered and
valid — and the registered status is what triggers the intra-community supply
exemption. Inferring it from a printed number would zero-rate a taxable sale on
evidence nobody verified.

That refusal is real, and it is also **lazy**: it is only raised where the
answer could change the verdict. The domestic rule consults the customer's
status ONLY to route the three reverse-charge kinds and the exempt immovable
supply, none of which a printed goods-or-services reading can produce — so on an
ordinary domestic invoice every status reaches the identical category, and
demanding one asked the operator a question with no consequence on the commonest
document there is. The same table that judges the supply nature judges this,
by the same means and under the same fail-toward-asking rule.

**Spanish territorial scope needs sub-national evidence.** A country code names
the State while the IVA territory inside it stays undetermined, and Spain holds
three that the law treats differently. The printed postal code is that
sub-national evidence — its first two digits are the province — so a Spanish
party is now resolved from the country and postal codes together.

Two limits on that join, both deliberate. It is gated on Spain having been
NAMED, never on the country resolver merely returning nothing, because
five-digit postal codes are not unique to Spain. And an absent or unreadable
postal code refuses rather than resolving to the mainland: the peninsula is the
majority population, so that default would be invisible in testing while placing
Canarian and Ceutan parties inside a territory their operations are not subject
to.

**What still does not resolve is an ordinary domestic invoice**, and the reason
is upstream of this module. Establishment evidence reaches it as a printed
country code, and a domestic Spanish invoice frequently prints no country at all
while its bare tax identifier carries no country prefix. A valid Spanish tax
identifier cannot stand in for one: the non-resident CIF leader, the K/L/M
identifiers issued to Spaniards abroad and to non-residents, and the NIE series
all belong to parties who are not established in Spain — and establishment for
IVA is the sede de actividad, not tax registration. So that population refuses
here, correctly, until the evidence question is settled.

**A party's IVA identification is a THIRD thing, asked separately and demanded
rarely.** Where a party is established and which Member State identifies it are
two facts (:class:`~domain.iva.PartyFact`), and this module resolves them from
different evidence on purpose: the identification from the party's own printed
IVA number, which settles it decisively because registration is precisely what
it asserts; the establishment from the country and postal evidence, which no
registration can supply on either side. The identification is then demanded only
where the branch the operation reaches declares it consumed — the
intra-community families, whose treatment is reported against a NIF-IVA — so the
foreign goods population resolves with no operator question while a domestic
invoice is never asked for a number its treatment does not turn on.

Both are settleable by an explicit operator assertion, which is the sanctioned
path until those authorities exist. An assertion is the operator's claim, made
knowingly; a default would be ours, made silently.

See Also:
    :func:`~domain.iva.classify_iva`
        The single rule table. This module produces its input and never
        duplicates its decisions.
    :class:`~application.ledger.classifier_inputs.ClassifierInputs`
        The evidence-and-profile facts this assembly draws on.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, NamedTuple

from pydantic import BaseModel, Field

from ...core.classifier_input_source import ClassifierInputSource, CounterpartyTaxablePersonStatus
from ...core.iva_category_resolution import IvaCategoryOutcome
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.iva.classification import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    PartyFact,
    TransactionKind,
    classify_iva,
    domestic_categories_by_rate_kind,
    domestic_rate_tier_is_required,
    rate_kind_for_domestic_category,
)
from ...domain.iva.establishment import (
    SPAIN_COUNTRY_CODE,
    StatedCountryCodeStatus,
    stated_country_code_status,
    territorial_scope_for_country,
    territorial_scope_for_spanish_postal_code,
)
from ...domain.iva.identification import identification_state_for_printed_tax_identifier
from ...domain.iva.schema import EUMemberState, IvaCategory, IvaRateKind
from ...domain.iva.supply_nature import SupplyNature

if TYPE_CHECKING:
    from datetime import date

    from ...domain.iva.classification import IvaClassificationResult
    from .classifier_inputs import ClassifierInputs

__all__ = [
    "ClassificationAssembly",
    "DeclaredFact",
    "DeclaredFacts",
    "IvaCategoryResolution",
    "MissingClassifierInput",
    "assemble_classification_criteria",
    "classify_from_assembled_criteria",
    "declared_category_from_document_record",
    "resolve_ingestion_iva_category",
]


#: What a printed supply nature contributes to the table's kind axis.
#:
#: Only the general services member is reachable from printed evidence. The
#: specialised kinds — land-related, passenger transport, the reverse-charge
#: sub-kinds — each carry legal consequences a bare goods/services reading does
#: not establish, so none of them is inferred here. A document that needs one
#: gets it from an operator assertion, never from this map.
_NATURE_TO_KIND: dict[SupplyNature, TransactionKind] = {
    SupplyNature.GOODS: TransactionKind.GOODS,
    SupplyNature.SERVICES: TransactionKind.SERVICES_GENERAL,
}


class MissingClassifierInput(BaseModel):
    """One input the table needs that the evidence did not establish.

    Attributes:
        field: The criteria field that could not be filled.
        reason: What was tried and why it did not settle the question.
        settled_by: The authority or assertion that would settle it. Never
            empty — a refusal an operator cannot act on is a dead end.
    """

    model_config = STRICT_FROZEN_CONFIG

    field: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    settled_by: str = Field(min_length=1)


class ClassificationAssembly(BaseModel):
    """Either the assembled criteria, or every input that stopped it.

    Attributes:
        criteria: The record the rule table consumes, when every input was
            established. ``None`` otherwise.
        missing: What stopped it. Empty exactly when ``criteria`` is present.
    """

    model_config = STRICT_FROZEN_CONFIG

    criteria: IvaInvoiceClassificationCriteria | None = None
    missing: tuple[MissingClassifierInput, ...] = ()

    @property
    def assembled(self) -> bool:
        """Return whether the criteria were fully established."""
        return self.criteria is not None


class _InitialClassificationState(NamedTuple):
    missing: tuple[MissingClassifierInput, ...]
    supply_nature: SupplyNature | None
    status: CustomerTaxStatus | None
    issuer_scope: IvaTerritorialScope | None
    customer_scope: IvaTerritorialScope | None
    issuer_state: EUMemberState | None
    customer_state: EUMemberState | None


#: Every status the customer could actually turn out to have.
#:
#: The probe ranges over the WHOLE enum rather than a curated subset, because a
#: subset would be a second judgement about which statuses are plausible — and
#: the point of the probe is to decide indifference without judging the customer
#: at all. Deriving it from the enum also means a new member joins the sweep on
#: the day it is declared instead of the day someone remembers this list.
_STATUS_CANDIDATES: tuple[CustomerTaxStatus, ...] = tuple(CustomerTaxStatus)


#: The status supplied on a branch whose treatment cannot turn on it.
#:
#: ``UNKNOWN`` and not a substantive member, and this is the safety asymmetry
#: rather than a naming preference. Every status predicate in the rule table
#: tests for a substantive member, so ``UNKNOWN`` satisfies none of them and
#: cannot trigger a rule on evidence nobody supplied — where a substantive
#: placeholder would rest entirely on the probe having been right. It is also
#: simply true: the enum documents this member as "counterparty status
#: unresolved", which is exactly what happened.
_UNDETERMINED_STATUS: CustomerTaxStatus = CustomerTaxStatus.UNKNOWN


def _customer_tax_status_gap(inputs: ClassifierInputs) -> MissingClassifierInput:
    """Say why the evidence could not settle the customer's IVA status.

    The printed identifier is deliberately NOT consulted as a source of the
    registered status. It establishes a taxable person; ``B2B_IVA_REGISTERED``
    asserts a *valid* registration and is the trigger for the intra-community
    supply exemption, so bridging the two would let an unverified number
    zero-rate a taxable sale.
    """
    established = inputs.counterparty_taxable_person
    reason = (
        "the document printed a counterparty tax identifier, which establishes a taxable person "
        "but not a valid registration"
        if established is CounterpartyTaxablePersonStatus.TAXABLE_PERSON
        else "the document printed no counterparty tax identifier, so nothing was established"
    )
    return MissingClassifierInput(
        field="customer_tax_status",
        reason=reason,
        settled_by="a VIES verification, or an explicit operator assertion of the customer's IVA status",
    )


def names_spain(country_code: str | None) -> bool:
    """Whether the printed country evidence POSITIVELY names Spain.

    Asked instead of reading the country resolver's ``None`` as "Spanish",
    because that return collapses three different situations: an absent code, a
    code too malformed to be one, and Spain. Measured against the live resolver,
    every one of ``None``, ``''``, ``'ESP'``, ``'E1'`` and ``'ES'`` yields
    ``None``, so a caller branching on it cannot tell "the operator must supply a
    country" from "the operator must supply a postal code".

    That distinction is load-bearing here rather than cosmetic: a postal code is
    consulted only when Spain was named, so reading absence as Spain would feed
    a foreign five-digit code to the Spanish province lookup.

    Compares against the shipped ``SPAIN_COUNTRY_CODE`` after the same trim and
    case fold the resolver applies, and deliberately re-derives no shape check —
    only ``ES`` can equal the constant, so the well-formedness question never
    arises and there is no second copy of it to drift.
    """
    return (country_code or "").strip().upper() == SPAIN_COUNTRY_CODE


def _unresolved_country_reason(country_code: str | None) -> str:
    """Say why a stated country code established nothing, in the operator's terms.

    Three outcomes, and they need different things done to them. A code in an
    ISO user-assigned range names no country by construction, so the document is
    wrong and the operator corrects it. A well-formed code the bundled
    vocabulary does not carry may name a real jurisdiction, so the gap is ours
    and re-reading the document settles nothing. Anything that is not a
    two-letter code at all is a reading failure.

    Which one applies is asked of
    :func:`~domain.iva.stated_country_code_status` rather than re-derived, so
    the boundary that narrowed the rung and the sentence explaining the refusal
    cannot drift apart.
    """
    status = stated_country_code_status(country_code)
    if status is StatedCountryCodeStatus.UNASSIGNED:
        return (
            f"the printed country code {country_code!r} is reserved by ISO 3166-1 to name no country, "
            "so it established nothing about where this party is"
        )
    if status is StatedCountryCodeStatus.UNCATALOGUED:
        return (
            f"the printed country code {country_code!r} is not carried by this system's country "
            "vocabulary, so nothing can yet be said about where this party is established"
        )
    return (
        f"the printed country code {country_code!r} is not a well-formed two-letter country code, "
        "so it established nothing about where this party is"
    )


def _scope(
    country_code: str | None,
    postal_code: str | None,
    *,
    field: str,
    asserted: IvaTerritorialScope | None,
) -> tuple[IvaTerritorialScope | None, MissingClassifierInput | None]:
    """Resolve one party's territorial scope from its printed establishment evidence.

    Two halves, asked in order. The country code answers for a foreign party and
    stops at the border for a Spanish one, because Spain holds three IVA
    territories the law treats differently and a country code cannot separate
    them. The postal code answers the sub-national half: its first two digits are
    the province.

    **The postal half is gated on Spain having been NAMED**, never on the country
    half merely having returned nothing. Five-digit postal codes are not unique to
    Spain, so consulting the Spanish province lookup without country evidence
    would read a French or German code as a Spanish province — the restrictive
    default one level below the country axis that already refuses it.

    **An unreadable postal code refuses rather than resolving to the mainland.**
    The peninsula is the majority population, so that default would be invisible
    in testing while placing Canarian and Ceutan parties inside a territory their
    operations are not subject to. The resolver already refuses it; the refusal is
    repeated here because a caller is free to substitute its own default for the
    resolver's ``None``, and this is the caller.
    """
    if asserted is not None:
        return asserted, None
    resolved = territorial_scope_for_country(country_code)
    if resolved is not None:
        return resolved, None

    if names_spain(country_code):
        territory = territorial_scope_for_spanish_postal_code(postal_code)
        if territory is not None:
            return territory, None
        reason = (
            "the printed country code names Spain, whose three IVA territories are treated "
            "differently by law, and no readable postal code established which one"
        )
        settled_by = "a printed postal code for this party, or an explicit operator assertion of the territory"
    elif (country_code or "").strip():
        # Two different failures reach here and the operator's next move differs
        # between them, so the reason must not flatten them. A code the closed
        # vocabulary does not carry IS well-formed -- saying it is malformed
        # would send the operator to re-read a field that reads perfectly. The
        # status axis owns the distinction; nothing about it is re-derived here.
        reason = _unresolved_country_reason(country_code)
        settled_by = "a printed two-letter country code for this party, or an explicit operator assertion"
    else:
        reason = "no country code was established for this party"
        settled_by = "a printed country code for this party, or an explicit operator assertion of the territory"

    return None, MissingClassifierInput(field=field, reason=reason, settled_by=settled_by)


def _identification_state(
    printed_identifier: str | None,
    *,
    asserted: EUMemberState | None,
) -> EUMemberState | None:
    """Resolve which Member State IVA-identifies a party, from registration evidence.

    **The printed IVA number is decisive here and is not corroborated**, which
    inverts how the same evidence is treated one axis over. The identification
    state asks which State registered the party, and a number the party printed
    under that State's own VIES structure is exactly that answer — there is no
    further inference between the evidence and the fact for a second rung to
    confirm. The establishment axis refuses the identical evidence for the
    opposite reason: there the inference is the whole distance, and every Member
    State registers non-residents on the same terms Spain does.

    **The printed address country is deliberately NOT consulted.** It was, and
    that was the conflation reappearing on the axis that names it: an address is
    a statement about where a party IS, and reading a registration off it
    manufactured a German identification from a German address for a party that
    might be identified anywhere. A party's own printed number, or an explicit
    assertion, are the two things that can settle this.

    Returns:
        The Member State, or ``None`` when nothing established it. ``None`` is
        not a refusal: whether it must be settled is the consuming branch's
        question, asked in :func:`assemble_classification_criteria` against the
        table's own declaration.
    """
    if asserted is not None:
        return asserted
    return identification_state_for_printed_tax_identifier(printed_identifier)


def _counterparty_identification_field(direction: InvoiceKind) -> str:
    """Return whose identification a reporting branch actually needs settling.

    **The counterparty's, and never the filer's.** The declaración recapitulativa
    reports the OTHER party's NIF-IVA against the operation; the filer's own
    registration is a profile and censo fact, system-authoritative and declared
    once, exactly as its own establishment is. Demanding both would put a
    per-document question on a fact the profile already carries — the shape the
    territorial ruling rejected one axis over — and it would fall on the
    commonest intra-community document there is.

    Which role the counterparty occupies is the direction: on an issued invoice
    the filer is the issuer, on a received one the customer.
    """
    return "customer_identification_state" if direction is InvoiceKind.ISSUED else "issuer_identification_state"


def _counterparty_residency_field(direction: InvoiceKind) -> str:
    """Return which residency slot the COUNTERPARTY occupies, for this direction.

    The establishment counterpart of :func:`_counterparty_identification_field`,
    and it resolves the same way: on an issued invoice the filer is the issuer,
    so the counterparty is the customer; on a received one the filer is the
    customer, so the counterparty is the issuer.

    Separate from its sibling rather than one shared mapping because the two
    axes name different criteria fields, and a caller that needed the residency
    while holding the identification name would have to translate.
    """
    return "customer_residency" if direction is InvoiceKind.ISSUED else "issuer_residency"


def _state_for_field(
    field: str,
    *,
    issuer: EUMemberState | None,
    customer: EUMemberState | None,
) -> EUMemberState | None:
    """Return whichever party's identification the named criteria field carries."""
    return issuer if field == "issuer_identification_state" else customer


def _identification_gap(field: str) -> MissingClassifierInput:
    """Say why the evidence could not settle a party's IVA identification state."""
    return MissingClassifierInput(
        field=field,
        reason=(
            "this operation's treatment is reported against the party's NIF-IVA, and no printed "
            "IVA number established which Member State identifies it"
        ),
        settled_by=(
            "a printed intra-community IVA number for this party, or an explicit operator assertion "
            "of the Member State that identifies it"
        ),
    )


#: The kind supplied on a branch the law does not fork on, where the document
#: established no nature.
#:
#: Not a guess about the document, and it is only sound because the branch was
#: checked rather than assumed: the domestic rule consults ``kind`` ONLY to
#: exclude the three reverse-charge kinds, and neither value this module can
#: produce is in that set. So both reachable kinds yield the identical category,
#: which is then picked from the rate tier. A test proves that indifference by
#: classifying the same operation under both, rather than trusting this note.
_NATURE_INDIFFERENT_KIND: TransactionKind = TransactionKind.GOODS


def _axis_forks_the_law(
    probe: Callable[[CustomerTaxStatus, TransactionKind], IvaCategory],
    *,
    slices: list[tuple[tuple[CustomerTaxStatus, ...], tuple[TransactionKind, ...]]],
) -> bool:
    """Whether ONE undetermined axis can change THIS operation's treatment.

    Asks the rule table about itself: classify the same operation under each
    value the axis could take and compare the verdicts. Identical verdicts mean
    the answer could not have mattered, so demanding it would ask the operator a
    question with no consequence — which is what put a blocking gap on every
    domestic invoice, first for the supply nature and then for the customer's
    status.

    Each entry in ``slices`` holds the OTHER undetermined axes fixed and ranges
    over the axis under test. Judging one axis at a time is what makes the
    verdict attributable: a single sweep over the product would fork whenever
    *anything* mattered, and would then demand an answer the law does not turn
    on because a different axis did.

    **This is not a second copy of the laziness rule.** A hand-written branch on
    the territorial scopes would have been exactly that, and would have drifted
    the moment the categories moved. The domain's ``supply_nature_is_required``
    remains the authority; it keys on an established CATEGORY and returns
    ``True`` for ``None``, so it cannot be consulted at assembly time, where the
    criteria that produce the category are still being built. Rather than invent
    a second key, this derives the answer from the one authority that can be
    consulted before a category exists: the table itself. A gate asserts the two
    agree on every category this probe can reach, so a change to either is
    caught rather than silently forked.

    Fails toward asking, on both shapes of not-knowing:

    * A probe that cannot classify at all forks, because an operation that could
      not be placed may still land on a branch needing the answer.
    * **A verdict of** :attr:`~domain.iva.IvaCategory.UNKNOWN` **forks**, because
      that is the table's no-rule-matched sentinel rather than a treatment.
      Without this, an operation no rule places would agree with itself across
      every candidate and be certified indifferent on the strength of that
      agreement — identical-because-unplaced read as identical-because-it-cannot-
      matter. A measured EU-to-EU pair does exactly that: all five statuses reach
      the fallthrough, which says nothing whatever about the status mattering.
    """
    for statuses, kinds in slices:
        try:
            verdicts = {probe(status, kind) for status in statuses for kind in kinds}
        except Exception:  # reason: an unclassifiable probe is not evidence of indifference.
            return True
        if len(verdicts) > 1 or IvaCategory.UNKNOWN in verdicts:
            return True
    return False


def _facts_consumed(
    probe: Callable[[CustomerTaxStatus, TransactionKind], frozenset[PartyFact]],
    *,
    status_candidates: tuple[CustomerTaxStatus, ...],
    kind_candidates: tuple[TransactionKind, ...],
) -> frozenset[PartyFact]:
    """Which party facts any branch this operation could reach actually turns on.

    The same extension of the same idea as :func:`_axis_forks_the_law`, and
    deliberately routed through the same authority rather than beside it: which
    branches need a party's IVA identification is a fact about the law, so it is
    ASKED of the rule table instead of restated here as a branch on the
    territorial scopes. A hand-written "EU parties need a Member State" was
    exactly that restatement, and it was wrong in a specific way — it made an
    establishment demand an identification, which is the conflation the split
    exists to end.

    The two probes differ only in what they read off the same verdict. That one
    reads the CATEGORY, because indifference is a claim about outcomes; this one
    reads the branch's own declaration, because a value can be operative
    downstream (a NIF-IVA reported on the declaración recapitulativa) without
    changing the category at all — an indifference probe would certify it
    unnecessary and drop it silently.

    Fails toward asking on both shapes of not-knowing, matching its sibling:

    * A probe that cannot classify demands everything, because an operation that
      could not be placed may still land on a branch needing the answer.
    * An unplaced operation demands everything too, and that is enforced at the
      table: the fallthrough sentinel declares both facts consumed. Without it
      an operation no rule places would report a uniform, undemanding set and be
      certified as needing nothing on the strength of nothing having been
      decided — identical-because-unplaced read as identical-because-indifferent,
      the same misreading the category probe guards against.

    Args:
        probe: Classifies this operation under candidate axis values and returns
            the matched branch's declaration.
        status_candidates: What the customer's status could still be.
        kind_candidates: What the supply kind could still be.

    Returns:
        The union over every reachable branch. A union rather than an
        intersection: an operation that might land on a reporting branch must be
        asked, and only an operation that could reach NO such branch is spared.
    """
    consumed: set[PartyFact] = set()
    for status in status_candidates:
        for kind in kind_candidates:
            try:
                consumed |= probe(status, kind)
            except Exception:  # reason: an unclassifiable probe establishes no branch's needs.
                all_party_facts: frozenset[PartyFact] = frozenset(member for member in PartyFact)
                return all_party_facts
    result: frozenset[PartyFact] = frozenset(consumed)
    return result


class DeclaredFact[T](BaseModel):
    """One fact supplied to the criteria, beside who established it.

    The value and its attribution travel together because they are one claim.
    Passing the value alone -- which the flat ``asserted_*`` parameters this
    replaces did -- loses WHO said it at the boundary, and the provenance stamp
    then has to guess or stay silent about a fact the classification stood on.

    Attributes:
        value: The fact itself, in its own closed type.
        source: Who established it. Reuses the shipped
            :class:`~core.ClassifierInputSource` rather than declaring a second
            source vocabulary: the audit envelope already speaks it, so one
            spelling flows from this channel through
            :class:`~application.ledger.classifier_inputs.ClassifierInputFact` to the stamp. A
            private enum here would have been a second authority on the one
            question "who says so".
    """

    model_config = STRICT_FROZEN_CONFIG

    value: T
    source: ClassifierInputSource


class DeclaredFacts(BaseModel):
    """Every fact supplied into one classification, whoever established it.

    **Extended by adding a FIELD, never a second route.** This is the whole
    reason it is a model rather than more keyword parameters: a later stage with
    a new fact to contribute adds an attribute here and the assembly, the
    envelope and the stamp carry it without a new channel. A second supply route
    would fork the attribution the same way the four flat parameters forked it,
    and the fork is invisible until an auditor asks who said what.

    Every field is optional. An absent fact is not a supplied ``None``: it means
    nobody established it, which is exactly what the assembly reports as a
    missing input rather than papering over.

    Attributes:
        supply_nature: What the operation supplies, where established.
        customer_tax_status: The customer's IVA status -- the sanctioned way to
            supply what a VIES consultation would otherwise settle.
        issuer_scope: Where the issuer is ESTABLISHED, where a country code
            cannot settle it. Never supplies the identification state: they are
            two facts (:class:`~domain.iva.PartyFact`), and an operator
            asserting where a party operates from has not thereby said which
            State registered it.
        customer_scope: The customer's establishment, on the same terms.
        issuer_identification_state: Which Member State IVA-identifies the
            issuer, where no IVA number was printed to establish it. Never
            supplies the establishment, symmetrically.
        customer_identification_state: The same for the customer.
        stated_category: The IVA treatment the document's own machine-readable
            record declares. Supplied as a FACT rather than used as a category
            in its own right: it is evidence about the operation on the same
            footing as the country codes beside it, and
            :func:`resolve_ingestion_iva_category` is the one place it is
            weighed against what the rule table reaches.
    """

    model_config = STRICT_FROZEN_CONFIG

    supply_nature: DeclaredFact[SupplyNature] | None = None
    customer_tax_status: DeclaredFact[CustomerTaxStatus] | None = None
    issuer_scope: DeclaredFact[IvaTerritorialScope] | None = None
    customer_scope: DeclaredFact[IvaTerritorialScope] | None = None
    issuer_identification_state: DeclaredFact[EUMemberState] | None = None
    customer_identification_state: DeclaredFact[EUMemberState] | None = None
    stated_category: DeclaredFact[IvaCategory] | None = None


def _value_of[T](fact: DeclaredFact[T] | None) -> T | None:
    """Return a declared fact's value, or ``None`` when nobody declared it."""
    return None if fact is None else fact.value


def _scope_or_recorded_gap(
    missing: list[MissingClassifierInput],
    country_code: str | None,
    postal_code: str | None,
    *,
    field: str,
    asserted: IvaTerritorialScope | None,
) -> IvaTerritorialScope | None:
    """Resolve one party's scope, recording rather than raising what stopped it.

    Asked of each party independently and accumulated into one list, so an
    operator missing both parties' evidence learns both at once.
    """
    scope, gap = _scope(country_code, postal_code, field=field, asserted=asserted)
    if gap is not None:
        missing.append(gap)
    return scope


def _gaps_reportable_before_placement(
    status: CustomerTaxStatus | None,
    supply_nature: SupplyNature | None,
    inputs: ClassifierInputs,
) -> list[MissingClassifierInput]:
    """Name the axes an incompletely-placed operation can still be asked about.

    Reported without consulting the table, because the table cannot be asked
    before the scopes resolve. The wording says so: each gap states that the
    operation is too incompletely placed to tell whether its treatment turns on
    the answer, rather than asserting that it does.
    """
    gaps: list[MissingClassifierInput] = []
    if status is None:
        gaps.append(_customer_tax_status_gap(inputs))
    if supply_nature is None:
        gaps.append(
            MissingClassifierInput(
                field="kind",
                reason=(
                    "no statutory citation on the document established whether it supplies goods "
                    "or services, and this operation is too incompletely placed to tell whether "
                    "its treatment turns on the answer"
                ),
                settled_by=(
                    "a printed statutory citation, or an explicit operator assertion of the supply "
                    "nature; resolving the other gaps may also settle it"
                ),
            ),
        )
    return gaps


def _status_axis_gap(
    probe: Callable[[CustomerTaxStatus, TransactionKind], IvaCategory],
    *,
    status: CustomerTaxStatus | None,
    kind_candidates: tuple[TransactionKind, ...],
    inputs: ClassifierInputs,
) -> MissingClassifierInput | None:
    """Demand the customer's IVA status only where the table's verdict turns on it."""
    if status is not None:
        return None
    if not _axis_forks_the_law(probe, slices=[(_STATUS_CANDIDATES, (kind,)) for kind in kind_candidates]):
        return None
    return _customer_tax_status_gap(inputs)


def _supply_nature_axis_gap(
    probe: Callable[[CustomerTaxStatus, TransactionKind], IvaCategory],
    *,
    supply_nature: SupplyNature | None,
    status_candidates: tuple[CustomerTaxStatus, ...],
    kind_candidates: tuple[TransactionKind, ...],
) -> MissingClassifierInput | None:
    """Demand the supply nature only where the table's verdict turns on it."""
    if supply_nature is not None:
        return None
    if not _axis_forks_the_law(
        probe,
        slices=[((candidate,), kind_candidates) for candidate in status_candidates],
    ):
        return None
    return MissingClassifierInput(
        field="kind",
        reason=(
            "no statutory citation on the document established whether it supplies goods "
            "or services, and this operation's treatment differs between them"
        ),
        settled_by="a printed statutory citation, or an explicit operator assertion of the supply nature",
    )


def _identification_axis_gap(
    consumption_probe: Callable[[CustomerTaxStatus, TransactionKind], frozenset[PartyFact]],
    *,
    counterparty_field: str,
    counterparty_state: EUMemberState | None,
    status_candidates: tuple[CustomerTaxStatus, ...],
    kind_candidates: tuple[TransactionKind, ...],
) -> MissingClassifierInput | None:
    """Demand the counterparty's NIF-IVA only where a reachable branch consumes it."""
    if counterparty_state is not None:
        return None
    if PartyFact.IVA_IDENTIFICATION_STATE not in _facts_consumed(
        consumption_probe,
        status_candidates=status_candidates,
        kind_candidates=kind_candidates,
    ):
        return None
    return _identification_gap(counterparty_field)


def _unresolved_axis_gaps(
    criteria_for: Callable[[CustomerTaxStatus, TransactionKind], IvaInvoiceClassificationCriteria],
    *,
    status: CustomerTaxStatus | None,
    supply_nature: SupplyNature | None,
    counterparty_field: str,
    counterparty_state: EUMemberState | None,
    inputs: ClassifierInputs,
) -> list[MissingClassifierInput]:
    """Ask the rule table which still-undetermined axes could change THIS verdict.

    Each axis is asked lazily, in the order the assembler reports them: an axis
    the table treats identically across every value it could still take is not a
    gap, and demanding it would put a question to the operator that no branch
    this operation can reach would consult.
    """

    def _probe(status_candidate: CustomerTaxStatus, kind: TransactionKind) -> IvaCategory:
        return classify_iva(criteria_for(status_candidate, kind)).category

    def _consumption_probe(
        status_candidate: CustomerTaxStatus,
        kind: TransactionKind,
    ) -> frozenset[PartyFact]:
        return classify_iva(criteria_for(status_candidate, kind)).consumes_party_facts

    # What each axis could still be. An established axis contributes its one
    # value, so it holds genuinely fixed while the other is judged.
    status_candidates = (status,) if status is not None else _STATUS_CANDIDATES
    kind_candidates = (
        (_NATURE_TO_KIND[supply_nature],) if supply_nature is not None else tuple(_NATURE_TO_KIND.values())
    )
    gaps = (
        _status_axis_gap(_probe, status=status, kind_candidates=kind_candidates, inputs=inputs),
        _supply_nature_axis_gap(
            _probe,
            supply_nature=supply_nature,
            status_candidates=status_candidates,
            kind_candidates=kind_candidates,
        ),
        _identification_axis_gap(
            _consumption_probe,
            counterparty_field=counterparty_field,
            counterparty_state=counterparty_state,
            status_candidates=status_candidates,
            kind_candidates=kind_candidates,
        ),
    )
    return [gap for gap in gaps if gap is not None]


def _domestic_rate_tier_is_reachable(
    issuer_scope: IvaTerritorialScope | None,
    customer_scope: IvaTerritorialScope | None,
    supply_nature: SupplyNature | None,
    customer_tax_status: CustomerTaxStatus | None = None,
) -> bool:
    """Whether any branch this operation can still reach demands a rate tier.

    Lazy in the idiom the supply-nature demand already uses: asked only where
    the law forks on it. A cross-border operation wants a domestic tier only
    where the law brings it back here -- a B2C service under LIVA art. 69.Uno.2.º
    is realizada in the TAI and taxed at a Spanish rate -- and the four kinds
    routed to reverse charge before the domestic rule runs never want one.

    Union semantics over the still-open axes, matching the identification demand
    directly below: an operation that MIGHT land on a branch needing the tier is
    asked for it. The alternative would spare an operation whose kind or whose
    recipient condition is merely unread, and the tier would then surface as an
    unclassifiable probe reported against the wrong field.

    A scope that did not resolve returns False, because its own gap is already
    recorded and the demand cannot be decided without it.
    """
    if issuer_scope is None or customer_scope is None:
        return False
    kinds = (_NATURE_TO_KIND[supply_nature],) if supply_nature is not None else tuple(_NATURE_TO_KIND.values())
    return any(
        domestic_rate_tier_is_required(
            issuer_residency=issuer_scope,
            customer_residency=customer_scope,
            kind=kind,
            customer_tax_status=customer_tax_status,
        )
        for kind in kinds
    )


def _initial_classification_state(
    *,
    transaction_date: date | None,
    declared: DeclaredFacts,
    issuer_country_code: str | None,
    customer_country_code: str | None,
    issuer_postal_code: str | None,
    customer_postal_code: str | None,
    issuer_identifier: str | None,
    customer_identifier: str | None,
    rate_tier: IvaRateKind | None,
) -> _InitialClassificationState:
    missing: list[MissingClassifierInput] = []
    supply_nature = _value_of(declared.supply_nature)
    status = _value_of(declared.customer_tax_status)
    issuer_scope = _scope_or_recorded_gap(
        missing,
        issuer_country_code,
        issuer_postal_code,
        field="issuer_residency",
        asserted=_value_of(declared.issuer_scope),
    )
    customer_scope = _scope_or_recorded_gap(
        missing,
        customer_country_code,
        customer_postal_code,
        field="customer_residency",
        asserted=_value_of(declared.customer_scope),
    )

    issuer_state = _identification_state(
        issuer_identifier,
        asserted=_value_of(declared.issuer_identification_state),
    )
    customer_state = _identification_state(
        customer_identifier,
        asserted=_value_of(declared.customer_identification_state),
    )

    if transaction_date is None:
        missing.append(
            MissingClassifierInput(
                field="transaction_date",
                reason="no invoice date was established",
                settled_by="the printed invoice date, or an explicit operator assertion",
            ),
        )

    # An undetermined status is passed as an OPEN axis rather than as a value,
    # so the tier is demanded alongside it instead of one round-trip later.
    settled_status = None if status is _UNDETERMINED_STATUS else status
    if rate_tier is None and _domestic_rate_tier_is_reachable(
        issuer_scope,
        customer_scope,
        supply_nature,
        settled_status,
    ):
        missing.append(
            MissingClassifierInput(
                field="rate_tier",
                reason=(
                    "the operation is domestic and no IVA rate tier was read from the document, "
                    "so the classifier cannot tell which domestic category applies"
                ),
                settled_by="the rate printed on the invoice lines, or an explicit operator assertion",
            ),
        )

    return _InitialClassificationState(
        missing=tuple(missing),
        supply_nature=supply_nature,
        status=status,
        issuer_scope=issuer_scope,
        customer_scope=customer_scope,
        issuer_state=issuer_state,
        customer_state=customer_state,
    )


def assemble_classification_criteria(
    *,
    transaction_date: date | None,
    direction: InvoiceKind,
    inputs: ClassifierInputs,
    declared: DeclaredFacts,
    issuer_country_code: str | None = None,
    customer_country_code: str | None = None,
    issuer_postal_code: str | None = None,
    customer_postal_code: str | None = None,
    issuer_identifier: str | None = None,
    customer_identifier: str | None = None,
    rate_tier: IvaRateKind | None = None,
) -> ClassificationAssembly:
    """Assemble the rule table's criteria, or return every input that stopped it.

    Accumulates rather than short-circuits: an operator who has to resolve four
    missing inputs should learn all four at once rather than one per attempt.

    Args:
        transaction_date: When the supply took place.
        direction: Issued or received, as the operator settled it at confirm.
        inputs: The evidence-and-profile facts collected for this document.
        declared: The facts supplied into this classification, each carrying who
            established it. Replaces the flat ``asserted_*`` parameters, which
            could carry a value but not its attribution.
        issuer_country_code: The issuer's printed country code, if any.
        customer_country_code: The customer's printed country code, if any.
        issuer_postal_code: The issuer's printed postal code, if any. Consulted
            only when the country evidence names Spain, to separate the three
            Spanish IVA territories a country code cannot tell apart.
        customer_postal_code: The same for the customer. Asked of each party
            independently, because an issuer in Las Palmas invoicing a customer
            in Madrid crosses a territorial boundary one shared code could not
            express.
        issuer_identifier: The issuer's printed tax identifier, if any. Read
            for the IVA IDENTIFICATION state only — a separate axis from the
            postal and country evidence above, which answer where the party is.
        customer_identifier: The same for the customer.
        rate_tier: The rate tier, required by the criteria model for ES-to-ES
            domestic operations.

    Returns:
        :class:`ClassificationAssembly`: the criteria, or the missing inputs.
    """
    initial = _initial_classification_state(
        transaction_date=transaction_date,
        declared=declared,
        issuer_country_code=issuer_country_code,
        customer_country_code=customer_country_code,
        issuer_postal_code=issuer_postal_code,
        customer_postal_code=customer_postal_code,
        issuer_identifier=issuer_identifier,
        customer_identifier=customer_identifier,
        rate_tier=rate_tier,
    )
    missing = list(initial.missing)
    supply_nature = initial.supply_nature
    status = initial.status
    issuer_scope = initial.issuer_scope
    customer_scope = initial.customer_scope

    issuer_state = initial.issuer_state
    customer_state = initial.customer_state

    if missing:
        # The probe needs otherwise-complete criteria, and this operation does
        # not have them -- so neither lazy question can be decided here. Both are
        # still REPORTED, because failing toward asking is the rule and because
        # dropping them would cost the accumulate-at-once property: an operator
        # resolving the other gaps would re-run only to meet a new one.
        missing.extend(_gaps_reportable_before_placement(status, supply_nature, inputs))
        # The identification is deliberately NOT reported here, and it is the one
        # place this function does not accumulate. The status and the nature are
        # reported because the table can be asked about them the moment the
        # scopes resolve, so naming them early costs nothing. Whether an
        # identification is needed is decided by the BRANCH, and no branch is
        # known yet -- so reporting it would put a NIF-IVA question on every
        # domestic invoice that merely lacks a country code, which is the exact
        # noise the per-branch demand exists to remove. The cost is one extra
        # round for the intra-community population, whose paper carries the
        # printed number that settles it anyway.
        return ClassificationAssembly(missing=tuple(missing))

    assert issuer_scope is not None  # narrowed: a gap would have been recorded
    assert customer_scope is not None
    assert transaction_date is not None

    def _criteria_for(
        status_candidate: CustomerTaxStatus,
        kind: TransactionKind,
    ) -> IvaInvoiceClassificationCriteria:
        return IvaInvoiceClassificationCriteria(
            transaction_date=transaction_date,
            issuer_residency=issuer_scope,
            customer_residency=customer_scope,
            customer_tax_status=status_candidate,
            kind=kind,
            direction=direction,
            issuer_identification_state=issuer_state,
            customer_identification_state=customer_state,
            rate_tier=rate_tier,
        )

    counterparty_field = _counterparty_identification_field(direction)
    missing.extend(
        _unresolved_axis_gaps(
            _criteria_for,
            status=status,
            supply_nature=supply_nature,
            counterparty_field=counterparty_field,
            counterparty_state=_state_for_field(
                counterparty_field,
                issuer=issuer_state,
                customer=customer_state,
            ),
            inputs=inputs,
        ),
    )

    if missing:
        return ClassificationAssembly(missing=tuple(missing))

    return ClassificationAssembly(
        criteria=_criteria_for(
            status if status is not None else _UNDETERMINED_STATUS,
            _NATURE_TO_KIND[supply_nature] if supply_nature is not None else _NATURE_INDIFFERENT_KIND,
        ),
    )


def classify_from_assembled_criteria(
    assembly: ClassificationAssembly,
) -> IvaClassificationResult | None:
    """Run the single rule table over assembled criteria, or return ``None``.

    A thin call rather than a second decision surface. Every classification
    judgement stays in :func:`~domain.iva.classify_iva`; this module's whole
    contribution is deciding whether the table may be consulted at all.
    """
    from ...domain.iva.classification import classify_iva

    if assembly.criteria is None:
        return None
    return classify_iva(assembly.criteria)


def declared_category_from_document_record(
    printed_code: IvaCategory | str | None,
) -> DeclaredFact[IvaCategory] | None:
    """Read the IVA treatment a document's own machine-readable record declares.

    **The one place a category is built from a document token**, and it is here
    rather than beside the reader on purpose: interpreting what the operation's
    treatment is belongs to the classification authority, and a reader that
    minted the value itself was a second authority answering the same question
    from weaker evidence.

    The UNTDID 5305 tax-category code is a fact only a structured reader can
    recover: it is IN the document and no text or vision reader can supply it.
    Dropping it is not a missing label but a missing declaration. A domestic
    reverse charge, an exempt supply and a zero-rated supply all print a base
    and no cuota, so once the code is gone the record cannot be told apart from
    an ordinary zero-cuota supply -- and the self-assessed output IVA a reverse
    charge obliges, which Modelo 303 collects in its own inversión del sujeto
    pasivo tier, is never assessed at all.

    A standard-rated supply maps to the empty string rather than a member: the
    rate itself carries the meaning there and there is no special category to
    state, so it resolves to ``None`` exactly as an absent code does.

    An unrecognised token also resolves to ``None`` rather than raising. The
    parser only ever writes values from its own closed UNTDID mapping, so a
    token outside it means that mapping changed shape; refusing the whole
    confirm over a label the operator can supply themselves would block a
    filing the rest of the record fully supports.

    Args:
        printed_code: The tax-category token the document's record carried.

    Returns:
        The declaration beside its attribution, or ``None`` when the document
        states no special category.
    """
    stated = str(printed_code or "").strip()
    if not stated:
        return None
    try:
        category = IvaCategory(stated)
    except ValueError:
        return None
    return DeclaredFact(value=category, source=ClassifierInputSource.DOCUMENT_EVIDENCE)


class IvaCategoryResolution(BaseModel):
    """The category one confirmed document resolves to, and what established it.

    Attributes:
        outcome: Which of the five states applies.
        category: The resolved treatment. ``None`` on ``CONTRADICTED`` and
            ``UNRESOLVED`` alike -- on the same terms
            :class:`~domain.iva.LegendDerivation` withholds one, so a caller
            cannot hold the value while ignoring the conflict that produced it.
        classified: What the rule table reached from the operation's own facts,
            where it could place the operation at all. Carried beside the
            verdict rather than folded into it, so a contradiction can name both
            halves of what disagreed.
        declared: What the document's own record declared, where it did.
        note: Operator-facing explanation, populated on ``CONTRADICTED`` to say
            what disagreed with what.
    """

    model_config = STRICT_FROZEN_CONFIG

    outcome: IvaCategoryOutcome
    category: IvaCategory | None = None
    classified: IvaCategory | None = None
    declared: DeclaredFact[IvaCategory] | None = None
    note: str = ""


def _table_verdict(assembly: ClassificationAssembly) -> IvaCategory | None:
    """Return the category the rule table placed this operation in, if any.

    :attr:`~domain.iva.IvaCategory.UNKNOWN` is read as "not established" rather
    than as a treatment, matching how :func:`_axis_forks_the_law` reads it: it
    is the table's no-rule-matched sentinel, and carrying it forward as a
    verdict would make an unplaced operation indistinguishable from a placed
    one at every later reader.
    """
    result = classify_from_assembled_criteria(assembly)
    if result is None or result.category is IvaCategory.UNKNOWN:
        return None
    return result.category


def _rate_tier_contradiction(declared: IvaCategory, rate_tier: IvaRateKind | None) -> str:
    """Say how a declared domestic category disagrees with the tier charged, if it does.

    The corroboration the rate evidence now performs. It derives nothing: the
    tier already reached the rule table as a criteria axis, where rule ``R05``
    turns it into a domestic category through the one shipped mapping. Asking
    the inverse of that mapping here checks the document against ITSELF -- the
    treatment its record declares against the tier its lines charged -- which is
    a question the table cannot answer, because the declared code never enters
    the criteria.

    Silent on every non-domestic category. ``rate_kind_for_domestic_category``
    returns ``None`` for intra-community, export, import, reverse-charge and
    recargo treatments, and that is the honest answer rather than a mismatch:
    those categories carry no rate tier derivable from the category alone, so a
    tier beside one of them corroborates nothing either way.
    """
    expected_tier = rate_kind_for_domestic_category(declared)
    if expected_tier is None or rate_tier is None or expected_tier is rate_tier:
        return ""
    return (
        f"the document's record declares the IVA treatment {declared.value!r}, which is charged at the "
        f"{expected_tier.value!r} tier, but its lines charge the {rate_tier.value!r} tier"
    )


#: Declared categories whose whole legal basis is WHERE the counterparty is.
#:
#: Both relieve the supply of Spanish output IVA on an establishment premise and
#: on nothing else: LIVA art. 25 exempts an entrega intracomunitaria to an
#: acquirer in another Member State, and LIVA art. 21 zero-rates an export to a
#: party outside the Community. Honouring either without that establishment
#: declares a relieved supply for a party nobody could place.
#:
#: The set is narrow on purpose and every exclusion is a decision. The domestic
#: members presuppose Spanish establishment, which is what the tier corroboration
#: already checks. ``domestic_reverse_charge`` also carries no cuota, but it
#: OBLIGES the recipient to self-assess output IVA, so mis-honouring it
#: over-declares rather than under-declares and is not this hazard. Only the two
#: relieving categories are here, and only these two are reachable as a declared
#: code anyway -- the structured readers emit exactly one UNTDID token per
#: member (``K`` and ``G``).
_RELIEF_ON_AN_ESTABLISHMENT_PREMISE: frozenset[IvaCategory] = frozenset(
    {
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
    },
)


#: Criteria fields naming a party's territorial establishment.
_RESIDENCY_FIELDS: frozenset[str] = frozenset({"issuer_residency", "customer_residency"})


def _unsupported_relief_claim(
    declared: IvaCategory,
    assembly: ClassificationAssembly,
    *,
    counterparty_country_status: StatedCountryCodeStatus | None,
    direction: InvoiceKind | None,
) -> str:
    """Say why a declared relief cannot be honoured on this evidence, if it cannot.

    The gap the ``DECLARED`` branch leaves open on its own. When the rule table
    returns nothing the document's own code is taken at face value, and the tier
    corroboration is silent on every non-domestic category by construction --
    so a document asserting an export or an intra-community supply routed an
    unplaceable counterparty straight to a relieved category with nothing
    disagreeing anywhere.

    **Absence of establishment is not disproof of the claim**, so this is not
    read as a contradiction and the document is not called wrong. It is a claim
    the evidence does not reach, which is a different thing and takes a different
    remedy: the category is withheld and the establishment is named as the fact
    that would settle it.

    **The exemption forgives ONE slot, not the whole set.** It is scoped to the
    counterparty's own residency because that is the only gap it has a warrant
    for; a filer whose territory the profile never established is an unfinished
    setup, and the document under review cannot fix it. Unscoped, a
    counterparty our vocabulary happened to miss suppressed the refusal for the
    filer's gap too, so the relief was honoured with neither party established.
    That direction under-declares, and it was unreachable until the
    counterparty's stated token started reaching this function at all.

    **A country our own vocabulary does not carry is exempted, and that
    exemption is the difference between a guard and a trap.** The scope resolver
    answers from a closed vocabulary, so a well-formed code naming a real
    jurisdiction it does not list resolves to nothing, and such jurisdictions
    exist at any moment because the vocabulary is a bounded subset that grows.
    The establishment is then a gap in OUR data rather than in the document.
    Refusing there would reject a legitimate export because of a row we have not
    written, which is the false-positive direction
    that makes an operator stop reading refusals. Only an absent, malformed or
    ISO-unassigned code reaches the refusal, and each of those genuinely
    established nothing about where the party is.

    Args:
        declared: The treatment the document's record declares.
        assembly: The criteria, or the inputs that stopped them.
        counterparty_country_status: What the counterparty's printed country
            code turned out to be, or ``None`` when no code was printed.
        direction: Which side of the invoice the filer is on, which is what
            says WHICH residency slot the exemption may forgive. ``None``
            forgives nothing: a caller that cannot say which party is the
            counterparty cannot claim our vocabulary is what failed, and the
            safe answer for a relief claim is to withhold rather than to
            honour it.

    Returns:
        The operator-facing reason, or ``""`` when the claim stands.
    """
    if declared not in _RELIEF_ON_AN_ESTABLISHMENT_PREMISE:
        return ""
    outstanding = {gap.field for gap in assembly.missing} & _RESIDENCY_FIELDS
    if not outstanding:
        return ""
    if counterparty_country_status is StatedCountryCodeStatus.UNCATALOGUED and direction is not None:
        # Only the COUNTERPARTY's own slot is forgiven, and only when the
        # direction says which slot that is. The exemption's whole warrant is
        # that OUR vocabulary failed to place the other party; it says nothing
        # about the filer, whose territory is a profile fact this document
        # cannot supply and whose absence is an unfinished setup rather than a
        # gap in our data. Forgiving the whole set on the counterparty's excuse
        # honoured a zero-rated export claim while the filer's own establishment
        # was unknown -- a relief granted on evidence nobody had.
        outstanding -= {_counterparty_residency_field(direction)}
    if not outstanding:
        return ""
    unestablished = sorted(outstanding)
    return (
        f"the document's record declares the IVA treatment {declared.value!r}, which relieves the "
        f"supply of Spanish IVA only because of where the counterparty is established, and "
        f"{' and '.join(unestablished)} was not established by this document"
    )


def resolve_ingestion_iva_category(
    assembly: ClassificationAssembly,
    *,
    declared: DeclaredFacts,
    rate_tier: IvaRateKind | None = None,
    counterparty_country_status: StatedCountryCodeStatus | None = None,
    direction: InvoiceKind | None = None,
) -> IvaCategoryResolution:
    """Resolve the IVA category of one document being ingested.

    **The single production surface that decides an ingested record's IVA
    category.** Two rival deriving surfaces once sat on the confirm path ahead
    of the rule table and reached it never: one read the document's declared
    tax-category code, the other re-derived a domestic category from the rate.
    Both are still consulted and neither decides any more -- the code arrives as
    a declared FACT and the rate as the criteria's own ``rate_tier`` axis, which
    is what rule ``R05`` already consults through the mapping the rate surface
    used to copy.

    Six outcomes, and "probably" is not one, matching the legend axis this
    sits beside:

    * The table places the operation and the code agrees -- ``CORROBORATED``.
    * The table places it and the document declared no code -- ``CLASSIFIED``.
      A standard-rated supply states no special category because the rate is
      the meaning, so there is nothing to corroborate against.
    * The document declares a code the table could not reach -- ``DECLARED``.
      The reverse-charge, exempt and zero-rated population, whose treatments
      turn on facts a printed page does not carry.
    * They disagree, or the declared code disagrees with the tier charged --
      ``CONTRADICTED``, carrying no category. **Which half is wrong is not
      decided here.** A wrong category is worse than an absent one, because an
      absent category asks the operator and a wrong one does not; and the two
      halves lead to different declarations, so picking silently picks a filing.
    * The table refused, no code was declared, and the document charged a
      registered Spanish tier -- ``RATE_INFERRED``. **The weakest answer, and
      the one that keeps the commonest document declarable.** The table refuses
      whenever a party's territory is unestablished, which an ordinary domestic
      invoice printing no country routinely leaves so; without this branch those
      records reach the invoice decomposition contract undeclared and the renta
      income path contributes their bank cash instead of their ingresos
      íntegros. What carries it is the charged tax rather than a default --
      Canarias and Ceuta y Melilla levy IGIC and IPSI, not IVA. **The outcome
      names the inference but nothing yet shows it to an operator**: it is
      neither persisted nor emitted, so a record resting on it currently reads
      exactly like one the rule table placed.
    * Nothing established one -- ``UNRESOLVED``. An honest blank, never a
      restrictive provision applied as a default.

    Args:
        assembly: The criteria the rule table consumes, or the inputs that
            stopped them.
        declared: The facts supplied into this classification, whose
            ``stated_category`` carries the document's own declaration.
        rate_tier: The tier the document's lines charged, for corroboration.
            The SAME value handed to :func:`assemble_classification_criteria`,
            so the two cannot read the document differently.
        direction: Which side of the invoice the filer is on. Reaches the
            relief guard, where it says which residency slot the counterparty
            occupies and therefore which one the catalogue-gap exemption may
            forgive. Omitted, the exemption forgives nothing.
        counterparty_country_status: What the counterparty's printed country
            code turned out to be, or ``None`` when none was printed. Consulted
            only to spare a relief claim whose establishment failed on OUR
            vocabulary rather than on the document.

    Returns:
        :class:`IvaCategoryResolution`: the resolved treatment and what
        established it, or the conflict that stopped it.
    """
    classified = _table_verdict(assembly)
    stated_fact = declared.stated_category
    if stated_fact is None:
        if classified is not None:
            return IvaCategoryResolution(
                outcome=IvaCategoryOutcome.CLASSIFIED,
                category=classified,
                classified=classified,
            )
        inferred = domestic_categories_by_rate_kind().get(rate_tier) if rate_tier is not None else None
        if inferred is None:
            return IvaCategoryResolution(outcome=IvaCategoryOutcome.UNRESOLVED)
        return IvaCategoryResolution(outcome=IvaCategoryOutcome.RATE_INFERRED, category=inferred)

    stated = stated_fact.value
    # Asked BEFORE the tier check and before the verdict comparison, because it
    # is the only rung that fires when nothing disagrees. A relief claim on an
    # unestablished counterparty passes every other check by construction: the
    # tier corroboration is silent on non-domestic categories, and there is no
    # verdict to compare against precisely because the establishment is missing.
    unsupported = _unsupported_relief_claim(
        stated,
        assembly,
        counterparty_country_status=counterparty_country_status,
        direction=direction,
    )
    if unsupported:
        return IvaCategoryResolution(
            outcome=IvaCategoryOutcome.UNSUPPORTED_RELIEF,
            classified=classified,
            declared=stated_fact,
            note=(
                f"{unsupported}; the category is withheld rather than the document called wrong, "
                "because absent establishment does not disprove the claim"
            ),
        )
    tier_conflict = _rate_tier_contradiction(stated, rate_tier)
    if tier_conflict:
        return IvaCategoryResolution(
            outcome=IvaCategoryOutcome.CONTRADICTED,
            classified=classified,
            declared=stated_fact,
            note=(
                f"{tier_conflict}; the document disagrees with itself and the category cannot be taken from either side"
            ),
        )
    if classified is None:
        return IvaCategoryResolution(outcome=IvaCategoryOutcome.DECLARED, category=stated, declared=stated_fact)
    if classified is stated:
        return IvaCategoryResolution(
            outcome=IvaCategoryOutcome.CORROBORATED,
            category=stated,
            classified=classified,
            declared=stated_fact,
        )
    return IvaCategoryResolution(
        outcome=IvaCategoryOutcome.CONTRADICTED,
        classified=classified,
        declared=stated_fact,
        note=(
            f"the document's record declares the IVA treatment {stated.value!r}, but this operation's own "
            f"establishment, status and supply facts classify it as {classified.value!r}; the two cannot both "
            "be true and the category cannot be taken from either side"
        ),
    )
