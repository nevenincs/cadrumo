"""Refuse an export that would write one casilla's value into unrelated cells.

This module uses :class:`RegistrySnapshot`, the pinned registry snapshot.
"""

from __future__ import annotations

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.export_shared_owner import written_unadjudicated_shared_owners
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.filing.errors import FilingExportValidationError
from .export_refusal_doors import ExportRefusalReason, export_design_terminal

_REFUSAL_MESSAGE = "application.filing.export.errors.shared_casilla_cells_unadjudicated"


def refuse_written_shared_owners(
    layout: ExportLayoutDefinition,
    *,
    registry_snapshot: RegistrySnapshot,
    casilla_values: dict[CasillaId, object],
) -> None:
    """Refuse before any byte exists when a value would reach cells of unconfirmed meaning.

    ``registry_snapshot`` is the :class:`RegistrySnapshot`, the pinned registry snapshot.
    """
    owners = written_unadjudicated_shared_owners(layout, registry_snapshot.revision.casillas, casilla_values)
    if not owners:
        return
    raise FilingExportValidationError(
        translated_message=_REFUSAL_MESSAGE,
        context={
            "modelo": str(registry_snapshot.modelo.id),
            "revision_id": str(registry_snapshot.revision.id),
            "layout_id": str(layout.id),
            "casilla_ids": ", ".join(str(owner.casilla_id) for owner in owners),
            "target_cells": {str(owner.casilla_id): list(owner.target_cell_ids) for owner in owners},
        },
        precondition_verdict=export_design_terminal(ExportRefusalReason.SHARED_CELLS_UNADJUDICATED),
    )


def is_shared_owner_refusal(error: BaseException) -> bool:
    """Say whether ``error`` is this refusal, which the modelo export boundary shows as it is."""
    translated_message = getattr(error, "translated_message", None)
    return isinstance(translated_message, str) and translated_message == _REFUSAL_MESSAGE


__all__ = ["is_shared_owner_refusal", "refuse_written_shared_owners"]
