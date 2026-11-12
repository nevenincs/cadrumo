"""Modelo 303 IVA wallet decision authority: persisted, refreshed and locally derived.

A persisted :class:`~cadrumo.domain.iva_compensation.reconciliation.IvaCompensationReconciliationDecision`
is replayed against the current local evidence and refreshed where it changed;
a missing one may be derived from local recurrence. A ``first_period_zero``
decision stands only where concrete zero authority or the profile's activity
start, read against the registry snapshot, proves every prior Modelo 303
compensation dependency is pre-activity.

It works with :class:`RegistrySnapshot`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from ...core.errors.hierarchy import InternalInvariantError
from ...core.period import Period
from ...core.type_guards import is_object_collection
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.iva_compensation.reconciliation import (
    IvaCompensationDecisionReason,
    IvaCompensationReconciliationDecision,
    IvaCompensationWalletObservationProtocol,
)
from ...domain.modelos.work_unit import WorkUnit
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ..calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    IvaWalletDecisionRepositoryProtocol,
)
from ..operator_actions.invariant_verdicts import internal_invariant_verdict
from .iva_wallet_binding import M303_PRIOR_COMPENSATION_ORIGIN_IDS
from .iva_wallet_prior_period import PriorModeloCalculations, prior_period_carry_evidence
from .iva_wallet_refusal import ModeloIvaWalletAuthorityUnavailableError, raise_iva_wallet_precondition
from .iva_wallet_values import taxpayer_nif_from_path_values

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_LOCAL_EVIDENCE_SOURCE_KINDS: Final[frozenset[str]] = frozenset(
    {"local_recurrence", "filed_history_observation"},
)
"""Source kinds that are locally derived rather than observed at AEAT.

Tested twice in this module, each time paired with a different second condition, so the
two checks agreed on the kinds only by hand. Held as a name so a kind added to one check
cannot be missed by the other.
"""


def persisted_decision_for_calculation(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
    repository: IvaWalletDecisionRepositoryProtocol,
    observation_repository: CalculationObservationRepositoryProtocol,
    history_repository: IvaCompensationHistoryRepositoryProtocol,
    profile_values: Mapping[str, str] | None,
    evaluated_at: datetime | None = None,
    persist_blocked: bool = True,
    prior_calculations: PriorModeloCalculations | None = None,
) -> IvaCompensationReconciliationDecision | None:
    """Return the persisted decision for calculation, refreshed and first-period-zero grounded.

    ``snapshot`` is the :class:`RegistrySnapshot` it uses.
    """
    persisted = load_persisted_iva_compensation_decision_for_work_unit(
        work_unit,
        repository=repository,
        profile_values=profile_values,
    )
    if persisted is None:
        return None
    refreshed = refresh_local_iva_compensation_decision_if_evidence_changed(
        work_unit,
        snapshot=snapshot,
        operation=operation,
        decision=persisted,
        repository=repository,
        observation_repository=observation_repository,
        history_repository=history_repository,
        profile_values=profile_values,
        evaluated_at=evaluated_at,
        persist_blocked=persist_blocked,
        prior_calculations=prior_calculations,
    )
    return require_first_period_zero_decision_grounded(
        work_unit,
        snapshot,
        refreshed,
        subject_leaf_key="modelo.work.calculate",
        profile_values=profile_values,
    )


def load_persisted_iva_compensation_decision_for_work_unit(
    work_unit: WorkUnit,
    *,
    repository: IvaWalletDecisionRepositoryProtocol,
    profile_values: Mapping[str, str] | None,
) -> IvaCompensationReconciliationDecision | None:
    """Load the persisted IVA compensation decision for a :class:`~WorkUnit`.

    Returns:
        The persisted :class:`IvaCompensationReconciliationDecision` for Modelo
        303 work units, or ``None`` when the work unit or bucket has no wallet
        authority record.
    """
    if work_unit.modelo != form_for_role("iva.periodic"):
        return None
    taxpayer_nif = taxpayer_nif_from_path_values(profile_values)
    if taxpayer_nif is None:
        return None
    return repository.load_decision(
        taxpayer_nif,
        work_unit.period,
    )


def _activity_start_date_from_path_values(values: Mapping[str, str] | None) -> date | None:
    """Return the lifecycle profile's declared activity-start date, if parseable."""
    from ...core.parsing.dates import parse_iso8601_date

    if values is None:
        return None
    try:
        return parse_iso8601_date(values.get("censo.activity_start_date"))
    except ValueError:
        return None


