"""Canonical lineage admission, identifier, ordering, and ruling rules."""

from __future__ import annotations

import collections
import re
from collections.abc import Iterable
from pathlib import Path

from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.registry.casilla_lineage_totality import (
    judging_predecessor,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .casilla_lineage_seed_design import identity_box
from .casilla_lineage_seed_paths import _UTF_8, RULINGS_PATH
from .casilla_lineage_seed_types import LineageRefusalCategory, Ruling

_CONTINUIDAD_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*[a-z0-9]$|^[a-z0-9]$")

_MIN_POSITIONAL_SPACE = 5

_MAX_POSITIONAL_EXPANSION = 3.0

_PARTIAL_STAMP = (
    "another occurrence of this identifier cannot carry a continuidad_id, and the registry refuses an identifier "
    "stamped in only part of its occurrences"
)


def _pairs(values: Iterable[str]) -> tuple[tuple[str, str], ...]:
    return tuple((left, right) for left, _, right in (value.partition(">") for value in values))


def load_rulings(path: Path = RULINGS_PATH) -> dict[str, list[Ruling]]:
    """Load every adjudicated ruling keyed by modelo.

    Rulings for an excluded modelo are applied to its data by whoever owns that
    modelo; this seeder reads them only to name its residual refusals precisely.
    """
    document = parse_toml(path.read_text(encoding=_UTF_8))
    rulings: dict[str, list[Ruling]] = collections.defaultdict(list)
    for entry in document["ruling"]:
        rulings[entry["modelo"]].append(
            Ruling(
                predecessor=entry["predecessor"],
                successor=entry["successor"],
                refuse_bare=bool(entry.get("refuse_bare", False)),
                rationale=entry["rationale"],
                grounded=_pairs(entry.get("grounded", ())),
                new_on_form=frozenset(entry.get("new_on_form", ())),
                new_on_form_stems=frozenset(entry.get("new_on_form_stems", ())),
                not_on_form=frozenset(entry.get("not_on_form", ())),
                held=_pairs(entry.get("held", ())),
                held_stems=frozenset(entry.get("held_stems", ())),
                held_reason=entry.get("held_reason", ""),
                withheld=_pairs(entry.get("withheld", ())),
                withheld_reason=entry.get("withheld_reason", ""),
                merged=_pairs(entry.get("merged", ())),
                merged_reason=entry.get("merged_reason", ""),
                discontinued=frozenset(entry.get("discontinued", ())),
            )
        )
    return dict(rulings)


def judged_pairs(
    modelo: ModeloDefinition, revisions: tuple[ModeloRevision, ...]
) -> tuple[tuple[ModeloRevision, ModeloRevision], ...]:
    """Every ``(predecessor, successor)`` edition pair whose successor rows are judged.

    Pairing is the lineage totality rule's own
    :func:`~cadrumo.domain.calculations.registry.casilla_lineage_totality.judging_predecessor`,
    reused rather than restated: a predecessor is the edition an edition's rows
    continue from, which is a closed earlier edition and never a concurrent
    sibling sharing its validity window. Period selectors do not decide it --
    two adjacent editions may name overlapping period tokens while the earlier
    one closes before the later one opens, and those rows do continue.
    """
    return tuple(
        (predecessor, successor)
        for index, successor in enumerate(revisions)
        if (predecessor := judging_predecessor(modelo, revisions, index)) is not None
    )


def admit_bare_chain(
    previous: CasillaDefinition, successor: CasillaDefinition
) -> tuple[LineageRefusalCategory | None, str]:
    """Return ``(None, detail)`` when a bare chain is admitted, else ``(category, reason)``.

    The identifier is already equal; role, type and the dedicated printed box
    must agree too. A missing role is its own category: nothing can be agreed
    with an absent role, and the load contract refuses a chain without one.
    """
    if previous.semantic_role is None or successor.semantic_role is None:
        side = "predecessor" if previous.semantic_role is None else "successor"
        return (
            LineageRefusalCategory.ROLE_ABSENT,
            f"no semantic_role on the {side} row; identity cannot be established on role",
        )
    if previous.semantic_role != successor.semantic_role:
        return (
            LineageRefusalCategory.CONTRADICTED,
            f"semantic_role moved {previous.semantic_role!r} -> {successor.semantic_role!r}",
        )
    if previous.data_type != successor.data_type:
        return (
            LineageRefusalCategory.CONTRADICTED,
            f"data_type moved {previous.data_type!s} -> {successor.data_type!s}",
        )
    before, after = identity_box(previous), identity_box(successor)
    if before is not None and after is not None and before != after:
        return LineageRefusalCategory.CONTRADICTED, f"form_number moved {before!r} -> {after!r}"
    return None, "identifier, semantic_role and data_type agree; form_number does not contradict"


def positional_hold(previous: ModeloRevision, successor: ModeloRevision) -> str | None:
    """A positional identifier space with boxes inserted: every bare chain across it is refused."""
    if not _positional_space_expanded(previous, successor):
        return None
    overlap = _section_overlap(previous, successor)
    if overlap is None or overlap > 0.25:
        return None
    prev_ids = {casilla.id for casilla in previous.casillas}
    succ_ids = {casilla.id for casilla in successor.casillas}
    return (
        f"positional identifier space: all {len(prev_ids)} predecessor ids reused among {len(succ_ids)} "
        f"successor rows with {overlap:.0%} shared section vocabulary, so boxes were inserted"
    )


def _positional_space_expanded(previous: ModeloRevision, successor: ModeloRevision) -> bool:
    prev_ids = {casilla.id for casilla in previous.casillas}
    succ_ids = {casilla.id for casilla in successor.casillas}
    if not prev_ids or len(succ_ids) == len(prev_ids) or not prev_ids <= succ_ids:
        return False
    return len(prev_ids) >= _MIN_POSITIONAL_SPACE and len(succ_ids) <= _MAX_POSITIONAL_EXPANSION * len(prev_ids)


def _section_overlap(previous: ModeloRevision, successor: ModeloRevision) -> float | None:
    prev_sections = {part for casilla in previous.casillas for part in casilla.section}
    succ_sections = {part for casilla in successor.casillas for part in casilla.section}
    if not prev_sections or not succ_sections:
        return None
    return len(prev_sections & succ_sections) / len(prev_sections | succ_sections)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-_")
    return slug[:128].rstrip("-_")


def _role_derived(role: str) -> str:
    return role.lower().replace("_", "-")
