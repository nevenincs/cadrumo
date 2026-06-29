"""IVA compensation wallet reconciliation orchestration.

The live AEAT wallet is external state. Local Modelo 303 recurrence is
internal reconstruction. This module is the application boundary that turns
those evidence sources, plus an explicit taxpayer override when present, into
the effective binding decision consumed by Modelo 303 calculation.

The pure decision logic
(:func:`~aeat.domain.iva_compensation._reconciliation.reconcile_iva_compensation_wallet`
and its wallet/recurrence predicates) lives in
:mod:`aeat.domain.iva_compensation._reconciliation`; it consumes structural
ports such as
:class:`~aeat.domain.iva_compensation._reconciliation.IvaCompensationWalletObservationProtocol`
and
:class:`~aeat.domain.iva_compensation._reconciliation.LocalIvaCompensationRecurrenceProtocol`
so the domain never imports the Sede adapter. This module orchestrates
:class:`~._observations_repository.CalculationObservationRepository` reads,
:class:`~._observations_repository.IvaWalletDecisionRepository` persistence, and
source-mesh resolution around that pure decision.

Binding resolution reads its active revision through a
:class:`~aeat.domain.calculations.registry.RegistrySnapshot` supplied via the
source mesh context.

See Also:
    :func:`~._binding_prefill.extract_modelo_303_local_iva_compensation_recurrence`
        Reconstructs the local Modelo 303 recurrence compared with wallet
        evidence.
    :class:`~aeat.application.aggregation.CalculationSourceResolution`
        The source-mesh envelope produced by
        :class:`~aeat.application.calculations._iva_wallet_reconciliation.IvaWalletDecisionSourceResolver`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ...core import BindingSourceKind, Modelo, Period
from ...core.hashing import sha256_hex
from ...domain.calculations.registry import RegistrySnapshot
from ...domain.iva_compensation._errors import IvaCompensationReconciliationInputError
from ...domain.iva_compensation._reconciliation import (
    DEFAULT_MAX_WALLET_AGE_DAYS,
    IvaCompensationOverride,
    IvaCompensationReconciliationDecision,
    IvaCompensationWalletObservationProtocol,
    local_recurrence_authority_source,
    reconcile_iva_compensation_wallet,
    validate_wallet_matches_snapshot,
)
from ..aggregation._source_mesh import (
    CalculationSourceContext,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)

if TYPE_CHECKING:
    from ._binding_prefill import BindingPrefillReport
    from ._observations_repository import CalculationObservationRepository, IvaWalletDecisionRepository


class IvaCompensationReconciliationReport(BaseModel):
    """Application-level reconciliation result for one Modelo 303 target.

    Carries the domain
    :class:`~aeat.domain.iva_compensation._reconciliation.IvaCompensationReconciliationDecision`
    plus the :class:`~._binding_prefill.BindingPrefillReport` used to reconstruct
    the local recurrence side of the comparison.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True)

    decision: IvaCompensationReconciliationDecision
    prefill_report: BindingPrefillReport


class IvaWalletDecisionSourceResolver:
    """Source-mesh adapter for persisted Modelo 303 IVA wallet decisions.

    Owns ``iva_wallet_decision`` and materialises the
    ``modelo-303-compensacion-pendiente-anteriores`` binding from a persisted
    :class:`~aeat.domain.iva_compensation._reconciliation.IvaCompensationReconciliationDecision`.
    The returned :class:`~aeat.application.aggregation.CalculationSourceResolution`
    carries the selected amount plus provenance for every authority source that
    participated in the wallet/filed-history/local-recurrence decision.
    """

    resolver_id = "iva_wallet_decision"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.IVA_WALLET_DECISION,)
    binding_id = "modelo-303-compensacion-pendiente-anteriores"

    def __init__(self, decision: IvaCompensationReconciliationDecision | None) -> None:
        self._decision = decision

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        if context.modelo != Modelo.M303.value or self._decision is None:
            return CalculationSourceResolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
            )
        decision = self._decision
        if decision.target_year != context.filing_year or decision.target_period != context.period:
            raise IvaCompensationReconciliationInputError(
                "IVA wallet reconciliation decision target does not match the Modelo 303 work unit",
            )
        if decision.blocked:
            raise IvaCompensationReconciliationInputError(
                f"IVA wallet reconciliation blocks automatic Modelo 303 calculation: {decision.divergence}",
            )
        if decision.selected_amount is None:
            raise IvaCompensationReconciliationInputError("IVA wallet reconciliation decision has no selected amount")
        fingerprint = f"sha256:{sha256_hex(decision.model_dump_json().encode('utf-8'))}"
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values={self.binding_id: Decimal(decision.selected_amount)},
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind=source.source_kind,
                    source_ref=source.source_locator,
                    fingerprint=fingerprint,
                )
                for source in decision.authority_sources
            ),
        )


