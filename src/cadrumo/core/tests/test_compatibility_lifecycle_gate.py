"""Central repo-wide gate for the compatibility-lifecycle governance.

The per-tier lineage gates own each persisted format's floor-vs-current
assertion intra-package; this gate owns the three cross-cutting invariants
that bind the regime itself.

- **Version-milestone tripwire.** While ``COMPATIBILITY_REGIME`` is
  ``PRE_RELEASE`` the package version must stay below ``1.0.0``. This catches
  a 1.0 cut made without consciously flipping the regime — the safety net
  kept behind the primary constant-owned decision.
- **One-way coherence.** ``RELEASED_FORMAT_FLOORS`` is populated if and only
  if the regime is ``RELEASED``. The frozen floors and the regime constant
  can never drift apart.
- **Enrollment, both directions.** Every key in a populated
  ``RELEASED_FORMAT_FLOORS`` names a declared, non-regenerable persisted
  format, AND every format declared ``DURABLE`` carries a floor. The second
  direction is what stops a flip freezing a proper subset of the durable
  formats and passing green while the frozen mapping reads as a complete
  inventory. Both directions read the ONE declaration in
  :data:`PERSISTED_FORMATS` through the core predicates; neither restates the
  key set. A hand-listed mirror here previously went stale against that
  declaration and made the two directions contradict each other, so that no
  flip mapping could satisfy both — latent, because both were vacuously green.

The whole mechanism is DORMANT today: the regime is ``PRE_RELEASE``,
``RELEASED_FORMAT_FLOORS`` is ``None``, and every assertion below is either
the live pre-release truth or vacuously green.

Reads only the public ``cadrumo.core`` compatibility-lifecycle policy — never a
tier's private floor/version constants, which stay intra-package.
"""

from __future__ import annotations

import tomllib
from importlib import metadata
from pathlib import Path
from typing import Final

import pytest

