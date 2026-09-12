"""Forward migration rekeying persisted relation overrides onto binding ids.

A :class:`~domain.modelos.calculation_revision.CalculationRevision` persists
``relation_overrides`` keyed by the id of the relation the operator overrode,
and that mapping feeds the content-addressed revision id. Relations have since
been absorbed into the binding providers that replaced them, so the runtime
override channel is keyed by the TARGET BINDING id: an override still stored
under a retired relation id matches no binding, contributes nothing, and does so
without saying anything -- the operator's explicit figure silently stops
applying to a filing-bound value.

This module is the forward, deterministic, idempotent stored-data migration that
closes that gap. It rekeys every stored override through the frozen
relation-to-binding join shipped beside it
(:mod:`.relation_binding_join`), recomputes each affected revision id through
the canonical identity function so the content address still describes its
contents, and reports the old-to-new revision id pairs it produced.

Properties the migration holds, in the order they matter:

*Forward.* It reads the retired vocabulary and writes the current one. There is
no reverse hop and no dual-read: once a catalogue is migrated, the retired keys
are gone from storage.

*Deterministic.* The join is frozen product data and the id recomputation is the
same pure function the write path uses, so the same stored catalogue always
yields the same migrated catalogue and the same revision ids.

*Idempotent.* A key that is already a binding id the join resolves onto is left
exactly as it is, so a second run rekeys nothing, recomputes nothing, and
returns the catalogue unchanged. Re-running after a partial failure is safe
because the write is a single compare-and-swap of the whole singleton.

*Non-destructive under doubt.* A key that is neither a known relation id nor a
known binding id is REFUSED, loudly, naming the key. It is never dropped and
never guessed at: an unrecognised override key means either a corpus the frozen
join does not describe or a corrupted catalogue, and both are conditions an
operator must see rather than a zero a filing can quietly inherit.

The join is many-to-one, so two retired relation ids in one revision can fold
onto the same binding. That collapse is accepted only when both stored values
are identical; a genuine disagreement is refused for the same reason, since
picking a winner would discard an operator-entered figure.

Stored override VALUES are taxpayer figures and appear in no result field and no
log record here. The migration reports identifiers only.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ....core.logging import get_logger
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.errors import RegistryError
from ....domain.calculations.registry.ids import BindingId, RelationId
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_repository import CalculationRevisionPersistenceError
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    derive_calculation_revision_id_from_revision,
)
from .relation_binding_join import bundled_relation_binding_join, bundled_relation_binding_join_targets

if TYPE_CHECKING:  # pragma: no cover — the repository is a signature type only
    from .modelos_calculation import CalculationRevisionCatalogueRepository

_LOGGER = get_logger(__name__)
_MIGRATION_MESSAGE = "errors.fail.fail_modelo_calculation_revision_persistence"
_WRITE_PROVENANCE_REASON = "calculation-revision:relation-override-binding-rekey"

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class OrphanedRelationOverrideError(CalculationRevisionPersistenceError):
    """Raised when a stored override key resolves to neither a relation nor a binding.

    Carries the offending keys and the owning revision id so an operator can
    find the catalogue entry. It does NOT carry the override values: they are
    taxpayer figures, and an error context is one of the surfaces that ends up
    in a log.
    """


class CalculationRevisionIdRemap(BaseModel):
    """One revision's content address before and after its overrides were rekeyed."""

    model_config = _STRICT_FROZEN

    previous_calculation_revision_id: str = Field(min_length=1)
    calculation_revision_id: str = Field(min_length=1)
    work_unit_id: str = Field(min_length=1)


class RelationOverrideRekey(BaseModel):
    """One override key's move from its retired relation id onto its binding id."""

    model_config = _STRICT_FROZEN

    calculation_revision_id: str = Field(min_length=1)
    """The id the owning revision carried BEFORE the rekey, so the pair can be
    traced back to the catalogue entry the migration read."""
    relation_id: RelationId
    binding_id: BindingId


class CalculationRevisionOverrideMigrationResult(BaseModel):
    """What one migration run changed, reported as identifiers only.

    ``rekeyed_revisions`` is empty on an already-migrated catalogue, which is
    how a caller distinguishes a no-op re-run from a first run.
    """

    model_config = _STRICT_FROZEN

    catalogue: CalculationRevisionCatalogue
    rekeyed_revisions: tuple[CalculationRevisionIdRemap, ...] = ()
    rekeyed_override_keys: tuple[RelationOverrideRekey, ...] = ()
    unchanged_revision_ids: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        """Report whether this run rekeyed anything at all."""
        return bool(self.rekeyed_revisions)


