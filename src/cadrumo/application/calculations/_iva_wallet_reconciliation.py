"""IVA compensation wallet reconciliation orchestration.

The live AEAT wallet is external state. Local Modelo 303 recurrence is
internal reconstruction. This module is the application boundary that turns
those evidence sources, plus an explicit taxpayer override when present, into
the effective binding decision consumed by Modelo 303 calculation.

The pure decision logic
(:func:`~domain.iva_compensation._reconciliation.reconcile_iva_compensation_wallet`
and its wallet/recurrence predicates) lives in
:mod:`~domain.iva_compensation._reconciliation`; it consumes structural
ports such as
:class:`~domain.iva_compensation._reconciliation.IvaCompensationWalletObservationProtocol`
and
:class:`~domain.iva_compensation._reconciliation.LocalIvaCompensationRecurrenceProtocol`
so the domain never imports the Sede adapter. This module orchestrates
:class:`~._observations_repository.CalculationObservationRepository` reads,
:class:`~._observations_repository.IvaWalletDecisionRepository` persistence, and
source-mesh resolution around that pure decision.

Binding resolution reads its active revision through a
:class:`~domain.calculations.registry.RegistrySnapshot` supplied via the
source mesh context.

See Also:
    :func:`~._binding_prefill.extract_modelo_303_local_iva_compensation_recurrence`
        Reconstructs the local Modelo 303 recurrence compared with wallet
        evidence.
    :class:`~application.aggregation.CalculationSourceResolution`
        The source-mesh envelope produced by
        :class:`~application.calculations._iva_wallet_reconciliation.IvaWalletDecisionSourceResolver`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ...core import BindingSourceKind, Modelo, Period
from ...core.hashing import sha256_hex
from ...domain.calculations.registry import RegistrySnapshot
from ...domain.iva_compensation import (
    DEFAULT_MAX_WALLET_AGE_DAYS,
    IvaCompensationOverride,
    IvaCompensationReconciliationDecision,
    IvaCompensationReconciliationInputError,
    IvaCompensationWalletObservationProtocol,
    local_recurrence_authority_source,
    reconcile_iva_compensation_wallet,
    validate_wallet_matches_snapshot,
)
from ..aggregation import (
    CalculationSourceContext,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)

if TYPE_CHECKING:
    from ._binding_prefill import BindingPrefillReport, LocalIvaCompensationRecurrence
    from ._observations_repository import CalculationObservationRepository, IvaWalletDecisionRepository


class IvaCompensationReconciliationReport(BaseModel):
    """Application-level reconciliation result for one Modelo 303 target.

    Carries the domain
    :class:`~domain.iva_compensation._reconciliation.IvaCompensationReconciliationDecision`
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
    :class:`~domain.iva_compensation._reconciliation.IvaCompensationReconciliationDecision`.
    The returned :class:`~application.aggregation.CalculationSourceResolution`
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
                translated_message="application.calculations.iva_wallet.errors.decision_target_mismatch",
                context={
                    "decision_target_year": decision.target_year,
                    "decision_target_period": str(decision.target_period),
                    "context_filing_year": context.filing_year,
                    "context_period": str(context.period),
                },
            )
        if decision.blocked:
            raise IvaCompensationReconciliationInputError(
                translated_message="application.calculations.iva_wallet.errors.decision_blocks_calculation",
                context={
                    "divergence": str(decision.divergence),
                    "target_year": decision.target_year,
                    "target_period": str(decision.target_period),
                },
            )
        if decision.selected_amount is None:
            raise IvaCompensationReconciliationInputError(
                translated_message="application.calculations.iva_wallet.errors.decision_no_selected_amount",
                context={
                    "target_year": decision.target_year,
                    "target_period": str(decision.target_period),
                },
            )
        fingerprint = f"sha256:{sha256_hex(decision.model_dump_json().encode('utf-8'))}"
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values={self.binding_id: Decimal(decision.selected_amount)},
            provenance=tuple(
                CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    source_kind=source.source_kind,
                    source_ref=source.source_locator,
                    fingerprint=fingerprint,
                )
                for source in decision.authority_sources
            ),
        )


