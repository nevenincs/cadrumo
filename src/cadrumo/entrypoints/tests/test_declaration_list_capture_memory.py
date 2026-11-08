"""List-shaped reads of one profile share calendar work until a session ends, and never across profiles.

Calendar builds are counted by observing the real builder, as the capture
memory's own tests do, never by replacing it.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from ...application.tests.test_workbench_capture_memory import _calendar_builds
from ...application.tests.test_workbench_generation_undeclared_works import _work_unit
from ...application.tests.workbench_generation_support import NOW, Repository, plain_generation_door, profile_record
from ...application.workbench_capture_memory import WorkbenchCaptureMemory, WorkbenchCaptureMemoryOwner
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.work_unit import WorkUnitCatalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIRST = "22222222-2222-4222-8222-222222222222"
_SECOND = "33333333-3333-4333-8333-333333333333"


class _Profile:
    """One profile's stores, read afresh by each list capture as the exact-profile door does."""

    def __init__(self, authority_operation: PinnedAuthorityOperation) -> None:
        unit = _work_unit(authority_operation, "303", NOW.year, "1T")
        self.operation = authority_operation
        self.work_units = Repository(WorkUnitCatalogue.model_construct(work_units={unit.work_unit_id: unit}))
        self.profile = Repository(profile_record(authority_operation))

    def builds(self, memory: WorkbenchCaptureMemory) -> int:
        """How often one list capture through ``memory`` builds the legal calendar."""
        door = plain_generation_door(
            self.operation, profile=self.profile, work_units=cast(Any, self.work_units), capture_memory=memory
        )
        return _calendar_builds(door.read_declaration_list_inputs)


def test_a_second_list_capture_reuses_the_calendar_the_first_computed(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    stores, owner = _Profile(authority_operation), WorkbenchCaptureMemoryOwner()

    first = stores.builds(owner.for_profile(_FIRST))
    second = stores.builds(owner.for_profile(_FIRST))

    assert first > 0
    assert second == 0, "the second capture reused the stored calendar work"


def test_a_session_end_makes_the_next_list_capture_compute_its_calendar_again(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    stores, owner = _Profile(authority_operation), WorkbenchCaptureMemoryOwner()
    first = stores.builds(owner.for_profile(_FIRST))

    owner.close()
    again = stores.builds(owner.for_profile(_FIRST))

    assert again == first > 0, "the calendar kept before the session ended was not served after it"


def test_another_profile_never_reads_the_calendar_the_first_profile_kept(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    stores, owner = _Profile(authority_operation), WorkbenchCaptureMemoryOwner()
    first = stores.builds(owner.for_profile(_FIRST))

    other = stores.builds(owner.for_profile(_SECOND))

    assert other == first > 0


def test_a_committed_work_unit_write_makes_the_next_list_capture_compute_its_calendar_again(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    stores, owner = _Profile(authority_operation), WorkbenchCaptureMemoryOwner()
    first = stores.builds(owner.for_profile(_FIRST))

    stores.work_units.revisions = ("revision-2",)
    stores.work_units.calls = 0
    after_write = stores.builds(owner.for_profile(_FIRST))

    assert after_write == first > 0, "a stale calendar never survives a write to the work units it was read from"
