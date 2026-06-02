"""Repository-backed IVA compensation wallet balance query.

Loads stored Modelo 303 compensation period states and projects them into the
pure :class:`IvaWalletBalanceReport` summary owned by the IVA-compensation
domain. The summary projection and its record live in
:mod:`aeat.domain.iva_compensation._balance`; this module is the application
orchestration that wires the repository to that pure projection.
"""

from __future__ import annotations

from ...domain.iva_compensation._balance import (
    IvaWalletBalanceReport,
    build_iva_wallet_balance_report,
)
from ...domain.iva_compensation._carry_forward import build_iva_compensation_carry_forward_report
from ._iva_compensation_history import IvaCompensationHistoryRepository


def query_iva_wallet_balance(*, as_of_year: int) -> IvaWalletBalanceReport:
    """Load all stored IVA compensation period states and return the balance report.

    Returns an :class:`IvaWalletBalanceReport` summarising the carry-forward
    lots and the available compensation balance as of ``as_of_year``.
    """
    repo = IvaCompensationHistoryRepository()
    states = repo.list_periods()
    carry_forward = build_iva_compensation_carry_forward_report(states, as_of_year=as_of_year)
    return build_iva_wallet_balance_report(carry_forward)


__all__ = [
    "query_iva_wallet_balance",
]
