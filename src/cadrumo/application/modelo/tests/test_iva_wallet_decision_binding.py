"""Modelo 303 calculation guard for IVA wallet reconciliation decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.operator_action_enums import ActionConditionality, NoRecoveryOutcome
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ids import BindingId
from ....domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from .._iva_wallet_gate import (
    ModeloIvaWalletReconciliationBlocked,
)
from .._iva_wallet_gate import (
    apply_iva_compensation_decision_binding as _apply_iva_compensation_decision_binding,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "34343434-3434-4343-8343-343434343434"
_TAXPAYER_REF = "taxpayeralpha"
_OTHER_TAXPAYER_REF = "othertaxpayeralpha"
_M303_PRIOR_COMPENSATION_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores",
    surface="_M303_PRIOR_COMPENSATION_CASILLA",
)
_M303_PRIOR_COMPENSATION_BINDING: BindingId = "modelo-303-compensacion-pendiente-anteriores"
_M303_REPERCUTIDO_GENERAL_CUOTA_BINDING: BindingId = "modelo-303-iva-repercutido-general-cuota"


def test_wallet_missing_taxpayer_is_an_application_owned_no_action_outcome() -> None:
    """A wallet decision without taxpayer identity carries no CLI recovery prose."""
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as raised:
        _apply(taxpayer_nif=None, decision=_decision())

    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.action is None
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


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
        reason_identity=("wallet_local_recurrence_divergence" if blocked else "aeat_wallet_validated"),
        wallet_captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        decided_at=datetime(2026, 5, 19, 12, 1, 0, tzinfo=UTC),
    )


def _revision():
    return bundled_authority().snapshot("303", filing_year=2026, period="2T").revision


def _apply(
    *,
    taxpayer_nif: str | None = _TAXPAYER_REF,
    casilla_inputs: dict[CasillaId, Decimal] | None = None,
    backend_casilla_inputs: dict[CasillaId, Decimal] | None = None,
    caller_binding_values: dict[BindingId, Decimal] | None = None,
    backend_binding_values: dict[BindingId, Decimal] | None = None,
    decision: IvaCompensationReconciliationDecision | None = None,
) -> None:
    _apply_iva_compensation_decision_binding(
        "303",
        2026,
        Period.from_year_and_code(2026, "2T"),
        bucket_id=_BUCKET_ID,
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
    assert not hasattr(exc, "suggestion")
    assert exc.precondition_failure.scenario_id == "modelo.work.calculate.iva_wallet.not_seeded"


def test_non_blocking_iva_wallet_decision_supplies_modelo_303_binding() -> None:
    caller: dict[BindingId, Decimal] = {}
    backend: dict[BindingId, Decimal] = {}

    _apply(caller_binding_values=caller, backend_binding_values=backend, decision=_decision())

    assert backend[_M303_PRIOR_COMPENSATION_BINDING] == Decimal("1200")


def test_blocked_iva_wallet_decision_refuses_modelo_303_automatic_calculation() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            Period.from_year_and_code(2026, "2T"),
            bucket_id=_BUCKET_ID,
            revision=_revision(),
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={},
            backend_casilla_inputs={},
            caller_binding_values={},
            backend_binding_values={},
            decision=_decision(blocked=True, amount=None),
        )
    assert (
        exc_info.value.translated_message == "application.iva_wallet.decision_reason.wallet_local_recurrence_divergence"
    )
    assert (
        exc_info.value.precondition_failure.scenario_id
        == "modelo.work.calculate.iva_wallet.wallet_local_recurrence_divergence"
    )


def test_blocked_wallet_refusal_precedes_caller_binding_conflict() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
        _apply(
            caller_binding_values={_M303_PRIOR_COMPENSATION_BINDING: Decimal("800")},
            decision=_decision(blocked=True, amount=None),
        )

    assert (
        exc_info.value.translated_message == "application.iva_wallet.decision_reason.wallet_local_recurrence_divergence"
    )


def test_target_mismatch_refusal_precedes_missing_taxpayer_identity() -> None:
    wrong_period = _decision().model_copy(
        update={"target_period": Period.from_year_and_code(2026, "1T")},
    )

    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
        _apply(taxpayer_nif=None, decision=wrong_period)

    assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_target_mismatch"


def test_caller_binding_conflict_with_wallet_decision_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            Period.from_year_and_code(2026, "2T"),
            bucket_id=_BUCKET_ID,
            revision=_revision(),
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={},
            backend_casilla_inputs={},
            caller_binding_values={_M303_PRIOR_COMPENSATION_BINDING: Decimal("800")},
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
            bucket_id=_BUCKET_ID,
            revision=_revision(),
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={},
            backend_casilla_inputs={},
            caller_binding_values={_M303_PRIOR_COMPENSATION_BINDING: Decimal("800")},
            backend_binding_values={},
            decision=None,
        )
    _assert_missing_wallet_decision_error(exc_info.value)


def test_modelo_303_without_prior_compensation_binding_can_calculate_without_wallet_decision() -> None:
    caller: dict[BindingId, Decimal] = {}
    backend: dict[BindingId, Decimal] = {_M303_REPERCUTIDO_GENERAL_CUOTA_BINDING: Decimal("100")}

    _apply(caller_binding_values=caller, backend_binding_values=backend, decision=None)

    assert backend == {_M303_REPERCUTIDO_GENERAL_CUOTA_BINDING: Decimal("100")}


def test_modelo_303_prior_compensation_casilla_without_wallet_decision_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            Period.from_year_and_code(2026, "2T"),
            bucket_id=_BUCKET_ID,
            revision=_revision(),
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={_M303_PRIOR_COMPENSATION_CASILLA: Decimal("800")},
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
            bucket_id=_BUCKET_ID,
            revision=_revision(),
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={},
            backend_casilla_inputs={_M303_PRIOR_COMPENSATION_CASILLA: Decimal("800")},
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
            bucket_id=_BUCKET_ID,
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
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            Period.from_year_and_code(2026, "2T"),
            bucket_id=_BUCKET_ID,
            revision=_revision(),
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={_M303_PRIOR_COMPENSATION_CASILLA: Decimal("800")},
            backend_casilla_inputs={},
            caller_binding_values={},
            backend_binding_values={},
            decision=_decision(),
        )
    assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_caller_casilla_conflict"


def test_backend_prior_compensation_casilla_conflict_with_wallet_decision_is_refused() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
        _apply(
            backend_casilla_inputs={_M303_PRIOR_COMPENSATION_CASILLA: Decimal("800")},
            decision=_decision(),
        )

    assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_backend_casilla_conflict"


def test_wallet_authority_replaces_the_existing_lower_precedence_backend_binding() -> None:
    backend = {_M303_PRIOR_COMPENSATION_BINDING: Decimal("800")}

    _apply(backend_binding_values=backend, decision=_decision())

    assert backend[_M303_PRIOR_COMPENSATION_BINDING] == Decimal("1200")
