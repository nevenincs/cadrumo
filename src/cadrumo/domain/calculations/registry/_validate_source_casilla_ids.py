"""Shared source-casilla-id helpers for cross-model validation.

Returns the canonical :class:`~core.CasillaId`
values a :class:`~domain.calculations.registry.ModeloRevision` can expose
to cross-model relation validators.

See Also:
    :mod:`domain.calculations.registry._casilla_membership`
        Declared-id membership and non-canonical metadata-token lookup.
    :mod:`domain.calculations.registry._validate_relation_sources`
        Relation source validation that consumes these canonical outputs.
    :mod:`domain.calculations.registry._validate_previous_filing_sources`
        Previous-filing binding validation that shares the same source check.
"""

from __future__ import annotations

from ....core import CasillaId
from .casilla_membership import casilla_noncanonical_reference_targets, declared_casilla_ids
from .schema import ModeloRevision


def revision_output_ids(revision: ModeloRevision) -> set[CasillaId]:
    """Return canonical source ids exposed by one registry revision.

    The returned :class:`~core.CasillaId` set is the casillas declared by the
    supplied :class:`~domain.calculations.registry.ModeloRevision`.
    """
    return set(declared_casilla_ids(revision))


def source_casilla_id_reference_failure(
    revision: ModeloRevision,
    source_casilla_id: CasillaId,
    *,
    source_scope: str,
    missing_failure: str,
) -> list[str]:
    """Return closure failures for a source casilla reference, if invalid.

    Cross-revision source references consume only canonical ``casilla.id`` values.
    Display numbers, form numbers, and export refs are refused even when they map
    to exactly one source casilla; the diagnostic names the canonical candidate so
    the author fixes the registry source instead of treating the token as unknown.

    Returns a single-item list on failure, empty on success -- ``list[str]``
    rather than ``str | None`` so every call site accumulates it the same way
    as every sibling validator (``failures.extend(...)``), with no special
    case for a check that happens to report at most one finding today.

    Args:
        revision: Source
            :class:`~domain.calculations.registry.ModeloRevision` whose
            canonical outputs are available to relation or previous-filing
            closure.
        source_casilla_id: Candidate
            :class:`~core.CasillaId` source
            reference token to validate.
        source_scope: Human-readable scope prefix for the emitted failure.
        missing_failure: Failure message to reuse for a truly unknown source id.
    """
    if source_casilla_id in revision_output_ids(revision):
        return []
    noncanonical_targets = casilla_noncanonical_reference_targets(revision, source_casilla_id)
    if noncanonical_targets:
        rendered_targets = ", ".join(noncanonical_targets)
        if len(noncanonical_targets) > 1:
            return [
                f"{source_scope} source casilla id {source_casilla_id!r} is not a canonical casilla.id "
                f"and is ambiguous; candidate casilla.id values: {rendered_targets}"
            ]
        return [
            f"{source_scope} source casilla id {source_casilla_id!r} is not a canonical casilla.id; "
            f"use canonical casilla.id {rendered_targets!r}"
        ]
    return [missing_failure]
