"""Application-layer orchestration for the Sheets calc-sheets export surface.

The workbook export completes inside the CLI handler, which called the
outbound Google adapter directly with no application-layer function between
them. That left the export surface with no legal place to persist last-sync
provenance from: persisting at the entrypoint would make it the first CLI site
writing to a secure-object namespace, and persisting from the adapter would
have an outbound adapter reach back into application storage, inverting the
dependency direction.

This module is that missing seam. :func:`export_modelo_to_sheets` builds the
plan, applies it through the outbound adapter, and records the completed run's
provenance -- on success AND on failure, because the write path RAISES rather
than returns, and a partial failure is exactly the state a reader most needs
to see.

See Also:
    :func:`~application.storage.sync_runs.record_sync_run`
        The shared co-write primitive this module calls on both completion
        paths.
    :func:`~adapters.outbound.google.apply_export_plan`
        The outbound write this module wraps with provenance.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ....core.bucket_pointer import require_active_bucket_id
from ....core.sync_surface import SyncSurface
from ....core.time.clock import now
from ..sync_runs._persist import record_sync_run
from ..sync_runs._records import SyncRunRecordRepositoryProtocol, bounded_scope_description, coverage_of

if TYPE_CHECKING:
    from ....adapters.outbound.google.calc_sheets_apply import CalcSheetsApplyResult
    from .records import SheetExportPlan

__all__ = ["export_modelo_to_sheets"]


class _SingleExportCoverage:
    """Coverage source for one calc-sheets export: the unit is the whole write.

    Unlike the filed sweep, which walks many declarations and can genuinely
    complete some while others fail, one export call materialises exactly one
    modelo+period+year workbook in a single write -- there is no population to
    walk within it. ``reached_count`` is 1 once the write completes and 0 when
    it never got there. ``divergences`` is always empty: detecting whether a
    written value diverges from anything is `verify`'s concern, driven by its
    own scenario and oracle, never the export's -- the export overwrites its
    target unconditionally rather than comparing against it.
    """

    __slots__ = ("_reached",)

    def __init__(self, *, reached: bool) -> None:
        self._reached = reached

    @property
    def reached_count(self) -> int:
        return 1 if self._reached else 0

    @property
    def divergences(self) -> tuple[object, ...]:
        return ()


def _export_scope_description(plan: SheetExportPlan) -> str:
    metadata = plan.metadata
    return bounded_scope_description(
        (f"{metadata.modelo_id}-{metadata.period.registry_token}-{metadata.filing_year}",),
    )


def export_modelo_to_sheets(
    plan: SheetExportPlan,
    *,
    credentials: object,
    root_folder_id: str,
    sync_run_repository: SyncRunRecordRepositoryProtocol,
    apply_export_plan: Callable[..., CalcSheetsApplyResult],
) -> CalcSheetsApplyResult:
    """Apply an already-built export plan to Sheets and record the run's provenance.

    Takes the plan already built by :func:`build_export_plan` rather than
    building one itself: the CLI's dry-run branch needs the SAME plan for its
    preview, and building it twice would let the two branches drift on what
    they describe. This function owns only the write-plus-provenance half.

    On a raised failure the run's sync-run record is still persisted, with
    ``succeeded=False`` and zero units reached, and the original exception is
    re-raised unchanged for the caller's existing refusal handling.

    Args:
        plan: The :class:`SheetExportPlan` to materialise.
        credentials: Google API credentials, forwarded to ``apply_export_plan``
            unchanged.
        root_folder_id: The operator's Drive root folder id.
        sync_run_repository: Persistence port for the completed-run provenance
            record, co-written with its bucket event.
        apply_export_plan: Outbound apply callable supplied by the composing
            entrypoint.

    Returns:
        The adapter's :class:`~adapters.outbound.google.CalcSheetsApplyResult`.

    Raises:
        Whatever ``apply_export_plan`` raises,
            after the failed run's provenance has been persisted.
    """
    bucket_id = require_active_bucket_id()
    scope = _export_scope_description(plan)

    try:
        result = apply_export_plan(plan, credentials=credentials, root_folder_id=root_folder_id)
    except Exception:
        record_sync_run(
            bucket_id=bucket_id,
            surface=SyncSurface.CALC_SHEETS_EXPORT,
            resolved_scope=scope,
            succeeded=False,
            coverage=coverage_of(_SingleExportCoverage(reached=False)),
            completed_at=now(),
            repository=sync_run_repository,
        )
        raise

    record_sync_run(
        bucket_id=bucket_id,
        surface=SyncSurface.CALC_SHEETS_EXPORT,
        resolved_scope=scope,
        succeeded=True,
        coverage=coverage_of(_SingleExportCoverage(reached=True)),
        completed_at=now(),
        repository=sync_run_repository,
    )
    return result
