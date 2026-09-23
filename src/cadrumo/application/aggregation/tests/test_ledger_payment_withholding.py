"""Payroll withholding captured from the ledger payment that settled the net salary."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from functools import partial
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.withholding_observation_workflow import WithholdingObservationWorkflowAdapter
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.ledger_payment_withholding import (
    LedgerPaymentWithholdingEvidenceError,
    LedgerPaymentWithholdingEvidenceRequest,
    build_ledger_payment_withholding_capture,
    resolve_ledger_payment_transaction,
)
from cadrumo.application.aggregation.tests.ledger_transaction_support import ledger_raw_transaction
from cadrumo.application.aggregation.withholding_observation_service import WithholdingObservationService
from cadrumo.application.aggregation.withholding_producer import WithholdingProducer, WithholdingProducerError
from cadrumo.application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
    WithholdingRecognitionRule,
)
from cadrumo.core.aggregation import BindingSourceKind, RetencionClave, RetencionScheme
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation
from cadrumo.domain.transactions.enums import TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

# One synthetic May 2025 payslip: 2500.00 gross, 15% IRPF (375.00), and the
# employee's 6.35% Social Security share (158.75) also withheld by the payer,
# so the bank paid 2500.00 - 375.00 - 158.75 = 1966.25.
_GROSS = Decimal("2500.00")
_IRPF = Decimal("375.00")
_EMPLOYEE_SOCIAL_SECURITY = Decimal("158.75")
_NET = _GROSS - _IRPF - _EMPLOYEE_SOCIAL_SECURITY
_PAID_ON = date(2025, 5, 30)
_EMPLOYEE_NIF = "11111111H"


def _payroll_payment(
    *,
    provider_id: str = "payroll-2025-05",
    amount: Decimal = _NET,
    booked_date: date = _PAID_ON,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    currency: str = "EUR",
    value_in_eur: Decimal | None = None,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    raw = ledger_raw_transaction(provider_id, booked_date=booked_date, amount=amount)
    if currency != raw.currency:
        raw = raw.model_copy(update={"currency": currency})
    fields: dict[str, object] = {
        "raw": raw,
        "direction": direction,
        "source_jurisdiction": "ES",
        "group_label": None,
        "lifecycle_state": lifecycle_state,
    }
    if value_in_eur is not None:
        fields["value_in_eur"] = value_in_eur
        fields["fx_rate"] = Decimal("1.08")
    return Transaction.model_validate(fields)


def _annual_detail(transaction: Transaction, *, paid_on: date = _PAID_ON) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=transaction.transaction_id,
        perceptor_tax_id=_EMPLOYEE_NIF,
        perceptor_legal_name="Empleada Sintetica",
        transaction_date=paid_on,
        clave=RetencionClave.from_registry("A"),
        percibido_dinerario=_GROSS,
        retencion_practicada=_IRPF,
        incapacity_cash_perception=Decimal("0"),
        incapacity_cash_withholding=Decimal("0"),
        incapacity_kind_value=Decimal("0"),
        incapacity_kind_ingreso_a_cuenta=Decimal("0"),
        incapacity_kind_repercutido=Decimal("0"),
        foral_retention_estatal=Decimal("0"),
        foral_retention_navarra=Decimal("0"),
        foral_retention_araba=Decimal("0"),
        foral_retention_gipuzkoa=Decimal("0"),
        foral_retention_bizkaia=Decimal("0"),
        base_retenciones=_GROSS,
        porcentaje_retencion=Decimal("15"),
        gastos_deducibles=_EMPLOYEE_SOCIAL_SECURITY,
    )


def _request(transaction: Transaction, **update: object) -> LedgerPaymentWithholdingEvidenceRequest:
    payload: dict[str, object] = {
        "transaction_id": transaction.transaction_id,
        "scheme": RetencionScheme("rendimientos_trabajo"),
        "recipient_tax_status": WithholdingRecipientTaxStatus.RESIDENT,
        "recipient_tax_regime": WithholdingRecipientTaxRegime.IRPF,
        "payment_event_id": "payroll-payment-2025-05",
        "allocation_id": "payroll-allocation-2025-05",
        "gross_base": _GROSS,
        "withholding_amount": _IRPF,
        "net_settlement": _NET,
        "idempotency_key": "payroll-capture-2025-05",
        "modelo_190_detail": _annual_detail(transaction),
    }
    return LedgerPaymentWithholdingEvidenceRequest.model_validate(payload | update)


def _refusal(transaction: Transaction, request: LedgerPaymentWithholdingEvidenceRequest, *, year: int = 2025) -> str:
    with pytest.raises(LedgerPaymentWithholdingEvidenceError) as exc_info:
        build_ledger_payment_withholding_capture(
            transaction,
            catalogue_revision_id="a" * 64,
            request=request,
            applicable_year=year,
        )
    return exc_info.value.refusal_code


def test_ledger_payment_builds_a_work_income_capture_for_its_quarter() -> None:
    """The paying transaction supplies source identity and the dated payment; the terms are declared."""
    transaction = _payroll_payment()

    capture = build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="a" * 64,
        request=_request(transaction),
        applicable_year=2025,
    )

    command = capture.command
    assert capture.scope.modelo == "111"
    assert capture.scope.period == Period.from_year_and_code(2025, "2T")
    assert capture.catalogue_read_revision_id == "a" * 64
    assert command.source_kind is BindingSourceKind.LEDGER_TRANSACTION
    assert command.source_object_id == transaction.transaction_id
    assert command.liability_snapshot.source_revision_id == command.source_revision_id
    assert command.perceptor_nif == _EMPLOYEE_NIF
    assert (command.taxable_base, command.retencion_amount, command.settlement_amount) == (_GROSS, _IRPF, _NET)
    assert (
        command.liability_snapshot.liability_base,
        command.liability_snapshot.liability_withholding,
        command.liability_snapshot.liability_settlement,
    ) == (_GROSS, _IRPF, _NET)
    payment = command.recognition_evidence.payment_or_satisfaction
    assert payment is not None
    assert payment.occurred_on == _PAID_ON
    assert payment.event_id == "payroll-payment-2025-05"
    assert command.recognition_evidence.income_kind is WithholdingIncomeKind.WORK


def test_source_revision_is_stable_across_unrelated_catalogue_revisions() -> None:
    """Another ledger write cannot strand this payment behind a false liability conflict."""
    transaction = _payroll_payment()
    first = build_ledger_payment_withholding_capture(
        transaction, catalogue_revision_id="a" * 64, request=_request(transaction), applicable_year=2025
    )
    later = build_ledger_payment_withholding_capture(
        transaction, catalogue_revision_id="b" * 64, request=_request(transaction), applicable_year=2025
    )
    corrected = build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="b" * 64,
        request=_request(transaction, gross_base=Decimal("2400.00")),
        applicable_year=2025,
    )

    assert first.command.source_revision_id == later.command.source_revision_id
    assert corrected.command.source_revision_id != first.command.source_revision_id


def test_settlement_below_gross_less_withholding_is_accepted_and_equality_too() -> None:
    """Employee deductions other than IRPF may lower the net, and an equal net is also valid."""
    exact_net = _GROSS - _IRPF
    transaction = _payroll_payment(provider_id="payroll-exact", amount=exact_net)
    capture = build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="a" * 64,
        request=_request(transaction, net_settlement=exact_net),
        applicable_year=2025,
    )

    assert capture.command.settlement_amount == Decimal("2125.00")


@pytest.mark.parametrize(
    ("make_transaction", "request_update", "year", "code"),
    (
        (
            partial(_payroll_payment, direction=TransactionDirection.INCOMING),
            {},
            2025,
            "transaction_not_outgoing_payment",
        ),
        (
            partial(_payroll_payment, direction=TransactionDirection.INTERNAL_TRANSFER),
            {},
            2025,
            "transaction_not_outgoing_payment",
        ),
        (
            partial(_payroll_payment, lifecycle_state=TransactionLifecycleState.ARCHIVED),
            {},
            2025,
            "transaction_not_active",
        ),
        (partial(_payroll_payment, currency="USD"), {}, 2025, "payment_eur_amount_unavailable"),
        (partial(_payroll_payment, currency="USD", value_in_eur=_NET), {}, 2025, "payment_currency_not_eur"),
        (_payroll_payment, {"withholding_amount": Decimal("2500.01")}, 2025, "withholding_exceeds_gross_base"),
        (_payroll_payment, {"net_settlement": Decimal("2125.01")}, 2025, "settlement_exceeds_gross_less_withholding"),
        (partial(_payroll_payment, amount=Decimal("1966.24")), {}, 2025, "paid_amount_settlement_mismatch"),
        (
            _payroll_payment,
            {"recipient_tax_status": WithholdingRecipientTaxStatus.NONRESIDENT},
            2025,
            "recipient_nonresident",
        ),
        (
            _payroll_payment,
            {"recipient_tax_status": WithholdingRecipientTaxStatus.UNKNOWN},
            2025,
            "recipient_residence_unknown",
        ),
        (_payroll_payment, {"recipient_tax_regime": WithholdingRecipientTaxRegime.IRNR}, 2025, "irnr_unsupported"),
        (
            _payroll_payment,
            {"recipient_tax_regime": WithholdingRecipientTaxRegime.UNKNOWN},
            2025,
            "unknown_recipient_tax_regime",
        ),
        (partial(_payroll_payment, booked_date=date(2024, 5, 30)), {}, 2024, "unsupported_applicable_year"),
        (partial(_payroll_payment, booked_date=date(2026, 1, 5)), {}, 2025, "payment_outside_applicable_year"),
    ),
)
def test_capture_refuses_before_any_command_exists(
    make_transaction: Callable[[], Transaction],
    request_update: dict[str, object],
    year: int,
    code: str,
) -> None:
    """Each unprovable payment or recipient fact refuses with its own stable code."""
    transaction = make_transaction()

    assert _refusal(transaction, _request(transaction, **request_update), year=year) == code


def test_request_for_another_transaction_is_refused() -> None:
    """A request cannot borrow a different payment's date or amount."""
    transaction = _payroll_payment()
    other = _payroll_payment(provider_id="payroll-other")

    assert _refusal(transaction, _request(other)) == "transaction_identity_mismatch"