@cache
def _declared_binding_ids_at(modelo: str, filing_year: int, period: str, revision_id: str) -> frozenset[BindingId]:
    """Return every binding id the revision at these coordinates declares.

    The coordinates are taken apart rather than passed as the typed ref because
    the memo key must be hashable by contract, not merely at runtime.

    The frozen join describes only the relations that existed BEFORE the cut, so
    it cannot know a binding authored after it. An override written against such
    a binding is already in the current vocabulary and must be carried through
    untouched; classifying it by the join alone would refuse it forever, and the
    operator's figure would be unreachable rather than merely stale.

    A snapshot the bundled authority cannot build leaves the declared set empty,
    which restores the join-only classification: that direction refuses rather
    than drops, so an unbuildable snapshot costs an operator an error, never a
    silently discarded override.
    """
    try:
        snapshot = bundled_authority().snapshot(
            modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        )
    except RegistryError:
        declared: tuple[BindingId, ...] = ()
    else:
        declared = tuple(binding.id for binding in snapshot.revision.bindings)
    return frozenset(declared)


def _declared_binding_ids(snapshot_ref: RegistrySnapshotRef) -> frozenset[BindingId]:
    """Return every binding id the revision named by *snapshot_ref* declares."""
    return _declared_binding_ids_at(
        str(snapshot_ref.modelo),
        int(snapshot_ref.modelo_year),
        str(snapshot_ref.period),
        str(snapshot_ref.revision_id),
    )


def _rekeyed_overrides_for_revision(
    revision: CalculationRevision,
    *,
    join: Mapping[RelationId, BindingId],
    join_targets: frozenset[BindingId],
) -> tuple[dict[BindingId, str], tuple[RelationOverrideRekey, ...]]:
    """Return one revision's binding-keyed overrides and the moves that produced them.

    Raises:
        OrphanedRelationOverrideError: A key is neither a retired relation id
            the frozen join knows, nor a binding id the join resolves onto, nor
            a binding the revision's own registry snapshot declares; or two
            retired keys fold onto one binding carrying different values.
    """
    current_binding_ids = join_targets | _declared_binding_ids(revision.registry_snapshot_ref)
    rekeyed: dict[BindingId, str] = {}
    moves: list[RelationOverrideRekey] = []
    orphans: list[str] = []
    collisions: list[str] = []
    for stored_key, stored_value in sorted(revision.relation_overrides.items()):
        binding_id = join.get(stored_key)
        if binding_id is None:
            if stored_key in current_binding_ids:
                # Already in the current vocabulary: a post-cut write, or this
                # revision on a second run. Left byte-identical so the run is a
                # no-op rather than a rewrite that would move the content address.
                binding_id = stored_key
            else:
                orphans.append(stored_key)
                continue
        else:
            moves.append(
                RelationOverrideRekey(
                    calculation_revision_id=revision.calculation_revision_id,
                    relation_id=stored_key,
                    binding_id=binding_id,
                ),
            )
        existing = rekeyed.get(binding_id)
        if existing is not None and existing != stored_value:
            collisions.append(binding_id)
            continue
        rekeyed[binding_id] = stored_value
    if orphans:
        raise OrphanedRelationOverrideError(
            "calculation revision carries override keys that are neither a known relation nor a known binding",
            translated_message=_MIGRATION_MESSAGE,
            context={
                "reason": "orphaned_relation_override",
                "calculation_revision_id": revision.calculation_revision_id,
                "override_keys": ", ".join(sorted(orphans)),
            },
        )
    if collisions:
        raise OrphanedRelationOverrideError(
            "calculation revision carries disagreeing overrides that fold onto one binding",
            translated_message=_MIGRATION_MESSAGE,
            context={
                "reason": "conflicting_relation_override_fold",
                "calculation_revision_id": revision.calculation_revision_id,
                "binding_ids": ", ".join(sorted(set(collisions))),
            },
        )
    return dict(sorted(rekeyed.items())), tuple(moves)


