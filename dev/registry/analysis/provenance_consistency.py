"""Screen: every child citation of a revision stays inside the revision manifest's own citations.

A revision manifest declares the ``legal_refs`` and ``source_refs`` it applies.
Every child it owns — casilla, formula, binding, relation, parameter,
continuity evolution, export layout and every resolved export field — declares
its own ``legal_refs`` and ``source_refs`` again. Load-time validation proves
each id resolves to the catalogue and meets the evidence tier; it never
compares a child's citation with its parent's. A casilla can therefore cite an
orden its revision does not apply, or a source the revision never grounds
itself on, and the registry validates.

Two surfaces are read, and the docstring says which for each:

- the authored fragment families on the revision (``casillas``, ``formulas``,
  ``bindings``, ``relations``, ``parameters``,
  ``casilla_continuidad_evolutions``, ``export_layouts``, ``deadline_windows``) — these carry their
  own citations and are the authoring surface for them;
- the RESOLVED export fields through
  :func:`~cadrumo.domain.calculations.registry.export.resolved_export_endpoints`,
  because binding-derived fields exist only after derivation and carry the
  citations the derivation copied from their template; reading the authored
  layouts would miss them.

A citation outside the manifest is not automatically wrong: the manifest may
be the under-declared side. The screen reports the child, the kind of
reference, and the ids that fall outside; it does not gate. Exit 0 always.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass
from typing import Literal, Protocol

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.export import resolved_export_endpoints
from cadrumo.domain.calculations.registry.schema import SCHEMA_FAMILY, ModeloRevision

from .corpus import bundled_modelo_ids

__all__ = [
    "OutsideReferenceScope",
    "ProvenanceFinding",
    "citing_children",
    "outside_reference_index",
    "outside_reference_scope",
    "provenance_findings",
    "screen_authority",
]

#: A citing family's name, which is the schema field the registry declares it
#: under. Formerly a hand-written Literal of eight names; it is now whatever
#: `SCHEMA_FAMILY` annotates, plus ``export_field`` for the derived surface the
#: screen adds separately, so a family added to the registry needs no edit here.
type ProvenanceChildKind = str
type ProvenanceRefKind = Literal["legal", "source"]


class _CitedChild(Protocol):
    """Any authored child that carries an id and its own citations."""

    @property
    def id(self) -> object: ...

    @property
    def legal_refs(self) -> tuple[object, ...]: ...

    @property
    def source_refs(self) -> tuple[object, ...]: ...


@dataclass(frozen=True, slots=True)
class ProvenanceFinding:
    """One child whose citations reach outside its revision manifest."""

    modelo: str
    revision: str
    child_kind: ProvenanceChildKind
    child_id: str
    ref_kind: ProvenanceRefKind
    outside: tuple[str, ...]


def _child_id(item: object, *, family: str, position: int) -> str:
    """Return a stable identifier for one citing child.

    Not every family names its members: a verification predicate carries no
    `id`, and the walk met that only once it followed the schema's nineteen
    families rather than the eight that all happened to have one. Where there is
    no id the child is named by its family and position, which is stable for a
    given declaration file and is honest about being a location rather than a
    name. Inventing an id would put a value in a finding that no declaration
    carries.
    """
    identifier = getattr(item, "id", None)
    return str(identifier) if identifier is not None else f"{family}[{position}]"


def citing_children(
    revision: ModeloRevision,
) -> tuple[tuple[str, tuple[_CitedChild, ...]], ...]:
    """Return every authored family of a revision that carries its own citations.

    Enumerated from the registry's own `SCHEMA_FAMILY` annotation rather than
    named here. The schema declares nineteen authored families; this walk once
    listed eight of them by hand, and the gap was not theoretical - nine of the
    eleven it omitted carry citations, together accounting for 1,684 citations
    reaching outside a manifest and for 141 of the 159 references this package
    reported as cited by nothing. A hand-written list of families is a copy of a
    declaration, and every copy in this package has drifted from its original.

    The family NAME is the schema's field name, used unchanged. Singularising it
    would be a transformation with no authority behind it, and the campaign has
    refused smaller heuristics than that.

    A family is included when its items carry citations at all, so a family that
    declares none is absent rather than reported empty. Resolved export fields
    are deliberately not here: they exist only after derivation and carry
    citations copied from their template, so a screen asking what a revision's
    AUTHORS declared must not see them. The screen that needs them adds them
    itself and says why.
    """
    families: list[tuple[str, tuple[_CitedChild, ...]]] = []
    for name, field in type(revision).model_fields.items():
        if not any(item is SCHEMA_FAMILY for item in getattr(field, "metadata", ())):
            continue
        value = getattr(revision, name, None)
        items = tuple(value) if isinstance(value, (tuple, list)) else ((value,) if value is not None else ())
        carriers = tuple(
            item for item in items if hasattr(item, "legal_refs") or hasattr(item, "source_refs")
        )
        if carriers:
            families.append((name, carriers))
    return tuple(families)


def provenance_findings(revision: ModeloRevision, *, modelo_id: str) -> tuple[ProvenanceFinding, ...]:
    """Return every child of ``revision`` citing a legal or source ref the manifest does not."""
    manifest_legal = frozenset(str(ref) for ref in revision.legal_refs)
    manifest_source = frozenset(str(ref) for ref in revision.source_refs)
    findings: list[ProvenanceFinding] = []

    def check(kind: ProvenanceChildKind, child_id: str, legal: tuple[str, ...], source: tuple[str, ...]) -> None:
        outside_legal = tuple(sorted(set(legal) - manifest_legal))
        outside_source = tuple(sorted(set(source) - manifest_source))
        if outside_legal:
            findings.append(ProvenanceFinding(modelo_id, str(revision.id), kind, child_id, "legal", outside_legal))
        if outside_source:
            findings.append(ProvenanceFinding(modelo_id, str(revision.id), kind, child_id, "source", outside_source))

    def refs(item: _CitedChild) -> tuple[tuple[str, ...], tuple[str, ...]]:
        # A family may carry one kind of reference and not the other: an
        # applicability rule cites law and names no source. Assuming both was
        # safe while the walk listed eight families by hand and stopped being so
        # the moment it followed the schema's nineteen.
        return (
            tuple(str(ref) for ref in getattr(item, "legal_refs", ())),
            tuple(str(ref) for ref in getattr(item, "source_refs", ())),
        )

    families = citing_children(revision)
    for kind, items in families:
        for position, item in enumerate(items):
            legal, source = refs(item)
            check(kind, _child_id(item, family=kind, position=position), legal, source)
    seen_fields: set[tuple[str, str, str]] = set()
    for endpoint in resolved_export_endpoints(revision):
        if endpoint.field is None:
            continue
        key = (endpoint.layout_id, endpoint.record_id, str(endpoint.field.id))
        if key in seen_fields:
            continue
        seen_fields.add(key)
        legal, source = refs(endpoint.field)
        check("export_field", ".".join(key), legal, source)
    return tuple(findings)


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[ProvenanceFinding, ...]:
    """Screen every revision of the named modelos through the validated authority."""
    findings: list[ProvenanceFinding] = []
    for modelo_id in modelo_ids:
        for revision in authority.modelo(modelo_id).revisions.values():
            findings.extend(provenance_findings(revision, modelo_id=modelo_id))
    return tuple(findings)


def outside_reference_index(
    findings: tuple[ProvenanceFinding, ...],
) -> dict[tuple[str, str, str, str], int]:
    """Collapse per-child findings onto the reference that is actually outside.

    The raw finding is per citing child, which is the right measurement and the
    wrong report: one reference missing from a revision manifest is cited by many
    children. The unit someone acts on is the reference; the number of children
    citing it is how much of the revision depends on that fix.

    The ratio is stated with its definition and its date rather than as a bare
    number, because three answer to it and this docstring carried a fourth. On
    2026-09-04, summing this index gives 59,184 citing children over 1,555
    references, so a reference is cited by about 38 children; the screen's own
    finding count is 33,385, which counts a child once per KIND of reference
    rather than once per reference.

    The figure here was nineteen for a long time and matched no reading of the
    corpus. It has since moved twice more, not because the registry changed but
    because this screen twice learned to read families it had been skipping -
    which is the argument for carrying the date: a number without one cannot be
    told from a number that is still true.
    """
    index: dict[tuple[str, str, str, str], int] = {}
    for finding in findings:
        for reference in finding.outside:
            key = (finding.modelo, finding.revision, str(finding.ref_kind), reference)
            index[key] = index.get(key, 0) + 1
    return index


@dataclass(frozen=True, slots=True)
class OutsideReferenceScope:
    """One reference outside its manifests, and how far the absence reaches."""

    modelo: str
    ref_kind: str
    reference: str
    #: The revisions of this modelo whose manifest omits the reference.
    revisions: tuple[str, ...]
    #: Whether that is every revision the modelo declares.
    spans_every_revision: bool
    #: Citing children across those revisions, which is how much depends on it.
    sites: int


def outside_reference_scope(
    index: dict[tuple[str, str, str, str], int],
    revision_counts: dict[str, int],
) -> tuple[OutsideReferenceScope, ...]:
    """Report whether a reference is absent from every revision or only some.

    Built on the index rather than on the findings, so there is one collapse
    from sites to references and this asks a further question of its result
    instead of repeating the reduction.

    The distinction is the remedy. A reference absent from every revision of its
    modelo is one omission - the modelo never declares it anywhere - and is
    plausibly fixed once. A reference present in some revisions and absent from
    others is drift between manifests that were meant to agree, and each gap is
    its own correction. The index alone cannot tell them apart: it is keyed per
    revision, so both shapes appear as several rows that look identical.

    ``revision_counts`` is passed in rather than read from an authority here,
    because this is arithmetic over an already-measured index and taking the
    authority would make it a second traversal of the registry.
    """
    grouped: dict[tuple[str, str, str], list[tuple[str, int]]] = collections.defaultdict(list)
    for (modelo, revision, ref_kind, reference), sites in index.items():
        grouped[(modelo, ref_kind, reference)].append((revision, sites))
    scopes = [
        OutsideReferenceScope(
            modelo=modelo,
            ref_kind=ref_kind,
            reference=reference,
            revisions=tuple(sorted(revision for revision, _ in members)),
            spans_every_revision=len(members) == revision_counts.get(modelo, -1),
            sites=sum(sites for _, sites in members),
        )
        for (modelo, ref_kind, reference), members in grouped.items()
    ]
    return tuple(sorted(scopes, key=lambda item: (-item.sites, item.modelo, item.reference)))


def main() -> int:
    """Print one greppable row per outside reference and a per-kind summary; always exit 0."""
    findings = screen_authority(bundled_authority(), bundled_modelo_ids())
    index = outside_reference_index(findings)
    for (modelo, revision, ref_kind, reference), sites in sorted(index.items()):
        sys.stdout.write(
            f"provenance_outside_manifest modelo={modelo} revision={revision} "
            f"ref_kind={ref_kind} outside={reference} citing_children={sites}\n",
        )
    authority = bundled_authority()
    scopes = outside_reference_scope(
        index, {modelo: len(authority.modelo(modelo).revisions) for modelo in bundled_modelo_ids()}
    )
    for scope in scopes:
        sys.stdout.write(
            f"provenance_reference_scope modelo={scope.modelo} ref_kind={scope.ref_kind} "
            f"reference={scope.reference} revisions={len(scope.revisions)} "
            f"spans_every_revision={str(scope.spans_every_revision).lower()} sites={scope.sites}\n",
        )
    from .manifest_uncited_references import screen_authority as uncited_screen

    uncited = uncited_screen(authority, bundled_modelo_ids())
    for item in uncited:
        sys.stdout.write(
            f"provenance_uncited_manifest_ref modelo={item.modelo} revision={item.revision} "
            f"ref_kind={item.ref_kind} reference={item.reference}\n",
        )
    by_kind: dict[str, int] = {}
    for f in findings:
        by_kind[f"{f.child_kind}.{f.ref_kind}"] = by_kind.get(f"{f.child_kind}.{f.ref_kind}", 0) + 1
    census = " ".join(f"{key}={value}" for key, value in sorted(by_kind.items()))
    # Single-child references are the small set worth reading one at a time: a
    # reference cited by one child and absent from the manifest is as likely to
    # be a citation outside the revision's scope as a gap in the manifest, while
    # one cited by hundreds is the manifest under-declaring. The screen does not
    # decide the direction; this is the figure that says where to look first.
    single = sum(1 for scope in scopes if scope.sites == 1)
    sys.stdout.write(
        f"summary surface=authored_families+resolved_fields outside_references={len(index)} "
        f"distinct_reference_ids={len({key[3] for key in index})} citing_sites={len(findings)} "
        f"modelo_reference_pairs={len(scopes)} "
        f"spanning_every_revision={sum(s.spans_every_revision for s in scopes)} "
        f"cited_by_one_child={single} uncited_manifest_refs={len(uncited)} {census}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
