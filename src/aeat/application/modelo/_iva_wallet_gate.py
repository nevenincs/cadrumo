"""Modelo IVA wallet gate for calculation and filing lifecycle checks.

Modelo 303 prior-compensation belongs to the IVA wallet authority, not to the
generic previous-filing source mesh. This module uses the calculation
:class:`RegistrySnapshot` and :class:`ModeloRevision` to route the wallet
decision into the prior-compensation binding, then checks a persisted
:class:`~aeat.domain.iva_compensation._reconciliation.IvaCompensationReconciliationDecision`
against the exported or filed :class:`CalculationRevision`.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Final, Protocol

from ...core import Modelo
from ...core import Period as _Period
from ...core.i18n import tr
from ...domain.calculations.registry import (
    BindingId,
    CasillaId,
    ModeloRevision,
    RegistrySnapshot,
    RegistrySnapshotError,
    validated_casilla_id,
)
from ...domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._errors import ModeloError
from ...domain.modelos._work_unit import WorkUnit
from ..calculations._observations_repository import IvaWalletDecisionRepository


class _IvaWalletBlockedDecision(Protocol):
    @property
    def divergence(self) -> object: ...

    @property
    def reason(self) -> object: ...


_M303_PRIOR_COMPENSATION_BINDING_ID: BindingId = "modelo-303-compensacion-pendiente-anteriores"
_M303_PRIOR_COMPENSATION_ORIGIN_IDS: Final[frozenset[str]] = frozenset(
    {
        _M303_PRIOR_COMPENSATION_BINDING_ID,
        "modelo-303-rel-self-compensacion-anteriores",
    },
)


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="IVA wallet gate casilla constant")
    except ValueError as exc:
        raise RuntimeError(f"IVA wallet gate casilla constant {value!r} is not a CasillaId") from exc


_M303_PRIOR_COMPENSATION_CASILLA_ID: Final[CasillaId] = _casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores",
)


class ModeloIvaWalletReconciliationBlockedError(ModeloError):
    """Raised when Modelo 303 calculation is blocked by IVA wallet reconciliation."""


ModeloIvaWalletReconciliationBlocked = ModeloIvaWalletReconciliationBlockedError


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

    The :class:`RegistrySnapshot` is passed to the lazy reconciliation path when
    no caller-supplied or persisted wallet decision exists.
    """
    if supplied_decision is None:
        persisted = load_persisted_iva_compensation_decision_for_work_unit(work_unit, repository=repository)
        if persisted is not None:
            return _require_first_period_zero_decision_grounded(work_unit, snapshot, persisted)
        if caller_supplied_prior_compensation_value(
            binding_values=binding_values,
            backend_binding_values=backend_binding_values,
            casilla_inputs=casilla_inputs,
            backend_casilla_inputs=backend_casilla_inputs,
        ):
            supplied_amounts = _supplied_prior_compensation_amounts(
                binding_values=binding_values,
                backend_binding_values=backend_binding_values,
                casilla_inputs=casilla_inputs,
                backend_casilla_inputs=backend_casilla_inputs,
            )
            decision = lazily_reconcile_local_iva_compensation_for_work_unit(
                work_unit,
                snapshot=snapshot,
                repository=repository,
                persist=False,
            )
            if decision is not None and not _decision_is_missing_local_authority(decision):
                if _decision_has_concrete_zero_authority(decision):
                    if any(amount != Decimal("0") for amount in supplied_amounts):
                        raise ModeloIvaWalletReconciliationBlocked(
                            translated_message="application.modelo.errors.iva_wallet_caller_binding_conflict",
                        )
                    decision = _non_blocking_concrete_zero_authority_decision(decision)
                if not decision.blocked:
                    decision = _require_first_period_zero_decision_grounded(work_unit, snapshot, decision)
                _save_iva_compensation_decision(decision, repository=repository)
                return decision
            return None
        return lazily_reconcile_local_iva_compensation_for_work_unit(
            work_unit,
            snapshot=snapshot,
            repository=repository,
        )
    return require_persisted_iva_compensation_decision_for_work_unit(
        work_unit,
        supplied_decision=supplied_decision,
        snapshot=snapshot,
        repository=repository,
    )


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

    The :class:`ModeloRevision` defines the binding channel; the decision amount
    is written only after target period and taxpayer identity checks pass.
    """
    if modelo != Modelo.M303:
        return
    binding_id = _M303_PRIOR_COMPENSATION_BINDING_ID
    bound_casilla_id = _M303_PRIOR_COMPENSATION_CASILLA_ID
    caller_casilla_value = dict(casilla_inputs or {}).get(bound_casilla_id)
    backend_casilla_value = dict(backend_casilla_inputs or {}).get(bound_casilla_id)
    if decision is None:
        caller_value = caller_binding_values.get(binding_id)
        backend_value = backend_binding_values.get(binding_id)
        if (
            caller_value is not None
            or backend_value is not None
            or caller_casilla_value is not None
            or backend_casilla_value is not None
        ):
            raise ModeloIvaWalletReconciliationBlocked(
                translated_message="application.modelo.errors.iva_wallet_not_seeded",
                suggestion="aeat app modelo iva-wallet seed --filing-year YEAR --period PERIOD --amount 0 --confirm",
            )
        return

    if not isinstance(decision, IvaCompensationReconciliationDecision):
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_unsupported_decision_type",
            context={"decision_type": type(decision).__name__},
        )
    if decision.target_period != period:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_target_mismatch",
            context={
                "target_year": decision.target_year,
                "target_period": decision.target_period.registry_token,
                "filing_year": filing_year,
                "period": period.registry_token,
            },
        )
    if taxpayer_nif is None:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_taxpayer_identity_missing",
        )
    if decision.taxpayer_nif.strip().upper() != taxpayer_nif.strip().upper():
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_taxpayer_mismatch",
        )
    if decision.blocked:
        raise ModeloIvaWalletReconciliationBlocked(
            "IVA wallet reconciliation blocks automatic Modelo 303 calculation: "
            f"{decision.divergence}: {decision.reason}",
            translated_message="application.modelo.errors.iva_wallet_blocked",
            context={"divergence": str(decision.divergence), "reason": str(decision.reason)},
        )
    if decision.selected_amount is None:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_selected_amount_missing",
        )
    selected = Decimal(decision.selected_amount)
    caller_value = caller_binding_values.get(binding_id)
    if caller_value is not None and Decimal(caller_value) != selected:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_caller_binding_conflict",
        )
    if caller_casilla_value is not None and Decimal(caller_casilla_value) != selected:
        raise ModeloIvaWalletReconciliationBlocked(
            "caller casilla input for Modelo 303 prior compensation conflicts with IVA wallet reconciliation decision",
            translated_message="application.modelo.errors.iva_wallet_caller_casilla_conflict",
        )
    if backend_casilla_value is not None and Decimal(backend_casilla_value) != selected:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_backend_casilla_conflict",
        )
    from ..aggregation import CalculationSourceContext
    from ..calculations import IvaWalletDecisionSourceResolver

    resolution = IvaWalletDecisionSourceResolver(decision).resolve(
        CalculationSourceContext(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision=revision,
        ),
    )
    backend_binding_values.update(resolution.binding_values)


def require_persisted_iva_compensation_decision_for_work_unit(
    work_unit: WorkUnit,
    *,
    supplied_decision: object,
    snapshot: RegistrySnapshot | None = None,
    repository: IvaWalletDecisionRepository | None = None,
) -> object:
    """Require a supplied Modelo 303 wallet decision to match the persisted decision.

    The optional :class:`RegistrySnapshot` grounds first-period-zero decisions;
    when omitted, the function resolves the snapshot from the supplied work unit.
    """
    if work_unit.modelo != Modelo.M303:
        return supplied_decision
    persisted = load_persisted_iva_compensation_decision_for_work_unit(work_unit, repository=repository)
    if persisted is None:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_not_seeded",
            suggestion="aeat app modelo iva-wallet seed --filing-year YEAR --period PERIOD --amount 0 --confirm",
        )
    if persisted != supplied_decision:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_supplied_decision_mismatch",
        )
    if _decision_is_first_period_zero(persisted):
        return _require_first_period_zero_decision_grounded(
            work_unit,
            snapshot or _registry_snapshot_for_work_unit(work_unit),
            persisted,
        )
    return persisted


def load_persisted_iva_compensation_decision_for_work_unit(
    work_unit: WorkUnit,
    *,
    repository: IvaWalletDecisionRepository | None = None,
) -> IvaCompensationReconciliationDecision | None:
    """Load and return the :class:`IvaCompensationReconciliationDecision` for a work unit."""
    if work_unit.modelo != Modelo.M303:
        return None
    taxpayer_nif = taxpayer_nif_for_bucket(work_unit.bucket_id)
    if taxpayer_nif is None:
        return None
    if repository is None:
        from ..calculations._observations_repository import IvaWalletDecisionRepository

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
    from ...domain.user_profile import ProfileNotFoundError
    from ..user_profile import UserProfileLifecycleRepository
    from ..user_profile._projections import record_to_path_values

    try:
        record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
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


def _registry_snapshot_for_work_unit(work_unit: WorkUnit) -> RegistrySnapshot:
    """Resolve the registry snapshot attached to ``work_unit``."""
    from ...core.resources import resources

    try:
        return resources().modelos.authority.snapshot(
            str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    except (FileNotFoundError, RegistrySnapshotError) as exc:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_blocked",
            context={
                "divergence": "first_period_zero_unproven",
                "reason": "registry snapshot could not be resolved to ground first-period-zero IVA decision",
            },
        ) from exc


def _decision_is_first_period_zero(decision: object) -> bool:
    return str(getattr(decision, "divergence", "")) == "first_period_zero"


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
            "reason": (
                "Caller-supplied zero matches concrete local IVA compensation history; "
                "no prior compensation balance is available to apply."
            ),
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
    decision: object,
) -> object:
    """Fail closed unless a first-period-zero decision is profile/registry-grounded."""
    if not _decision_is_first_period_zero(decision):
        return decision
    if _decision_has_concrete_zero_authority(decision):
        return decision
    if _activity_start_proves_first_iva_period(work_unit, snapshot):
        return decision
    raise ModeloIvaWalletReconciliationBlocked(
        translated_message="application.modelo.errors.iva_wallet_blocked",
        context={
            "divergence": "first_period_zero_unproven",
            "reason": (
                "first-period-zero IVA compensation requires profile activity-start proof that every "
                "Modelo 303 prior-compensation dependency is pre-activity"
            ),
        },
    )


def _activity_start_proves_first_iva_period(work_unit: WorkUnit, snapshot: RegistrySnapshot) -> bool:
    """Return whether the profile proves no prior IVA-compensation obligation existed."""
    from ..calculations import (
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
    :class:`IvaCompensationReconciliationDecision`. In the seed-only local
    authority case, the local Modelo 303 recurrence is the authority, so derive
    and persist the decision here instead of refusing calculation.


    The :class:`RegistrySnapshot` supplies the Modelo 303 revision context for
    the reconciliation service.
    """
    if work_unit.modelo != Modelo.M303:
        return None
    taxpayer_nif = taxpayer_nif_for_bucket(work_unit.bucket_id)
    if taxpayer_nif is None:
        return None
    from ..calculations._iva_wallet_reconciliation import reconcile_modelo_303_iva_compensation

    report = reconcile_modelo_303_iva_compensation(
        snapshot,
        taxpayer_nif=taxpayer_nif,
        wallet=None,
        decision_repository=repository,
        # Missing local recurrence proves a zero only when the profile's
        # activity-start date scopes every Modelo 303 prior-compensation
        # dependency out as pre-activity. Otherwise the reconciliation must keep
        # failing closed as missing wallet/local history.
        treat_absent_recurrence_as_first_period=_activity_start_proves_first_iva_period(work_unit, snapshot),
        persist=persist,
    )
    return report.decision


