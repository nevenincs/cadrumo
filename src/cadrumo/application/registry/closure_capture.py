"""Public registry-closure native atomic capture over filing-export coverage.

This module owns the capture contract over the registry release predicate; it
computes nothing of its own. ``compose_filing_export_coverage`` remains the
sole owner of limb derivation; this module republishes its limbs with a
currentness coordinate.

Filing byte-evidence can move independently of the registry snapshot because
it reads corpus files whose content is not tracked by snapshot identity. An
independent native generation therefore remains required.

See Also:
    :func:`~cadrumo.application.registry.filing_export_coverage.compose_filing_export_coverage`
        The sole authority this module captures without reimplementation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from secrets import token_bytes
from threading import RLock

from ...core.errors.hierarchy import CadrumoError
from ...core.hashing import content_hash_hex
from ...domain.calculations.registry.authority import ValidatedRegistryAuthority
from ..filing.export_proof import FilingExportProofAuthority
from .closure import RegistryClosureLimb
from .filing_export_coverage import compose_filing_export_coverage

_closure_capture_process_pid = os.getpid()
_closure_capture_process_nonce = token_bytes(32)
_closure_capture_domains: set[str] = set()
_closure_capture_lock = RLock()
_closure_capture_generations: dict[str, tuple[str, int]] = {}
_closure_capture_generation = 0


class RegistryClosureCaptureError(CadrumoError, RuntimeError):
    """Raised when the registry closure cannot be captured over one stable window."""


@dataclass(frozen=True, slots=True)
class RegistryClosureCapture:
    """Every filing-export closure limb and its coordinate.

    ``limbs`` republishes exactly what the filing-export composer returned in
    ``(modelo, revision)`` order. No field is reconstructed. The process
    incarnation is folded into the opaque comparison domain and never exposed.
    """

    limbs: tuple[RegistryClosureLimb, ...]
    comparison_domain: str
    generation: int

    def require_current(self, current: RegistryClosureCurrentCoordinate) -> RegistryClosureCapture:
        """Refuse a currentness comparison outside this owner process domain."""
        _require_closure_process_domain(self.comparison_domain)
        current.require_current(self)
        return self


@dataclass(frozen=True, slots=True)
class RegistryClosureCurrentCoordinate:
    """Opaque same-process coordinate for the registry-closure owner scope."""

    comparison_domain: str
    generation: int

    def require_current(self, captured: RegistryClosureCapture) -> RegistryClosureCurrentCoordinate:
        """Require a capture from this exact owner scope and process incarnation."""
        _require_closure_process_domain(self.comparison_domain)
        _require_closure_process_domain(captured.comparison_domain)
        if self.comparison_domain != captured.comparison_domain:
            raise RegistryClosureCaptureError(
                translated_message="errors.refused.registry_closure_capture_not_current",
                context={"reason": "distinct_owner_scope"},
            )
        if self.generation != captured.generation:
            raise RegistryClosureCaptureError(
                translated_message="errors.refused.registry_closure_capture_not_current",
                context={"reason": "capture_superseded"},
            )
        return self


def _require_closure_process_domain(domain: str) -> None:
    """Refuse a coordinate domain not minted in this process incarnation."""
    if _closure_capture_process_pid != os.getpid():
        raise RegistryClosureCaptureError(
            translated_message="errors.refused.registry_closure_capture_not_current",
            context={"reason": "forked_process"},
        )
    with _closure_capture_lock:
        known = domain in _closure_capture_domains
    if not known:
        raise RegistryClosureCaptureError(
            translated_message="errors.refused.registry_closure_capture_not_current",
            context={"reason": "foreign_process_incarnation"},
        )


def _closure_comparison_domain() -> str:
    """Mint the non-persisted coordinate domain for the registry-closure owner scope."""
    domain = content_hash_hex(
        {
            "owner": "application.registry.closure_capture",
            "namespace": "registry.closure",
            "process_incarnation": _closure_capture_process_nonce.hex(),
        }
    )
    with _closure_capture_lock:
        _closure_capture_domains.add(domain)
    return domain


def _closure_limbs(
    *,
    authority: ValidatedRegistryAuthority,
    filing_proof_authority: FilingExportProofAuthority | None,
) -> tuple[RegistryClosureLimb, ...]:
    filing_report = compose_filing_export_coverage(authority=authority, proof_authority=filing_proof_authority)
    return filing_report.limbs


def _closure_observation(limbs: tuple[RegistryClosureLimb, ...]) -> str:
    """Fingerprint the composed limb content, the sole signal closure movement needs."""
    return content_hash_hex([limb.model_dump(mode="json") for limb in limbs])


def _closure_generation_for(domain: str, observation: str) -> int:
    """Assign one injective, order-preserving generation per distinct observation."""
    global _closure_capture_generation
    with _closure_capture_lock:
        recorded = _closure_capture_generations.get(domain)
        if recorded is not None and recorded[0] == observation:
            return recorded[1]
        _closure_capture_generation += 1
        _closure_capture_generations[domain] = (observation, _closure_capture_generation)
        return _closure_capture_generation


def read_registry_closure_current_coordinate(
    *,
    authority: ValidatedRegistryAuthority,
    filing_proof_authority: FilingExportProofAuthority | None = None,
) -> RegistryClosureCurrentCoordinate:
    """Return the typed current coordinate for same-domain capture validation."""
    limbs = _closure_limbs(
        authority=authority,
        filing_proof_authority=filing_proof_authority,
    )
    domain = _closure_comparison_domain()
    return RegistryClosureCurrentCoordinate(
        comparison_domain=domain,
        generation=_closure_generation_for(domain, _closure_observation(limbs)),
    )


def capture_registry_closure(
    *,
    authority: ValidatedRegistryAuthority,
    filing_proof_authority: FilingExportProofAuthority | None = None,
) -> RegistryClosureCapture:
    """Compose filing-export closure and stamp it with a currentness coordinate.

    Unlike a shard or catalogue read, composing closure has no concurrent
    in-process writer to race: ``authority`` is already loaded and the live
    proof authority is the read itself, not
    a mutable store a retry could observe settling. A single composition is
    therefore the whole read; the coordinate records what it produced rather
    than reproving it did not move mid-read.
    """
    limbs = _closure_limbs(
        authority=authority,
        filing_proof_authority=filing_proof_authority,
    )
    domain = _closure_comparison_domain()
    return RegistryClosureCapture(
        limbs=limbs,
        comparison_domain=domain,
        generation=_closure_generation_for(domain, _closure_observation(limbs)),
    )


__all__ = [
    "RegistryClosureCapture",
    "RegistryClosureCaptureError",
    "RegistryClosureCurrentCoordinate",
    "capture_registry_closure",
    "read_registry_closure_current_coordinate",
]
