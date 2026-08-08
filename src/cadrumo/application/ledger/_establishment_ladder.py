"""Ask the strongest available evidence where a counterparty is established, in order.

Four rungs, each already an authority in its own right, composed here into the
ordered ladder the classification criteria need. The composition is the whole
deliverable: every rung answers honestly on its own, and the DAMAGE comes from
consulting them in the wrong order.

**First decisive rung wins, and the order is not a preference.** Spain, France,
Germany and Italy all print five-digit postal codes, so a French ``75001`` handed
to the Spanish province lookup returns the peninsula and a ``51001`` returns
Ceuta -- placing a French party inside a Spanish territory, or outside LIVA
entirely. Neither is caught by a check further down, because both are perfectly
well-formed answers to the wrong question. What prevents it is that the country
rung is consulted first and, having answered, stops the ladder.

The rungs, strongest first:

1. **The printed tax identifier.** An intra-community VAT number leads with its
   Member State's prefix, which is a country stated in the one field a domestic
   invoice's address block often leaves out.
2. **The printed address country**, as a name matched against the bounded
   registry vocabulary or as an already-printed alpha-2 code.
3. **The Spanish postal code**, consulted ONLY where the country evidence
   positively named Spain. A postal pattern alone presupposes exactly what it
   would have to prove.
4. **A previously confirmed counterparty-level fact**, because establishment is
   a property of the entity and the operator should be asked at most once.

**Spain is a trigger, not an exhausted rung.** The country rung deliberately
returns no SCOPE for Spain -- ``ES`` names the Member State while the territory
inside it stays undetermined between the TAI, Canarias and Ceuta y Melilla -- so
the ladder reads the country CODE rather than the scope to decide whether the
postal rung applies. Treating that ``None`` as "no evidence" would skip the one
rung that can answer, and would do so for the majority population.

**An exhausted ladder yields nothing, and nothing never becomes a territory.**
There is no branch here that produces a scope from the absence of evidence. The
peninsula is the commonest answer, so a default there would pass every test
written from mainland fixtures while silently placing Canarian and Ceutan
parties inside a territory their operations are not subject to.

**A corrupt registry is not an unestablished party.** The country vocabulary and
the territory table REFUSE a malformed or fold-colliding table rather than
degrading, and that refusal travels out of here untouched. No rung is wrapped in
a bare ``except``: converting it to a quiet "not established" would send an
operator to confirm a counterparty's territory in answer to a broken bundled
data file, which is a defect with no operator remedy.

**The taxpayer's own side never enters this ladder.** One party on every ingested
invoice is the operator, whose territory is a profile fact resolved by
:func:`~application.ledger.resolve_filer_territorial_scope`. Only the
counterparty's scope is ever sought on the paper.

See Also:
    :func:`~application.ledger.resolve_counterparty_establishment`
        The fourth rung, and the store an operator's answer persists into.
    :class:`~application.ledger.DeclaredFacts`
        The one channel a resolved scope reaches the criteria assembly through.
    :class:`~domain.iva.IvaTerritorialScope`
        The closed target every rung resolves into.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG, ClassifierInputSource
from ...domain.iva import (
    IvaTerritorialScope,
    country_code_for_printed_country_name,
    territorial_scope_for_country,
    territorial_scope_for_printed_tax_identifier,
    territorial_scope_for_spanish_postal_code,
)

# `names_spain` is the sibling module's authority on what positively names
# Spain, and is imported rather than restated: a second copy of that test is
# exactly the drift that would let one surface open the postal rung while the
# other does not. The import direction also keeps the pair acyclic, since the
# declared-fact channel below is owned there too.
from ._classification_assembly import DeclaredFact, names_spain
from ._counterparty_establishment import (
    CounterpartyEstablishmentContradiction,
    CounterpartyEstablishmentRepository,
    resolve_counterparty_establishment,
)

if TYPE_CHECKING:
    from ...domain.iva import InvoiceKind
    from ._evidence_draft import InvoiceDraft

__all__ = [
    "CounterpartyEstablishment",
    "EstablishmentRung",
    "resolve_counterparty_establishment_scope",
    "resolve_draft_counterparty_establishment",
    "scope_printed_evidence_would_establish",
]


class EstablishmentRung(StrEnum):
    """Which rung of the ladder settled a counterparty's territory.

    Recorded rather than discarded because the rungs differ in what an auditor
    can be shown. The first three are anchorable to a printed form on the page;
    the fourth is a person's assertion, and pointing an auditor at a page for it
    would be a claim the document never made.

    Attributes:
        TAX_IDENTIFIER_PREFIX: The counterparty's printed VAT number named its
            Member State.
        PRINTED_COUNTRY: The printed address country named a country whose
            territory is settled by the country alone.
        SPANISH_POSTAL_CODE: The country evidence named Spain and the printed
            postal code separated the three Spanish IVA territories.
        CONFIRMED_COUNTERPARTY_FACT: An operator had already confirmed this
            counterparty's establishment, and the paper settled nothing that
            disagreed.
    """

    TAX_IDENTIFIER_PREFIX = "tax_identifier_prefix"
    PRINTED_COUNTRY = "printed_country"
    SPANISH_POSTAL_CODE = "spanish_postal_code"
    CONFIRMED_COUNTERPARTY_FACT = "confirmed_counterparty_fact"


class CounterpartyEstablishment(BaseModel):
    """What the ladder settled about one counterparty on one document.

    Attributes:
        scope: The territory, or ``None`` when the ladder exhausted without a
            decisive rung. ``None`` is this codebase's spelling of the ruling's
            UNKNOWN: a missing scope is not a kind of scope, and adding an
            unknown member to the closed set would put a value into it that
            every rule table downstream would then have to special-case.
        rung: Which rung answered. ``None`` exactly when ``scope`` is.
        source: How the answer is backed -- a printed form for the evidence
            rungs, a person for the remembered assertion. ``None`` exactly when
            ``scope`` is, because an unsettled question has nobody vouching for
            it.
        contradiction: A confirmed fact the document's printed evidence
            disputes. Carried WITH no scope: the stored value is an operator's
            claim about an entity and the printed value is an issuer's claim
            about one document, and neither may be preferred without a decision.
    """

    model_config = STRICT_FROZEN_CONFIG

    scope: IvaTerritorialScope | None = None
    rung: EstablishmentRung | None = None
    source: ClassifierInputSource | None = None
    contradiction: CounterpartyEstablishmentContradiction | None = None

    @property
    def established(self) -> bool:
        """Return whether the ladder settled a territory."""
        return self.scope is not None

    @property
    def contradicted(self) -> bool:
        """Return whether the evidence disputes a confirmed fact."""
        return self.contradiction is not None

    @property
    def declared_fact(self) -> DeclaredFact[IvaTerritorialScope] | None:
        """Return this scope in the form the criteria assembly consumes.

        The one channel a resolved scope reaches the assembly through, so the
        value and who established it travel together. ``None`` where the ladder
        settled nothing, which the assembly then reports as a missing input.
        """
        if self.scope is None or self.source is None:
            return None
        return DeclaredFact[IvaTerritorialScope](value=self.scope, source=self.source)


def _printed_country_code(
    *,
    printed_country_name: str | None,
    printed_country_code: str | None,
) -> str | None:
    """Return the country code the document's address block states, if any.

    Both spellings are the same rung. The NAME is asked first because it is the
    form an address block actually prints -- in the document's own language, so
    asking a reading stage for the code would be asking it to translate, and
    translation is inference. The already-printed code is the fallback for the
    surfaces that carry one.

    A name outside the vocabulary does not fall through to the raw code as a
    country: an unrecognised name establishes nothing, and the code is consulted
    only where no name was recognised at all.
    """
    from_name = country_code_for_printed_country_name(printed_country_name)
    if from_name is not None:
        return from_name
    return printed_country_code


def _printed_evidence(
    *,
    tax_identifier: str | None,
    country_code: str | None,
    postal_code: str | None,
) -> tuple[IvaTerritorialScope | None, EstablishmentRung | None]:
    """Walk the three document rungs in order and stop at the first decisive one.

    Ordering is the safety property, not an optimisation: the country rung is
    consulted before the postal rung so that a foreign five-digit code is never
    offered to the Spanish province lookup, which would answer it.
    """
    from_identifier = territorial_scope_for_printed_tax_identifier(tax_identifier)
    if from_identifier is not None:
        return from_identifier, EstablishmentRung.TAX_IDENTIFIER_PREFIX

    from_country = territorial_scope_for_country(country_code)
    if from_country is not None:
        return from_country, EstablishmentRung.PRINTED_COUNTRY

    # Spain reaches here rather than above BY DESIGN: the country rung refuses to
    # resolve `ES` because it names the State while the IVA territory inside it
    # stays undetermined. That refusal is the postal rung's trigger, so the CODE
    # is tested rather than the scope the code produced.
    if names_spain(country_code):
        from_postal = territorial_scope_for_spanish_postal_code(postal_code)
        if from_postal is not None:
            return from_postal, EstablishmentRung.SPANISH_POSTAL_CODE

    return None, None


def scope_printed_evidence_would_establish(
    *,
    tax_identifier: str | None = None,
    printed_country_name: str | None = None,
    printed_country_code: str | None = None,
    postal_code: str | None = None,
) -> IvaTerritorialScope | None:
    """Return the territory this printed evidence alone would settle, or ``None``.

    The document rungs only, with no store consulted and nothing persisted. It
    exists so a DIAGNOSTIC can name a territory without re-deriving the boundary
    that produces it: an advisory warning that a party's address values are of
    unverified attribution is far more actionable when it also says where those
    values would place the party, and the operator is then contesting a concrete
    claim rather than an abstraction.

    Quoting rather than copying is the whole point. A second walk of the rungs
    written for the advisory would be a second copy of a regulatory boundary,
    free to drift from this one -- and the ordering it would have to reproduce
    is precisely the safety property this module exists to hold.

    **Not a resolution, and never a substitute for one.** No confirmed
    counterparty fact is consulted, so a contradiction cannot surface here and
    an answer from this function must never reach the criteria. Callers wanting
    the settled territory call
    :func:`resolve_counterparty_establishment_scope`.

    Args:
        tax_identifier: The party's identifier as printed, if any.
        printed_country_name: The country as printed in the address block.
        printed_country_code: An already-printed alpha-2 country code.
        postal_code: The party's printed postal code.

    Returns:
        The territory the printed rungs settle, or ``None`` where they exhaust.
    """
    scope, _rung = _printed_evidence(
        tax_identifier=tax_identifier,
        country_code=_printed_country_code(
            printed_country_name=printed_country_name,
            printed_country_code=printed_country_code,
        ),
        postal_code=postal_code,
    )
    return scope


def resolve_counterparty_establishment_scope(
    *,
    bucket_id: str,
    tax_identifier: str | None = None,
    printed_country_name: str | None = None,
    printed_country_code: str | None = None,
    postal_code: str | None = None,
    repository: CounterpartyEstablishmentRepository | None = None,
) -> CounterpartyEstablishment:
    """Resolve where a counterparty is established, or settle nothing and say so.

    The confirmed-fact rung is consulted even when the paper was decisive, and
    that is not a departure from first-decisive-rung: the store is asked to
    COMPARE, not to answer. A confirmed-Canarian counterparty printing a French
    country code is a real signal -- a different entity behind a reused
    identifier, an establishment that moved, or an assertion made in error --
    and none of the three is settled by preferring a side, so the disagreement
    is carried and NO scope is returned. Skipping the store on a decisive page
    would take that channel offline for exactly the population it protects.

    Args:
        bucket_id: Active profile bucket, for the confirmed-fact rung.
        tax_identifier: The counterparty's identifier as printed, if any.
        printed_country_name: The country as printed in the address block, in
            whatever language the issuer set it.
        printed_country_code: An already-printed alpha-2 country code, for
            surfaces that carry one instead of a name.
        postal_code: The counterparty's printed postal code. Consulted only
            where the country evidence positively named Spain.
        repository: Injected store.

    Returns:
        :class:`CounterpartyEstablishment`: the territory and the rung that
        settled it, a contradiction, or neither.

    Raises:
        IvaCatalogueError: When the bundled country vocabulary or territory
            registry cannot be read, is malformed, or carries a name two
            countries claim. Deliberately propagated: a broken bundled data file
            is a defect, and quietly reporting it as an unestablished party
            would send an operator to answer a question that is not theirs.
        Exception: Whatever the confirmed-fact store raises, on the same terms
            and for a sharper reason. A store that cannot be read is not a
            counterparty nobody has confirmed -- and the operator may have
            confirmed this one already, so swallowing the failure would retract
            their own earlier answer and ask them for it again, against a store
            that would refuse to record it. The secure repository takes the same
            position on the tier below, raising rather than returning ``None``
            when a row exists but is inconsistent, precisely so an inconsistency
            cannot hide behind an ordinary miss. No error type is named here
            because none is caught: the store owns its own vocabulary and this
            function is transparent to it.
    """
    country_code = _printed_country_code(
        printed_country_name=printed_country_name,
        printed_country_code=printed_country_code,
    )
    evidenced, rung = _printed_evidence(
        tax_identifier=tax_identifier,
        country_code=country_code,
        postal_code=postal_code,
    )

    remembered = resolve_counterparty_establishment(
        bucket_id=bucket_id,
        tax_identifier=tax_identifier,
        country_code=country_code,
        evidenced_scope=evidenced,
        repository=repository,
    )
    if remembered.contradiction is not None:
        return CounterpartyEstablishment(contradiction=remembered.contradiction)

    if evidenced is not None:
        return CounterpartyEstablishment(
            scope=evidenced,
            rung=rung,
            source=ClassifierInputSource.DOCUMENT_EVIDENCE,
        )

    if remembered.fact is not None:
        return CounterpartyEstablishment(
            scope=remembered.fact.value,
            rung=EstablishmentRung.CONFIRMED_COUNTERPARTY_FACT,
            source=remembered.fact.source,
        )

    return CounterpartyEstablishment()


def resolve_draft_counterparty_establishment(
    *,
    bucket_id: str,
    draft: InvoiceDraft,
    kind: InvoiceKind,
    repository: CounterpartyEstablishmentRepository | None = None,
) -> CounterpartyEstablishment:
    """Route a read document's COUNTERPARTY into the ladder, by direction.

    A draft is pre-direction data: it records what each party's block said
    without deciding which of them the filer is. This is where that decision
    reaches the establishment question, and it makes it through the one authority
    that already makes it for the confirm path, so a document cannot be read as
    having one counterparty when its identity is resolved and another when its
    territory is.

    **The filer's own side is never asked here.** One party on every ingested
    invoice is the operator, whose territory is a profile fact; feeding their
    printed block to a ladder built for the counterparty would answer a question
    the profile already answers, and would answer it from weaker evidence.

    **Every rung is reachable from a read document, and only from a read one.**
    The reading path recovers each party's printed country name, so the country
    rung has a source and the postal rung -- gated on country evidence positively
    naming Spain -- can be triggered by it. The STRUCTURED path is the remaining
    gap and it is upstream of this function: the e-invoice parsers read a postal
    element and no country element, so a Facturae, UBL or CII document reaches
    only the identifier and confirmed-fact rungs. A Spanish counterparty on one
    of those exhausts to nothing and is asked once, which is the honest outcome
    rather than a defective one; what would be defective is reading this
    function's correct answers as evidence that every path reaches every rung.

    Args:
        bucket_id: Active profile bucket, for the confirmed-fact rung.
        draft: The pre-direction reading of the document.
        kind: Which side of the invoice the filer is on, as the operator settled
            it at confirm. Never the reader's suggestion.
        repository: Injected store.

    Returns:
        :class:`CounterpartyEstablishment`: the territory and the rung that
        settled it, a contradiction, or neither.
    """
    # Deferred to call time: the draft module reaches the parsers, the reading
    # package and the catalogue, so importing it at module scope would make this
    # lean module pay for all of it. The sanctioned cycle-break shape, and it
    # changes only WHEN the owning module executes -- the selection keeps its one
    # home and one import path.
    from ._evidence_draft import counterparty_draft_side

    side = counterparty_draft_side(draft, kind=kind)
    return resolve_counterparty_establishment_scope(
        bucket_id=bucket_id,
        tax_identifier=side.tax_id,
        printed_country_code=side.country_code,
        printed_country_name=side.country,
        postal_code=side.postal_code,
        repository=repository,
    )