def require_persisted_iva_compensation_decision_matches_revision(
    work_unit: WorkUnit,
    revision: CalculationRevision,
    *,
    repository: IvaWalletDecisionRepository | None = None,
) -> IvaCompensationReconciliationDecision | None:
    """Return the :class:`IvaCompensationReconciliationDecision` when it matches the revision.

    The check reads the supplied :class:`CalculationRevision` and blocks when
    its Modelo 303 prior-compensation amount differs from the persisted wallet
    decision.
    """
    if work_unit.modelo != Modelo.M303:
        return None
    decision = load_persisted_iva_compensation_decision_for_work_unit(work_unit, repository=repository)
    if decision is None:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_not_seeded",
            suggestion="aeat app modelo iva-wallet seed --filing-year YEAR --period PERIOD --amount 0 --confirm",
        )
    if decision.blocked:
        raise ModeloIvaWalletReconciliationBlocked(
            iva_wallet_blocked_message(decision),
            translated_message="application.modelo.errors.iva_wallet_blocked",
            context={"divergence": str(decision.divergence), "reason": str(decision.reason)},
        )
    if decision.target_period != work_unit.period:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_blocked",
            context={
                "divergence": "authority_target_mismatch",
                "reason": "persisted IVA wallet decision target does not match the Modelo 303 work unit",
            },
        )
    if _decision_is_first_period_zero(decision):
        _require_first_period_zero_decision_grounded(
            work_unit,
            _registry_snapshot_for_work_unit(work_unit),
            decision,
        )
    if decision.selected_amount is None:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_blocked",
            context={
                "divergence": "authority_missing_amount",
                "reason": "persisted IVA wallet decision has no selected amount",
            },
        )
    revision_amount = revision_iva_compensation_amount(revision)
    if revision_amount is None:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_blocked",
            context={
                "divergence": "authority_revision_missing_amount",
                "reason": "calculation revision does not carry the Modelo 303 prior-compensation amount",
            },
        )
    if Decimal(decision.selected_amount) != revision_amount:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_blocked",
            context={
                "divergence": "authority_amount_mismatch",
                "reason": "persisted IVA wallet decision does not match the calculation revision",
            },
        )
    return decision


