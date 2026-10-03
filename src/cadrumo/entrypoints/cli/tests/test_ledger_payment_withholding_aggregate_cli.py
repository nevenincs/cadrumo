"""Payroll withholding reaches Modelo 111 through the aggregate CLI from its ledger payment.

The per-perceptor store is populated only by invoking
``aeat app modelo aggregate --ledger-payment-withholding``; the paying
transaction is seeded through the canonical transaction repository, and the
casilla values are read from ``aeat app modelo work calculate``. Every expected
figure is derived below from the synthetic payslip, not from a prior run.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from cadrumo.application.modelo.aggregate_operation import MODELO_AGGREGATE_OPERATION_DEFINITION_ID
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.application.user_profile.tests.profile_values import complete_profile_facts

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
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
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.cli_envelope import unwrap_schema_envelope
from ...adapter_composition import build_retencion_observation_ports
from .native_api_cli_support import NativeApiCliSession, native_api_cli_session
from .test_runtime_invoice_add import password_profile_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

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


_M111_PROFILE_FACTS = (
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
)


def _capture_scope(client_id: UUID) -> AccessScope:
    return AccessScope(
        operations=frozenset({MODELO_AGGREGATE_OPERATION_DEFINITION_ID}),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.COMMIT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=f"{MODELO_AGGREGATE_OPERATION_DEFINITION_ID}.result",
                    category=DisclosureCategory.TAX_VALUES,
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _payroll_profile_preparer(
    authority_operation: PinnedAuthorityOperation,
    *,
    extra_facts: tuple[UserProfileFact, ...] = (),
) -> Callable[[UUID, Path], Transaction]:
    def prepare(profile_id: UUID, root: Path) -> Transaction:
        facts = complete_profile_facts(authority_operation.profile_schema(), (*_M111_PROFILE_FACTS, *extra_facts))
        populated = upsert_test_profile_facts(profile_id, facts, root=root)
        with bound_test_profile_record(profile_id, root=root) as repository:
            ready = repository.complete_setup(
                populated.profile_id,
                expected_revision=populated.record_revision,
                expected_content_digest=populated.content_digest,
            )
        assert ready.setup_state is ProfileSetupState.COMPLETE
        return _seed_payroll_payment(str(profile_id))

    return prepare


def _seed_payroll_payment(bucket_id: str) -> Transaction:
    """Store the bank payment of the net salary through the canonical repository."""
    transaction = Transaction.model_validate(
        {
            "raw": ledger_raw_transaction("payroll-2025-02", booked_date=_PAID_ON, amount=_NET),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "group_label": None,
        }
    )
    TransactionCatalogueRepository(bucket_id=bucket_id).save(TransactionCatalogue.from_transactions([transaction]))
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


def _aggregate(session: NativeApiCliSession[Transaction], modelo: str, *capture_options: str) -> tuple[int, str]:
    result = session.invoke_password(
        "--language",
        "en",
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
    )
    return result.exit_code, result.output


def _stored_q1_retenciones(
    session: NativeApiCliSession[Transaction], authority_operation: PinnedAuthorityOperation
) -> tuple[RetencionObservation, ...]:
    with password_profile_session(session.profile_id, authority_operation):
        return build_retencion_observation_ports(bucket_id=str(session.profile_id)).repository.load_observations(
            "111", Period.from_year_and_code(2025, "1T")
        )


def _calculate_m111_q1_via_cli(session: NativeApiCliSession[Transaction]) -> dict[str, str]:
    created = session.invoke_password(
        "app", "modelo", "work", "create", "--modelo", "111", "--year", "2025", "--period", "1T"
    )
    assert created.exit_code == 0, created.output
    calculated = session.invoke_password(
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
    )
    assert calculated.exit_code == 0, calculated.output
    casilla_values = unwrap_schema_envelope(calculated.output)["casilla_values"]
    assert isinstance(casilla_values, dict)
    return {str(key): str(value) for key, value in casilla_values.items()}


def test_ledger_payroll_payment_reaches_m111_work_casillas_and_replays_idempotently(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """A captured payslip moves casillas 01/02/03, and the identical replay changes nothing."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_capture_scope,
        prepare_profile=_payroll_profile_preparer(authority_operation),
    ) as session:
        transaction = session.prepared
        payload = _payroll_payload(transaction.transaction_id)

        exit_code, output = _aggregate(session, "111", "--ledger-payment-withholding", payload)
        assert exit_code == 0, output
        first_window = json.loads(output)["result"]["withholding_window"]
        assert first_window["generation"] == 1

        stored = _stored_q1_retenciones(session, authority_operation)
        assert len(stored) == 1
        observation = stored[0]
        assert observation.source_kind is BindingSourceKind.LEDGER_TRANSACTION
        assert observation.source_object_id == transaction.transaction_id
        assert observation.taxable_base == _GROSS
        assert observation.retencion_amount == _IRPF
        assert observation.accrued_on == _PAID_ON.isoformat()

        replay_code, replay_output = _aggregate(session, "111", "--ledger-payment-withholding", payload)
        assert replay_code == 0, replay_output
        assert json.loads(replay_output)["result"]["withholding_window"] == first_window
        assert len(_stored_q1_retenciones(session, authority_operation)) == 1

        casilla_values = _calculate_m111_q1_via_cli(session)

    # One employee; gross 2400.00; 15% IRPF on it is 360.00, the only retención in the quarter.
    assert Decimal(casilla_values["01"]) == Decimal("1")
    assert Decimal(casilla_values["02"]) == Decimal("2400.00")
    assert Decimal(casilla_values["03"]) == Decimal("360.00")
    assert Decimal(casilla_values["28"]) == Decimal("360.00")
    assert Decimal(casilla_values.get("08") or "0") == Decimal("0")


