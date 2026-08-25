"""Concrete runtime composition for installed and diagnostic TUI sessions."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from ...domain.modelos import WorkUnitCatalogue


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
    from ...adapters.outbound.aeat.auth.provider_selection import select_provider as select_outbound_auth_provider
    from ...adapters.outbound.aeat.auth.session_store import build_session_store
    from ...adapters.persistence.profile.extracted_document_cache import ExtractedDocumentCacheRepository
    from ...adapters.persistence.storage import build_profile_custody_port, build_profile_login_session_port
    from ...adapters.persistence.workflow import build_workflow_persistence_port
    from ...application.auth.protocols import bind_session_store
    from ...application.auth.providers import bind_auth_provider_selector
    from ...application.ledger.extracted_document_cache import bind_extracted_document_cache_repository_factory
    from ...application.user_profile.custody_ports import bind_profile_custody_port
    from ...application.user_profile.language_resolver import register_language_resolver
    from ...application.user_profile.login_session_port import bind_profile_login_session_port
    from ...application.workflow.persistence import bind_workflow_persistence_port
    from ...core import STORAGE_TAXONOMY, StorageCategory, storage_location
    from ...core.config import SecretStoreBackend, load_settings, override_settings

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
        composition.enter_context(bind_profile_custody_port(build_profile_custody_port()))
        composition.enter_context(bind_profile_login_session_port(build_profile_login_session_port()))
        composition.enter_context(bind_workflow_persistence_port(build_workflow_persistence_port()))
        composition.enter_context(bind_extracted_document_cache_repository_factory(ExtractedDocumentCacheRepository))
        composition.enter_context(bind_auth_provider_selector(select_outbound_auth_provider))
        composition.enter_context(bind_session_store(build_session_store()))
        register_language_resolver()
        yield storage_root


__all__ = ["load_modelo_work_unit_catalogue", "profile_storage_scope"]
