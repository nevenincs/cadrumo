"""Parity gate: the two storage-kind enums must agree where they overlap.

Two enums name the kind of a storage node, and they are **deliberately not
merged**. :class:`StorageNodeKind` in ``core`` answers the one question the
taxonomy asks -- is this member a directory or a single file -- because a
name-suffix heuristic cannot reach ``manifest.toml``, ``.lock``, or the
keystore sidecars. :class:`StoragePathKind` in the storage adapter answers a
wider one, adding ``LOGICAL_SQL`` for a row that lives in the encrypted
database rather than on disk, and ``BLOB_OBJECT`` for content-addressed blob
content. The adapter's set is a strict superset.

A duplication audit examined the pair and classified them CONSTRAINT-DIVERGENT
rather than duplicated: collapsing them would either force ``core`` to carry
adapter concepts it has no use for, or force the adapter to lose the two
members it genuinely needs. So the correct relationship is not one enum -- it
is two enums that **agree on the members they share**.

That agreement is the whole risk, and nothing enforced it. Both spell
``DIRECTORY = "directory"`` and ``FILE = "file"`` today, and code on either side
of the boundary compares them by value, because a :class:`~enum.StrEnum` member
equals its string. Change one spelling -- ``"file"`` to ``"FILE"``, or
``"directory"`` to ``"dir"`` -- and every such comparison silently starts
returning ``False``. Nothing raises. A member simply stops matching its
counterpart, and a node classified as a file on one side is classified as
nothing at all on the other.

This gate pins the overlap and only the overlap. It asserts that every member
NAME the two enums share carries the same VALUE, and it deliberately does not
assert the member sets are equal -- that would red the moment the adapter adds
a fifth kind, which is exactly the growth the divergence exists to permit.

The positive control is what makes the gate load-bearing: it constructs the
drift this gate exists to catch and proves the comparison rejects it. Without
it, a comparison that could never fail would read as protection.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

import pytest

from ...adapters.persistence.storage.namespace_taxonomy import StoragePathKind
from ..storage_taxonomy import StorageNodeKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


EXPECTED_SHARED_MEMBERS: Final[frozenset[str]] = frozenset({"DIRECTORY", "FILE"})
"""The member names both enums are expected to carry.

Pinned rather than derived so that *losing* an overlap is a failure too. A
purely computed intersection would silently shrink to nothing if a member were
renamed on one side, and an empty intersection trivially satisfies a
value-equality check -- the vacuous-pass shape this constant exists to refuse.
"""


def _shared_member_names() -> frozenset[str]:
    """Return the member names present in both enums."""
    return frozenset(StorageNodeKind.__members__) & frozenset(StoragePathKind.__members__)


def test_the_two_enums_still_share_the_expected_members() -> None:
    """The overlap is the pinned set, so a rename on either side is caught.

    Guards the value-equality test below against passing vacuously: an
    intersection that has quietly emptied would satisfy it with nothing to
    compare.
    """
    assert _shared_member_names() == EXPECTED_SHARED_MEMBERS, (
        f"the shared member set drifted to {sorted(_shared_member_names())}; "
        f"expected {sorted(EXPECTED_SHARED_MEMBERS)}. A member renamed on one side "
        f"breaks every cross-boundary comparison silently -- rename it on both, or "
        f"update this constant if the overlap genuinely changed"
    )


@pytest.mark.parametrize("member_name", sorted(EXPECTED_SHARED_MEMBERS))
def test_shared_members_carry_equal_values(member_name: str) -> None:
    """A member the two enums share must spell its value identically.

    Both are :class:`~enum.StrEnum`, so a member compares equal to its own
    string. Code on either side of the core/adapter boundary relies on that,
    which makes a divergent spelling a silent mismatch rather than an error.
    """
    core_value = StorageNodeKind[member_name].value
    adapter_value = StoragePathKind[member_name].value

    assert core_value == adapter_value, (
        f"StorageNodeKind.{member_name} = {core_value!r} but "
        f"StoragePathKind.{member_name} = {adapter_value!r}. These are compared by "
        f"value across the core/adapter boundary, so a divergent spelling makes the "
        f"comparison return False instead of raising -- fix the spelling, do not "
        f"relax this gate"
    )


def test_the_adapter_set_may_grow_without_reding_this_gate() -> None:
    """The superset relationship is permitted, and this gate must not forbid it.

    The two enums are CONSTRAINT-DIVERGENT by decision, not by accident. A gate
    asserting the member sets were equal would red on the next adapter-only kind
    and pressure a future author into merging enums the audit deliberately kept
    apart.
    """
    adapter_only = frozenset(StoragePathKind.__members__) - frozenset(StorageNodeKind.__members__)

    assert adapter_only, (
        "the adapter enum no longer carries any member of its own; if the two sets have "
        "genuinely converged, that is a design change to record, not to absorb silently"
    )


def test_a_divergent_spelling_would_be_caught_positive_control() -> None:
    """Prove the value comparison rejects the drift it exists to catch.

    Builds a stand-in adapter enum spelling a shared member differently and
    confirms the same comparison the gate performs fails against it. Without
    this, a check that happens to pass and a check that *cannot* fail are
    indistinguishable from a green run.
    """

    class DriftedPathKind(StrEnum):
        DIRECTORY = "dir"  # drifted from "directory"
        FILE = "file"

    shared = frozenset(StorageNodeKind.__members__) & frozenset(DriftedPathKind.__members__)
    assert "DIRECTORY" in shared, "the control must actually share the member it drifts"

    mismatches = [name for name in shared if StorageNodeKind[name].value != DriftedPathKind[name].value]

    assert mismatches == ["DIRECTORY"], (
        "the value comparison did not flag a deliberately drifted spelling, so it cannot flag a real one"
    )
