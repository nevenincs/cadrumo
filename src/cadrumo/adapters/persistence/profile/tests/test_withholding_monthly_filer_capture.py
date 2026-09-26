"""A filer whose schedule is not quarterly cannot capture withholding into a quarterly window.

The filers are real profile records whose cadence comes from the published
Modelo 111 and 123 filing schedules. Every capture path runs over the real
encrypted store, and after each refusal the quarter it would have used is read
back empty.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.tests.ledger_capital_support import (
    capital_payment,
    capital_request,
    withholding_producer,
)
from cadrumo.adapters.persistence.profile.tests.test_ledger_payment_withholding import _payroll_payment, _request
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.invoice_retencion import (
    InvoiceWithholdingEvidenceRequest,
    build_invoice_withholding_capture,
)
from cadrumo.application.aggregation.ledger_payment_withholding import (
    LedgerPaymentWithholdingEvidenceError,
    build_ledger_payment_withholding_capture,
)
from cadrumo.application.aggregation.retenciones import RetencionObservation
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    LARGE_COMPANY_FACTS,
    PUBLIC_ADMINISTRATION_FACTS,
    REDEME_FACTS,
    published_filer_cadence,
    quarterly_filer_cadence,
)
from cadrumo.application.aggregation.withholding_filing_cadence import WithholdingFilingCadenceError
from cadrumo.application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from cadrumo.core.aggregation import RetencionClave, RetencionScheme
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from cadrumo.domain.invoices.models import Invoice, InvoiceLine
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.user_profile.values import UserProfileFact

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_MONTHS = "01|02|03|04|05|06|07|08|09|10|11|12"
_MONTHLY_111_FILERS = pytest.mark.parametrize(
    "facts",
    [LARGE_COMPANY_FACTS, PUBLIC_ADMINISTRATION_FACTS],
    ids=["large-company", "public-administration"],
)


def _stored(objects: SecureObjectRepository, modelo: str, quarter: str) -> tuple[RetencionObservation, ...]:
    return RetencionObservationRepositoryAdapter(objects=objects).load_observations(
        modelo, Period.from_year_and_code(2025, quarter)
    )


def _received_professional_invoice() -> Invoice:
    subtotal = Decimal("500.00")
    rate = iva_rate_percentage(IvaRate.from_registry("RATE_21"), date(2025, 1, 1))
    assert rate is not None
    line = InvoiceLine(
        description="Synthetic professional service",
        quantity=Decimal("1"),
        unit_price=subtotal,
        subtotal=subtotal,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=subtotal * rate,
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": "MONTHLY-PRO-001",
            "issued_at": date(2025, 3, 31),
            "counterparty_name": "Synthetic Recipient SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": subtotal,
            "iva_total": line.iva_amount,
            "grand_total": subtotal + line.iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory("domestic_general"),
            "retention_rate": Decimal("0.19"),
            "retention_amount": Decimal("95.00"),
        }
    )


def _professional_request(invoice: Invoice) -> InvoiceWithholdingEvidenceRequest:
    paid_on = date(2025, 4, 2)
    return InvoiceWithholdingEvidenceRequest(
        invoice_id=invoice.invoice_id,
        income_kind=WithholdingIncomeKind.PROFESSIONAL,
        scheme=RetencionScheme("actividades_profesionales"),
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        payment_event_id="professional-payment-2025-04",
        payment_occurred_on=paid_on,
        allocation_id="professional-allocation-2025-04",
        allocated_base=Decimal("500.00"),
        allocated_withholding=Decimal("95.00"),
        allocated_settlement=Decimal("500.00"),
        idempotency_key="professional-capture-2025-04",
        modelo_190_detail=WithholdingObservation(
            source_id=invoice.invoice_id,
            perceptor_tax_id=invoice.counterparty_tax_id or "",
            perceptor_legal_name=invoice.counterparty_name,
            transaction_date=paid_on,
            clave=RetencionClave.from_registry("G"),
            percibido_dinerario=Decimal("500.00"),
            retencion_practicada=Decimal("95.00"),
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
            base_retenciones=Decimal("500.00"),
            porcentaje_retencion=Decimal("19"),
        ),
    )


def _assert_quarter_refused(error: WithholdingFilingCadenceError, *, modelo: str, quarter: str, scheduled: str) -> None:
    assert error.refusal_code == "withholding_quarterly_window_not_scheduled"
    assert error.context == {
        "modelo": modelo,
        "filing_year": "2025",
        "period": quarter,
        "scheduled_periods": scheduled,
        "monthly_windows_supported": False,
    }
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.action is None


@_MONTHLY_111_FILERS
def test_invoice_capture_refuses_a_monthly_111_filer_and_writes_nothing(
    tmp_path: Path, facts: tuple[UserProfileFact, ...]
) -> None:
    invoice = _received_professional_invoice()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        with pytest.raises(WithholdingFilingCadenceError) as raised:
            build_invoice_withholding_capture(
                invoice,
                catalogue_revision_id="a" * 64,
                request=_professional_request(invoice),
                applicable_year=2025,
                cadence=published_filer_cadence(2025, facts=facts),
            )
        stored = _stored(profile.repository, "111", "2T")

    _assert_quarter_refused(raised.value, modelo="111", quarter="2T", scheduled=_MONTHS)
    assert stored == ()


@_MONTHLY_111_FILERS
def test_ledger_payroll_capture_refuses_a_monthly_111_filer_and_writes_nothing(
    tmp_path: Path, facts: tuple[UserProfileFact, ...]
) -> None:
    transaction = _payroll_payment()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        with pytest.raises(WithholdingFilingCadenceError) as raised:
            build_ledger_payment_withholding_capture(
                transaction,
                catalogue_revision_id="a" * 64,
                request=_request(transaction),
                applicable_year=2025,
                cadence=published_filer_cadence(2025, facts=facts),
            )
        stored = _stored(profile.repository, "111", "2T")

    _assert_quarter_refused(raised.value, modelo="111", quarter="2T", scheduled=_MONTHS)
    assert stored == ()


def test_ledger_capital_capture_refuses_a_large_company_that_no_123_schedule_covers(tmp_path: Path) -> None:
    transaction = capital_payment()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        with pytest.raises(WithholdingFilingCadenceError) as raised:
            build_ledger_payment_withholding_capture(
                transaction,
                catalogue_revision_id="a" * 64,
                request=capital_request(transaction),
                applicable_year=2025,
                cadence=published_filer_cadence(2025, facts=LARGE_COMPANY_FACTS),
            )
        stored = _stored(profile.repository, "123", "2T")

    _assert_quarter_refused(raised.value, modelo="123", quarter="2T", scheduled="")
    assert stored == ()


@pytest.mark.parametrize(
    ("modelo", "facts", "scheduled"),
    [
        ("111", LARGE_COMPANY_FACTS, _MONTHS),
        ("111", PUBLIC_ADMINISTRATION_FACTS, _MONTHS),
        ("123", LARGE_COMPANY_FACTS, ""),
    ],
    ids=["111-large-company", "111-public-administration", "123-large-company"],
)
def test_the_producer_refuses_a_command_built_for_another_cadence_and_writes_nothing(
    tmp_path: Path,
    modelo: str,
    facts: tuple[UserProfileFact, ...],
    scheduled: str,
) -> None:
    """The producer is the only mutation path, so it re-checks the schedule it is given."""
    if modelo == "111":
        transaction = _payroll_payment()
        request = _request(transaction)
    else:
        transaction = capital_payment()
        request = capital_request(transaction)
    capture = build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="a" * 64,
        request=request,
        applicable_year=2025,
        cadence=quarterly_filer_cadence(2025),
    )
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        with pytest.raises(WithholdingFilingCadenceError) as raised:
            withholding_producer(profile.repository).capture(
                capture.command,
                cadence=published_filer_cadence(2025, facts=facts),
            )
        stored = _stored(profile.repository, modelo, "2T")
        annual = PercepcionObservationRepositoryAdapter(objects=profile.repository).load_annual_source_observations(
            "111", 2025
        )

    _assert_quarter_refused(raised.value, modelo=modelo, quarter="2T", scheduled=scheduled)
    assert stored == ()
    assert annual == ()


def test_a_redeme_filer_still_captures_quarterly_as_the_calendar_shows(tmp_path: Path) -> None:
    """REDEME changes IVA cadence only; the withholding schedules keep this filer quarterly."""
    transaction = _payroll_payment()
    cadence = published_filer_cadence(2025, facts=REDEME_FACTS)
    capture = build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="a" * 64,
        request=_request(transaction),
        applicable_year=2025,
        cadence=cadence,
    )
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        result = withholding_producer(profile.repository).capture(capture.command, cadence=cadence)
        stored = _stored(profile.repository, "111", "2T")

    assert result is not None
    assert result.scope.period == Period.from_year_and_code(2025, "2T")
    assert len(stored) == 1


def test_a_cadence_for_another_year_is_refused_before_any_command() -> None:
    transaction = _payroll_payment()
    with pytest.raises(LedgerPaymentWithholdingEvidenceError) as raised:
        build_ledger_payment_withholding_capture(
            transaction,
            catalogue_revision_id="a" * 64,
            request=_request(transaction),
            applicable_year=2025,
            cadence=quarterly_filer_cadence(2024),
        )

    assert raised.value.refusal_code == "filer_cadence_year_mismatch"
