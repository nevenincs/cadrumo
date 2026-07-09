"""Regime-switched compatibility-lifecycle policy for persisted formats.

Two operator directives pull apart across time. Pre-release, the
``no-legacy-compatibility`` rule stands unchanged: delete-not-migrate,
durability floors chase the current version, no read-tolerance of
pre-current shapes. Post-release, struct compatibility and multi-year
persistence of a taxpayer's filed data become MUSTs. This module owns the
transition the durability substrate left ungoverned — WHEN the posture
flips, WHAT flips, and WHAT enforces it — as a DORMANT, regime-switched
policy that is a no-op today and activates on a one-line, ADR-gated flip.

:data:`COMPATIBILITY_REGIME` is a one-way repo-committed constant. While it
is :attr:`CompatibilityRegime.PRE_RELEASE` the policy predicates are
behaviour-identical to the pre-release floors-chase-current posture — they
read no old shapes, migrate nothing, and tolerate nothing. The
:attr:`CompatibilityRegime.RELEASED` branch freezes each format's durability
floor at its released value and demands upgrader-chain completeness plus
cross-version fixture coverage for any version above the frozen floor.

The predicates are PURE: every fact they judge on is an explicit parameter,
so the ``RELEASED`` branch is proven correct by synthetic-input tests
without monkeypatching the enforcing gate — the no-patching constraint the
``2026-07-08-released-data-durability-adr`` set for its lineage gates.

Governing vault record
    ``2026-07-09-compatibility-lifecycle-adr`` (regime-switched dormant
    durability governance), building on
    ``2026-07-08-released-data-durability-adr`` (the per-format mechanism).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Final


class CompatibilityRegime(StrEnum):
    """The codebase's compatibility posture at a point in its lifecycle.

    A property of the committed source, never of the runtime environment: it
    is deliberately NOT a setting, env var, or on-disk marker, so a
    compliance regime cannot vary per machine, be silently unset in CI, or
    be monkeypatched inside its own enforcing gate.
    """

    #: Pre-release: delete-not-migrate, floors chase current, no
    #: read-tolerance of pre-current shapes. The regime today.
    PRE_RELEASE = "pre_release"
    #: Released: durability floors frozen at their released values, older
    #: persisted shapes must remain readable through registered upgraders.
    RELEASED = "released"


#: The one-way compatibility regime of this codebase commit. Flipped to
#: :attr:`CompatibilityRegime.RELEASED` ONLY by an accepted checkpoint ADR
#: whose flip commit also freezes :data:`RELEASED_FORMAT_FLOORS` at the
#: then-current per-format floors. There is no path back to
#: ``PRE_RELEASE`` — release is a one-way door.
COMPATIBILITY_REGIME: Final[CompatibilityRegime] = CompatibilityRegime.PRE_RELEASE

#: The per-format durability floors frozen at the release checkpoint, keyed
#: by format (``"secure_object"``, ``"bundle"``, ``"archive"``). ``None``
#: while :data:`COMPATIBILITY_REGIME` is ``PRE_RELEASE`` — populated ONLY in
#: the flip commit with the then-current floors, e.g.
#: ``{"secure_object": 1, "bundle": 3, "archive": 2}``. Once populated, each
#: floor is frozen: a version bump above it post-release requires a real
#: upgrader and old-shape fixture, not a floor raise.
RELEASED_FORMAT_FLOORS: Final[Mapping[str, int] | None] = None


def expected_floor(
    regime: CompatibilityRegime,
    format_key: str,
    current_version: int,
    released_floors: Mapping[str, int] | None,
) -> int:
    """Return the durability floor a format's lineage gate must assert.

    Pure: judges only on its explicit parameters. Under
    ``PRE_RELEASE`` the floor chases the current version (older shapes are
    deleted, never migrated), so the expected floor IS ``current_version``.
    Under ``RELEASED`` the floor is frozen at the released value recorded in
    ``released_floors`` and no longer tracks the current version.

    Raises:
        ValueError: When ``regime`` is ``RELEASED`` but ``released_floors``
            is ``None`` — an incoherent state the coherence gate also
            rejects, guarded here so the predicate never indexes ``None``.
        KeyError: When ``released_floors`` has no entry for ``format_key``
            under ``RELEASED`` — a format enrolled in a tier gate but absent
            from the frozen floors, which the enrollment gate rejects.
    """
    if regime is CompatibilityRegime.PRE_RELEASE:
        return current_version
    if released_floors is None:
        raise ValueError(
            "RELEASED regime requires a frozen RELEASED_FORMAT_FLOORS mapping",
        )
    return released_floors[format_key]


def lineage_obligations(
    regime: CompatibilityRegime,
    format_key: str,
    current_version: int,
    floor: int,
    released_floors: Mapping[str, int] | None,
    has_registered_upgraders_for_gap: bool,
    has_fixture_coverage: bool,
) -> tuple[str, ...]:
    """Return the violated compatibility obligations for one format.

    Pure: every fact is an explicit parameter, so the ``RELEASED`` branch is
    exercisable with synthetic inputs. An empty tuple means the format
    satisfies every obligation for the given regime.

    Under ``PRE_RELEASE`` there is one obligation: the floor may not exceed
    the current version (a floor above current is incoherent — there is no
    version to read). A normal floor-raise (floor == current) is clean.

    Under ``RELEASED`` three obligations bind: the floor MUST stay frozen at
    the released value (``floor == released_floors[format_key]``); and when
    the current version is above the frozen floor, the per-hop upgrader chain
    across the gap MUST be complete and cross-version fixture coverage MUST
    exist. A post-flip version bump without an upgrader or an old-shape
    fixture is a violation.
    """
    violations: list[str] = []
    if regime is CompatibilityRegime.PRE_RELEASE:
        if floor > current_version:
            violations.append("floor_exceeds_current")
        return tuple(violations)

    frozen = expected_floor(regime, format_key, current_version, released_floors)
    if floor != frozen:
        violations.append("floor_not_frozen")
    if current_version > floor:
        if not has_registered_upgraders_for_gap:
            violations.append("missing_upgraders")
        if not has_fixture_coverage:
            violations.append("missing_fixture_coverage")
    return tuple(violations)


__all__ = [
    "COMPATIBILITY_REGIME",
    "RELEASED_FORMAT_FLOORS",
    "CompatibilityRegime",
    "expected_floor",
    "lineage_obligations",
]
