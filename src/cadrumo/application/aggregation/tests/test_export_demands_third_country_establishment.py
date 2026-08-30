"""An export must be PLACED outside the Union, not merely fail to be placed inside it.

Ley 37/1992 art. 21 exempts an export because the operation leaves the
Community, so the exemption turns on where the counterparty IS. The gate used
to fire only when an EU member state was recorded, which made absence of a
member state the sole evidence of third-country establishment -- and absence
was also what an unrecorded establishment and a typo looked like, because the
field could not represent a third country at all.

The error direction is UNDER-declaration on the issued side: a supply nobody
had placed anywhere was zero-rated. Nothing downstream objected, because a
zero-rated export legitimately carries no cuota.

Two things this must NOT become, both tested here as controls:

* A refusal of legitimate exports. A genuine third-country counterparty must
  still classify, and so must one that happens to hold an EU IVA number -- art.
  21 exempts on the goods leaving, never on the acquirer's registrations.
* A refusal driven by OUR data gaps. A well-formed code naming a real country
  the bundled vocabulary has not catalogued is spared, on the same authority
  and for the same reason the ingestion path's declared-relief guard spares it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.iva import EUMemberState, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.country_vocabulary_specimens import an_uncatalogued_alpha2
from .._iva_ledger import (
    IVA_LEDGER_COUNTERPARTY_GATE_REASONS,
    IvaLedgerAggregationIssueReason,
    validate_iva_ledger_counterparty_category,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EXPORT_FAMILIES = (
    IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
    IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
)


def _row(
    *,
    category: IvaCategory,
    counterparty_country: str | None,
    identification_state: EUMemberState | None = None,
) -> Transaction:
    return Transaction(
        raw=RawTransaction(
            provider_transaction_id="export-row",
            booked_date=date(2026, 5, 12),
            value_date=date(2026, 5, 12),
            amount=Decimal("2500.00"),
            currency="EUR",
            counterparty="Acme Inc",
            description="Consultancy export",
            provenance=RawProvenance(
                source_path=Path(__file__),
                source_sha256="c" * 64,
                source_row_index=1,
                source_format=SourceFormat.CSV,
                ingested_at=datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
                provider_name="CSV provider",
            ),
            raw_fields={},
        ),
        direction=TransactionDirection.INCOMING,
        business_classification=BusinessClassification.BUSINESS,
        taxable_base=Decimal("2500.00"),
        iva_rate=Decimal("0.00"),
        iva_amount=Decimal("0.00"),
        iva_category=category,
        counterparty_country=counterparty_country,
        counterparty_identification_state=identification_state,
        source_jurisdiction=None,
        group_label=None,
    )


@pytest.mark.parametrize("category", _EXPORT_FAMILIES)
def test_an_export_placing_the_counterparty_nowhere_is_refused(category: IvaCategory) -> None:
    """The defect itself: no establishment recorded, and the supply zero-rated anyway."""
    issue = validate_iva_ledger_counterparty_category(_row(category=category, counterparty_country=None))

    assert issue is not None, "an unplaced counterparty was granted export relief"
    assert issue.reason is IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT


@pytest.mark.parametrize("category", _EXPORT_FAMILIES)
@pytest.mark.parametrize("unassigned", ("XX", "ZZ", "QQ"))
def test_an_iso_unassigned_code_establishes_nothing(category: IvaCategory, unassigned: str) -> None:
    """These pairs denote no country BY CONSTRUCTION, so they cannot place a party.

    They are the shapes a placeholder, a truncated field or a slipped keystroke
    actually takes. Before the country was stored they were unreachable here --
    the member-state field could not hold them -- and they arrived as the same
    blank a genuine export produced.
    """
    issue = validate_iva_ledger_counterparty_category(_row(category=category, counterparty_country=unassigned))

    assert issue is not None, f"{unassigned} placed a counterparty outside the Union"
    assert issue.reason is IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT


@pytest.mark.parametrize("category", _EXPORT_FAMILIES)
def test_a_genuine_third_country_export_still_classifies(category: IvaCategory) -> None:
    """The control that stops this fix from becoming the opposite defect.

    Nothing in this apparatus watches over-payment, so a guard that refused
    legitimate exports would produce valid output, no refusal, and no signal to
    the taxpayer.
    """
    assert validate_iva_ledger_counterparty_category(_row(category=category, counterparty_country="US")) is None


@pytest.mark.parametrize("category", _EXPORT_FAMILIES)
def test_an_eu_iva_number_does_not_disqualify_a_third_country_export(category: IvaCategory) -> None:
    """Establishment decides an export; registration does not.

    A US-established company can hold an Irish IVA number, and art. 21 exempts
    on the goods leaving the Community rather than on who IVA-identifies the
    acquirer. Reading identification here would be the same
    identification-for-establishment substitution the intra-community branch
    exists to prevent, run in the opposite direction.
    """
    row = _row(category=category, counterparty_country="US", identification_state=EUMemberState.IE)

    assert validate_iva_ledger_counterparty_category(row) is None


@pytest.mark.parametrize("category", _EXPORT_FAMILIES)
def test_a_country_our_own_vocabulary_omits_is_spared(category: IvaCategory) -> None:
    """The carve-out that separates a guard from a trap.

    The specimen is a real third country the bundled vocabulary does not carry,
    so it resolves to no scope. Refusing there would reject a legitimate export
    over a row nobody has written yet -- a false positive that teaches an
    operator to skip refusals, which costs more than the case it catches.

    It is DERIVED rather than named, so the case follows the vocabulary's
    boundary rather than reddening the day that country is admitted, which would
    report a fixture change as a behaviour change.
    """
    row = _row(category=category, counterparty_country=an_uncatalogued_alpha2())

    assert validate_iva_ledger_counterparty_category(row) is None


@pytest.mark.parametrize("category", _EXPORT_FAMILIES)
def test_an_eu_established_counterparty_keeps_its_own_refusal(category: IvaCategory) -> None:
    """The pre-existing rule must keep firing, and under its OWN reason.

    A wrong place and no place are different operator problems: one says the
    category is wrong, the other says a fact is missing. Collapsing them would
    send half the population to correct the wrong thing.
    """
    issue = validate_iva_ledger_counterparty_category(_row(category=category, counterparty_country="DE"))

    assert issue is not None
    assert issue.reason is IvaLedgerAggregationIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION


def test_the_intra_community_branch_is_untouched_by_the_export_rule() -> None:
    """Establishment must not leak into the identification-keyed branch.

    Art. 25 exempts on the acquirer's IVA identification in another Member
    State and says nothing about its sede, so recording a country must neither
    satisfy nor break that branch.
    """
    unidentified = _row(category=IvaCategory.INTRA_COMMUNITY_SUPPLY, counterparty_country="US")
    issue = validate_iva_ledger_counterparty_category(unidentified)

    assert issue is not None, "a country was accepted in place of an IVA identification"
    assert issue.reason is IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE

    identified = _row(
        category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        counterparty_country=None,
        identification_state=EUMemberState.DE,
    )
    assert validate_iva_ledger_counterparty_category(identified) is None


def test_the_declared_emission_set_matches_what_the_gate_actually_emits() -> None:
    """The declared set is pinned to behaviour, not trusted.

    A reason declared but unreachable, or emitted but undeclared, would break
    the preflight totality partition that keys operator messages off this set.
    """
    observed: set[IvaLedgerAggregationIssueReason] = set()
    probes = (
        (IvaCategory.INTRA_COMMUNITY_SUPPLY, None, None),
        (IvaCategory.INTRA_COMMUNITY_SUPPLY, None, EUMemberState.ES),
        (IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED, "DE", None),
        (IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED, None, None),
    )
    for category, country, identification in probes:
        issue = validate_iva_ledger_counterparty_category(
            _row(category=category, counterparty_country=country, identification_state=identification),
        )
        if issue is not None:
            observed.add(issue.reason)

    assert observed == IVA_LEDGER_COUNTERPARTY_GATE_REASONS
