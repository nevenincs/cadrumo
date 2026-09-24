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
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....adapters.persistence.profile.tests.ledger_capital_support import (
    CAPITAL_EXIGIBLE_ON,
    CAPITAL_GROSS,
    CAPITAL_HOLDER_NIF,
    CAPITAL_IRPF,
    capital_payment,
    capital_request,
)
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from ....application.aggregation.retenciones import RetencionObservation
from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....core.storage_taxonomy import StorageCategory
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.storage_scope import storage_overrides
from ...adapter_composition import build_retencion_observation_ports
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_BUCKET_ID = "00000000-0000-4000-8000-000000000454"
_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
# The coupon became exigible on 30 June 2025, so it belongs to the second quarter
# even though the bank paid it on 2 July.
_Q2 = "2T"


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


def _seed_ready_profile(root: Path) -> None:
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
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
            ),
            created_at=_T0,
            updated_at=_T0,
            context=_profile_creation_context_for_test(),
        ),
        root=root,
        label="M123 ledger capital withholding",
    )


def _seed_coupon_payment(profile: TestRuntimeProfile) -> Transaction:
    transaction = capital_payment()
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository).save(
        TransactionCatalogue.from_transactions([transaction])
    )
    return transaction


def _aggregate(modelo: str, period: str, *capture_options: str) -> tuple[int, str]:
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
            period,
            *capture_options,
        ]
    )
    return result.exit_code, result.output


def _stored(modelo: str, period: str) -> tuple[RetencionObservation, ...]:
    return build_retencion_observation_ports(bucket_id=_BUCKET_ID).repository.load_observations(
        modelo, Period.from_year_and_code(2025, period)
    )


def _work(verb: str, *extra: str) -> tuple[int, str]:
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            verb,
            "--modelo",
            "123",
            "--year",
            "2025",
            "--period",
            _Q2,
            *extra,
        ]
    )
    return result.exit_code, result.output


def test_ledger_capital_payment_is_stored_in_m123_and_calculation_stays_refused(tmp_path: Path) -> None:
    """A captured coupon lands in the 123 second quarter; calculating that period still refuses."""
    _prepare_cli_directories(tmp_path)
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M123 ledger capital") as profile:
        _seed_ready_profile(profile.storage_root)
        transaction = _seed_coupon_payment(profile)
        payload = capital_request(transaction).model_dump_json()

        exit_code, output = _aggregate("123", _Q2, "--ledger-payment-withholding", payload)
        assert exit_code == 0, output
        stored = _stored("123", _Q2)
        assert len(stored) == 1
        observation = stored[0]
        assert observation.source_kind is BindingSourceKind.LEDGER_TRANSACTION
        assert observation.source_object_id == transaction.transaction_id
        assert observation.perceptor_nif == CAPITAL_HOLDER_NIF
        assert (observation.taxable_base, observation.retencion_amount) == (CAPITAL_GROSS, CAPITAL_IRPF)
        assert observation.accrued_on == CAPITAL_EXIGIBLE_ON.isoformat()
        assert _stored("111", _Q2) == ()

        created_code, created_output = _work("create")
        assert created_code == 0, created_output
        calculated_code, calculated_output = _work("calculate", "--by", "Payer")

    assert calculated_code != 0, calculated_output
    error = json.loads(calculated_output)["error"]
    assert error["code"] == "REFUSED_MODELO_123_COUNT_AUTHORITY_UNRESOLVED", calculated_output
    assert "casilla_values" not in calculated_output


def test_ledger_capital_capture_refuses_the_wrong_modelo_and_other_123_transports(tmp_path: Path) -> None:
    """A coupon cannot settle through Modelo 111, and 123 takes no invoice or hand-typed retención."""
    _prepare_cli_directories(tmp_path)
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M123 ledger capital") as profile:
        _seed_ready_profile(profile.storage_root)
        transaction = _seed_coupon_payment(profile)
        payload = capital_request(transaction).model_dump_json()
        manual_row = json.dumps(
            {
                "source_kind": "ledger_transaction",
                "source_object_id": transaction.transaction_id,
                "perceptor_nif": CAPITAL_HOLDER_NIF,
                "scheme": "intereses",
                "taxable_base": str(CAPITAL_GROSS),
                "retencion_amount": str(CAPITAL_IRPF),
                "accrued_on": CAPITAL_EXIGIBLE_ON.isoformat(),
            }
        )

        refusals = (
            _aggregate("111", _Q2, "--ledger-payment-withholding", payload),
            _aggregate("123", _Q2, "--retencion-observation", manual_row),
        )

        assert [code for code, _output in refusals] == [2, 2], refusals
        assert {json.loads(output)["error"]["code"] for _code, output in refusals} == {"REFUSED_CLI_BOUNDARY"}
        assert _stored("111", _Q2) == ()
        assert _stored("123", _Q2) == ()
