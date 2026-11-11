"""Shared setup for the split test modules."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.work_addressing import ModeloVisibleFilingTarget
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.modelo.workspace import (
    capture_modelo_workspace_locale_summary,
    capture_modelo_workspace_target_captures,
)
from cadrumo.application.modelo.workspace_models import (
    ModeloWorkspaceVisibleFilingTargetV1,
)
from cadrumo.application.modelo.workspace_schema import (
    resolve_static_inspection_schema_identity,
    static_inspection_contributors,
)
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import revision_covering
from cadrumo.domain.calculations.registry.tests.published_authority import (
    published_supported_filing_years,
)
from cadrumo.domain.modelos.tests.work_unit_catalogue_support import build_work_unit_catalogue
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue

from .....application.modelo.workspace_baseline import resolve_workspace_baseline
from .published_authority_support import published_authority_operation
from .ready_profile_support import seed_ready_profile

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection


def supported_filing_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no supported filing years"
    assert support.years, "the published support envelope admits no filing year"
    return tuple(support.years)


FILING_YEAR = max(supported_filing_years())


_WORKSPACE_PROFILE_ID = "13000000-0000-4000-8000-000000000231"


T0 = datetime(FILING_YEAR, 6, 5, 9, 0, 0, tzinfo=UTC)


LAW_SELECTED_REVISION_ID = revision_covering("130", FILING_YEAR).id


def _seed_ready_profile(objects: SecureObjectRepository, *, bucket_id: str) -> None:
    seed_ready_profile(bucket_id=bucket_id, at=T0)


@pytest.fixture
def workspace_repos(tmp_path: Path) -> Iterator[tuple[str, WorkUnitCatalogueRepository]]:
    """Yield one real bucket-scoped work-unit repository over an isolated profile."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_WORKSPACE_PROFILE_ID) as profile:
        _seed_ready_profile(profile.repository, bucket_id=profile.bucket_id)
        yield profile.bucket_id, WorkUnitCatalogueRepository(objects=profile.repository)


def counted_catalogue_reads(monkeypatch: pytest.MonkeyPatch) -> list[WorkUnitCatalogueRepository]:
    """Record each encrypted-SQL catalogue read, which still runs, by any repository from here on."""
    reads: list[WorkUnitCatalogueRepository] = []
    read = WorkUnitCatalogueRepository.load_revisioned

    def recorded(repository: WorkUnitCatalogueRepository) -> tuple[WorkUnitCatalogue, str]:
        reads.append(repository)
        return read(repository)

    monkeypatch.setattr(WorkUnitCatalogueRepository, "load_revisioned", recorded)
    return reads


def seed_work_unit(
    repository: WorkUnitCatalogueRepository,
    *,
    bucket_id: str,
    revision_id: str = LAW_SELECTED_REVISION_ID,
    operation: PinnedAuthorityOperation,
) -> WorkUnit:
    return create_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=FILING_YEAR,
        period=Period.from_year_and_code(FILING_YEAR, "1T"),
        revision_id=revision_id,
        ports=WorkLifecyclePorts(
            work_unit_repository=repository,
            bucket_event_repository=BucketEventHistoryRepository(),
        ),
        clock=T0,
        operation=operation,
    )


def visible_target(bucket_id: str, *, revision_id: str | None = None) -> ModeloWorkspaceVisibleFilingTargetV1:
    return ModeloWorkspaceVisibleFilingTargetV1(
        target=ModeloVisibleFilingTarget(
            modelo="130",
            filing_year=FILING_YEAR,
            period=Period.from_year_and_code(FILING_YEAR, "1T"),
            registry_revision_id=revision_id,
            bucket_id=bucket_id,
        ),
    )


def _visible_target_for(
    modelo: str,
    *,
    filing_year: int,
    period: str,
    bucket_id: str,
    revision_id: str | None = None,
) -> ModeloWorkspaceVisibleFilingTargetV1:
    return ModeloWorkspaceVisibleFilingTargetV1(
        target=ModeloVisibleFilingTarget(
            modelo=modelo,
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, period),
            registry_revision_id=revision_id,
            bucket_id=bucket_id,
        ),
    )


