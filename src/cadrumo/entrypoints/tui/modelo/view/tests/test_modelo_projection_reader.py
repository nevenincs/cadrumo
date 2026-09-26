"""Real proof for the launcher's shared Modelo projection reader.

``_modelo_projection_reader`` is the one seam that tries GRADED_SNAPSHOT and
falls back to STATIC_INSPECTION on a taxpayer-facing refusal. These tests
exercise it against a real bucket, a real registry authority and a real
work unit -- never a mocked resolver -- so the fallback and the carried
refusal are proven against the actual admission functions, not a stand-in
that would agree with itself.
"""

from __future__ import annotations

import pytest

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......application.modelo.workspace_models import ModeloWorkspaceRefusalCode
from ......application.workbench_generation import ModeloWorkspaceProjectedReadV1
from ......domain.calculations.registry.authority import bundled_indexed_authority
from ....launcher import _modelo_projection_reader

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
