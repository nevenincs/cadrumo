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

**A printed IVA number is NOT a rung here, and that is the correction this
ladder exists in its current form to carry.** It once was the first and
strongest one: a ``DE`` prefix resolved decisively to ``EU_MEMBER`` and stopped
the walk. Every Member State registers non-residents on exactly the terms Spain
does, so that read the party's REGISTRATION as its PLACE — and it did so on one
side only, because a Spanish registration was already, correctly, refused. The
foreign direction was the dangerous one: a German-registered entity actually
established in Spain resolved silently and confidently, where its Spanish mirror
failed loud to the operator.

The prefix is now terminal for the OTHER fact, the party's IVA identification
state, which it settles decisively because registration is exactly what that
fact asserts. What it never settles alone is where the party IS.

The rungs, strongest first:

1. **The printed address country**, as a name matched against the bounded
   registry vocabulary or as an already-printed alpha-2 code. It is now first,
   and it needs no help from the registration: an address stating France places
   a French-established party whatever State registered it.
2. **The Spanish postal code**, consulted ONLY where the country evidence
   positively named Spain. A postal pattern alone presupposes exactly what it
   would have to prove.
3. **A foreign registration CONCORDANT with an independent rung**, where the
   address rungs settled nothing. The registration alone is never enough; what
   makes it usable is a second, independent signal agreeing with it — a printed
   treatment consistent with the party not being established here, such as a
   reverse-charge mention with no Spanish IVA charged. Concordant papers resolve
   silently, which is what keeps the foreign population from being asked.
4. **A previously confirmed counterparty-level fact**, because establishment is
   a property of the entity and the operator should be asked at most once.

**And any Spain-indicating rung beside a foreign registration is a CONTRADICTION,
never a resolution either way.** A Spanish address, country-gated Spanish postal
evidence, or Spanish IVA charged at a registry rate, printed on a document whose
counterparty carries another State's IVA number, is the characteristic face of a
foreign-registered entity operating through an establecimiento permanente in
Spain. It fails loud, and it is checked BEFORE the ordinary rungs so the postal
rung cannot quietly answer it.

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
:func:`~application.ledger.filer_establishment.resolve_filer_territorial_scope`. Only the
counterparty's scope is ever sought on the paper.

See Also:
    :func:`~application.ledger.counterparty_establishment.resolve_confirmed_counterparty_facts`
        The fourth rung, and the store an operator's answer persists into.
    :class:`~application.ledger.classification_assembly.DeclaredFacts`
        The one channel a resolved scope reaches the criteria assembly through.
    :class:`~domain.iva.IvaTerritorialScope`
        The closed target every rung resolves into.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ...core.classifier_input_source import ClassifierInputSource
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.iva.classification import IvaTerritorialScope
from ...domain.iva.establishment import (
    country_code_for_printed_country_name,
    territorial_scope_for_country,
    territorial_scope_for_spanish_postal_code,
)
from ...domain.iva.identification import identification_state_for_printed_tax_identifier
from ...domain.iva.legend_derivation import match_regime_legend
from ...domain.iva.lookup import rate_kinds_for_declared_rate
from ...domain.iva.schema import EUMemberState

# `names_spain` is the sibling module's authority on what positively names
# Spain, and is imported rather than restated: a second copy of that test is
# exactly the drift that would let one surface open the postal rung while the
# other does not. The import direction also keeps the pair acyclic, since the
# declared-fact channel below is owned there too.
from .classification_assembly import DeclaredFact, names_spain
from .counterparty_establishment import (
    ConfirmedCounterpartyFactsRepository,
    CounterpartyEstablishmentContradiction,
    resolve_confirmed_counterparty_facts,
)

if TYPE_CHECKING:
    from datetime import date

    from ...domain.iva.classification import InvoiceKind
    from .invoice_draft_records import InvoiceDraft

