"""CLI authority admission and dispatch-time storage materialization."""

from __future__ import annotations

from ..core.config import load_settings
from ..core.logging import get_logger

__all__ = ["admit_cli_authority", "provision_cli_storage"]

_LOGGER = get_logger(__name__)


def admit_cli_authority() -> None:
    """Validate the shipped authority before any command is parsed, writing nothing.

    Admission validates the published descriptor and content-addressed SQLite
    generation without hydrating registry components or reaching development
    authoring inputs, and it never creates storage: a help request, a bare
    group or a refused parse must leave a fresh state root untouched.
    """
    from ..domain.calculations.registry.authority_location import bundled_authority_descriptor_path
    from ..domain.calculations.registry.authority_store import require_authority_store_available

    require_authority_store_available(bundled_authority_descriptor_path())
    _LOGGER.debug("CLI authority admitted")


def provision_cli_storage(*, writes_state: bool) -> None:
    """Provision owned storage defaults for a command that parsing has accepted to run.

    Explicit storage overrides are dependencies and are validated by the
    materializer rather than created, for every command that runs. Called at
    dispatch, once parse-time refusals have had their chance. Only a command
    that may write state materialises the state tree; one that writes nothing
    gets the derived, rebuildable caches its work may fill, so a first run
    never looks like a configured install.
    """
    from ..core.storage_materialization import ensure_storage_tree
    from ..core.storage_taxonomy import StorageGrouping

    ensure_storage_tree(
        load_settings(),
        derived_groupings=None if writes_state else frozenset({StorageGrouping.CACHE}),
    )
