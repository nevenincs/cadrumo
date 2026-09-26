"""Pilot proof that work income is captured from its paying ledger transaction.

The paying transaction is stored through the canonical encrypted transaction
repository and read back through the same addressed lookup the installed host
composes.  Every expected figure derives from the synthetic payslip below.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from textual.widgets import Static

from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from cadrumo.application.aggregation.retenciones import RetencionObservation
from cadrumo.application.aggregation.tests.ledger_transaction_support import ledger_raw_transaction
from cadrumo.core.aggregation import BindingSourceKind, RetencionClave
from cadrumo.core.period import Period
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.withholding.installed import _read_ledger_payment
from cadrumo.entrypoints.tui.withholding.screen import WithholdingEvidenceScreen

from .test_screen import _choice, _click, _door_for, _set, _status

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

# One synthetic May 2025 payslip: 2500.00 gross, 15% IRPF (375.00), and the
# employee's 6.35% Social Security share (158.75) also withheld by the payer,
# so the bank paid 2500.00 - 375.00 - 158.75 = 1966.25.
_PAYROLL_GROSS = Decimal("2500.00")
_PAYROLL_IRPF = Decimal("375.00")
_PAYROLL_NET = _PAYROLL_GROSS - _PAYROLL_IRPF - Decimal("158.75")
_PAYROLL_PAID_ON = date(2025, 5, 30)
_PAYROLL_QUARTER = Period.from_year_and_code(2025, "2T")


def _seed_payroll_payment(profile: TestRuntimeProfile, *, amount: Decimal = _PAYROLL_NET) -> Transaction:
    """Store the outgoing EUR net-salary payment through the canonical repository."""
    transaction = Transaction.model_validate(
        {
            "raw": ledger_raw_transaction("tui-payroll-2025-05", booked_date=_PAYROLL_PAID_ON, amount=amount),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "group_label": None,
        }
    )
    TransactionCatalogueRepository(bucket_id=profile.bucket_id, objects=profile.repository).save(
        TransactionCatalogue.from_transactions([transaction])
    )
    return transaction


def _fill_payroll(screen: WithholdingEvidenceScreen, transaction_id: str, *, net: Decimal = _PAYROLL_NET) -> None:
    """Enter every declared payroll fact explicitly; nothing is inferred from the payment."""
    _choice(screen, "income-kind", "work")
    _set(screen, "scheme", "rendimientos_trabajo")
    _set(screen, "transaction-id", transaction_id)
    _set(screen, "payment-id", "tui-payroll-payment-2025-05")
    _set(screen, "payment-date", _PAYROLL_PAID_ON.isoformat())
    _set(screen, "allocation-id", "tui-payroll-allocation-2025-05")
    _set(screen, "allocated-base", str(_PAYROLL_GROSS))
    _set(screen, "allocated-withholding", str(_PAYROLL_IRPF))
    _set(screen, "allocated-settlement", str(net))
    _set(screen, "idempotency-key", "tui-payroll-capture-2025-05")
    _set(screen, "perceptor-nif", "11111111H")
    _set(screen, "perceptor-name", "Empleada Sintetica")
    _set(screen, "clave", "A")
    _set(screen, "province", "28")
    _set(screen, "deductible-expenses", "0.00")
    _set(screen, "territorial-deduction", "0")
    _set(screen, "annual-percentage", "15.00")
    _set(screen, "inspect-modelo", "111")
    _set(screen, "inspect-period", "2025-2T")


def _inspection_text(screen: WithholdingEvidenceScreen) -> str:
    return str(screen.query_one("#withholding-inspection", Static).render())


def _no_invoice(supplied: str) -> None:
    raise AssertionError(f"work income read the invoice catalogue for {supplied}")


def _payroll_screen(profile: TestRuntimeProfile) -> WithholdingEvidenceScreen:
    transactions = TransactionCatalogueRepository(bucket_id=profile.bucket_id, objects=profile.repository)
    return WithholdingEvidenceScreen(
        door=_door_for(profile.repository),
        invoice_lookup=_no_invoice,
        ledger_payment_lookup=lambda transaction_id: _read_ledger_payment(transactions, transaction_id),
        filing_year=2025,
    )


def _stored_q2(profile: TestRuntimeProfile) -> tuple[RetencionObservation, ...]:
    return RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations("111", _PAYROLL_QUARTER)


@pytest.mark.asyncio
async def test_pilot_captures_payroll_from_its_ledger_payment_and_inspects_modelo_111(tmp_path: Path) -> None:
    """The operator's work capture writes the 111 retención and its 190 row, then replays."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        transaction = _seed_payroll_payment(profile)
        screen = _payroll_screen(profile)
        async with ScreenHostApp(screen).run_test(size=(160, 60)) as pilot:
            await pilot.pause()
            _fill_payroll(screen, transaction.transaction_id)
            await _click(pilot, screen, "#withholding-inspect")
            assert "0 active projections" in _inspection_text(screen)
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "captured"
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "replayed"
            await _click(pilot, screen, "#withholding-inspect")
            assert "111 2T: 2 active projections" in _inspection_text(screen)
            pilot.app.exit(None)

        stored = _stored_q2(profile)
        annual = PercepcionObservationRepositoryAdapter(objects=profile.repository).load_annual_source_observations(
            "111", 2025
        )

    assert len(stored) == 1
    observation = stored[0]
    assert observation.source_kind is BindingSourceKind.LEDGER_TRANSACTION
    assert observation.source_object_id == transaction.transaction_id
    assert (observation.taxable_base, observation.retencion_amount) == (_PAYROLL_GROSS, _PAYROLL_IRPF)
    assert observation.accrued_on == _PAYROLL_PAID_ON.isoformat()
    assert len(annual) == 1
    assert annual[0].clave == RetencionClave.from_registry("A")
    assert annual[0].perceptor_legal_name == "Empleada Sintetica"
    assert annual[0].source_allocation_id == "tui-payroll-allocation-2025-05"


