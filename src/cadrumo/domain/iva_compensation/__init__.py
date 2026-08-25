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
as :class:`IvaCompensationOverride`, :class:`IvaCompensationAuthoritySource`, and
:class:`IvaCompensationReconciliationDecision` separate AEAT wallet evidence,
filed-history evidence, local recurrence, and taxpayer override before Modelo
303 consumes casilla ``110``. :func:`reconcile_iva_compensation_wallet` and
:func:`validate_wallet_matches_snapshot` apply that reconciliation policy
against a live wallet observation conforming to
:class:`IvaCompensationWalletObservationProtocol`.

Repositories, secure-object custody, live wallet acquisition, and bucket event
emission remain application responsibilities.

See Also:
    :class:`application.calculations.IvaCompensationHistoryRepository`
        Encrypted local period-state history consumed by carry reconstruction.
    :class:`application.calculations.IvaWalletDecisionRepository`
        Persisted wallet-authority decisions selected before Modelo 303
        calculation consumes casilla ``110``.
    :mod:`application.calculations`
        Application source resolvers for previous-filing carries, IVA wallet
        decisions, and Modelo 390 annual carry partitioning.
    :mod:`application.live`
        Read-only AEAT wallet and filed-history capture surface that supplies
        external evidence without performing live writes.
    :mod:`application.modelo`
        Work-unit calculation and IVA-wallet gate that apply the persisted
        authority decision to registry snapshots.
    :class:`adapters.persistence.profile.buckets.BucketEventHistoryRepository`
        Bucket audit trail for persisted decisions and capture orchestration,
        outside this pure domain package.
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
    iva_compensation_period_sort_key,
)
from .errors import (
    IvaCompensationCarryForwardPolicyError,
    IvaCompensationCasillaReferenceError,
    IvaCompensationDecimalParseError,
    IvaCompensationReconciliationInputError,
    IvaCompensationSeedConflictError,
    IvaCompensationYearRangeError,
    IvaWalletReconciliationError,
)
from ._filed_derivation import (
    M303_COMPENSATION_APLICADA_CASILLA,
    M303_COMPENSATION_AVAILABLE_CASILLA,
    M303_COMPENSATION_GENERADA_CASILLA,
    M303_COMPENSATION_POSTERIOR_CASILLA,
    M303_COMPENSATION_RESULTADO_CASILLA,
    M303CompensationAvailableDerivation,
    derive_m303_compensation_available_from_casillas,
)
from ._reconciliation import (
    DEFAULT_MAX_WALLET_AGE_DAYS,
    IvaCompensationAuthoritySource,
    IvaCompensationDecisionReason,
    IvaCompensationDivergence,
    IvaCompensationOverride,
    IvaCompensationReconciliationDecision,
    IvaCompensationWalletObservationProtocol,
    local_recurrence_authority_source,
    reconcile_iva_compensation_wallet,
    validate_wallet_matches_snapshot,
)

__all__ = [
    "DEFAULT_MAX_WALLET_AGE_DAYS",
    "M303_COMPENSATION_APLICADA_CASILLA",
    "M303_COMPENSATION_AVAILABLE_CASILLA",
    "M303_COMPENSATION_GENERADA_CASILLA",
    "M303_COMPENSATION_POSTERIOR_CASILLA",
    "M303_COMPENSATION_RESULTADO_CASILLA",
    "IvaCompensationAuthoritySource",
    "IvaCompensationCarryForwardLot",
    "IvaCompensationCarryForwardPolicyError",
    "IvaCompensationCarryForwardReport",
    "IvaCompensationCasillaReferenceError",
    "IvaCompensationDecimalParseError",
    "IvaCompensationDecisionReason",
    "IvaCompensationDivergence",
    "IvaCompensationExpiryReviewState",
    "IvaCompensationOverride",
    "IvaCompensationPeriodState",
    "IvaCompensationReconciliationDecision",
    "IvaCompensationReconciliationInputError",
    "IvaCompensationSeedConflictError",
    "IvaCompensationWalletObservationProtocol",
    "IvaCompensationYearEndCarryPartition",
    "IvaCompensationYearRangeError",
    "IvaWalletBalanceReport",
    "IvaWalletReconciliationError",
    "M303CompensationAvailableDerivation",
    "build_iva_compensation_carry_forward_report",
    "build_iva_wallet_balance_report",
    "derive_303_compensation_available",
    "derive_iva_compensation_year_end_carry_partition",
    "derive_m303_compensation_available_from_casillas",
    "enforce_iva_compensation_four_year_window",
    "iva_compensation_period_sort_key",
    "local_recurrence_authority_source",
    "reconcile_iva_compensation_wallet",
    "validate_wallet_matches_snapshot",
]
