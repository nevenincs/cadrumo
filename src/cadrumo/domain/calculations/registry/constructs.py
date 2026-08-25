"""Construct resolution for registry revisions.

Resolves named construct groups declared on a :class:`ModeloRevision` into
typed ``ResolvedConstruct`` records that list every member (casilla, formula,
binding, etc.) with its id and value.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .errors import RegistrySnapshotError
from .modelo_localization import resolve_modelo_localization
from .schema import ModeloRevision
from .schema_base import LegalRefs, RegistryModel, SourceRefs


@dataclass(frozen=True, slots=True)
class ResolvedConstructMember:
    """One member resolved from a registry construct group.

    A construct group bundles heterogeneous registry entities (casillas,
    formulas, parameters, bindings, etc.) under a common id. Each member
    records the entity ``kind`` (e.g. ``"casilla"``, ``"formula"``), its
    registry ``id`` string, and the fully-typed ``value`` object retrieved
    from the revision index.
    """

    kind: str
    id: str
    value: object


class ResolvedConstruct(RegistryModel):
    """A fully-resolved registry construct group for one ``ModeloRevision``.

    A construct is a named thematic bundle declared in the registry TOML that
    groups related revision entities (casillas, formulas, bindings, etc.) so
    that consumers can iterate over them without knowing the full revision
    schema. After resolution every member carries its typed value object, not
    just its id string.

    ``legal_refs`` and ``source_refs`` carry the provenance declared on the
    construct entry in the TOML tree; they are propagated unchanged from the
    ``ModeloRevision`` construct record.
    """

    id: str
    localization_key: str
    legal_refs: LegalRefs
    source_refs: SourceRefs
    members: tuple[ResolvedConstructMember, ...]

    def get_title(self, locale: str) -> str:
        """Resolve the construct title from the shared catalogue."""
        resolved = resolve_modelo_localization((self.localization_key,), locale=locale, required=True)
        assert resolved is not None
        return resolved

    @property
    def title(self) -> str:
        """Return the strict official-Spanish construct title."""
        return self.get_title("es")

    def members_of_kind(self, kind: str) -> tuple[ResolvedConstructMember, ...]:
        """Return every member whose ``kind`` matches the given string.

        Args:
            kind: Entity kind to filter on, e.g. ``"casilla"`` or ``"formula"``.

        Returns:
            A tuple of matching :class:`ResolvedConstructMember` instances, empty if
            no members carry the requested kind.
        """
        return tuple(member for member in self.members if member.kind == kind)


type _RevisionIndex = Callable[[ModeloRevision], Mapping[str, object]]


# ANY-RETURN-RATIONALE-REGISTRY-CONSTRUCT-INDEX: values is a heterogeneous
# tuple of registry construct members (casillas, formulas, rules, ...) whose
# concrete element type varies per call site.
def _index(values: tuple[Any, ...]) -> Mapping[str, object]:
    return {str(value.id): value for value in values}


_CONSTRUCT_MEMBER_INDEXES: tuple[tuple[str, str, _RevisionIndex], ...] = (
    ("casilla", "casilla_ids", lambda revision: _index(revision.casillas)),
    ("formula", "formulas", lambda revision: _index(revision.formulas)),
    ("parameter", "parameters", lambda revision: _index(revision.parameters)),
    ("binding", "bindings", lambda revision: _index(revision.bindings)),
    ("relation", "relations", lambda revision: _index(revision.relations)),
    ("export layout", "export_layouts", lambda revision: _index(revision.export_layouts)),
    ("extraction profile", "extraction_profiles", lambda revision: _index(revision.extraction_profiles)),
    ("cross-reference", "live_cross_references", lambda revision: _index(revision.live_cross_references)),
    ("workbook parity reference", "workbook_parity_refs", lambda revision: _index(revision.workbook_parity_refs)),
    (
        "verification expectation",
        "verification_expectations",
        lambda revision: _index(revision.verification_expectations),
    ),
    ("application link", "application_links", lambda revision: _index(revision.application_links)),
    ("deadline window", "deadline_windows", lambda revision: _index(revision.deadline_windows)),
    ("filing schedule", "filing_schedules", lambda revision: _index(revision.filing_schedules)),
    (
        "dependency classification",
        "dependency_classifications",
        lambda revision: _index(revision.dependency_classifications),
    ),
)


def resolve_revision_constructs(revision: ModeloRevision) -> tuple[ResolvedConstruct, ...]:
    """Resolve all construct groups declared on a revision.

    Iterates over ``revision.constructs`` in declaration order and calls
    ``resolve_construct`` for each entry.

    Args:
        revision: The :class:`ModeloRevision` (a dated version of an AEAT modelo —
            tax form) whose construct groups should be resolved.

    Returns:
        A tuple of :class:`ResolvedConstruct` records in the same order as
        ``revision.constructs``.

    Raises:
        ``RegistrySnapshotError``: if any construct or its member references
            are missing from the revision.
    """
    return tuple(resolve_construct(revision, construct.id) for construct in revision.constructs)


def resolve_construct(revision: ModeloRevision, construct_id: str) -> ResolvedConstruct:
    """Resolve a single named construct group from a revision.

    Looks up ``construct_id`` in ``revision.constructs``, then iterates every
    member collection declared on the construct (casillas, formulas,
    parameters, bindings, and the remaining entity kinds in
    ``_CONSTRUCT_MEMBER_INDEXES``) to build the typed ``ResolvedConstructMember``
    list. Each member id is looked up in a pre-built revision index; an unknown
    id raises ``RegistrySnapshotError`` immediately.

    Args:
        revision: The :class:`ModeloRevision` to resolve against.
        construct_id: The registry-declared id of the construct group to
            resolve.

    Returns:
        A :class:`ResolvedConstruct` carrying all members with their typed values.

    Raises:
        ``RegistrySnapshotError``: if ``construct_id`` is not declared on the
            revision, or if any member id does not exist in the corresponding
            revision collection.
    """
    construct = next((item for item in revision.constructs if item.id == construct_id), None)
    if construct is None:
        raise RegistrySnapshotError(f"revision {revision.id!r} has no construct {construct_id!r}")

    members: list[ResolvedConstructMember] = []
    indexes = [(kind, attr, build_index(revision)) for kind, attr, build_index in _CONSTRUCT_MEMBER_INDEXES]
    for kind, attr, values_by_id in indexes:
        for member_id in getattr(construct, attr):
            value = values_by_id.get(member_id)
            if value is None:
                raise RegistrySnapshotError(f"construct {construct.id!r} references unknown {kind} {member_id!r}")
            members.append(ResolvedConstructMember(kind=kind, id=member_id, value=value))

    return ResolvedConstruct(
        id=construct.id,
        localization_key=construct.localization_key,
        legal_refs=construct.legal_refs,
        source_refs=construct.source_refs,
        members=tuple(members),
    )
