"""CLI reproduction for M100/2025 work-retention binding equivalence."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.calculations import CalculationObservationRepository
from ....application.modelo import APP_FILING_SOURCE_KIND
from ....domain.calculations.registry import RegistryModeloObservation
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.modelo_cli import create_modelo_work_unit_via_cli
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "568d7ee0-33e4-4efb-8bae-5c4e97d9a1b7"
_CAPTURED_AT = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="M100 M190 retenciones CLI profile",
    ) as profile:
        yield profile


def _seed_m100_2025_profile(runtime_profile: TestRuntimeProfile) -> None:
    record = UserProfileRecord(
        schema_id="cadrumo.user_profile",
        # Sourced from the schema, never pinned: a literal goes stale the moment
        # the profile schema is revised, and the record then refuses to validate
        # against its own canonical version.
        schema_version=load_user_profile_schema().version,
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="identity.name", value="Ana"),
            UserProfileFact(path="identity.surnames", value="Retenciones"),
            UserProfileFact(path="activities.description", value="economic activity"),
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
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.sex", value="H"),
            UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
            UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
            UserProfileFact(path="provenance.source", value="manual_cli"),
        ),
    )
    seed_test_profile_record(record, root=runtime_profile.storage_root, label="M100 M190 retenciones CLI profile")


def _seed_prior_year_zero_carry(runtime_profile: TestRuntimeProfile) -> None:
    CalculationObservationRepository(objects=runtime_profile.repository).save(
        CalculationObservationRepository(objects=runtime_profile.repository).prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="100",
                filing_year=2024,
                period="0A",
                observations=registry_grounded_observations(
                    modelo="100",
                    filing_year=2024,
                    period="0A",
                    casilla_values={"1391": Decimal("0")},
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_CAPTURED_AT,
        )
    )


def test_m100_2025_cli_m190_annual_retenciones_populates_0596(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Real CLI reproduction: accepted M190 annual-retention binding affects 0596."""
    _seed_m100_2025_profile(runtime_profile)
    _seed_prior_year_zero_carry(runtime_profile)
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="100",
        filing_year=2025,
        period="0A",
        revision="2025",
    )

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            "--casilla",
            "0003=32000",
            "--casilla",
            "0102=9600",
            "--binding",
            "renta-2025-modelo-100-estimacion-directa-es-normal=1",
            "--binding",
            "renta-2025-modelo-184-atribucion-actividades-economicas=0",
            "--binding",
            "renta-2025-modelo-190-retenciones-anuales=4200",
            "--relation",
            "renta-2025-rel-130-pagos-fraccionados=0",
            "--relation",
            "renta-2025-rel-131-pagos-fraccionados=0",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert Decimal(payload["casilla_values"]["0596"]) == Decimal("4200")
    assert Decimal(payload["casilla_values"]["0609"]) == Decimal("4200")
