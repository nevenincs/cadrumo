"""Where the establishment ladder is actually reached: the confirm path.

The ladder, its four rungs, the identification and establishment split, the
country vocabulary, the alpha-3 correspondence and the Spanish postal derivation
were each built and each gated. None of them was called from a live path. This
module is the call: it takes the document an operator is confirming and the
direction they settled it under, resolves BOTH parties' territories through the
authorities that own them, and hands the answers to the criteria assembly in the
one channel that carries who established what.

**Two parties, two authorities, and they are not interchangeable.** The filer's
own territory is a profile fact -- system-authoritative, declared once, and
identical whichever document is being confirmed -- so it is read from the profile
and never from the paper. Only the counterparty's territory is a document
question, and it is answered by the ladder. Resolving the filer from their
printed address block would ask a probabilistic reader for something already
known with certainty, and resolving the counterparty from the profile would
answer a question about one entity with a fact about another.

**Neither authority is doubled by the assembly.** The criteria assembly can
derive a scope from a printed country and postal code itself, and this module
deliberately hands it NEITHER for the parties it has already resolved. A scope
supplied as a declared fact and a scope re-derived from the same printed values
are two answers to one question, and the second one is reached exactly when the
first refused -- so the duplication would not merely be redundant, it would
resurrect every answer the ladder declined to give. The ladder's refusals are
the reason it exists.

**An exhausted ladder yields no territory and says so.** There is no branch here
that answers without evidence. The peninsula is the majority population, so a
default there is invisible in testing while silently placing Canarian and Ceutan
counterparties inside a territory their operations are not subject to. What an
exhausted ladder produces instead is a review item naming the counterparty, so
the question reaches a person.

**The review items are surfaced, not yet refused, and that is a stated
interim.** The fourth amendment's design is one question per new counterparty
whose paper is non-decisive, deduped by an operator answer persisted at
counterparty level. The persisting verb has no operator-facing surface yet, so
refusing here would make every domestic invoice permanently unconfirmable rather
than asking once -- a refusal nobody can answer is not a review gate. The items
are therefore carried onto the confirmation result, where the review surface
reads them, and the refusal follows the answer channel rather than preceding it.

See Also:
    :func:`~application.ledger.resolve_draft_counterparty_establishment`
        The ladder this module routes the counterparty into.
    :func:`~application.ledger.resolve_filer_territorial_scope`
        The profile authority for the filer's own side.
    :class:`UserProfileRecord`
        The record that authority reads the filer's territory out of, and the
        reason the filer's side is never asked of the paper: it is a declared
        system-authoritative fact, so an absent record is a setup gap rather
        than an unreadable document.
    :func:`~application.ledger.assemble_classification_criteria`
        What the resolved scopes are carried into.
    :class:`~application.ledger.DeclaredFacts`
        The one channel a resolved scope reaches the assembly through.
    :class:`~domain.iva.IvaTerritorialScope`
        The closed territory axis both authorities resolve into.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG, ClassifierInputSource, ConfirmationBlockReason, IvaCategoryOutcome
from ...core.parsing import parse_iso8601_date
from ...domain.iva import (
    InvoiceKind,
    IvaCategory,
    IvaRateKind,
    IvaTerritorialScope,
    SupplyNature,
    SupplyNatureDerivationOutcome,
    derive_supply_nature_from_citation,
    record_country_code_status,
    supply_nature_implied_by_category,
)
from ._classification_assembly import (
    ClassificationAssembly,
    DeclaredFact,
    DeclaredFacts,
    IvaCategoryResolution,
    assemble_classification_criteria,
    declared_category_from_document_record,
    resolve_ingestion_iva_category,
)
from ._classifier_inputs import collect_classifier_inputs
from ._confirmation_gate import ConfirmationBlocker, blocker_id
from ._counterparty_establishment import ConfirmedCounterpartyFactsRepository
from ._establishment_ladder import CounterpartyEstablishment, resolve_draft_counterparty_establishment
from ._filer_establishment import FILER_POSTCODE_FACT_PATH, resolve_filer_territorial_scope

if TYPE_CHECKING:
    from datetime import date

    from ...domain.user_profile import UserProfileRecord
    from ._evidence_draft import InvoiceDraft

__all__ = ["ConfirmedEstablishment", "resolve_confirmed_establishment"]


class ConfirmedEstablishment(BaseModel):
    """Both parties' territories as one confirm resolved them, and what is still open.

    Attributes:
        counterparty: What the ladder settled about the counterparty, including
            the rung that settled it, any contradiction against a remembered
            fact, and the registration conflict that marks a foreign-registered
            entity operating establishedly in Spain. Carried whole rather than
            flattened to its scope: an auditor asking why a record says what it
            says needs the rung, and a caller told only the territory cannot
            distinguish an exhausted ladder from a conflicted one.
        filer_scope: The taxpayer's own territory, from their profile.
            ``None`` when the profile could not establish it, which is a setup
            gap surfaced as a review item rather than a value invented here.
        declared: The scopes in the form the criteria assembly consumes, each
            beside who established it, with the issuer and customer slots
            filled by the DIRECTION the operator settled rather than by the
            order the document printed its parties in.
        assembly: The criteria the rule table consumes, or every input that
            stopped them. Present whether or not the scopes resolved: the
            missing-input list is what tells an operator all their gaps at once.
        category: The IVA treatment this document resolves to, and what
            established it. The confirm path takes the persisted category from
            here and from nowhere else.
        review_items: The resolvable questions this document leaves open, in the
            review gate's own blocker shape so one surface reads them all.
    """

    model_config = STRICT_FROZEN_CONFIG

    counterparty: CounterpartyEstablishment
    filer_scope: IvaTerritorialScope | None = None
    declared: DeclaredFacts = DeclaredFacts()
    assembly: ClassificationAssembly = ClassificationAssembly()
    category: IvaCategoryResolution = IvaCategoryResolution(outcome=IvaCategoryOutcome.UNRESOLVED)
    review_items: tuple[ConfirmationBlocker, ...] = ()

    @property
    def resolved(self) -> bool:
        """Return whether the counterparty's territory was settled."""
        return self.counterparty.established


