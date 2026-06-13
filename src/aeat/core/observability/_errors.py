"""Concrete observability errors layered over :class:`AeatObservabilityError`.

The base class :class:`aeat.core.errors.AeatObservabilityError` lives in
:mod:`aeat.core.errors` so other subpackages can catch it without
importing observability internals. This module re-exports the base and
declares the leaf error types raised inside the observability layer.
"""

from __future__ import annotations

from pathlib import Path

from ..errors import AeatObservabilityError


class RunContextMissingError(AeatObservabilityError):
    """Raised when :func:`record_event` runs outside an active :func:`run_context`.

    Caused by calling the recorder from a thread that did not propagate
    the contextvar bound by :func:`aeat.core.observability.run_context`,
    or by calling it from CLI bootstrap code that runs before the run
    context enters.
    """


class RunTraceValidationError(AeatObservabilityError):
    """Raised when persisted ``trace.json`` or ``events.jsonl`` fails strict validation.

    Surfaces both shape-level rejections (bad ``run_id``, malformed
    JSON line) and pydantic strict-mode validation failures.
    """


class RunTracePersistenceError(AeatObservabilityError):
    """Raised when run-trace files cannot be created, read, or written."""

    def __init__(self, *, operation: str, path: Path) -> None:
        """Build a registered persistence error with structured context.

        Args:
            operation: Stable operation label, e.g. ``"save_trace"``.
            path: Filesystem path whose access failed.
        """
        super().__init__(
            context={"operation": operation, "path": str(path)},
            translated_message="errors.fail.fail_observability_run_trace_persistence",
        )
        self.operation = operation
        self.path = path


class AeatCorpusDriftError(AeatObservabilityError):
    """Raised when replay detects that ``corpus_sha256`` has drifted.

    Carries both the recorded and observed hashes plus the entrypoint
    so the caller can render an actionable diff.
    :func:`aeat.core.observability.replay_run` is the only call site
    that raises this.

    Attributes:
        run_id: Identifier of the recorded run being replayed.
        recorded: ``corpus_sha256`` captured at the original run.
        observed: ``corpus_sha256`` computed against the current tree.
        entrypoint: CLI entrypoint string of the recorded run.
    """

    def __init__(
        self,
        *,
        run_id: str,
        recorded: str,
        observed: str,
        entrypoint: str,
    ) -> None:
        """Build the drift error and its diagnostic message.

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
    "RunTracePersistenceError",
    "RunTraceValidationError",
]
