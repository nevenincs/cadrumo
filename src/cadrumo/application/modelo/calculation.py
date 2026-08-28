"""Public calculation materialization capture for one persisted revision.

This module owns the operator-facing capture contract over a materialized
:class:`~cadrumo.domain.modelos.CalculationRevision`. It computes nothing: the
revision and its provenance come from the sole calculation-revision authority
in :mod:`cadrumo.application.modelo._calculation_actions`, which remains a
package-private implementation collaborator. There is no parallel calculation,
source-graph, persistence or redaction path here, and none may be added.

The capture is source-graph-safe because it republishes the revision exactly as
the authority materialized it. The revision already carries its own casilla
provenance, so no separate graph projection is derived and no locator is
re-exposed outside the record that owns it.

See Also:
    :class:`~cadrumo.domain.modelos.CalculationRevision`
        The materialized record this module captures without reconstruction.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from secrets import token_bytes
from threading import RLock
from typing import TYPE_CHECKING

from ...core.errors import CadrumoError
from ...core.hashing import content_hash_hex
from ._calculation_actions import get_calculation_revision

if TYPE_CHECKING:
    from ...core.identity import CalculationRevisionId
    from ...domain.modelos import CalculationRevision, CalculationRevisionCatalogueRepositoryProtocol

_CALCULATION_CAPTURE_MAX_ATTEMPTS = 8
_calculation_capture_process_pid = os.getpid()
_calculation_capture_process_nonce = token_bytes(32)
_calculation_capture_domains: set[str] = set()
_calculation_capture_lock = RLock()
_calculation_capture_generations: dict[str, tuple[tuple[str, ...], int]] = {}
_calculation_capture_generation = 0


class ModeloCalculationCaptureError(CadrumoError, RuntimeError):
    """Raised when a calculation cannot be captured over one stable window."""


@dataclass(frozen=True, slots=True)
class ModeloCalculationCapture:
    """One materialized calculation revision and its currentness coordinate.

    ``revision`` is exactly what the calculation-revision authority returned;
    no field is reconstructed and no source graph is re-derived. The physical
    storage root, bucket and revision identity are folded into the opaque
    comparison domain and never exposed.
    """

    revision: CalculationRevision
    comparison_domain: str
    generation: int

    def require_current(self, current: ModeloCalculationCurrentCoordinate) -> ModeloCalculationCapture:
        """Refuse a currentness comparison outside this owner process domain."""
        _require_calculation_process_domain(self.comparison_domain)
        current.require_current(self)
        return self


@dataclass(frozen=True, slots=True)
class ModeloCalculationCurrentCoordinate:
    """Opaque same-process coordinate for one calculation owner scope."""

    comparison_domain: str
    generation: int

    def require_current(self, captured: ModeloCalculationCapture) -> ModeloCalculationCurrentCoordinate:
        """Require a capture from this exact owner scope and process incarnation."""
        _require_calculation_process_domain(self.comparison_domain)
        _require_calculation_process_domain(captured.comparison_domain)
        if self.comparison_domain != captured.comparison_domain:
            raise ModeloCalculationCaptureError(
                translated_message="errors.refused.modelo_calculation_capture_not_current",
                context={"reason": "distinct_owner_scope"},
            )
        if self.generation != captured.generation:
            raise ModeloCalculationCaptureError(
                translated_message="errors.refused.modelo_calculation_capture_not_current",
                context={"reason": "capture_superseded"},
            )
        return self


def _require_calculation_process_domain(domain: str) -> None:
    """Refuse a coordinate domain not minted in this process incarnation."""
    if _calculation_capture_process_pid != os.getpid():
        raise ModeloCalculationCaptureError(
            translated_message="errors.refused.modelo_calculation_capture_not_current",
            context={"reason": "forked_process"},
        )
    with _calculation_capture_lock:
        known = domain in _calculation_capture_domains
    if not known:
        raise ModeloCalculationCaptureError(
            translated_message="errors.refused.modelo_calculation_capture_not_current",
            context={"reason": "foreign_process_incarnation"},
        )


def _calculation_comparison_domain(calculation_revision_id: CalculationRevisionId) -> str:
    """Mint the non-persisted coordinate domain for one calculation owner scope."""
    from ...core.config import load_settings

    domain = content_hash_hex(
        {
            "owner": "application.modelo.calculation",
            "storage_root": str(load_settings().cadrumo_local_storage_root),
            "namespace": "modelo.calculation_revision",
            "calculation_revision_id": str(calculation_revision_id),
            "process_incarnation": _calculation_capture_process_nonce.hex(),
        }
    )
    with _calculation_capture_lock:
        _calculation_capture_domains.add(domain)
    return domain


def _calculation_owner_observation(
    calculation_revision_id: CalculationRevisionId,
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
) -> tuple[str, ...]:
    """Read the calculation catalogue limb backing one revision id."""
    from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository

    repository = calculation_repository or CalculationRevisionCatalogueRepository()
    _catalogue, catalogue_revision = repository.load_revisioned()
    return (str(calculation_revision_id), catalogue_revision)


def _calculation_generation_for(domain: str, observation: tuple[str, ...]) -> int:
    """Assign one injective, order-preserving generation per distinct observation."""
    global _calculation_capture_generation
    with _calculation_capture_lock:
        recorded = _calculation_capture_generations.get(domain)
        if recorded is not None and recorded[0] == observation:
            return recorded[1]
        _calculation_capture_generation += 1
        _calculation_capture_generations[domain] = (observation, _calculation_capture_generation)
        return _calculation_capture_generation


def read_modelo_calculation_current_coordinate(
    calculation_revision_id: CalculationRevisionId,
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> ModeloCalculationCurrentCoordinate:
    """Return the typed current coordinate for same-domain capture validation."""
    observation = _calculation_owner_observation(
        calculation_revision_id,
        calculation_repository=calculation_repository,
    )
    domain = _calculation_comparison_domain(calculation_revision_id)
    return ModeloCalculationCurrentCoordinate(
        comparison_domain=domain,
        generation=_calculation_generation_for(domain, observation),
    )


def capture_modelo_calculation(
    calculation_revision_id: CalculationRevisionId,
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
) -> ModeloCalculationCapture:
    """Materialize one calculation revision over a window in which it did not move.

    The catalogue limb is read either side of the sole
    :func:`~cadrumo.application.modelo._calculation_actions.get_calculation_revision`
    authority, so a write landing mid-read is retried rather than published as a
    revision paired with a coordinate from another catalogue state.
    """
    for _attempt in range(_CALCULATION_CAPTURE_MAX_ATTEMPTS):
        before = _calculation_owner_observation(
            calculation_revision_id,
            calculation_repository=calculation_repository,
        )
        revision = get_calculation_revision(
            calculation_revision_id,
            calculation_repository=calculation_repository,
        )
        after = _calculation_owner_observation(
            calculation_revision_id,
            calculation_repository=calculation_repository,
        )
        if before != after:
            continue
        domain = _calculation_comparison_domain(calculation_revision_id)
        return ModeloCalculationCapture(
            revision=revision,
            comparison_domain=domain,
            generation=_calculation_generation_for(domain, after),
        )
    raise ModeloCalculationCaptureError(
        translated_message="errors.refused.modelo_calculation_capture_not_current",
        context={"reason": "contended", "attempts": _CALCULATION_CAPTURE_MAX_ATTEMPTS},
    )


__all__ = [
    "ModeloCalculationCapture",
    "ModeloCalculationCaptureError",
    "ModeloCalculationCurrentCoordinate",
    "capture_modelo_calculation",
    "read_modelo_calculation_current_coordinate",
]
