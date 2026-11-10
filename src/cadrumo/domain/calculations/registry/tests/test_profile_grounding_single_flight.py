"""The profile grounding index is walked once per generation, however many threads ask.

A background warm-up and an interactive read may both want the index of one
pinned generation. Each case runs the real registry-wide walk over the bundled
authority; the walk is only observed (counted and, where a case needs a walk to
be under way, held at its entry), never replaced. A read joins a walk already
under way rather than repeating it, a warm-up never waits on another walk, and
an abandoned warm-up leaves the read to walk itself. A deferred warm-up decodes
nothing while it is told to defer, and a read that joins it ends the deferral.
"""

from __future__ import annotations

import contextvars
import threading
from collections.abc import Callable, Generator, Mapping
from dataclasses import dataclass, field

import pytest

from .. import profile_grounding
from ..authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..profile_grounding import ProfileKeyGrounding, build_profile_grounding_index, warm_profile_grounding_index

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_WAIT_SECONDS = 120


@dataclass
class _ObservedWalks:
    """Count real walks and hold the first one at its entry until released."""

    entered: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)
    count: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def wrap(
        self, walk: Callable[..., Mapping[str, ProfileKeyGrounding] | None]
    ) -> Callable[..., Mapping[str, ProfileKeyGrounding] | None]:
        # An abandoned walk returns None; the wrapper passes the walk's own result through.
        def observed(*args: object, **kwargs: object) -> Mapping[str, ProfileKeyGrounding] | None:
            with self._lock:
                self.count += 1
                first = self.count == 1
            if first:
                self.entered.set()
                assert self.release.wait(_WAIT_SECONDS)
            return walk(*args, **kwargs)

        return observed


@pytest.fixture
def operation() -> Generator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as leased:
        yield leased


@pytest.fixture
def walks(monkeypatch: pytest.MonkeyPatch) -> _ObservedWalks:
    """Start every case from a cold process cache with the real walk observed."""
    monkeypatch.setattr(profile_grounding, "_grounding_index_cache", {})
    monkeypatch.setattr(profile_grounding, "_grounding_index_flights", {})
    observed = _ObservedWalks()
    monkeypatch.setattr(
        profile_grounding,
        "_compute_profile_grounding_index",
        observed.wrap(profile_grounding._compute_profile_grounding_index),
    )
    return observed


def _in_thread[T](call: Callable[[], T]) -> tuple[threading.Thread, list[T]]:
    """Run ``call`` on another thread inside this thread's governed-fact scope."""
    results: list[T] = []
    context = contextvars.copy_context()
    thread = threading.Thread(target=lambda: results.append(context.run(call)))
    thread.start()
    return thread, results


def test_a_read_joins_the_warm_up_under_way_and_the_registry_is_walked_once(
    operation: PinnedAuthorityOperation, walks: _ObservedWalks
) -> None:
    warming, warmed = _in_thread(lambda: warm_profile_grounding_index(operation, abandoned=lambda: False))
    assert walks.entered.wait(_WAIT_SECONDS)

    reading, read = _in_thread(lambda: build_profile_grounding_index(operation))
    reading.join(timeout=0.2)
    assert reading.is_alive(), "the read finished without the walk under way"
    assert walks.count == 1, "the read started a second walk instead of joining the first"

    walks.release.set()
    warming.join(timeout=_WAIT_SECONDS)
    reading.join(timeout=_WAIT_SECONDS)

    assert warmed == [True]
    assert walks.count == 1
    assert read[0] is build_profile_grounding_index(operation)
    assert "censo.status" in read[0]
    assert walks.count == 1


def test_a_warm_up_never_waits_on_a_read_already_walking(
    operation: PinnedAuthorityOperation, walks: _ObservedWalks
) -> None:
    reading, read = _in_thread(lambda: build_profile_grounding_index(operation))
    assert walks.entered.wait(_WAIT_SECONDS)

    # Returns at once on this thread while the read's walk is still held.
    assert warm_profile_grounding_index(operation, abandoned=lambda: False) is False
    assert walks.count == 1

    walks.release.set()
    reading.join(timeout=_WAIT_SECONDS)
    assert walks.count == 1
    # Once cached, a warm-up has nothing left to do.
    assert warm_profile_grounding_index(operation, abandoned=lambda: False) is False
    assert build_profile_grounding_index(operation) is read[0]


