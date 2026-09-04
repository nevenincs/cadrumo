"""Band-containment gate: a per-query relevance boost never leaves its class.

The committed relevance file is query-keyed, but the search index stores one
static weight per record, so the query dimension cannot survive injection. The
loader resolves that mismatch by keeping each record's strongest weight across
every query. Taking the stronger of THAT and the record's base weight let any
record which topped a single query outrank whole classes above it for every
query -- a legal provision boosted to 0.98 sat above the casilla rows at 0.8
and the modelo cards at 0.9 that it merely grounds.

The governing contract confines a boost to the band between its own class's
declared weight and the next class's, reserving a margin so it approaches but
never reaches the class above. Curation then orders within a class and the
declared ladder orders across classes, which is what each authority is for.

These gates assert that invariant over the REAL committed relevance data and
the REAL declared table, never over a synthetic fixture, and they first prove
the corpus actually contains boosts that would escape -- so a future corpus
with nothing to contain cannot let the gate pass vacuously.
"""

from __future__ import annotations

import json
from itertools import pairwise

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _strongest_committed_boosts() -> dict[tuple[str, str], float]:
    """Return ``(record_id, kind) -> strongest committed weight`` from real data.

    Mirrors what the injector's loader collapses the query-keyed file down to,
    read straight from the committed bytes through the one path authority
    rather than through a fixture or a hand-rolled path.
    """
    from .._miss_rate import relevance_mapping_path

    path = relevance_mapping_path()
    if not path.is_file():
        pytest.fail(f"committed relevance data missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    strongest: dict[tuple[str, str], float] = {}
    for mapping in payload["mappings"]:
        for target in mapping["targets"]:
            key = (target["record_id"], target["kind"])
            weight = float(target["ranking_weight"])
            if weight > strongest.get(key, -1.0):
                strongest[key] = weight
    return strongest


def _display_class_for_kind(kind: str):
    from ..search_record import SearchRecordKind
    from ..unified_record import _KIND_TO_DISPLAY_CLASS

    return _KIND_TO_DISPLAY_CLASS[SearchRecordKind(kind)]


def test_the_committed_corpus_actually_contains_boosts_that_would_escape() -> None:
    """The gate below has a live subject: raw boosts do exceed their band.

    Without this anchor a corpus whose every boost happened to sit inside its
    band would make the containment gate pass while proving nothing.
    """
    from ..unified_record import display_class_band_ceiling

    escaping = [
        (record_id, weight)
        for (record_id, kind), weight in _strongest_committed_boosts().items()
        if weight > display_class_band_ceiling(_display_class_for_kind(kind))
    ]
    assert escaping, "no committed boost exceeds its band ceiling; the containment gate would prove nothing"


def test_no_contained_boost_reaches_its_band_ceiling() -> None:
    """Every committed boost, once contained, stays strictly inside its band."""
    from ..unified_record import (
        contain_boost_in_band,
        display_class_band_ceiling,
        display_class_base_weight,
    )

    violations: list[str] = []
    for (record_id, kind), weight in _strongest_committed_boosts().items():
        display_class = _display_class_for_kind(kind)
        floor = display_class_base_weight(display_class)
        ceiling = display_class_band_ceiling(display_class)
        contained = contain_boost_in_band(display_class, weight)
        if not floor <= contained <= ceiling:
            violations.append(f"{record_id} ({display_class.value}): {contained} outside [{floor}, {ceiling}]")
        elif contained == ceiling and ceiling > floor:
            violations.append(f"{record_id} ({display_class.value}): {contained} reaches its ceiling {ceiling}")
    assert not violations, "contained boosts left their band:\n" + "\n".join(f"  - {row}" for row in violations)


def test_no_contained_boost_reaches_the_floor_of_any_higher_class() -> None:
    """The defect stated directly: a boost must never overtake a class above it.

    A legal provision boosted for one query outranked every casilla row and
    every modelo card for all queries. This asserts against every higher class
    at once, so a future band whose ceiling is mis-derived is still caught.
    """
    from ..search_record import ResultDisplayClass
    from ..unified_record import contain_boost_in_band, display_class_base_weight

    violations: list[str] = []
    for (record_id, kind), weight in _strongest_committed_boosts().items():
        display_class = _display_class_for_kind(kind)
        floor = display_class_base_weight(display_class)
        contained = contain_boost_in_band(display_class, weight)
        for other in ResultDisplayClass:
            other_floor = display_class_base_weight(other)
            if other_floor > floor and contained >= other_floor:
                violations.append(f"{record_id} ({display_class.value}) at {contained} reaches {other.value}")
    assert not violations, "boosted records overtook a higher class:\n" + "\n".join(f"  - {row}" for row in violations)


def test_an_unboosted_record_sits_exactly_on_its_floor() -> None:
    """A zero boost yields the declared weight, so the ladder is preserved."""
    from ..search_record import ResultDisplayClass
    from ..unified_record import contain_boost_in_band, display_class_base_weight

    for display_class in ResultDisplayClass:
        assert contain_boost_in_band(display_class, 0.0) == display_class_base_weight(display_class)


def test_a_stronger_boost_ranks_higher_within_the_band() -> None:
    """Curation keeps its resolution: boosts still order records continuously.

    Ordering must be STRICT. A rejected alternative simply clamped the boost to
    the base weight, which leaves it either below the base and ignored or above
    it and clipped back to it -- so distinct boosts collapse onto one value and
    curation silently stops ordering anything. A merely non-decreasing
    assertion passes under that inert behaviour, so it would not catch it.

    Checked on a class with headroom; the top class is bounded by its own floor
    and is excluded because it has none to order within.
    """
    from ..search_record import ResultDisplayClass
    from ..unified_record import (
        contain_boost_in_band,
        display_class_band_ceiling,
        display_class_base_weight,
    )

    with_headroom = [
        member
        for member in ResultDisplayClass
        if display_class_band_ceiling(member) > display_class_base_weight(member)
    ]
    assert with_headroom, "no class carries headroom; boosts could not order anything"
    for display_class in with_headroom:
        ranked = [contain_boost_in_band(display_class, boost) for boost in (0.1, 0.4, 0.7, 0.95)]
        assert all(weaker < stronger for weaker, stronger in pairwise(ranked)), (
            f"{display_class.value}: distinct boosts collapsed onto the same weight: {ranked}"
        )


def test_a_boost_outside_the_unit_interval_clamps_rather_than_escapes() -> None:
    """A malformed weight cannot become a cross-band promotion."""
    from ..search_record import ResultDisplayClass
    from ..unified_record import (
        contain_boost_in_band,
        display_class_band_ceiling,
        display_class_base_weight,
    )

    for display_class in ResultDisplayClass:
        floor = display_class_base_weight(display_class)
        ceiling = display_class_band_ceiling(display_class)
        assert contain_boost_in_band(display_class, -5.0) == floor
        assert floor <= contain_boost_in_band(display_class, 42.0) <= ceiling
