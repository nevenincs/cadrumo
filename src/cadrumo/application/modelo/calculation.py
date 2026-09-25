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

Core types:
:class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.hashing import content_hash_hex
from ..producer_capture import ProducerCapture, ProducerCaptureCoordinate, ProducerCaptureScope
from .calculation_revision_gate import require_calculation_revision_coordinates_current

if TYPE_CHECKING:
    from collections.abc import Mapping
    from decimal import Decimal

    from ...core.casilla_id import CasillaId
    from ...core.identity.hex_ids import CalculationRevisionId
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.bindings import CasillaObservation
    from ...domain.modelos.calculation_revision import CalculationRevision
    from .calculation_action_ports import CalculationActionPorts


_CALCULATION_CAPTURE_SCOPE = ProducerCaptureScope(
    owner="application.modelo.calculation",
    namespace="modelo.calculation_revision",
)


def _calculation_owner_observation(*, ports: CalculationActionPorts) -> tuple[str, ...]:
    """Read the two catalogue limbs a materialized revision is a function of.

    A calculation revision is resolved out of the calculation catalogue and
    validated against the work-unit catalogue that owns it, so a write to
    either between two reads makes the revision a stitch across two states.
    """
    _calculations, calculation_revision = ports.calculation_repository.load_revisioned()
    _work_units, work_unit_revision = ports.work_unit_repository.load_revisioned()
    return (calculation_revision, work_unit_revision)


def _calculation_capture_coordinate(calculation_revision_id: CalculationRevisionId) -> dict[str, object]:
    return {"calculation_revision_id": content_hash_hex({"id": str(calculation_revision_id)})}


def read_modelo_calculation_current_coordinate(
    calculation_revision_id: CalculationRevisionId,
    *,
    ports: CalculationActionPorts,
) -> ProducerCaptureCoordinate:
    """Return the typed current coordinate for same-domain capture validation."""
    return _CALCULATION_CAPTURE_SCOPE.read_current_coordinate(
        coordinate=_calculation_capture_coordinate(calculation_revision_id),
        observe=lambda: _calculation_owner_observation(ports=ports),
    )


def capture_modelo_calculation(
    calculation_revision_id: CalculationRevisionId,
    *,
    ports: CalculationActionPorts,
) -> ProducerCapture[CalculationRevision]:
    """Materialize one calculation revision over a window in which it did not move.

    The revision is exactly what the sole calculation-revision authority
    (:func:`~cadrumo.application.modelo.calculation_actions.get_calculation_revision`)
    returned. This module computes nothing and reconstructs nothing; it adds
    the currentness coordinate a pinned multi-producer read needs.
    """
    from .calculation_actions import get_calculation_revision

    return _CALCULATION_CAPTURE_SCOPE.capture(
        coordinate=_calculation_capture_coordinate(calculation_revision_id),
        observe=lambda: _calculation_owner_observation(ports=ports),
        build=lambda: get_calculation_revision(calculation_revision_id, ports=ports),
    )


def visible_calculation_casilla_values(
    revision: CalculationRevision,
    *,
    operation: PinnedAuthorityOperation,
) -> Mapping[CasillaId, Decimal]:
    """Return the casilla values of a persisted revision that an operator should see.

    The write path has already removed registry-declared row templates. The read
    path first re-confirms the persisted canonical coordinate and never guesses
    semantic membership from an identifier prefix.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
    """
    require_calculation_revision_coordinates_current(revision, operation=operation)
    return revision.casilla_values


def visible_calculation_observations(
    revision: CalculationRevision,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[CasillaObservation, ...]:
    """Return the observations of a persisted revision that an operator should see.

    This is the observation-stream counterpart of
    :func:`visible_calculation_casilla_values` and applies the same canonical
    revision re-confirmation before returning the write-time materialization.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
    """
    require_calculation_revision_coordinates_current(revision, operation=operation)
    return revision.observations


__all__ = [
    "capture_modelo_calculation",
    "read_modelo_calculation_current_coordinate",
    "visible_calculation_casilla_values",
    "visible_calculation_observations",
]
