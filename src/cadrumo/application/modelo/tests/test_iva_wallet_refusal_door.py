"""An IVA wallet block on Modelo 303 is a refusal with a door to Saldo de IVA, never a failure.

The carried compensation of a 303 needs an authority the filer can supply: the
AEAT wallet captured, the amount declared on the previous return registered, or
a taxpayer override. Until one exists the calculation is refused, effect none,
and the refusal opens the declaration's Saldo de IVA, where each of those is
recorded. A registry that cannot be read is not the filer's to put right, so
that one stays a failure.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code
from ....core.period import Period
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.iva_compensation.reconciliation import (
    IvaCompensationAuthoritySource,
    IvaCompensationReconciliationDecision,
)
from ...operations.error_detail import build_operation_error_detail
from ...operations.next_step import OperationOpenIvaWalletStepV1
from ..iva_wallet_binding import apply_iva_compensation_decision_binding
from ..iva_wallet_refusal import (
    ModeloIvaWalletAuthorityUnavailableError,
    ModeloIvaWalletReconciliationBlockedError,
    iva_wallet_door,
)

pytestmark = [pytest.mark.usefixtures("authority_operation"), pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "34343434-3434-4343-8343-343434343434"
_WORK_UNIT_ID = "b" * 64
_TAXPAYER_REF = "taxpayeralpha"


def _blocked_decision() -> IvaCompensationReconciliationDecision:
    snapshot_ref = published_snapshot("303", filing_year=2026, period="2T").snapshot_ref
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        target_registry_snapshot_ref=snapshot_ref,
        source_registry_snapshot_refs=(snapshot_ref,),
        selected_authority="missing",
        selected_amount=None,
        wallet_amount=Decimal("1200"),
        local_recurrence_amount=Decimal("800"),
        authority_sources=(
            IvaCompensationAuthoritySource(
                source_kind="local_recurrence",
                amount=Decimal("800"),
                source_locator="test:local-recurrence:2026:2T",
                source_modelo="303",
                source_filing_year=2026,
                source_periods=(Period.from_year_and_code(2026, "2T"),),
                registry_snapshot_refs=(snapshot_ref,),
            ),
        ),
        override_amount=None,
        divergence="wallet_higher",
        blocked=True,
        stale_wallet=False,
        reason_identity="wallet_local_recurrence_divergence",
        wallet_captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        decided_at=datetime(2026, 5, 19, 12, 1, 0, tzinfo=UTC),
    )


def _refused_through_the_door() -> ModeloIvaWalletReconciliationBlockedError:
    with pytest.raises(ModeloIvaWalletReconciliationBlockedError) as raised, iva_wallet_door(_WORK_UNIT_ID):
        apply_iva_compensation_decision_binding(
            "303",
            2026,
            Period.from_year_and_code(2026, "2T"),
            bucket_id=_BUCKET_ID,
            revision=published_snapshot("303", filing_year=2026, period="2T").revision,
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={},
            backend_casilla_inputs={},
            caller_binding_values={},
            backend_binding_values={},
            decision=_blocked_decision(),
        )
    return raised.value


def test_a_wallet_block_is_registered_as_a_refusal() -> None:
    """DISCRIMINATING: the supervisor settles a REFUSED registration as refused, not failed."""
    assert get_registered_error_code(ModeloIvaWalletReconciliationBlockedError).category is ErrorCategory.REFUSED


def test_a_blocked_wallet_refusal_opens_the_declaration_s_saldo_de_iva() -> None:
    error = _refused_through_the_door()

    assert get_registered_error_code(error).category is ErrorCategory.REFUSED
    detail = build_operation_error_detail(error)
    assert detail is not None
    assert isinstance(detail.next_step, OperationOpenIvaWalletStepV1)
    assert detail.next_step.work_unit_id == _WORK_UNIT_ID
    assert detail.next_step.words.strip() != ""


def test_an_unreadable_registry_stays_a_failure() -> None:
    """ANTI-VACUITY: only the filer's own precondition becomes a refusal."""
    assert get_registered_error_code(ModeloIvaWalletAuthorityUnavailableError).category is ErrorCategory.ERROR
    assert issubclass(ModeloIvaWalletAuthorityUnavailableError, ModeloIvaWalletReconciliationBlockedError)
