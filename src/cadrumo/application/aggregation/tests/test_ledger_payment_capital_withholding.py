"""Movable-capital withholding captured from the ledger payment of the income."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from functools import partial
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.ledger_payment_withholding import (
    LedgerPaymentWithholdingCapture,
    LedgerPaymentWithholdingEvidenceError,
    LedgerPaymentWithholdingEvidenceRequest,
    build_ledger_payment_withholding_capture,
)
from cadrumo.application.aggregation.m193_phase_materialization import (
    Modelo193DisclosurePhase,
    materialize_modelo_193_disclosure_phases,
)
from cadrumo.application.aggregation.tests.ledger_capital_support import (
    CAPITAL_EXIGIBLE_ON,
    CAPITAL_GROSS,
    CAPITAL_HOLDER_NAME,
    CAPITAL_HOLDER_NIF,
    CAPITAL_IRPF,
    CAPITAL_NET,
    CAPITAL_PAID_ON,
    capital_payment,
    capital_pending_payment,
    capital_request,
    withholding_producer,
)
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    quarterly_filer_cadence,
    quarterly_filer_cadence_for,
)
from cadrumo.application.aggregation.withholding_producer import WithholdingProducerError
from cadrumo.application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
    WithholdingRecognitionRule,
)
from cadrumo.core.aggregation import BindingSourceKind, RetencionScheme
from cadrumo.core.period import Period
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import Transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_Q2_2025 = Period.from_year_and_code(2025, "2T")


def _build(
    transaction: Transaction,
    request: LedgerPaymentWithholdingEvidenceRequest,
    *,
    year: int = 2025,
) -> LedgerPaymentWithholdingCapture:
    return build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="c" * 64,
        request=request,
        applicable_year=year,
        cadence=quarterly_filer_cadence(year),
    )


def _refusal(transaction: Transaction, request: LedgerPaymentWithholdingEvidenceRequest, *, year: int = 2025) -> str:
    with pytest.raises(LedgerPaymentWithholdingEvidenceError) as exc_info:
        _build(transaction, request, year=year)
    return exc_info.value.refusal_code


def test_capital_payment_builds_a_123_capture_at_the_exigibility_quarter() -> None:
    """A July payment of a June-exigible coupon is recognised in June, so it lands in 2025 2T."""
    transaction = capital_payment()

    capture = _build(transaction, capital_request(transaction))

    command = capture.command
    assert capture.scope.modelo == "123"
    assert capture.scope.period == _Q2_2025
    assert command.source_kind is BindingSourceKind.LEDGER_TRANSACTION
    assert command.source_object_id == transaction.transaction_id
    assert (command.perceptor_nif, command.perceptor_name) == (CAPITAL_HOLDER_NIF, CAPITAL_HOLDER_NAME)
    assert (command.taxable_base, command.retencion_amount, command.settlement_amount) == (
        CAPITAL_GROSS,
        CAPITAL_IRPF,
        CAPITAL_NET,
    )
    assert command.modelo_190_detail is None
    assert command.modelo_193_pending_payment is None
    evidence = command.recognition_evidence
    assert evidence.income_kind is WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL
    assert evidence.exigibility is not None
    assert (evidence.exigibility.event_id, evidence.exigibility.occurred_on) == (
        "coupon-exigible-2025-06",
        CAPITAL_EXIGIBLE_ON,
    )
    assert evidence.payment_or_satisfaction is not None
    assert evidence.payment_or_satisfaction.occurred_on == CAPITAL_PAID_ON


def test_capital_payment_before_exigibility_is_recognised_on_the_payment() -> None:
    """An advance payment on 31 March of income exigible on 15 April belongs to 1T, not 2T."""
    transaction = capital_payment(provider_id="coupon-advance", booked_date=date(2025, 3, 31))

    capture = _build(transaction, capital_request(transaction, exigibility_occurred_on=date(2025, 4, 15)))

    assert capture.scope.period == Period.from_year_and_code(2025, "1T")


def test_capital_source_revision_binds_the_exigibility_event() -> None:
    """Correcting the exigibility date is a different liability fact, not the same source revision."""
    transaction = capital_payment()

    original = _build(transaction, capital_request(transaction))
    corrected = _build(transaction, capital_request(transaction, exigibility_occurred_on=date(2025, 6, 29)))

    assert corrected.command.source_revision_id != original.command.source_revision_id


def test_captured_capital_payment_is_stored_in_the_123_window_only(tmp_path: Path) -> None:
    """The shared producer stores one 123 retención and no Modelo 190 percepción for the coupon."""
    transaction = capital_payment()
    capture = _build(transaction, capital_request(transaction))

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        result = withholding_producer(profile.repository).capture(
            capture.command, cadence=quarterly_filer_cadence_for(capture.command)
        )
        replay = withholding_producer(profile.repository).capture(
            capture.command, cadence=quarterly_filer_cadence_for(capture.command)
        )
        stored = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations("123", _Q2_2025)
        payroll_window = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
            "111", _Q2_2025
        )
        annual_190 = PercepcionObservationRepositoryAdapter(objects=profile.repository).load_annual_source_observations(
            "111", 2025
        )

    assert result is not None
    assert result.scope == capture.scope
    assert result.recognition.rule is WithholdingRecognitionRule.EXIGIBILITY_OR_EARLIER_PAYMENT
    assert result.recognition.recognized_on == CAPITAL_EXIGIBLE_ON
    assert result.recognition.recognition_event_id == "coupon-exigible-2025-06"
    assert result.recognition.settlement_event_id == "coupon-payment-2025-07"
    assert replay is not None and replay.mutation.replayed
    assert len(stored) == 1
    row = stored[0]
    assert row.source_kind is BindingSourceKind.LEDGER_TRANSACTION
    assert row.source_object_id == transaction.transaction_id
    assert row.scheme == RetencionScheme("intereses")
    assert (row.taxable_base, row.retencion_amount, row.accrued_on) == (CAPITAL_GROSS, CAPITAL_IRPF, "2025-06-30")
    assert row.modelo_193_capital is None
    assert payroll_window == ()
    assert annual_190 == ()


def test_capital_paid_the_next_year_feeds_both_modelo_193_phases(tmp_path: Path) -> None:
    """A December coupon the holder collected in January is PENDING in 2025 and settled in 2026."""
    paid_on = date(2026, 1, 20)
    transaction = capital_payment(provider_id="coupon-2025-12", booked_date=paid_on)
    request = capital_request(
        transaction,
        payment_event_id="coupon-payment-2026-01",
        exigibility_occurred_on=date(2025, 12, 15),
        modelo_193_pending_payment=capital_pending_payment(transaction, transaction_date=paid_on),
    )
    capture = _build(transaction, request)

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        result = withholding_producer(profile.repository).capture(
            capture.command, cadence=quarterly_filer_cadence_for(capture.command)
        )
        stored = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
            "123", Period.from_year_and_code(2025, "4T")
        )

    assert result is not None
    assert result.scope == capture.scope
    assert capture.scope.period == Period.from_year_and_code(2025, "4T")
    assert len(stored) == 1
    pending = materialize_modelo_193_disclosure_phases(stored, filing_year=2025)
    settled = materialize_modelo_193_disclosure_phases(stored, filing_year=2026)
    assert [row.phase for row in pending] == [Modelo193DisclosurePhase.PENDING]
    assert [row.phase for row in settled] == [Modelo193DisclosurePhase.SETTLED_PRIOR_ACCRUAL]
    assert settled[0].annual_detail.perceptor_tax_id == CAPITAL_HOLDER_NIF
    assert settled[0].annual_detail.accrual_year == 2025
    assert settled[0].settlement_event_id == "coupon-payment-2026-01"


@pytest.mark.parametrize(
    ("make_transaction", "request_update", "code"),
    (
        (
            partial(capital_payment, booked_date=date(2026, 1, 20)),
            {"exigibility_occurred_on": date(2025, 12, 15)},
            "capital_paid_after_accrual_year_without_pending_evidence",
        ),
        (
            partial(capital_payment, booked_date=date(2025, 1, 10)),
            {"exigibility_occurred_on": date(2024, 12, 20)},
            "recognition_outside_applicable_year",
        ),
        (partial(capital_payment, direction=TransactionDirection.INCOMING), {}, "transaction_not_outgoing_payment"),
        (partial(capital_payment, amount=Decimal("809.99")), {}, "paid_amount_settlement_mismatch"),
        (capital_payment, {"net_settlement": Decimal("810.01")}, "settlement_exceeds_gross_less_withholding"),
        (capital_payment, {"recipient_tax_status": WithholdingRecipientTaxStatus.NONRESIDENT}, "recipient_nonresident"),
        (
            capital_payment,
            {"recipient_tax_status": WithholdingRecipientTaxStatus.UNKNOWN},
            "recipient_residence_unknown",
        ),
        (
            capital_payment,
            {"recipient_tax_regime": WithholdingRecipientTaxRegime.IS},
            "corporate_income_tax_unsupported",
        ),
    ),
)
def test_capital_capture_refuses_before_any_command_exists(
    make_transaction: Callable[[], Transaction],
    request_update: dict[str, object],
    code: str,
) -> None:
    """Each unprovable capital payment, timing or recipient fact refuses with its own stable code."""
    transaction = make_transaction()

    assert _refusal(transaction, capital_request(transaction, **request_update)) == code


@pytest.mark.parametrize(
    ("request_update", "message"),
    (
        (
            {"exigibility_event_id": None, "exigibility_occurred_on": None},
            "ordinary movable capital income requires exigibility evidence",
        ),
        ({"exigibility_occurred_on": None}, "exigibility evidence requires both event id and date"),
        ({"perceptor_nif": None}, "ordinary movable capital income requires the perceptor NIF"),
        ({"perceptor_name": None}, "ordinary movable capital income requires the perceptor name"),
        ({"perceptor_name": "   "}, "ordinary movable capital income requires the perceptor name"),
        ({"income_kind": WithholdingIncomeKind.PROFESSIONAL}, "work or ordinary movable capital income only"),
        ({"income_kind": WithholdingIncomeKind.URBAN_RENT}, "work or ordinary movable capital income only"),
        ({"income_kind": WithholdingIncomeKind.INVESTMENT_FUND}, "work or ordinary movable capital income only"),
    ),
)
def test_capital_request_refuses_an_incomplete_or_foreign_shape(
    request_update: dict[str, object], message: str
) -> None:
    """The transport refuses missing capital evidence and income kinds a ledger payment cannot prove."""
    transaction = capital_payment()

    with pytest.raises(ValidationError, match=message):
        capital_request(transaction, **request_update)


def test_capital_payment_under_a_work_scheme_is_refused_by_the_shared_producer(tmp_path: Path) -> None:
    """The producer owns the scheme-to-income table, so a payroll scheme never reaches the 123 window."""
    transaction = capital_payment()
    capture = _build(transaction, capital_request(transaction, scheme=RetencionScheme("rendimientos_trabajo")))

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        with pytest.raises(WithholdingProducerError) as exc_info:
            withholding_producer(profile.repository).capture(
                capture.command, cadence=quarterly_filer_cadence_for(capture.command)
            )
        stored = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations("123", _Q2_2025)

    assert exc_info.value.refusal_code == "scheme_income_kind_mismatch"
    assert stored == ()


def test_pending_evidence_with_a_same_year_payment_is_refused_by_the_shared_producer(tmp_path: Path) -> None:
    """A coupon paid in its own year was collected, so the holder-not-presented cause contradicts it."""
    transaction = capital_payment()
    request = capital_request(
        transaction,
        modelo_193_pending_payment=capital_pending_payment(transaction, transaction_date=CAPITAL_PAID_ON),
    )
    capture = _build(transaction, request)

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        with pytest.raises(WithholdingProducerError) as exc_info:
            withholding_producer(profile.repository).capture(
                capture.command, cadence=quarterly_filer_cadence_for(capture.command)
            )
        stored = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations("123", _Q2_2025)

    assert exc_info.value.refusal_code == "modelo_193_nonpayment_cause_conflicts_with_same_year_settlement"
    assert stored == ()
