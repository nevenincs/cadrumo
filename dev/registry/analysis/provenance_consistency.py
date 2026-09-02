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

import sys
from dataclasses import dataclass
from typing import Literal, Protocol

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.export import resolved_export_endpoints
from cadrumo.domain.calculations.registry.schema import ModeloRevision

__all__ = ["ProvenanceFinding", "provenance_findings", "screen_authority"]

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


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[ProvenanceFinding, ...]:
    """Screen every revision of the named modelos through the validated authority."""
    findings: list[ProvenanceFinding] = []
    for modelo_id in modelo_ids:
        for revision in authority.modelo(modelo_id).revisions.values():
            findings.extend(provenance_findings(revision, modelo_id=modelo_id))
    return tuple(findings)


def _bundled_modelo_ids() -> tuple[str, ...]:
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    return tuple(sorted(str(code) for code in registry_modelo_codes()))


def main() -> int:
    """Print one greppable row per finding and a per-kind summary; always exit 0."""
    findings = screen_authority(bundled_authority(), _bundled_modelo_ids())
    for f in findings:
        sys.stdout.write(
            f"provenance_outside_manifest modelo={f.modelo} revision={f.revision} child={f.child_kind}:{f.child_id} "
            f"ref_kind={f.ref_kind} outside={','.join(f.outside)}\n",
        )
    by_kind: dict[str, int] = {}
    for f in findings:
        by_kind[f"{f.child_kind}.{f.ref_kind}"] = by_kind.get(f"{f.child_kind}.{f.ref_kind}", 0) + 1
    census = " ".join(f"{key}={value}" for key, value in sorted(by_kind.items()))
    sys.stdout.write(f"summary surface=authored_families+resolved_fields findings={len(findings)} {census}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
