"""Behavior for the canonical modelo work-unit picker read surface.

In a scripted (non-``--tui``) invocation this behaves exactly like ``work
list``. Under ``--tui`` it additionally launches the keyboard-navigable
picker, and on a real selection chains directly into the sole C1 bounded
review destination for the chosen work unit -- the one path an operator has
from "which filing do I want" to "review it" without leaving the TUI.
"""

from __future__ import annotations

import typer

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...application.modelo._work_lifecycle import lifecycle_continuation_for_work_list, list_work_units
from ...application.modelo.work_review import build_modelo_work_review
from ...core.external_constants import OutputLanguage
from ...domain.modelos import WorkUnit
from ._common import (
    activate_subcommand_output_language,
    active_profile_label,
    emit_envelope,
    resolve_lifecycle_continuation_notice,
)
from ._modelo_behavior_support import require_active_profile, resolve_work_unit_for_cli
from ._modelo_payloads import WorkSelectResult
from ._modelo_rendering import work_unit_list_lines, work_unit_payload
from ._tui_policy import tui_was_requested

__all__ = ["work_select"]


def _run_select_destination(units: tuple[WorkUnit, ...]) -> str | None:
    """Launch the picker host and return the chosen work-unit id, if any.

    Kept as its own seam so a test can substitute a non-blocking stand-in for
    the real full-screen ``run()`` call without touching the resolution logic
    around it.
    """
    from ...entrypoints.tui.modelo.view.work_select import ModeloWorkSelectApp

    return ModeloWorkSelectApp(units).run()


def _run_review_destination_for_selected_unit(*, work_unit_id: str, bucket_id: str | None) -> None:
    from ...entrypoints.tui.modelo.view.work_review import ModeloWorkReviewApp

    unit = resolve_work_unit_for_cli(work_unit_id=work_unit_id, bucket_id=bucket_id)
    review = build_modelo_work_review(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        verification_repository=VerificationReportCatalogueRepository(),
    )
    ModeloWorkReviewApp(review).run()


def work_select(
    ctx: typer.Context,
    bucket_id: str | None = None,
    include_discarded: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """List modelo work units, and under ``--tui`` let the operator pick one."""
    activate_subcommand_output_language(ctx, output_language)
    require_active_profile()
    units = list_work_units(bucket_id=bucket_id, include_discarded=include_discarded)

    selected_work_unit_id: str | None = None
    if tui_was_requested(ctx):
        selected_work_unit_id = _run_select_destination(tuple(units))
        if selected_work_unit_id is not None:
            _run_review_destination_for_selected_unit(work_unit_id=selected_work_unit_id, bucket_id=bucket_id)

    result = WorkSelectResult.model_validate(
        {
            "bucket_id_filter": bucket_id,
            "include_discarded": include_discarded,
            "work_unit_count": len(units),
            "work_units": [work_unit_payload(unit) for unit in units],
            "selected_work_unit_id": selected_work_unit_id,
        }
    )
    lines = [
        f"active_profile\t{active_profile_label() or ''}",
        f"selected_work_unit_id\t{selected_work_unit_id or ''}",
        *work_unit_list_lines(units, include_discarded=include_discarded),
    ]
    follow_up = resolve_lifecycle_continuation_notice(lifecycle_continuation_for_work_list(units))
    emit_envelope(ctx, command="modelo.work.select", result=result, lines=lines, notices=[follow_up])
