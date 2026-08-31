"""Shared real-projection fixtures for the C2 workspace view tests.

One isolated profile, one real work unit, and a real
``resolve_static_inspection_result`` -- so every test in this package reads
what the application layer actually produces rather than a constructed
stand-in that would agree with its author.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......application.modelo.work_addressing import ModeloVisibleFilingTarget
from ......application.modelo.work_lifecycle import create_work_unit
from ......application.modelo.workspace import resolve_static_inspection_result
from ......application.modelo.workspace_models import ModeloWorkspaceVisibleFilingTargetV1
from ......core.external_constants import OutputLanguage
from ......core.period import Period
from ......domain.calculations.registry.authority import bundled_authority
from ......domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ......tests.profile_capsule import seed_test_profile_record
from ......tests.secure_sql import isolated_runtime_profile

_PROFILE_ID = "13000000-0000-4000-8000-000000000231"
_REVISION = "2019-y-siguientes"
_T0 = datetime(2026, 6, 5, 9, 0, 0, tzinfo=UTC)
_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test Operator"),
    UserProfileFact(path="identity.surnames", value="Workspace"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="provenance.source", value="manual_cli"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


@pytest.fixture
def bucket_and_repository(tmp_path: Path) -> Iterator[tuple[str, WorkUnitCatalogueRepository]]:
    """Yield one real bucket-scoped work-unit repository over an isolated profile."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile:
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=_READY_PROFILE_FACTS,
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        repository = WorkUnitCatalogueRepository(objects=profile.repository)
        create_work_unit(
            bucket_id=profile.bucket_id,
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id=_REVISION,
            repository=repository,
            clock=_T0,
        )
        yield profile.bucket_id, repository


def resolve_real_result(bucket_id: str, repository: WorkUnitCatalogueRepository, language: OutputLanguage):
    """Resolve one real static-inspection result for the seeded target."""
    return resolve_static_inspection_result(
        ModeloWorkspaceVisibleFilingTargetV1(
            target=ModeloVisibleFilingTarget(
                modelo="130", filing_year=2026, period=Period.from_year_and_code(2026, "1T")
            )
        ),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=bundled_authority(),
        output_language=language,
    )
