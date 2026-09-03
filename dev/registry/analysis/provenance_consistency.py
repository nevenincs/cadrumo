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
  ``casilla_continuidad_evolutions``, ``export_layouts``) — these carry their
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
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from .corpus import bundled_modelo_ids

__all__ = [
    "OutsideReferenceScope",
    "ProvenanceFinding",
    "UncitedManifestReference",
    "outside_reference_index",
    "outside_reference_scope",
    "provenance_findings",
    "screen_authority",
    "screen_uncited_manifest_references",
    "uncited_manifest_references",
]

type ProvenanceChildKind = Literal[
    "casilla",
    "formula",
    "binding",
    "relation",
    "parameter",
    "evolution",
    "export_layout",
    "export_field",
]
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
        return (
            tuple(str(ref) for ref in item.legal_refs),
            tuple(str(ref) for ref in item.source_refs),
        )

    families: tuple[tuple[ProvenanceChildKind, tuple[_CitedChild, ...]], ...] = (
        ("casilla", tuple(revision.casillas)),
        ("formula", tuple(revision.formulas)),
        ("binding", tuple(revision.bindings)),
        ("relation", tuple(revision.relations)),
        ("parameter", tuple(revision.parameters)),
        ("evolution", tuple(revision.casilla_continuidad_evolutions)),
        ("export_layout", tuple(revision.export_layouts)),
    )
    for kind, items in families:
        for item in items:
            legal, source = refs(item)
            check(kind, str(item.id), legal, source)
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


@dataclass(frozen=True, slots=True)
class UncitedManifestReference:
    """One reference a revision manifest declares that none of its children cites."""

    modelo: str
    revision: str
    ref_kind: ProvenanceRefKind
    reference: str


def uncited_manifest_references(
    revision: ModeloRevision, *, modelo_id: str
) -> tuple[UncitedManifestReference, ...]:
    """Return manifest references no child of the revision cites.

    The mirror of the condition above, and it was unmeasured. A manifest and its
    children's citations are two descriptions of the same revision's grounding,
    and neither contains the other: 59 revisions declare a manifest that is a
    subset of what their children cite, and 69 declare references nothing cites.
    Screening one direction only reported half a disagreement.

    Read from the authored families and not from resolved export fields, because
    a derived field's citations are copied from its template and would make a
    manifest reference look cited by a child that does not declare it.
    """
    cited_legal: set[str] = set()
    cited_source: set[str] = set()
    families: tuple[tuple[_CitedChild, ...], ...] = (
        tuple(revision.casillas),
        tuple(revision.formulas),
        tuple(revision.bindings),
        tuple(revision.relations),
        tuple(revision.parameters),
        tuple(revision.casilla_continuidad_evolutions),
        tuple(revision.export_layouts),
    )
    for items in families:
        for item in items:
            cited_legal |= {str(ref) for ref in item.legal_refs}
            cited_source |= {str(ref) for ref in item.source_refs}
    found: list[UncitedManifestReference] = []
    for kind, declared, cited in (
        ("legal", revision.legal_refs, cited_legal),
        ("source", revision.source_refs, cited_source),
    ):
        for reference in sorted({str(ref) for ref in declared} - cited):
            found.append(
                UncitedManifestReference(
                    modelo=modelo_id,
                    revision=str(revision.id),
                    ref_kind=kind,
                    reference=reference,
                )
            )
    return tuple(found)


def screen_uncited_manifest_references(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[UncitedManifestReference, ...]:
    """Screen every revision for manifest references nothing cites."""
    found: list[UncitedManifestReference] = []
    for modelo_id in modelo_ids:
        for revision in authority.modelo(modelo_id).revisions.values():
            found.extend(uncited_manifest_references(revision, modelo_id=modelo_id))
    return tuple(found)


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
    children, so the site count exceeds the number of things to fix by roughly
    nineteen to one. The unit someone acts on is the reference; the number of
    children citing it is how much of the revision depends on that fix.
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
    uncited = screen_uncited_manifest_references(authority, bundled_modelo_ids())
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
        f"cited_by_one_child={single} {census}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