def _resolve_reconciliation_repositories(
    *,
    repository: CalculationObservationRepository | None,
    decision_repository: IvaWalletDecisionRepository | None,
    persist: bool,
) -> tuple[CalculationObservationRepository, IvaWalletDecisionRepository]:
    """Resolve both repositories, refusing an explicit pair that would split the encrypted backend.

    A decision repository defaulted from the observation repository shares its
    backend by construction; only an explicitly supplied one can diverge, and a
    divergence is refused whenever the decision will actually be persisted.
    """
    from ._observations_repository import CalculationObservationRepository, IvaWalletDecisionRepository

    repo = repository if repository is not None else CalculationObservationRepository()
    decision_repo = (
        decision_repository
        if decision_repository is not None
        else IvaWalletDecisionRepository(objects=repo.secure_object_repository)
    )
    if (
        persist
        and decision_repository is not None
        and decision_repo.secure_object_repository.engine is not repo.secure_object_repository.engine
    ):
        raise IvaCompensationReconciliationInputError(
            translated_message="application.calculations.iva_wallet.errors.decision_repository_backend_split",
            context={"persist": persist, "decision_repository_supplied": True},
        )
    return repo, decision_repo


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
    local_evidence_found_but_unusable: bool = False,
    local_recurrence: LocalIvaCompensationRecurrence | None = None,
    use_repository_local_recurrence: bool = True,
    persist: bool = True,
) -> IvaCompensationReconciliationReport:
    """Resolve, compare, and optionally persist the Modelo 303 IVA wallet decision.

    The function validates wallet evidence against the target
    :class:`~domain.calculations.registry.RegistrySnapshot`, reconstructs local recurrence through
    :func:`~._binding_prefill.extract_modelo_303_local_iva_compensation_recurrence`,
    delegates authority selection to
    :func:`~domain.iva_compensation._reconciliation.reconcile_iva_compensation_wallet`,
    and persists the resulting
    :class:`~domain.iva_compensation._reconciliation.IvaCompensationReconciliationDecision`
    through :class:`~._observations_repository.IvaWalletDecisionRepository` when
    ``persist`` is true.

    Args:
        snapshot: The :class:`~domain.calculations.registry.RegistrySnapshot`
            identifying the Modelo 303 target revision.
        taxpayer_nif: Taxpayer identifier expected to match live wallet evidence.
        wallet: Live AEAT wallet observation to reconcile, when available.
        repository: Optional
            :class:`~application.calculations._observations_repository.CalculationObservationRepository`
            used to read prior local recurrence.
        decision_repository: Optional
            :class:`~application.calculations._observations_repository.IvaWalletDecisionRepository`
            used to persist the resulting wallet authority. When persistence is
            enabled, an explicitly supplied repository must use the same
            encrypted storage backend as ``repository``.
        override: Optional
            :class:`~domain.iva_compensation._reconciliation.IvaCompensationOverride`
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
        local_evidence_found_but_unusable: Whether the caller FOUND a prior
            local record and could not interpret it as prior-compensation
            evidence. Only the caller knows this: an absent amount looks the
            same here whether nothing was stored or something was and could not
            be read. It changes no outcome, only what the no-authority decision
            says, so an operator is not told nothing exists while their own
            prior record sits in the store.
        local_recurrence: Optional local recurrence evidence supplied by the
            caller. Callers that own a stricter evidence boundary can pass its
            already-validated projection here.
        use_repository_local_recurrence: Whether to use the generic
            repository/history reconstruction as the local recurrence source.
            A caller that supplies a stricter recurrence may disable this so a
            legacy generic observation cannot regain authority by fallback.
            When disabled the generic reconstruction is not performed at all,
            so the returned ``prefill_report`` is empty: a switched-off producer
            contributes neither a value nor a report.
        persist: Whether to store the resulting decision for later calculation replay.

    The local side is not recomputed here. It is read through the same
    previous-filing binding resolver used by the calculation chain.

    Returns an
    :class:`~application.calculations._iva_wallet_reconciliation.IvaCompensationReconciliationReport`.

    See Also:
        :class:`~application.calculations._iva_wallet_reconciliation.IvaWalletDecisionSourceResolver`
            Converts a persisted non-blocking decision into the Modelo 303
            ``iva_wallet_decision`` source value.
    """
    if str(getattr(snapshot.modelo, "id", snapshot.modelo)) != Modelo.M303.value:
        raise IvaCompensationReconciliationInputError(
            translated_message="application.calculations.iva_wallet.errors.modelo_303_only",
            context={"modelo": str(getattr(snapshot.modelo, "id", snapshot.modelo))},
        )
    snapshot_period = Period.from_year_and_code(snapshot.filing_year, snapshot.period)
    if wallet is not None:
        validate_wallet_matches_snapshot(
            wallet,
            taxpayer_nif=taxpayer_nif,
            target_year=snapshot.filing_year,
            target_period=snapshot_period,
        )

    from ._binding_prefill import BindingPrefillReport, extract_modelo_303_local_iva_compensation_recurrence

    repo, decision_repo = _resolve_reconciliation_repositories(
        repository=repository,
        decision_repository=decision_repository,
        persist=persist,
    )
    # The selection happens BEFORE the work, not after it. The two producers of
    # this recurrence are not substitutable: the generic reconstruction below
    # accepts envelopes the caller-supplied strict path deliberately refuses, so
    # they cannot be collapsed into one. Running the generic one regardless and
    # discarding its recurrence still let its prefill report ride out on the
    # returned report, which meant a producer the caller had switched off went on
    # shaping the artefact the caller received -- the switch turned off the value
    # and not the influence. It also spent a repository read and a full history
    # reconstruction on the path that had just declared it must have no authority.
    if use_repository_local_recurrence:
        recurrence, prefill_report = extract_modelo_303_local_iva_compensation_recurrence(
            snapshot,
            repository=repo,
            captured_at=decided_at,
        )
    else:
        recurrence = local_recurrence
        prefill_report = BindingPrefillReport(prefilled=(), binding_values={})
    local_recurrence_amount = recurrence.amount if recurrence is not None else None
    # First-period treatment: with no live wallet and no prior recurrence, the
    # caller-asserted first IVA period has a legally-certain zero
    # ``iva.compensacion-pendiente-periodos-anteriores`` (LIVA art. 99.5).
    # Pass an explicit zero recurrence + the first-period flag so the decision
    # is the non-blocking ``first_period_zero`` rather than the ``missing``
    # block. A present recurrence still flows through normally.
    #
    # This never overrides a recurrence it can SEE, but seeing one is the
    # caller's job: a ``None`` here says only that the caller produced no
    # recurrence, never why. The claim that used to stand in this comment --
    # that only the genuinely-absent case is mapped to zero -- was the defect
    # rather than the guarantee, because a caller that had found a stored
    # observation and could not read it arrived with the same ``None`` as a
    # caller that had found nothing at all, and an unreadable envelope became a
    # proven zero on the compensación. The caller must therefore pass the flag
    # false whenever it saw evidence it could not use.
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
        local_evidence_found_but_unusable=local_evidence_found_but_unusable,
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