from ..compatibility_lifecycle import (
    COMPATIBILITY_REGIME,
    PERSISTED_FORMATS,
    PersistedFormatClass,
    RELEASED_FORMAT_FLOORS,
)
from ..compatibility_lifecycle import (
    CompatibilityRegime,
    misclassified_floor_keys,
    unfloored_durable_formats,
    unknown_floor_keys,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DISTRIBUTION_NAME: Final[str] = "cadrumo"


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
        pyproject = Path(__file__).resolve().parents[4] / "pyproject.toml"
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


def test_every_released_floor_key_names_a_live_format_tier() -> None:
    """Enrollment: a populated floor mapping may only name real, durable tiers.

    The reference set is DERIVED from :data:`PERSISTED_FORMATS` through the
    core predicates rather than restated here. It used to be a hand-listed
    mirror of three keys, and the mirror went stale the moment the declaration
    grew to five: the sibling gate below requires every DURABLE format to carry
    a floor, so with ``bucket_dek`` and ``bucket_manifest`` declared durable but
    absent from the hand-list, enrolling them failed THIS gate while omitting
    them failed that one. No flip mapping could satisfy both. Both were
    vacuously green, so the contradiction was latent rather than red. (Both
    formats have since been de-enrolled, their implementations having been
    retired; the deadlock they caused is the reason this set is derived.)

    Deriving makes that deadlock unrepresentable rather than merely resolved:
    the two gates now read one declaration, so widening the inventory cannot
    put them out of step again.

    Vacuously green today (``RELEASED_FORMAT_FLOORS`` is ``None``); the
    predicates' teeth are proven directly below with synthetic mappings.
    """
    unknown = unknown_floor_keys(RELEASED_FORMAT_FLOORS, PERSISTED_FORMATS)
    assert unknown == (), (
        f"RELEASED_FORMAT_FLOORS names format key(s) {unknown} that no PERSISTED_FORMATS "
        "declaration governs. A floor is a promise to keep reading bytes; a key naming no "
        "declared format promises durability with nothing on the other end of it. Declare "
        "the format in PERSISTED_FORMATS, or drop the floor key"
    )
    misclassified = misclassified_floor_keys(RELEASED_FORMAT_FLOORS, PERSISTED_FORMATS)
    assert misclassified == (), (
        f"RELEASED_FORMAT_FLOORS freezes a floor for REGENERABLE format(s) {misclassified}. "
        "A durability floor for state the application is designed to discard is not a "
        "stronger guarantee, it is an obligation to honour shapes nothing needs to keep. "
        "Drop the floor key, or reclassify the format DURABLE if its bytes are taxpayer data"
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
        # tiers frozen, every other durable format left bare.
        #
        # These expectations are hand-listed ON PURPOSE. Deriving them from
        # PERSISTED_FORMATS would compute the answer the same way the function
        # under test does, so every case would pass by construction. The cost is
        # that they go stale whenever the inventory changes -- which is the
        # price of an independent expectation, not a defect in it.
        (
            {"secure_object": 1, "bundle": 3, "archive": 3},
            (
                "bucket_database_file",
                "operation_journal",
                "profile_capsule_archive_payload",
                "profile_capsule_commit",
                "profile_capsule_password_envelope",
                "profile_capsule_recovery_envelope",
                "profile_record",
                "secret_index",
            ),
        ),
        # One omission is still an omission.
        (
            {"secure_object": 1, "bundle": 3, "archive": 3, "secret_index": 2},
            (
                "bucket_database_file",
                "operation_journal",
                "profile_capsule_archive_payload",
                "profile_capsule_commit",
                "profile_capsule_password_envelope",
                "profile_capsule_recovery_envelope",
                "profile_record",
            ),
        ),
        # Freezing only the substrate leaves every other durable format bare.
        (
            {"secure_object": 1},
            (
                "archive",
                "bucket_database_file",
                "bundle",
                "operation_journal",
                "profile_capsule_archive_payload",
                "profile_capsule_commit",
                "profile_capsule_password_envelope",
                "profile_capsule_recovery_envelope",
                "profile_record",
                "secret_index",
            ),
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


@pytest.mark.parametrize(
    ("floors", "expected"),
    [
        # A typo'd key promises durability for bytes no declaration governs.
        ({"secure_object": 1, "bucket_manifets": 2}, ("bucket_manifets",)),
        # A floor left behind by a format retired from the declaration table.
        ({"secure_object": 1, "retired_format": 4}, ("retired_format",)),
        # Reported sorted, and independently of the regenerable check.
        ({"zzz_unknown": 1, "aaa_unknown": 2}, ("aaa_unknown", "zzz_unknown")),
    ],
)
def test_the_unknown_key_predicate_names_every_undeclared_floor_key(
    floors: dict[str, int],
    expected: tuple[str, ...],
) -> None:
    """Non-vacuity: the live gate is green only because nothing is frozen yet.

    Driven through the real predicate against the real declaration table.
    Without these the gate would pass just as happily if the predicate always
    returned an empty tuple — which is the failure mode that let a hand-listed
    reference set go stale here unnoticed in the first place.
    """
    assert unknown_floor_keys(floors, PERSISTED_FORMATS) == expected


def test_the_unknown_key_predicate_accepts_the_complete_durable_freeze() -> None:
    """The other half of non-vacuity, and the deadlock proof.

    The exact mapping the flip must land — every DURABLE format, derived from
    the declaration — passes BOTH enrollment directions at once. Under the
    superseded hand-listed reference set this mapping was impossible: it failed
    the unknown-key direction on ``bucket_dek`` and ``bucket_manifest`` while
    any mapping omitting them failed the uncovered-durable direction. That no
    mapping could satisfy both is the contradiction this asserts is gone.
    """
    complete = {key: 1 for key, value in PERSISTED_FORMATS.items() if value is PersistedFormatClass.DURABLE}
    assert len(complete) >= 4, (
        f"expected the durable inventory to exceed the retired hand-list of three; got {complete}"
    )
    assert unknown_floor_keys(complete, PERSISTED_FORMATS) == ()
    assert misclassified_floor_keys(complete, PERSISTED_FORMATS) == ()
    assert unfloored_durable_formats(complete, PERSISTED_FORMATS) == ()


def test_a_regenerable_floor_key_is_declared_but_still_refused() -> None:
    """The two floor-key directions are distinct checks, not one restated.

    A regenerable format IS declared, so the unknown-key predicate passes it;
    only the misclassification predicate refuses it. Asserting both here stops
    a later simplification collapsing them into one and silently dropping a
    direction.
    """
    regenerable = sorted(key for key, value in PERSISTED_FORMATS.items() if value is PersistedFormatClass.REGENERABLE)
    assert regenerable, "the declaration table must carry regenerable formats for this to mean anything"
    floors = {"secure_object": 1, regenerable[0]: 1}
    assert unknown_floor_keys(floors, PERSISTED_FORMATS) == ()
    assert misclassified_floor_keys(floors, PERSISTED_FORMATS) == (regenerable[0],)
