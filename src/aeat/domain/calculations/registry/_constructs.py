"""Construct resolution for registry revisions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from ._errors import RegistrySnapshotError
from ._schema import ModeloRevision


@dataclass(frozen=True, slots=True)
class ResolvedConstructMember:
    kind: str
    id: str
    value: object


@dataclass(frozen=True, slots=True)
class ResolvedConstruct:
    id: str
    title: str
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    members: tuple[ResolvedConstructMember, ...]

    def members_of_kind(self, kind: str) -> tuple[ResolvedConstructMember, ...]:
        return tuple(member for member in self.members if member.kind == kind)


type _RevisionIndex = Callable[[ModeloRevision], Mapping[str, object]]


def _index(values: tuple[Any, ...]) -> Mapping[str, object]:
    return {str(value.id): value for value in values}


_CONSTRUCT_MEMBER_INDEXES: tuple[tuple[str, str, _RevisionIndex], ...] = (
    ("casilla", "casillas", lambda revision: _index(revision.casillas)),
    ("formula", "formulas", lambda revision: _index(revision.formulas)),
    ("parameter", "parameters", lambda revision: _index(revision.parameters)),
    ("binding", "bindings", lambda revision: _index(revision.bindings)),
    ("algorithm provider", "algorithm_providers", lambda revision: _index(revision.algorithm_providers)),
    ("algorithm binding", "algorithm_bindings", lambda revision: _index(revision.algorithm_bindings)),
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
        "support removal decision",
        "support_removal_decisions",
        lambda revision: _index(revision.support_removal_decisions),
    ),
    (
        "dependency classification",
        "dependency_classifications",
        lambda revision: _index(revision.dependency_classifications),
    ),
)


def resolve_revision_constructs(revision: ModeloRevision) -> tuple[ResolvedConstruct, ...]:
    return tuple(resolve_construct(revision, construct.id) for construct in revision.constructs)


def resolve_construct(revision: ModeloRevision, construct_id: str) -> ResolvedConstruct:
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
        title=construct.title,
        legal_refs=construct.legal_refs,
        source_refs=construct.source_refs,
        members=tuple(members),
    )
