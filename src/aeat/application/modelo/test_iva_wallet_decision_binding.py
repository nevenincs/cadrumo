"""Modelo 303 calculation guard for IVA wallet reconciliation decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ..calculations._iva_wallet_reconciliation import IvaCompensationReconciliationDecision
from ._actions import ModeloIvaWalletReconciliationBlocked, _apply_iva_compensation_decision_binding

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _decision(
    *,
    blocked: bool = False,
    amount: Decimal | None = Decimal("1200"),
) -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period="2T",
        selected_authority="aeat_wallet" if not blocked else "missing",
        selected_amount=amount,
        wallet_amount=Decimal("1200"),
        local_recurrence_amount=Decimal("1200") if not blocked else Decimal("800"),
        override_amount=None,
        divergence="match" if not blocked else "wallet_higher",
        blocked=blocked,
        stale_wallet=False,
        reason="wallet decision fixture",
        wallet_captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        decided_at=datetime(2026, 5, 19, 12, 1, 0, tzinfo=UTC),
    )


def test_non_blocking_iva_wallet_decision_supplies_modelo_303_binding() -> None:
    caller: dict[str, Decimal] = {}
    backend: dict[str, Decimal] = {}

    _apply_iva_compensation_decision_binding(
        "303",
        2026,
        "2T",
        taxpayer_nif="12345678Z",
        casilla_inputs={},
        backend_casilla_inputs={},
        caller_binding_values=caller,
        backend_binding_values=backend,
        decision=_decision(),
    )

    assert backend["modelo-303-compensacion-pendiente-anteriores"] == Decimal("1200")


def test_blocked_iva_wallet_decision_refuses_modelo_303_automatic_calculation() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="blocks automatic Modelo 303 calculation"):
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            "2T",
            taxpayer_nif="12345678Z",
            casilla_inputs={},
            backend_casilla_inputs={},
            caller_binding_values={},
            backend_binding_values={},
            decision=_decision(blocked=True, amount=None),
        )


def test_caller_binding_conflict_with_wallet_decision_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="conflicts"):
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            "2T",
            taxpayer_nif="12345678Z",
            casilla_inputs={},
            backend_casilla_inputs={},
            caller_binding_values={"modelo-303-compensacion-pendiente-anteriores": Decimal("800")},
            backend_binding_values={},
            decision=_decision(),
        )


def test_modelo_303_prior_compensation_binding_without_wallet_decision_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="requires a persisted IVA wallet"):
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            "2T",
            taxpayer_nif="12345678Z",
            casilla_inputs={},
            backend_casilla_inputs={},
            caller_binding_values={"modelo-303-compensacion-pendiente-anteriores": Decimal("800")},
            backend_binding_values={},
            decision=None,
        )


def test_modelo_303_without_prior_compensation_binding_can_calculate_without_wallet_decision() -> None:
    caller: dict[str, Decimal] = {}
    backend: dict[str, Decimal] = {"modelo-303-iva-repercutido-general-cuota": Decimal("100")}

    _apply_iva_compensation_decision_binding(
        "303",
        2026,
        "2T",
        taxpayer_nif="12345678Z",
        casilla_inputs={},
        backend_casilla_inputs={},
        caller_binding_values=caller,
        backend_binding_values=backend,
        decision=None,
    )

    assert backend == {"modelo-303-iva-repercutido-general-cuota": Decimal("100")}


def test_modelo_303_prior_compensation_casilla_without_wallet_decision_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="requires a persisted IVA wallet"):
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            "2T",
            taxpayer_nif="12345678Z",
            casilla_inputs={"iva.compensacion-pendiente-periodos-anteriores": Decimal("800")},
            backend_casilla_inputs={},
            caller_binding_values={},
            backend_binding_values={},
            decision=None,
        )


def test_modelo_303_backend_prior_compensation_casilla_without_wallet_decision_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="requires a persisted IVA wallet"):
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            "2T",
            taxpayer_nif="12345678Z",
            casilla_inputs={},
            backend_casilla_inputs={"iva.compensacion-pendiente-periodos-anteriores": Decimal("800")},
            caller_binding_values={},
            backend_binding_values={},
            decision=None,
        )


def test_modelo_303_wallet_decision_for_other_taxpayer_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="taxpayer"):
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            "2T",
            taxpayer_nif="99999999R",
            casilla_inputs={},
            backend_casilla_inputs={},
            caller_binding_values={},
            backend_binding_values={},
            decision=_decision(),
        )


def test_modelo_303_prior_compensation_casilla_conflict_with_wallet_decision_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="caller casilla"):
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            "2T",
            taxpayer_nif="12345678Z",
            casilla_inputs={"iva.compensacion-pendiente-periodos-anteriores": Decimal("800")},
            backend_casilla_inputs={},
            caller_binding_values={},
            backend_binding_values={},
            decision=_decision(),
        )
