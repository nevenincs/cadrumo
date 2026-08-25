"""The one identifier naming a validated registry snapshot.

A registry snapshot is addressed by four coordinates -- modelo, revision,
filing year, and period -- because AEAT binds each ``(modelo, filing_year,
period)`` triple to exactly one revision by published orden. Dropping any of
them produces an identifier that two genuinely different snapshots can share.

Two Modelo 130 declarations for 2025/1T and 2026/1T both resolve revision
``2019-y-siguientes``, so a modelo-plus-revision identifier names them
identically. Reports and persisted observations correlate on this value, so a
collision silently merges the provenance of separate filings.

See Also:
    :class:`~domain.calculations.registry.RegistrySnapshot`
        The snapshot this identifier names.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core.identity import RegistrySnapshotId
from .ids import RevisionId

if TYPE_CHECKING:
    from .schema import RegistrySnapshot


def registry_snapshot_id(
    *,
    modelo: str,
    revision_id: RevisionId,
    filing_year: int,
    period: str,
) -> RegistrySnapshotId:
    """Return the canonical identifier for one validated registry snapshot.

    The coordinates are passed explicitly rather than read from a snapshot
    because not every caller's authoritative coordinates come from one. A
    parsed declaration stamps the year and period the DOCUMENT declares, which
    is what makes a later comparison against the law-resolved snapshot able to
    detect a mismatch; sourcing both sides from the snapshot would make that
    comparison tautological.

    Args:
        modelo: Stable modelo identifier, e.g. ``130``.
        revision_id: Registry revision identifier, e.g. ``2019-y-siguientes``.
        filing_year: The filing year the snapshot was resolved for.
        period: Registry period token, e.g. ``1T``.

    Returns:
        The colon-joined four-coordinate identifier.
    """
    return f"{modelo}:{revision_id}:{filing_year}:{period}"


def registry_snapshot_id_for(snapshot: RegistrySnapshot) -> RegistrySnapshotId:
    """Return the canonical identifier for ``snapshot``'s own coordinates.

    Use this when the snapshot IS the authority for all four coordinates. When
    the year and period come from a parsed artefact instead, call
    :func:`registry_snapshot_id` with those values.

    Args:
        snapshot: The :class:`RegistrySnapshot` whose modelo, revision,
            filing year, and period supply the four identity coordinates.
    """
    return registry_snapshot_id(
        modelo=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )


__all__ = ["registry_snapshot_id", "registry_snapshot_id_for"]
