"""M100 negative general-base carry resolves on the live calculate path.

A prior finding described a manual transcription into casilla 0501.
The registry's actual carry vehicle is the Anexo C negative general-base stock:
prior M100 casilla 1391 is copied by a ``previous_filing`` binding into the
next year's opening pending casilla 1388. Casilla 0501 remains the separate
Art. 50 compensation line and must not be used as a manual carry ingress.

These tests prove the live bucket-aggregation calculate path resolves the
existing previous-filing binding from real stored observations, with no caller
``--binding`` for the carry and no ``--casilla 0501`` input.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    BindingId,
    CasillaId,
    RegistryModeloObservation,
    validated_casilla_id,
)
from ....domain.user_profile import (
    UserProfileFact,
    UserProfileRecord,
)
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository
from ...user_profile import UserProfileLifecycleRepository
from .._calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND
from .._work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "cd7a6304-1000-4100-8100-000000000365"
_PERIOD = "0A"
_CLOCK = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
_QUARTERS = ("1T", "2T", "3T", "4T")

_OPENING_PENDING: CasillaId = validated_casilla_id("1388", surface="_OPENING_PENDING")
_GENERATED_PENDING: CasillaId = validated_casilla_id("1391", surface="_GENERATED_PENDING")
_CASILLA_0501: CasillaId = validated_casilla_id("0501", surface="_CASILLA_0501")
_M130_PAGOS_OUTPUT: CasillaId = validated_casilla_id("19", surface="_M130_PAGOS_OUTPUT")
_M131_PAGOS_OUTPUT: CasillaId = validated_casilla_id("15", surface="_M131_PAGOS_OUTPUT")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield the active profile's real encrypted-SQLite object repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _seed_taxpayer_unit_profile(secure_objects: SecureObjectRepository) -> None:
    record = UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Test runtime profile",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="identity.name", value="Test"),
            UserProfileFact(path="identity.surnames", value="Operator"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
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
            UserProfileFact(path="filing_export.declaration_type", value="1"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendientes_count", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendientes_minimos_aggregate_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.gastos_guarderia_reales_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.cotizaciones_ss_madre_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendientes_menores_3_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=Decimal("0")),
            UserProfileFact(path="renta_family.unidad_familiar_otros_miembros_base", value=Decimal("0")),
            UserProfileFact(path="renta_family.madrid_nacimiento_adopcion_eligible_count", value=Decimal("0")),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(record)


def _save_observation(
    obs_repo: CalculationObservationRepository,
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: dict[CasillaId, Decimal],
) -> None:
    obs_repo.save_observation(
        RegistryModeloObservation(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observations=registry_grounded_observations(
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                casilla_values=casilla_values,
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_CLOCK,
    )


def _seed_prior_m100_generated_pending(
    obs_repo: CalculationObservationRepository,
    *,
    source_year: int,
    value: Decimal,
) -> None:
    _save_observation(
        obs_repo,
        modelo="100",
        filing_year=source_year,
        period=_PERIOD,
        casilla_values={_GENERATED_PENDING: value},
    )


def _seed_zero_pagos_quarters(obs_repo: CalculationObservationRepository, *, filing_year: int) -> None:
    """Seed zero M130/M131 pago-fraccionado legs so M100 direct pago relations resolve."""
    for period in _QUARTERS:
        _save_observation(
            obs_repo,
            modelo="130",
            filing_year=filing_year,
            period=period,
            casilla_values={_M130_PAGOS_OUTPUT: Decimal("0")},
        )
        _save_observation(
            obs_repo,
            modelo="131",
            filing_year=filing_year,
            period=period,
            casilla_values={_M131_PAGOS_OUTPUT: Decimal("0")},
        )


def _calculate_m100(secure_objects: SecureObjectRepository, *, filing_year: int) -> BucketAggregationCalculationResult:
    snapshot = resources().modelos.authority.snapshot("100", filing_year=filing_year, period=_PERIOD)
    work_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, _PERIOD),
        revision_id=snapshot.revision.id,
        repository=work_repo,
        clock=_CLOCK,
    )
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        binding_values={f"renta-{filing_year}-modelo-100-estimacion-directa-es-normal": Decimal("1")},
        work_unit_repository=work_repo,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        clock=_CLOCK,
    )


@pytest.mark.parametrize(
    ("filing_year", "source_year", "binding_id", "prior_pending"),
    (
        (2024, 2023, "renta-2024-base-liquidable-negativa-general-anterior", Decimal("3210.00")),
        (2025, 2024, "renta-2025-base-liquidable-negativa-general-anterior", Decimal("4321.00")),
    ),
)
def test_m100_prior_negative_general_base_carries_without_manual_0501_input(
    secure_objects: SecureObjectRepository,
    filing_year: int,
    source_year: int,
    binding_id: BindingId,
    prior_pending: Decimal,
) -> None:
    """Prior M100 1391 auto-fills current 1388 without transcribing casilla 0501."""
    obs_repo = CalculationObservationRepository(objects=secure_objects)
    _seed_taxpayer_unit_profile(secure_objects)
    _seed_prior_m100_generated_pending(obs_repo, source_year=source_year, value=prior_pending)
    _seed_zero_pagos_quarters(obs_repo, filing_year=filing_year)

    result = _calculate_m100(secure_objects, filing_year=filing_year)
    revision = result.revision

    assert Decimal(revision.binding_overrides[binding_id]) == prior_pending
    assert Decimal(revision.input_values_by_casilla_id[_OPENING_PENDING]) == prior_pending
    assert Decimal(revision.casilla_values[_OPENING_PENDING]) == prior_pending
    assert _CASILLA_0501 not in revision.input_values_by_casilla_id
    assert Decimal(revision.casilla_values[_CASILLA_0501]) == Decimal("0")
    assert not any(diagnostic.binding_id == binding_id for diagnostic in result.source_diagnostics)
