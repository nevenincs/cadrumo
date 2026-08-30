"""Concrete runtime composition for installed and diagnostic TUI sessions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from contextlib import ExitStack, asynccontextmanager, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from ...domain.modelos.work_unit import WorkUnitCatalogue

if TYPE_CHECKING:
    from textual.app import AutopilotCallbackType

    from ...application.operations.composition import OperationComposedServices


def load_modelo_work_unit_catalogue(bucket_id: str) -> WorkUnitCatalogue:
    """Load one profile's work-unit catalogue at the TUI composition boundary."""
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository

    return WorkUnitCatalogueRepository(bucket_id=bucket_id).load()


@contextmanager
def profile_storage_scope(root: Path) -> Generator[Path]:
    """Bind persistent profile infrastructure rooted at ``root`` for one TUI run.

    This is the sole TUI composition seam permitted to construct persistence
    adapters. Screens and devtools receive application contracts after this
    scope has bound them; neither needs to know which concrete adapter serves
    the session.
    """
    from ...core import STORAGE_TAXONOMY, StorageCategory, storage_location
    from ...core.config import SecretStoreBackend, load_settings, override_settings
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


async def _run_root_session(*, headless: bool, auto_pilot: AutopilotCallbackType | None) -> None:
    """Compose one session's services, run the root application, settle them.

    The services are composed OUTSIDE the application and handed to it, so
    the root never constructs its own graph and the scope still settles if
    the application raises on the way up or down.
    """
    from .app import CadrumoTuiApp

    async with operation_services_scope() as services:
        await CadrumoTuiApp(services=services).run_async(headless=headless, auto_pilot=auto_pilot)


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


__all__ = ["load_modelo_work_unit_catalogue", "main", "operation_services_scope", "profile_storage_scope"]
