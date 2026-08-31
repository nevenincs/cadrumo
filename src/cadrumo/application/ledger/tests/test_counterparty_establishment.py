"""Ask once per counterparty, never default a territory, never overwrite silently.

Three properties this store exists for, and each is tested against the real
encrypted boundary rather than an in-memory stand-in:

**Absence is never a territory.** The mainland is the majority population, so a
default there passes every fixture an author with mainland examples would write,
while silently placing Canarian and Ceutan parties inside a territory their
operations are not subject to. The sweep below ranges over the whole
:class:`~domain.iva.IvaTerritorialScope` enum rather than spot-checking the
mainland, so a default introduced at any member is caught.

**One entity, one record, however the page spells the identifier.** The
confirmation is remembered against the canonical identifier, so the same
supplier printing ``ESB-1234567-4`` next month is answered rather than asked
again -- which is the whole reason an honest refusal on the domestic population
is affordable.

**Disagreement is surfaced, never resolved by preference.** A confirmed-Canarian
counterparty printing a French country code is a real signal. Preferring the
stored value hides a changed establishment; preferring the page imports the
issuer's error as authority. The resolution carries both and no fact.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.classifier_input_source import ClassifierInputSource
from ....domain.iva.classification import IvaTerritorialScope, classify_iva
from ..classification_assembly import (
    DeclaredFact,
    DeclaredFacts,
    assemble_classification_criteria,
)
from ..classifier_inputs import ClassifierInputs
from ..counterparty_establishment import (
    ConfirmedCounterpartyFacts,
    ConfirmedCounterpartyFactsInputError,
    ConfirmedCounterpartyFactsRepository,
    CounterpartyEstablishmentConflictError,
    confirmed_counterparty_facts_key,
    forget_confirmed_counterparty_facts,
    record_confirmed_counterparty_facts,
    resolve_confirmed_counterparty_facts,
)
from ._counterparty_fact_fixtures import runtime_profile
from ._ledger_value_fixtures import repository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["repository", "runtime_profile"]

_BUCKET_ID = "36363636-3636-4636-8636-363636363636"
_SUPPLIER_CIF = "B12345674"
_OTHER_CIF = "B87654321"
_ASSERTED_AT = datetime(2026, 4, 17, 11, 5, tzinfo=UTC)


def _confirm(
    repository: ConfirmedCounterpartyFactsRepository,
    *,
    tax_identifier: str = _SUPPLIER_CIF,
    scope: IvaTerritorialScope = IvaTerritorialScope.ES_CANARIAS,
    note: str = "",
) -> ConfirmedCounterpartyFacts:
    return record_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=tax_identifier,
        territorial_scope=scope,
        asserted_by="operator@example.test",
        note=note,
        asserted_at=_ASSERTED_AT,
        repository=repository,
    )


# --------------------------------------------------------------------------
# Absence is never a territory
# --------------------------------------------------------------------------


@pytest.mark.parametrize("scope", list(IvaTerritorialScope))
def test_an_empty_store_never_answers_with_any_territory(
    repository: ConfirmedCounterpartyFactsRepository,
    scope: IvaTerritorialScope,
) -> None:
    """No member of the enum is reachable from an empty store.

    Parameterised over the WHOLE enum rather than asserting "not mainland".
    Spot-checking the mainland would leave a default at any other member
    invisible, and the sweep joins a new member on the day it is declared rather
    than on the day someone remembers this test.
    """
    resolution = resolve_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        repository=repository,
    )

    assert resolution.fact is None
    assert resolution.contradiction is None
    assert resolution.fact is None or resolution.fact.value is not scope


def test_the_bare_cif_domestic_invoice_resolves_to_nothing(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """The commonest ingested document, and it must produce no territory at all.

    A bare ``B``-CIF, no printed country, no gated postal evidence: the exact
    shape the ladder was ruled for. Nothing here may resolve to the mainland,
    and nothing may resolve to anything else either.
    """
    resolution = resolve_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        country_code=None,
        evidenced_scope=None,
        repository=repository,
    )

    assert resolution.fact is None
    assert resolution.contradiction is None
    assert not resolution.contradicted


def test_a_document_printing_no_identifier_resolves_to_nothing(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """No identifier means no entity to have remembered anything about."""
    _confirm(repository)

    for absent in (None, "", "   "):
        resolution = resolve_confirmed_counterparty_facts(
            bucket_id=_BUCKET_ID,
            tax_identifier=absent,
            repository=repository,
        )
        assert resolution.fact is None, absent
        assert resolution.contradiction is None, absent


def test_an_unverifiable_identifier_has_no_key_and_finds_nothing(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """A reading that does not verify addresses no record, in either direction.

    No fallback key is derived from the raw string: two different misreadings of
    one page would collide under it and share one entity's territory with
    another.
    """
    assert confirmed_counterparty_facts_key("B99999999") is None
    # The bare body, genuinely without its prefix. This assertion previously
    # named that property while passing `DE123456789`, which CARRIES its prefix
    # -- so it locked in the absent-country-means-Spain default it was written
    # to describe, and read as protection while doing the opposite.
    assert confirmed_counterparty_facts_key("123456789") is None, "a foreign number without its prefix is not one"

    resolution = resolve_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier="B99999999",
        repository=repository,
    )
    assert resolution.fact is None

    with pytest.raises(ConfirmedCounterpartyFactsInputError) as raised:
        _confirm(repository, tax_identifier="B99999999")
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "ledger.counterparty.identifier_valid"
    assert verdict.action is None
    assert verdict.no_recovery_outcome == "operator_decision"


def test_a_prefixed_foreign_identifier_addresses_a_record_without_a_stated_country(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """An intra-community IVA number states its own country, so it has an identity.

    The population this whole apparatus exists for. While an absent country
    defaulted to Spain, a foreign counterparty printing a prefixed IVA number
    and no address block got no key at all -- so the operator's answer to "where
    is this party established" could be neither stored nor retrieved, and the
    ladder's remembered-fact rung was unreachable for them.

    Asserted through the key AND through a real store round trip, because the
    key alone would pass against a repository that still refused the fact. The
    Spanish control below is what keeps this from being read as "any string now
    verifies".
    """
    key = confirmed_counterparty_facts_key("SE556677889901")
    assert key is not None
    assert key == confirmed_counterparty_facts_key("SE 556677889901"), "separators are not identity"

    stored = _confirm(repository, tax_identifier="SE556677889901", scope=IvaTerritorialScope.EU_MEMBER)
    assert stored.counterparty_key == key
    resolution = resolve_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier="SE556677889901",
        repository=repository,
    )
    assert resolution.fact is not None
    assert resolution.fact.value is IvaTerritorialScope.EU_MEMBER

    # A country the caller SUPPLIES still decides, so a stated country that
    # disagrees with the printed prefix stays a refusal rather than being
    # silently resolved in the prefix's favour.
    assert confirmed_counterparty_facts_key("SE556677889901", country_code="ES") is None


# --------------------------------------------------------------------------
# One entity, one record
# --------------------------------------------------------------------------


@pytest.mark.parametrize("printed", ["B12345674", "ESB12345674", "B-1234567-4", "  b12345674 "])
def test_every_printed_spelling_of_one_identifier_finds_the_one_record(
    repository: ConfirmedCounterpartyFactsRepository,
    printed: str,
) -> None:
    """The confirmation is remembered against the entity, not against a string.

    This is what bounds the operator's cost to one question per counterparty: a
    supplier whose next invoice prints the prefixed or hyphenated form must be
    answered from the store rather than asked again.
    """
    _confirm(repository)

    resolution = resolve_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=printed,
        repository=repository,
    )

    assert resolution.fact is not None
    assert resolution.fact.value is IvaTerritorialScope.ES_CANARIAS


def test_a_different_counterparty_is_not_answered_by_this_one(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """A fact confirmed about one entity must not leak onto another."""
    _confirm(repository)

    resolution = resolve_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_OTHER_CIF,
        repository=repository,
    )

    assert resolution.fact is None


def test_the_remembered_fact_is_attributed_to_the_operator(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """A classification standing on this must record that a person said so.

    Not the document: the fact exists precisely because the document did not
    state it, and an envelope claiming otherwise would send an auditor to a page
    that never carried the answer.
    """
    stored = _confirm(repository)

    assert stored.source is ClassifierInputSource.OPERATOR_ASSERTION
    resolution = resolve_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        repository=repository,
    )
    assert resolution.fact is not None
    assert resolution.fact.source is ClassifierInputSource.OPERATOR_ASSERTION


def test_a_document_sourced_fact_is_refused_by_the_model() -> None:
    """The store is not a cache of page readings.

    A remembered document reading would answer later documents as though an
    operator had confirmed it, which takes the contradiction channel offline for
    the population it protects.
    """
    with pytest.raises(ValueError, match="confirmed by an operator"):
        ConfirmedCounterpartyFacts(
            counterparty_key="a" * 64,
            canonical_tax_identifier=_SUPPLIER_CIF,
            territorial_scope=IvaTerritorialScope.ES_CANARIAS,
            source=ClassifierInputSource.DOCUMENT_EVIDENCE,
            asserted_by="operator@example.test",
            asserted_at=_ASSERTED_AT,
        )


# --------------------------------------------------------------------------
# Disagreement, and the write contract
# --------------------------------------------------------------------------


def test_agreeing_printed_evidence_corroborates_rather_than_contradicts(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """Evidence matching the confirmed fact leaves the fact usable."""
    _confirm(repository)

    resolution = resolve_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        evidenced_scope=IvaTerritorialScope.ES_CANARIAS,
        repository=repository,
    )

    assert resolution.contradiction is None
    assert resolution.fact is not None
    assert resolution.fact.value is IvaTerritorialScope.ES_CANARIAS


def test_disagreeing_printed_evidence_yields_a_contradiction_and_no_fact(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """Neither side wins, and the caller is left nothing to proceed on.

    Preferring the stored value would hide an establishment that moved;
    preferring the page would import a misprinting issuer's claim as authority.
    Both figures are carried and the fact is withheld, so a consumer reading
    ``fact`` cannot act on a value the evidence disputes.
    """
    _confirm(repository)

    resolution = resolve_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        evidenced_scope=IvaTerritorialScope.EU_MEMBER,
        repository=repository,
    )

    assert resolution.contradicted
    assert resolution.fact is None
    contradiction = resolution.contradiction
    assert contradiction is not None
    assert contradiction.confirmed_scope is IvaTerritorialScope.ES_CANARIAS
    assert contradiction.evidenced_scope is IvaTerritorialScope.EU_MEMBER
    assert contradiction.canonical_tax_identifier == _SUPPLIER_CIF
    assert IvaTerritorialScope.ES_CANARIAS.value in contradiction.detail
    assert IvaTerritorialScope.EU_MEMBER.value in contradiction.detail


def test_reconfirming_the_same_territory_is_a_no_op(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """A retry returns the stored record, unre-stamped.

    Re-stamping ``asserted_at`` would make a repeated call look like a fresh
    confirmation, which is exactly what an audit of "when did we decide this"
    must not be told.
    """
    first = _confirm(repository, note="confirmed by telephone")
    again = record_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier="ESB-1234567-4",
        territorial_scope=IvaTerritorialScope.ES_CANARIAS,
        asserted_by="someone-else@example.test",
        note="confirmed by telephone",
        asserted_at=datetime(2026, 9, 1, tzinfo=UTC),
        repository=repository,
    )

    assert again == first
    assert again.asserted_at == _ASSERTED_AT
    assert again.asserted_by == "operator@example.test"


def test_asserting_a_different_territory_refuses_rather_than_overwriting(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """A silent overwrite would reclassify every invoice already derived under the old answer."""
    _confirm(repository)

    with pytest.raises(CounterpartyEstablishmentConflictError) as raised:
        _confirm(repository, scope=IvaTerritorialScope.ES_MAINLAND)

    message = str(raised.value)
    assert IvaTerritorialScope.ES_CANARIAS.value in message
    assert IvaTerritorialScope.ES_MAINLAND.value in message

    resolution = resolve_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        repository=repository,
    )
    assert resolution.fact is not None
    assert resolution.fact.value is IvaTerritorialScope.ES_CANARIAS


def test_withdrawing_a_fact_is_the_route_to_correcting_one(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """Correction is a deliberate two-step, so retracting an answer is visible."""
    _confirm(repository)

    assert forget_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        repository=repository,
    )
    assert (
        resolve_confirmed_counterparty_facts(
            bucket_id=_BUCKET_ID,
            tax_identifier=_SUPPLIER_CIF,
            repository=repository,
        ).fact
        is None
    )

    corrected = _confirm(repository, scope=IvaTerritorialScope.ES_MAINLAND)
    assert corrected.territorial_scope is IvaTerritorialScope.ES_MAINLAND

    assert not forget_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_OTHER_CIF,
        repository=repository,
    )


# --------------------------------------------------------------------------
# What the fact is FOR
# --------------------------------------------------------------------------


def test_the_remembered_fact_unblocks_the_criteria_assembly(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """The pair that shows the row's purpose: blocked without it, derived with it.

    A received invoice from a supplier whose paper is non-decisive. The
    taxpayer's own side is a profile fact, so the only open axis is the
    counterparty's. Without the remembered confirmation the assembly reports
    ``issuer_residency`` missing; with it the rule table derives, and the
    category it derives is ``DOMESTIC_NOT_SUBJECT`` -- the Canarian outcome a
    mainland default would have replaced with a subject-to-IVA one.
    """
    from datetime import date

    from ....domain.iva.classification import InvoiceKind
    from ....domain.iva.schema import IvaCategory

    filer_side = DeclaredFact[IvaTerritorialScope](
        value=IvaTerritorialScope.ES_MAINLAND,
        source=ClassifierInputSource.PROFILE_AUTHORITY,
    )

    blocked = assemble_classification_criteria(
        transaction_date=date(2026, 3, 10),
        direction=InvoiceKind.RECEIVED,
        inputs=ClassifierInputs(),
        declared=DeclaredFacts(
            customer_scope=filer_side,
            issuer_scope=resolve_confirmed_counterparty_facts(
                bucket_id=_BUCKET_ID,
                tax_identifier=_SUPPLIER_CIF,
                repository=repository,
            ).fact,
        ),
    )
    assert not blocked.assembled
    assert "issuer_residency" in {gap.field for gap in blocked.missing}

    _confirm(repository)

    remembered = resolve_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        repository=repository,
    ).fact
    assert remembered is not None

    derived = assemble_classification_criteria(
        transaction_date=date(2026, 3, 10),
        direction=InvoiceKind.RECEIVED,
        inputs=ClassifierInputs(),
        declared=DeclaredFacts(customer_scope=filer_side, issuer_scope=remembered),
    )
    assert derived.assembled, [gap.field for gap in derived.missing]
    assert derived.criteria is not None
    assert derived.criteria.issuer_residency is IvaTerritorialScope.ES_CANARIAS
    assert classify_iva(derived.criteria).category is IvaCategory.DOMESTIC_NOT_SUBJECT
