"""Behavior for the canonical modelo work-unit list read surface."""

from __future__ import annotations

import typer

from ...application.modelo.work_lifecycle import lifecycle_continuation_for_work_list, list_work_units
from ...core.external_constants import OutputLanguage
from ._common import (
    activate_subcommand_output_language,
    active_profile_label,
    emit_envelope,
    resolve_lifecycle_continuation_notice,
)
from ._modelo_behavior_support import require_active_profile
from ._modelo_payloads import WorkSelectResult
from ._modelo_rendering import work_unit_list_lines, work_unit_payload

__all__ = ["work_select"]


def work_select(
    ctx: typer.Context,
    bucket_id: str | None = None,
    include_discarded: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """List modelo work units through the scripted command surface."""
    activate_subcommand_output_language(ctx, output_language)
    require_active_profile()
    units = list_work_units(bucket_id=bucket_id, include_discarded=include_discarded)

    result = WorkSelectResult.model_validate(
        {
            "bucket_id_filter": bucket_id,
            "include_discarded": include_discarded,
            "work_unit_count": len(units),
            "work_units": [work_unit_payload(unit) for unit in units],
        }
    )
    lines = [
        f"active_profile\t{active_profile_label() or ''}",
        *work_unit_list_lines(units, include_discarded=include_discarded),
    ]
    follow_up = resolve_lifecycle_continuation_notice(lifecycle_continuation_for_work_list(units))
    emit_envelope(ctx, command="modelo.work.select", result=result, lines=lines, notices=[follow_up])
