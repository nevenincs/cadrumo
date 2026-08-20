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


#: A nested shape earns its OWN entry in :data:`PERSISTED_FORMATS` -- rather
#: than being covered by its container's -- only when BOTH conditions below
#: hold. Proximity is not the test: "it lives inside an already-enrolled
#: container" has repeatedly misclassified real taxpayer records, because a
#: container's floor proves its own bytes decrypt or parse and says nothing
#: about whether the grammar living inside them can still be read.
#:
#: 1. INDEPENDENT GRAMMAR. The shape declares a version distinct from any
#:    enclosing container's or envelope's version, such that a reader needs
#:    THIS version -- not merely the container's -- to interpret the bytes.
#:    When two declarations turn out to state ONE format's version rather
#:    than two formats' (a domain-model default and a persistence-row
#:    default naming the same number), that is DUPLICATION, not a second
#:    format: collapse to the declaration actually exercised on the live
#:    write path -- never to whichever side an a-priori layering preference
#:    names, because the layering preference has lost against evidence every
#:    time it was tested here.
#: 2. DURABLE READBACK. The shape's OWN bytes -- not a digest, a boolean, or
#:    any other derivative of them -- are themselves written to persistent
#:    storage and meant to be parsed back through that grammar by a real
#:    read path, or they are the sole surviving evidence of a fact nothing
#:    can reconstruct. A shape that lives only in-process and folds a digest
#:    into some OTHER persisted structure, discarding its own instance, has
#:    nothing on disk whose readability this inventory must guarantee --
#:    only the container holding the digest is a format, and the digest
#:    algorithm's own stability is a different concern from this one. A
#:    shape that clears this bar by being durably written, but is ALWAYS
#:    recomputed fresh from an already-durable authoritative source rather
#:    than trusted on read, still enrols -- format-hood is not defeated by
#:    being a cache -- but that same fact argues for classing it
#:    :attr:`PersistedFormatClass.REGENERABLE` rather than
#:    :attr:`PersistedFormatClass.DURABLE`.
#:
#: Both conditions must hold to enrol as a distinct entry. Failing (1) alone
#: does not exclude a shape that is nonetheless durably read back under its
#: own grammar -- it enrols, argued on (2). Failing (2) means there is no
#: format to enrol at all, independent of how (1) resolves.


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
    # ``bucket_dek`` and ``bucket_manifest`` were de-enrolled here as a
    # deliberate durability decision, not as bookkeeping: neither format has any
    # remaining implementation in the tree. The plaintext per-bucket manifest is
    # retired -- nothing reads or writes one, and profile discovery, labels and
    # key material all belong to the custody capsule. The separately wrapped
    # bucket data key is retired with it; the capsule's own password-wrapped DEK
    # is a different format under different custody, not this one renamed.
    #
    # Removing an entry is the same class of decision as adding one, so it is
    # recorded rather than left to inference. Note that this inventory is
    # enumerated only by the FLOOR gate, which validates released floors against
    # these keys and never validates these keys against the tree -- so an entry
    # outliving its implementation is invisible here, which is how the data-key
    # entry outlived its own deletion.
    #
    # The three profile-capsule file formats are enrolled below. They were
    # absent while the retired manifest was present -- the artefact being
    # removed was governed and the artefact replacing it was not -- and the
    # blindness noted above is why: nothing enumerates the tree against this
    # inventory, so a format that never appears here never fails anything.
    # Each carries its own schema-version constant, and each class is argued
    # rather than inherited from its neighbours.
    #
    # The capsule's custody and data CATEGORIES are deliberately not here: both
    # are directories rather than file formats, so they carry no bytes to keep
    # readable. What they contain is enrolled under its own keys.
    #
    # Unreadable, no password unwraps the bucket's data key ever again, and
    # every encrypted record under it is lost. This is the obligation the
    # retired ``bucket_dek`` entry used to carry, now under different custody.
    "profile_capsule_password_envelope": PersistedFormatClass.DURABLE,
    # The SOLE discovery proof for a capsule: recognition reads this marker and
    # nothing else, and returns "no such profile" when it will not parse. There
    # is no rebuild path, and its self-digest is not something an operator can
    # reconstruct by hand -- so losing readability does not corrupt the profile,
    # it makes the profile cease to exist while its bytes sit on disk.
    "profile_capsule_commit": PersistedFormatClass.DURABLE,
    # NOT regenerable, which is the whole test: the application cannot re-derive
    # recovery material on demand the way it rebuilds a session or a throttle.
    # Its readability is load-bearing exactly in the case it exists for -- a
    # forgotten password -- where failing to read it turns a recoverable profile
    # into total loss. Optional to CREATE is not the same as discardable once
    # created.
    "profile_capsule_recovery_envelope": PersistedFormatClass.DURABLE,
    # The capsule ARCHIVE's payload grammar, distinct from the archive container
    # it travels in: the container's version proves the file's framing parses, and
    # this one decides whether the password envelope, sentinel and recovery slot
    # inside it can still be located. The read path refuses outright on a version
    # it does not recognise, so an unreadable payload is not a degraded restore --
    # it is a backup that no longer restores anything, which is the one job an
    # exported capsule archive exists to do.
    "profile_capsule_archive_payload": PersistedFormatClass.DURABLE,
    # The encrypted profile record: the taxpayer's own facts. Its version is a
    # SEPARATE durability axis from the secure object that carries it -- the
    # envelope governs how the bytes decrypt, this governs whether the record
    # inside them can still be read and its lineage authenticated. A frozen
    # floor on the container does not cover the grammar within it, so an
    # unreadable record is unreadable however sound the envelope is. It has
    # already been bumped once, so that axis has been moving unobserved on the
    # most sensitive data the product holds.
    "profile_record": PersistedFormatClass.DURABLE,
    # The per-bucket SQLite file holding the encrypted secure_objects table --
    # every filing, ledger entry, and evidence record a taxpayer has. The rows
    # inside are already DURABLE under "secure_object"; the file that carries
    # them is the same durability obligation at the container level.
    "bucket_database_file": PersistedFormatClass.DURABLE,
    # These transition batches carry authoritative lifecycle and effect facts
    # after real external actions; they cannot be regenerated safely.
    "operation_journal": PersistedFormatClass.DURABLE,
    # The secret-store index maps HMAC lookup digests to blob references. It
    # is DURABLE rather than regenerable: the digest is an HMAC of the natural
    # key, and while each stored record still carries that key, no rebuild
    # path exists to walk the blobs and re-derive the map. Losing the index
    # therefore strands every secret it addressed.
    "secret_index": PersistedFormatClass.DURABLE,
    # Regenerable — operational state, discarded and rebuilt on mismatch.
    "profile_session": PersistedFormatClass.REGENERABLE,
    # The crash-window journal for one interrupted session-key swap, and the
    # entry most exposed to being classed by its neighbours: every capsule format
    # beside it is DURABLE, and it is not. Its private constant name is a Python
    # visibility fact, not a fact about the bytes -- it is written to the
    # operator's disk under the keystore sidecar, survives process exit, is
    # parsed back through its own strict grammar on the recovery path, and
    # refuses a foreign version. What it uniquely records is the INTENT of a swap
    # the process died in the middle of, so an unreadable one strands one OS
    # keychain secret and blocks the recovery that would have revoked it. That is
    # a hygiene cost, not lost taxpayer bytes. Acting on a half-understood one is
    # the real hazard: the journal names which of two session keys to revoke, and
    # a doubtful reading could revoke the LIVE one. Delete-and-refuse is the
    # correct response, which is what this class means.
    "profile_session_retirement_journal": PersistedFormatClass.REGENERABLE,
    "login_throttle": PersistedFormatClass.REGENERABLE,
    "config_reset_journal": PersistedFormatClass.REGENERABLE,
    "bucket_lock": PersistedFormatClass.REGENERABLE,
    "bucket_output_language_hint": PersistedFormatClass.REGENERABLE,
    # The cold-start database URL before any profile bucket exists. Every
    # profile-bound write refuses this route
    # (StorageRouteKind.ROOT_FALLBACK_DATABASE), so no taxpayer content ever
    # lands here -- it is a placeholder nothing real writes through, and
    # delete-and-refuse costs nothing.
    "root_fallback_database": PersistedFormatClass.REGENERABLE,
    # A run trace, its event log, and its captured envelope are diagnostic and
    # replay tooling, not filing evidence: the RUNS category itself is
    # RETENTION lifecycle and fingerprint-EXCLUDED because per-run churn is
    # the point. Losing one means a stale run cannot be replayed for
    # debugging; it never strands taxpayer data.
    "run_trace": PersistedFormatClass.REGENERABLE,
    "run_events": PersistedFormatClass.REGENERABLE,
    "run_envelope": PersistedFormatClass.REGENERABLE,
    # Diagnostic accounting (LLM usage/telemetry) and evictable caches (the
    # response cache, the registry-verdict skip-validation proof) -- none of
    # them taxpayer filing evidence. The two logical/display-only entries
    # (usage, run-telemetry) never materialise a file at all; the cache entry
    # is likewise SQL-backed. The lock file and the verdict cache file ARE
    # real writes, both freely deleted and regenerated.
    "llm_usage_record": PersistedFormatClass.REGENERABLE,
    "llm_run_telemetry_record": PersistedFormatClass.REGENERABLE,
    "auth_acquisition_lock": PersistedFormatClass.REGENERABLE,
    "validation_verdict_cache_entry": PersistedFormatClass.REGENERABLE,
    "llm_cache_entry": PersistedFormatClass.REGENERABLE,
    # REGENERABLE on the strength of its own contract rather than by default:
    # the transaction-to-revision index is a derived read-side cache, rebuilt
    # from the finalized revision catalogue, and the ledger rule requires
    # lifecycle correctness to rely on that live scan rather than on this
    # index's freshness. Delete-and-rebuild is therefore the CORRECT response
    # to a version mismatch, which is exactly what the class means -- and it is
    # the one format here whose class is a finding rather than a formality.
    "participation_index": PersistedFormatClass.REGENERABLE,
    # The active-profile pointer. Classed on which response to an unreadable
    # one is CORRECT, not on how easily an operator clicks again: a pointer we
    # cannot fully read must be discarded, because tolerating a doubtful one
    # routes the next operation at the wrong taxpayer's bucket. Read-tolerance
    # is the hazard here, and REGENERABLE is the class whose contract is
    # delete-and-refuse.
    #
    # It is worth being explicit that this does NOT rest on "the operator can
    # re-select": recoverable by the operator is not regenerable by the
    # application, and the application genuinely cannot derive this fact --
    # resolution has exactly two rungs, an in-process override and this file,
    # and the pointer exists precisely because the answer cannot be read out of
    # encrypted state without already knowing it. The class is right for a
    # different reason than the easy one.
    "active_profile_pointer": PersistedFormatClass.REGENERABLE,
    # The three AEAT authority-session records, each argued rather than classed
    # as a block -- they sit inside one encrypted container and share a shape,
    # which is exactly the proximity that assigns a wrong class.
    #
    # Certificate session metadata: binds a captured browser storage state to a
    # storage-state fingerprint, idle deadline, certificate thumbprint and
    # subject, all of which exist to be REVALIDATED before a resume. Unreadable,
    # the resume cannot be validated, and resuming unvalidated is the thing the
    # record exists to prevent. Re-authentication reconstructs every field.
    "aeat_certificate_session_metadata": PersistedFormatClass.REGENERABLE,
    # Cl@ve Movil: the same binding for a human-in-the-loop flow, and the one
    # whose re-establishment costs the operator most -- a phone and a fresh
    # verification code. Cost of redoing it is not the test; whether the
    # application should read a doubtful one is, and it must not.
    "aeat_clave_movil_session_metadata": PersistedFormatClass.REGENERABLE,
    # Cl@ve Permanente: the same binding for the headless credential flow.
    # Nothing here is unreconstructable -- identity, landing URL and deadline
    # are all observed again on the next login.
    "aeat_clave_permanente_session_metadata": PersistedFormatClass.REGENERABLE,
    # The two plaintext hold-owner snapshots the deletion preflight reads without
    # the bucket key, and the derived evidence recomputed from them. All three
    # gate a DESTRUCTIVE operation, and that is what decides the class rather
    # than how hard each is to re-record: absence and unreadability both produce
    # the same refusal, so discarding a doubtful one blocks an erase, while
    # tolerating one that half-parses can report zero open cases or zero retained
    # filings and permit the erase the record exists to prevent.
    #
    # Filing retention is additionally a projection of the encrypted modelo
    # catalogue, itself DURABLE under "secure_object" -- the participation-index
    # shape, rebuilt by profile creation and filing persistence.
    "profile_filing_retention_snapshot": PersistedFormatClass.REGENERABLE,
    # Legal hold is NOT a cache: nothing in the tree derives the open case
    # identifiers, which arrive from a legal matter outside the application. It
    # is classed here on the refusal argument alone, not on rebuildability.
    "profile_legal_hold_snapshot": PersistedFormatClass.REGENERABLE,
    # The derived evidence the deletion preflight assembles from the two
    # snapshots above. It clears the nested-format boundary test in the loose
    # sense -- its own `schema_version` is independent and its own bytes are
    # durably written to a per-owner file -- but fails the stricter half that
    # would argue DURABLE: nothing in the tree ever loads this file back
    # through its typed grammar. Its owning `refresh()` unconditionally
    # recomputes the evidence from the already-durable legal-hold and
    # filing-retention snapshots and overwrites the file on every call, which
    # is the participation-index shape exactly -- a derived read-side artefact
    # for which delete-and-rebuild is the correct response to an unreadable
    # version, not a promise to keep reading old bytes nothing consults again.
    "profile_custody_hold_evidence": PersistedFormatClass.REGENERABLE,
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
