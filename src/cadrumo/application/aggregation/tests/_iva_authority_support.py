"""Real authority-bound entry point for non-investment aggregation tests."""

from __future__ import annotations

from ....core import Period
from ....domain.bienes_inversion import BienesInversionIvaRegister
from ....domain.transactions import TransactionCatalogue
from .._iva_ledger import (
    IvaLedgerAggregation,
    IvaLedgerProrrataApportionment,
)
from .._iva_ledger import (
    aggregate_iva_ledger_observations as _aggregate,
)

_PROFILE_ID = "484081b3-cc99-46ad-9b87-90097405670d"  # was 'aggregation-test-profile'
_EMPTY_REGISTER = BienesInversionIvaRegister()


def aggregate_iva_ledger_observations(
    transactions: TransactionCatalogue,
    *,
    period: Period,
    prorrata_apportionment: IvaLedgerProrrataApportionment | None = None,
) -> IvaLedgerAggregation:
    """Delegate with a typed empty register owned by the same explicit profile."""
    return _aggregate(
        transactions,
        period=period,
        ledger_profile_id=_PROFILE_ID,
        investment_asset_register=_EMPTY_REGISTER,
        investment_asset_profile_id=_PROFILE_ID,
        prorrata_apportionment=prorrata_apportionment,
    )


__all__ = ["aggregate_iva_ledger_observations"]