__all__ = [
    "CounterpartyEstablishment",
    "EstablishmentRung",
    "RegistrationEstablishmentConflict",
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

    **There is no tax-identifier rung, and its absence is the point.** One was
    here, first and strongest, until a printed foreign prefix was recognised as
    evidence of REGISTRATION rather than of place. The member is not retained
    unused: an unreachable rung in a closed set is a value every consumer would
    still have to handle, and the honest record of what settled such a document
    is that nothing did.

    Attributes:
        CONCORDANT_REGISTRATION: A foreign registration corroborated by an
            independent signal agreeing with it, where the address rungs settled
            nothing and no rung indicated Spain. Weaker than the printed rungs
            above it, which is why it is consulted after them.
        ADDRESS_COUNTRY: The country stated in the party's address block named
            a country whose territory is settled by the country alone.

            Named for WHERE the evidence sits, not for how it was rendered.
            It was ``PRINTED_COUNTRY`` while a printed document was the only
            thing that could feed it; a structured record states the same
            country in an element, and an operator reading "printed" against
            a machine-readable invoice is told the value came from somewhere
            it did not. The rung is one rung either way -- the same
            authority decides what a country establishes -- so the label
            names the address rather than the medium.
        SPANISH_POSTAL_CODE: The country evidence named Spain and the postal
            code in the address separated the three Spanish IVA territories.
        CONFIRMED_COUNTERPARTY_FACT: An operator had already confirmed this
            counterparty's establishment, and the paper settled nothing that
            disagreed.
    """

    CONCORDANT_REGISTRATION = "concordant_registration"
    ADDRESS_COUNTRY = "address_country"
    SPANISH_POSTAL_CODE = "spanish_postal_code"
    CONFIRMED_COUNTERPARTY_FACT = "confirmed_counterparty_fact"


class RegistrationEstablishmentConflict(BaseModel):
    """A foreign registration printed beside evidence placing the party in Spain.

    Carried rather than resolved, on the same terms as the confirmed-fact
    disagreement and for a sharper reason. **This is the shape the dangerous
    population characteristically presents.** An entity registered in another
    Member State but operating through an establecimiento permanente in Spain
    charges Spanish IVA on its domestic supplies and prints a Spanish address to
    do it — so a foreign IVA number beside a Spanish address, Spanish postal
    evidence or a Spanish registry rate is not noise, it is the signature of the
    exact case the split exists to catch.

    Preferring either side would be a guess with a filing behind it. Preferring
    the registration reinstates the silent ``EU_MEMBER`` this whole change
    removes; preferring the Spanish evidence would assert an establishment the
    document does not state. So no scope is returned and a human decides.

    Attributes:
        identification_state: The Member State whose IVA number was printed.
        spain_indicating: What placed the party in Spain, in operator-facing
            words. Never empty — a conflict nobody can see the other half of is
            not actionable.
        detail: The disagreement in words, for the operator-facing finding.
    """

    model_config = STRICT_FROZEN_CONFIG

    identification_state: EUMemberState
    spain_indicating: tuple[str, ...] = Field(min_length=1)
    detail: str = Field(min_length=1)


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
        identification_state: The Member State whose IVA number the counterparty
            printed. Settled TERMINALLY by the prefix and carried independently
            of ``scope``, because they are two facts: this one is decided by
            registration evidence, and the other is decided by no registration at
            all. It is populated on a conflict and on an unestablished result
            alike -- the paper can name the registering State perfectly well
            while saying nothing about where the party operates.
        registration_conflict: A foreign registration printed beside evidence
            placing the party in Spain. Carried WITH no scope, on the same
            reasoning as ``contradiction``.
    """

    model_config = STRICT_FROZEN_CONFIG

    scope: IvaTerritorialScope | None = None
    rung: EstablishmentRung | None = None
    source: ClassifierInputSource | None = None
    contradiction: CounterpartyEstablishmentContradiction | None = None
    identification_state: EUMemberState | None = None
    registration_conflict: RegistrationEstablishmentConflict | None = None

    @property
    def established(self) -> bool:
        """Return whether the ladder settled a territory."""
        return self.scope is not None

    @property
    def contradicted(self) -> bool:
        """Return whether the evidence disputes a confirmed fact.

        Reports the stored-fact disagreement only. The registration conflict is
        a different disagreement between different parties -- an issuer's own
        two statements rather than an issuer against an operator -- and folding
        them into one flag would leave a caller unable to say which it is
        looking at, or to route them to the finding each deserves.
        """
        return self.contradiction is not None

    @property
    def conflicted(self) -> bool:
        """Return whether a foreign registration sits beside Spain-indicating evidence."""
        return self.registration_conflict is not None

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


def _party_country_code(
    *,
    stated_country_name: str | None,
    resolved_country_code: str | None,
) -> str | None:
    """Return the country code the document states about this party, if any.

    Both spellings are the same rung. The NAME is asked first because it is the
    form an address block actually prints -- in the document's own language, so
    asking a reading stage for the code would be asking it to translate, and
    translation is inference. The code is the fallback for the surfaces that
    carry one.

    **Stated rather than printed, on both spellings.** A machine-readable
    document reaches this rung too, and its country element was never set in
    type: naming the parameters for typography would make the resolver assert a
    provenance the structured lane never observed, which is the same conflation
    that once shipped a derived value as printed evidence.

    A name outside the vocabulary does not fall through to the raw code as a
    country: an unrecognised name establishes nothing, and the code is consulted
    only where no name was recognised at all.
    """
    from_name = country_code_for_printed_country_name(stated_country_name)
    if from_name is not None:
        return from_name
    return resolved_country_code


_PERCENT: Final[Decimal] = Decimal("100")
"""What a printed IVA rate is divided by to reach the fraction the registry keys on."""


def _spanish_iva_was_charged(
    charged_iva_rates: tuple[Decimal, ...],
    *,
    on_date: date | None,
) -> bool:
    """Whether the document charges IVA at a rate the SPANISH registry carries.

    A repercutido line is only Spain-indicating if the rate is a Spanish one: a
    German supplier invoicing a German customer charges German IVA, and reading
    any charged tax as Spanish tax would place half of Europe inside the TAI.
    The registry is asked rather than a literal compared, so a rate the schedule
    stops carrying stops indicating.

    **Without a date the check is inconclusive, and inconclusive contributes
    nothing in either direction.** It raises no conflict, because a false
    conflict blocks a legitimate filing; and it supplies no concordance, because
    a rate nobody could verify is not a second signal. The operation then falls
    to the ordinary rungs and, failing those, to a question -- safe both ways.

    Args:
        charged_iva_rates: The rates as a document PRINTS them, whole-number
            percentages. The registry's inverse lookup takes a fraction, so the
            conversion happens here rather than at every caller -- the same
            hundredth the discrepancy check in the draft module applies, and the
            unit is named in both places because a percentage handed to that
            lookup silently matches nothing and reads as "no Spanish rate".
        on_date: The date the rate must have been in force.
    """
    if on_date is None:
        return False
    return any(
        rate_kinds_for_declared_rate(EUMemberState.ES, rate / _PERCENT, on_date)
        for rate in charged_iva_rates
        # Zero is excluded before the lookup and not by it. The registry answers
        # that 0 % is always a legitimate Spanish ZERO-tier rate, which is true
        # and is the wrong question here: a zero-rated line charges no tax, so
        # it places the party nowhere.
        if rate > 0
    )


def _spain_indicating(
    *,
    country_code: str | None,
    postal_code: str | None,
    spanish_iva_charged: bool,
) -> tuple[str, ...]:
    """Return every signal placing this party in Spain, in operator-facing words.

    Collected rather than short-circuited, because this feeds a finding a human
    has to act on: a Spanish address AND Spanish IVA at a registry rate is a far
    stronger prompt than whichever single signal happened to be tested first.
    """
    signals: list[str] = []
    if names_spain(country_code):
        signals.append("the printed address country names Spain")
        if territorial_scope_for_spanish_postal_code(postal_code) is not None:
            signals.append("the printed postal code resolves to a Spanish IVA territory")
    if spanish_iva_charged:
        signals.append("the document charges IVA at a Spanish registry rate")
    return tuple(signals)


def _mention_declares_no_spanish_tax(regime_legend: str | None) -> bool:
    """Whether the printed mention itself declares the issuer charged nothing here.

    A reverse-charge mention shifts the tax to the recipient, and LIVA art.
    84.Uno.2 makes the recipient the sujeto pasivo precisely when the supplier is
    NOT established in the territory -- so an issuer printing it has stated, in a
    mention the regulation fixes the wording of, that it did not have to charge
    here.

    Asked of the shipped legend record rather than by comparing the phrase,
    because which mentions expect a repercutido line is already declared there;
    a second list here would be a second authority on the statutory vocabulary.
    """
    legend = match_regime_legend(regime_legend)
    return legend is not None and not legend.expects_repercutido_line


def _taxed_under_the_registration_state(
    charged_iva_rates: tuple[Decimal, ...],
    *,
    identification: EUMemberState,
    on_date: date | None,
) -> bool:
    """Whether the document charges tax at the registration State own rate.

    The second corroborating treatment, and a POSITIVE signal rather than an
    absence. A supplier not established here charges under the law it IS
    established under, so a document printing a rate that its own Member State
    schedule carries has done exactly that -- and it has done it in arithmetic,
    which is harder to print by accident than a phrase.

    **The rate must be one Spain does NOT also carry, or it corroborates
    nothing.** Twenty-one per cent is the general rate in Spain and in the
    Netherlands alike, so a Dutch-identified issuer charging it has stated
    something both readings explain equally. Nineteen is German and not Spanish,
    so it discriminates. That exclusion is not spelled here: the walk reaches
    this point only when no Spain-indicating signal fired, and a charged Spanish
    registry rate IS such a signal, so any rate still standing is already one the
    Spanish schedule does not carry on this date.

    **Both schedules are asked of the registry, never compared to literals.** A
    rate the schedule stops carrying stops corroborating, and a State whose rate
    changes moves here with it.

    Args:
        charged_iva_rates: The rates as the document PRINTS them, whole-number
            percentages, converted to the fraction the registry keys on.
        identification: The Member State whose IVA identification the party
            printed -- the only State whose schedule is relevant, because the
            claim being corroborated is that the party is established THERE.
        on_date: The date the rate must have been in force.

    Returns:
        Whether some charged rate is one that State schedule carries.

        ``False`` without a date, on the terms the Spanish check states: a rate
        nobody could verify is not a second signal, and inconclusive contributes
        nothing in either direction rather than being read as agreement.
    """
    if on_date is None:
        return False
    return any(
        rate_kinds_for_declared_rate(identification, rate / _PERCENT, on_date)
        for rate in charged_iva_rates
        # Zero is excluded for the reason it is excluded on the Spanish side: a
        # zero-rated line charges no tax under anybody law, so it places the
        # party nowhere rather than in the State whose schedule happens to carry
        # a zero tier.
        if rate > 0
    )


def _treatment_concurs_with_non_establishment(
    *,
    regime_legend: str | None,
    spanish_iva_charged: bool,
    charged_iva_rates: tuple[Decimal, ...],
    identification: EUMemberState,
    on_date: date | None,
) -> bool:
    """Whether the printed treatment independently agrees the party is not here.

    Two signals, either of which corroborates, and they are independent kinds of
    evidence rather than two spellings of one: the mention is what the issuer
    SAID about the operation, and the charged rate is what the issuer DID about
    it. A document carrying either has stated, in the regulation own words or in
    its own arithmetic, that it did not tax here.

    **The single-source version was safe but incomplete, and it was recorded as
    such rather than left to be found.** Only the reverse-charge mention was
    recognised, so a foreign-registered issuer that simply charged its own
    country IVA -- the ordinary shape of a cross-border invoice that is not a
    reverse charge -- corroborated nothing and fell to a question. That is the
    safe direction: an unanswered question, never a wrong territory. It was still
    a gap.

    **Spanish tax charged defeats both limbs**, and that is checked once here
    rather than inside each. A document charging at a Spanish registry rate is
    the Spain-indicating signal the walk has already tested, so reaching this
    point with one would mean the walk contradicted itself; the check is repeated
    rather than assumed, because relying on a caller ordering for a safety
    property is how the ordering becomes load-bearing without saying so.
    """
    if spanish_iva_charged:
        return False
    if _mention_declares_no_spanish_tax(regime_legend):
        return True
    return _taxed_under_the_registration_state(
        charged_iva_rates,
        identification=identification,
        on_date=on_date,
    )


def _printed_evidence(
    *,
    tax_identifier: str | None,
    country_code: str | None,
    postal_code: str | None,
    regime_legend: str | None = None,
    charged_iva_rates: tuple[Decimal, ...] = (),
    on_date: date | None = None,
) -> tuple[IvaTerritorialScope | None, EstablishmentRung | None, RegistrationEstablishmentConflict | None]:
    """Walk the document rungs and stop at the first decisive one, or conflict.

    Ordering is the safety property, not an optimisation, and it now carries two
    of them. The country rung is consulted before the postal rung so a foreign
    five-digit code is never offered to the Spanish province lookup, which would
    answer it. And the registration-versus-Spain check is consulted before BOTH,
    so a foreign-registered party printing a Spanish address surfaces instead of
    being quietly resolved to a Spanish territory by the rung below.

    The printed IVA number appears here only as the thing that must be
    CORROBORATED. It settles no territory by itself at any point in this walk.
    """
    identification = identification_state_for_printed_tax_identifier(tax_identifier)
    spanish_iva_charged = _spanish_iva_was_charged(charged_iva_rates, on_date=on_date)

    # FOREIGN registration, not merely a registration. The conflict this raises
    # is the characteristic face of a foreign-registered entity operating
    # through an establecimiento permanente here, so a SPANISH identification
    # beside Spain-indicating evidence is agreement rather than contradiction.
    #
    # The test used to be "is not None" and was safe only by accident: ES was
    # absent from the identification vocabulary, so no Spanish number ever
    # reached it. Admitting ES made the accident visible, and the condition now
    # says what it always meant.
    if identification is not None and identification is not EUMemberState.ES:
        indicating = _spain_indicating(
            country_code=country_code,
            postal_code=postal_code,
            spanish_iva_charged=spanish_iva_charged,
        )
        if indicating:
            return (
                None,
                None,
                RegistrationEstablishmentConflict(
                    identification_state=identification,
                    spain_indicating=indicating,
                    detail=(
                        f"the counterparty prints a {identification.value.upper()} IVA identification while "
                        f"{'; '.join(indicating)}. A party registered in another Member State may still be "
                        f"established in Spain through a sede or establecimiento permanente, and this "
                        f"document states both -- which of the two governs its IVA treatment is not settled "
                        f"by the paper"
                    ),
                ),
            )

    from_country = territorial_scope_for_country(country_code)
    if from_country is not None:
        return from_country, EstablishmentRung.ADDRESS_COUNTRY, None

    # Spain reaches here rather than above BY DESIGN: the country rung refuses to
    # resolve `ES` because it names the State while the IVA territory inside it
    # stays undetermined. That refusal is the postal rung's trigger, so the CODE
    # is tested rather than the scope the code produced.
    if names_spain(country_code):
        from_postal = territorial_scope_for_spanish_postal_code(postal_code)
        if from_postal is not None:
            return from_postal, EstablishmentRung.SPANISH_POSTAL_CODE, None

    if identification is not None and _treatment_concurs_with_non_establishment(
        regime_legend=regime_legend,
        spanish_iva_charged=spanish_iva_charged,
        charged_iva_rates=charged_iva_rates,
        identification=identification,
        on_date=on_date,
    ):
        # The registration's OWN State, and only because something else agreed.
        # `None` here is not a failure to look up a country: Northern Ireland
        # carries an IVA prefix without being an ISO jurisdiction the catalogue
        # resolves, and a registration whose territory cannot be named is one
        # this walk cannot corroborate into a scope.
        concordant = territorial_scope_for_country(identification.value.upper())
        if concordant is not None:
            return concordant, EstablishmentRung.CONCORDANT_REGISTRATION, None

    return None, None, None


def scope_printed_evidence_would_establish(
    *,
    tax_identifier: str | None = None,
    stated_country_name: str | None = None,
    resolved_country_code: str | None = None,
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

    **A registration conflict reads here as no territory**, which is the honest
    projection for a diagnostic: the advisory this feeds says where the printed
    values would place the party, and a document whose registration and address
    disagree has no single such place to name. The conflict itself is an
    operator-facing finding rather than a hint, and it surfaces through the
    resolution path that can carry it.

    Args:
        tax_identifier: The party's identifier as printed, if any.
        stated_country_name: The country the document states for this party.
        resolved_country_code: The party's country as an alpha-2 code, already
            RESOLVED through the bounded vocabulary -- never the token a
            record stated. A structured document states an alpha-3 as
            readily as an alpha-2, and both are ``str | None``, so feeding
            the stated token here type-checks and silently places nobody.
        postal_code: The party's printed postal code.

    Returns:
        The territory the printed rungs settle, or ``None`` where they exhaust.
    """
    scope, _rung, _conflict = _printed_evidence(
        tax_identifier=tax_identifier,
        country_code=_party_country_code(
            stated_country_name=stated_country_name,
            resolved_country_code=resolved_country_code,
        ),
        postal_code=postal_code,
    )
    return scope


def resolve_counterparty_establishment_scope(
    *,
    bucket_id: str,
    tax_identifier: str | None = None,
    stated_country_name: str | None = None,
    resolved_country_code: str | None = None,
    postal_code: str | None = None,
    regime_legend: str | None = None,
    charged_iva_rates: tuple[Decimal, ...] = (),
    on_date: date | None = None,
    repository: ConfirmedCounterpartyFactsRepository | None = None,
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
        stated_country_name: The country the document states for this party, in
            whatever language the issuer set it. Printed in an address block on
            a rendered document, carried in a country element on a structured
            one; the rung treats the two alike, so the parameter claims only
            that the document stated it.
        resolved_country_code: The party's country as an already-resolved
            alpha-2 code, never the stated token, for
            surfaces that carry one instead of a name.
        postal_code: The counterparty's printed postal code. Consulted only
            where the country evidence positively named Spain.
        regime_legend: The statutory mention the document prints, if any. Read
            for one thing only: whether the treatment independently agrees the
            counterparty is not established here.
        charged_iva_rates: Every IVA percentage the document charges. Spanish
            registry rates among them place the party here; foreign ones say
            nothing, which is why the rates are passed rather than a flag.
        on_date: The invoice date, for asking the rate schedule what a rate
            meant when it was charged. ``None`` makes the rate check
            inconclusive rather than negative.
        repository: Injected store.

    Returns:
        :class:`CounterpartyEstablishment`: the territory and the rung that
        settled it, a conflict, a contradiction, or none of them.

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
    country_code = _party_country_code(
        stated_country_name=stated_country_name,
        resolved_country_code=resolved_country_code,
    )
    identification = identification_state_for_printed_tax_identifier(tax_identifier)
    evidenced, rung, conflict = _printed_evidence(
        tax_identifier=tax_identifier,
        country_code=country_code,
        postal_code=postal_code,
        regime_legend=regime_legend,
        charged_iva_rates=charged_iva_rates,
        on_date=on_date,
    )

    # Returned before the store is asked, and deliberately. A conflict means the
    # PAPER disagrees with itself, so there is no evidenced scope to compare a
    # remembered fact against -- asking would either compare against nothing or
    # invite the stored value to settle a question the document just raised.
    if conflict is not None:
        return CounterpartyEstablishment(
            identification_state=identification,
            registration_conflict=conflict,
        )

    remembered = resolve_confirmed_counterparty_facts(
        bucket_id=bucket_id,
        tax_identifier=tax_identifier,
        country_code=country_code,
        evidenced_scope=evidenced,
        repository=repository,
    )
    # The printed prefix is terminal where it reads, and the remembered
    # assertion fills the gap where it does not. That precedence is the same one
    # the territory takes -- the page outranks the memory -- and it is what makes
    # one operator answer serve every later document rather than being asked
    # again per invoice.
    #
    # A bare Spanish CIF prints no prefix at all, so this gap is the ordinary
    # case rather than the exceptional one. Without the fallback the stored
    # answer would be unreachable for exactly the counterparties an operator
    # most often has to answer for.
    settled_identification = identification
    if settled_identification is None and remembered.identification is not None:
        settled_identification = remembered.identification.value

    if remembered.contradiction is not None:
        return CounterpartyEstablishment(
            identification_state=settled_identification,
            contradiction=remembered.contradiction,
        )

    if evidenced is not None:
        return CounterpartyEstablishment(
            scope=evidenced,
            rung=rung,
            source=ClassifierInputSource.DOCUMENT_EVIDENCE,
            identification_state=settled_identification,
        )

    if remembered.fact is not None:
        return CounterpartyEstablishment(
            scope=remembered.fact.value,
            rung=EstablishmentRung.CONFIRMED_COUNTERPARTY_FACT,
            source=remembered.fact.source,
            identification_state=settled_identification,
        )

    return CounterpartyEstablishment(identification_state=settled_identification)


def _charged_iva_rates(draft: InvoiceDraft) -> tuple[Decimal, ...]:
    """Return every IVA percentage the document charges, from all three carriers.

    All three are read because a document uses whichever its reader could
    recover: some print a rate per line, some only a per-rate subtotal block,
    and a text- or vision-read document carries neither -- it states one flat
    rate, because those readers recover printed totals rather than a
    decomposition. A walk of a subset reports no charged tax for every document
    using the rest, silently turning a Spain-indicating signal off for a whole
    population.

    **The flat rate was the missing one, and it is the model-read lane's ONLY
    carrier.** The line and subtotal carriers are populated exclusively by the
    structured reader, so this collected nothing at all for every text and
    vision document: ``spanish_iva_charged`` is derived from this list alone, so
    the establecimiento-permanente contradiction lost its rate signal and the
    non-establishment concordance lost a corroborator, on exactly the documents
    a model read. The sibling authority on the same question --
    :func:`~application.ledger.regime_contradiction.draft_prints_a_repercutido_line` -- already reads
    the flat rate, so the two disagreed about what a document charged.

    A rate is what is collected, never a cuota amount. Whether the rate is a
    SPANISH one is the question this feeds, and only the percentage can answer
    it; an amount says tax was charged without saying whose.
    """
    rates = [line.iva_rate for line in draft.lines if line.iva_rate is not None]
    rates.extend(subtotal.iva_rate for subtotal in draft.iva_breakdown if subtotal.iva_rate is not None)
    if draft.iva_rate is not None:
        rates.append(draft.iva_rate)
    return tuple(rates)


def _draft_date(draft: InvoiceDraft) -> date | None:
    """Return the invoice date the rate schedule should be asked about.

    Parsed through the shipped date authority rather than re-read here, and an
    unparseable value yields ``None`` rather than raising: a date the reader
    could not recover is an ordinary outcome of reading, and it makes the rate
    check inconclusive rather than making the whole resolution fail.
    """
    from ...core.parsing import parse_iso8601_date

    return parse_iso8601_date(draft.invoice_date)


def resolve_draft_counterparty_establishment(
    *,
    bucket_id: str,
    draft: InvoiceDraft,
    kind: InvoiceKind,
    repository: ConfirmedCounterpartyFactsRepository | None = None,
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

    **The document's TREATMENT is read here, not just its address block.** The
    concordance rung and the Spain-indicating check both need what the invoice
    did about tax, so the regime mention and every charged IVA rate travel in
    beside the address values. They are drawn from the whole document rather
    than from the counterparty's side of it, and that is correct rather than
    sloppy: an invoice states one treatment for the operation, not one per
    party, and the charged rate is the issuer's claim about the supply.

    **Every rung is reachable from a read document, and only from a read one.**
    The reading path recovers each party's printed country name, so the country
    rung has a source and the postal rung -- gated on country evidence positively
    naming Spain -- can be triggered by it. The STRUCTURED path is the remaining
    gap and it is upstream of this function: the e-invoice parsers read a postal
    element and no country element, so a Facturae, UBL or CII document reaches
    only the concordance and confirmed-fact rungs. A Spanish counterparty on one
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
        settled it, a conflict, a contradiction, or none of them.
    """
    # Deferred to call time: the draft module reaches the parsers, the reading
    # package and the catalogue, so importing it at module scope would make this
    # lean module pay for all of it. The sanctioned cycle-break shape, and it
    # changes only WHEN the owning module executes -- the selection keeps its one
    # home and one import path.
    from .evidence_draft import counterparty_draft_side

    side = counterparty_draft_side(draft, kind=kind)
    return resolve_counterparty_establishment_scope(
        bucket_id=bucket_id,
        tax_identifier=side.tax_id,
        resolved_country_code=side.country_code,
        stated_country_name=side.country,
        postal_code=side.postal_code,
        regime_legend=draft.regime_legend,
        charged_iva_rates=_charged_iva_rates(draft),
        on_date=_draft_date(draft),
        repository=repository,
    )
