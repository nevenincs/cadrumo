"""Gate: a casilla that keeps its role across adjacent editions keeps its formula and binding.

The cross-edition casilla comparison covers label, section, data type, semantic
role and legal references. It does not compare how the casilla is computed, so a
formula or binding declared in one edition and silently absent in the adjacent
one passes every existing guard. This audit compares exactly that, for casillas
whose semantic role is the same in both editions, and accepts the difference
only when the edition that changed it declares a continuity evolution for the casilla.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cadrumo.domain.calculations.registry.schema import ModeloRevision

if TYPE_CHECKING:
    from .edition_singleton_audit import EditionView

__all__ = ("CasillaFact", "DroppedMemberFinding", "casilla_facts", "dropped_member_findings")


@dataclass(frozen=True, slots=True)
class CasillaFact:
    """How one casilla is computed in one edition."""

    role: str | None
    has_formula: bool
    has_binding: bool
    cites_difference: bool


@dataclass(frozen=True, slots=True)
class DroppedMemberFinding:
    """A formula or binding present in one adjacent edition and absent in the other."""

    modelo: str
    casilla_id: str
    member: str
    present_in: str
    absent_in: str

    @property
    def key(self) -> str:
        """Return the stable baseline key."""
        subject = f"{self.modelo}|{self.casilla_id}|{self.member}"
        return f"casilla-member|{subject}|present={self.present_in}|absent={self.absent_in}"


def casilla_facts(revision: ModeloRevision) -> Mapping[str, CasillaFact]:
    """Project one hydrated edition's casillas into comparable facts."""
    lineages = {evolution.continuidad_id for evolution in revision.casilla_continuidad_evolutions}
    return {
        str(casilla.id): CasillaFact(
            role=casilla.semantic_role,
            has_formula=casilla.formula is not None,
            has_binding=casilla.binding is not None or bool(casilla.alternate_bindings),
            cites_difference=casilla.continuidad_id in lineages,
        )
        for casilla in revision.casillas
    }


def _differences(left: CasillaFact, right: CasillaFact) -> list[tuple[str, bool]]:
    """Return ``(member, present_in_left)`` for each computed member the two sides disagree on."""
    found: list[tuple[str, bool]] = []
    if left.has_formula != right.has_formula:
        found.append(("formula", left.has_formula))
    if left.has_binding != right.has_binding:
        found.append(("binding", left.has_binding))
    return found


def _pair_findings(modelo: str, left: EditionView, right: EditionView) -> list[DroppedMemberFinding]:
    findings: list[DroppedMemberFinding] = []
    for casilla_id, left_fact in left.casillas.items():
        right_fact = right.casillas.get(casilla_id)
        if right_fact is None or left_fact.role != right_fact.role or right_fact.cites_difference:
            continue
        for member, present_left in _differences(left_fact, right_fact):
            present, absent = (left, right) if present_left else (right, left)
            findings.append(DroppedMemberFinding(modelo, casilla_id, member, present.edition, absent.edition))
    return findings


def dropped_member_findings(modelo: str, editions: Sequence[EditionView]) -> tuple[DroppedMemberFinding, ...]:
    """Compare every adjacent pair of editions that print the same periods."""
    tracks: dict[tuple[str, ...], list[EditionView]] = {}
    for edition in editions:
        tracks.setdefault(edition.track, []).append(edition)
    found = [
        finding
        for group in tracks.values()
        for left, right in itertools.pairwise(group)
        for finding in _pair_findings(modelo, left, right)
    ]
    return tuple(sorted(found, key=lambda item: item.key))