def test_an_abandoned_warm_up_caches_nothing_and_its_waiting_read_walks_itself(
    operation: PinnedAuthorityOperation, walks: _ObservedWalks
) -> None:
    closing = threading.Event()
    warming, warmed = _in_thread(lambda: warm_profile_grounding_index(operation, abandoned=closing.is_set))
    assert walks.entered.wait(_WAIT_SECONDS)
    reading, read = _in_thread(lambda: build_profile_grounding_index(operation))
    reading.join(timeout=0.2)
    assert reading.is_alive() and walks.count == 1

    closing.set()
    walks.release.set()
    warming.join(timeout=_WAIT_SECONDS)
    reading.join(timeout=_WAIT_SECONDS)

    assert warmed == [False]
    assert walks.count == 2, "the waiting read did not walk after the warm-up was abandoned"
    assert "censo.status" in read[0]
    assert build_profile_grounding_index(operation) is read[0]


@dataclass
class _CountedDecodes:
    """Count real revision decodes without replacing them."""

    count: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def wrap(self, decode: Callable[..., object]) -> Callable[..., object]:
        def observed(*args: object, **kwargs: object) -> object:
            with self._lock:
                self.count += 1
            return decode(*args, **kwargs)

        return observed


@pytest.fixture
def decodes(monkeypatch: pytest.MonkeyPatch) -> _CountedDecodes:
    counted = _CountedDecodes()
    monkeypatch.setattr(PinnedAuthorityOperation, "revision", counted.wrap(PinnedAuthorityOperation.revision))
    return counted


def test_a_deferred_warm_up_decodes_nothing_until_it_may_go_on(
    operation: PinnedAuthorityOperation, walks: _ObservedWalks, decodes: _CountedDecodes
) -> None:
    walks.release.set()
    busy = threading.Event()
    busy.set()
    warming, warmed = _in_thread(
        lambda: warm_profile_grounding_index(operation, abandoned=lambda: False, deferred=busy.is_set)
    )
    assert walks.entered.wait(_WAIT_SECONDS)
    warming.join(timeout=0.3)
    assert warming.is_alive(), "the warm-up finished while it was told to defer"
    assert decodes.count == 0
    assert profile_grounding._grounding_index_cache == {}

    busy.clear()
    warming.join(timeout=_WAIT_SECONDS)
    assert warmed == [True]
    assert decodes.count == len(operation.revision_ids())
    assert "censo.status" in build_profile_grounding_index(operation)


def test_a_read_joining_a_deferred_warm_up_ends_the_deferral(
    operation: PinnedAuthorityOperation, walks: _ObservedWalks
) -> None:
    walks.release.set()
    # Deferring forever: only the read that joins can let this walk go on.
    warming, warmed = _in_thread(
        lambda: warm_profile_grounding_index(operation, abandoned=lambda: False, deferred=lambda: True)
    )
    assert walks.entered.wait(_WAIT_SECONDS)

    reading, read = _in_thread(lambda: build_profile_grounding_index(operation))
    reading.join(timeout=_WAIT_SECONDS)
    warming.join(timeout=_WAIT_SECONDS)

    assert not reading.is_alive(), "the read waited on a walk that kept deferring to it"
    assert warmed == [True]
    assert walks.count == 1, "the read walked again instead of joining the deferred walk"
    assert "censo.status" in read[0]


def test_an_abandoned_deferred_warm_up_stops_without_decoding_or_caching(
    operation: PinnedAuthorityOperation, walks: _ObservedWalks, decodes: _CountedDecodes
) -> None:
    walks.release.set()
    closing = threading.Event()
    warming, warmed = _in_thread(
        lambda: warm_profile_grounding_index(operation, abandoned=closing.is_set, deferred=lambda: True)
    )
    assert walks.entered.wait(_WAIT_SECONDS)
    closing.set()
    warming.join(timeout=_WAIT_SECONDS)

    assert warmed == [False]
    assert decodes.count == 0
    assert profile_grounding._grounding_index_cache == {}
    assert profile_grounding._grounding_index_flights == {}