def _review_item(*, field: str | None, detail: str) -> ConfirmationBlocker:
    """Return one establishment question in the review gate's own shape.

    Built with the gate's own id derivation rather than a second one, so an
    item raised here addresses identically to one raised by a deterministic
    check and an operator cannot meet two id schemes for one class of question.
    """
    reason = ConfirmationBlockReason.UNDETERMINED_ESTABLISHMENT
    return ConfirmationBlocker(
        blocker_id=blocker_id(reason=reason, field=field, detail=detail),
        reason=reason,
        field=field,
        detail=detail,
    )


def _filer_scope(
    profile_record: UserProfileRecord | None,
) -> tuple[IvaTerritorialScope | None, ConfirmationBlocker | None]:
    """Resolve the filer's own territory, or surface why it could not be.

    The resolver refuses rather than defaulting, and refusing is right: an
    incomplete profile is a setup gap. Its typed refusal propagates unchanged so
    the shared boundary retains the failed condition, evidence, and closed
    outcome rather than recasting a profile precondition as document-review text.
    """
    if profile_record is None:
        return None, _review_item(
            field=FILER_POSTCODE_FACT_PATH,
            detail=(
                "no taxpayer profile was resolvable, so the filer's own IVA territory could not be "
                f"established; it is a profile fact ({FILER_POSTCODE_FACT_PATH}) and is never read "
                "off an invoice"
            ),
        )
    return resolve_filer_territorial_scope(profile_record=profile_record), None


