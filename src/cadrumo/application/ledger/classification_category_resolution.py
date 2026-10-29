"""Resolve an ingested document's declared and classified IVA treatment."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from ...core.classifier_input_source import ClassifierInputSource
from ...core.iva_category_resolution import IvaCategoryOutcome
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.clock import today_madrid
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.iva_category_catalogue import registry_category_projection, require_iva_category
from ...domain.iva.classification import rate_kind_for_domestic_category, resolve_iva_classification_inputs
from ...domain.iva.establishment import StatedCountryCodeStatus
from ...domain.iva.schema import InvoiceKind, IvaCategory, IvaRateKind
from .classification_assembly import (
    ClassificationAssembly,
    DeclaredFact,
    DeclaredFacts,
    classify_from_assembled_criteria,
)


def _counterparty_residency_field(direction: InvoiceKind) -> str:
    """Return which residency slot the COUNTERPARTY occupies, for this direction.

    The establishment counterpart of :func:`counterparty_identification_field`,
    and it resolves the same way: on an issued invoice the filer is the issuer,
    so the counterparty is the customer; on a received one the filer is the
    customer, so the counterparty is the issuer.

    Separate from its sibling rather than one shared mapping because the two
    axes name different criteria fields, and a caller that needed the residency
    while holding the identification name would have to translate.
    """
    return "customer_residency" if direction is InvoiceKind.ISSUED else "issuer_residency"


def declared_category_from_document_record(
    printed_code: IvaCategory | str | None,
    *,
    operation: PinnedAuthorityOperation,
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
        operation: Caller-owned pinned authority operation used to validate and
            project the category token.

    Returns:
        The declaration beside its attribution, or ``None`` when the document
        states no special category.
    """
    stated = str(printed_code or "").strip()
    if not stated:
        return None
    try:
        category = require_iva_category(stated, authority=operation)
    except RegistryValidationError:
        return None
    return DeclaredFact(value=category, source=ClassifierInputSource.DOCUMENT_EVIDENCE)


class IvaCategoryResolution(BaseModel):
    """The category one confirmed document resolves to, and what established it.

    Attributes:
        outcome: Which of the five states applies.
        category: The resolved treatment. ``None`` on ``CONTRADICTED`` and
            ``UNRESOLVED`` alike -- on the same terms
            :class:`~domain.iva.legend_derivation.LegendDerivation` withholds one, so a caller
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


def _table_verdict(assembly: ClassificationAssembly, *, operation: PinnedAuthorityOperation) -> IvaCategory | None:
    """Return the category the rule table placed this operation in, if any.

    The registry-declared ``unknown`` category is read as "not established" rather
    than as a treatment, matching how :func:`axis_forks_the_law` reads it: it
    is the table's no-rule-matched sentinel, and carrying it forward as a
    verdict would make an unplaced operation indistinguishable from a placed
    one at every later reader.
    """
    result = classify_from_assembled_criteria(assembly, operation=operation)
    if result is None or result.category == require_iva_category("unknown", authority=operation):
        return None
    return result.category


def _rate_tier_contradiction(
    declared: IvaCategory,
    rate_tier: IvaRateKind | None,
    *,
    operation: PinnedAuthorityOperation,
    effective_date: date,
) -> str:
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
    projected = resolve_iva_classification_inputs(effective_date=effective_date, operation=operation)
    expected_tier = rate_kind_for_domestic_category(declared, mapping=projected.rate_categories)
    if expected_tier is None or rate_tier is None or expected_tier == rate_tier:
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
#: Criteria fields naming a party's territorial establishment.
_RESIDENCY_FIELDS: frozenset[str] = frozenset({"issuer_residency", "customer_residency"})


def _unsupported_relief_claim(
    declared: IvaCategory,
    assembly: ClassificationAssembly,
    *,
    counterparty_country_status: StatedCountryCodeStatus | None,
    direction: InvoiceKind | None,
    operation: PinnedAuthorityOperation,
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
        operation: Caller-owned pinned authority operation used for the relief
            category projection.

    Returns:
        The operator-facing reason, or ``""`` when the claim stands.
    """
    if declared not in registry_category_projection("relief_on_establishment_premise", authority=operation):
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


def _resolve_undeclared_ingestion_category(
    assembly: ClassificationAssembly,
    *,
    operation: PinnedAuthorityOperation,
    classified: IvaCategory | None,
    rate_tier: IvaRateKind | None,
) -> IvaCategoryResolution:
    """Resolve table-placed and charged-rate fallback outcomes without a declared fact."""
    if classified is not None:
        return IvaCategoryResolution(
            outcome=IvaCategoryOutcome.CLASSIFIED,
            category=classified,
            classified=classified,
        )
    projected = resolve_iva_classification_inputs(
        effective_date=(assembly.criteria.transaction_date if assembly.criteria is not None else today_madrid()),
        operation=operation,
    )
    inferred = projected.rate_categories.get(rate_tier) if rate_tier is not None else None
    if inferred is None:
        return IvaCategoryResolution(outcome=IvaCategoryOutcome.UNRESOLVED)
    return IvaCategoryResolution(outcome=IvaCategoryOutcome.RATE_INFERRED, category=inferred)


def resolve_ingestion_iva_category(
    assembly: ClassificationAssembly,
    *,
    operation: PinnedAuthorityOperation,
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
        operation: Caller-owned pinned authority operation retained through the
            table and category resolution.

    Returns:
        :class:`IvaCategoryResolution`: the resolved treatment and what
        established it, or the conflict that stopped it.
    """
    classified = _table_verdict(assembly, operation=operation)
    stated_fact = declared.stated_category
    if stated_fact is None:
        return _resolve_undeclared_ingestion_category(
            assembly,
            operation=operation,
            classified=classified,
            rate_tier=rate_tier,
        )

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
        operation=operation,
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
    tier_conflict = _rate_tier_contradiction(
        stated,
        rate_tier,
        operation=operation,
        effective_date=(assembly.criteria.transaction_date if assembly.criteria is not None else today_madrid()),
    )
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
    if classified == stated:
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
