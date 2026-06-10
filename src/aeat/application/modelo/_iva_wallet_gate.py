"""Modelo IVA wallet gate for calculation and filing lifecycle checks.

Use of :class:`CalculationRevision`, :class:`ModeloRevision`, :class:`RegistrySnapshot` for compliance.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from ...core import Modelo
from ...core.i18n import tr
from ...domain.calculations.registry import ModeloRevision, RegistrySnapshot
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._errors import ModeloError
from ...domain.modelos._work_unit import WorkUnit

if TYPE_CHECKING:
    from ...domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
    from ..calculations._observations_repository import IvaWalletDecisionRepository

_M303_PRIOR_COMPENSATION_BINDING_ID = "modelo-303-compensacion-pendiente-anteriores"
_M303_PRIOR_COMPENSATION_CASILLA_ID = "iva.compensacion-pendiente-periodos-anteriores"


class ModeloIvaWalletReconciliationBlockedError(ModeloError):
    """Raised when Modelo 303 calculation is blocked by IVA wallet reconciliation."""


ModeloIvaWalletReconciliationBlocked = ModeloIvaWalletReconciliationBlockedError


def resolve_iva_compensation_decision_for_calculation(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    supplied_decision: object | None,
    repository: IvaWalletDecisionRepository | None,
    binding_values: Mapping[str, Decimal] | None,
    backend_binding_values: Mapping[str, Decimal] | None,
    casilla_inputs: Mapping[str, Decimal] | None,
    backend_casilla_inputs: Mapping[str, Decimal] | None,
) -> object | None:
    """Resolve the Modelo 303 IVA wallet decision that may feed calculation bindings.

    Use of :class:`RegistrySnapshot` for compliance.
    """
    if supplied_decision is None:
        persisted = load_persisted_iva_compensation_decision_for_work_unit(work_unit, repository=repository)
        if persisted is not None:
            return persisted
        if caller_supplied_prior_compensation_value(
            binding_values=binding_values,
            backend_binding_values=backend_binding_values,
            casilla_inputs=casilla_inputs,
            backend_casilla_inputs=backend_casilla_inputs,
        ):
            return None
        return lazily_reconcile_local_iva_compensation_for_work_unit(
            work_unit,
            snapshot=snapshot,
            repository=repository,
        )
    return require_persisted_iva_compensation_decision_for_work_unit(
        work_unit,
        supplied_decision=supplied_decision,
        repository=repository,
    )


def apply_iva_compensation_decision_binding(
    modelo: str,
    filing_year: int,
    period: str,
    *,
    bucket_id: str,
    revision: ModeloRevision,
    taxpayer_nif: str | None = None,
    casilla_inputs: Mapping[str, Decimal] | None = None,
    backend_casilla_inputs: Mapping[str, Decimal] | None = None,
    caller_binding_values: dict[str, Decimal],
    backend_binding_values: dict[str, Decimal],
    decision: object | None,
) -> None:
    """Apply a non-blocking IVA wallet decision to Modelo 303 binding values.

    Use of :class:`ModeloRevision` for compliance.
    """
    if modelo != Modelo.M303.value:
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

    from ...domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision

    if not isinstance(decision, IvaCompensationReconciliationDecision):
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_unsupported_decision_type",
            context={"decision_type": type(decision).__name__},
        )
    if decision.target_year != filing_year or decision.target_period != period:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_target_mismatch",
            context={
                "target_year": decision.target_year,
                "target_period": decision.target_period,
                "filing_year": filing_year,
                "period": period,
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
        )
    )
    backend_binding_values.update(resolution.binding_values)


def require_persisted_iva_compensation_decision_for_work_unit(
    work_unit: WorkUnit,
    *,
    supplied_decision: object,
    repository: IvaWalletDecisionRepository | None = None,
) -> object:
    """Require a supplied Modelo 303 wallet decision to match the persisted decision."""
    if work_unit.modelo != Modelo.M303.value:
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
    return persisted


def load_persisted_iva_compensation_decision_for_work_unit(
    work_unit: WorkUnit,
    *,
    repository: IvaWalletDecisionRepository | None = None,
) -> IvaCompensationReconciliationDecision | None:
    """Load and return the :class:`IvaCompensationReconciliationDecision` for a work unit."""
    if work_unit.modelo != Modelo.M303.value:
        return None
    taxpayer_nif = taxpayer_nif_for_bucket(work_unit.bucket_id)
    if taxpayer_nif is None:
        return None
    if repository is None:
        from ..calculations._observations_repository import IvaWalletDecisionRepository

        repository = IvaWalletDecisionRepository()

    return repository.load_decision(
        taxpayer_nif,
        work_unit.filing_year,
        work_unit.period,
    )


def caller_supplied_prior_compensation_value(
    *,
    binding_values: Mapping[str, Decimal] | None,
    backend_binding_values: Mapping[str, Decimal] | None,
    casilla_inputs: Mapping[str, Decimal] | None,
    backend_casilla_inputs: Mapping[str, Decimal] | None,
) -> bool:
    """Return whether a Modelo 303 prior-compensation value was explicitly supplied.

    The lazy local reconciliation must not fire when the operator or a backend
    resolver explicitly asserts the prior-compensation binding/casilla. That
    value needs reconciliation against a real wallet/seed decision, and the
    seed-verb guidance must surface.
    """
    binding_id = _M303_PRIOR_COMPENSATION_BINDING_ID
    casilla_id = _M303_PRIOR_COMPENSATION_CASILLA_ID
    return (
        dict(binding_values or {}).get(binding_id) is not None
        or dict(backend_binding_values or {}).get(binding_id) is not None
        or dict(casilla_inputs or {}).get(casilla_id) is not None
        or dict(backend_casilla_inputs or {}).get(casilla_id) is not None
    )


def lazily_reconcile_local_iva_compensation_for_work_unit(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    repository: IvaWalletDecisionRepository | None = None,
) -> IvaCompensationReconciliationDecision | None:
    """Auto-derive and persist the local-authority Modelo 303 compensation decision.

    Calculate's prior-compensation gate requires a persisted
    :class:`IvaCompensationReconciliationDecision`. In the seed-only local
    authority case, the local Modelo 303 recurrence is the authority, so derive
    and persist the decision here instead of refusing calculation.


    Use of :class:`RegistrySnapshot` for compliance.
    """
    if work_unit.modelo != Modelo.M303.value:
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
        # No caller-supplied prior-compensation value reached this point and no
        # live wallet is configured. A missing prior local recurrence is the
        # taxpayer's first IVA period, so casilla 110 is a legally-certain zero.
        treat_absent_recurrence_as_first_period=True,
        persist=True,
    )
    return report.decision


def require_persisted_iva_compensation_decision_matches_revision(
    work_unit: WorkUnit,
    revision: CalculationRevision,
    *,
    repository: IvaWalletDecisionRepository | None = None,
) -> IvaCompensationReconciliationDecision | None:
    """Return the :class:`IvaCompensationReconciliationDecision` when it matches the revision.

    Uses :class:`CalculationRevision` for the revision match check.
    """
    if work_unit.modelo != Modelo.M303.value:
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
        )
    if decision.target_year != work_unit.filing_year or decision.target_period != work_unit.period:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_blocked",
            context={
                "divergence": "authority_target_mismatch",
                "reason": "persisted IVA wallet decision target does not match the Modelo 303 work unit",
            },
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

    Use of :class:`CalculationRevision` for compliance.
    """
    casilla_value = dict(revision.casilla_values).get(_M303_PRIOR_COMPENSATION_CASILLA_ID)
    if casilla_value is not None:
        return Decimal(casilla_value)
    binding_value = dict(revision.binding_overrides).get(_M303_PRIOR_COMPENSATION_BINDING_ID)
    if binding_value is not None:
        return Decimal(binding_value)
    return None


def iva_wallet_blocked_message(decision: Any) -> str:
    """Render a localized IVA wallet blocked message from a decision-like object."""
    divergence = str(decision.divergence)
    reason = str(decision.reason)
    return tr("application.modelo.errors.iva_wallet_blocked", divergence=divergence, reason=reason)


def taxpayer_nif_for_bucket(bucket_id: str) -> str | None:
    """Return the profile tax id for a bucket, or ``None`` when absent."""
    from ...domain.user_profile import ProfileNotFoundError
    from ..user_profile._profile_repository import ProfileRepository
    from ..user_profile._projections import record_to_path_values

    try:
        profile = ProfileRepository().load(bucket_id)
        record = profile.record
    except ProfileNotFoundError:
        return None
    value = record_to_path_values(record).get("identity.tax_id")
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
