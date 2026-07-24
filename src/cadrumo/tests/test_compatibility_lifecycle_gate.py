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
- **Enrollment.** Every key in a populated ``RELEASED_FORMAT_FLOORS`` names a
  live persisted-format tier.

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
    RELEASED_FORMAT_FLOORS,
    CompatibilityRegime,
    expected_floor,
    lineage_obligations,
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
