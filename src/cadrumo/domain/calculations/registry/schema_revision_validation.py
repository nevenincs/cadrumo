"""Cross-revision and storage-delta invariants the Modelo schema models enforce."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import TYPE_CHECKING

from .errors import RegistryValidationError
from .revision_contracts import DeclaredPredecessor

if TYPE_CHECKING:
    from .ids import RevisionId
    from .schema import ModeloRevision
    from .schema_verification import VerificationExpectationDefinition


def validate_selected_view_references(
    modelo_id: str,
    revisions: Mapping[RevisionId, ModeloRevision],
    revision_ids: frozenset[str],
) -> None:
    """Resolve a selected view's cross-revision identity references against its directory.

    Invariants that compare payloads of several revisions (predecessor date
    agreement and cycles, structural-succession lineage ownership) belong to
    complete-modelo validation, which the directory's source modelo passed.
    """
    foreign = sorted(set(revisions) - revision_ids)
    if foreign:
        raise RegistryValidationError(
            f"modelo {modelo_id!r} view revisions {foreign!r} are not revisions of its directory; "
            f"declared revisions are {sorted(revision_ids)!r}"
        )
    for revision in revisions.values():
        predecessor = revision.predecessor
        if isinstance(predecessor, DeclaredPredecessor) and predecessor.revision_id not in revision_ids:
            raise RegistryValidationError(
                f"modelo {modelo_id!r} revision {revision.id!r} declares predecessor {predecessor.revision_id!r}, "
                f"which is not a revision of this modelo; declared revisions are {sorted(revision_ids)!r}"
            )
        for relation in revision.casilla_structural_successions:
            if relation.to_revision != revision.id or relation.from_revision not in revision_ids:
                raise RegistryValidationError(
                    f"structural succession {modelo_id}/{revision.id}/{relation.id}: unknown endpoint revision; "
                    f"declared revisions are {sorted(revision_ids)!r}"
                )


def require_revision_family_storage_delta(revision: ModeloRevision) -> None:
    """Refuse a revision whose keyed-family storage delta is incoherent."""
    from .keyed_families import KEYED_FAMILY_SPECS

    keyed = {spec.section for spec in KEYED_FAMILY_SPECS}
    scoped = {spec.section for spec in KEYED_FAMILY_SPECS if spec.scoped}
    cleared = [item.family for item in revision.cleared_families]
    named = _named_storage_delta_families(revision, cleared)
    _require_known_storage_families(named, keyed)
    _require_storage_delta_baseline(revision, named)
    _require_unique_clearances_and_scopes(revision, cleared)
    operated = _operated_storage_delta_families(revision)
    _require_scoped_storage_operations(revision, scoped, operated)


def _named_storage_delta_families(revision: ModeloRevision, cleared: list[str]) -> list[str]:
    return [
        *cleared,
        *revision.scoped_families,
        *(item.family for item in revision.family_overrides),
        *(item.family for item in revision.family_removals),
        *(item.family for item in revision.family_positions),
    ]


def _operated_storage_delta_families(revision: ModeloRevision) -> set[str]:
    return {
        *(item.family for item in revision.family_overrides),
        *(item.family for item in revision.family_removals),
        *(item.family for item in revision.family_positions),
    }


def _require_known_storage_families(named: list[str], keyed: set[str]) -> None:
    unknown = sorted(set(named) - keyed)
    if unknown:
        raise RegistryValidationError(f"family storage delta names non-keyed families {unknown!r}")


def _require_storage_delta_baseline(revision: ModeloRevision, named: list[str]) -> None:
    if named and revision.family_storage_baseline is None and revision.predecessor is None:
        raise RegistryValidationError("family storage delta requires family_storage_baseline or a named predecessor")


def _require_unique_clearances_and_scopes(revision: ModeloRevision, cleared: list[str]) -> None:
    if len(set(cleared)) != len(cleared):
        raise RegistryValidationError(
            "cleared families must be unique; one family carries one authored clearance, so two entries "
            "leave the merge with two reasons for one decision and no rule for picking between them"
        )
    if len(set(revision.scoped_families)) != len(revision.scoped_families):
        raise RegistryValidationError("scoped families must be unique")


def _require_scoped_storage_operations(
    revision: ModeloRevision,
    scoped: set[str],
    operated: set[str],
) -> None:
    invalid_scopes = sorted(set(revision.scoped_families) - scoped)
    if invalid_scopes:
        raise RegistryValidationError(f"family assertion scope names non-scoped families {invalid_scopes!r}")
    missing_scopes = sorted((operated & scoped) - set(revision.scoped_families))
    if missing_scopes:
        raise RegistryValidationError(
            f"scoped family storage operations require an edition-local assertion scope {missing_scopes!r}"
        )


def require_revision_keys_and_review_references(
    revisions: Mapping[RevisionId, ModeloRevision],
    revision_ids: frozenset[str],
) -> None:
    """Refuse a revision filed under the wrong key or citing an unknown review reference."""
    for key, revision in revisions.items():
        _require_revision_key(key, revision)
        _require_review_reference(revision, revision_ids)


def _require_revision_key(key: RevisionId, revision: ModeloRevision) -> None:
    if key != revision.id:
        raise RegistryValidationError(f"revision key {key!r} does not match revision id {revision.id!r}")


def _require_review_reference(revision: ModeloRevision, revision_ids: frozenset[str]) -> None:
    if revision.reviewed_against == revision.id:
        raise RegistryValidationError(
            f"revision {revision.id!r} has invalid review reference: reviewed_against cannot name itself"
        )
    if revision.reviewed_against is not None and revision.reviewed_against not in revision_ids:
        raise RegistryValidationError(
            f"revision {revision.id!r} has dangling review reference "
            f"reviewed_against={revision.reviewed_against!r}; declared revisions are {sorted(revision_ids)!r}"
        )


def union_across_expectations[T](
    expectations: Sequence[VerificationExpectationDefinition],
    select: Callable[[VerificationExpectationDefinition], Iterable[T]],
) -> frozenset[T]:
    """Union one declared set across every expectation folded into a policy.

    The fold is a union rather than an intersection on purpose: an id any single
    expectation declares is in scope for the snapshot's policy, so a second
    expectation cannot narrow the first one's declared coverage away.
    """
    return frozenset(value for expectation in expectations for value in select(expectation))
