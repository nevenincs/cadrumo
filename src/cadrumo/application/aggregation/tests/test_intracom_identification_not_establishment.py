"""The art. 25 gate reads IVA identification, never country of establishment.

Ley 37/1992 art. 25.Uno exempts an intra-community supply on the acquirer
holding an IVA identification assigned by ANOTHER Member State. It says nothing
about where that acquirer is established, which arts. 69-70 govern. The two
facts diverge in both directions and both divergences land in money:

- A Spanish-established acquirer holding a German IVA number is an
  intra-community acquirer. Keyed on establishment it was refused an exemption
  art. 25 grants -- Spanish IVA charged on an exempt supply, OVER-declaration.
- A German-established acquirer purchasing under a Spanish NIF-IVA is not.
  Keyed on establishment its domestic supply was zero-rated -- silent
  UNDER-declaration.

The two are asserted in ONE test deliberately. Either alone is satisfiable by
tightening the wrong side: a gate that simply demanded a non-ES establishment
passes the second case while still failing the first, and a gate that accepted
any EU establishment passes the first while still failing the second. Only the
pair pins the fact the exemption actually turns on.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.ledger_iva_bindings import resolve_ledger_iva_aggregation_binding_values
from ....domain.iva.schema import EUMemberState, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .. import IvaLedgerAggregationIssueReason
from .._iva_ledger import IvaLedgerAggregation
from .iva_authority_support import aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERIOD = Period.from_year_and_code(2026, "2T")
_CASILLA_59_BASE: BindingId = "modelo-303-casilla-59-entregas-intracomunitarias-base"


@cache
def _modelo_303_revision():
    return bundled_authority().snapshot("303", filing_year=2025, period="1T").revision


def _casilla_59(aggregation: IvaLedgerAggregation) -> Decimal:
    resolved = resolve_ledger_iva_aggregation_binding_values(_modelo_303_revision(), aggregation.observations)
    return resolved.get(_CASILLA_59_BASE, Decimal("0"))


def _raw(provider_id: str) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 4, 15),
        value_date=date(2026, 4, 15),
        amount=Decimal("5000.00"),
        currency="EUR",
        counterparty="Acquirer",
        description=f"art25 {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 16, 9, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _intracom_supply(
    provider_id: str,
    *,
    established_in: EUMemberState | None,
    identified_in: EUMemberState | None,
) -> Transaction:
    """An intra-community goods supply whose two counterparty facts are set independently."""
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("5000.00"),
            "iva_rate": Decimal("0"),
            "iva_amount": Decimal("0"),
            "iva_category": IvaCategory.INTRA_COMMUNITY_SUPPLY,
            "counterparty_country": (established_in.value.upper() if established_in is not None else None),
            "counterparty_identification_state": identified_in,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
        },
    )


def _aggregate(transaction: Transaction):
    return aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions([transaction]),
        period=_PERIOD,
    )


def test_art25_turns_on_identification_in_both_directions() -> None:
    """The paired proof: identification decides the exemption, establishment does not.

    Both rows carry the SAME taxable base and differ only in which of the two
    counterparty facts names Spain. If the gate read establishment, each
    assertion below would hold the opposite value.
    """
    # Established in Spain, IVA-identified in Germany. Art. 25 exempts this.
    spanish_established_german_identified = _aggregate(
        _intracom_supply(
            "es-established-de-identified", established_in=EUMemberState.ES, identified_in=EUMemberState.DE
        ),
    )
    assert spanish_established_german_identified.issues == (), (
        "a Spanish-established acquirer holding a German IVA number is an intra-community "
        f"acquirer under art. 25; got {[i.reason.value for i in spanish_established_german_identified.issues]}"
    )
    assert len(spanish_established_german_identified.observations) == 1
    assert _casilla_59(spanish_established_german_identified) == Decimal("5000.00")

    # Established in Germany, purchasing under a Spanish NIF-IVA. Domestic supply.
    german_established_spanish_identified = _aggregate(
        _intracom_supply(
            "de-established-es-identified", established_in=EUMemberState.DE, identified_in=EUMemberState.ES
        ),
    )
    assert german_established_spanish_identified.observations == (), (
        "a counterparty purchasing under a Spanish IVA identification is not an "
        "intra-community acquirer, so its base must not reach casilla 59"
    )
    assert [issue.reason for issue in german_established_spanish_identified.issues] == [
        IvaLedgerAggregationIssueReason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION,
    ]
    assert _casilla_59(german_established_spanish_identified) == Decimal("0")


def test_absent_identification_refuses_and_never_falls_back_to_the_country() -> None:
    """Absent means absent: no country-derived fallback in either direction.

    The establishment is a perfectly good non-ES Member State here. A gate that
    fell back to it would grant the exemption; a gate that fell back to it in
    the other direction would refuse a row whose establishment was Spanish for
    the wrong reason. Both are refused identically, for the one honest reason.
    """
    for label, established_in in (
        ("non-ES establishment", EUMemberState.DE),
        ("ES establishment", EUMemberState.ES),
        ("no establishment", None),
    ):
        aggregation = _aggregate(
            _intracom_supply(
                f"absent-identification-{established_in}", established_in=established_in, identified_in=None
            ),
        )
        assert aggregation.observations == (), f"{label}: absent identification must withhold the base"
        assert [issue.reason for issue in aggregation.issues] == [
            IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE,
        ], f"{label}: must refuse for absent identification, not derive one from the country"
        # The refusal is resolvable: it names the fact to record, not a bare rejection.
        assert "identif" in aggregation.issues[0].detail.lower()
        assert _casilla_59(aggregation) == Decimal("0")
