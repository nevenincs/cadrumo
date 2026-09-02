"""Regression guard: every casilla ``export_refs`` claim is carried by the resolved export surface.

A casilla declares ``export_refs`` to say "an export field carries me". The
export layout declares the same edge from the other side. Nothing at load
time walks the casilla side of that edge, so a casilla could claim a field no
layout provides and the registry would still validate. This screen walks the
casilla side.

Across the bundled registry the edge is symmetric today: with all three
linkage paths resolved the residue is zero. The screen is therefore a
regression guard, not a repair, and its detector teeth come from constructed
fixtures in its test, never from the corpus.

It reads the resolved surface through
:func:`~cadrumo.domain.calculations.registry.export.resolved_export_casillas`
and carries no walk of its own. Three earlier readings of this edge each
reassembled the surface by hand and each dropped one of the three linkage
paths (binding derivation, the projection fallback, the record row mapping),
producing 384, then 18, then 0 findings for the same tree. The accessor's
docstring enumerates the paths; this module must not re-derive them.

The screen exits 0 whatever it finds. It reports findings; it does not gate.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.export import resolved_export_casillas
from cadrumo.domain.calculations.registry.schema import ModeloRevision

__all__ = [
    "ExportRefSymmetryFinding",
    "screen_authority",
    "unsatisfied_export_refs",
]


@dataclass(frozen=True, slots=True)
class ExportRefSymmetryFinding:
    """One casilla whose ``export_refs`` claim the resolved surface does not carry."""

    modelo: str
    revision: str
    casilla_id: CasillaId
    export_refs: tuple[str, ...]


def unsatisfied_export_refs(revision: ModeloRevision, *, modelo_id: str) -> tuple[ExportRefSymmetryFinding, ...]:
    """Return the casillas of ``revision`` whose ``export_refs`` the resolved surface does not carry."""
    carried = resolved_export_casillas(revision)
    return tuple(
        ExportRefSymmetryFinding(
            modelo=modelo_id,
            revision=str(revision.id),
            casilla_id=casilla.id,
            export_refs=tuple(casilla.export_refs),
        )
        for casilla in revision.casillas
        if casilla.export_refs and casilla.id not in carried
    )


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[ExportRefSymmetryFinding, ...]:
    """Screen every revision of the named modelos through the validated authority."""
    findings: list[ExportRefSymmetryFinding] = []
    for modelo_id in modelo_ids:
        definition = authority.modelo(modelo_id)
        for revision in definition.revisions.values():
            findings.extend(unsatisfied_export_refs(revision, modelo_id=modelo_id))
    return tuple(findings)


def _bundled_modelo_ids() -> tuple[str, ...]:
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    return tuple(sorted(str(code) for code in registry_modelo_codes()))


def main() -> int:
    """Print one greppable row per finding and a closing summary; always exit 0."""
    authority = bundled_authority()
    findings = screen_authority(authority, _bundled_modelo_ids())
    for finding in findings:
        sys.stdout.write(
            f"export_ref_unsatisfied modelo={finding.modelo} revision={finding.revision} "
            f"casilla={finding.casilla_id} export_refs={','.join(finding.export_refs)}\n",
        )
    sys.stdout.write(f"summary surface=resolved findings={len(findings)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
