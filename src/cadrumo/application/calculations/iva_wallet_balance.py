"""Repository-backed IVA compensation wallet balance query.

Loads stored Modelo 303 compensation period states and projects them into the
pure
:class:`~domain.iva_compensation.IvaWalletBalanceReport` summary
owned by the IVA-compensation domain. The summary projection and its record are
exposed from :mod:`domain.iva_compensation`; this module is the application
orchestration that wires
:class:`~application.calculations.IvaCompensationHistoryRepository`
to that pure projection.

See Also:
    :func:`~domain.iva_compensation.build_iva_compensation_carry_forward_report`
        Builds the FIFO lot projection from stored period states.
    :func:`~domain.iva_compensation.build_iva_wallet_balance_report`
        Collapses the carry-forward lots into the operator-facing balance
        snapshot.
"""

from __future__ import annotations

from ...domain.iva_compensation.balance import IvaWalletBalanceReport, build_iva_wallet_balance_report
from ...domain.iva_compensation.carry_forward import build_iva_compensation_carry_forward_report
from .iva_compensation_history import IvaCompensationHistoryRepository


def query_iva_wallet_balance(*, as_of_year: int) -> IvaWalletBalanceReport:
    """Load all stored IVA compensation period states and return the balance report.

    Reads
    :class:`~domain.iva_compensation.IvaCompensationPeriodState`
    rows from
    :class:`~application.calculations.IvaCompensationHistoryRepository`,
    builds a
    :class:`~domain.iva_compensation.IvaCompensationCarryForwardReport`,
    and returns an
    :class:`~domain.iva_compensation.IvaWalletBalanceReport`
    summarising available compensation as of ``as_of_year``.
    """
    repo = IvaCompensationHistoryRepository()
    states = repo.list_periods()
    carry_forward = build_iva_compensation_carry_forward_report(states, as_of_year=as_of_year)
    return build_iva_wallet_balance_report(carry_forward)


__all__ = [
    "query_iva_wallet_balance",
]
