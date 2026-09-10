"""Continuity policy that reads how a casilla row claims its predecessor.

A ``continuidad_origin`` of ``seeded`` or ``grounded`` asserts that the row
continues the row of the edition immediately before it that carries the same
``continuidad_id``. The two continuations rest on different things and this
policy keeps them apart:

- a SEEDED chain is inference written down: identifier, ``semantic_role`` and
  ``data_type`` agree, and the dedicated printed box ``form_number`` agrees
  where both rows state one. It is admissible only while that predicate still
  holds against the predecessor row. A seeded chain can never carry a
  divergence, because nothing but the predicate stands behind it;
- a GROUNDED chain is a statement established from the cited evidence in
  ``continuidad_evidence``. The predicate is not re-applied to it -- a
  renumbered or retyped box is exactly what evidence can establish -- and a
  link it grounds needs no ``semantic_role`` to be accepted as a link.

Both must resolve their predecessor: exactly one row carrying the chain in the
adjacent, non-overlapping predecessor edition.

Where this policy stops:

- it does not re-read the cited evidence; a grounded row is taken at its
  citation, and whether the citation proves the link is a review question;
- a row with no ``continuidad_origin`` is treated as an authored declaration,
  exactly as before origins existed. Unset does not distinguish an authored
  chain from an unexamined one, so this policy neither verifies nor excuses
  unmarked rows;
- the absence origins (``new_on_form``, ``predecessor_edition_silent``,
  ``not_on_form``) are not read here;
- only the adjacent predecessor link is checked. A seeded row two editions on
  is judged against its own predecessor, never against the chain's start.
"""

from __future__ import annotations

from dataclasses import dataclass

from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.ids import RevisionId
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions, revisions_overlap
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

__all__ = (
    "lineage_origin_continuity_failures",
    "role_exempt_occurrences",
)

type _OccurrenceKey = tuple[RevisionId, CasillaId]


@dataclass(frozen=True, slots=True)
class _ResolvedPredecessor:
    revision: ModeloRevision
    casilla: CasillaDefinition


def lineage_origin_continuity_failures(modelo: ModeloDefinition) -> tuple[str, ...]:
    """Refuse a continuation whose predecessor or seeding predicate does not hold."""
    revisions = ordered_revisions(modelo)
    failures: list[str] = []
    for index, revision in enumerate(revisions):
        predecessor_revision = revisions[index - 1] if index > 0 else None
        for casilla in revision.casillas:
            origin = casilla.continuidad_origin
            if origin is None or not origin.continues_a_chain:
                continue
            resolved = _resolve_predecessor(predecessor_revision, revision, casilla)
            if isinstance(resolved, str):
                failures.append(_format_failure(modelo.id, revision.id, casilla, resolved))
                continue
            if origin is CasillaLineageOrigin.SEEDED:
                contradiction = _seeding_contradiction(resolved.casilla, casilla)
                if contradiction is not None:
                    failures.append(
                        _format_failure(
                            modelo.id,
                            revision.id,
                            casilla,
                            f"seeded continuation of {resolved.revision.id!r} casilla {resolved.casilla.id!r} "
                            f"no longer holds: {contradiction}; a seeded chain is inference and cannot carry "
                            "a divergence -- ground it in cited evidence or withdraw it",
                        ),
                    )
    return tuple(failures)