def rekey_calculation_revision_overrides(
    catalogue: CalculationRevisionCatalogue,
) -> CalculationRevisionOverrideMigrationResult:
    """Rekey every stored relation override onto its binding id, in memory.

    The pure half of the migration: no storage is touched, so this is the
    function tests and the repository-facing entry point share. A revision whose
    overrides are already binding-keyed -- including every revision with no
    overrides at all -- is carried through untouched and its content address is
    not recomputed, which is what makes a second run a no-op.

    Args:
        catalogue: The catalogue as read from storage.

    Returns:
        The migrated catalogue plus the identifier-only record of what moved.

    Raises:
        OrphanedRelationOverrideError: A stored override key could not be
            resolved, or two keys folded onto one binding with different values.
    """
    join = bundled_relation_binding_join()
    join_targets = bundled_relation_binding_join_targets()
    migrated: dict[str, CalculationRevision] = {}
    remaps: list[CalculationRevisionIdRemap] = []
    moves: list[RelationOverrideRekey] = []
    unchanged: list[str] = []
    for revision in sorted(catalogue.values(), key=lambda item: item.calculation_revision_id):
        rekeyed, revision_moves = _rekeyed_overrides_for_revision(
            revision,
            join=join,
            join_targets=join_targets,
        )
        if not revision_moves and rekeyed == dict(revision.relation_overrides):
            migrated[revision.calculation_revision_id] = revision
            unchanged.append(revision.calculation_revision_id)
            continue
        candidate = revision.model_copy(update={"relation_overrides": rekeyed})
        recomputed = derive_calculation_revision_id_from_revision(candidate)
        rekeyed_revision = candidate.model_copy(update={"calculation_revision_id": recomputed})
        # The content address is what makes a revision immutable, so it is
        # re-derived rather than carried: a recomputation that disagreed with
        # the model's own invariant would mean this migration changed an
        # identity axis it does not know about, and that must not reach storage.
        if derive_calculation_revision_id_from_revision(rekeyed_revision) != recomputed:
            raise CalculationRevisionPersistenceError(
                "rekeyed calculation revision does not reproduce its recomputed content address",
                translated_message=_MIGRATION_MESSAGE,
                context={
                    "reason": "revision_id_recomputation_unstable",
                    "calculation_revision_id": revision.calculation_revision_id,
                },
            )
        if recomputed in migrated:
            raise CalculationRevisionPersistenceError(
                "two calculation revisions collide on one content address after rekeying",
                translated_message=_MIGRATION_MESSAGE,
                context={
                    "reason": "rekeyed_revision_id_collision",
                    "calculation_revision_id": recomputed,
                },
            )
        migrated[recomputed] = rekeyed_revision
        remaps.append(
            CalculationRevisionIdRemap(
                previous_calculation_revision_id=revision.calculation_revision_id,
                calculation_revision_id=recomputed,
                work_unit_id=revision.work_unit_id,
            ),
        )
        moves.extend(revision_moves)
    return CalculationRevisionOverrideMigrationResult(
        catalogue=CalculationRevisionCatalogue(revisions=dict(sorted(migrated.items()))),
        rekeyed_revisions=tuple(remaps),
        rekeyed_override_keys=tuple(moves),
        unchanged_revision_ids=tuple(sorted(unchanged)),
    )


def migrate_stored_relation_overrides_to_binding_ids(
    repository: CalculationRevisionCatalogueRepository,
) -> CalculationRevisionOverrideMigrationResult:
    """Rekey one profile's stored overrides and persist the result atomically.

    The read is revision-guarded and the write is the singleton's own
    compare-and-swap, so a calculate run committing between the two makes this
    call fail rather than discard that run's revision. A failed run leaves the
    stored catalogue exactly as it was and can simply be re-run.

    An already-migrated catalogue is not written back at all: the migration is
    idempotent in storage as well as in memory, so re-running it does not churn
    the row's revision lineage.

    Args:
        repository: The bucket-bound calculation-revision catalogue repository.

    Returns:
        The identifier-only record of what moved, carrying the migrated
        catalogue.

    Raises:
        OrphanedRelationOverrideError: A stored override key could not be
            resolved to a binding.
    """
    catalogue, expected_revision_id = repository.load_revisioned()
    result = rekey_calculation_revision_overrides(catalogue)
    if not result.changed:
        return result
    repository.save_with_secure_object_writes(
        result.catalogue,
        (),
        expected_revision_id=expected_revision_id,
    )
    _LOGGER.info(
        "rekeyed persisted calculation-revision relation overrides onto binding ids",
        extra={
            "reason": _WRITE_PROVENANCE_REASON,
            "rekeyed_revision_count": len(result.rekeyed_revisions),
            "rekeyed_override_key_count": len(result.rekeyed_override_keys),
            "revision_id_pairs": [
                (remap.previous_calculation_revision_id, remap.calculation_revision_id)
                for remap in result.rekeyed_revisions
            ],
            "override_key_pairs": [(move.relation_id, move.binding_id) for move in result.rekeyed_override_keys],
        },
    )
    return result


__all__ = [
    "CalculationRevisionIdRemap",
    "CalculationRevisionOverrideMigrationResult",
    "OrphanedRelationOverrideError",
    "RelationOverrideRekey",
    "migrate_stored_relation_overrides_to_binding_ids",
    "rekey_calculation_revision_overrides",
]
