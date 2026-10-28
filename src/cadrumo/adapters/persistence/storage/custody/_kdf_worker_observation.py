"""Lifecycle timing and diagnostics for a supervised profile KDF worker."""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Literal

from .....application.user_profile.proof_cancellation import ProfileProofCancelledError
from .....core.diagnostic_log import DiagnosticValue, diagnostic_event
from .....core.logging import get_logger
from ._kdf_operations import KdfOperation

logger = get_logger("cadrumo.adapters.persistence.storage.custody._kdf_worker_supervision")

type KdfWorkerStage = Literal[
    "start",
    "ready_wait",
    "ready_attestation",
    "request_write",
    "result_wait",
    "clean_exit",
    "result_validation",
    "cleanup",
]
type KdfWorkerCleanupStatus = Literal["completed", "unconfirmed", "failed"]
type KdfCleanupPart = Literal["process", "pipes", "directory"]

KDF_WORKER_PHASE_FIELDS: dict[KdfWorkerStage, str] = {
    "start": "kdf_start_elapsed_ms",
    "ready_wait": "kdf_ready_wait_elapsed_ms",
    "ready_attestation": "kdf_ready_attestation_elapsed_ms",
    "request_write": "kdf_request_write_elapsed_ms",
    "result_wait": "kdf_result_wait_elapsed_ms",
    "clean_exit": "kdf_clean_exit_elapsed_ms",
    "cleanup": "kdf_cleanup_elapsed_ms",
}


class KdfWorkerObservation:
    """Timing and failure observations retained with one worker lifetime."""

    _started_ns: int
    _adopted_ns: int | None
    _phase_elapsed_ms: dict[KdfWorkerStage, float | None]
    _cleanup_elapsed_ms: dict[KdfCleanupPart, float | None]
    _failure_stage: KdfWorkerStage | Literal["caller"] | None
    _failure_type: str | None
    _result_refused: bool
    _diagnostic_emitted: bool
    _operation: KdfOperation | None

    @contextmanager
    def _phase(self, stage: KdfWorkerStage) -> Generator[None]:
        """Collect fixed monotonic spans in memory; never emit during a phase."""
        started = time.monotonic_ns()
        try:
            yield
        except BaseException as error:
            if self._failure_type is None:
                self._failure_stage = stage
                self._failure_type = type(error).__name__
            raise
        finally:
            if stage in KDF_WORKER_PHASE_FIELDS:
                elapsed_ms = max(0, time.monotonic_ns() - started) / 1_000_000
                self._phase_elapsed_ms[stage] = (self._phase_elapsed_ms[stage] or 0.0) + elapsed_ms

    @contextmanager
    def _cleanup_span(self, part: KdfCleanupPart) -> Generator[None]:
        """Attribute cleanup delay without changing failure precedence or ownership."""
        started = time.monotonic_ns()
        try:
            yield
        finally:
            elapsed_ms = max(0, time.monotonic_ns() - started) / 1_000_000
            self._cleanup_elapsed_ms[part] = (self._cleanup_elapsed_ms[part] or 0.0) + elapsed_ms

    def _emit_diagnostic(
        self,
        *,
        cleanup_status: KdfWorkerCleanupStatus,
        cleanup_error: BaseException | None,
        primary_error: BaseException | None,
        exit_code: int | None = None,
    ) -> None:
        """Attempt one summary after cleanup; elapsed time excludes this emission."""
        if self._diagnostic_emitted:
            return
        self._diagnostic_emitted = True
        fields: dict[str, DiagnosticValue] = {
            name: self._phase_elapsed_ms[stage] for stage, name in KDF_WORKER_PHASE_FIELDS.items()
        }
        fields.update(
            kdf_cleanup_process_elapsed_ms=self._cleanup_elapsed_ms["process"],
            kdf_cleanup_pipes_elapsed_ms=self._cleanup_elapsed_ms["pipes"],
            kdf_cleanup_directory_elapsed_ms=self._cleanup_elapsed_ms["directory"],
        )
        outcome = self._diagnostic_outcome(cleanup_status, cleanup_error, primary_error)
        finished_ns = time.monotonic_ns()
        if self._adopted_ns is not None:
            # A prestarted child may wait minutes for a password. Preserve that
            # lifetime separately; it is not time spent handling the request.
            fields["kdf_worker_age_seconds"] = max(0, finished_ns - self._started_ns) / 1_000_000_000
        fields.update(
            kdf_operation=self._operation.value if self._operation is not None else None,
            stage=self._failure_stage,
            error_type=self._failure_type,
            outcome=outcome,
            elapsed_seconds=max(
                0, finished_ns - (self._adopted_ns if self._adopted_ns is not None else self._started_ns)
            )
            / 1_000_000_000,
            cleanup_status=cleanup_status,
            cleanup_incomplete=cleanup_status != "completed",
            cleanup_error_type=type(cleanup_error).__name__ if cleanup_error is not None else None,
            exit_code=exit_code,
        )
        diagnostic_event(
            logger,
            "kdf_worker_lifecycle",
            fields=fields,
            level=(
                logging.DEBUG
                if outcome in {"completed", "sample_rejected", "cancelled"}
                else logging.WARNING
                if outcome == "refused"
                else logging.ERROR
            ),
            primary_error=primary_error,
        )

    def _diagnostic_outcome(
        self,
        cleanup_status: KdfWorkerCleanupStatus,
        cleanup_error: BaseException | None,
        primary_error: BaseException | None,
    ) -> str:
        outcome = "completed"
        if self._failure_type is not None or cleanup_error is not None:
            outcome = "failed"
        elif cleanup_status != "completed":
            outcome = "unconfirmed"
        elif self._result_refused:
            outcome = "refused"
        if (
            isinstance(primary_error, ProfileProofCancelledError)
            and cleanup_status == "completed"
            and cleanup_error is None
        ):
            outcome = "cancelled"
        # A calibration probe exceeding its sample budget is an expected
        # rejection of that grid point, not a failed password operation.
        if self._sample_rejected(cleanup_status, cleanup_error):
            outcome = "sample_rejected"
        return outcome

    def _sample_rejected(self, cleanup_status: KdfWorkerCleanupStatus, cleanup_error: BaseException | None) -> bool:
        return (
            self._operation is KdfOperation.CALIBRATE
            and self._failure_stage == "result_wait"
            and self._failure_type == "TimeoutError"
            and cleanup_status == "completed"
            and cleanup_error is None
        )
