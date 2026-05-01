"""Concrete observability errors layered over :class:`AeatObservabilityError`.

The base class :class:`AeatObservabilityError` lives in
:mod:`aeat.core.errors` so other subpackages can catch it without importing
observability internals (see ADR D8). This module re-exports it and
declares the leaf error types raised inside the observability layer.
"""

from __future__ import annotations

from ..errors import AeatObservabilityError


class RunContextMissingError(AeatObservabilityError):
    """Raised when an observability call is made outside an active run context."""

    pass


class RunTraceValidationError(AeatObservabilityError):
    """Raised when persisted JSONL or trace.json fails strict validation."""

    pass


class AeatCorpusDriftError(AeatObservabilityError):
    """Raised when replay detects that ``corpus_sha256`` has drifted.

    Carries both the recorded and observed hashes plus the entrypoint
    so the caller can render an actionable diff. Replay is the only
    call site that raises this.
    """

    def __init__(
        self,
        *,
        run_id: str,
        recorded: str,
        observed: str,
        entrypoint: str,
    ) -> None:
        """Construct a corpus-drift error.

        Args:
            run_id: Identifier of the recorded run being replayed.
            recorded: ``corpus_sha256`` captured at the original run.
            observed: ``corpus_sha256`` computed against the current tree.
            entrypoint: CLI entrypoint string of the recorded run.
        """
        super().__init__(
            f"corpus drift on replay of run {run_id!r}: "
            f"recorded={recorded[:12]}... observed={observed[:12]}... "
            f"entrypoint={entrypoint!r}",
        )
        self.run_id: str = run_id
        self.recorded: str = recorded
        self.observed: str = observed
        self.entrypoint: str = entrypoint


__all__ = [
    "AeatCorpusDriftError",
    "AeatObservabilityError",
    "RunContextMissingError",
    "RunTraceValidationError",
]
