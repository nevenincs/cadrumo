"""The canonical lifecycle-order predicate holds exactly one order and no other.

``lifecycle_stages_in_canonical_order`` is the single ordering authority the
trajectory dimension of a golden scenario rests on, so it is checked over every
ordering of the four stages rather than one hand-picked pair. A stage absent
from a trajectory is unconstrained, which is what lets a scenario legitimately
stop at ``verify``, and a command the lifecycle does not name must not move the
verdict either way.
"""

from __future__ import annotations

from itertools import permutations

import pytest

from .._models import LIFECYCLE_STAGE_ORDER, lifecycle_stages_in_canonical_order

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_UNRELATED = ("config.profile.status", "overview.status", "ledger.view")


def _positions(trajectory: tuple[str, ...]) -> dict[str, int]:
    return {command: index for index, command in enumerate(trajectory)}


def test_exactly_one_ordering_of_every_stage_is_canonical() -> None:
    ordered = [
        candidate
        for candidate in permutations(LIFECYCLE_STAGE_ORDER)
        if lifecycle_stages_in_canonical_order(_positions(candidate))
    ]

    assert ordered == [LIFECYCLE_STAGE_ORDER]


@pytest.mark.parametrize("length", range(len(LIFECYCLE_STAGE_ORDER) + 1))
def test_every_subset_in_canonical_order_is_ordered_and_every_swap_in_it_is_not(length: int) -> None:
    for subset in permutations(LIFECYCLE_STAGE_ORDER, length):
        canonical = tuple(stage for stage in LIFECYCLE_STAGE_ORDER if stage in subset)
        assert lifecycle_stages_in_canonical_order(_positions(canonical)), canonical
        # A present pair out of order is refused, so "absent is unconstrained" is not "anything passes".
        assert lifecycle_stages_in_canonical_order(_positions(subset)) is (subset == canonical), subset


def test_commands_the_lifecycle_does_not_name_cannot_change_the_verdict() -> None:
    interleaved: list[str] = []
    for index, stage in enumerate(LIFECYCLE_STAGE_ORDER):
        interleaved.extend((_UNRELATED[index % len(_UNRELATED)], stage))
    reversed_stages = tuple(reversed(LIFECYCLE_STAGE_ORDER))

    assert lifecycle_stages_in_canonical_order(_positions(tuple(interleaved)))
    assert not lifecycle_stages_in_canonical_order(_positions((*_UNRELATED, *reversed_stages)))
    # No lifecycle stage is present at all, so there is nothing to order.
    assert lifecycle_stages_in_canonical_order(_positions(_UNRELATED))


def test_a_repeated_stage_is_read_at_its_last_position() -> None:
    create, calculate, verify, export = LIFECYCLE_STAGE_ORDER
    # ``_positions`` keeps the last index of a repeated command, which is the
    # position the runner's own mapping comprehension keeps.
    repeated = (create, calculate, verify, export, create)

    assert _positions(repeated)[create] == 4
    assert not lifecycle_stages_in_canonical_order(_positions(repeated))
