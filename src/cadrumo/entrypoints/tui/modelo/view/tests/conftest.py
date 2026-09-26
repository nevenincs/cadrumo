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

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ......application.modelo.work_addressing import ModeloVisibleFilingTarget, law_selected_revision_for_work_target
from ......application.modelo.work_lifecycle import create_work_unit
from ......application.modelo.workspace import resolve_static_inspection_result
from ......application.modelo.workspace_models import ModeloWorkspaceVisibleFilingTargetV1
from ......core.external_constants import OutputLanguage
from ......core.period import Period
from ......domain.user_profile.values import ProfileSetupState, UserProfileFact

_PROFILE_ID = "13000000-0000-4000-8000-000000000231"
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
    yield from _seeded_bucket(tmp_path, modelo="130")


@pytest.fixture
def m303_bucket_and_repository(tmp_path: Path) -> Iterator[tuple[str, WorkUnitCatalogueRepository]]:
    """Yield the same isolated profile holding one Modelo 303 work unit instead."""
    yield from _seeded_bucket(tmp_path, modelo="303")


def _seeded_bucket(tmp_path: Path, *, modelo: str) -> Iterator[tuple[str, WorkUnitCatalogueRepository]]:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile,
        bundled_indexed_authority().operation() as operation,
    ):
        seed_test_profile_record(
            _create_profile_record_for_test(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=_READY_PROFILE_FACTS,
                created_at=_T0,
                updated_at=_T0,
                context=operation.profile_create_context(),
            ),
        )
        repository = WorkUnitCatalogueRepository(objects=profile.repository)
        period = Period.from_year_and_code(2026, "1T")
        create_work_unit(
            bucket_id=profile.bucket_id,
            modelo=modelo,
            filing_year=2026,
            period=period,
            revision_id=law_selected_revision_for_work_target(
                modelo=modelo, filing_year=2026, period=period, operation=operation
            ),
            ports=WorkLifecyclePorts(
                work_unit_repository=repository,
                bucket_event_repository=BucketEventHistoryRepository(),
            ),
            clock=_T0,
            operation=operation,
        )
        yield profile.bucket_id, repository


def resolve_real_result(
    bucket_id: str,
    repository: WorkUnitCatalogueRepository,
    language: OutputLanguage,
    *,
    modelo: str = "130",
):
    """Resolve one real static-inspection result for the seeded target."""
    with bundled_indexed_authority().operation() as operation:
        return resolve_static_inspection_result(
            ModeloWorkspaceVisibleFilingTargetV1(
                target=ModeloVisibleFilingTarget(
                    modelo=modelo, filing_year=2026, period=Period.from_year_and_code(2026, "1T")
                )
            ),
            bucket_id=bucket_id,
            catalogue_repository=repository,
            authority=operation,
            output_language=language,
        )