def reconcile_modelo_303_iva_compensation(
    snapshot: RegistrySnapshot,
    *,
    taxpayer_nif: str,
    wallet: IvaCompensationWalletObservationProtocol | None,
    repository: CalculationObservationRepository | None = None,
    decision_repository: IvaWalletDecisionRepository | None = None,
    override: IvaCompensationOverride | None = None,
    decided_at: datetime | None = None,
    max_wallet_age_days: int = DEFAULT_MAX_WALLET_AGE_DAYS,
    treat_absent_recurrence_as_first_period: bool = False,
    persist: bool = True,
) -> IvaCompensationReconciliationReport:
    """Resolve, compare, and optionally persist the Modelo 303 IVA wallet decision.

    The function validates wallet evidence against the target
    :class:`~aeat.domain.calculations.registry.RegistrySnapshot`, reconstructs local recurrence through
    :func:`~._binding_prefill.extract_modelo_303_local_iva_compensation_recurrence`,
    delegates authority selection to
    :func:`~aeat.domain.iva_compensation._reconciliation.reconcile_iva_compensation_wallet`,
    and persists the resulting
    :class:`~aeat.domain.iva_compensation._reconciliation.IvaCompensationReconciliationDecision`
    through :class:`~._observations_repository.IvaWalletDecisionRepository` when
    ``persist`` is true.

    Args:
        snapshot: The :class:`~aeat.domain.calculations.registry.RegistrySnapshot`
            identifying the Modelo 303 target revision.
        taxpayer_nif: Taxpayer identifier expected to match live wallet evidence.
        wallet: Live AEAT wallet observation to reconcile, when available.
        repository: Optional
            :class:`~aeat.application.calculations._observations_repository.CalculationObservationRepository`
            used to read prior local recurrence.
        decision_repository: Optional
            :class:`~aeat.application.calculations._observations_repository.IvaWalletDecisionRepository`
            used to persist the resulting wallet authority.
        override: Optional
            :class:`~aeat.domain.iva_compensation._reconciliation.IvaCompensationOverride`
            evidence when the operator has resolved a divergence.
        decided_at: Decision timestamp override for deterministic replay and tests.
        max_wallet_age_days: Maximum accepted age for live wallet evidence.
        treat_absent_recurrence_as_first_period: When ``True`` and there is no
            live wallet and no prior local recurrence, treat the target as the
            taxpayer's FIRST IVA period: ``iva.compensacion-pendiente-periodos-anteriores``
            is zero per LIVA art. 99.5 (no prior compensation balance can exist), yielding the non-blocking
            ``first_period_zero`` decision instead of the ``missing`` block. The
            caller asserts first-period status (e.g. the calculate path verifies
            no prior 303 compensation history exists). It NEVER fabricates a
            non-zero balance: a present recurrence still flows through normally.
        persist: Whether to store the resulting decision for later calculation replay.

    The local side is not recomputed here. It is read through the same
    previous-filing binding resolver used by the calculation chain.

    Returns an
    :class:`~aeat.application.calculations._iva_wallet_reconciliation.IvaCompensationReconciliationReport`.

    See Also:
        :class:`~aeat.application.calculations._iva_wallet_reconciliation.IvaWalletDecisionSourceResolver`
            Converts a persisted non-blocking decision into the Modelo 303
            ``iva_wallet_decision`` source value.
    """
    if str(getattr(snapshot.modelo, "id", snapshot.modelo)) != Modelo.M303.value:
        raise IvaCompensationReconciliationInputError(
            "IVA compensation wallet reconciliation only applies to Modelo 303",
        )
    snapshot_period = Period.from_year_and_code(snapshot.filing_year, snapshot.period)
    if wallet is not None:
        validate_wallet_matches_snapshot(
            wallet,
            taxpayer_nif=taxpayer_nif,
            target_year=snapshot.filing_year,
            target_period=snapshot_period,
        )

    from ._binding_prefill import extract_modelo_303_local_iva_compensation_recurrence
    from ._observations_repository import CalculationObservationRepository, IvaWalletDecisionRepository

    repo = repository if repository is not None else CalculationObservationRepository()
    decision_repo = (
        decision_repository
        if decision_repository is not None
        else IvaWalletDecisionRepository(objects=repo.secure_object_repository)
    )
    recurrence, prefill_report = extract_modelo_303_local_iva_compensation_recurrence(
        snapshot,
        repository=repo,
        captured_at=decided_at,
    )
    local_recurrence_amount = recurrence.amount if recurrence is not None else None
    # First-period treatment: with no live wallet and no prior recurrence, the
    # caller-asserted first IVA period has a legally-certain zero
    # ``iva.compensacion-pendiente-periodos-anteriores`` (LIVA art. 99.5).
    # Pass an explicit zero recurrence + the first-period flag so the decision
    # is the non-blocking ``first_period_zero`` rather than the ``missing``
    # block. This NEVER overrides a real recurrence: only the
    # genuinely-absent (None) case is mapped to zero.
    is_first_iva_period = treat_absent_recurrence_as_first_period and wallet is None and local_recurrence_amount is None
    if is_first_iva_period:
        local_recurrence_amount = Decimal("0")
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif=taxpayer_nif,
        target_year=snapshot.filing_year,
        target_period=snapshot_period,
        wallet=wallet,
        local_recurrence_amount=local_recurrence_amount,
        local_recurrence_source=local_recurrence_authority_source(recurrence),
        override=override,
        decided_at=decided_at,
        max_wallet_age_days=max_wallet_age_days,
        is_first_iva_period=is_first_iva_period,
    )
    if persist:
        decision_repo.save_decision(decision)
    return IvaCompensationReconciliationReport(
        decision=decision,
        prefill_report=prefill_report,
    )


__all__ = [
    "IvaCompensationReconciliationReport",
    "IvaWalletDecisionSourceResolver",
    "reconcile_iva_compensation_wallet",
    "reconcile_modelo_303_iva_compensation",
]
