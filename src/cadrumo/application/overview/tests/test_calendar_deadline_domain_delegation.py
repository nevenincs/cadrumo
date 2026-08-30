"""Overview delegates window matching and status classification to the deadline domain.

The overview calendar used to carry its own copy of two deadline rules: it
scanned ``authority.deadline_windows(filing_year)`` for a matching registry
window, and it restated the OVERDUE / DUE_TODAY / DUE_SOON / UPCOMING
boundaries around ``closes_on``. Both copies AGREED with the deadline domain,
which is precisely what made them dangerous — a change to either rule could
move extemporaneidad and calendar placement independently, and no parity
assertion would have noticed until after they had already diverged.

That agreement also governs what can be proven here. A test asserting "overview
and the deadline domain return the same window / the same status" passes
whether or not overview delegates, because the duplicate produced the same
answers. Such assertions are SUPPORTING only. The DISCRIMINATING assertions in
this module therefore test the MECHANISM — that overview actually reaches the
canonical owner — so that removing the delegation fails them.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ....core import Period
from ....domain.deadlines.engine import classify_obligation_status
from ....domain.deadlines.models import ObligationStatus
from ....domain.deadlines.plazo import resolve_filing_closes_on, resolve_filing_window
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..calendar import _local_work_unit_status, _registry_window_for_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Declared locally rather than imported from ``calendar_test_support``: that
# module resolves a registry snapshot at import time, which would couple the
# classification tests below to a registry load they do not need.
_BUCKET_ID = "7390a6bb-5577-4e08-8518-16e6292f690f"
_MODELO = "130"
_FILING_YEAR = 2026
_DUE_SOON_DAYS = 14


def _work_unit(period_code: str = "1T") -> WorkUnit:
    """Build a real Modelo 130 work unit for a registry-covered period."""
    period = Period.from_year_and_code(_FILING_YEAR, period_code)
    revision_id = "deadline-domain-delegation"
    created_at = datetime(_FILING_YEAR, 1, 2, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=ModeloCode(_MODELO),
            filing_year=_FILING_YEAR,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(_MODELO),
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision_id,
        name=f"delegation-{_MODELO}-{_FILING_YEAR}",
        created_at=created_at,
        updated_at=created_at,
    )


# ---------------------------------------------------------------------------
# F63 — one registry deadline-window resolver
# ---------------------------------------------------------------------------


def test_overview_window_lookup_goes_through_the_domain_resolver_cache() -> None:
    """DISCRIMINATING: overview's lookup must reach the canonical resolver.

    ``resolve_filing_window`` is ``lru_cache``-backed, so its miss counter is a
    real instrument for whether a caller went through it. Evicting the cache
    and then calling overview's helper must register a miss; a reimplemented
    local scan inside overview would answer correctly and leave the counter at
    zero. This asserts the mechanism, which a parity assertion cannot.
    """
    unit = _work_unit()
    resolve_filing_window.cache_clear()
    assert resolve_filing_window.cache_info().misses == 0, "cache_clear must reset the instrument"

    _registry_window_for_work_unit(unit)

    assert resolve_filing_window.cache_info().misses == 1, (
        "overview resolved a deadline window without going through domain.deadlines.resolve_filing_window"
    )


def test_overview_window_lookup_reuses_the_cached_domain_entry() -> None:
    """DISCRIMINATING: a repeat overview lookup must hit the domain cache.

    A local reimplementation would rescan the authority on every call and never
    register a hit, so the hit counter distinguishes delegation from a
    coincidentally-equal duplicate.
    """
    unit = _work_unit()
    resolve_filing_window.cache_clear()

    _registry_window_for_work_unit(unit)
    _registry_window_for_work_unit(unit)

    info = resolve_filing_window.cache_info()
    assert (info.misses, info.hits) == (1, 1), f"expected one miss then one hit, got {info}"


def test_domain_closes_on_projects_the_same_window_overview_reads() -> None:
    """SUPPORTING: the two surfaces agree on the window they resolve.

    This agreement held BEFORE the consolidation, so it cannot fail under the
    mutation and is context rather than proof. It is retained because it pins
    the projection contract: the extemporaneidad surface must expose exactly
    the ``closes_on`` of the window overview reads for the same target.
    """
    unit = _work_unit()
    window = _registry_window_for_work_unit(unit)
    assert window is not None, "Modelo 130 2026 1T must have a bundled registry deadline window"

    assert resolve_filing_closes_on(_MODELO, _FILING_YEAR, unit.period) == window.closes_on


def test_overview_keeps_its_local_period_fallback_when_no_window_exists() -> None:
    """SUPPORTING: an unmatched target still yields ``None`` from the resolver.

    Overview's own fallback to the period date span depends on this contract,
    and the shared resolver must not start borrowing a neighbouring year's
    window to avoid returning ``None``.
    """
    far_future_year = 2200  # the highest year the typed Period accepts
    far_future = Period.from_year_and_code(far_future_year, "1T")

    assert resolve_filing_window(_MODELO, far_future_year, far_future) is None


# ---------------------------------------------------------------------------
# F64 — one obligation status classifier
# ---------------------------------------------------------------------------


def test_overview_status_calls_the_canonical_classifier() -> None:
    """DISCRIMINATING: overview must delegate its date boundaries.

    The retired duplicate restated the four boundary comparisons inline and
    returned identical statuses, so no outcome assertion can separate the two
    implementations. The compiled name references can: a restated
    implementation references ``ObligationStatus`` four times and never names
    the classifier.
    """
    referenced = _local_work_unit_status.__code__.co_names

    assert "_classify_obligation_status" in referenced, (
        "overview._local_work_unit_status must delegate to "
        "domain.deadlines.classify_obligation_status; referenced names were "
        f"{referenced}"
    )


def test_overview_filing_gate_short_circuits_before_the_classifier() -> None:
    """DISCRIMINATING: the filed-pointer gate is the one intentional difference.

    A unit carrying a filing pointer must report FILED even on a date the
    canonical classifier calls OVERDUE. Removing overview's gate — or moving it
    after the delegation — makes this return OVERDUE and fails the test.
    """
    unit = _work_unit().model_copy(update={"current_filing_record_id": "filing-record-1"})
    closes_on = date(2026, 4, 20)
    today = date(2026, 6, 1)

    assert classify_obligation_status(closes_on, today, _DUE_SOON_DAYS) is ObligationStatus.OVERDUE
    assert _local_work_unit_status(unit, closes_on, today, _DUE_SOON_DAYS) is ObligationStatus.FILED


@pytest.mark.parametrize(
    ("today", "expected", "expected_delta"),
    (
        (date(2026, 4, 21), ObligationStatus.OVERDUE, -1),
        (date(2026, 4, 20), ObligationStatus.DUE_TODAY, 0),
        (date(2026, 4, 19), ObligationStatus.DUE_SOON, 1),
        (date(2026, 4, 6), ObligationStatus.DUE_SOON, 14),
        (date(2026, 4, 5), ObligationStatus.UPCOMING, 15),
    ),
)
def test_unfiled_work_unit_matches_the_classifier_at_every_boundary(
    today: date,
    expected: ObligationStatus,
    expected_delta: int,
) -> None:
    """SUPPORTING: every boundary agrees across both surfaces.

    The retired duplicate produced these same statuses, so this parametrisation
    passes under the mutation and is context, not proof. It is retained as the
    boundary inventory the delegation must keep honouring: OVERDUE the day
    after close, DUE_TODAY on it, DUE_SOON across the fourteen-day window
    inclusive of its far edge, and UPCOMING beyond it.

    ``expected_delta`` pins the GROUND of each verdict — the signed day
    distance to ``closes_on`` that produced it — so a status that happens to be
    right for an unrelated reason (a shifted close date, an off-by-one window)
    cannot read as agreement.
    """
    unit = _work_unit()
    closes_on = date(2026, 4, 20)
    assert (closes_on - today).days == expected_delta, "the case's stated ground must hold"

    assert _local_work_unit_status(unit, closes_on, today, _DUE_SOON_DAYS) is expected
    assert classify_obligation_status(closes_on, today, _DUE_SOON_DAYS) is expected
