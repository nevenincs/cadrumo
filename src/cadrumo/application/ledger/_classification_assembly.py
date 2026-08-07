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

**Registration status needs VIES.** A printed VAT identifier establishes that
someone is acting as a taxable person, not that their number is registered and
valid — and the registered status is what triggers the intra-community supply
exemption. Inferring it from a printed number would zero-rate a taxable sale on
evidence nobody verified.

**Spanish territorial scope needs sub-national evidence.** A country code names
the State while the IVA territory inside it stays undetermined, and Spain holds
three that the law treats differently. So a domestic pair contributes nothing
here, and nothing may paper over that with a mainland default.

Both are settleable by an explicit operator assertion, which is the sanctioned
path until those authorities exist. An assertion is the operator's claim, made
knowingly; a default would be ours, made silently.

See Also:
    :func:`~domain.iva.classify_iva`
        The single rule table. This module produces its input and never
        duplicates its decisions.
    :class:`~application.ledger.ClassifierInputs`
        The evidence-and-profile facts this assembly draws on.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG, ClassifierInputSource, CounterpartyTaxablePersonStatus
from ...domain.iva import (
    CustomerTaxStatus,
    EUMemberState,
    IvaCategory,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    SupplyNature,
    TransactionKind,
    classify_iva,
    territorial_scope_for_country,
)

if TYPE_CHECKING:
    from datetime import date

    from ...domain.iva import InvoiceKind, IvaClassificationResult, IvaRateKind
    from ._classifier_inputs import ClassifierInputs

