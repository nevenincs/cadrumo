"""Modelo IVA wallet gate for calculation and filing lifecycle checks.

Modelo 303 prior-compensation belongs to the IVA wallet authority, not to the
generic previous-filing source mesh. This module uses the calculation
:class:`~cadrumo.domain.calculations.registry.RegistrySnapshot` and
:class:`~cadrumo.domain.calculations.registry.ModeloRevision` to route the wallet
decision into the prior-compensation binding, then checks a persisted
:class:`~cadrumo.domain.iva_compensation.reconciliation.IvaCompensationReconciliationDecision`
against the exported or filed
:class:`~CalculationRevision`.

The gate is deliberately repository-backed: transient wallet decisions cannot
feed the Modelo 303 engine unless the same decision is already present in
:class:`~cadrumo.application.calculations.IvaWalletDecisionRepository` for the
work-unit taxpayer and period. Calculation, verification, internal filing, and
export all replay this authority instead of trusting a caller-provided binding
value for casilla 110. Blocked, missing, stale, target-mismatched, or
amount-mismatched decisions raise
:class:`~cadrumo.application.modelo.ModeloIvaWalletReconciliationBlockedError`
before a revision, filing record, or fichero-BOE artefact can be persisted.

The only lazy path is local-authority derivation for a bucket-scoped
:class:`~WorkUnit`: it can persist a non-blocking local
recurrence decision, and a ``first_period_zero`` decision is accepted only when
profile activity-start evidence and the
:class:`~cadrumo.domain.calculations.registry.RegistrySnapshot` prove every prior
Modelo 303 compensation dependency is pre-activity.

See Also:
    :func:`~cadrumo.application.calculations.reconcile_modelo_303_iva_compensation`:
        Builds and persists the reconciliation decision consumed here.
    :class:`~cadrumo.application.calculations.IvaWalletDecisionSourceResolver`:
        Projects a non-blocking decision into calculation binding values.
    :func:`~cadrumo.application.modelo.verification_actions._require_cross_period_clean_state`:
        Treats matching IVA-wallet authority as the Modelo 303 compensation gate.
    :func:`~cadrumo.application.modelo.export.export_modelo_revision`:
        Replays this gate before writing a Modelo 303 export artefact.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Final, NamedTuple, Never, override

from ...core.casilla_id import CasillaId
from ...core.identity import same_tax_identifier
from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.period import Period as _Period
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.bindings_previous_filing import previous_filing_observation_requirements
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import (
    ModeloRevision,
    RegistrySnapshot,
)
from ...domain.iva_compensation.reconciliation import (
    IvaCompensationDecisionReason,
    IvaCompensationReconciliationDecision,
)
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.work_unit import WorkUnit
from ..calculations._revision_carry_gate import revision_carry_outcome
from ..calculations.binding_prefill import LocalIvaCompensationRecurrence
from ..calculations.iva_compensation_casillas import (
    M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
    M303_DISPONIBLE_CASILLA,
)
from ..calculations.m303_carry_ingress import M303CarryIngressError, validate_normalized_m303_carry_observation_envelope
from ..calculations.observations_repository import CalculationObservationRepository, IvaWalletDecisionRepository
from .action_errors import ModeloPreconditionErrorMixin
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure

_M303_PRIOR_COMPENSATION_BINDING_ID: BindingId = "modelo-303-compensacion-pendiente-anteriores"
_M303_PRIOR_COMPENSATION_ORIGIN_IDS: Final[frozenset[str]] = frozenset(
    {
        _M303_PRIOR_COMPENSATION_BINDING_ID,
        "modelo-303-rel-self-compensacion-anteriores",
    },
)


_M303_PRIOR_COMPENSATION_CASILLA_ID: Final[CasillaId] = M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA
_M303_AVAILABLE_COMPENSATION_CASILLA_ID: Final[CasillaId] = M303_DISPONIBLE_CASILLA


class _WalletBindingTarget(NamedTuple):
    bucket_id: str
    modelo: str
    filing_year: int
    period: _Period
    revision: ModeloRevision


class _PriorCompensationInputs(NamedTuple):
    caller_binding_value: Decimal | None
    backend_binding_value: Decimal | None
    caller_casilla_value: Decimal | None
    backend_casilla_value: Decimal | None


class ModeloIvaWalletReconciliationBlockedError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when Modelo 303 calculation is blocked by IVA wallet reconciliation."""

    def __init__(
        self,
        *,
        translated_message: str,
        precondition_failure: ModeloPreconditionFailure,
        context: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(
            context=context,
            translated_message=translated_message,
            precondition_failure=precondition_failure,
        )

    @property
    @override
    def precondition_failure(self) -> ModeloPreconditionFailure:
        """Return the required application-owned IVA-wallet refusal verdict."""
        failure = super().precondition_failure
        assert failure is not None
        return failure


ModeloIvaWalletReconciliationBlocked = ModeloIvaWalletReconciliationBlockedError


def _blocked_refusal(decision: IvaCompensationReconciliationDecision) -> tuple[str, str]:
    """Name WHY a wallet decision blocks, and the message that says it.

    Returns the code AND its translated-message key together, because the two
    cannot be chosen independently: every neighbouring refusal in this module
    states a specific code and selects the message written for that case, and a
    site that picked a specific code while keeping the generic template would
    put a machine token in the ``%{reason}`` slot of a sentence meant for a
    person. That is what the blocked refusal did -- an operator read the same
    sentence for a stale wallet as for evidence that existed and could not be
    interpreted.

    The persisted reason is a closed locale-neutral identity. Every blocking
    identity selects its own translated message, so calculate and export expose
    the same specific cause as the history surface without domain-authored prose.
    """
    if decision.reason_identity is IvaCompensationDecisionReason.LOCAL_EVIDENCE_UNREADABLE:
        return "local_evidence_unreadable", "application.iva_wallet.decision_reason.local_evidence_unreadable"
    if decision.reason_identity is IvaCompensationDecisionReason.NO_USABLE_AUTHORITY:
        return "no_usable_authority", "application.iva_wallet.decision_reason.no_usable_authority"
    if decision.reason_identity is IvaCompensationDecisionReason.FILED_HISTORY_REQUIRES_OVERRIDE:
        return (
            "filed_history_requires_override",
            "application.iva_wallet.decision_reason.filed_history_requires_override",
        )
    if decision.reason_identity is IvaCompensationDecisionReason.LOCAL_RECURRENCE_REQUIRES_OVERRIDE:
        return (
            "local_recurrence_requires_override",
            "application.iva_wallet.decision_reason.local_recurrence_requires_override",
        )
    if decision.reason_identity is IvaCompensationDecisionReason.STALE_WALLET_NO_LOCAL_RECURRENCE:
        return (
            "stale_wallet_no_local_recurrence",
            "application.iva_wallet.decision_reason.stale_wallet_no_local_recurrence",
        )
    if decision.reason_identity is IvaCompensationDecisionReason.STALE_WALLET_LOCAL_RECURRENCE_REQUIRES_OVERRIDE:
        return (
            "stale_wallet_local_recurrence_requires_override",
            "application.iva_wallet.decision_reason.stale_wallet_local_recurrence_requires_override",
        )
    if decision.reason_identity is IvaCompensationDecisionReason.WALLET_LOCAL_RECURRENCE_DIVERGENCE:
        return (
            "wallet_local_recurrence_divergence",
            "application.iva_wallet.decision_reason.wallet_local_recurrence_divergence",
        )
    raise ValueError(
        f"blocked IVA wallet decision has non-blocking reason {decision.reason_identity.value!r}",
    )


def _raise_iva_wallet_precondition(
    *,
    subject_leaf_key: str,
    reason_code: str,
    translated_message: str,
    evidence_values: Mapping[str, str | int | bool | Decimal],
    context: Mapping[str, object] | None = None,
    cause: BaseException | None = None,
) -> Never:
    """Raise one locale-neutral IVA-wallet readiness refusal."""
    error = ModeloIvaWalletReconciliationBlocked(
        translated_message=translated_message,
        context=context,
        precondition_failure=build_modelo_precondition_failure(
            subject_leaf_key=subject_leaf_key,
            condition_id=f"{subject_leaf_key}.iva_wallet.ready",
            scenario_id=f"{subject_leaf_key}.iva_wallet.{reason_code}",
            evidence_id=f"{subject_leaf_key}.iva_wallet",
            evidence_values=evidence_values,
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        ),
    )
    if cause is not None:
        raise error from cause
    raise error


def _persisted_decision_for_calculation(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    repository: IvaWalletDecisionRepository | None,
) -> IvaCompensationReconciliationDecision | None:
    persisted = load_persisted_iva_compensation_decision_for_work_unit(work_unit, repository=repository)
    if persisted is None:
        return None
    refreshed = _refresh_local_iva_compensation_decision_if_evidence_changed(
        work_unit,
        snapshot=snapshot,
        decision=persisted,
        repository=repository,
    )
    return _require_first_period_zero_decision_grounded(
        work_unit,
        snapshot,
        refreshed,
        subject_leaf_key="modelo.work.calculate",
    )


def _resolve_caller_supplied_prior_compensation(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    repository: IvaWalletDecisionRepository | None,
    supplied_amounts: tuple[Decimal, ...],
) -> IvaCompensationReconciliationDecision | None:
    decision = lazily_reconcile_local_iva_compensation_for_work_unit(
        work_unit,
        snapshot=snapshot,
        repository=repository,
        persist=False,
    )
    if decision is None or _decision_is_missing_local_authority(decision):
        return None
    if _decision_has_concrete_zero_authority(decision):
        if any(amount != Decimal("0") for amount in supplied_amounts):
            _raise_iva_wallet_precondition(
                subject_leaf_key="modelo.work.calculate",
                reason_code="caller_binding_conflict",
                translated_message="application.modelo.errors.iva_wallet_caller_binding_conflict",
                evidence_values={
                    "binding_id": _M303_PRIOR_COMPENSATION_BINDING_ID,
                    "nonzero_amount_count": sum(amount != Decimal("0") for amount in supplied_amounts),
                },
            )
        decision = _non_blocking_concrete_zero_authority_decision(decision)
    if not decision.blocked:
        decision = _require_first_period_zero_decision_grounded(
            work_unit,
            snapshot,
            decision,
            subject_leaf_key="modelo.work.calculate",
        )
    _save_iva_compensation_decision(decision, repository=repository)
    return decision


def resolve_iva_compensation_decision_for_calculation(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    supplied_decision: object | None,
    repository: IvaWalletDecisionRepository | None,
    binding_values: Mapping[BindingId, Decimal] | None,
    backend_binding_values: Mapping[BindingId, Decimal] | None,
    casilla_inputs: Mapping[CasillaId, Decimal] | None,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
) -> object | None:
    """Resolve the Modelo 303 IVA wallet decision that may feed calculation bindings.

    The :class:`~WorkUnit` fixes the bucket, taxpayer profile
    lookup, target period, and registry revision; the
    :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot` is passed to the
    lazy reconciliation path when no caller-supplied or persisted wallet decision
    exists. A supplied decision must match the persisted
    :class:`~cadrumo.domain.iva_compensation.reconciliation.IvaCompensationReconciliationDecision`.
    If the caller supplied a prior-compensation binding or casilla without a
    decision, the function tries only the local-authority zero path and otherwise
    returns ``None`` so calculation surfaces the seed/reconcile guidance instead
    of silently trusting the value.
    """
    if supplied_decision is not None:
        return require_persisted_iva_compensation_decision_for_work_unit(
            work_unit,
            supplied_decision=supplied_decision,
            snapshot=snapshot,
            repository=repository,
        )
    persisted = _persisted_decision_for_calculation(
        work_unit,
        snapshot=snapshot,
        repository=repository,
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
            repository=repository,
            supplied_amounts=supplied_amounts,
        )
    return lazily_reconcile_local_iva_compensation_for_work_unit(
        work_unit,
        snapshot=snapshot,
        repository=repository,
    )


def _prior_compensation_inputs(
    *,
    casilla_inputs: Mapping[CasillaId, Decimal] | None,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
    caller_binding_values: Mapping[BindingId, Decimal],
    backend_binding_values: Mapping[BindingId, Decimal],
) -> _PriorCompensationInputs:
    return _PriorCompensationInputs(
        caller_binding_value=caller_binding_values.get(_M303_PRIOR_COMPENSATION_BINDING_ID),
        backend_binding_value=backend_binding_values.get(_M303_PRIOR_COMPENSATION_BINDING_ID),
        caller_casilla_value=dict(casilla_inputs or {}).get(_M303_PRIOR_COMPENSATION_CASILLA_ID),
        backend_casilla_value=dict(backend_casilla_inputs or {}).get(_M303_PRIOR_COMPENSATION_CASILLA_ID),
    )


def _require_decision_for_supplied_inputs(inputs: _PriorCompensationInputs) -> None:
    supplied_values = tuple(value for value in inputs if value is not None)
    if not supplied_values:
        return
    _raise_iva_wallet_precondition(
        subject_leaf_key="modelo.work.calculate",
        reason_code="not_seeded",
        translated_message="application.modelo.errors.iva_wallet_not_seeded",
        evidence_values={
            "binding_id": _M303_PRIOR_COMPENSATION_BINDING_ID,
            "casilla_id": _M303_PRIOR_COMPENSATION_CASILLA_ID,
            "supplied_value_count": len(supplied_values),
        },
    )


def _validated_decision_amount(
    decision: object,
    *,
    target: _WalletBindingTarget,
    taxpayer_nif: str | None,
) -> tuple[IvaCompensationReconciliationDecision, Decimal]:
    if not isinstance(decision, IvaCompensationReconciliationDecision):
        _raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="unsupported_decision_type",
            translated_message="application.modelo.errors.iva_wallet_unsupported_decision_type",
            evidence_values={"decision_type": type(decision).__name__},
            context={"decision_type": type(decision).__name__},
        )
    if decision.target_period != target.period:
        _raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="target_mismatch",
            translated_message="application.modelo.errors.iva_wallet_target_mismatch",
            evidence_values={
                "target_year": decision.target_year,
                "target_period": decision.target_period.registry_token,
                "filing_year": target.filing_year,
                "period": target.period.registry_token,
            },
            context={
                "target_year": decision.target_year,
                "target_period": decision.target_period.registry_token,
                "filing_year": target.filing_year,
                "period": target.period.registry_token,
            },
        )
    if taxpayer_nif is None:
        _raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="taxpayer_identity_missing",
            translated_message="application.modelo.errors.iva_wallet_taxpayer_identity_missing",
            evidence_values={"taxpayer_identity_present": False},
        )
    if not same_tax_identifier(decision.taxpayer_nif, taxpayer_nif):
        _raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="taxpayer_mismatch",
            translated_message="application.modelo.errors.iva_wallet_taxpayer_mismatch",
            evidence_values={"taxpayer_identity_match": False},
        )
    if decision.blocked:
        blocked_reason, blocked_message = _blocked_refusal(decision)
        _raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code=blocked_reason,
            translated_message=blocked_message,
            evidence_values={
                "divergence_code": str(decision.divergence),
                "wallet_blocked": True,
            },
            context={"divergence": str(decision.divergence), "reason": blocked_reason},
        )
    if decision.selected_amount is None:
        _raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="selected_amount_missing",
            translated_message="application.modelo.errors.iva_wallet_selected_amount_missing",
            evidence_values={"selected_amount_present": False},
        )
    return decision, Decimal(decision.selected_amount)