def _corrupt_stored_revision(
    repository: WorkUnitCatalogueRepository,
    work_unit: WorkUnit,
    *,
    corrupted_revision_id: str = "not-the-law-selected-revision",
) -> None:
    """Write a work unit whose stored revision has drifted from the law-selected one.

    ``create_work_unit`` itself re-confirms the law-selected pairing at write
    time, so a genuinely stale stored revision (the registry's law-selected
    pick moved on after the work unit was created under an earlier orden) is
    reproduced here the same way :mod:`test_work_addressing` reproduces a
    generation-superseding write: by constructing the catalogue directly,
    never by asking Workspace to accept a hand-picked mismatch.
    """
    from cadrumo.domain.modelos.work_unit import derive_work_unit_id

    payload = work_unit.model_dump()
    payload.update(
        work_unit_id=derive_work_unit_id(
            bucket_id=work_unit.bucket_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            revision_id=corrupted_revision_id,
        ),
        revision_id=corrupted_revision_id,
    )
    repository.save(build_work_unit_catalogue((WorkUnit(**payload),)))


def _exact_target(work_unit: WorkUnit):
    from cadrumo.application.modelo.work_addressing import ModeloExactWorkUnitTarget

    return ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=work_unit.bucket_id)


def assemble_static_inspection_pieces(bucket_id: str, repository: WorkUnitCatalogueRepository):
    """Build every piece needed for schema_facet tests, real captures throughout."""
    from cadrumo.application.modelo.workspace_producers import (
        ModeloWorkspaceFieldManifestPortV1,
        ModeloWorkspaceLocaleCataloguePortV1,
    )
    from cadrumo.core.external_constants import OutputLanguage
    from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

    authority = published_authority_operation()
    work_capture, registry_capture, _axes = capture_modelo_workspace_target_captures(
        visible_target(bucket_id),
        bucket_id=bucket_id,
        catalogue_repository=repository,
        authority=authority,
    )
    registry_projection = registry_capture.projection
    inspection = registry_projection.inspection
    assert isinstance(inspection, RegistryRevisionInspection)

    from cadrumo.application.modelo.workspace import resolve_modelo_workspace_revision_axes
    from cadrumo.application.modelo.workspace_models import ModeloWorkspaceResolvedTargetV1

    resolution = work_capture.projection
    axes = resolve_modelo_workspace_revision_axes(resolution, registry_projection=registry_projection)
    work_unit = resolution.work_unit
    assert resolution.filing_year is not None
    target = ModeloWorkspaceResolvedTargetV1(
        bucket_id=resolution.bucket_id,
        modelo=resolution.modelo,
        filing_year=resolution.filing_year,
        period=resolution.period,
        law_selected_revision_id=axes.law_selected_revision_id,
        review_status=registry_projection.review_status,
        requested_revision_assertion=axes.requested_revision_assertion,
        stored_revision_assertion=axes.stored_revision_assertion,
        work_unit_id=work_unit.work_unit_id if work_unit is not None else None,
        work_state=work_unit.state if work_unit is not None else None,
    )
    schema_identity = resolve_static_inspection_schema_identity(inspection)
    locale = capture_modelo_workspace_locale_summary(target, output_language=OutputLanguage.ES)
    locale_capture = ModeloWorkspaceLocaleCataloguePortV1(
        translation_key=f"modelo.schema.130.revision.{LAW_SELECTED_REVISION_ID}.field.label",
        locale=OutputLanguage.ES.value,
    ).capture_projection_with_epoch()
    field_manifest_capture = ModeloWorkspaceFieldManifestPortV1(authority=inspection).capture_projection_with_epoch()
    baseline = resolve_workspace_baseline(
        target,
        schema_identity=schema_identity,
        locale=locale,
        stamps=(work_capture.stamp, registry_capture.stamp, locale_capture.stamp, field_manifest_capture.stamp),
        epochs=(work_capture.epoch, registry_capture.epoch, locale_capture.epoch, field_manifest_capture.epoch),
    )
    contributors = static_inspection_contributors()
    return inspection, target, schema_identity, baseline, contributors


def real_303_inspection() -> RegistryRevisionInspection:
    return real_inspection("303", filing_year=FILING_YEAR, period="1T")


def real_inspection(modelo: str, *, filing_year: int, period: str) -> RegistryRevisionInspection:
    from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

    authority = published_authority_operation()
    capture = authority.capture_law_selected_projection(modelo, filing_year=filing_year, period=period)
    inspection = capture.projection
    assert isinstance(inspection, RegistryRevisionInspection)
    return inspection