@pytest.mark.asyncio
async def test_pilot_refuses_payroll_whose_paid_amount_is_not_the_declared_net(tmp_path: Path) -> None:
    """A net the bank did not pay refuses with the producer's code and writes nothing."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        transaction = _seed_payroll_payment(profile)
        screen = _payroll_screen(profile)
        async with ScreenHostApp(screen).run_test(size=(160, 60)) as pilot:
            await pilot.pause()
            _fill_payroll(screen, transaction.transaction_id, net=_PAYROLL_NET - Decimal("0.01"))
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "refused: paid_amount_settlement_mismatch"
            # The perceptor is required evidence, never a blank default.
            _fill_payroll(screen, transaction.transaction_id)
            _set(screen, "perceptor-name", "")
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "refused: invalid_withholding_evidence"
            # Deductible expenses are declared evidence for work income; a blank
            # field is not a zero, and no payer fact is prefilled to stand in.
            _fill_payroll(screen, transaction.transaction_id)
            _set(screen, "deductible-expenses", "")
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "refused: invalid_withholding_evidence"
            _fill_payroll(screen, transaction.transaction_id)
            _set(screen, "clave", "")
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "refused: invalid_withholding_evidence"
            pilot.app.exit(None)

        assert _stored_q2(profile) == ()


@pytest.mark.asyncio
async def test_pilot_refuses_payroll_for_a_transaction_the_ledger_does_not_hold(tmp_path: Path) -> None:
    """A well-formed but unknown transaction id refuses before any write."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        _seed_payroll_payment(profile)
        screen = _payroll_screen(profile)
        async with ScreenHostApp(screen).run_test(size=(160, 60)) as pilot:
            await pilot.pause()
            _fill_payroll(screen, "f" * 64)
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "refused: transaction_not_found"
            pilot.app.exit(None)

        assert _stored_q2(profile) == ()
