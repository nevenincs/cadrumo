"""Regime-switched compatibility-lifecycle policy for persisted formats.

Compatibility posture pulls apart across time. Pre-release, the posture is
delete-not-migrate: durability floors chase the current version, and there
is no read-tolerance of pre-current shapes. Post-release, struct
compatibility and multi-year persistence of a taxpayer's filed data become
MUSTs. This module owns the transition — WHEN the posture flips, WHAT
flips, and WHAT enforces it — as a DORMANT, regime-switched policy that is
a no-op today and activates on a one-line flip.

:data:`COMPATIBILITY_REGIME` is a one-way repo-committed constant. While it
is :attr:`CompatibilityRegime.PRE_RELEASE` the policy predicates are
behaviour-identical to the pre-release floors-chase-current posture — they
read no old shapes, migrate nothing, and tolerate nothing. The
:attr:`CompatibilityRegime.RELEASED` branch freezes each format's durability
floor at its released value and demands upgrader-chain completeness plus
cross-version fixture coverage for any version above the frozen floor.

The predicates are PURE: every fact they judge on is an explicit parameter,
so the ``RELEASED`` branch is proven correct by synthetic-input tests
without monkeypatching the enforcing gate.
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
    #: In the released regime, durability floors are frozen at their released values; older
    #: persisted shapes must remain readable through registered upgraders.
    RELEASED = "released"


#: The one-way compatibility regime of this codebase commit. Flipped to
#: :attr:`CompatibilityRegime.RELEASED` ONLY by a checkpoint commit that
#: also freezes :data:`RELEASED_FORMAT_FLOORS` at the then-current
#: per-format floors. There is no path back to ``PRE_RELEASE`` — release is
#: a one-way door.
COMPATIBILITY_REGIME: Final[CompatibilityRegime] = CompatibilityRegime.PRE_RELEASE

#: The per-format durability floors frozen at the release checkpoint, keyed
#: by format (``"secure_object"``, ``"bundle"``, ``"archive"``). ``None``
#: while :data:`COMPATIBILITY_REGIME` is ``PRE_RELEASE`` — populated ONLY in
#: the flip commit with the then-current floors, e.g.
#: ``{"secure_object": 1, "bundle": 3, "archive": 2}``. Once populated, each
#: floor is frozen: a version bump above it post-release requires a real
#: upgrader and old-shape fixture, not a floor raise.
RELEASED_FORMAT_FLOORS: Final[Mapping[str, int] | None] = None


class PersistedFormatClass(StrEnum):
    """How long one persisted format's bytes must stay readable.

    The durability obligations differ by KIND of persisted data, not by
    storage mechanism. A taxpayer's filed evidence must survive every
    future version of this application; the sidecar recording how many
    login attempts have failed must not, and promising to read a stale one
    forever would be a liability rather than a guarantee.
    """

    #: Taxpayer data. Its bytes must stay readable across versions: the
    #: format carries a durability floor, a per-hop upgrader registry, and
    #: (post-checkpoint) a committed old-version fixture. Losing the ability
    #: to read it destroys data no operator can reconstruct.
    DURABLE = "durable"
    #: Operational state the application regenerates on demand — a session,
    #: a throttle sidecar, a crash-recovery journal, a lock. Delete-and-
    #: refuse is the CORRECT policy in both regimes: a version mismatch
    #: discards the record and the next operation rebuilds it. These formats
    #: carry NO durability floor and MUST NOT appear in
    #: :data:`RELEASED_FORMAT_FLOORS`.
    REGENERABLE = "regenerable"


#: Every persisted format this application writes, and the durability class
#: it belongs to. This mapping is the CLOSED inventory the enrollment gate
#: enumerates against: a new persisted format that does not appear here
#: fails the gate rather than passing by omission. Adding a format here is
#: a deliberate durability decision, not bookkeeping.
PERSISTED_FORMATS: Final[Mapping[str, PersistedFormatClass]] = {
    # Durable — taxpayer data and the key material that unlocks it.
    "secure_object": PersistedFormatClass.DURABLE,
    "bundle": PersistedFormatClass.DURABLE,
    "archive": PersistedFormatClass.DURABLE,
    "bucket_dek": PersistedFormatClass.DURABLE,
    "bucket_manifest": PersistedFormatClass.DURABLE,
    # The secret-store index maps HMAC lookup digests to blob references. It
    # is DURABLE rather than regenerable: the digest is an HMAC of the natural
    # key, and while each stored record still carries that key, no rebuild
    # path exists to walk the blobs and re-derive the map. Losing the index
    # therefore strands every secret it addressed.
    "secret_index": PersistedFormatClass.DURABLE,
    # Regenerable — operational state, discarded and rebuilt on mismatch.
    "profile_session": PersistedFormatClass.REGENERABLE,
    "login_throttle": PersistedFormatClass.REGENERABLE,
    "config_reset_journal": PersistedFormatClass.REGENERABLE,
    "bucket_lock": PersistedFormatClass.REGENERABLE,
    "bucket_output_language_hint": PersistedFormatClass.REGENERABLE,
}


def undeclared_persisted_formats(
    discovered_keys: frozenset[str],
    declared: Mapping[str, PersistedFormatClass],
) -> tuple[str, ...]:
    """Return discovered persisted formats carrying no durability declaration.

    Pure, and deliberately ENUMERATING rather than allowlisting: the caller
    discovers the live format set from the storage registry, and any key it
    finds that is absent from ``declared`` is returned as a violation. A new
    persisted format therefore fails until someone decides whether its bytes
    are taxpayer data or regenerable state — the decision the durability
    obligations hang off.
    """
    return tuple(sorted(discovered_keys - set(declared)))


def stale_persisted_format_declarations(
    discovered_keys: frozenset[str],
    declared: Mapping[str, PersistedFormatClass],
) -> tuple[str, ...]:
    """Return declared formats no longer present in the discovered set.

    The converse of :func:`undeclared_persisted_formats`: a declaration left
    behind by a retired format is stale inventory, and a stale entry is what
    lets the next reader believe a coverage claim that nothing backs.
    """
    return tuple(sorted(set(declared) - discovered_keys))


def misclassified_floor_keys(
    released_floors: Mapping[str, int] | None,
    declared: Mapping[str, PersistedFormatClass],
) -> tuple[str, ...]:
    """Return frozen-floor keys that name a regenerable format.

    A durability floor is a promise to keep reading old bytes. Making that
    promise about a session or a throttle sidecar is not a stronger
    guarantee — it is an obligation to honour shapes the application is
    designed to discard, so the checkpoint flip must never freeze a floor
    for a :attr:`PersistedFormatClass.REGENERABLE` format.
    """
    floors = released_floors or {}
    return tuple(
        sorted(key for key in floors if declared.get(key) is PersistedFormatClass.REGENERABLE),
    )


def unknown_floor_keys(
    released_floors: Mapping[str, int] | None,
    declared: Mapping[str, PersistedFormatClass],
) -> tuple[str, ...]:
    """Return frozen-floor keys naming a format the inventory has never heard of.

    :func:`misclassified_floor_keys` catches a floor frozen for a format
    declared REGENERABLE. Neither it nor :func:`unfloored_durable_formats`
    catches a floor key that appears in ``declared`` at all — a typo, or a
    format retired from :data:`PERSISTED_FORMATS` while its floor stayed
    behind. Such a key promises durability for bytes no declaration governs,
    which is a claim with nothing on the other end of it.

    Together with its two siblings this closes the key-set relation in both
    directions: every floor key names a declared format, no floor key names a
    regenerable one, and every durable format carries a floor. That triple is
    what lets the enrollment gate derive its reference set from
    :data:`PERSISTED_FORMATS` instead of restating it as a hand-listed mirror
    that goes stale the moment the declaration grows.

    Returns an empty tuple while ``released_floors`` is ``None``: under
    ``PRE_RELEASE`` nothing is frozen, so no key can be unknown.
    """
    floors = released_floors or {}
    return tuple(sorted(set(floors) - set(declared)))


def unfloored_durable_formats(
    released_floors: Mapping[str, int] | None,
    declared: Mapping[str, PersistedFormatClass],
) -> tuple[str, ...]:
    """Return durable formats the frozen floors fail to cover.

    The converse of :func:`misclassified_floor_keys`, and the direction that
    was missing. That predicate stops a floor being frozen for bytes the
    application is designed to discard; this one stops taxpayer bytes being
    left out of the guarantee entirely.

    Without it a checkpoint flip can freeze a proper subset of the durable
    formats and pass every gate green, because nothing else asserts that a
    :attr:`PersistedFormatClass.DURABLE` declaration implies a floor. The
    frozen mapping then reads to every later author as the complete
    inventory of what the product promises to keep reading, while the
    formats absent from it silently carry no promise at all — the more
    dangerous failure, since the omission is invisible precisely where the
    guarantee is being claimed.

    Returns an empty tuple while ``released_floors`` is ``None``: under
    ``PRE_RELEASE`` nothing is frozen, so nothing is yet uncovered.
    """
    if released_floors is None:
        return ()
    return tuple(
        sorted(
            key
            for key, format_class in declared.items()
            if format_class is PersistedFormatClass.DURABLE and key not in released_floors
        ),
    )


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
    "PERSISTED_FORMATS",
    "RELEASED_FORMAT_FLOORS",
    "CompatibilityRegime",
    "PersistedFormatClass",
    "expected_floor",
    "lineage_obligations",
    "misclassified_floor_keys",
    "stale_persisted_format_declarations",
    "undeclared_persisted_formats",
    "unfloored_durable_formats",
    "unknown_floor_keys",
]
