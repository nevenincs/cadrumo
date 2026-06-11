"""Modelo 303 calculation guard for IVA wallet reconciliation decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
from .._actions import ModeloIvaWalletReconciliationBlocked, _apply_iva_compensation_decision_binding

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TAXPAYER_REF = "taxpayeralpha"
_OTHER_TAXPAYER_REF = "othertaxpayeralpha"


def _decision(
    *,
    blocked: bool = False,
    amount: Decimal | None = Decimal("1200"),
) -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
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


def _revision():
    return resources().modelos.authority.snapshot("303", filing_year=2026, period="2T").revision


def _apply(
    *,
    taxpayer_nif: str = _TAXPAYER_REF,
    casilla_inputs: dict[str, Decimal] | None = None,
    backend_casilla_inputs: dict[str, Decimal] | None = None,
    caller_binding_values: dict[str, Decimal] | None = None,
    backend_binding_values: dict[str, Decimal] | None = None,
    decision: IvaCompensationReconciliationDecision | None = None,
) -> None:
    _apply_iva_compensation_decision_binding(
        "303",
        2026,
        Period.from_year_and_code(2026, "2T"),
        bucket_id="operator",
        revision=_revision(),
        taxpayer_nif=taxpayer_nif,
        casilla_inputs=casilla_inputs or {},
        backend_casilla_inputs=backend_casilla_inputs or {},
        caller_binding_values=caller_binding_values if caller_binding_values is not None else {},
        backend_binding_values=backend_binding_values if backend_binding_values is not None else {},
        decision=decision,
    )


def _assert_missing_wallet_decision_error(exc: ModeloIvaWalletReconciliationBlocked) -> None:
    if exc.translated_message is None:
        assert "requires a persisted IVA wallet" in str(exc)
        return
    assert exc.translated_message == "application.modelo.errors.iva_wallet_not_seeded"
    assert exc.suggestion is not None
    assert "iva-wallet seed" in exc.suggestion


def test_non_blocking_iva_wallet_decision_supplies_modelo_303_binding() -> None:
    caller: dict[str, Decimal] = {}
    backend: dict[str, Decimal] = {}

    _apply(caller_binding_values=caller, backend_binding_values=backend, decision=_decision())

    assert backend["modelo-303-compensacion-pendiente-anteriores"] == Decimal("1200")


def test_blocked_iva_wallet_decision_refuses_modelo_303_automatic_calculation() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="blocks automatic Modelo 303 calculation"):
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            Period.from_year_and_code(2026, "2T"),
            bucket_id="operator",
            revision=_revision(),
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={},
            backend_casilla_inputs={},
            caller_binding_values={},
            backend_binding_values={},
            decision=_decision(blocked=True, amount=None),
        )


def test_caller_binding_conflict_with_wallet_decision_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            Period.from_year_and_code(2026, "2T"),
            bucket_id="operator",
            revision=_revision(),
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={},
            backend_casilla_inputs={},
            caller_binding_values={"modelo-303-compensacion-pendiente-anteriores": Decimal("800")},
            backend_binding_values={},
            decision=_decision(),
        )
    assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_caller_binding_conflict"


def test_modelo_303_prior_compensation_binding_without_wallet_decision_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            Period.from_year_and_code(2026, "2T"),
            bucket_id="operator",
            revision=_revision(),
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={},
            backend_casilla_inputs={},
            caller_binding_values={"modelo-303-compensacion-pendiente-anteriores": Decimal("800")},
            backend_binding_values={},
            decision=None,
        )
    _assert_missing_wallet_decision_error(exc_info.value)


def test_modelo_303_without_prior_compensation_binding_can_calculate_without_wallet_decision() -> None:
    caller: dict[str, Decimal] = {}
    backend: dict[str, Decimal] = {"modelo-303-iva-repercutido-general-cuota": Decimal("100")}

    _apply(caller_binding_values=caller, backend_binding_values=backend, decision=None)

    assert backend == {"modelo-303-iva-repercutido-general-cuota": Decimal("100")}


def test_modelo_303_prior_compensation_casilla_without_wallet_decision_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            Period.from_year_and_code(2026, "2T"),
            bucket_id="operator",
            revision=_revision(),
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={"iva.compensacion-pendiente-periodos-anteriores": Decimal("800")},
            backend_casilla_inputs={},
            caller_binding_values={},
            backend_binding_values={},
            decision=None,
        )
    _assert_missing_wallet_decision_error(exc_info.value)


def test_modelo_303_backend_prior_compensation_casilla_without_wallet_decision_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            Period.from_year_and_code(2026, "2T"),
            bucket_id="operator",
            revision=_revision(),
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={},
            backend_casilla_inputs={"iva.compensacion-pendiente-periodos-anteriores": Decimal("800")},
            caller_binding_values={},
            backend_binding_values={},
            decision=None,
        )
    _assert_missing_wallet_decision_error(exc_info.value)


def test_modelo_303_wallet_decision_for_other_taxpayer_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            Period.from_year_and_code(2026, "2T"),
            bucket_id="operator",
            revision=_revision(),
            taxpayer_nif=_OTHER_TAXPAYER_REF,
            casilla_inputs={},
            backend_casilla_inputs={},
            caller_binding_values={},
            backend_binding_values={},
            decision=_decision(),
        )
    assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_taxpayer_mismatch"


def test_modelo_303_prior_compensation_casilla_conflict_with_wallet_decision_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="caller casilla"):
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            Period.from_year_and_code(2026, "2T"),
            bucket_id="operator",
            revision=_revision(),
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={"iva.compensacion-pendiente-periodos-anteriores": Decimal("800")},
            backend_casilla_inputs={},
            caller_binding_values={},
            backend_binding_values={},
            decision=_decision(),
        )