__all__ = [
    "ClassificationAssembly",
    "DeclaredFact",
    "DeclaredFacts",
    "MissingClassifierInput",
    "assemble_classification_criteria",
    "classify_from_assembled_criteria",
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


def _customer_tax_status(
    inputs: ClassifierInputs,
    asserted: CustomerTaxStatus | None,
) -> tuple[CustomerTaxStatus | None, MissingClassifierInput | None]:
    """Resolve the customer's IVA status, or say why the evidence cannot.

    The printed identifier is deliberately NOT consulted as a source of the
    registered status. It establishes a taxable person; ``B2B_IVA_REGISTERED``
    asserts a *valid* registration and is the trigger for the intra-community
    supply exemption, so bridging the two would let an unverified number
    zero-rate a taxable sale.
    """
    if asserted is not None:
        return asserted, None
    established = inputs.counterparty_taxable_person
    reason = (
        "the document printed a counterparty tax identifier, which establishes a taxable person "
        "but not a valid registration"
        if established is CounterpartyTaxablePersonStatus.TAXABLE_PERSON
        else "the document printed no counterparty tax identifier, so nothing was established"
    )
    return None, MissingClassifierInput(
        field="customer_tax_status",
        reason=reason,
        settled_by="a VIES verification, or an explicit operator assertion of the customer's IVA status",
    )


def _scope(
    country_code: str | None,
    *,
    field: str,
    asserted: IvaTerritorialScope | None,
) -> tuple[IvaTerritorialScope | None, MissingClassifierInput | None]:
    """Resolve one party's territorial scope from its printed country code."""
    if asserted is not None:
        return asserted, None
    resolved = territorial_scope_for_country(country_code)
    if resolved is not None:
        return resolved, None
    reason = (
        f"the printed country code {country_code!r} names Spain, whose three IVA territories are "
        "treated differently by law and cannot be told apart from a country code"
        if country_code
        else "no country code was established for this party"
    )
    return None, MissingClassifierInput(
        field=field,
        reason=reason,
        settled_by="sub-national establishment evidence, or an explicit operator assertion of the territory",
    )


def _member_state(
    country_code: str | None,
    *,
    scope: IvaTerritorialScope | None,
    field: str,
) -> tuple[EUMemberState | None, MissingClassifierInput | None]:
    """Resolve which Member State a party is in, when the table requires it.

    Only asked when the scope is EU_MEMBER: the criteria model requires the
    State there and forbids inventing one anywhere else. A scope that arrived by
    operator assertion carries no country code with it, so the State it implies
    has to be established too rather than assumed from the assertion.
    """
    if scope is not IvaTerritorialScope.EU_MEMBER:
        return None, None
    # The enum's tokens are lower-case while a document prints the code however
    # it likes, so the case is folded here rather than assumed either way.
    normalised = (country_code or "").strip().lower()
    try:
        return EUMemberState(normalised), None
    except ValueError:
        return None, MissingClassifierInput(
            field=field,
            reason=(
                f"the party is established in the EU but the printed country code {country_code!r} "
                "does not name a Member State the rate schedule carries"
            ),
            settled_by="a printed country code naming the Member State, or an explicit operator assertion",
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


def _nature_forks_the_law(probe: Callable[[TransactionKind], IvaCategory]) -> bool:
    """Whether the supply's nature can change THIS operation's treatment.

    Asks the rule table about itself: classify the same operation under each
    kind a printed nature can produce and compare the verdicts. Identical
    verdicts mean the answer could not have mattered, so demanding it would ask
    the operator a question with no consequence — which is what put a blocking
    gap on every domestic invoice.

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

    Fails toward asking: a probe that cannot classify at all forks, because an
    operation that could not be placed may still land on a branch needing the
    answer.
    """
    try:
        verdicts = {probe(kind) for kind in _NATURE_TO_KIND.values()}
    except Exception:  # reason: an unclassifiable probe is not evidence of indifference.
        return True
    return len(verdicts) > 1


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
            :class:`~application.ledger.ClassifierInputFact` to the stamp. A
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
        issuer_scope: The issuer's territory, where a country code cannot
            settle it.
        customer_scope: The customer's territory, on the same terms.
    """

    model_config = STRICT_FROZEN_CONFIG

    supply_nature: DeclaredFact[SupplyNature] | None = None
    customer_tax_status: DeclaredFact[CustomerTaxStatus] | None = None
    issuer_scope: DeclaredFact[IvaTerritorialScope] | None = None
    customer_scope: DeclaredFact[IvaTerritorialScope] | None = None


def _value_of[T](fact: DeclaredFact[T] | None) -> T | None:
    """Return a declared fact's value, or ``None`` when nobody declared it."""
    return None if fact is None else fact.value


def assemble_classification_criteria(
    *,
    transaction_date: date | None,
    direction: InvoiceKind,
    inputs: ClassifierInputs,
    declared: DeclaredFacts,
    issuer_country_code: str | None = None,
    customer_country_code: str | None = None,
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
        rate_tier: The rate tier, required by the criteria model for ES-to-ES
            domestic operations.

    Returns:
        :class:`ClassificationAssembly`: the criteria, or the missing inputs.
    """
    missing: list[MissingClassifierInput] = []

    supply_nature = _value_of(declared.supply_nature)

    status, status_gap = _customer_tax_status(inputs, _value_of(declared.customer_tax_status))
    if status_gap is not None:
        missing.append(status_gap)

    issuer_scope, issuer_gap = _scope(
        issuer_country_code,
        field="issuer_residency",
        asserted=_value_of(declared.issuer_scope),
    )
    if issuer_gap is not None:
        missing.append(issuer_gap)

    customer_scope, customer_gap = _scope(
        customer_country_code,
        field="customer_residency",
        asserted=_value_of(declared.customer_scope),
    )
    if customer_gap is not None:
        missing.append(customer_gap)

    issuer_state, issuer_state_gap = _member_state(
        issuer_country_code,
        scope=issuer_scope,
        field="issuer_member_state",
    )
    if issuer_state_gap is not None:
        missing.append(issuer_state_gap)

    customer_state, customer_state_gap = _member_state(
        customer_country_code,
        scope=customer_scope,
        field="customer_member_state",
    )
    if customer_state_gap is not None:
        missing.append(customer_state_gap)

    if transaction_date is None:
        missing.append(
            MissingClassifierInput(
                field="transaction_date",
                reason="no invoice date was established",
                settled_by="the printed invoice date, or an explicit operator assertion",
            ),
        )

    if missing:
        # The probe needs otherwise-complete criteria, and this operation does
        # not have them -- so the nature question cannot be decided here. It is
        # still REPORTED, because failing toward asking is the rule and because
        # dropping it would cost the accumulate-at-once property: an operator
        # resolving the other gaps would re-run only to meet a new one.
        if supply_nature is None:
            missing.append(
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
        return ClassificationAssembly(missing=tuple(missing))

    assert status is not None  # narrowed: a gap would have been recorded
    assert issuer_scope is not None
    assert customer_scope is not None
    assert transaction_date is not None

    def _probe(kind: TransactionKind) -> IvaCategory:
        return classify_iva(
            IvaInvoiceClassificationCriteria(
                transaction_date=transaction_date,
                issuer_residency=issuer_scope,
                customer_residency=customer_scope,
                customer_tax_status=status,
                kind=kind,
                direction=direction,
                issuer_member_state=issuer_state,
                customer_member_state=customer_state,
                rate_tier=rate_tier,
            ),
        ).category

    if supply_nature is None and _nature_forks_the_law(_probe):
        return ClassificationAssembly(
            missing=(
                MissingClassifierInput(
                    field="kind",
                    reason=(
                        "no statutory citation on the document established whether it supplies goods "
                        "or services, and this operation's treatment differs between them"
                    ),
                    settled_by="a printed statutory citation, or an explicit operator assertion of the supply nature",
                ),
            ),
        )

    return ClassificationAssembly(
        criteria=IvaInvoiceClassificationCriteria(
            transaction_date=transaction_date,
            issuer_residency=issuer_scope,
            customer_residency=customer_scope,
            customer_tax_status=status,
            kind=_NATURE_TO_KIND[supply_nature] if supply_nature is not None else _NATURE_INDIFFERENT_KIND,
            direction=direction,
            issuer_member_state=issuer_state,
            customer_member_state=customer_state,
            rate_tier=rate_tier,
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
    from ...domain.iva import classify_iva

    if assembly.criteria is None:
        return None
    return classify_iva(assembly.criteria)
