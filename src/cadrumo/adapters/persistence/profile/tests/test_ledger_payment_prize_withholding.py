"""Prize withholding captured from the ledger payment that paid a contest prize, read by Modelo 111."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.withholding_observation_workflow import WithholdingObservationWorkflowAdapter
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.ledger_payment_withholding import (
    LedgerPaymentWithholdingEvidenceError,
    LedgerPaymentWithholdingEvidenceRequest,
    build_ledger_payment_withholding_capture,
)
from cadrumo.application.aggregation.modelo_bindings_retenciones import RetencionesAggregationSourceResolver
from cadrumo.application.aggregation.retencion_observations_repository import RetencionObservationPorts
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.aggregation.tests.ledger_transaction_support import ledger_raw_transaction
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    quarterly_filer_cadence,
    quarterly_filer_cadence_for,
)
from cadrumo.application.aggregation.withholding_observation_service import WithholdingObservationService
from cadrumo.application.aggregation.withholding_producer import WithholdingProducer
from cadrumo.application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
    WithholdingRecognitionRule,
)
from cadrumo.core.aggregation import RetencionClave, RetencionScheme
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.retenciones_bindings import RetencionesAggregationProvider
from cadrumo.domain.calculations.registry.tests.published_authority import published_supported_filing_years
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import Transaction
from cadrumo.tests.withholding_zero_blocks import zeroed_withholding_blocks

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    return support.years


# A synthetic contest prize of 1000.00 paid in May with the 19 per cent retención
# (190.00) held back, so the bank paid 810.00 to the winner.
_PRIZE = Decimal("1000.00")
_PRIZE_RETENCION = Decimal("190.00")
_PRIZE_CATEGORY = "premios"
_WINNER_NIF = "00002500G"
_WINNER_NAME = "Ganadora Sintetica"

# The work-income control: one payslip in the same quarter.
_GROSS = Decimal("2500.00")
_IRPF = Decimal("375.00")
_EMPLOYEE_NIF = "00001500M"


def _payment(
    provider_id: str,
    *,
    year: int,
    amount: Decimal,
    irpf_category: str | None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": ledger_raw_transaction(provider_id, booked_date=date(year, 5, 30), amount=amount),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "group_label": None,
            "irpf_category": irpf_category,
        }
    )


def _prize_payment(
    *, year: int, gross: Decimal = _PRIZE, retencion: Decimal = _PRIZE_RETENCION, category: str | None = None
) -> Transaction:
    return _payment(
        f"prize-{year}-05",
        year=year,
        amount=gross - retencion,
        irpf_category=_PRIZE_CATEGORY if category is None else category,
    )


def _annual_detail(
    transaction: Transaction,
    *,
    year: int,
    tax_id: str,
    name: str,
    clave: str,
    gross: Decimal,
    retencion: Decimal,
) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=transaction.transaction_id,
        perceptor_tax_id=tax_id,
        perceptor_legal_name=name,
        transaction_date=date(year, 5, 30),
        clave=RetencionClave.from_registry(clave),
        percibido_dinerario=gross,
        retencion_practicada=retencion,
        **zeroed_withholding_blocks(),
        base_retenciones=gross,
    )


def _prize_request(
    transaction: Transaction,
    *,
    year: int,
    gross: Decimal = _PRIZE,
    retencion: Decimal = _PRIZE_RETENCION,
) -> LedgerPaymentWithholdingEvidenceRequest:
    return LedgerPaymentWithholdingEvidenceRequest(
        transaction_id=transaction.transaction_id,
        income_kind=WithholdingIncomeKind.PRIZE,
        scheme=RetencionScheme("premios"),
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        payment_event_id=f"prize-payment-{year}-05",
        allocation_id=f"prize-allocation-{year}-05",
        gross_base=gross,
        withholding_amount=retencion,
        net_settlement=gross - retencion,
        idempotency_key=f"prize-capture-{year}-05",
        modelo_190_detail=_annual_detail(
            transaction,
            year=year,
            tax_id=_WINNER_NIF,
            name=_WINNER_NAME,
            clave="K",
            gross=gross,
            retencion=retencion,
        ),
    )


def _payroll_request(transaction: Transaction, *, year: int) -> LedgerPaymentWithholdingEvidenceRequest:
    return LedgerPaymentWithholdingEvidenceRequest(
        transaction_id=transaction.transaction_id,
        income_kind=WithholdingIncomeKind.WORK,
        scheme=RetencionScheme("rendimientos_trabajo"),
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        payment_event_id=f"payroll-payment-{year}-05",
        allocation_id=f"payroll-allocation-{year}-05",
        gross_base=_GROSS,
        withholding_amount=_IRPF,
        net_settlement=_GROSS - _IRPF,
        idempotency_key=f"payroll-capture-{year}-05",
        modelo_190_detail=_annual_detail(
            transaction,
            year=year,
            tax_id=_EMPLOYEE_NIF,
            name="Empleada Sintetica",
            clave="A",
            gross=_GROSS,
            retencion=_IRPF,
        ),
    )


def _producer(objects: SecureObjectRepository) -> WithholdingProducer:
    return WithholdingProducer(
        service=WithholdingObservationService(
            WithholdingObservationWorkflowAdapter(
                objects=objects,
                retenciones=RetencionObservationRepositoryAdapter(objects=objects),
                percepciones=PercepcionObservationRepositoryAdapter(objects=objects),
            )
        )
    )


def _capture(
    objects: SecureObjectRepository,
    transaction: Transaction,
    request: LedgerPaymentWithholdingEvidenceRequest,
    *,
    year: int,
) -> None:
    capture = build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="a" * 64,
        request=request,
        applicable_year=year,
        cadence=quarterly_filer_cadence(year),
    )
    result = _producer(objects).capture(capture.command, cadence=quarterly_filer_cadence_for(capture.command))
    assert result is not None
    assert result.recognition.rule is WithholdingRecognitionRule.PAID_OR_SATISFIED
    assert result.recognition.recognized_on == date(year, 5, 30)


def _m111_casillas(objects: SecureObjectRepository, *, year: int) -> dict[str, Decimal]:
    """Resolve the quarter's Modelo 111 retenciones bindings and key them by their target casilla."""
    period = Period.from_year_and_code(year, "2T")
    with bundled_indexed_authority().operation() as operation:
        revision = operation.snapshot("111", filing_year=year, period="2T").revision
        resolution = RetencionesAggregationSourceResolver(
            ports=RetencionObservationPorts(repository=RetencionObservationRepositoryAdapter(objects=objects))
        ).resolve(
            CalculationSourceContext(
                bucket_id="synthetic-prize-payer",
                modelo="111",
                filing_year=year,
                period=period,
                revision=revision,
            )
        )
    targets = {
        str(binding.id): str(binding.provider.target_casilla_id)
        for binding in revision.bindings
        if isinstance(binding.provider, RetencionesAggregationProvider)
    }
    return {targets[str(binding_id)]: value for binding_id, value in resolution.binding_values.items()}