def test_unknown_transaction_id_is_refused_by_the_catalogue_lookup() -> None:
    """An id the catalogue does not hold is a refusal, never an empty capture."""
    held = _payroll_payment()
    missing = _payroll_payment(provider_id="payroll-never-stored")
    catalogue = TransactionCatalogue.from_transactions([held])

    assert resolve_ledger_payment_transaction(catalogue, held.transaction_id) == held
    with pytest.raises(LedgerPaymentWithholdingEvidenceError) as exc_info:
        resolve_ledger_payment_transaction(catalogue, missing.transaction_id)
    assert exc_info.value.refusal_code == "transaction_not_found"


@pytest.mark.parametrize(
    "income_kind",
    (
        WithholdingIncomeKind.PROFESSIONAL,
        WithholdingIncomeKind.URBAN_RENT,
        WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL,
    ),
)
def test_request_accepts_work_income_only(income_kind: WithholdingIncomeKind) -> None:
    """A salary payment is never evidence for professional, rent or capital income."""
    transaction = _payroll_payment()

    with pytest.raises(ValidationError, match="work income only"):
        _request(transaction, income_kind=income_kind)


def test_request_refuses_a_caller_authored_recognition_date() -> None:
    """The transport carries the payment reference, never a derived filing coordinate."""
    transaction = _payroll_payment()
    payload = _request(transaction).model_dump(mode="json") | {"recognized_on": "2025-05-30"}

    with pytest.raises(ValidationError, match="recognized_on"):
        LedgerPaymentWithholdingEvidenceRequest.model_validate_json(json.dumps(payload))


