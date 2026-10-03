"""Movable-capital withholding reaches the Modelo 123 window through the aggregate CLI.

The coupon's paying transaction is seeded through the canonical transaction
repository and captured only by invoking
``aeat app modelo aggregate --ledger-payment-withholding``. Capture stores the
evidence; it does not make Modelo 123 calculable, because no official rule
defines its "Número de rentas" count, so ``aeat app modelo work calculate``
must still refuse the period with its typed reason.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from cadrumo.application.modelo.aggregate_contracts import MODELO_AGGREGATE_OPERATION_DEFINITION_ID
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.application.user_profile.tests.profile_values import complete_profile_facts

from ....adapters.persistence.profile.tests.ledger_capital_support import (
    CAPITAL_EXIGIBLE_ON,
    CAPITAL_GROSS,
    CAPITAL_HOLDER_NIF,
    CAPITAL_IRPF,
    CAPITAL_YEAR,
    capital_payment,
    capital_request,
)
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ....application.aggregation.retenciones import RetencionObservation
from ....application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ...adapter_composition import build_retencion_observation_ports
from .native_api_cli_support import NativeApiCliSession, native_api_cli_session
from .test_runtime_invoice_add import password_profile_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

# The coupon became exigible on 30 June of its year, so it belongs to the second quarter
# even though the bank paid it on 2 July.
_Q2 = "2T"

_CAPITAL_PROFILE_FACTS = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="identity.name", value="Test"),
    UserProfileFact(path="identity.surnames", value="Payer"),
    UserProfileFact(path="activities.description", value="capital income payer activity"),
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
    """Grant aggregate access with all-period transaction catalogue lookup."""
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


def _capital_profile_preparer(authority_operation: PinnedAuthorityOperation) -> Callable[[UUID, Path], Transaction]:
    """Complete the enrolled profile and seed its canonical coupon payment."""

    def prepare(profile_id: UUID, root: Path) -> Transaction:
        facts = complete_profile_facts(authority_operation.profile_schema(), _CAPITAL_PROFILE_FACTS)
        populated = upsert_test_profile_facts(profile_id, facts, root=root)
        with bound_test_profile_record(profile_id, root=root) as repository:
            ready = repository.complete_setup(
                profile_id,
                expected_revision=populated.record_revision,
                expected_content_digest=populated.content_digest,
            )
        assert ready.setup_state is ProfileSetupState.COMPLETE
        transaction = capital_payment()
        TransactionCatalogueRepository(bucket_id=str(profile_id)).save(
            TransactionCatalogue.from_transactions([transaction])
        )
        return transaction

    return prepare


def _aggregate(
    session: NativeApiCliSession[Transaction], modelo: str, period: str, *capture_options: str
) -> tuple[int, str]:
    result = session.invoke_password(
        "app",
        "modelo",
        "aggregate",
        "--modelo",
        modelo,
        "--year",
        f"{CAPITAL_YEAR}",
        "--period",
        period,
        *capture_options,
    )
    return result.exit_code, result.output


def _stored(profile_id: UUID, modelo: str, period: str) -> tuple[RetencionObservation, ...]:
    return build_retencion_observation_ports(bucket_id=str(profile_id)).repository.load_observations(
        modelo, Period.from_year_and_code(CAPITAL_YEAR, period)
    )


def _work(session: NativeApiCliSession[Transaction], verb: str, *extra: str) -> tuple[int, str]:
    result = session.invoke_password(
        "app",
        "modelo",
        "work",
        verb,
        "--modelo",
        "123",
        "--year",
        f"{CAPITAL_YEAR}",
        "--period",
        _Q2,
        *extra,
    )
    return result.exit_code, result.output


def test_ledger_capital_payment_is_stored_in_m123_and_calculation_stays_refused(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """A captured coupon lands in the 123 second quarter; calculating that period still refuses."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_capture_scope,
        prepare_profile=_capital_profile_preparer(authority_operation),
    ) as session:
        transaction = session.prepared
        payload = capital_request(transaction).model_dump_json()

        exit_code, output = _aggregate(session, "123", _Q2, "--ledger-payment-withholding", payload)
        assert exit_code == 0, f"{output}\n{session.runtime_failure_observations!r}"
        captured_window = json.loads(output)["result"]["withholding_window"]
        read_code, read_output = _aggregate(session, "123", _Q2)
        assert read_code == 0, read_output
        assert json.loads(read_output)["result"]["withholding_window"] == captured_window
        with password_profile_session(session.profile_id, authority_operation):
            stored = _stored(session.profile_id, "123", _Q2)
            assert len(stored) == 1
            observation = stored[0]
            assert observation.source_kind is BindingSourceKind.LEDGER_TRANSACTION
            assert observation.source_object_id == transaction.transaction_id
            assert observation.perceptor_nif == CAPITAL_HOLDER_NIF
            assert (observation.taxable_base, observation.retencion_amount) == (CAPITAL_GROSS, CAPITAL_IRPF)
            assert observation.accrued_on == CAPITAL_EXIGIBLE_ON.isoformat()
            assert _stored(session.profile_id, "111", _Q2) == ()
        created_code, created_output = _work(session, "create")
        assert created_code == 0, created_output
        calculated_code, calculated_output = _work(session, "calculate", "--by", "Payer")

    assert calculated_code != 0, calculated_output
    error = json.loads(calculated_output)["error"]
    assert error["code"] == "REFUSED_MODELO_123_COUNT_AUTHORITY_UNRESOLVED", calculated_output
    context = error["context"]
    assert context["reason"] == "REFUSED_MODELO_123_COUNT_AUTHORITY_UNRESOLVED", calculated_output
    assert context["terminal_condition"] == "refused", calculated_output
    assert isinstance(context["operation_id"], str) and context["operation_id"], calculated_output
    assert "casilla_values" not in calculated_output


