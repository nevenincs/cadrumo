"""Concrete observability errors layered over :class:`CadrumoObservabilityError`.

The base class :class:`cadrumo.core.errors.CadrumoObservabilityError` lives in
:mod:`cadrumo.core.errors` so other subpackages can catch it without
importing observability internals. This module declares the leaf error types
raised by :func:`record_event`,
:func:`run_context`, :func:`load_trace`, and :func:`replay_run`.
"""

from __future__ import annotations

from pathlib import Path

from ..errors import CadrumoObservabilityError


class RunContextMissingError(CadrumoObservabilityError):
    """Raised when :func:`record_event` runs outside an active :func:`run_context`.

    Caused by calling the recorder from a thread that did not propagate
    the contextvar bound by :func:`cadrumo.core.observability.run_context`,
    or by calling it from CLI bootstrap code that runs before the run
    context enters.
    """


class RunTraceValidationError(CadrumoObservabilityError):
    """Raised when persisted ``trace.json`` or ``events.jsonl`` fails strict validation.

    Surfaces both shape-level rejections (bad ``run_id``, malformed
    JSON line) and strict validation failures for :class:`RunTrace` or
    :class:`RunEvent` records.
    """


class RunTracePersistenceError(CadrumoObservabilityError):
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


class AeatCorpusDriftError(CadrumoObservabilityError):
    """Raised when replay detects that ``corpus_sha256`` has drifted.

    Carries both the recorded and observed hashes plus the entrypoint
    so the caller can render an actionable diff.
    :func:`cadrumo.core.observability.replay_run` is the only call site
    that raises this.

    Attributes:
        run_id: Identifier of the recorded run being replayed.
        recorded: ``corpus_sha256`` captured at the original run.
        observed: ``corpus_sha256`` computed against the current
            configuration.
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
            observed: ``corpus_sha256`` computed against the current
            configuration.
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


class GoldenCaptureError(CadrumoObservabilityError):
    """Raised when a captured envelope document cannot be typed / re-validated.

    Surfaces an emitted-envelope document whose ``command`` is not in the
    JSON-contract schema registry, or whose payload fails strict
    validation against the registered schema. The deterministic-output
    substrate refuses to compare an untyped document, keeping the
    captured payload from degrading to a ``dict[str, Any]`` bag.
    """


class GoldenReplayMismatchError(CadrumoObservabilityError):
    """Raised when a replayed envelope diverges from its captured expectation.

    Carries the differing JSON paths (after the declared narrow mask is
    applied) so the caller can render an actionable diff. The
    :func:`cadrumo.core.observability.replay_run` envelope-assertion tier and
    the operator golden gate both raise this through the shared compare
    primitive.

    Attributes:
        differing_paths: Sorted tuple of dotted JSON paths that differ
            after masking.
    """

    def __init__(self, *, differing_paths: tuple[str, ...], detail: str) -> None:
        """Build the mismatch error and its diagnostic message.

        Args:
            differing_paths: Dotted JSON paths that differ after masking.
            detail: Rendered human-readable diff summary.
        """
        super().__init__(detail)
        self.differing_paths: tuple[str, ...] = differing_paths


__all__ = [
    "AeatCorpusDriftError",
    "GoldenCaptureError",
    "GoldenReplayMismatchError",
    "RunContextMissingError",
    "RunTracePersistenceError",
    "RunTraceValidationError",
]
