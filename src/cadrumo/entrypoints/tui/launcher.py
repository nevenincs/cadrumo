"""Concrete runtime composition for installed and diagnostic TUI sessions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import ExitStack, asynccontextmanager, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from ...domain.modelos.errors import ModeloError
from ...domain.modelos.work_unit import WorkUnitCatalogue

if TYPE_CHECKING:
    from ...application.search.installed_workbench import InstalledWorkbenchSearchSnapshotV1
    from .search import WorkbenchSearchDoorV1
    from textual.app import AutopilotCallbackType

    from ...application.modelo.work_review import ModeloWorkReview
    from ...application.modelo.workspace_models import ModeloWorkspaceStaticInspectionResultV1
    from ...application.operations.composition import OperationComposedServices
    from ...core.external_constants import OutputLanguage
    from ...domain.modelos.work_unit import WorkUnit


def load_modelo_work_unit_catalogue(bucket_id: str) -> WorkUnitCatalogue:
    """Load one profile's work-unit catalogue at the TUI composition boundary."""
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository

    return WorkUnitCatalogueRepository(bucket_id=bucket_id).load()


def _require_active_bucket_id(bucket_id: str | None) -> str:
    """Resolve the bucket a session reads, refusing a cold start outright.

    A session that reached a work destination without a profile has nothing to
    render, and the honest report is a refusal rather than an empty surface
    that looks like a profile holding no work.
    """
    from ...core.bucket_pointer import resolve_active_bucket_id

    resolved = bucket_id or resolve_active_bucket_id()
    if resolved is None:
        raise ModeloError("no active profile: a work destination needs one profile's bucket to read")
    return resolved


def resolve_modelo_work_unit(*, work_unit_id: str, bucket_id: str | None) -> WorkUnit:
    """Resolve one work unit by exact id at the TUI composition boundary.

    The identifier is all that crosses into this process, so the record it
    names is read here rather than received. That is what makes the surface a
    read of current persistence instead of a projection of whatever a sibling
    entrypoint held when it asked for the destination.
    """
    from ...application.modelo.work_addressing import resolve_modelo_work_unit_for_operator_target

    resolved_bucket_id = _require_active_bucket_id(bucket_id)
    return resolve_modelo_work_unit_for_operator_target(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        catalogue=load_modelo_work_unit_catalogue(resolved_bucket_id),
        resolved_bucket_id=resolved_bucket_id,
    )


def load_modelo_work_units(*, bucket_id: str | None, include_discarded: bool) -> tuple[WorkUnit, ...]:
    """Read the work units a picker offers at the TUI composition boundary."""
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ...application.modelo.work_lifecycle import list_work_units

    resolved_bucket_id = _require_active_bucket_id(bucket_id)
    return list_work_units(
        bucket_id=bucket_id,
        include_discarded=include_discarded,
        repository=WorkUnitCatalogueRepository(bucket_id=resolved_bucket_id),
    )


def build_modelo_work_review_for_unit(unit: WorkUnit) -> ModeloWorkReview:
    """Build the canonical review record for one resolved unit."""
    from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ...application.modelo.work_review import build_modelo_work_review

    return build_modelo_work_review(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        verification_repository=VerificationReportCatalogueRepository(),
    )


def resolve_modelo_workspace_static_inspection(
    unit: WorkUnit, *, output_language: OutputLanguage
) -> ModeloWorkspaceStaticInspectionResultV1:
    """Assemble the workspace read result for one resolved unit."""
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ...application.modelo.work_addressing import ModeloVisibleFilingTarget
    from ...application.modelo.workspace import resolve_static_inspection_result
    from ...application.modelo.workspace_models import ModeloWorkspaceVisibleFilingTargetV1
    from ...domain.calculations.registry.authority import bundled_authority

    return resolve_static_inspection_result(
        ModeloWorkspaceVisibleFilingTargetV1(
            target=ModeloVisibleFilingTarget(
                modelo=unit.modelo,
                filing_year=unit.filing_year,
                period=unit.period,
            )
        ),
        bucket_id=unit.bucket_id,
        catalogue_repository=WorkUnitCatalogueRepository(),
        authority=bundled_authority(),
        output_language=output_language,
    )