def _refusal(transaction: Transaction, request: LedgerPaymentWithholdingEvidenceRequest, *, year: int) -> str:
    with pytest.raises(LedgerPaymentWithholdingEvidenceError) as exc_info:
        build_ledger_payment_withholding_capture(
            transaction,
            catalogue_revision_id="a" * 64,
            request=request,
            applicable_year=year,
            cadence=quarterly_filer_cadence(year),
        )
    return exc_info.value.refusal_code


@pytest.mark.parametrize("year", _supported_years())
def test_a_paid_prize_reaches_modelo_111_casillas_13_to_15_beside_unchanged_work_income(
    tmp_path: Path, year: int
) -> None:
    """The prize fills the premios block, the payslip keeps the work block, and neither leaks into the other."""
    prize = _prize_payment(year=year)
    payroll = _payment(f"payroll-{year}-05", year=year, amount=_GROSS - _IRPF, irpf_category=None)

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        _capture(profile.repository, payroll, _payroll_request(payroll, year=year), year=year)
        work_only = _m111_casillas(profile.repository, year=year)
        _capture(profile.repository, prize, _prize_request(prize, year=year), year=year)
        casillas = _m111_casillas(profile.repository, year=year)
        annual = PercepcionObservationRepositoryAdapter(objects=profile.repository).load_annual_source_observations(
            "111", year
        )

    assert (casillas["13"], casillas["14"], casillas["15"]) == (Decimal("1"), _PRIZE, _PRIZE_RETENCION)
    assert (casillas["01"], casillas["02"], casillas["03"]) == (Decimal("1"), _GROSS, _IRPF)
    assert {key: work_only[key] for key in ("01", "02", "03")} == {key: casillas[key] for key in ("01", "02", "03")}
    assert (work_only["13"], work_only["14"], work_only["15"]) == (Decimal("0"), Decimal("0"), Decimal("0"))
    prize_rows = [row for row in annual if row.clave == RetencionClave.from_registry("K")]
    assert [(row.perceptor_tax_id, row.percibido_dinerario, row.retencion_practicada) for row in prize_rows] == [
        (_WINNER_NIF, _PRIZE, _PRIZE_RETENCION)
    ]


@pytest.mark.parametrize("year", _supported_years())
def test_a_prize_retencion_off_the_registry_rate_is_held_and_nothing_is_stored(tmp_path: Path, year: int) -> None:
    """A retención that is not 19 per cent of the prize is refused rather than declared."""
    wrong = Decimal("150.00")
    prize = _prize_payment(year=year, retencion=wrong)

    assert _refusal(prize, _prize_request(prize, year=year, retencion=wrong), year=year) == (
        "prize_retencion_rate_nonconforming"
    )
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        stored = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
            "111", Period.from_year_and_code(year, "2T")
        )
    assert stored == ()


@pytest.mark.parametrize("year", _supported_years())
def test_a_prize_whose_base_does_not_exceed_the_exclusion_threshold_is_refused(year: int) -> None:
    """RIRPF art. 75.3.f) excludes a prize of 300 euros or less from retención, so none is declared."""
    gross = Decimal("300.00")
    retencion = Decimal("57.00")
    prize = _prize_payment(year=year, gross=gross, retencion=retencion)

    assert _refusal(prize, _prize_request(prize, year=year, gross=gross, retencion=retencion), year=year) == (
        "prize_base_within_withholding_exclusion"
    )


def test_a_payment_not_classified_as_a_prize_is_refused() -> None:
    """The prize terms attach only to a movement the ledger classifies as a paid prize."""
    year = _supported_years()[-1]
    unclassified = _payment(f"prize-{year}-05", year=year, amount=_PRIZE - _PRIZE_RETENCION, irpf_category=None)

    assert _refusal(unclassified, _prize_request(unclassified, year=year), year=year) == (
        "transaction_not_classified_as_prize"
    )


def test_a_prize_request_requires_its_modelo_190_clave_detail() -> None:
    """Modelo 190 restates every prize perceptor, so the annual detail is required, not optional."""
    year = _supported_years()[-1]
    prize = _prize_payment(year=year)

    payload = _prize_request(prize, year=year).model_dump(mode="json") | {"modelo_190_detail": None}

    with pytest.raises(ValidationError, match="prize income requires Modelo 190 annual detail"):
        LedgerPaymentWithholdingEvidenceRequest.model_validate_json(json.dumps(payload))
