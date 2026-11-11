"""Modelo 303 prior-compensation binding fed from a validated IVA wallet decision.

The wallet decision reaches the prior-compensation casilla only through
:func:`apply_iva_compensation_decision_binding`, after its target period and
taxpayer identity are checked and every caller or backend input for the same
binding or casilla agrees with the selected amount.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final, NamedTuple

from ...core.casilla_id import CasillaId
from ...core.identity.tax_id import same_tax_identifier
from ...core.period import Period
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_PENDING_PRIOR_CASILLA,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from .iva_wallet_refusal import blocked_iva_wallet_refusal, raise_iva_wallet_precondition

M303_PRIOR_COMPENSATION_BINDING_ID: BindingId = "modelo-303-compensacion-pendiente-anteriores"
M303_PRIOR_COMPENSATION_ORIGIN_IDS: Final[frozenset[str]] = frozenset(
    {
        M303_PRIOR_COMPENSATION_BINDING_ID,
        "modelo-303-rel-self-compensacion-anteriores",
    },
)


class _WalletBindingTarget(NamedTuple):
    bucket_id: str
    modelo: str
    filing_year: int
    period: Period
    revision: ModeloRevision


class _PriorCompensationInputs(NamedTuple):
    caller_binding_value: Decimal | None
    backend_binding_value: Decimal | None
    caller_casilla_value: Decimal | None
    backend_casilla_value: Decimal | None


def _prior_compensation_inputs(
    *,
    casilla_inputs: Mapping[CasillaId, Decimal] | None,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None,
    caller_binding_values: Mapping[BindingId, Decimal],
    backend_binding_values: Mapping[BindingId, Decimal],
) -> _PriorCompensationInputs:
    return _PriorCompensationInputs(
        caller_binding_value=caller_binding_values.get(M303_PRIOR_COMPENSATION_BINDING_ID),
        backend_binding_value=backend_binding_values.get(M303_PRIOR_COMPENSATION_BINDING_ID),
        caller_casilla_value=dict(casilla_inputs or {}).get(M303_COMPENSATION_PENDING_PRIOR_CASILLA),
        backend_casilla_value=dict(backend_casilla_inputs or {}).get(M303_COMPENSATION_PENDING_PRIOR_CASILLA),
    )


def _require_decision_for_supplied_inputs(inputs: _PriorCompensationInputs, *, carry_period: Period) -> None:
    supplied_values = tuple(value for value in inputs if value is not None)
    if not supplied_values:
        return
    raise_iva_wallet_precondition(
        subject_leaf_key="modelo.work.calculate",
        reason_code="not_seeded",
        translated_message="application.modelo.errors.iva_wallet_not_seeded",
        evidence_values={
            "binding_id": M303_PRIOR_COMPENSATION_BINDING_ID,
            "casilla_id": M303_COMPENSATION_PENDING_PRIOR_CASILLA,
            "supplied_value_count": len(supplied_values),
        },
        carry_period=carry_period,
    )


def _validated_decision_amount(
    decision: object,
    *,
    target: _WalletBindingTarget,
    taxpayer_nif: str | None,
) -> tuple[IvaCompensationReconciliationDecision, Decimal]:
    if not isinstance(decision, IvaCompensationReconciliationDecision):
        raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="unsupported_decision_type",
            translated_message="application.modelo.errors.iva_wallet_unsupported_decision_type",
            evidence_values={"decision_type": type(decision).__name__},
            context={"decision_type": type(decision).__name__},
        )
    if decision.target_period != target.period:
        raise_iva_wallet_precondition(
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
        raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="taxpayer_identity_missing",
            translated_message="application.modelo.errors.iva_wallet_taxpayer_identity_missing",
            evidence_values={"taxpayer_identity_present": False},
        )
    if not same_tax_identifier(decision.taxpayer_nif, taxpayer_nif):
        raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="taxpayer_mismatch",
            translated_message="application.modelo.errors.iva_wallet_taxpayer_mismatch",
            evidence_values={"taxpayer_identity_match": False},
        )
    if decision.blocked:
        blocked_reason, blocked_message = blocked_iva_wallet_refusal(decision)
        raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code=blocked_reason,
            translated_message=blocked_message,
            evidence_values={
                "divergence_code": str(decision.divergence),
                "wallet_blocked": True,
            },
            context={"divergence": str(decision.divergence), "reason": blocked_reason},
            carry_period=target.period,
            local_amount=decision.local_recurrence_amount,
        )
    if decision.selected_amount is None:
        raise_iva_wallet_precondition(
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
        raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="caller_binding_conflict",
            translated_message="application.modelo.errors.iva_wallet_caller_binding_conflict",
            evidence_values={
                "binding_id": M303_PRIOR_COMPENSATION_BINDING_ID,
                "decision_amount": selected,
                "supplied_amount": Decimal(inputs.caller_binding_value),
            },
        )
    if inputs.caller_casilla_value is not None and Decimal(inputs.caller_casilla_value) != selected:
        raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="caller_casilla_conflict",
            translated_message="application.modelo.errors.iva_wallet_caller_casilla_conflict",
            evidence_values={
                "casilla_id": M303_COMPENSATION_PENDING_PRIOR_CASILLA,
                "decision_amount": selected,
                "supplied_amount": Decimal(inputs.caller_casilla_value),
            },
        )
    if inputs.backend_casilla_value is not None and Decimal(inputs.backend_casilla_value) != selected:
        raise_iva_wallet_precondition(
            subject_leaf_key="modelo.work.calculate",
            reason_code="backend_casilla_conflict",
            translated_message="application.modelo.errors.iva_wallet_backend_casilla_conflict",
            evidence_values={
                "casilla_id": M303_COMPENSATION_PENDING_PRIOR_CASILLA,
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
    from ..aggregation.source_mesh import CalculationSourceContext
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
    period: Period,
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

    The :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision` defines the
    binding channel; the decision amount is written only after target period and
    taxpayer identity checks pass. Caller and backend inputs for the same binding
    or casilla must either match the selected decision amount or are refused as
    conflicts. The effective value is then produced through
    :class:`~cadrumo.application.calculations.iva_wallet_reconciliation.IvaWalletDecisionSourceResolver`, so
    the calculation source mesh records the IVA-wallet provenance instead of a
    generic ``previous_filing`` source.
    """
    if modelo != form_for_role("iva.periodic"):
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
        _require_decision_for_supplied_inputs(inputs, carry_period=target.period)
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
