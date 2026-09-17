"""Registry-scoped casilla id membership helpers.

The helpers inspect one
:class:`~domain.calculations.registry.schema.ModeloRevision` and return canonical
:class:`~domain.calculations.registry.schema_surfaces.CasillaDefinition` membership keyed
only by declared ``casilla.id`` values.

See Also:
    :mod:`core.casilla_id`
        Shape validation for :class:`~core.casilla_id.CasillaId`.
    :mod:`domain.calculations.registry.formula_runtime_ops`
        Runtime input canonicalisation that rejects undeclared casillas through
        these helpers.
    :mod:`application.modelo._registry_helpers`
        Application boundary that refuses non-canonical casilla metadata tokens.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING

from ....core.casilla_id import CasillaId
from .binding_value_contract import BindingValueChannel
from .errors import RegistryValidationError
from .schema_surfaces import CasillaDefinition

if TYPE_CHECKING:
    from .schema import ModeloRevision


def duplicate_casilla_ids(casilla_ids: Iterable[CasillaId]) -> tuple[CasillaId, ...]:
    """Return the ids appearing more than once in ``casilla_ids``, sorted.

    For a collection that must address each casilla exactly once — a
    revision's :class:`~domain.calculations.registry.schema_surfaces.CasillaDefinition`
    declarations, a calculation result's observation and unresolved rows — a
    repeated id makes the downstream mapping resolve by position and drop
    every row but the last. This is the one fold that names the repeats so
    such a collection can refuse the ambiguity at construction.

    Not every casilla-keyed collection is under that rule: multi-row
    informativas repeat a casilla once per declared item, and their ordered
    row tuple is the multiplicity carrier. Callers decide whether repetition
    is ambiguity or payload; this helper only reports it.
    """
    counts = Counter(casilla_ids)
    return tuple(sorted(casilla_id for casilla_id, count in counts.items() if count > 1))


def casillas_by_id(revision: ModeloRevision) -> dict[CasillaId, CasillaDefinition]:
    """Return casilla definitions keyed by canonical ``casilla.id``.

    Args:
        revision: The
            :class:`~domain.calculations.registry.schema.ModeloRevision` whose
            :class:`~domain.calculations.registry.schema_surfaces.CasillaDefinition`
            declarations are inspected.
    """
    duplicate_ids = duplicate_casilla_ids(casilla.id for casilla in revision.casillas)
    if duplicate_ids:
        raise RegistryValidationError(
            f"revision {revision.id!r} declares duplicate casilla.id values; "
            f"casilla references are ambiguous: {duplicate_ids!r}",
            context={"revision_id": revision.id, "casilla_ids": ",".join(duplicate_ids)},
        )
    return {casilla.id: casilla for casilla in revision.casillas}


def declared_casilla_ids(revision: ModeloRevision) -> frozenset[CasillaId]:
    """Return canonical ids declared by a registry revision.

    The returned :class:`~core.casilla_id.CasillaId` set is
    scoped to one :class:`~domain.calculations.registry.schema.ModeloRevision`; it
    is stronger than shape validation alone.
    """
    return frozenset(casillas_by_id(revision))


def row_template_casilla_ids(revision: ModeloRevision) -> frozenset[CasillaId]:
    """Return the casillas that are one field of a record a row-set binding emits.

    Such a casilla is written once per emitted row, never typed once as a
    scalar, so its completeness belongs to the row source. The record is named
    by the casilla's leading section and by the row-set binding's provider.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    records = {
        str(record)
        for binding in revision.bindings
        if binding.value.channel is BindingValueChannel.ROW_SET
        and (record := getattr(binding.provider, "record", None)) is not None
    }
    return frozenset(
        casilla.id for casilla in revision.casillas if casilla.section and str(casilla.section[0]) in records
    )


def undeclared_casilla_ids(
    revision: ModeloRevision,
    casilla_ids: Iterable[CasillaId],
) -> tuple[CasillaId, ...]:
    """Return ids not declared by a registry revision.

    The ``revision`` argument is a
    :class:`~domain.calculations.registry.schema.ModeloRevision`. Use this after
    raw keys have already been validated as
    :class:`~core.casilla_id.CasillaId` shape-compatible.
    """
    return tuple(sorted(set(casilla_ids) - declared_casilla_ids(revision)))


def casilla_noncanonical_reference_tokens(revision: ModeloRevision) -> dict[str, tuple[CasillaId, ...]]:
    """Return refused metadata tokens for a registry revision.

    The ``revision`` argument is a
    :class:`~domain.calculations.registry.schema.ModeloRevision`.
    The keys are printed numbers, form numbers, and export refs that are not
    canonical ``casilla.id`` values. Values are the canonical candidate
    :class:`~core.casilla_id.CasillaId` entries.
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
    :class:`~domain.calculations.registry.schema.ModeloRevision`. Callers use
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