def _require_inputs_match_decision(
    inputs: _PriorCompensationInputs,
    selected: Decimal,
) -> None:
    if inputs.caller_binding_value is not None and Decimal(inputs.caller_binding_value) != selected:
        _raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="caller_binding_conflict",
            translated_message="application.modelo.errors.iva_wallet_caller_binding_conflict",
            evidence_values={
                "binding_id": _M303_PRIOR_COMPENSATION_BINDING_ID,
                "decision_amount": selected,
                "supplied_amount": Decimal(inputs.caller_binding_value),
            },
        )
    if inputs.caller_casilla_value is not None and Decimal(inputs.caller_casilla_value) != selected:
        _raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="caller_casilla_conflict",
            translated_message="application.modelo.errors.iva_wallet_caller_casilla_conflict",
            evidence_values={
                "casilla_id": _M303_PRIOR_COMPENSATION_CASILLA_ID,
                "decision_amount": selected,
                "supplied_amount": Decimal(inputs.caller_casilla_value),
            },
        )
    if inputs.backend_casilla_value is not None and Decimal(inputs.backend_casilla_value) != selected:
        _raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="backend_casilla_conflict",
            translated_message="application.modelo.errors.iva_wallet_backend_casilla_conflict",
            evidence_values={
                "casilla_id": _M303_PRIOR_COMPENSATION_CASILLA_ID,
                "decision_amount": selected,
                "supplied_amount": Decimal(inputs.backend_casilla_value),
            },
        )


