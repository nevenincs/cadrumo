"""Currentness captures for Modelo work catalogue selections."""

from __future__ import annotations

import os
from dataclasses import dataclass
from secrets import token_bytes
from threading import RLock

from ...core.hashing import content_hash_hex
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from .work_addressing import ModeloWorkSelectorContradictionError, ModeloWorkSelectorError
from .work_selection import (
    ModeloWorkResolution,
    ModeloWorkSelectionMode,
    ModeloWorkSelectorRequest,
    resolve_modelo_work_bucket,
    select_modelo_work_resolution,
)

_WORK_CAPTURE_MAX_ATTEMPTS = 8
_work_capture_process_pid = os.getpid()
_work_capture_process_nonce = token_bytes(32)
_work_capture_domains: set[str] = set()
_work_capture_lock = RLock()
_work_capture_generations: dict[str, tuple[tuple[str, ...], int]] = {}
_work_capture_generation = 0


class ModeloWorkCaptureError(ModeloWorkSelectorError):
    """Raised when a work capture cannot reach one uncontended observation."""


@dataclass(frozen=True, slots=True)
class ModeloWorkCapture:
    """One isolated work resolution and its currentness coordinate.

    The capture carries the strict frozen :class:`ModeloWorkResolution` selected
    over exactly one catalogue read, plus an opaque comparison domain and a
    generation. The physical storage root, bucket, namespace and object key that
    produced it are folded into the domain digest and are never exposed.
    """

    resolution: ModeloWorkResolution
    comparison_domain: str
    generation: int

    def require_current(self, current: ModeloWorkCurrentCoordinate) -> ModeloWorkCapture:
        """Refuse a currentness comparison outside this physical process domain."""
        _require_work_capture_process_domain(self.comparison_domain)
        current.require_current(self)
        return self


@dataclass(frozen=True, slots=True)
class ModeloWorkCurrentCoordinate:
    """Opaque same-process coordinate for one work catalogue owner scope."""

    comparison_domain: str
    generation: int

    def require_current(self, captured: ModeloWorkCapture) -> ModeloWorkCurrentCoordinate:
        """Require a capture from this exact scope and process incarnation."""
        _require_work_capture_process_domain(self.comparison_domain)
        _require_work_capture_process_domain(captured.comparison_domain)
        if self.comparison_domain != captured.comparison_domain:
            raise ModeloWorkCaptureError(
                translated_message="errors.refused.modelo_work_capture_not_current",
                context={"reason": "distinct_owner_scope"},
            )
        if self.generation != captured.generation:
            raise ModeloWorkCaptureError(
                translated_message="errors.refused.modelo_work_capture_not_current",
                context={"reason": "capture_superseded"},
            )
        return self


def _require_work_capture_process_domain(domain: str) -> None:
    """Refuse a coordinate domain not minted in this process incarnation."""
    if _work_capture_process_pid != os.getpid():
        raise ModeloWorkCaptureError(
            translated_message="errors.refused.modelo_work_capture_not_current",
            context={"reason": "forked_process"},
        )
    with _work_capture_lock:
        known = domain in _work_capture_domains
    if not known:
        raise ModeloWorkCaptureError(
            translated_message="errors.refused.modelo_work_capture_not_current",
            context={"reason": "foreign_process_incarnation"},
        )


def _work_capture_comparison_domain(*, bucket_id: str, implicit: bool) -> str:
    """Mint the non-persisted coordinate domain for one owner scope."""
    from ...core.config import load_settings

    domain = content_hash_hex(
        {
            "owner": "application.modelo.work_addressing",
            "storage_root": str(load_settings().cadrumo_local_storage_root),
            "namespace": "modelo.work_unit_catalogue",
            "bucket_id": bucket_id,
            "implicit_pointer_limb": implicit,
            "process_incarnation": _work_capture_process_nonce.hex(),
        }
    )
    with _work_capture_lock:
        _work_capture_domains.add(domain)
    return domain


