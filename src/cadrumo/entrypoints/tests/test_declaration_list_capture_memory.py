"""List-shaped reads of one profile share calendar work, and never across profiles."""

from __future__ import annotations

from typing import Any, cast

import pytest

from ...application.tests.test_workbench_generation_undeclared_works import _work_unit
from ...application.tests.workbench_generation_support import NOW, Repository, plain_generation_door, profile_record
from ...application.workbench_capture_memory import WorkbenchCaptureMemory
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ..workbench_generation_composition import _declaration_list_capture_memory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIRST = "22222222-2222-4222-8222-222222222222"
_SECOND = "33333333-3333-4333-8333-333333333333"


def test_one_profile_reuses_its_memory_and_another_profile_closes_it() -> None:
    first = _declaration_list_capture_memory(_FIRST)
    assert _declaration_list_capture_memory(_FIRST) is first

    second = _declaration_list_capture_memory(_SECOND)
    assert second is not first
    built: list[int] = []
    key = cast(Any, object())
    first.calendar.reuse(key, lambda: built.append(1) or cast(Any, object()))
    first.calendar.reuse(key, lambda: built.append(1) or cast(Any, object()))
    assert len(built) == 2, "a closed memory stores nothing"


def test_a_second_list_capture_reuses_the_calendar_the_first_computed(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    unit = _work_unit(authority_operation, "303", NOW.year, "1T")
    work_units = Repository(WorkUnitCatalogue.model_construct(work_units={unit.work_unit_id: unit}))
    profile = Repository(profile_record(authority_operation))
    memory = WorkbenchCaptureMemory()

    def capture():
        door = plain_generation_door(
            authority_operation, profile=profile, work_units=cast(Any, work_units), capture_memory=memory
        )
        return door.read_declaration_list_inputs().calendar

    first = capture()
    second = capture()

    assert second is not None
    assert second.generated_at == first.generated_at, "the second capture reused the stored calendar work"