@contextmanager
def profile_storage_scope(root: Path) -> Generator[Path]:
    """Bind persistent profile infrastructure rooted at ``root`` for one TUI run.

    This is the sole TUI composition seam permitted to construct persistence
    adapters. Screens and devtools receive application contracts after this
    scope has bound them; neither needs to know which concrete adapter serves
    the session.
    """
    from ...core.config import SecretStoreBackend, load_settings, override_settings
    from ...core.storage_taxonomy import StorageCategory
    from ...core.storage_taxonomy_locations import STORAGE_TAXONOMY, storage_location
    from ..adapter_composition import profile_adapter_composition

    storage_root = root / "cadrumo-storage"
    secret_field = STORAGE_TAXONOMY[StorageCategory.SECRETS].settings_field
    if secret_field is None:
        message = "the declared secret storage category has no settings field"
        raise RuntimeError(message)
    secret_path = root / storage_location(StorageCategory.SECRETS).relative_path()
    with ExitStack() as composition:
        composition.enter_context(
            override_settings(
                cadrumo_local_storage_root=storage_root,
                cadrumo_active_profile=None,
                cadrumo_secret_store_backend=SecretStoreBackend.AUTO,
                cadrumo_secret_passphrase=load_settings().cadrumo_dev_test_database_password,
                cadrumo_profile_kdf_measure_calibration=False,
                **{secret_field: secret_path},
            )
        )
        composition.enter_context(profile_adapter_composition())
        yield storage_root


@asynccontextmanager
async def operation_services_scope() -> AsyncGenerator[OperationComposedServices]:
    """Compose the operation platform for one TUI run and settle it after.

    This is the sole TUI composition seam permitted to build the operation
    registry, journal, leases and supervisor. Screens and controllers receive
    the composed services; none of them constructs the graph, so a TUI session
    has exactly one place where that inventory comes into being.

    The factory itself lives one level up, shared with the CLI. Moving it into
    this package would oblige every other frontend to import the TUI to reach
    it, which is the dependency the TUI boundary exists to forbid.
    """
    from ..operation_composition import compose_operation_dependencies

    services = compose_operation_dependencies()
    try:
        yield services
    finally:
        await services.shutdown()


def compose_installed_workbench_search(
    snapshot: InstalledWorkbenchSearchSnapshotV1 | None = None,
) -> WorkbenchSearchDoorV1:
    """Bind one already-assembled immutable snapshot to the installed root.

    Snapshot assembly remains application-owned and happens before this
    boundary.  An uncomposed session honestly starts with no searchable
    documents; it never reads storage or contacts a service simply because the
    command palette opens.
    """
    from ...application.search.installed_workbench import InstalledWorkbenchSearchSnapshotV1

    return (snapshot or InstalledWorkbenchSearchSnapshotV1(())).service()


async def _run_root_session(
    *,
    headless: bool,
    auto_pilot: AutopilotCallbackType | None,
    workbench_search_snapshot: InstalledWorkbenchSearchSnapshotV1 | None = None,
    refresh_workbench_search: Callable[[], WorkbenchSearchDoorV1] | None = None,
) -> None:
    """Compose one session's services, run the root application, settle them.

    The services are composed OUTSIDE the application and handed to it, so
    the root never constructs its own graph and the scope still settles if
    the application raises on the way up or down.
    """
    from .app import CadrumoTuiApp

    async with operation_services_scope() as services:
        await CadrumoTuiApp(
            services=services,
            workbench_search_service=compose_installed_workbench_search(workbench_search_snapshot),
            refresh_workbench_search=refresh_workbench_search,
        ).run_async(headless=headless, auto_pilot=auto_pilot)


def main(*, headless: bool = False, auto_pilot: AutopilotCallbackType | None = None) -> int:
    """Start one dedicated TUI session and report its process exit status.

    This is the sole entry point for module execution and for the installed
    console script; neither reaches past it into the composition seams, and
    neither imports the CLI. ``headless`` and ``auto_pilot`` are Textual's
    own run parameters, carried so a caller can drive a real session to
    completion without a terminal rather than assert against an import.
    """
    asyncio.run(_run_root_session(headless=headless, auto_pilot=auto_pilot))
    return 0


__all__ = [
    "build_modelo_work_review_for_unit",
    "compose_installed_workbench_search",
    "load_modelo_work_unit_catalogue",
    "load_modelo_work_units",
    "main",
    "operation_services_scope",
    "profile_storage_scope",
    "resolve_modelo_work_unit",
    "resolve_modelo_workspace_static_inspection",
]
