"""Private rule-table probes and mappings used by classification assembly."""

from __future__ import annotations

from collections.abc import Callable

from ...domain.iva.classification import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaTerritorialScope,
    PartyFact,
    TransactionKind,
    domestic_rate_tier_is_required,
)
from ...domain.iva.schema import EUMemberState, IvaCategory
from ...domain.iva.supply_nature import SupplyNature

#: What a printed supply nature contributes to the table's kind axis.
#:
#: Only the general services member is reachable from printed evidence. The
#: specialised kinds — land-related, passenger transport, the reverse-charge
#: sub-kinds — each carry legal consequences a bare goods/services reading does
#: not establish, so none of them is inferred here. A document that needs one
#: gets it from an operator assertion, never from this map.
NATURE_TO_KIND: dict[SupplyNature, TransactionKind] = {
    SupplyNature.GOODS: TransactionKind.GOODS,
    SupplyNature.SERVICES: TransactionKind.SERVICES_GENERAL,
}


#: The kind supplied on a branch the law does not fork on, where the document
#: established no nature.
#:
#: Not a guess about the document, and it is only sound because the branch was
#: checked rather than assumed: the domestic rule consults ``kind`` ONLY to
#: exclude the three reverse-charge kinds, and neither value this module can
#: produce is in that set. So both reachable kinds yield the identical category,
#: which is then picked from the rate tier. A test proves that indifference by
#: classifying the same operation under both, rather than trusting this note.
NATURE_INDIFFERENT_KIND: TransactionKind = TransactionKind.GOODS


def counterparty_identification_field(direction: InvoiceKind) -> str:
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


def state_for_field(
    field: str,
    *,
    issuer: EUMemberState | None,
    customer: EUMemberState | None,
) -> EUMemberState | None:
    """Return the identification state carried by ``field``."""
    return issuer if field == "issuer_identification_state" else customer


def axis_forks_the_law(
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


def facts_consumed(
    probe: Callable[[CustomerTaxStatus, TransactionKind], frozenset[PartyFact]],
    *,
    status_candidates: tuple[CustomerTaxStatus, ...],
    kind_candidates: tuple[TransactionKind, ...],
) -> frozenset[PartyFact]:
    """Which party facts any branch this operation could reach actually turns on.

    The same extension of the same idea as :func:`axis_forks_the_law`, and
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
                return frozenset(PartyFact)
    return frozenset(consumed)


def domestic_rate_tier_is_reachable(
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
    kinds = (NATURE_TO_KIND[supply_nature],) if supply_nature is not None else tuple(NATURE_TO_KIND.values())
    return any(
        domestic_rate_tier_is_required(
            issuer_residency=issuer_scope,
            customer_residency=customer_scope,
            kind=kind,
            customer_tax_status=customer_tax_status,
        )
        for kind in kinds
    )
