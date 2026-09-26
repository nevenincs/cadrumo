"""One stable-window capture mechanism for application producer projections.

A Workspace read pins several independent producers into one baseline, and the
baseline is only worth anything if each producer's contribution was observed
over a window in which that producer did not move. Every such producer needs
the same four things: an opaque owner-scoped comparison domain, an injective
generation per distinct observation, a build retried when the observation moved
under it, and a refusal when a coordinate from another owner scope or another
process incarnation is compared against a capture.

Those four things are written once here rather than once per producer. The
older Workspace contributors each carry their own open-coded copy of this
mechanism; this module exists so that the producers wired after them share one
implementation instead of adding further copies, and so a future consolidation
has one place to consolidate ONTO.

The comparison domain is opaque on purpose: it folds the storage root, the
owner, the namespace, the producer's own coordinate and a per-process nonce
into a digest, so it names a scope without exposing a path, a bucket or any
taxpayer coordinate to a caller holding a capture.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from secrets import token_bytes
from threading import RLock

from ..core.errors.hierarchy import CadrumoError
from ..core.hashing import content_hash_hex

__all__ = [
    "ProducerCapture",
    "ProducerCaptureCoordinate",
    "ProducerCaptureError",
    "ProducerCaptureScope",
]

_CAPTURE_MAX_ATTEMPTS = 8
_capture_process_pid = os.getpid()
_capture_process_nonce = token_bytes(32)
_capture_domains: set[str] = set()
_capture_lock = RLock()
_capture_generations: dict[str, tuple[tuple[str, ...], int]] = {}
_capture_generation = 0


class ProducerCaptureError(CadrumoError):
    """Raised when a producer projection cannot be captured over one stable window."""


def _refusal(reason: str, **context: object) -> ProducerCaptureError:
    return ProducerCaptureError(
        translated_message="errors.refused.producer_capture_not_current",
        context={"reason": reason, **context},
    )


def _require_process_domain(domain: str) -> None:
    """Refuse a coordinate domain not minted in this process incarnation.

    A forked child inherits the parent's generation table while owning none of
    the state it describes, so every domain it reads is a claim about another
    process. Refusing the whole comparison is the only safe answer.
    """
    if _capture_process_pid != os.getpid():
        raise _refusal("forked_process")
    with _capture_lock:
        known = domain in _capture_domains
    if not known:
        raise _refusal("foreign_process_incarnation")


@dataclass(frozen=True, slots=True)
class ProducerCaptureCoordinate:
    """Opaque same-process currentness coordinate for one producer owner scope."""

    comparison_domain: str
    generation: int

    def require_current[ValueT](self, captured: ProducerCapture[ValueT]) -> ProducerCaptureCoordinate:
        """Require a capture from this exact owner scope and process incarnation."""
        _require_process_domain(self.comparison_domain)
        _require_process_domain(captured.comparison_domain)
        if self.comparison_domain != captured.comparison_domain:
            raise _refusal("distinct_owner_scope")
        if self.generation != captured.generation:
            raise _refusal("capture_superseded")
        return self


@dataclass(frozen=True, slots=True)
class ProducerCapture[ValueT]:
    """One producer projection and the currentness coordinate it was read under.

    ``value`` is exactly what the producer returned. Nothing here reshapes,
    recomputes or redacts it: the capture adds a coordinate, never a second
    opinion about the projection's content.
    """

    value: ValueT
    comparison_domain: str
    generation: int

    def require_current(self, current: ProducerCaptureCoordinate) -> ProducerCapture[ValueT]:
        """Refuse a currentness comparison outside this owner process domain."""
        _require_process_domain(self.comparison_domain)
        current.require_current(self)
        return self


@dataclass(frozen=True, slots=True)
class ProducerCaptureScope:
    """The owner and namespace one producer's captures are scoped to.

    Two producers with distinct ``owner``/``namespace`` pairs can never mint
    the same comparison domain, so a coordinate from one can never be accepted
    as current for the other even when their coordinates coincide.
    """

    owner: str
    namespace: str

    def comparison_domain(self, coordinate: Mapping[str, object]) -> str:
        """Mint and register the non-persisted domain for one owner coordinate."""
        from ..core.config import load_settings

        domain = content_hash_hex(
            {
                "owner": self.owner,
                "namespace": self.namespace,
                "storage_root": str(load_settings().cadrumo_local_storage_root),
                "coordinate": dict(sorted((key, str(value)) for key, value in coordinate.items())),
                "process_incarnation": _capture_process_nonce.hex(),
            }
        )
        with _capture_lock:
            _capture_domains.add(domain)
        return domain

    def read_current_coordinate(
        self,
        *,
        coordinate: Mapping[str, object],
        observe: Callable[[], Sequence[str]],
    ) -> ProducerCaptureCoordinate:
        """Return the typed current coordinate for same-domain capture validation."""
        observation = tuple(observe())
        domain = self.comparison_domain(coordinate)
        return ProducerCaptureCoordinate(
            comparison_domain=domain,
            generation=_generation_for(domain, observation),
        )

    def capture[ValueT](
        self,
        *,
        coordinate: Mapping[str, object],
        observe: Callable[[], Sequence[str]],
        build: Callable[[], ValueT],
    ) -> ProducerCapture[ValueT]:
        """Build one projection over a window in which its owner limbs did not move.

        ``observe`` is read either side of ``build``. A write landing
        mid-build is retried rather than published, so a capture never pairs a
        projection with a coordinate taken from a different owner state.
        """
        for _attempt in range(_CAPTURE_MAX_ATTEMPTS):
            before = tuple(observe())
            value = build()
            after = tuple(observe())
            if before != after:
                continue
            domain = self.comparison_domain(coordinate)
            return ProducerCapture(
                value=value,
                comparison_domain=domain,
                generation=_generation_for(domain, after),
            )
        raise _refusal("contended", attempts=_CAPTURE_MAX_ATTEMPTS)


def _generation_for(domain: str, observation: tuple[str, ...]) -> int:
    """Assign one injective, order-preserving generation per distinct observation."""
    global _capture_generation
    with _capture_lock:
        recorded = _capture_generations.get(domain)
        if recorded is not None and recorded[0] == observation:
            return recorded[1]
        _capture_generation += 1
        _capture_generations[domain] = (observation, _capture_generation)
        return _capture_generation