def _apply_wallet_resolution(
    *,
    target: _WalletBindingTarget,
    decision: IvaCompensationReconciliationDecision,
    backend_binding_values: dict[BindingId, Decimal],
) -> None:
    from ..aggregation import CalculationSourceContext
    from ..calculations.iva_wallet_reconciliation import IvaWalletDecisionSourceResolver
    from .calculation_route import require_calculation_route_resolver

    resolver = IvaWalletDecisionSourceResolver(decision)
    require_calculation_route_resolver("pre_mesh", resolver)
    resolution = resolver.resolve(
        CalculationSourceContext(
            bucket_id=target.bucket_id,
            modelo=target.modelo,
            filing_year=target.filing_year,
            period=target.period,
            revision=target.revision,
        ),
    )
    backend_binding_values.update(resolution.binding_values)


def apply_iva_compensation_decision_binding(
    modelo: str,
    filing_year: int,
    period: _Period,
    *,
    bucket_id: str,
    revision: ModeloRevision,
    taxpayer_nif: str | None = None,
    casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    caller_binding_values: dict[BindingId, Decimal],
    backend_binding_values: dict[BindingId, Decimal],
    decision: object | None,
) -> None:
    """Apply a non-blocking IVA wallet decision to Modelo 303 binding values.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` defines the
    binding channel; the decision amount is written only after target period and
    taxpayer identity checks pass. Caller and backend inputs for the same binding
    or casilla must either match the selected decision amount or are refused as
    conflicts. The effective value is then produced through
    :class:`~cadrumo.application.calculations.IvaWalletDecisionSourceResolver`, so
    the calculation source mesh records the IVA-wallet provenance instead of a
    generic ``previous_filing`` source.
    """
    if modelo != Modelo.M303:
        return
    target = _WalletBindingTarget(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision=revision,
    )
    inputs = _prior_compensation_inputs(
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
        caller_binding_values=caller_binding_values,
        backend_binding_values=backend_binding_values,
    )
    if decision is None:
        _require_decision_for_supplied_inputs(inputs)
        return
    validated_decision, selected = _validated_decision_amount(
        decision,
        target=target,
        taxpayer_nif=taxpayer_nif,
    )
    _require_inputs_match_decision(inputs, selected)
    _apply_wallet_resolution(
        target=target,
        decision=validated_decision,
        backend_binding_values=backend_binding_values,
    )


