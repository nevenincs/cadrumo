"""Central repo-wide gate for the compatibility-lifecycle governance.

The per-tier lineage gates own each persisted format's floor-vs-current
assertion intra-package; this gate owns the three cross-cutting invariants
that bind the regime itself, plus the cross-version fixture-coverage harness.

- **Version-milestone tripwire.** While ``COMPATIBILITY_REGIME`` is
  ``PRE_RELEASE`` the package version must stay below ``1.0.0``. This catches
  a 1.0 cut made without consciously flipping the regime — the safety net
  kept behind the primary constant-owned decision.
- **One-way coherence.** ``RELEASED_FORMAT_FLOORS`` is populated if and only
  if the regime is ``RELEASED``. The frozen floors and the regime constant
  can never drift apart.
- **Enrollment, both directions.** Every key in a populated
  ``RELEASED_FORMAT_FLOORS`` names a live persisted-format tier, AND every
  format declared ``DURABLE`` carries a floor. The second direction is what
  stops a flip freezing a proper subset of the durable formats and passing
  green while the frozen mapping reads as a complete inventory.

The whole mechanism is DORMANT today: the regime is ``PRE_RELEASE``,
``RELEASED_FORMAT_FLOORS`` is ``None``, the fixture corpus is empty, and every
assertion below is either the live pre-release truth or vacuously green.

Reads only the public ``cadrumo.core`` compatibility-lifecycle policy — never a
tier's private floor/version constants, which stay intra-package.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from importlib import metadata
from pathlib import Path
from typing import Final

import pytest

from ..core import (
    COMPATIBILITY_REGIME,
    PERSISTED_FORMATS,
    RELEASED_FORMAT_FLOORS,
    CompatibilityRegime,
    PersistedFormatClass,
    expected_floor,
    lineage_obligations,
    unfloored_durable_formats,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DISTRIBUTION_NAME: Final[str] = "cadrumo"

#: The persisted-format tiers a released floor key may name: the secure-object
#: substrate, the portable profile bundle, and the sealed archive. The
#: canonical key set the enrollment invariant validates against.
_CANONICAL_FORMAT_KEYS: Final[frozenset[str]] = frozenset(
    {"secure_object", "bundle", "archive"},
)

#: The current on-disk version of each released format, populated in the flip
#: commit alongside :data:`RELEASED_FORMAT_FLOORS` so the coverage harness can
#: range ``floor..current-1``. Empty while ``PRE_RELEASE`` (mirrors
#: ``RELEASED_FORMAT_FLOORS is None``); the loop that indexes it never runs
#: today, so no tier constant is imported across a package boundary here.
_RELEASED_FORMAT_CURRENT_VERSIONS: Final[Mapping[str, int]] = {}

#: Root of the committed cross-version fixture corpus. Empty today; the release
#: checkpoint and later post-floor version bumps add per-format subdirectories.
_FIXTURE_ROOT: Final[Path] = Path(__file__).resolve().parents[1] / "_data" / "compat_fixtures"


def _package_major_version() -> int:
    """Return the major component of this codebase's package version.

    Reads the installed distribution metadata, falling back to the committed
    ``pyproject.toml`` when the distribution is not installed (a source-only
    checkout). A compliance regime is a property of the codebase, so either
    source names the same version.
    """
    try:
        raw = metadata.version(_DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
        raw = str(tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"])
    return int(raw.split(".", 1)[0])


def test_pre_release_regime_keeps_the_package_below_the_one_point_zero_milestone() -> None:
    """The tripwire: a 1.0 cut must not happen while the regime is pre-release."""
    if COMPATIBILITY_REGIME is CompatibilityRegime.PRE_RELEASE:
        assert _package_major_version() < 1, (
            "package version has reached 1.0 while COMPATIBILITY_REGIME is still "
            "PRE_RELEASE: flip the regime to RELEASED and freeze RELEASED_FORMAT_FLOORS "
            "in the checkpoint commit before cutting the first release"
        )


def test_released_floors_are_populated_exactly_when_the_regime_is_released() -> None:
    """One-way coherence: the frozen floors and the regime constant move together."""
    assert (RELEASED_FORMAT_FLOORS is not None) == (COMPATIBILITY_REGIME is CompatibilityRegime.RELEASED)


def test_every_flip_time_constant_moves_together() -> None:
    """Coherence for the THIRD flip-time constant: current-versions track the floors.

    The flip commit must populate ``_RELEASED_FORMAT_CURRENT_VERSIONS`` (the range
    source for the coverage harness) in lock-step with ``RELEASED_FORMAT_FLOORS``.
    Binding their key sets here catches a flip that freezes floors but forgets the
    current-versions with an instructive failure, rather than the bare ``KeyError``
    the coverage loop would otherwise raise at the checkpoint. Vacuously green today
    (both empty), so it changes no behaviour pre-release.
    """
    assert set(_RELEASED_FORMAT_CURRENT_VERSIONS) == set(RELEASED_FORMAT_FLOORS or {}), (
        "the release-checkpoint flip must populate _RELEASED_FORMAT_CURRENT_VERSIONS "
        "with the same format keys as RELEASED_FORMAT_FLOORS, in the same commit"
    )


def test_every_released_floor_key_names_a_live_format_tier() -> None:
    """Enrollment: a populated floor mapping may only name real tiers.

    Vacuously green today (``RELEASED_FORMAT_FLOORS`` is ``None``).
    """
    floors = RELEASED_FORMAT_FLOORS or {}
    unknown = set(floors) - _CANONICAL_FORMAT_KEYS
    assert unknown == set(), (
        f"RELEASED_FORMAT_FLOORS names non-tier format keys {unknown}; every frozen "
        f"floor must map to a live persisted-format tier {sorted(_CANONICAL_FORMAT_KEYS)}"
    )


def test_every_durable_format_carries_a_frozen_floor() -> None:
    """Enrollment, the other direction: a durable format may not be left uncovered.

    The sibling gate above stops a frozen floor naming a format that is not a
    live tier. Nothing asserted the converse, so a checkpoint flip could freeze
    a proper SUBSET of the durable formats and pass every gate green — and the
    frozen mapping would then read to every later author as the complete
    inventory of what the product promises to keep reading.

    Vacuously green today (``RELEASED_FORMAT_FLOORS`` is ``None``); the
    predicate's teeth are proven directly below with synthetic mappings.
    """
    uncovered = unfloored_durable_formats(RELEASED_FORMAT_FLOORS, PERSISTED_FORMATS)
    assert uncovered == (), (
        f"persisted format(s) {uncovered} are declared DURABLE but carry no frozen floor. "
        "A durability guarantee that silently omits taxpayer bytes is worse than none, because "
        "the omission is invisible exactly where the guarantee is claimed. Either enroll each "
        "format (a floor constant, a version ceiling, an upgrader registry, and a tier gate) or "
        "reclassify it REGENERABLE in PERSISTED_FORMATS if its bytes are genuinely rebuildable — "
        "in the same commit that freezes the floors"
    )


@pytest.mark.parametrize(
    ("floors", "expected"),
    [
        # The exact shape the checkpoint would take today: the three canonical
        # tiers frozen, the two durable formats with no floor machinery omitted.
        (
            {"secure_object": 1, "bundle": 3, "archive": 3},
            ("bucket_dek", "bucket_manifest"),
        ),
        # One omission is still an omission.
        (
            {"secure_object": 1, "bundle": 3, "archive": 3, "bucket_manifest": 2},
            ("bucket_dek",),
        ),
        # Freezing only the substrate leaves every other durable format bare.
        (
            {"secure_object": 1},
            ("archive", "bucket_dek", "bucket_manifest", "bundle"),
        ),
    ],
)
def test_the_enrollment_predicate_names_every_uncovered_durable_format(
    floors: dict[str, int],
    expected: tuple[str, ...],
) -> None:
    """Non-vacuity: the live gate above is green only because nothing is frozen yet.

    Each case is a real mapping the flip commit could plausibly land, driven
    through the real predicate against the real declaration table. Without
    these the gate would pass just as happily if the predicate always returned
    an empty tuple.
    """
    assert unfloored_durable_formats(floors, PERSISTED_FORMATS) == expected


def test_the_enrollment_predicate_accepts_a_complete_freeze() -> None:
    """The other half of non-vacuity: the predicate is not simply always-failing.

    A mapping covering every durable format returns clean, so the parametrised
    rejections above are discriminating rather than vacuously strict.
    """
    complete = {key: 1 for key, value in PERSISTED_FORMATS.items() if value is PersistedFormatClass.DURABLE}
    assert unfloored_durable_formats(complete, PERSISTED_FORMATS) == ()


def test_a_regenerable_format_is_never_required_to_carry_a_floor() -> None:
    """Regenerable state is excluded by construction, not by an allowlist.

    A floor is a promise to keep reading old bytes; making it about a session
    or a throttle sidecar would be an obligation to honour shapes the
    application deliberately discards.
    """
    regenerable = sorted(key for key, value in PERSISTED_FORMATS.items() if value is PersistedFormatClass.REGENERABLE)
    assert regenerable, "the declaration table must carry regenerable formats for this to mean anything"
    durable_only = {key: 1 for key, value in PERSISTED_FORMATS.items() if value is PersistedFormatClass.DURABLE}
    assert unfloored_durable_formats(durable_only, PERSISTED_FORMATS) == ()


def test_fixture_corpus_root_exists() -> None:
    """The committed fixture harness is a real directory, empty today."""
    assert _FIXTURE_ROOT.is_dir(), (
        f"missing cross-version fixture corpus root {_FIXTURE_ROOT}; it ships now "
        "(empty) so the coverage harness has a real home before the release flip"
    )


def test_cross_version_fixtures_cover_every_supported_old_version() -> None:
    """Every released version below current carries a committed fixture.

    The corpus gate is a CONSUMER of the same policy predicates the tier floor
    gates use, never a second source of truth for the required range: the
    floor comes from :func:`expected_floor` (identical to the value the tier
    gate asserts against), and whether the missing coverage is a violation is
    decided by :func:`lineage_obligations` — so the corpus gate and the floor
    gates cannot drift apart.

    Vacuously green today: ``RELEASED_FORMAT_FLOORS`` is ``None``, so the loop
    body never runs and no old-shape fixture is required (or fabricated, which
    ``no-legacy-compatibility`` forbids). Post-flip, a version bump above a
    frozen floor without its captured old-version fixture fails here.
    """
    floors = RELEASED_FORMAT_FLOORS or {}
    for format_key in floors:
        current = _RELEASED_FORMAT_CURRENT_VERSIONS[format_key]
        floor = expected_floor(COMPATIBILITY_REGIME, format_key, current, RELEASED_FORMAT_FLOORS)
        has_fixture_coverage = all(
            (_FIXTURE_ROOT / format_key / str(version)).is_dir() for version in range(floor, current)
        )
        obligations = lineage_obligations(
            COMPATIBILITY_REGIME,
            format_key,
            current_version=current,
            floor=floor,
            released_floors=RELEASED_FORMAT_FLOORS,
            # Upgrader-chain completeness is the tier floor gate's axis; this
            # gate owns only the fixture-coverage obligation below.
            has_registered_upgraders_for_gap=True,
            has_fixture_coverage=has_fixture_coverage,
        )
        assert "missing_fixture_coverage" not in obligations, (
            f"released format {format_key!r} supports versions {floor}..{current - 1} but "
            f"ships no committed fixture for one of them under {_FIXTURE_ROOT / format_key}; "
            "capture the old-version fixture in the bump commit"
        )
