"""Rental register subpackage (#454).

Per-finca + per-contract register backing the M100 Anexo C aggregates
(LIRPF arts. 22-24 + 85), the LIRPF art. 23.2 four-tier auto-resolver
introduced by Ley 12/2023, and the LIRPF art. 23.1.f amortización 3 %
multi-year ledger with a per-finca cost-basis cap.

Public API: callers outside :mod:`aeat.rental` import only from this
module. Internal modules (``_models``, ``_enums``, ``_errors``,
``_repository``, ``_tier_resolver``, ``_amortization_ledger``,
``_expense_rollup``, ``_anexo_c_aggregator``, ``anexo_c_provider``)
are implementation details.

See ``.vault/adr/2026-04-29-rental-income-hardening-adr.md`` for the
design record and ``.vault/plan/2026-04-29-rental-income-hardening-plan.md``
for the rollout plan.
"""

from __future__ import annotations

from ._enums import ExpenseCategory, ReduccionTier, UseType
from ._errors import (
    AmortizationLedgerCapExceededError,
    AnexoCAggregationError,
    ContractNotFoundError,
    FincaNotFoundError,
    RentalRegisterError,
    TierResolutionError,
)
from ._models import (
    RentalAmortizationLedgerEntry,
    RentalContract,
    RentalExpense,
    RentalFinca,
    RentalIncomeRecord,
)
from ._repository import (
    RentalAmortizationLedgerRepository,
    RentalContractRepository,
    RentalExpenseRepository,
    RentalFincaRepository,
    RentalIncomeRepository,
)

__all__ = [
    "AmortizationLedgerCapExceededError",
    "AnexoCAggregationError",
    "ContractNotFoundError",
    "ExpenseCategory",
    "FincaNotFoundError",
    "ReduccionTier",
    "RentalAmortizationLedgerEntry",
    "RentalAmortizationLedgerRepository",
    "RentalContract",
    "RentalContractRepository",
    "RentalExpense",
    "RentalExpenseRepository",
    "RentalFinca",
    "RentalFincaRepository",
    "RentalIncomeRecord",
    "RentalIncomeRepository",
    "RentalRegisterError",
    "TierResolutionError",
    "UseType",
]
