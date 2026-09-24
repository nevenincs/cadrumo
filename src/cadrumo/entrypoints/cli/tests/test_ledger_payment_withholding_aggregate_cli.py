"""Payroll withholding reaches Modelo 111 through the aggregate CLI from its ledger payment.

The per-perceptor store is populated only by invoking
``aeat app modelo aggregate --ledger-payment-withholding``; the paying
transaction is seeded through the canonical transaction repository, and the
casilla values are read from ``aeat app modelo work calculate``. Every expected
figure is derived below from the synthetic payslip, not from a prior run.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from ....application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ....application.aggregation.ledger_payment_withholding import LedgerPaymentWithholdingEvidenceRequest
from ....application.aggregation.retenciones import RetencionObservation
from ....application.aggregation.tests.ledger_transaction_support import ledger_raw_transaction
from ....application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ....core.aggregation import BindingSourceKind, RetencionClave
from ....core.period import Period
from ....core.storage_taxonomy import StorageCategory
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.cli_envelope import unwrap_schema_envelope
from ....tests.storage_scope import storage_overrides
from ...adapter_composition import build_retencion_observation_ports
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_BUCKET_ID = "00000000-0000-4000-8000-000000000453"
_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
_PAID_ON = date(2025, 2, 28)
_EMPLOYEE_NIF = "11111111H"
_EMPLOYEE_NAME = "Empleada Sintetica"

# One February 2025 payslip: 2400.00 gross, 15% IRPF (360.00), and the
# employee's 6.35% Social Security share (152.40), which the payer also
# withholds, so the bank paid 2400.00 - 360.00 - 152.40 = 1887.60.
_GROSS = Decimal("2400.00")
_IRPF = Decimal("360.00")
_EMPLOYEE_SOCIAL_SECURITY = Decimal("152.40")
_NET = Decimal("1887.60")


def _prepare_cli_directories(tmp_path: Path) -> None:
    for directory in storage_overrides(
        tmp_path,
        StorageCategory.SECRETS,
        StorageCategory.TOKENS,
        StorageCategory.RUNS,
        StorageCategory.DRAFTS,
        StorageCategory.FINANCIAL_TRANSACTIONS,
        StorageCategory.INVOICES,
    ).values():
        directory.mkdir(parents=True, exist_ok=True)


def _seed_ready_profile(root: Path, *, extra_facts: tuple[UserProfileFact, ...] = ()) -> None:
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Employer"),
                UserProfileFact(path="activities.description", value="withholding employer activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                UserProfileFact(path="withholding.colegio_concertado", value=False),
                *extra_facts,
            ),
            created_at=_T0,
            updated_at=_T0,
            context=_profile_creation_context_for_test(),
        ),
        root=root,
        label="M111 ledger payroll withholding",
    )


def _seed_payroll_payment(profile: TestRuntimeProfile) -> Transaction:
    """Store the bank payment of the net salary through the canonical repository."""
    transaction = Transaction.model_validate(
        {
            "raw": ledger_raw_transaction("payroll-2025-02", booked_date=_PAID_ON, amount=_NET),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "group_label": None,
        }
    )
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository).save(
        TransactionCatalogue.from_transactions([transaction])
    )
    return transaction


def _payroll_payload(transaction_id: str, *, idempotency_key: str = "payroll-capture-2025-02") -> str:
    """Build the full public payload, including the mandatory Modelo 190 annual detail."""
    annual_detail = WithholdingObservation(
        source_id=transaction_id,
        perceptor_tax_id=_EMPLOYEE_NIF,
        perceptor_legal_name=_EMPLOYEE_NAME,
        transaction_date=_PAID_ON,
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
    return LedgerPaymentWithholdingEvidenceRequest(
        transaction_id=transaction_id,
        scheme="rendimientos_trabajo",
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        payment_event_id="payroll-payment-2025-02",
        allocation_id="payroll-allocation-2025-02",
        gross_base=_GROSS,
        withholding_amount=_IRPF,
        net_settlement=_NET,
        idempotency_key=idempotency_key,
        modelo_190_detail=annual_detail,
    ).model_dump_json()


def _aggregate(modelo: str, *capture_options: str) -> tuple[int, str]:
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "aggregate",
            "--modelo",
            modelo,
            "--year",
            "2025",
            "--period",
            "1T",
            *capture_options,
        ]
    )
    return result.exit_code, result.output


def _stored_q1_retenciones() -> tuple[RetencionObservation, ...]:
    return build_retencion_observation_ports(bucket_id=_BUCKET_ID).repository.load_observations(
        "111", Period.from_year_and_code(2025, "1T")
    )


def _calculate_m111_q1_via_cli() -> dict[str, str]:
    created = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "create", "--modelo", "111", "--year", "2025", "--period", "1T"]
    )
    assert created.exit_code == 0, created.output
    calculated = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            "--modelo",
            "111",
            "--year",
            "2025",
            "--period",
            "1T",
            "--by",
            "Employer",
        ]
    )
    assert calculated.exit_code == 0, calculated.output
    casilla_values = unwrap_schema_envelope(calculated.output)["casilla_values"]
    assert isinstance(casilla_values, dict)
    return {str(key): str(value) for key, value in casilla_values.items()}


def test_ledger_payroll_payment_reaches_m111_work_casillas_and_replays_idempotently(tmp_path: Path) -> None:
    """A captured payslip moves casillas 01/02/03, and the identical replay changes nothing."""
    _prepare_cli_directories(tmp_path)
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 ledger payroll") as profile:
        _seed_ready_profile(profile.storage_root)
        transaction = _seed_payroll_payment(profile)
        payload = _payroll_payload(transaction.transaction_id)

        exit_code, output = _aggregate("111", "--ledger-payment-withholding", payload)
        assert exit_code == 0, output
        first_window = json.loads(output)["result"]["withholding_window"]
        assert first_window["generation"] == 1

        stored = _stored_q1_retenciones()
        assert len(stored) == 1
        observation = stored[0]
        assert observation.source_kind is BindingSourceKind.LEDGER_TRANSACTION
        assert observation.source_object_id == transaction.transaction_id
        assert observation.taxable_base == _GROSS
        assert observation.retencion_amount == _IRPF
        assert observation.accrued_on == _PAID_ON.isoformat()

        replay_code, replay_output = _aggregate("111", "--ledger-payment-withholding", payload)
        assert replay_code == 0, replay_output
        assert json.loads(replay_output)["result"]["withholding_window"] == first_window
        assert len(_stored_q1_retenciones()) == 1

        casilla_values = _calculate_m111_q1_via_cli()

    # One employee; gross 2400.00; 15% IRPF on it is 360.00, the only retención in the quarter.
    assert Decimal(casilla_values["01"]) == Decimal("1")
    assert Decimal(casilla_values["02"]) == Decimal("2400.00")
    assert Decimal(casilla_values["03"]) == Decimal("360.00")
    assert Decimal(casilla_values["28"]) == Decimal("360.00")
    assert Decimal(casilla_values.get("08") or "0") == Decimal("0")


def test_ledger_payroll_capture_refuses_an_unknown_transaction(tmp_path: Path) -> None:
    """A transaction id the ledger does not hold writes nothing."""
    _prepare_cli_directories(tmp_path)
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 ledger payroll") as profile:
        _seed_ready_profile(profile.storage_root)
        _seed_payroll_payment(profile)

        exit_code, output = _aggregate("111", "--ledger-payment-withholding", _payroll_payload("f" * 64))

        assert exit_code == 2, output
        assert "transaction_not_found" in output
        assert _stored_q1_retenciones() == ()


def test_ledger_payroll_capture_refuses_a_second_transport_and_other_modelos(tmp_path: Path) -> None:
    """The payroll flag cannot share a command with invoice or hand-typed rows, nor leave Modelo 111."""
    _prepare_cli_directories(tmp_path)
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 ledger payroll") as profile:
        _seed_ready_profile(profile.storage_root)
        transaction = _seed_payroll_payment(profile)
        payload = _payroll_payload(transaction.transaction_id)
        invoice_payload = InvoiceWithholdingEvidenceRequest(
            invoice_id="a" * 64,
            income_kind=WithholdingIncomeKind.PROFESSIONAL,
            scheme="actividades_profesionales",
            recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
            recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
            payment_event_id="invoice-payment",
            payment_occurred_on=_PAID_ON,
            allocation_id="invoice-allocation",
            allocated_base=Decimal("100.00"),
            allocated_withholding=Decimal("15.00"),
            allocated_settlement=Decimal("106.00"),
            idempotency_key="invoice-capture",
        ).model_dump_json()
        manual_row = json.dumps(
            {
                "source_kind": "ledger_transaction",
                "source_object_id": transaction.transaction_id,
                "perceptor_nif": _EMPLOYEE_NIF,
                "scheme": "rendimientos_trabajo",
                "taxable_base": "2400.00",
                "retencion_amount": "360.00",
                "accrued_on": _PAID_ON.isoformat(),
            }
        )

        refusals = (
            _aggregate("111", "--ledger-payment-withholding", payload, "--received-invoice-retencion", invoice_payload),
            _aggregate("111", "--ledger-payment-withholding", payload, "--retencion-observation", manual_row),
            _aggregate("111", "--ledger-payment-withholding", payload, "--ledger-payment-withholding", payload),
            _aggregate("115", "--ledger-payment-withholding", payload),
        )

        assert [code for code, _output in refusals] == [2, 2, 2, 2], refusals
        assert {json.loads(output)["error"]["code"] for _code, output in refusals} == {"REFUSED_CLI_BOUNDARY"}
        assert _stored_q1_retenciones() == ()


def test_ledger_payroll_capture_refuses_a_large_company_whose_modelo_111_is_monthly(tmp_path: Path) -> None:
    """The stored profile makes Modelo 111 monthly, so the quarterly capture is refused and writes nothing."""
    _prepare_cli_directories(tmp_path)
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 ledger payroll") as profile:
        _seed_ready_profile(
            profile.storage_root,
            extra_facts=(UserProfileFact(path="censo.large_company", value=True),),
        )
        transaction = _seed_payroll_payment(profile)

        exit_code, output = _aggregate(
            "111", "--ledger-payment-withholding", _payroll_payload(transaction.transaction_id)
        )

        assert exit_code != 0, output
        error = json.loads(output)["error"]
        assert error["code"] == "REFUSED_WITHHOLDING_FILING_CADENCE", output
        assert _stored_q1_retenciones() == ()