def _producer(objects: object) -> WithholdingProducer:
    from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository

    assert isinstance(objects, SecureObjectRepository)
    return WithholdingProducer(
        service=WithholdingObservationService(
            WithholdingObservationWorkflowAdapter(
                objects=objects,
                retenciones=RetencionObservationRepositoryAdapter(objects=objects),
                percepciones=PercepcionObservationRepositoryAdapter(objects=objects),
            )
        )
    )


def test_captured_payment_projects_a_work_retencion_and_its_annual_row(tmp_path: Path) -> None:
    """The shared producer stores one 111 retención and one 190 percepción for the payment."""
    transaction = _payroll_payment()
    capture = build_ledger_payment_withholding_capture(
        transaction, catalogue_revision_id="a" * 64, request=_request(transaction), applicable_year=2025
    )

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        result = _producer(profile.repository).capture(capture.command)
        replay = _producer(profile.repository).capture(capture.command)
        retenciones = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
            "111", Period.from_year_and_code(2025, "2T")
        )
        annual = PercepcionObservationRepositoryAdapter(objects=profile.repository).load_annual_source_observations(
            "111", 2025
        )

    assert result is not None
    assert result.scope == capture.scope
    assert result.recognition.rule is WithholdingRecognitionRule.PAID_OR_SATISFIED
    assert result.recognition.recognized_on == _PAID_ON
    assert replay is not None and replay.mutation.replayed
    assert len(retenciones) == 1
    stored = retenciones[0]
    assert stored.source_kind is BindingSourceKind.LEDGER_TRANSACTION
    assert stored.source_object_id == transaction.transaction_id
    assert stored.scheme == RetencionScheme("rendimientos_trabajo")
    assert (stored.taxable_base, stored.retencion_amount, stored.accrued_on) == (_GROSS, _IRPF, "2025-05-30")
    assert len(annual) == 1
    assert annual[0].clave == RetencionClave.from_registry("A")
    assert annual[0].source_allocation_id == "payroll-allocation-2025-05"


def test_non_work_scheme_is_refused_by_the_shared_producer(tmp_path: Path) -> None:
    """The producer, not this builder, owns the scheme-to-income table."""
    transaction = _payroll_payment()
    capture = build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="a" * 64,
        request=_request(transaction, scheme=RetencionScheme("actividades_profesionales")),
        applicable_year=2025,
    )

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        with pytest.raises(WithholdingProducerError) as exc_info:
            _producer(profile.repository).capture(capture.command)
        stored = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
            "111", Period.from_year_and_code(2025, "2T")
        )

    assert exc_info.value.refusal_code == "scheme_income_kind_mismatch"
    assert stored == ()