def test_ledger_capital_capture_refuses_the_wrong_modelo_and_other_123_transports(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """A coupon cannot settle through Modelo 111, and 123 takes no invoice evidence, alone or beside the payment."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_capture_scope,
        prepare_profile=_capital_profile_preparer(authority_operation),
    ) as session:
        transaction = session.prepared
        payload = capital_request(transaction).model_dump_json()
        invoice_payload = InvoiceWithholdingEvidenceRequest(
            invoice_id="a" * 64,
            income_kind=WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL,
            scheme="intereses",
            recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
            recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
            exigibility_event_id="coupon-exigible",
            exigibility_occurred_on=CAPITAL_EXIGIBLE_ON,
            allocation_id="invoice-allocation",
            allocated_base=CAPITAL_GROSS,
            allocated_withholding=CAPITAL_IRPF,
            allocated_settlement=CAPITAL_GROSS - CAPITAL_IRPF,
            idempotency_key="invoice-capture",
        ).model_dump_json()

        refusals = (
            _aggregate(session, "111", _Q2, "--ledger-payment-withholding", payload),
            _aggregate(session, "123", _Q2, "--received-invoice-retencion", invoice_payload),
            _aggregate(
                session,
                "123",
                _Q2,
                "--ledger-payment-withholding",
                payload,
                "--received-invoice-retencion",
                invoice_payload,
            ),
        )

        assert [code for code, _output in refusals] == [2, 2, 2], refusals
        assert {json.loads(output)["error"]["code"] for _code, output in refusals} == {"REFUSED_CLI_BOUNDARY"}
        invoice_only_message = json.loads(refusals[1][1])["error"]["message"]
        assert "--ledger-payment-withholding" in invoice_only_message, invoice_only_message
        exclusive_message = json.loads(refusals[2][1])["error"]["message"]
        assert "--received-invoice-retencion" in exclusive_message, exclusive_message
        with password_profile_session(session.profile_id, authority_operation):
            assert _stored(session.profile_id, "111", _Q2) == ()
            assert _stored(session.profile_id, "123", _Q2) == ()
