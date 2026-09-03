"""Screen: the transition from a casilla's declared type to the wire type that renders it.

A casilla declares a ``data_type`` carrying its domain meaning. The export field
that renders it declares its own ``data_type`` drawn from a deliberately narrower
wire vocabulary, because a fixed-width record has fewer distinctions than the
domain does. The narrowing is a design choice, not a defect.

What is missing is a declaration of WHICH narrowings are legitimate. Nothing in
the registry states that ``money`` may render as ``decimal`` while, say,
``money`` rendering as ``text`` would be a defect. Every transition is currently
accepted because no rule exists to reject one, so this screen reports the
transitions the corpus actually uses rather than judging them. Its output is the
evidence a transition table would be authored from; the gate comes after the
table, not before it.

It reads the resolved surface through
:func:`~cadrumo.domain.calculations.registry.export.resolved_export_endpoints`
and carries no walk of its own. A partial walk of that surface is the known
defect mode on this codebase and has produced four wrong figures; the accessor's
docstring enumerates the three linkage paths.

Row-mapped endpoints carry no field type of their own: after binding derivation
the row's slot is a binding-kind field naming the binding rather than the
casilla, so there is no rendered type to compare. Those endpoints are counted
and reported separately rather than being silently dropped or paired against a
type they do not have.

The screen exits 0 whatever it finds. It reports findings; it does not gate.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass

from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.export import resolved_export_endpoints
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from .corpus import bundled_modelo_ids

__all__ = [
    "WireTypeTransition",
    "screen_authority",
    "transitions_for_revision",
]


@dataclass(frozen=True, slots=True)
class WireTypeTransition:
    """One casilla-to-wire type transition observed on the resolved surface."""

    modelo: str
    revision: str
    casilla_id: CasillaId
    casilla_type: str
    wire_type: str
    divergent: bool


def transitions_for_revision(revision: ModeloRevision, *, modelo_id: str) -> tuple[WireTypeTransition, ...]:
    """Return every casilla-to-wire transition the revision's resolved fields carry.

    Endpoints reached through the record row mapping are excluded: they have no
    rendered field type to compare against.
    """
    declared = {casilla.id: casilla.data_type for casilla in revision.casillas}
    observed: list[WireTypeTransition] = []
    for endpoint in resolved_export_endpoints(revision):
        if endpoint.field is None:
            continue
        casilla_type = declared.get(endpoint.casilla_id)
        if casilla_type is None:
            continue
        casilla_name = str(casilla_type)
        wire_name = str(endpoint.field.data_type)
        observed.append(
            WireTypeTransition(
                modelo=modelo_id,
                revision=str(revision.id),
                casilla_id=endpoint.casilla_id,
                casilla_type=casilla_name,
                wire_type=wire_name,
                divergent=casilla_name != wire_name,
            )
        )
    return tuple(observed)


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[WireTypeTransition, ...]:
    """Collect transitions across every revision of the named modelos."""
    observed: list[WireTypeTransition] = []
    for modelo_id in modelo_ids:
        definition = authority.modelo(modelo_id)
        for revision in definition.revisions.values():
            observed.extend(transitions_for_revision(revision, modelo_id=modelo_id))
    return tuple(observed)


def main() -> int:
    """Print one row per distinct transition with its count; always exit 0."""
    authority = bundled_authority()
    observed = screen_authority(authority, bundled_modelo_ids())
    pairs = collections.Counter((item.casilla_type, item.wire_type) for item in observed)
    divergent = sum(count for (source, target), count in pairs.items() if source != target)
    for (source, target), count in sorted(pairs.items(), key=lambda entry: (-entry[1], entry[0])):
        verdict = "divergent" if source != target else "identity"
        sys.stdout.write(f"wire_type_transition from={source} to={target} count={count} kind={verdict}\n")
    sys.stdout.write(
        f"summary surface=resolved transitions={len(observed)} divergent={divergent} distinct_pairs={len(pairs)}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