def test_ledger_payroll_capture_refuses_an_unknown_transaction(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """A transaction id the ledger does not hold writes nothing."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_capture_scope,
        prepare_profile=_payroll_profile_preparer(authority_operation),
    ) as session:
        exit_code, output = _aggregate(session, "111", "--ledger-payment-withholding", _payroll_payload("f" * 64))

        assert exit_code == 2, output
        assert "transaction_not_found" in output
        assert _stored_q1_retenciones(session, authority_operation) == ()


def test_ledger_payroll_capture_refuses_a_second_transport_and_other_modelos(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The payroll flag cannot share a command with invoice evidence or a second payment, nor leave Modelo 111."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_capture_scope,
        prepare_profile=_payroll_profile_preparer(authority_operation),
    ) as session:
        transaction = session.prepared
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

        refusals = (
            _aggregate(
                session, "111", "--ledger-payment-withholding", payload, "--received-invoice-retencion", invoice_payload
            ),
            _aggregate(
                session, "111", "--ledger-payment-withholding", payload, "--ledger-payment-withholding", payload
            ),
            _aggregate(session, "115", "--ledger-payment-withholding", payload),
        )

        assert [code for code, _output in refusals] == [2, 2, 2], refusals
        assert {json.loads(output)["error"]["code"] for _code, output in refusals} == {"REFUSED_CLI_BOUNDARY"}
        exclusive_message = json.loads(refusals[0][1])["error"]["message"]
        assert "--received-invoice-retencion" in exclusive_message, exclusive_message
        assert _stored_q1_retenciones(session, authority_operation) == ()


def test_ledger_payroll_capture_refuses_a_large_company_whose_modelo_111_is_monthly(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The stored profile makes Modelo 111 monthly, so the quarterly capture is refused and writes nothing."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_capture_scope,
        prepare_profile=_payroll_profile_preparer(
            authority_operation,
            extra_facts=(UserProfileFact(path="censo.large_company", value=True),),
        ),
    ) as session:
        transaction = session.prepared

        exit_code, output = _aggregate(
            session, "111", "--ledger-payment-withholding", _payroll_payload(transaction.transaction_id)
        )

        assert exit_code != 0, output
        error = json.loads(output)["error"]
        assert error["code"] == "REFUSED_CLI_BOUNDARY", output
        assert error["message"] == "Invalid value: withholding_quarterly_window_not_scheduled", output
        assert _stored_q1_retenciones(session, authority_operation) == ()
