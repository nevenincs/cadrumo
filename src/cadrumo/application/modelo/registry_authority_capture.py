"""Workspace registry capture port served from one published authority operation."""

from __future__ import annotations

from datetime import date

from ...core.authority_grade import RegistryAuthorityGrade
from ...domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    RegistryAuthorityCapture,
    RegistryAuthorityCurrentCoordinate,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.snapshot import collect_snapshot_ref_ids
from ...domain.calculations.registry.static_inspection import RegistryRevisionInspection
from ...domain.calculations.registry.temporal import select_revision_metadata


class PinnedRegistryAuthorityCapture:
    """Answer the workspace registry capture port from one generation-pinned operation.

    The capture's comparison domain is the operation's logical generation, so
    a later read admitted against the same published generation compares
    equal and a republished generation does not.
    """

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        """Bind the port to an already-leased authority operation."""
        self._operation = operation

    def capture_law_selected_projection(
        self,
        modelo_id: str,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
        grade: RegistryAuthorityGrade | None = None,
    ) -> RegistryAuthorityCapture:
        """Capture the static inspection, or the grade-admitted snapshot, for one filing coordinate."""
        directory = self._operation.modelo_directory(modelo_id)
        selected = select_revision_metadata(directory, filing_year=filing_year, period=period, on=on)
        revision = self._operation.revision(modelo_id, str(selected.id))
        if grade is None:
            modelo_definition = directory.materialize(revision)
            legal_ids, source_ids = collect_snapshot_ref_ids(modelo_definition, revision)
            projection: RegistryRevisionInspection | RegistrySnapshot = RegistryRevisionInspection.from_revision(
                modelo=modelo_definition,
                revision=revision,
                source_root=None,
                sources={source_id: self._operation.source_reference(source_id) for source_id in source_ids},
                legal_ref_ids=frozenset(legal_ids),
            )
        else:
            projection = self._operation.snapshot(
                modelo_id,
                filing_year=filing_year,
                period=period,
                on=on,
                grade=grade,
            )
        return RegistryAuthorityCapture(
            projection=projection,
            comparison_domain=self._operation.generation.logical_generation,
            generation=0,
        )

    def read_current_coordinate(self) -> RegistryAuthorityCurrentCoordinate:
        """Return the coordinate a capture from this operation compares against."""
        return RegistryAuthorityCurrentCoordinate(
            comparison_domain=self._operation.generation.logical_generation,
            generation=0,
        )
