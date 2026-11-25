"""Modelo IVA wallet gate for calculation and filing lifecycle checks.

Modelo 303 prior-compensation belongs to the IVA wallet authority, not to the
generic previous-filing source mesh. This module uses the calculation
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot` and
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision` to route the wallet
decision into the prior-compensation binding, then checks a persisted
:class:`~cadrumo.domain.iva_compensation.reconciliation.IvaCompensationReconciliationDecision`
against the exported or filed
:class:`~CalculationRevision`.

The gate is deliberately repository-backed: transient wallet decisions cannot
feed the Modelo 303 engine unless the same decision is already present in
:class:`~cadrumo.application.calculations.observations_repository.IvaWalletDecisionRepositoryProtocol` for the
work-unit taxpayer and period. Calculation, verification, internal filing, and
export all replay this authority instead of trusting a caller-provided binding
value for casilla 110. Blocked, missing, stale, target-mismatched, or
amount-mismatched decisions raise
:class:`~cadrumo.application.modelo.iva_wallet_refusal.ModeloIvaWalletReconciliationBlockedError`
before a revision, filing record, or fichero-BOE artefact can be persisted.

The only lazy path is local-authority derivation for a bucket-scoped
:class:`~WorkUnit`: it can persist a non-blocking local
recurrence decision, and a ``first_period_zero`` decision is accepted only when
profile activity-start evidence and the
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot` prove every prior
Modelo 303 compensation dependency is pre-activity.

See Also:
    :func:`~cadrumo.application.calculations.iva_wallet_reconciliation.reconcile_modelo_303_iva_compensation`:
        Builds and persists the reconciliation decision consumed here.
    :class:`~cadrumo.application.calculations.iva_wallet_reconciliation.IvaWalletDecisionSourceResolver`:
        Projects a non-blocking decision into calculation binding values.
    ``cadrumo.application.modelo.verification_actions._require_cross_period_clean_state``:
        Treats matching IVA-wallet authority as the Modelo 303 compensation gate.
    :func:`~cadrumo.application.modelo.export.export_modelo_revision`:
        Replays this gate before writing a Modelo 303 export artefact.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_PENDING_PRIOR_CASILLA,
)
from ...domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ...domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.work_unit import WorkUnit
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ..calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    IvaWalletDecisionRepositoryProtocol,
)
from ..user_profile.projections import profile_path_values_for_bucket
from .iva_wallet_binding import M303_PRIOR_COMPENSATION_BINDING_ID
from .iva_wallet_decision_authority import (
    decision_has_concrete_zero_authority,
    decision_is_first_period_zero,
    decision_is_missing_local_authority,
    load_persisted_iva_compensation_decision_for_work_unit,
    non_blocking_concrete_zero_authority_decision,
    persisted_decision_for_calculation,
    reconcile_local_iva_compensation,
    registry_snapshot_for_work_unit,
    require_first_period_zero_decision_grounded,
    save_iva_compensation_decision,
)
from .iva_wallet_prior_period import PriorModeloCalculations
from .iva_wallet_refusal import blocked_iva_wallet_refusal, iva_wallet_door, raise_iva_wallet_precondition
from .iva_wallet_values import revision_iva_compensation_amount

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


def _resolve_caller_supplied_prior_compensation(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
    repository: IvaWalletDecisionRepositoryProtocol,
    observation_repository: CalculationObservationRepositoryProtocol,
    history_repository: IvaCompensationHistoryRepositoryProtocol,
    supplied_amounts: tuple[Decimal, ...],
    profile_values: Mapping[str, str] | None,
    evaluated_at: datetime | None = None,
) -> IvaCompensationReconciliationDecision | None:
    decision = reconcile_local_iva_compensation(
        work_unit,
        snapshot=snapshot,
        operation=operation,
        repository=repository,
        observation_repository=observation_repository,
        history_repository=history_repository,
        persist=False,
        profile_values=profile_values,
        evaluated_at=evaluated_at,
    )
    if decision is None:
        return None
    if decision_is_missing_local_authority(decision):
        _require_no_unproven_prior_amounts(decision, supplied_amounts, revision=snapshot.revision)
        return None
    if decision_has_concrete_zero_authority(decision):
        decision = _accept_only_zero_supplied_amounts(decision, supplied_amounts)
    if not decision.blocked:
        decision = require_first_period_zero_decision_grounded(
            work_unit,
            snapshot,
            decision,
            subject_leaf_key="modelo.work.calculate",
            profile_values=profile_values,
        )
        save_iva_compensation_decision(decision, repository=repository)
    return decision


def _require_no_unproven_prior_amounts(
    decision: IvaCompensationReconciliationDecision,
    supplied_amounts: tuple[Decimal, ...],
    *,
    revision: ModeloRevision,
) -> None:
    if not any(amount != Decimal("0") for amount in supplied_amounts):
        return
    blocked_reason, blocked_message = blocked_iva_wallet_refusal(decision)
    raise_iva_wallet_precondition(
        subject_leaf_key="modelo.work.calculate",
        reason_code=blocked_reason,
        translated_message=blocked_message,
        evidence_values={
            "binding_id": M303_PRIOR_COMPENSATION_BINDING_ID,
            "nonzero_amount_count": sum(amount != Decimal("0") for amount in supplied_amounts),
            "wallet_blocked": True,
        },
        context={"divergence": str(decision.divergence), "reason": blocked_reason},
        carry_period=decision.target_period,
        local_amount=decision.local_recurrence_amount,
        carry_revision=revision,
    )


def _accept_only_zero_supplied_amounts(
    decision: IvaCompensationReconciliationDecision,
    supplied_amounts: tuple[Decimal, ...],
) -> IvaCompensationReconciliationDecision:
    if any(amount != Decimal("0") for amount in supplied_amounts):
        raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="caller_binding_conflict",
            translated_message="application.modelo.errors.iva_wallet_caller_binding_conflict",
            evidence_values={
                "binding_id": M303_PRIOR_COMPENSATION_BINDING_ID,
                "nonzero_amount_count": sum(amount != Decimal("0") for amount in supplied_amounts),
            },
        )
    return non_blocking_concrete_zero_authority_decision(decision)


def resolve_iva_compensation_decision_for_calculation(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
    supplied_decision: object | None,
    observation_repository: CalculationObservationRepositoryProtocol,
    history_repository: IvaCompensationHistoryRepositoryProtocol,
    repository: IvaWalletDecisionRepositoryProtocol,
    binding_values: Mapping[BindingId, Decimal] | None,
    backend_binding_values: Mapping[BindingId, Decimal] | None,
    casilla_inputs: Mapping[CasillaId, Decimal] | None,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
    profile_values: Mapping[str, str] | None,
    evaluated_at: datetime | None = None,
    prior_calculations: PriorModeloCalculations | None = None,
) -> object | None:
    """Resolve the Modelo 303 IVA wallet decision that may feed calculation bindings.

    The :class:`~WorkUnit` fixes the bucket, taxpayer profile
    lookup, target period, and registry revision; the
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot` is passed to the
    lazy reconciliation path when no caller-supplied or persisted wallet decision
    exists. A supplied decision must match the persisted
    :class:`~cadrumo.domain.iva_compensation.reconciliation.IvaCompensationReconciliationDecision`.
    If the caller supplied a prior-compensation binding or casilla without a
    decision, the function tries only the local-authority zero path. A nonzero
    supplied value with no usable required authority is a terminal no-action
    refusal; an otherwise ungrounded zero still returns ``None`` for the
    first-profile seed/reconcile guidance. ``profile_values`` is the path
    projection of the profile the calculation already loaded, or ``None`` when
    it has none. ``prior_calculations`` reads the taxpayer's own calculation of
    the previous period where nothing filed records it; its credit then feeds
    this period at calculation grade only.
    """
    if supplied_decision is not None:
        require_persisted_iva_compensation_decision_for_work_unit(
            work_unit,
            supplied_decision=supplied_decision,
            snapshot=snapshot,
            repository=repository,
            profile_values=profile_values,
        )
    # A blocked decision is refused right after this returns, so the
    # calculation stores none: the refusal then writes nothing and settles with
    # no effect. Verification, filing and export still store a blocked refresh.
    persisted = persisted_decision_for_calculation(
        work_unit,
        snapshot=snapshot,
        operation=operation,
        repository=repository,
        observation_repository=observation_repository,
        history_repository=history_repository,
        profile_values=profile_values,
        evaluated_at=evaluated_at,
        persist_blocked=False,
        prior_calculations=prior_calculations,
    )
    if persisted is not None:
        return persisted
    supplied_amounts = _supplied_prior_compensation_amounts(
        binding_values=binding_values,
        backend_binding_values=backend_binding_values,
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
    )
    if supplied_amounts:
        return _resolve_caller_supplied_prior_compensation(
            work_unit,
            snapshot=snapshot,
            operation=operation,
            repository=repository,
            observation_repository=observation_repository,
            history_repository=history_repository,
            supplied_amounts=supplied_amounts,
            profile_values=profile_values,
            evaluated_at=evaluated_at,
        )
    return reconcile_local_iva_compensation(
        work_unit,
        snapshot=snapshot,
        operation=operation,
        repository=repository,
        observation_repository=observation_repository,
        history_repository=history_repository,
        persist=True,
        profile_values=profile_values,
        evaluated_at=evaluated_at,
        prior_calculations=prior_calculations,
    )


def require_persisted_iva_compensation_decision_for_work_unit(
    work_unit: WorkUnit,
    *,
    supplied_decision: object,
    snapshot: RegistrySnapshot | None = None,
    repository: IvaWalletDecisionRepositoryProtocol,
    profile_values: Mapping[str, str] | None,
) -> object:
    """Require a supplied Modelo 303 wallet decision to match the persisted decision.

    The optional :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
    grounds first-period-zero decisions; when omitted, the function resolves the
    snapshot from the supplied :class:`~WorkUnit`. This check
    prevents a transient or stale
    :class:`~cadrumo.domain.iva_compensation.reconciliation.IvaCompensationReconciliationDecision`
    from feeding calculation values unless the repository contains the same
    authority record.
    """
    if work_unit.modelo != form_for_role("iva.periodic"):
        return supplied_decision
    persisted = load_persisted_iva_compensation_decision_for_work_unit(
        work_unit,
        repository=repository,
        profile_values=profile_values,
    )
    if persisted is None:
        raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="not_seeded",
            translated_message="application.modelo.errors.iva_wallet_not_seeded",
            evidence_values={"persisted_decision_present": False},
            carry_period=work_unit.period,
            carry_revision=(
                snapshot or registry_snapshot_for_work_unit(work_unit, subject_leaf_key="modelo.work.calculate")
            ).revision,
        )
    if persisted != supplied_decision:
        raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="supplied_decision_mismatch",
            translated_message="application.modelo.errors.iva_wallet_supplied_decision_mismatch",
            evidence_values={"persisted_decision_match": False},
        )
    if decision_is_first_period_zero(persisted):
        return require_first_period_zero_decision_grounded(
            work_unit,
            snapshot
            or registry_snapshot_for_work_unit(
                work_unit,
                subject_leaf_key="modelo.work.calculate",
            ),
            persisted,
            subject_leaf_key="modelo.work.calculate",
            profile_values=profile_values,
        )
    return persisted


def _supplied_prior_compensation_amounts(
    *,
    binding_values: Mapping[BindingId, Decimal] | None,
    backend_binding_values: Mapping[BindingId, Decimal] | None,
    casilla_inputs: Mapping[CasillaId, Decimal] | None,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
) -> tuple[Decimal, ...]:
    """Return supplied Modelo 303 prior-compensation amounts from all input channels."""
    binding_id = M303_PRIOR_COMPENSATION_BINDING_ID
    casilla_id = M303_COMPENSATION_PENDING_PRIOR_CASILLA
    values = (
        dict(binding_values or {}).get(binding_id),
        dict(backend_binding_values or {}).get(binding_id),
        dict(casilla_inputs or {}).get(casilla_id),
        dict(backend_casilla_inputs or {}).get(casilla_id),
    )
    return tuple(Decimal(value) for value in values if value is not None)


def require_persisted_iva_compensation_decision_matches_revision(
    work_unit: WorkUnit,
    revision: CalculationRevision,
    *,
    repository: IvaWalletDecisionRepositoryProtocol,
    observation_repository: CalculationObservationRepositoryProtocol,
    history_repository: IvaCompensationHistoryRepositoryProtocol,
    operation: PinnedAuthorityOperation,
    subject_leaf_key: str = "modelo.export",
    evaluated_at: datetime | None = None,
) -> IvaCompensationReconciliationDecision | None:
    """Return the IVA compensation decision when it matches the revision.

    The check reads the supplied
    :class:`~CalculationRevision` and blocks verification,
    internal filing, or export when its Modelo 303
    prior-compensation amount differs from the persisted wallet decision, when
    the decision targets another period, or when the decision is blocked/missing.
    Non-Modelo 303 work units return ``None`` because the IVA wallet authority
    owns only Modelo 303 prior compensation.

    Returns:
        The matching :class:`IvaCompensationReconciliationDecision` for Modelo
        303, or ``None`` for non-Modelo 303 work units.
    """
    with iva_wallet_door(work_unit.work_unit_id):
        return _persisted_decision_matching_revision(
            work_unit,
            revision,
            repository=repository,
            observation_repository=observation_repository,
            history_repository=history_repository,
            operation=operation,
            subject_leaf_key=subject_leaf_key,
            evaluated_at=evaluated_at,
        )


def _persisted_decision_matching_revision(
    work_unit: WorkUnit,
    revision: CalculationRevision,
    *,
    repository: IvaWalletDecisionRepositoryProtocol,
    observation_repository: CalculationObservationRepositoryProtocol,
    history_repository: IvaCompensationHistoryRepositoryProtocol,
    operation: PinnedAuthorityOperation,
    subject_leaf_key: str = "modelo.export",
    evaluated_at: datetime | None = None,
) -> IvaCompensationReconciliationDecision | None:
    """The check behind :func:`require_persisted_iva_compensation_decision_matches_revision`, without its door."""
    if work_unit.modelo != form_for_role("iva.periodic"):
        return None
    profile_values = profile_path_values_for_bucket(work_unit.bucket_id)
    snapshot = registry_snapshot_for_work_unit(work_unit, subject_leaf_key=subject_leaf_key, operation=operation)
    decision = persisted_decision_for_calculation(
        work_unit,
        snapshot=snapshot,
        operation=operation,
        repository=repository,
        observation_repository=observation_repository,
        history_repository=history_repository,
        profile_values=profile_values,
        evaluated_at=evaluated_at,
    )
    if decision is None:
        raise_iva_wallet_precondition(
            subject_leaf_key=subject_leaf_key,
            reason_code="not_seeded",
            translated_message="application.modelo.errors.iva_wallet_not_seeded",
            evidence_values={"persisted_decision_present": False},
            carry_period=work_unit.period,
            carry_revision=snapshot.revision,
        )
    if decision.blocked:
        blocked_reason, blocked_message = blocked_iva_wallet_refusal(decision)
        raise_iva_wallet_precondition(
            subject_leaf_key=subject_leaf_key,
            reason_code=blocked_reason,
            translated_message=blocked_message,
            evidence_values={
                "divergence_code": str(decision.divergence),
                "wallet_blocked": True,
            },
            context={"divergence": str(decision.divergence), "reason": blocked_reason},
            carry_period=work_unit.period,
            local_amount=decision.local_recurrence_amount,
            carry_revision=snapshot.revision,
        )
    if decision.target_period != work_unit.period:
        raise_iva_wallet_precondition(
            subject_leaf_key=subject_leaf_key,
            reason_code="target_mismatch",
            translated_message="application.modelo.errors.iva_wallet_blocked",
            evidence_values={
                "decision_target_year": decision.target_year,
                "decision_target_period": decision.target_period.registry_token,
                "work_unit_filing_year": work_unit.filing_year,
                "work_unit_period": work_unit.period.registry_token,
            },
            context={
                "divergence": "authority_target_mismatch",
                "reason": "target_mismatch",
            },
        )
    if decision.selected_authority == "local_calculation":
        raise_iva_wallet_precondition(
            subject_leaf_key=subject_leaf_key,
            reason_code="local_calculation_only",
            translated_message="application.iva_wallet.decision_reason.local_calculation_only",
            evidence_values={"divergence_code": str(decision.divergence), "wallet_blocked": True},
            context={"divergence": str(decision.divergence), "reason": "local_calculation_only"},
        )
    if decision_is_first_period_zero(decision):
        require_first_period_zero_decision_grounded(
            work_unit,
            registry_snapshot_for_work_unit(
                work_unit,
                subject_leaf_key=subject_leaf_key,
                operation=operation,
            ),
            decision,
            subject_leaf_key=subject_leaf_key,
            profile_values=profile_values,
        )
    if decision.selected_amount is None:
        raise_iva_wallet_precondition(
            subject_leaf_key=subject_leaf_key,
            reason_code="selected_amount_missing",
            translated_message="application.modelo.errors.iva_wallet_blocked",
            evidence_values={"selected_amount_present": False},
            context={
                "divergence": "authority_missing_amount",
                "reason": "selected_amount_missing",
            },
        )
    revision_amount = revision_iva_compensation_amount(revision)
    if revision_amount is None:
        raise_iva_wallet_precondition(
            subject_leaf_key=subject_leaf_key,
            reason_code="revision_amount_missing",
            translated_message="application.modelo.errors.iva_wallet_revision_amount_missing",
            evidence_values={
                "binding_id": M303_PRIOR_COMPENSATION_BINDING_ID,
                "casilla_id": M303_COMPENSATION_PENDING_PRIOR_CASILLA,
                "revision_amount_present": False,
            },
            context={
                "divergence": "authority_revision_missing_amount",
                "reason": "revision_amount_missing",
            },
        )
    if Decimal(decision.selected_amount) != revision_amount:
        raise_iva_wallet_precondition(
            subject_leaf_key=subject_leaf_key,
            reason_code="amount_mismatch",
            translated_message="application.modelo.errors.iva_wallet_amount_mismatch",
            evidence_values={
                "decision_amount": Decimal(decision.selected_amount),
                "revision_amount": revision_amount,
            },
            context={
                "divergence": "authority_amount_mismatch",
                "reason": "amount_mismatch",
            },
        )
    return decision