def revision_iva_compensation_amount(revision: CalculationRevision) -> Decimal | None:
    """Return the Modelo 303 prior-compensation amount carried by a revision.

    Reads the :class:`CalculationRevision` casilla values first, then binding
    overrides, matching the persisted calculation payload.
    """
    casilla_value = dict(revision.casilla_values).get(_M303_PRIOR_COMPENSATION_CASILLA_ID)
    if casilla_value is not None:
        return Decimal(casilla_value)
    binding_value = dict(revision.binding_overrides).get(_M303_PRIOR_COMPENSATION_BINDING_ID)
    if binding_value is not None:
        return Decimal(binding_value)
    return None


def iva_wallet_blocked_message(decision: _IvaWalletBlockedDecision) -> str:
    """Render a localized IVA wallet blocked message from a decision-like object."""
    divergence = str(decision.divergence)
    reason = str(decision.reason)
    return tr("application.modelo.errors.iva_wallet_blocked", divergence=divergence, reason=reason)


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
    "iva_wallet_blocked_message",
    "lazily_reconcile_local_iva_compensation_for_work_unit",
    "load_persisted_iva_compensation_decision_for_work_unit",
    "require_persisted_iva_compensation_decision_for_work_unit",
    "require_persisted_iva_compensation_decision_matches_revision",
    "resolve_iva_compensation_decision_for_calculation",
    "revision_iva_compensation_amount",
    "taxpayer_nif_for_bucket",
]