def role_exempt_occurrences(modelo: ModeloDefinition) -> frozenset[_OccurrenceKey]:
    """Return the chain occurrences every lineage link of which is grounded.

    A link is the step from a row to the predecessor it continues. It is
    grounded only when the continuing row declares ``grounded`` with non-empty
    evidence and its predecessor resolves; a seeded or unmarked continuation is
    never grounded. An occurrence is exempt from carrying a ``semantic_role``
    for continuity linkage only when it touches at least one link and every
    link touching it -- the one it continues and each one continuing it -- is
    grounded. A chain start with no earlier occurrence has no incoming link.
    """
    revisions = ordered_revisions(modelo)
    position = {revision.id: index for index, revision in enumerate(revisions)}
    first_position: dict[str, int] = {}
    for revision in revisions:
        for casilla in revision.casillas:
            if casilla.continuidad_id is not None:
                first_position.setdefault(casilla.continuidad_id, position[revision.id])

    grounded_incoming: set[_OccurrenceKey] = set()
    has_incoming: set[_OccurrenceKey] = set()
    grounded_successors: set[_OccurrenceKey] = set()
    ungrounded_successors: set[_OccurrenceKey] = set()
    for index, revision in enumerate(revisions):
        predecessor_revision = revisions[index - 1] if index > 0 else None
        for casilla in revision.casillas:
            if casilla.continuidad_id is None:
                continue
            key = (revision.id, casilla.id)
            if first_position[casilla.continuidad_id] < index:
                has_incoming.add(key)
            resolved = _resolve_predecessor(predecessor_revision, revision, casilla)
            if isinstance(resolved, str):
                continue
            predecessor_key = (resolved.revision.id, resolved.casilla.id)
            if _is_grounded_link(casilla):
                grounded_incoming.add(key)
                grounded_successors.add(predecessor_key)
            else:
                ungrounded_successors.add(predecessor_key)

    exempt: set[_OccurrenceKey] = set()
    for revision in revisions:
        for casilla in revision.casillas:
            if casilla.continuidad_id is None:
                continue
            key = (revision.id, casilla.id)
            incoming_ok = key in grounded_incoming or key not in has_incoming
            touches_a_link = key in grounded_incoming or key in grounded_successors
            if incoming_ok and touches_a_link and key not in ungrounded_successors:
                exempt.add(key)
    return frozenset(exempt)


def _is_grounded_link(casilla: CasillaDefinition) -> bool:
    evidence = casilla.continuidad_evidence
    return (
        casilla.continuidad_origin is CasillaLineageOrigin.GROUNDED and evidence is not None and bool(evidence.strip())
    )


def _resolve_predecessor(
    predecessor_revision: ModeloRevision | None,
    revision: ModeloRevision,
    casilla: CasillaDefinition,
) -> _ResolvedPredecessor | str:
    """Return the row ``casilla`` continues, or the reason no single row qualifies."""
    if predecessor_revision is None:
        return "the first edition has no predecessor edition to continue"
    if revisions_overlap(predecessor_revision, revision):
        return (
            f"predecessor edition {predecessor_revision.id!r} shares a validity window with this edition, "
            "so neither precedes the other"
        )
    carriers = tuple(
        candidate
        for candidate in predecessor_revision.casillas
        if candidate.continuidad_id is not None and candidate.continuidad_id == casilla.continuidad_id
    )
    if not carriers:
        return (
            f"predecessor edition {predecessor_revision.id!r} does not carry continuidad_id {casilla.continuidad_id!r}"
        )
    if len(carriers) > 1:
        return (
            f"predecessor edition {predecessor_revision.id!r} carries continuidad_id {casilla.continuidad_id!r} "
            f"on {len(carriers)} rows {tuple(sorted(str(carrier.id) for carrier in carriers))!r}; "
            "a continuation must name exactly one"
        )
    return _ResolvedPredecessor(revision=predecessor_revision, casilla=carriers[0])


def _seeding_contradiction(previous: CasillaDefinition, successor: CasillaDefinition) -> str | None:
    """Return why the mechanical seeding predicate fails between two rows, if it does."""
    if previous.id != successor.id:
        return f"casilla identifier moved {str(previous.id)!r} -> {str(successor.id)!r}"
    if previous.semantic_role is None or successor.semantic_role is None:
        side = "predecessor" if previous.semantic_role is None else "successor"
        return f"the {side} row has no semantic_role to agree on"
    if previous.semantic_role != successor.semantic_role:
        return f"semantic_role moved {previous.semantic_role!r} -> {successor.semantic_role!r}"
    if previous.data_type != successor.data_type:
        return f"data_type moved {previous.data_type!s} -> {successor.data_type!s}"
    if (
        previous.form_number is not None
        and successor.form_number is not None
        and previous.form_number != successor.form_number
    ):
        return f"form_number moved {previous.form_number!r} -> {successor.form_number!r}"
    return None


def _format_failure(modelo_id: str, revision_id: RevisionId, casilla: CasillaDefinition, reason: str) -> str:
    origin = casilla.continuidad_origin
    origin_token = origin.value if origin is not None else None
    return (
        "casilla lineage continuation refused: "
        f"modelo {modelo_id} revision {revision_id!r} casilla {str(casilla.id)!r} "
        f"continuidad_origin {origin_token!r} continuidad_id {casilla.continuidad_id!r}: {reason}"
    )