def require_persisted_iva_compensation_decision_for_work_unit(
    work_unit: WorkUnit,
    *,
    supplied_decision: object,
    snapshot: RegistrySnapshot | None = None,
    repository: IvaWalletDecisionRepository | None = None,
) -> object:
    """Require a supplied Modelo 303 wallet decision to match the persisted decision.

    The optional :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot`
    grounds first-period-zero decisions; when omitted, the function resolves the
    snapshot from the supplied :class:`~WorkUnit`. This check
    prevents a transient or stale
    :class:`~cadrumo.domain.iva_compensation.reconciliation.IvaCompensationReconciliationDecision`
    from feeding calculation values unless the repository contains the same
    authority record.
    """
    if work_unit.modelo != Modelo.M303:
        return supplied_decision
    persisted = load_persisted_iva_compensation_decision_for_work_unit(work_unit, repository=repository)
    if persisted is None:
        _raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="not_seeded",
            translated_message="application.modelo.errors.iva_wallet_not_seeded",
            evidence_values={"persisted_decision_present": False},
        )
    if persisted != supplied_decision:
        _raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="supplied_decision_mismatch",
            translated_message="application.modelo.errors.iva_wallet_supplied_decision_mismatch",
            evidence_values={"persisted_decision_match": False},
        )
    if _decision_is_first_period_zero(persisted):
        return _require_first_period_zero_decision_grounded(
            work_unit,
            snapshot
            or _registry_snapshot_for_work_unit(
                work_unit,
                subject_leaf_key="modelo.work.calculate",
            ),
            persisted,
            subject_leaf_key="modelo.work.calculate",
        )
    return persisted


