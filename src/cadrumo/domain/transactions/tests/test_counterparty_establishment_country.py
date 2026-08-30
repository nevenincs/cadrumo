"""A ledger row must be able to say WHERE a counterparty is established.

The establishment fact on a transaction used to be an ``EUMemberState``, a set
closed over the Union. Such a field can record "established in Germany" and
cannot record "established in the United States", so the only representation a
third country ever had was the ABSENCE of a member state -- and absence is also
what an unrecorded establishment looks like, and what a typo looks like.

That collapse is what let a gate read "not recorded" as "outside the Union". On
the issued side outside the Union is export treatment, zero-rated, so a supply
could be exempted from a fact nobody had stated. Storing the country and
DERIVING the member state -- the shape :class:`~domain.invoices.Invoice` has
always used -- is what separates the four situations again.

These tests pin that separation. They assert on the country authority's own
verdicts rather than on a hand-written list of third countries, so a code moving
between the catalogues moves here with it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....tests.country_vocabulary_specimens import an_uncatalogued_alpha2
from ...iva import (
    EUMemberState,
    IvaTerritorialScope,
    StatedCountryCodeStatus,
    stated_country_code_status,
    territorial_scope_for_country,
)
from ..enums import TransactionDirection
from ..models import Transaction
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _transaction(*, counterparty_country: str | None) -> Transaction:
    return Transaction(
        raw=RawTransaction(
            provider_transaction_id="row-1",
            booked_date=date(2026, 4, 10),
            value_date=date(2026, 4, 10),
            amount=Decimal("100.00"),
            currency="EUR",
            counterparty="Acme Inc",
            description="Consultancy",
            provenance=RawProvenance(
                source_path=Path(__file__),
                source_sha256="a" * 64,
                source_row_index=1,
                source_format=SourceFormat.CSV,
                ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
                provider_name="CSV provider",
            ),
            raw_fields={},
        ),
        direction=TransactionDirection.INCOMING,
        source_jurisdiction=None,
        group_label=None,
        counterparty_country=counterparty_country,
    )


def test_a_third_country_establishment_is_recordable_at_all() -> None:
    """The capability the enum-typed field structurally lacked.

    Asserted against :func:`territorial_scope_for_country` rather than against
    the string ``"US"``, because the claim is not that the code round-trips --
    it is that the stored value RESOLVES to a third country, which is what a
    gate downstream has to be able to ask.
    """
    transaction = _transaction(counterparty_country="US")

    assert transaction.counterparty_country == "US"
    assert territorial_scope_for_country(transaction.counterparty_country) is IvaTerritorialScope.THIRD_COUNTRY


def test_the_member_state_is_derived_and_never_stored_twice() -> None:
    """One establishment fact, one home.

    Two stored copies of one fact can disagree, and the disagreement is silent.
    ``counterparty_eu_member_state`` is therefore a read-only projection: this
    asserts it derives correctly AND that it cannot be set independently.
    """
    assert _transaction(counterparty_country="DE").counterparty_eu_member_state is EUMemberState.DE
    assert _transaction(counterparty_country="US").counterparty_eu_member_state is None

    with pytest.raises(ValidationError):
        Transaction.model_validate(
            {
                **_transaction(counterparty_country="DE").model_dump(),
                "counterparty_eu_member_state": "fr",
            },
        )


@pytest.mark.parametrize(
    ("country", "scope", "status"),
    (
        ("DE", IvaTerritorialScope.EU_MEMBER, StatedCountryCodeStatus.CATALOGUED),
        ("US", IvaTerritorialScope.THIRD_COUNTRY, StatedCountryCodeStatus.CATALOGUED),
        ("XX", None, StatedCountryCodeStatus.UNASSIGNED),
        (an_uncatalogued_alpha2(), None, StatedCountryCodeStatus.UNCATALOGUED),
        (None, None, None),
    ),
)
def test_the_four_ways_a_row_can_fail_to_name_a_third_country_stay_distinct(
    country: str | None,
    scope: IvaTerritorialScope | None,
    status: StatedCountryCodeStatus | None,
) -> None:
    """Every one of these used to be the same value: ``None``.

    ``XX`` is a reserved ISO pair that denotes nothing by construction, so it is
    the operator's typo. The derived specimen is a REAL third country the bundled
    vocabulary does not carry, so it is this codebase's catalogue gap -- and it
    is the case that stops "does not resolve" from being read as "not a third
    country". Derived rather than named, because which country is outside the
    vocabulary changes as rows are written and the property is what is under
    test.
    ``None`` is an unrecorded fact. Only ``US`` may license export treatment.
    """
    transaction = _transaction(counterparty_country=country)

    assert transaction.counterparty_country == country
    assert territorial_scope_for_country(transaction.counterparty_country) is scope
    assert stated_country_code_status(transaction.counterparty_country) is status


@pytest.mark.parametrize("malformed", ("USA", "us", "1E", "U", ""))
def test_a_code_that_is_not_a_well_formed_alpha_2_pair_is_refused(malformed: str) -> None:
    """Shape is refused at construction; MEMBERSHIP deliberately is not.

    The uncatalogued case above proves why: a membership check here would make a
    genuine third country unrecordable the moment the bundled vocabulary lagged
    reality, which trades a silent wrong answer for a silent missing one.
    """
    with pytest.raises(ValidationError):
        _transaction(counterparty_country=malformed)


def test_the_stored_country_survives_a_strict_json_round_trip() -> None:
    """The fact must survive the persistence boundary, not just construction.

    A field that validates and then does not persist would leave the gate
    reading ``None`` again on every reload -- the same blank, one layer down.
    """
    original = _transaction(counterparty_country="US")

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.counterparty_country == "US"
    assert territorial_scope_for_country(restored.counterparty_country) is IvaTerritorialScope.THIRD_COUNTRY
