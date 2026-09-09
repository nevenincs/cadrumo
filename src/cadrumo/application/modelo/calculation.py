"""Public calculation materialization capture for one persisted revision.

This module owns the operator-facing capture contract over a materialized
:class:`~CalculationRevision`. It computes nothing: the
revision and its provenance come from the sole calculation-revision authority
in :mod:`cadrumo.application.modelo.calculation_actions`, which remains a
package-private implementation collaborator. There is no parallel calculation,
source-graph, persistence or redaction path here, and none may be added.

The capture is source-graph-safe because it republishes the revision exactly as
the authority materialized it. The revision already carries its own casilla
provenance, so no separate graph projection is derived and no locator is
re-exposed outside the record that owns it.

See Also:
    :class:`~CalculationRevision`
        The materialized record this module captures without reconstruction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .calculation_revision_gate import require_calculation_revision_coordinates_current

if TYPE_CHECKING:
    from collections.abc import Mapping
    from decimal import Decimal

    from ...core.casilla_id import CasillaId
    from ...domain.calculations.registry.bindings import CasillaObservation
    from ...domain.modelos.calculation_revision import CalculationRevision


def visible_calculation_casilla_values(revision: CalculationRevision) -> Mapping[CasillaId, Decimal]:
    """Return the casilla values of a persisted revision that an operator should see.

    The write path has already removed registry-declared row templates. The read
    path first re-confirms the persisted canonical coordinate and never guesses
    semantic membership from an identifier prefix.
    """
    require_calculation_revision_coordinates_current(revision)
    return revision.casilla_values


def visible_calculation_observations(revision: CalculationRevision) -> tuple[CasillaObservation, ...]:
    """Return the observations of a persisted revision that an operator should see.

    This is the observation-stream counterpart of
    :func:`visible_calculation_casilla_values` and applies the same canonical
    revision re-confirmation before returning the write-time materialization.
    """
    require_calculation_revision_coordinates_current(revision)
    return revision.observations


__all__ = [
    "visible_calculation_casilla_values",
    "visible_calculation_observations",
]
