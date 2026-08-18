"""Real CLI proof for Modelo 303 simplified-regime scope resolution."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.calculations import IvaWalletDecisionRepository
from ....core import Period
from ....core.resources import resources
from ....domain.deadlines import M303RegimeComposition
from ....domain.iva_compensation import IvaCompensationReconciliationDecision
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.cli_envelope import unwrap_schema_envelope
from ....tests.cli_runner import invoke_cached_cli
from ....tests.modelo_cli import create_modelo_work_unit_via_cli
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "e3030000-0000-4000-8000-000000000060"
_DECIDED_AT = datetime(2026, 4, 1, tzinfo=UTC)


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


def _store_current_profile(
    runtime_profile: TestRuntimeProfile,
    *,
    composition: M303RegimeComposition,
) -> None:
    seed_test_profile_record(
        UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="M303"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value=composition.value),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            ),
        ),
        root=runtime_profile.storage_root,
        label="M303 CLI scope profile",
    )


def _m303_work_id() -> str:
    revision = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T").revision.id
    return create_modelo_work_unit_via_cli(
        modelo="303",
        filing_year=2026,
        period="1T",
        revision=revision,
    )


def _store_zero_prior_compensation(runtime_profile: TestRuntimeProfile) -> None:
    IvaWalletDecisionRepository(objects=runtime_profile.repository).save_decision(
        IvaCompensationReconciliationDecision(
            taxpayer_nif="12345678Z",
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "1T"),
            selected_authority="aeat_wallet",
            selected_amount=Decimal("0.00"),
            wallet_amount=Decimal("0.00"),
            local_recurrence_amount=Decimal("0.00"),
            override_amount=None,
            divergence="match",
            blocked=False,
            stale_wallet=False,
            reason_identity="aeat_wallet_validated",
            wallet_captured_at=_DECIDED_AT,
            decided_at=_DECIDED_AT,
        )
    )


def _calculate(work_unit_id: str):
    return invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            "--no-m303-joint-return-elected",
        ]
    )


def test_m303_general_scope_reaches_real_cli_calculation(runtime_profile: TestRuntimeProfile) -> None:
    _store_current_profile(runtime_profile, composition=M303RegimeComposition.GENERAL)
    _store_zero_prior_compensation(runtime_profile)

    result = _calculate(_m303_work_id())

    assert result.exit_code == 0, result.output
    payload = unwrap_schema_envelope(result.output)
    assert "iva.resultado" in payload["casilla_values"]


@pytest.mark.parametrize("composition", (M303RegimeComposition.SIMPLIFIED, M303RegimeComposition.MIXED))
def test_m303_simplified_and_mixed_scope_block_real_cli_before_formula(
    runtime_profile: TestRuntimeProfile,
    composition: M303RegimeComposition,
) -> None:
    _store_current_profile(runtime_profile, composition=composition)
    _store_zero_prior_compensation(runtime_profile)

    result = _calculate(_m303_work_id())

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert "S58 evidence projection" in error["message"]