def _counterparty_review_items(
    counterparty: CounterpartyEstablishment,
    *,
    tax_identifier: str | None,
    field: str,
) -> tuple[ConfirmationBlocker, ...]:
    """Return the questions the ladder's outcome leaves for a person.

    Three outcomes reach a person and they are different questions, so they are
    not folded into one item. A contradiction is an operator's remembered claim
    against this document's printed one; a registration conflict is the issuer's
    own two statements disagreeing, which is the characteristic face of a
    foreign-registered entity established in Spain; an exhausted ladder is
    nobody disagreeing with anybody and simply nothing having been said.
    """
    naming = tax_identifier or "the counterparty (no identifier was printed)"
    if counterparty.contradiction is not None:
        return (_review_item(field=field, detail=f"{naming}: {counterparty.contradiction.detail}"),)
    if counterparty.registration_conflict is not None:
        return (_review_item(field=field, detail=f"{naming}: {counterparty.registration_conflict.detail}"),)
    if counterparty.established:
        return ()
    return (
        _review_item(
            field=field,
            detail=(
                f"{naming}: this document establishes no IVA territory for the counterparty. The "
                "country and postal evidence settled nothing and no confirmed fact is on record, so "
                "the territory is unknown rather than the mainland"
            ),
        ),
    )


def _resolved_supply_nature(
    *,
    supply_nature: SupplyNature | None,
    printed_citation: str | None,
    stated_category: DeclaredFact[IvaCategory] | None,
) -> DeclaredFact[SupplyNature] | None:
    """Resolve supply nature by operator, citation, then category authority."""
    if supply_nature is not None:
        return DeclaredFact(value=supply_nature, source=ClassifierInputSource.OPERATOR_ASSERTION)
    derivation = derive_supply_nature_from_citation(printed_citation=printed_citation)
    if derivation.outcome is SupplyNatureDerivationOutcome.DERIVED and derivation.nature is not None:
        return DeclaredFact(value=derivation.nature, source=ClassifierInputSource.DOCUMENT_EVIDENCE)
    category_derivation = supply_nature_implied_by_category(
        None if stated_category is None else stated_category.value,
    )
    if category_derivation.outcome is not SupplyNatureDerivationOutcome.DERIVED:
        return None
    if category_derivation.nature is None:
        return None
    return DeclaredFact(value=category_derivation.nature, source=ClassifierInputSource.DOCUMENT_EVIDENCE)


def _declared_facts(
    *,
    kind: InvoiceKind,
    counterparty: CounterpartyEstablishment,
    filer_scope: IvaTerritorialScope | None,
    stated_category: DeclaredFact[IvaCategory] | None,
    supply_nature: SupplyNature | None = None,
    printed_citation: str | None = None,
) -> DeclaredFacts:
    """Place each resolved fact on the party it belongs to, by direction.

    The draft is pre-direction data and the criteria are not: they name an
    issuer and a customer. On a RECEIVED document the counterparty issued it, so
    the ladder's answer is the issuer's territory and the profile's is the
    customer's; ISSUED is the mirror. Filling both slots from one resolution --
    or filling them in the printed order -- would place every operation inside a
    single territory, which classifies as domestic whatever the document said.

    The stated category takes no side: it is a fact about the OPERATION rather
    than about either party, so it rides the same channel without a direction
    swap.
    """
    counterparty_scope = counterparty.declared_fact
    counterparty_identification = (
        None
        if counterparty.identification_state is None
        else DeclaredFact(value=counterparty.identification_state, source=ClassifierInputSource.DOCUMENT_EVIDENCE)
    )
    filer = (
        None if filer_scope is None else DeclaredFact(value=filer_scope, source=ClassifierInputSource.PROFILE_AUTHORITY)
    )
    asserted_nature = _resolved_supply_nature(
        supply_nature=supply_nature,
        printed_citation=printed_citation,
        stated_category=stated_category,
    )
    if kind is InvoiceKind.RECEIVED:
        return DeclaredFacts(
            issuer_scope=counterparty_scope,
            customer_scope=filer,
            issuer_identification_state=counterparty_identification,
            stated_category=stated_category,
            supply_nature=asserted_nature,
        )
    return DeclaredFacts(
        issuer_scope=filer,
        customer_scope=counterparty_scope,
        customer_identification_state=counterparty_identification,
        stated_category=stated_category,
        supply_nature=asserted_nature,
    )


