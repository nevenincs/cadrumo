"""Real proof for the launcher's shared Modelo projection reader.

``_modelo_projection_reader`` is the one seam that tries GRADED_SNAPSHOT and
falls back to STATIC_INSPECTION on a taxpayer-facing refusal. These tests
exercise it against a real bucket, a real registry authority and a real
work unit -- never a mocked resolver -- so the fallback and the carried
refusal are proven against the actual admission functions, not a stand-in
that would agree with itself.
"""

from __future__ import annotations

from datetime import date
from typing import cast

import pytest

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......application.modelo.workspace_models import ModeloWorkspaceRefusalCode
from ......application.producer_capture import ProducerCaptureError
from ......application.workbench_generation import ModeloWorkspaceProjectedReadV1
from ......core.authority_grade import RegistryAuthorityGrade
from ......domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    RegistryAuthorityCapture,
    RegistryAuthorityCurrentCoordinate,
    bundled_indexed_authority,
)
from ....launcher import MODELO_WORKSPACE_READ_ATTEMPTS, _modelo_projection_reader

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_the_reader_falls_back_to_static_and_carries_the_refusal_it_fell_back_from(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """A freshly created work unit has no calculation, so the graded read refuses honestly.

    The refused arm is CALCULATION_UNAVAILABLE: the seeded work unit exists
    (ruling out TARGET_NOT_FOUND) but was never calculated. The returned
    projection is still admitted -- STATIC_INSPECTION remains valid for this
    refusal -- and the refusal travels alongside it rather than being
    silently discarded.
    """
    bucket_id, repository = bucket_and_repository
    catalogue, _ = repository.load_revisioned()
    (unit,) = catalogue.work_units.values()

    with bundled_indexed_authority().operation() as operation:
        read = _modelo_projection_reader(operation)(unit)

    assert isinstance(read, ModeloWorkspaceProjectedReadV1)
    assert read.graded_refusal is not None
    assert read.graded_refusal.code is ModeloWorkspaceRefusalCode.CALCULATION_UNAVAILABLE
    assert read.graded_refusal.selected_target is not None
    assert read.graded_refusal.selected_target.work_unit_id == unit.work_unit_id
    assert read.projection.target.work_unit_id == unit.work_unit_id
    assert read.projection.target.bucket_id == bucket_id


class _RepublishedAfterEveryCapture:
    """The real pinned operation, republished after every registry capture taken from it.

    Every admission therefore finds the registry moved at its currentness
    pass. Only the coordinate read is altered; every other call, the captures
    included, is the real operation's.
    """

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self._operation = operation
        self._republications = 0

    def capture_law_selected_projection(
        self,
        modelo_id: str,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
        grade: RegistryAuthorityGrade | None = None,
    ) -> RegistryAuthorityCapture:
        capture = self._operation.capture_law_selected_projection(
            modelo_id, filing_year=filing_year, period=period, on=on, grade=grade
        )
        self._republications += 1
        return capture

    def read_current_coordinate(self) -> RegistryAuthorityCurrentCoordinate:
        current = self._operation.read_current_coordinate()
        return RegistryAuthorityCurrentCoordinate(
            comparison_domain=current.comparison_domain,
            generation=current.generation + self._republications,
        )

    def __getattr__(self, name: str) -> object:
        return getattr(self._operation, name)


def test_the_reader_gives_up_on_a_unit_that_changes_on_every_read(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """A bounded number of re-reads, then the contended refusal; never an endless loop."""
    _bucket_id, repository = bucket_and_repository
    catalogue, _ = repository.load_revisioned()
    (unit,) = catalogue.work_units.values()

    with bundled_indexed_authority().operation() as operation:
        republishing = cast("PinnedAuthorityOperation", _RepublishedAfterEveryCapture(operation))
        with pytest.raises(ProducerCaptureError) as refusal:
            _modelo_projection_reader(republishing)(unit)

    assert refusal.value.context == {"reason": "contended", "attempts": MODELO_WORKSPACE_READ_ATTEMPTS}