def registry_snapshot_for_work_unit(
    work_unit: WorkUnit,
    *,
    subject_leaf_key: str,
    operation: PinnedAuthorityOperation | None = None,
) -> RegistrySnapshot:
    """Resolve the registry snapshot attached to ``work_unit``."""
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return registry_snapshot_for_work_unit(
                work_unit,
                subject_leaf_key=subject_leaf_key,
                operation=indexed_operation,
            )
    try:
        return operation.snapshot(
            str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    except (FileNotFoundError, RegistrySnapshotError) as exc:
        raise_iva_wallet_precondition(
            subject_leaf_key=subject_leaf_key,
            reason_code="registry_snapshot_unavailable",
            error_type=ModeloIvaWalletAuthorityUnavailableError,
            translated_message="application.modelo.errors.iva_wallet_registry_snapshot_unavailable",
            evidence_values={
                "modelo_id": str(work_unit.modelo),
                "filing_year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
                "registry_snapshot_available": False,
            },
            context={
                "divergence": "first_period_zero_unproven",
                "reason": "registry_snapshot_unavailable",
            },
            cause=exc,
        )


def decision_is_first_period_zero(decision: object) -> bool:
    """Return whether ``decision`` records a first-period zero carry."""
    return str(getattr(decision, "divergence", "")) == "first_period_zero"


def refresh_local_iva_compensation_decision_if_evidence_changed(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
    decision: IvaCompensationReconciliationDecision,
    repository: IvaWalletDecisionRepositoryProtocol,
    observation_repository: CalculationObservationRepositoryProtocol,
    history_repository: IvaCompensationHistoryRepositoryProtocol,
    profile_values: Mapping[str, str] | None,
    evaluated_at: datetime | None = None,
    persist_blocked: bool = True,
    prior_calculations: PriorModeloCalculations | None = None,
) -> IvaCompensationReconciliationDecision:
    """Return ``decision``, or its local refresh where the local evidence it replays has changed.

    ``snapshot`` is the :class:`RegistrySnapshot` it uses.
    """
    if decision.selected_authority == "taxpayer_override":
        return decision
    refreshed = reconcile_local_iva_compensation(
        work_unit,
        snapshot=snapshot,
        operation=operation,
        repository=repository,
        observation_repository=observation_repository,
        history_repository=history_repository,
        persist=False,
        wallet=_wallet_evidence_from_decision(decision),
        profile_values=profile_values,
        evaluated_at=evaluated_at,
        prior_calculations=prior_calculations,
    )
    if refreshed is None or _decision_replay_basis(refreshed) == _decision_replay_basis(decision):
        return decision
    if _keeps_local_calculation(decision, refreshed, prior_calculations=prior_calculations):
        return decision
    if persist_blocked or not refreshed.blocked:
        save_iva_compensation_decision(refreshed, repository=repository)
    return refreshed


def _keeps_local_calculation(
    decision: IvaCompensationReconciliationDecision,
    refreshed: IvaCompensationReconciliationDecision,
    *,
    prior_calculations: PriorModeloCalculations | None,
) -> bool:
    """Whether a stored local-calculation carry stands because this reader cannot see calculations.

    Verification, filing and export read no prior calculation, so a refresh
    there that finds no other authority has not learnt the carry is gone; it
    keeps the stored decision and refuses it as a local calculation instead.
    Any authority it does find -- the wallet, a filed return, a declared
    opening balance -- replaces it.
    """
    return (
        prior_calculations is None
        and decision.selected_authority == "local_calculation"
        and refreshed.selected_authority == "missing"
    )


def _decision_replay_basis(decision: IvaCompensationReconciliationDecision) -> tuple[object, ...]:
    return (
        decision.wallet_captured_at,
        decision.stale_wallet,
        decision.wallet_amount,
        decision.source_registry_snapshot_refs,
        decision.selected_authority,
        decision.selected_amount,
        decision.local_recurrence_amount,
        decision.divergence,
        decision.blocked,
        decision.reason_identity,
        tuple(
            (
                source.source_kind,
                source.amount,
                source.source_locator,
                source.source_modelo,
                source.source_filing_year,
                source.source_periods,
            )
            for source in decision.authority_sources
        ),
    )


def decision_is_missing_local_authority(decision: object) -> bool:
    """Return whether ``decision`` found no local authority and selected no amount."""
    return str(getattr(decision, "divergence", "")) == "missing" and getattr(decision, "selected_amount", None) is None


def _source_periods(source: object) -> tuple[Period, ...]:
    """Return the canonical periods one evidence source names.

    A carrier whose periods are not canonical cannot ground a zero, and reading
    it as if it were would answer the authority question from an unknown shape.
    """
    raw_periods = getattr(source, "source_periods", None)
    if not raw_periods:
        return ()
    if not is_object_collection(raw_periods):
        raise InternalInvariantError(
            "iva wallet evidence source periods are not a collection",
            precondition_verdict=internal_invariant_verdict("iva_wallet_evidence.source_periods_collection"),
        )
    periods: list[Period] = []
    for period in raw_periods:
        if not isinstance(period, Period):
            raise InternalInvariantError(
                "iva wallet evidence source names a non-canonical period",
                precondition_verdict=internal_invariant_verdict("iva_wallet_evidence.source_period_canonical"),
            )
        periods.append(period)
    return tuple(periods)


def _source_proves_concrete_zero_authority(source: object, *, target_start: date | None) -> bool:
    amount = getattr(source, "amount", None)
    if amount is None or Decimal(amount) != Decimal("0"):
        return False
    source_kind = str(getattr(source, "source_kind", ""))
    if source_kind == "aeat_wallet":
        return getattr(source, "captured_at", None) is not None
    if source_kind not in _LOCAL_EVIDENCE_SOURCE_KINDS:
        return False
    periods = _source_periods(source)
    # Local evidence proves a zero only from periods before the target; a
    # source naming the target period itself is the first-period placeholder,
    # which only the activity start can ground.
    return bool(periods) and (target_start is None or all(period.start_date < target_start for period in periods))


def decision_has_concrete_zero_authority(decision: object) -> bool:
    """Return whether ``decision`` selects zero on evidence that concretely proves it."""
    selected_amount = getattr(decision, "selected_amount", None)
    if selected_amount is None or Decimal(selected_amount) != Decimal("0"):
        return False
    target_period = getattr(decision, "target_period", None)
    target_start = target_period.start_date if target_period is not None else None
    return any(
        _source_proves_concrete_zero_authority(source, target_start=target_start)
        for source in getattr(decision, "authority_sources", ()) or ()
    )


def non_blocking_concrete_zero_authority_decision(
    decision: IvaCompensationReconciliationDecision,
) -> IvaCompensationReconciliationDecision:
    """Return ``decision`` as a non-blocking zero matching the local authority."""
    return decision.model_copy(
        update={
            "selected_authority": "local_recurrence",
            "selected_amount": Decimal("0"),
            "divergence": "match",
            "blocked": False,
            "stale_wallet": False,
            "reason_identity": IvaCompensationDecisionReason.CALLER_ZERO_MATCHES_LOCAL_AUTHORITY,
        },
    )


def save_iva_compensation_decision(
    decision: IvaCompensationReconciliationDecision,
    *,
    repository: IvaWalletDecisionRepositoryProtocol,
) -> None:
    """Persist ``decision`` in the IVA wallet decision ``repository``."""
    repository.save_decision(decision)


def require_first_period_zero_decision_grounded(
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    decision: IvaCompensationReconciliationDecision,
    *,
    subject_leaf_key: str,
    profile_values: Mapping[str, str] | None,
) -> IvaCompensationReconciliationDecision:
    """Fail closed unless a first-period-zero decision is profile/registry-grounded.

    ``snapshot`` is the :class:`RegistrySnapshot` it uses.
    """
    if not decision_is_first_period_zero(decision):
        return decision
    if decision_has_concrete_zero_authority(decision):
        return decision
    if _activity_start_proves_first_iva_period(snapshot, profile_values=profile_values):
        return decision.model_copy(
            update={
                "reason_identity": (IvaCompensationDecisionReason.FIRST_PERIOD_ZERO_ACTIVITY_START_UNCONTRASTED),
            },
        )
    raise_iva_wallet_precondition(
        subject_leaf_key=subject_leaf_key,
        reason_code="first_period_zero_ungrounded",
        translated_message="application.modelo.errors.iva_wallet_first_period_zero_ungrounded",
        evidence_values={
            "divergence_code": "first_period_zero",
            "concrete_zero_authority": False,
            "activity_start_proof": False,
        },
        context={
            "divergence": "first_period_zero_unproven",
            "reason": "first_period_zero_ungrounded",
        },
        carry_period=work_unit.period,
        carry_revision=snapshot.revision,
    )


def _activity_start_proves_first_iva_period(
    snapshot: RegistrySnapshot,
    *,
    profile_values: Mapping[str, str] | None,
) -> bool:
    """Return whether the profile proves no prior IVA-compensation obligation existed."""
    from ..calculations.cross_period_clean_state import (
        cross_period_dependency_requirements,
        partition_cross_period_requirements_by_activity_start,
    )

    activity_start_date = _activity_start_date_from_path_values(profile_values)
    if activity_start_date is None:
        return False
    requirements = tuple(
        requirement
        for requirement in cross_period_dependency_requirements(snapshot)
        if requirement.source_modelo == form_for_role("iva.periodic")
        and M303_PRIOR_COMPENSATION_ORIGIN_IDS.intersection(requirement.origin_ids)
    )
    if not requirements:
        return False
    partition = partition_cross_period_requirements_by_activity_start(
        requirements,
        activity_start_date=activity_start_date,
    )
    return bool(partition.suppressed) and not partition.in_scope


@dataclass(frozen=True, slots=True)
class _PersistedWalletEvidence:
    """The original captured wallet operands retained by a persisted decision."""

    taxpayer_nif: str
    target_year: int
    target_period: Period
    total_pending: Decimal
    source_url: str
    captured_at: datetime


def _wallet_evidence_from_decision(
    decision: IvaCompensationReconciliationDecision,
) -> IvaCompensationWalletObservationProtocol | None:
    if decision.wallet_amount is None or decision.wallet_captured_at is None:
        return None
    sources = [source for source in decision.authority_sources if source.source_kind == "aeat_wallet"]
    if len(sources) != 1 or sources[0].amount != decision.wallet_amount:
        return None
    return _PersistedWalletEvidence(
        taxpayer_nif=decision.taxpayer_nif,
        target_year=decision.target_year,
        target_period=decision.target_period,
        total_pending=decision.wallet_amount,
        source_url=sources[0].source_locator,
        captured_at=decision.wallet_captured_at,
    )


def reconcile_local_iva_compensation(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
    repository: IvaWalletDecisionRepositoryProtocol,
    observation_repository: CalculationObservationRepositoryProtocol,
    history_repository: IvaCompensationHistoryRepositoryProtocol,
    persist: bool,
    profile_values: Mapping[str, str] | None,
    wallet: IvaCompensationWalletObservationProtocol | None = None,
    evaluated_at: datetime | None = None,
    prior_calculations: PriorModeloCalculations | None = None,
) -> IvaCompensationReconciliationDecision | None:
    """Derive the local-authority decision for a Modelo 303 ``work_unit``, persisting it when asked.

    ``snapshot`` is the :class:`RegistrySnapshot` it uses.
    """
    if work_unit.modelo != form_for_role("iva.periodic"):
        return None
    taxpayer_nif = taxpayer_nif_from_path_values(profile_values)
    if taxpayer_nif is None:
        return None
    from ..calculations.binding_prefill import BindingPrefillReport
    from ..calculations.iva_wallet_reconciliation import reconcile_modelo_303_iva_compensation

    evidence = prior_period_carry_evidence(
        work_unit,
        snapshot=snapshot,
        operation=operation,
        repository=observation_repository,
        history_repository=history_repository,
        # The taxpayer's own calculation stands in only where AEAT's wallet is
        # absent too; a wallet is the authority, never checked against it.
        prior_calculations=prior_calculations if wallet is None else None,
        profile_values=profile_values,
    )
    report = reconcile_modelo_303_iva_compensation(
        snapshot,
        taxpayer_nif=taxpayer_nif,
        wallet=wallet,
        repository=observation_repository,
        decision_repository=repository,
        operation=operation,
        local_recurrence=evidence.recurrence,
        prefill_report=BindingPrefillReport(prefilled=(), binding_values={}),
        # A stored prior-period observation this build cannot use is NOT an
        # absence. Its presence proves the taxpayer had a prior Modelo 303
        # period, which is the exact fact the activity-start proof asserts did
        # not exist, so it can never ground a first-period zero. Only a genuine
        # absence reaches the activity-start question. This previously read the
        # activity-start proof alone, and an unreadable envelope became a proven
        # zero on the compensación.
        treat_absent_recurrence_as_first_period=(
            not evidence.prior_period_observation_found
            and _activity_start_proves_first_iva_period(snapshot, profile_values=profile_values)
        ),
        # The caller is the only party that can tell having found nothing from
        # having found a record it could not read. Without this the no-authority
        # outcome states that nothing is available while the taxpayer's own
        # prior record sits in the store.
        local_evidence_found_but_unusable=(evidence.prior_period_observation_found and evidence.recurrence is None),
        local_calculation_refusal=evidence.local_calculation_refusal,
        persist=False,
        decided_at=evaluated_at,
    )
    decision = require_first_period_zero_decision_grounded(
        work_unit,
        snapshot,
        report.decision,
        subject_leaf_key="modelo.work.calculate",
        profile_values=profile_values,
    )
    if persist and not decision.blocked:
        save_iva_compensation_decision(decision, repository=repository)
    return decision
