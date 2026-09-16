"""``aeat app modelo work create`` authenticates the profile once for its readiness gates.

The command runs the baseline gate and the full readiness gate itself, then the
work-unit writer runs both again for the same unchanged record. Each gate used to
decrypt the profile capsule on its own; the command now loads it once and hands
it down. The count is taken on the real encrypted repository behind the real CLI.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from ....application.modelo import profile_readiness_gate
from ....application.user_profile.profile_record_repository import ProfileRecordRepository
from ....domain.calculations.registry.tests.published_authority import leased_profile_create_context
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from .modelo_cli import create_modelo_work_unit_via_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_PROFILE_ID = "0ac1e000-0000-4000-8000-000000370001"
_LABEL = "Work create profile load count"


@pytest.fixture
def runtime_profile(tmp_path: Path, authority_operation: object) -> Iterator[TestRuntimeProfile]:
    del authority_operation  # the record is created under the leased generation
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID, label=_LABEL) as profile:
        record = create_user_profile_record(
            profile_id=_PROFILE_ID,
            setup_state=ProfileSetupState.COMPLETE,
            facts=(
                UserProfileFact(path="identity.name", value="Marta"),
                UserProfileFact(path="identity.surnames", value="Diaz Ortega"),
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="provenance.source", value="manual_cli"),
                UserProfileFact(path="renta_taxpayer.birth_date", value="1985-06-15"),
                UserProfileFact(path="renta_filing.declaration_type", value="1"),
            ),
            context=leased_profile_create_context(),
        )
        seed_test_profile_record(record, root=profile.storage_root, label=_LABEL)
        yield profile


@pytest.fixture
def gate_loads(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every profile decrypt the readiness-gate module performs, still performing it."""
    loads: list[str] = []
    real_load = ProfileRecordRepository.load

    def counting_load(self: ProfileRecordRepository, profile_id: str | UUID) -> UserProfileRecord:
        if sys._getframe(1).f_globals.get("__name__") == profile_readiness_gate.__name__:
            loads.append(str(profile_id))
        return real_load(self, profile_id)

    monkeypatch.setattr(ProfileRecordRepository, "load", counting_load)
    return loads


@pytest.mark.usefixtures("runtime_profile")
def test_work_create_authenticates_the_profile_once_for_all_its_gates(gate_loads: list[str]) -> None:
    create_modelo_work_unit_via_cli(modelo="100", filing_year=2024, period="0A", revision="2024")

    assert gate_loads == [_PROFILE_ID]
