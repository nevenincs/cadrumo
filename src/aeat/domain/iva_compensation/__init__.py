"""Public facade for pure IVA-compensation domain primitives.

This package owns the regulatory Modelo 303 carry-forward projection, the
Modelo 390 year-end carry partition, the wallet reconciliation decision logic,
and the wallet balance projection. The domain works with typed immutable records
such as :class:`IvaCompensationPeriodState`,
:class:`IvaCompensationCarryForwardLot`,
:class:`IvaCompensationCarryForwardReport`,
:class:`IvaCompensationYearEndCarryPartition`, and
:class:`IvaWalletBalanceReport`; it does not open repositories, emit bucket
events, or resolve the active profile.

Compensation availability is derived by :func:`derive_303_compensation_available`
and then projected through
:func:`build_iva_compensation_carry_forward_report` /
:func:`enforce_iva_compensation_four_year_window`. Reconciliation records such
as :class:`IvaCompensationOverride`,
:class:`~aeat.domain.iva_compensation._reconciliation.IvaCompensationAuthoritySource`,
and
:class:`~aeat.domain.iva_compensation._reconciliation.IvaCompensationReconciliationDecision`
separate AEAT wallet evidence, filed-history evidence, local recurrence, and
taxpayer override before Modelo 303 consumes casilla ``110``.

Repositories, secure-object custody, live wallet acquisition, and bucket event
emission remain application responsibilities. See
:class:`~aeat.application.calculations.IvaCompensationHistoryRepository`,
:class:`~aeat.application.calculations.IvaWalletDecisionRepository`,
:mod:`aeat.application.calculations._iva_wallet_reconciliation`,
:mod:`aeat.application.modelo._iva_wallet_gate`, and
:class:`~aeat.domain.buckets.BucketEventHistoryRepository` for those persisted
and orchestration boundaries.
"""

from __future__ import annotations

from ._balance import (
    IvaWalletBalanceReport,
    build_iva_wallet_balance_report,
)
from ._carry_forward import (
    IvaCompensationCarryForwardLot,
    IvaCompensationCarryForwardReport,
    IvaCompensationExpiryReviewState,
    IvaCompensationPeriodState,
    IvaCompensationYearEndCarryPartition,
    build_iva_compensation_carry_forward_report,
    derive_303_compensation_available,
    derive_iva_compensation_year_end_carry_partition,
    enforce_iva_compensation_four_year_window,
)
from ._errors import (
    IvaCompensationCarryForwardPolicyError,
    IvaCompensationCasillaReferenceError,
    IvaCompensationDecimalParseError,
    IvaCompensationReconciliationInputError,
    IvaCompensationSeedConflictError,
    IvaCompensationYearRangeError,
)
from ._reconciliation import (
    IvaCompensationOverride,
)

__all__ = [
    "IvaCompensationCarryForwardLot",
    "IvaCompensationCarryForwardPolicyError",
    "IvaCompensationCarryForwardReport",
    "IvaCompensationCasillaReferenceError",
    "IvaCompensationDecimalParseError",
    "IvaCompensationExpiryReviewState",
    "IvaCompensationOverride",
    "IvaCompensationPeriodState",
    "IvaCompensationReconciliationInputError",
    "IvaCompensationSeedConflictError",
    "IvaCompensationYearEndCarryPartition",
    "IvaCompensationYearRangeError",
    "IvaWalletBalanceReport",
    "build_iva_compensation_carry_forward_report",
    "build_iva_wallet_balance_report",
    "derive_303_compensation_available",
    "derive_iva_compensation_year_end_carry_partition",
    "enforce_iva_compensation_four_year_window",
]