def _work_pointer_limb() -> str:
    """Return the implicit pointer limb coordinate for the active storage root."""
    from ...core.bucket_pointer import pointer_path
    from ...core.config import load_settings
    from ...core.paths import path_stat_fingerprint

    target = pointer_path(load_settings().cadrumo_local_storage_root)
    try:
        return content_hash_hex(path_stat_fingerprint(target))
    except OSError:
        return "absent"


def _work_capture_generation_for(domain: str, observation: tuple[str, ...]) -> int:
    """Assign one injective, order-preserving generation per distinct observation."""
    global _work_capture_generation
    with _work_capture_lock:
        recorded = _work_capture_generations.get(domain)
        if recorded is not None and recorded[0] == observation:
            return recorded[1]
        _work_capture_generation += 1
        _work_capture_generations[domain] = (observation, _work_capture_generation)
        return _work_capture_generation


def _work_capture_observation(
    request: ModeloWorkSelectorRequest,
    *,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
) -> tuple[str, WorkUnitCatalogue, tuple[str, ...], bool]:
    """Read the pointer and one catalogue record until the two limbs agree."""
    implicit = request.bucket_id is None
    for _attempt in range(_WORK_CAPTURE_MAX_ATTEMPTS):
        limb_before = _work_pointer_limb() if implicit else None
        bucket_id = resolve_modelo_work_bucket(request)
        catalogue, revision_id = catalogue_repository.load_revisioned()
        if implicit and _work_pointer_limb() != limb_before:
            continue
        observation: tuple[str, ...]
        if implicit:
            if limb_before is None:
                raise ModeloWorkSelectorContradictionError(
                    "implicit pointer observation requires the limb the pointer held before",
                )
            observation = (limb_before, revision_id)
        else:
            observation = (revision_id,)
        return bucket_id, catalogue, observation, implicit
    raise ModeloWorkCaptureError(
        translated_message="errors.refused.modelo_work_capture_not_current",
        context={"attempts": _WORK_CAPTURE_MAX_ATTEMPTS},
    )


def capture_modelo_work_resolution(
    request: ModeloWorkSelectorRequest,
    *,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
    mode: ModeloWorkSelectionMode = ModeloWorkSelectionMode.VISIBLE_OR_EXACT,
) -> ModeloWorkCapture:
    """Atomically capture one work resolution over a single catalogue read.

    The implicit pointer limb and the one-record catalogue coordinate are read
    so that a pointer replacement interleaved with the catalogue read is retried
    rather than composed, which is what defeats a pointer/catalogue ABA. An
    explicit ``bucket_id`` excludes the pointer limb entirely while still
    carrying the catalogue generation. No registry is consulted and the
    catalogue is read exactly once per successful attempt.
    """
    bucket_id, catalogue, observation, implicit = _work_capture_observation(
        request,
        catalogue_repository=catalogue_repository,
    )
    resolution = select_modelo_work_resolution(
        request,
        catalogue=catalogue,
        bucket_id=bucket_id,
        mode=mode,
    )
    domain = _work_capture_comparison_domain(bucket_id=bucket_id, implicit=implicit)
    return ModeloWorkCapture(
        resolution=resolution,
        comparison_domain=domain,
        generation=_work_capture_generation_for(domain, observation),
    )


def read_modelo_work_current_coordinate(
    request: ModeloWorkSelectorRequest,
    *,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
) -> ModeloWorkCurrentCoordinate:
    """Read the coordinate a later pass compares a work capture against.

    The same pointer and catalogue limbs :func:`capture_modelo_work_resolution`
    observes, in the same owner domain, so a catalogue write since the capture
    yields a different generation.
    """
    bucket_id, _catalogue, observation, implicit = _work_capture_observation(
        request,
        catalogue_repository=catalogue_repository,
    )
    domain = _work_capture_comparison_domain(bucket_id=bucket_id, implicit=implicit)
    return ModeloWorkCurrentCoordinate(
        comparison_domain=domain,
        generation=_work_capture_generation_for(domain, observation),
    )