def _contradiction_item(resolution: IvaCategoryResolution) -> tuple[ConfirmationBlocker, ...]:
    """Return the review item a self-contradicting IVA declaration raises.

    Carried under the shipped ``CONTRADICTED_REGIME`` reason rather than a new
    one: that reason already names "the document's stated regime and the tax it
    charged cannot both be true", which is exactly this conflict. Declaring a
    second reason for it would give an operator two id schemes for one class of
    question.

    **"Carried" is the honest verb, and it is not "surfaced".** Every item on
    :attr:`ConfirmedEstablishment.review_items` reaches no operator: no
    production caller reads that field, and the confirm command's payload is
    built from the invoice, the draft and the confirmation id alone. So the
    conflict is constructed, attached, and seen by nobody.

    That is why the CATEGORY is withheld as well as the item raised. The
    withholding is the half that currently has teeth -- a contradicted document
    reaches the record with no treatment, which the decomposition contract
    refuses out loud -- while the explanatory item waits for a surface to read
    it. Were the item the only consequence, a contradiction would be silent.
    """
    if resolution.outcome is not IvaCategoryOutcome.CONTRADICTED:
        return ()
    reason = ConfirmationBlockReason.CONTRADICTED_REGIME
    return (
        ConfirmationBlocker(
            blocker_id=blocker_id(reason=reason, field="iva_category", detail=resolution.note),
            reason=reason,
            field="iva_category",
            detail=resolution.note,
        ),
    )


