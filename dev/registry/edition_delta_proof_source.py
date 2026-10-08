"""Read one edition from either side of an independent delta proof."""

from __future__ import annotations

from pathlib import Path

from cadrumo.domain.calculations.registry.errors import RegistryError

from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_source as _edition_delta_source


def read_staged_edition(modelo_dir: Path, revision_id: str, *, side: str) -> _edition_delta_source._EditionSource:
    """Read one edition from a proof tree, refusing the migration when that side does not materialise."""
    try:
        return _edition_delta_source._read_edition(modelo_dir, revision_id)
    except RegistryError as exc:
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r}: the {side} tree does not materialise: {type(exc).__name__}: {exc}",
        ) from exc