def load_persisted_iva_compensation_decision_for_work_unit(
    work_unit: WorkUnit,
    *,
    repository: IvaWalletDecisionRepository | None = None,
) -> IvaCompensationReconciliationDecision | None:
    """Load the persisted IVA compensation decision for a :class:`~WorkUnit`.

    Returns:
        The persisted :class:`IvaCompensationReconciliationDecision` for Modelo
        303 work units, or ``None`` when the work unit or bucket has no wallet
        authority record.
    """
    if work_unit.modelo != Modelo.M303:
        return None
    taxpayer_nif = taxpayer_nif_for_bucket(work_unit.bucket_id)
    if taxpayer_nif is None:
        return None
    if repository is None:
        from ..calculations.observations_repository import IvaWalletDecisionRepository

        repository = IvaWalletDecisionRepository()

    return repository.load_decision(
        taxpayer_nif,
        work_unit.period,
    )


def caller_supplied_prior_compensation_value(
    *,
    binding_values: Mapping[BindingId, Decimal] | None,
    backend_binding_values: Mapping[BindingId, Decimal] | None,
    casilla_inputs: Mapping[CasillaId, Decimal] | None,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
) -> bool:
    """Return whether a Modelo 303 prior-compensation value was explicitly supplied.

    The lazy local reconciliation must not fire when the operator or a backend
    resolver explicitly asserts the prior-compensation binding/casilla. That
    value needs reconciliation against a real wallet/seed decision, and the
    seed-verb guidance must surface.
    """
    return bool(
        _supplied_prior_compensation_amounts(
            binding_values=binding_values,
            backend_binding_values=backend_binding_values,
            casilla_inputs=casilla_inputs,
            backend_casilla_inputs=backend_casilla_inputs,
        ),
    )


def _supplied_prior_compensation_amounts(
    *,
    binding_values: Mapping[BindingId, Decimal] | None,
    backend_binding_values: Mapping[BindingId, Decimal] | None,
    casilla_inputs: Mapping[CasillaId, Decimal] | None,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
) -> tuple[Decimal, ...]:
    """Return supplied Modelo 303 prior-compensation amounts from all input channels."""
    binding_id = _M303_PRIOR_COMPENSATION_BINDING_ID
    casilla_id = _M303_PRIOR_COMPENSATION_CASILLA_ID
    values = (
        dict(binding_values or {}).get(binding_id),
        dict(backend_binding_values or {}).get(binding_id),
        dict(casilla_inputs or {}).get(casilla_id),
        dict(backend_casilla_inputs or {}).get(casilla_id),
    )
    return tuple(Decimal(value) for value in values if value is not None)


def _profile_path_values_for_bucket(bucket_id: str) -> dict[str, str] | None:
    """Return canonical user-profile path values for ``bucket_id``."""
    from ...domain.user_profile.errors import ProfileNotFoundError
    from ..user_profile.profile_record_repository import ProfileRecordRepository
    from ..user_profile.projections import record_to_path_values

    try:
        record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return None
    return record_to_path_values(record)


def _activity_start_date_for_modelo_profile(bucket_id: str) -> date | None:
    """Return the lifecycle profile's declared activity-start date, if parseable."""
    from ...core.parsing import parse_iso8601_date

    values = _profile_path_values_for_bucket(bucket_id)
    if values is None:
        return None
    try:
        return parse_iso8601_date(values.get("censo.activity_start_date"))
    except ValueError:
        return None