def resolve_confirmed_establishment(
    *,
    bucket_id: str,
    draft: InvoiceDraft,
    kind: InvoiceKind,
    invoice_date: date | None = None,
    rate_tier: IvaRateKind | None = None,
    supply_nature: SupplyNature | None = None,
    repository: ConfirmedCounterpartyFactsRepository | None = None,
) -> ConfirmedEstablishment:
    """Resolve both parties' territories for one confirm, and classify the operation.

    The confirm path's single call into the establishment and classification
    apparatus. Everything it reaches -- the ladder, the profile authority, the
    declared-facts channel, the criteria assembly and the rule table behind it
    -- had no production caller before this function, so this is the whole of
    what makes them reachable.

    Args:
        bucket_id: Active profile bucket, for the ladder's confirmed-fact rung.
        draft: The pre-direction reading of the document being confirmed.
        kind: Which side of the invoice the filer is on, as the operator settled
            it at confirm. Never the reader's suggestion, and never inferred
            here: it decides which party the ladder is even asked about.
        invoice_date: The operator's date override, when they supplied one. It
            layers over the printed date exactly as it does on every other
            field, and it must reach HERE rather than only the writer: the tier
            a rate belonged to changes by statute, so classifying against the
            printed date while the record is dated otherwise answers about a
            rate the supply was never charged at.
        rate_tier: The tier the document's lines charged, resolved by the
            reading stage. Reaches the criteria as the axis rule ``R05``
            consults, which is what makes the rule table -- rather than a
            second copy of its mapping -- produce a domestic category.
        supply_nature: The operator's own statement of whether the supply is
            goods or services, when they have made one. It is demanded only on
            the branches where the law forks on it -- cross-border and reverse
            charge -- and the ADR sanctions exactly two sources for the axis: a
            printed statutory citation, which decides by law, and this
            assertion. It enters stamped as an OPERATOR assertion so the
            classifier's inputs stay facts about who established them; a
            document citing art. 69 and an operator saying "services" are
            different kinds of claim and must not arrive looking alike.
        repository: Injected counterparty-fact store.

    Returns:
        :class:`ConfirmedEstablishment`: both territories where they resolved,
        the criteria or the inputs that stopped them, the resolved IVA category,
        and every question left for a person.
    """
    # Call-time imports: the side selector and the refusal type live in the
    # draft module, which imports this one's neighbours; the workflow reach is
    # deferred for the same reason the confirm path defers its own.
    from ..wizard import WizardStatusError, load_active_taxpayer_profile
    from cadrumo.application.workflow.persistence import workflow_state_repository
    from ._evidence_draft import counterparty_draft_side

    counterparty = resolve_draft_counterparty_establishment(
        bucket_id=bucket_id,
        draft=draft,
        kind=kind,
        repository=repository,
    )

    state = workflow_state_repository().load()
    filer_scope, filer_item = _filer_scope(state.active_profile_record())
    try:
        profile = load_active_taxpayer_profile(state)
    except WizardStatusError:
        profile = None

    declared = _declared_facts(
        kind=kind,
        counterparty=counterparty,
        filer_scope=filer_scope,
        # Read through the classification authority, never minted beside the
        # document reader: what a tax-category token means about the operation
        # is a classification question, and a reader answering it was a second
        # authority working from weaker evidence than the rule table.
        stated_category=declared_category_from_document_record(draft.iva_category),
        supply_nature=supply_nature,
        # The mention the reader already recovers, handed to the citation axis.
        # Both readers carry it -- the structured path reads it exactly from the
        # record, the model path transcribes it -- so wiring it here reaches
        # every lane rather than the one it was written for.
        printed_citation=draft.regime_legend,
    )
    assembly = assemble_classification_criteria(
        # The operator's override layers over the printed date, parsed through
        # the shipped date authority and never re-read here. An unparseable date
        # with no override is an ordinary outcome of reading a page, so it
        # arrives as ``None`` and the assembly reports it as a missing input
        # beside the others rather than aborting the confirm.
        transaction_date=invoice_date if invoice_date is not None else parse_iso8601_date(draft.invoice_date),
        direction=kind,
        inputs=collect_classifier_inputs(draft, profile=profile),
        declared=declared,
        rate_tier=rate_tier,
        # No printed country, postal code or identifier is handed through. Both
        # parties have already been resolved by the authority that owns them,
        # and the assembly's own derivation would answer the same questions a
        # second time -- reaching exactly the values the ladder refused.
    )
    side = counterparty_draft_side(draft, kind=kind)
    category = resolve_ingestion_iva_category(
        assembly,
        declared=declared,
        rate_tier=rate_tier,
        # The counterparty's own STATED code, classified by the shipped status
        # axis rather than re-derived. It spares a declared relief whose
        # establishment failed on OUR closed vocabulary rather than on the
        # document -- a well-formed code naming a jurisdiction the vocabulary
        # does not list is our gap, and refusing a real export over it is the
        # false positive that trains an operator to stop reading refusals.
        #
        # Asked of the record's own token, never of the resolved alpha-2 beside
        # it, and the sparing is unreachable from the other field. The resolved
        # field is populated only where the vocabulary PLACED the token, so it
        # is empty for exactly the codes this exemption exists for: reading it
        # handed the classifier `None` for `TH` and `THA` alike, which is the
        # same answer a document with no address block gives, and the guard
        # refused every legitimate Thai export while its own tests -- which
        # supply the status directly -- stayed green. The record token also
        # carries the alpha-3 spelling Facturae states, which the printed-value
        # status axis declines to judge at all.
        counterparty_country_status=record_country_code_status(side.stated_country_token),
        # Which party the counterparty IS, so the catalogue-gap exemption
        # forgives that party's residency and no other. The operator settled
        # this direction; it is never the reader's suggestion.
        direction=kind,
    )
    items = _counterparty_review_items(counterparty, tax_identifier=side.tax_id, field=side.tax_id_field)
    if filer_item is not None:
        items = (*items, filer_item)
    items = (*items, *_contradiction_item(category))

    return ConfirmedEstablishment(
        counterparty=counterparty,
        filer_scope=filer_scope,
        declared=declared,
        assembly=assembly,
        category=category,
        review_items=items,
    )
