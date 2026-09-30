"""The cross-edition stability gate: a moved placement needs an acknowledgement.

An operator must never find a form silently rearranged. Each revision's layout
is compared with its declared predecessor's: a casilla that continues across
the edge (same ``continuidad_id``, or the same id where neither declares one)
and sits on the form in both editions keeps its ``(page, section)`` position,
or the move is listed in the acknowledgement file with the reviewed reason.
An acknowledgement naming a move that no longer happens is stale and refused
too, so the file never outlives the moves it explains.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.toml import load_toml
from cadrumo.domain.calculations.registry.revision_contracts import DeclaredPredecessor
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision

__all__ = [
    "STABILITY_ACKNOWLEDGEMENTS",
    "PlacementMove",
    "moved_placements",
    "read_acknowledgements",
    "unacknowledged_moves",
]

STABILITY_ACKNOWLEDGEMENTS: Final[Path] = Path(__file__).with_name("stability_acknowledgements.toml")


@dataclass(frozen=True, slots=True, order=True)
class PlacementMove:
    """One continuing casilla whose on-form position differs from its predecessor's."""

    modelo_id: str
    revision_id: str
    casilla_id: str
    from_position: str
    to_position: str


def _continuity_key(revision: ModeloRevision) -> dict[str, str]:
    return {casilla.id: casilla.continuidad_id or casilla.id for casilla in revision.casillas}


def _positions(revision: ModeloRevision) -> dict[str, str]:
    if not revision.form_layouts:
        return {}
    keys = _continuity_key(revision)
    return {
        keys.get(casilla_id, casilla_id): f"{page}/{section}"
        for casilla_id, (page, section) in revision.form_layouts[0].casilla_sections().items()
    }


def moved_placements(modelos: Iterable[ModeloDefinition]) -> tuple[PlacementMove, ...]:
    """Return every continuing on-form casilla whose position moved across a declared edge."""
    moves: list[PlacementMove] = []
    for modelo in modelos:
        for revision_id, revision in modelo.revisions.items():
            predecessor = revision.predecessor
            if not isinstance(predecessor, DeclaredPredecessor):
                continue
            previous = modelo.revisions.get(predecessor.revision_id)
            if previous is None:
                continue
            before = _positions(previous)
            after = _positions(revision)
            by_key = {key: casilla_id for casilla_id, key in _continuity_key(revision).items()}
            moves.extend(
                PlacementMove(str(modelo.id), str(revision_id), by_key.get(key, key), before[key], position)
                for key, position in after.items()
                if key in before and before[key] != position
            )
    return tuple(sorted(moves))


def read_acknowledgements(path: Path = STABILITY_ACKNOWLEDGEMENTS) -> Mapping[PlacementMove, str]:
    """Return every acknowledged move with its reviewed reason."""
    acknowledged: dict[PlacementMove, str] = {}
    if not path.is_file():
        return acknowledged
    with path.open("rb") as handle:
        entries = load_toml(handle).get("moves", [])
    for entry in entries if isinstance(entries, list) else ():
        move = PlacementMove(
            str(entry["modelo"]),
            str(entry["revision"]),
            str(entry["casilla"]),
            str(entry["from"]),
            str(entry["to"]),
        )
        acknowledged[move] = str(entry["reason"])
    return acknowledged


def unacknowledged_moves(
    moves: Iterable[PlacementMove],
    acknowledged: Mapping[PlacementMove, str],
) -> tuple[tuple[PlacementMove, ...], tuple[PlacementMove, ...]]:
    """Return the moves nobody acknowledged and the acknowledgements naming no current move."""
    current = set(moves)
    missing = tuple(sorted(current - acknowledged.keys()))
    stale = tuple(sorted(acknowledged.keys() - current))
    return missing, stale