def _registry_snapshot_for_work_unit(
    work_unit: WorkUnit,
    *,
    subject_leaf_key: str,
) -> RegistrySnapshot:
    """Resolve the registry snapshot attached to ``work_unit``."""
    try:
        return bundled_authority().snapshot(
            str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    except (FileNotFoundError, RegistrySnapshotError) as exc:
        _raise_iva_wallet_precondition(
            subject_leaf_key=subject_leaf_key,
            reason_code="registry_snapshot_unavailable",
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


def _decision_is_first_period_zero(decision: object) -> bool:
    return str(getattr(decision, "divergence", "")) == "first_period_zero"


def _refresh_local_iva_compensation_decision_if_evidence_changed(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    decision: IvaCompensationReconciliationDecision,
    repository: IvaWalletDecisionRepository | None,
) -> IvaCompensationReconciliationDecision:
    if not (
        _decision_is_first_period_zero(decision)
        or _decision_is_missing_local_authority(decision)
        or _decision_uses_observation_envelope_recurrence(decision)
    ):
        return decision
    refreshed = lazily_reconcile_local_iva_compensation_for_work_unit(
        work_unit,
        snapshot=snapshot,
        repository=repository,
        persist=False,
    )
    if refreshed is None or _decision_replay_basis(refreshed) == _decision_replay_basis(decision):
        return decision
    _save_iva_compensation_decision(refreshed, repository=repository)
    return refreshed


def _decision_uses_observation_envelope_recurrence(decision: object) -> bool:
    """Whether a decision must revalidate the prior filed-envelope recurrence.

    A local envelope recurrence can be superseded or found invalid on a later
    encrypted read. Replay only re-evaluates the selected local filed-history
    authority, never a settled live-wallet or taxpayer-override decision whose
    arbitrary evidence locator might share this textual prefix.
    """
    if str(getattr(decision, "selected_authority", "")) not in {
        "local_recurrence",
        "filed_history",
    }:
        return False
    return any(
        str(getattr(source, "source_kind", "")) in {"local_recurrence", "filed_history_observation"}
        and str(getattr(source, "source_locator", "")).startswith("observation-envelope:")
        for source in getattr(decision, "authority_sources", ()) or ()
    )


def _decision_replay_basis(decision: IvaCompensationReconciliationDecision) -> tuple[object, ...]:
    return (
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


def _decision_is_missing_local_authority(decision: object) -> bool:
    return str(getattr(decision, "divergence", "")) == "missing" and getattr(decision, "selected_amount", None) is None


def _decision_has_concrete_zero_authority(decision: object) -> bool:
    selected_amount = getattr(decision, "selected_amount", None)
    if selected_amount is None or Decimal(selected_amount) != Decimal("0"):
        return False
    for source in getattr(decision, "authority_sources", ()) or ():
        amount = getattr(source, "amount", None)
        if amount is None or Decimal(amount) != Decimal("0"):
            continue
        source_kind = str(getattr(source, "source_kind", ""))
        if source_kind == "aeat_wallet" and getattr(source, "captured_at", None) is not None:
            return True
        if source_kind in {"local_recurrence", "filed_history_observation"} and tuple(
            getattr(source, "source_periods", ()) or (),
        ):
            return True
    return False


def _non_blocking_concrete_zero_authority_decision(
    decision: IvaCompensationReconciliationDecision,
) -> IvaCompensationReconciliationDecision:
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


def _save_iva_compensation_decision(
    decision: IvaCompensationReconciliationDecision,
    *,
    repository: IvaWalletDecisionRepository | None,
) -> None:
    repo = repository if repository is not None else IvaWalletDecisionRepository()
    repo.save_decision(decision)


def _require_first_period_zero_decision_grounded(
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    decision: IvaCompensationReconciliationDecision,
    *,
    subject_leaf_key: str,
) -> IvaCompensationReconciliationDecision:
    """Fail closed unless a first-period-zero decision is profile/registry-grounded."""
    if not _decision_is_first_period_zero(decision):
        return decision
    if _decision_has_concrete_zero_authority(decision):
        return decision
    if _activity_start_proves_first_iva_period(work_unit, snapshot):
        return decision.model_copy(
            update={
                "reason_identity": (IvaCompensationDecisionReason.FIRST_PERIOD_ZERO_ACTIVITY_START_UNCONTRASTED),
            },
        )
    _raise_iva_wallet_precondition(
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
    )


def _activity_start_proves_first_iva_period(work_unit: WorkUnit, snapshot: RegistrySnapshot) -> bool:
    """Return whether the profile proves no prior IVA-compensation obligation existed."""
    from ..calculations.cross_period_clean_state import (
        cross_period_dependency_requirements,
        partition_cross_period_requirements_by_activity_start,
    )

    activity_start_date = _activity_start_date_for_modelo_profile(work_unit.bucket_id)
    if activity_start_date is None:
        return False
    requirements = tuple(
        requirement
        for requirement in cross_period_dependency_requirements(snapshot)
        if requirement.source_modelo == Modelo.M303.value
        and _M303_PRIOR_COMPENSATION_ORIGIN_IDS.intersection(requirement.origin_ids)
    )
    if not requirements:
        return False
    partition = partition_cross_period_requirements_by_activity_start(
        requirements,
        activity_start_date=activity_start_date,
    )
    return bool(partition.suppressed) and not partition.in_scope


def lazily_reconcile_local_iva_compensation_for_work_unit(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    repository: IvaWalletDecisionRepository | None = None,
    persist: bool = True,
) -> IvaCompensationReconciliationDecision | None:
    """Auto-derive and persist the local-authority Modelo 303 compensation decision.

    Calculate's prior-compensation gate requires a persisted
    :class:`~cadrumo.domain.iva_compensation.reconciliation.IvaCompensationReconciliationDecision`.
    In the seed-only local authority case, the local Modelo 303 recurrence is the
    authority, so derive and persist the decision here instead of refusing
    calculation.

    The :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot` supplies the
    Modelo 303 revision context for the reconciliation service. Missing local
    recurrence is treated as ``first_period_zero`` only when the work unit's
    profile activity-start date scopes every Modelo 303 compensation dependency
    out as pre-activity; otherwise the reconciliation remains a blocking
    missing-authority state.
    """
    if work_unit.modelo != Modelo.M303:
        return None
    taxpayer_nif = taxpayer_nif_for_bucket(work_unit.bucket_id)
    if taxpayer_nif is None:
        return None
    from ..calculations.iva_wallet_reconciliation import reconcile_modelo_303_iva_compensation

    evidence = _prior_period_carry_evidence(work_unit, snapshot=snapshot)
    report = reconcile_modelo_303_iva_compensation(
        snapshot,
        taxpayer_nif=taxpayer_nif,
        wallet=None,
        decision_repository=repository,
        local_recurrence=evidence.recurrence,
        # The generic previous-filing reader can still read legacy envelopes for
        # unrelated consumers. The lazy Modelo 303 wallet gate instead admits
        # only the explicit disposition-aware envelope recurrence below.
        use_repository_local_recurrence=False,
        # A stored prior-period observation this build cannot use is NOT an
        # absence. Its presence proves the taxpayer had a prior Modelo 303
        # period, which is the exact fact the activity-start proof asserts did
        # not exist, so it can never ground a first-period zero. Only a genuine
        # absence reaches the activity-start question. This previously read the
        # activity-start proof alone, and an unreadable envelope became a proven
        # zero on the compensación.
        treat_absent_recurrence_as_first_period=(
            not evidence.prior_period_observation_found and _activity_start_proves_first_iva_period(work_unit, snapshot)
        ),
        # The caller is the only party that can tell having found nothing from
        # having found a record it could not read. Without this the no-authority
        # outcome states that nothing is available while the taxpayer's own
        # prior record sits in the store.
        local_evidence_found_but_unusable=(evidence.prior_period_observation_found and evidence.recurrence is None),
        persist=False,
    )
    decision = _require_first_period_zero_decision_grounded(
        work_unit,
        snapshot,
        report.decision,
        subject_leaf_key="modelo.work.calculate",
    )
    if persist:
        _save_iva_compensation_decision(decision, repository=repository)
    return decision


class _PriorPeriodCarryEvidence(NamedTuple):
    """What the wallet gate learned about the prior Modelo 303 period.

    ``recurrence`` is the usable carry projection, or ``None`` when this build
    cannot turn the stored observation into one.
    ``prior_period_observation_found`` answers the separate question of whether
    an observation for that period was persisted at all. An observation that
    exists but cannot be used still proves the period existed, so only a genuine
    absence may ground a first-period zero on the compensación.
    """

    recurrence: LocalIvaCompensationRecurrence | None
    prior_period_observation_found: bool


_NO_PRIOR_PERIOD_OBSERVATION: Final = _PriorPeriodCarryEvidence(
    recurrence=None,
    prior_period_observation_found=False,
)


def _prior_period_carry_evidence(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
) -> _PriorPeriodCarryEvidence:
    """Return validated filed M303 envelope recurrence, and whether one was stored.

    A prior calculation revision records a local calculation, not the filed
    declaration's disposition. It therefore cannot establish this recurrence.
    Missing, legacy, revision-refused, or disposition-conflicting envelopes
    yield no usable recurrence, so the wallet gate blocks rather than selecting
    an invented carry amount.

    Every case that found a stored observation and could not use it additionally
    reports it as present. Previously all of them returned a bare ``None``
    indistinguishable from a genuine absence, and the caller paired that ``None``
    with the profile's activity-start proof to reach ``first_period_zero`` -- so
    an envelope this build could not read was converted into a proven zero on the
    compensación, laundering a taxpayer's carried credit into nothing. The
    docstring claimed the gate blocked in those cases, which was true of every
    path except the one that mattered.
    """
    requirements = tuple(
        requirement
        for requirement in previous_filing_observation_requirements(
            snapshot.revision,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
        )
        if requirement.source_modelo == Modelo.M303.value
        and _M303_PRIOR_COMPENSATION_BINDING_ID in requirement.binding_ids
    )
    if len(requirements) != 1 or len(requirements[0].periods) != 1:
        return _NO_PRIOR_PERIOD_OBSERVATION
    requirement = requirements[0]
    source_period = (
        requirement.filing_periods[0]
        if requirement.filing_periods
        else _Period.from_year_and_code(requirement.filing_year, requirement.periods[0])
    )
    payload = CalculationObservationRepository().load_observation(Modelo.M303.value, source_period)
    if payload is None:
        return _NO_PRIOR_PERIOD_OBSERVATION
    found = _PriorPeriodCarryEvidence(recurrence=None, prior_period_observation_found=True)
    observation = payload.observation
    if (
        observation.filing_year != requirement.filing_year
        or observation.period != source_period.registry_token
        or revision_carry_outcome(
            payload.stamped_revision_id,
            source_modelo=observation.modelo,
            source_filing_year=observation.filing_year,
            source_period=observation.period,
        ).refused
    ):
        return found
    try:
        validated = validate_normalized_m303_carry_observation_envelope(payload)
    except M303CarryIngressError:
        return found
    amount = validated.observation.casilla_values.get(_M303_AVAILABLE_COMPENSATION_CASILLA_ID)
    if amount is None:
        return found
    return _PriorPeriodCarryEvidence(
        recurrence=LocalIvaCompensationRecurrence(
            binding_id=_M303_PRIOR_COMPENSATION_BINDING_ID,
            amount=amount,
            source_kind=str(validated.source_kind),
            source_modelo=Modelo.M303.value,
            source_filing_year=requirement.filing_year,
            source_periods=(source_period,),
            resolved_at=validated.captured_at,
            source_locator=(
                f"observation-envelope:{Modelo.M303.value}:{source_period.filing_year}:{source_period.registry_token}"
            ),
        ),
        prior_period_observation_found=True,
    )


def require_persisted_iva_compensation_decision_matches_revision(
    work_unit: WorkUnit,
    revision: CalculationRevision,
    *,
    repository: IvaWalletDecisionRepository | None = None,
    subject_leaf_key: str = "modelo.export",
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
    if work_unit.modelo != Modelo.M303:
        return None
    decision = load_persisted_iva_compensation_decision_for_work_unit(work_unit, repository=repository)
    if decision is None:
        _raise_iva_wallet_precondition(
            subject_leaf_key=subject_leaf_key,
            reason_code="not_seeded",
            translated_message="application.modelo.errors.iva_wallet_not_seeded",
            evidence_values={"persisted_decision_present": False},
        )
    if decision.blocked:
        blocked_reason, blocked_message = _blocked_refusal(decision)
        _raise_iva_wallet_precondition(
            subject_leaf_key=subject_leaf_key,
            reason_code=blocked_reason,
            translated_message=blocked_message,
            evidence_values={
                "divergence_code": str(decision.divergence),
                "wallet_blocked": True,
            },
            context={"divergence": str(decision.divergence), "reason": blocked_reason},
        )
    if decision.target_period != work_unit.period:
        _raise_iva_wallet_precondition(
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
    if _decision_is_first_period_zero(decision):
        _require_first_period_zero_decision_grounded(
            work_unit,
            _registry_snapshot_for_work_unit(
                work_unit,
                subject_leaf_key=subject_leaf_key,
            ),
            decision,
            subject_leaf_key=subject_leaf_key,
        )
    if decision.selected_amount is None:
        _raise_iva_wallet_precondition(
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
        _raise_iva_wallet_precondition(
            subject_leaf_key=subject_leaf_key,
            reason_code="revision_amount_missing",
            translated_message="application.modelo.errors.iva_wallet_revision_amount_missing",
            evidence_values={
                "binding_id": _M303_PRIOR_COMPENSATION_BINDING_ID,
                "casilla_id": _M303_PRIOR_COMPENSATION_CASILLA_ID,
                "revision_amount_present": False,
            },
            context={
                "divergence": "authority_revision_missing_amount",
                "reason": "revision_amount_missing",
            },
        )
    if Decimal(decision.selected_amount) != revision_amount:
        _raise_iva_wallet_precondition(
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


def revision_iva_compensation_amount(revision: CalculationRevision) -> Decimal | None:
    """Return the Modelo 303 prior-compensation amount carried by a revision.

    Reads the :class:`~CalculationRevision` casilla values
    first, then binding overrides, matching the persisted calculation payload.
    """
    casilla_value = dict(revision.casilla_values).get(_M303_PRIOR_COMPENSATION_CASILLA_ID)
    if casilla_value is not None:
        return Decimal(casilla_value)
    binding_value = dict(revision.binding_overrides).get(_M303_PRIOR_COMPENSATION_BINDING_ID)
    if binding_value is not None:
        return Decimal(binding_value)
    return None


def taxpayer_nif_for_bucket(bucket_id: str) -> str | None:
    """Return the profile tax id for a bucket, or ``None`` when absent."""
    values = _profile_path_values_for_bucket(bucket_id)
    if values is None:
        return None
    value = values.get("identity.tax_id")
    if value is None or not value.strip():
        return None
    return value.strip()


__all__ = [
    "ModeloIvaWalletReconciliationBlocked",
    "ModeloIvaWalletReconciliationBlockedError",
    "apply_iva_compensation_decision_binding",
    "caller_supplied_prior_compensation_value",
    "lazily_reconcile_local_iva_compensation_for_work_unit",
    "load_persisted_iva_compensation_decision_for_work_unit",
    "require_persisted_iva_compensation_decision_for_work_unit",
    "require_persisted_iva_compensation_decision_matches_revision",
    "resolve_iva_compensation_decision_for_calculation",
    "revision_iva_compensation_amount",
    "taxpayer_nif_for_bucket",
]
