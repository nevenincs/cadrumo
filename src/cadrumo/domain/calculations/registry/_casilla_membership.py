"""Registry-scoped casilla id membership helpers.

The helpers inspect one
:class:`~domain.calculations.registry.ModeloRevision` and return canonical
:class:`~domain.calculations.registry.CasillaDefinition` membership keyed
only by declared ``casilla.id`` values.

See Also:
    :mod:`core._casilla_id`
        Shape validation for :class:`~domain.calculations.registry.CasillaId`.
    :mod:`domain.calculations.registry._formula_runtime_ops`
        Runtime input canonicalisation that rejects undeclared casillas through
        these helpers.
    :mod:`application.modelo._registry_helpers`
        Application boundary that refuses non-canonical casilla metadata tokens.
"""

from __future__ import annotations

from collections.abc import Iterable

from ._errors import RegistryValidationError
from ._ids import CasillaId
from ._schema import CasillaDefinition, ModeloRevision


def casillas_by_id(revision: ModeloRevision) -> dict[CasillaId, CasillaDefinition]:
    """Return casilla definitions keyed by canonical ``casilla.id``.

    Args:
        revision: The
            :class:`~domain.calculations.registry.ModeloRevision` whose
            :class:`~domain.calculations.registry.CasillaDefinition`
            declarations are inspected.
    """
    casillas: dict[CasillaId, CasillaDefinition] = {}
    duplicates: set[CasillaId] = set()
    for casilla in revision.casillas:
        if casilla.id in casillas:
            duplicates.add(casilla.id)
        casillas[casilla.id] = casilla
    if duplicates:
        duplicate_ids = tuple(sorted(duplicates))
        raise RegistryValidationError(
            f"revision {revision.id!r} declares duplicate casilla.id values; "
            f"casilla references are ambiguous: {duplicate_ids!r}",
            context={"revision_id": revision.id, "casilla_ids": ",".join(duplicate_ids)},
        )
    return casillas


def declared_casilla_ids(revision: ModeloRevision) -> frozenset[CasillaId]:
    """Return canonical ids declared by a registry revision.

    The returned :class:`~domain.calculations.registry.CasillaId` set is
    scoped to one :class:`~domain.calculations.registry.ModeloRevision`; it
    is stronger than shape validation alone.
    """
    return frozenset(casillas_by_id(revision))


def undeclared_casilla_ids(
    revision: ModeloRevision,
    casilla_ids: Iterable[CasillaId],
) -> tuple[CasillaId, ...]:
    """Return ids not declared by a registry revision.

    The ``revision`` argument is a
    :class:`~domain.calculations.registry.ModeloRevision`. Use this after
    raw keys have already been validated as
    :class:`~domain.calculations.registry.CasillaId` shape-compatible.
    """
    return tuple(sorted(set(casilla_ids) - declared_casilla_ids(revision)))


def casilla_noncanonical_reference_tokens(revision: ModeloRevision) -> dict[str, tuple[CasillaId, ...]]:
    """Return refused metadata tokens for a registry revision.

    The ``revision`` argument is a
    :class:`~domain.calculations.registry.ModeloRevision`.
    The keys are printed numbers, form numbers, and export refs that are not
    canonical ``casilla.id`` values. Values are the canonical candidate
    :class:`~domain.calculations.registry.CasillaId` entries.
    """
    tokens: dict[str, set[CasillaId]] = {}
    for casilla in revision.casillas:
        for token in _casilla_metadata_tokens(casilla):
            if token is None or token == casilla.id:
                continue
            tokens.setdefault(token, set()).add(casilla.id)
    return {token: tuple(sorted(casilla_ids)) for token, casilla_ids in tokens.items()}


def casilla_noncanonical_reference_targets(revision: ModeloRevision, token: str) -> tuple[CasillaId, ...]:
    """Return canonical ids whose revision metadata matches a token.

    The ``revision`` argument is a
    :class:`~domain.calculations.registry.ModeloRevision`. Callers use
    this to reject printed numbers, form numbers, and export refs while still
    naming the canonical casilla candidates in diagnostics.
    """
    return casilla_noncanonical_reference_tokens(revision).get(token, ())


def format_noncanonical_casilla_reference(token: str, targets: tuple[CasillaId, ...]) -> str:
    """Render a refused metadata token with its canonical casilla candidates.

    ``targets`` comes from :func:`casilla_noncanonical_reference_targets`.
    A single target is rendered as a correction while multiple targets are
    rendered as an ambiguity so every boundary explains why it cannot infer an
    id from a printed number, form number, or export reference.
    """
    rendered_targets = ", ".join(targets)
    if len(targets) > 1:
        return f"{token!r} is ambiguous; candidate casilla.id values: {rendered_targets}"
    return f"{token!r} -> {rendered_targets}"


def _casilla_metadata_tokens(casilla: CasillaDefinition) -> tuple[str | None, ...]:
    return (casilla.number, casilla.form_number, *casilla.export_refs)
