"""Registry-wide ratchet ceiling for orden_aplicabilidad follow-up items.

The period-revision-resolution decision requires the orden_aplicabilidad
follow-up (advisory) population to shrink monotonically. This test loads the
REAL registry and counts every revision that produces a follow-up item, then
asserts the count is at or below the ceiling N.

N is pinned at the CURRENT count (15 as of 2026-06-29). DO NOT raise N. Only
lower it as backfill progresses. The gate exists to ensure the unstamped
pre-ratchet population can only ratchet DOWN.

Hard failures (new revisions without orden_aplicabilidad, or dangling /
corpus-less entries) are NOT counted here — those block the registry load
entirely and are tested in test_orden_aplicabilidad.py.  This test concerns
only the advisory / follow-up track: pre-ratchet (valid_from < 2026-06-10)
revisions that have not yet been backfilled.

No mocks.  No skips.  No xfail.  Real registry, real loader.
"""

from __future__ import annotations

from functools import cache

import pytest

from .....core.resources import bundled_path
from .._loader import load_registry_tree
from .._validate_orden_aplicabilidad import validate_orden_aplicabilidad

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# ---------------------------------------------------------------------------
# Ratchet ceiling — NEVER RAISE THIS NUMBER.
# Lower it as follow-up backfill progresses.
# Current as of 2026-06-29 (legal-grounding gap discovery pass).
# ---------------------------------------------------------------------------
_FOLLOW_UP_COUNT_CEILING: int = 15

_REGISTRY_ROOT = bundled_path("registry", "aeat")


@cache
def _registry_follow_up_count() -> tuple[int, list[str]]:
    """Load the registry and count follow-up items from validate_orden_aplicabilidad.

    Returns (count, list_of_revision_identifiers_with_follow_ups).
    """
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    total = 0
    affected: list[str] = []
    for modelo in modelos:
        for rev_id, revision in modelo.revisions.items():
            _hard, follow_up = validate_orden_aplicabilidad(
                f"modelo {modelo.id} revision {rev_id}",
                modelo.id,
                revision,
                catalogues.legal,
            )
            if follow_up:
                total += len(follow_up)
                affected.append(f"{modelo.id}/{rev_id}")
    return total, sorted(affected)


def test_orden_aplicabilidad_follow_up_count_does_not_exceed_ceiling() -> None:
    """The number of follow-up items across the full registry must not exceed
    _FOLLOW_UP_COUNT_CEILING.

    When this test fails, it means a new pre-ratchet revision was added to the
    registry without backfilling its orden_aplicabilidad — a ratchet regression.
    Fix it by adding the orden_aplicabilidad entry to the new revision's TOML,
    not by raising the ceiling.
    """
    count, affected = _registry_follow_up_count()
    assert count <= _FOLLOW_UP_COUNT_CEILING, (
        f"orden_aplicabilidad follow-up count is {count}, exceeding the "
        f"ratchet ceiling of {_FOLLOW_UP_COUNT_CEILING}. "
        f"DO NOT raise the ceiling. Instead, backfill orden_aplicabilidad "
        f"for the newly-added pre-ratchet revisions or ensure new revisions "
        f"(valid_from >= 2026-06-10) declare it (hard failure, not follow-up). "
        f"Affected revisions ({len(affected)}):\n" + "\n".join(f"  {r}" for r in affected)
    )


def test_orden_aplicabilidad_no_hard_failures_in_registry() -> None:
    """No revision in the full registry produces hard gate failures.

    Hard failures (new revision without orden_aplicabilidad, dangling entry,
    corpus-less entry, entry absent from legal_refs) block registry load.
    If the registry loads, they are absent — this test is a belt-and-suspenders
    assertion that the loader's hard-failure gate stayed intact.
    """
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    all_hard: list[str] = []
    for modelo in modelos:
        for rev_id, revision in modelo.revisions.items():
            hard, _follow_up = validate_orden_aplicabilidad(
                f"modelo {modelo.id} revision {rev_id}",
                modelo.id,
                revision,
                catalogues.legal,
            )
            all_hard.extend(f"{modelo.id}/{rev_id}: {msg}" for msg in hard)

    assert not all_hard, f"Hard gate failures found in the committed registry ({len(all_hard)} total):\n" + "\n".join(
        f"  {item}" for item in all_hard
    )
