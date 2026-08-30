"""Behavior for the canonical modelo work-unit picker read surface.

In a scripted (non-``--tui``) invocation this behaves exactly like ``work
list``. Under ``--tui`` it additionally launches the keyboard-navigable
picker, and on a real selection chains directly into the sole C1 bounded
review destination for the chosen work unit -- the one path an operator has
from "which filing do I want" to "review it" without leaving the TUI.
"""

from __future__ import annotations

import typer

from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...application.modelo.work_addressing import ModeloVisibleFilingTarget
from ...application.modelo.work_lifecycle import lifecycle_continuation_for_work_list, list_work_units
from ...application.modelo.workspace import resolve_static_inspection_result
from ...application.modelo.workspace_models import ModeloWorkspaceVisibleFilingTargetV1
from ...core.external_constants import OutputLanguage
from ...core.i18n import output_language
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.modelos.work_unit import WorkUnit
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


def _run_workspace_destination_for_selected_unit(*, work_unit_id: str, bucket_id: str | None) -> str | None:
    """Land the picked unit on the workspace overview, or report why it could not.

    Returns ``None`` on a successful read, or the refusal's reconsideration
    condition when the workspace declined to admit. The refusal is RETURNED
    rather than swallowed: an operator who asked for a screen and silently
    got none has been told nothing, and the caller surfaces it as a notice
    beside the envelope it already emits.
    """
    from ...entrypoints.tui.components.host import ScreenHostApp
    from ...entrypoints.tui.modelo.routes import WORKSPACE_SELECTION_OUTCOME, resolve_destination
    from ...entrypoints.tui.modelo.view.controller import admit_workspace_session

    unit = resolve_work_unit_for_cli(work_unit_id=work_unit_id, bucket_id=bucket_id)
    result = resolve_static_inspection_result(
        ModeloWorkspaceVisibleFilingTargetV1(
            target=ModeloVisibleFilingTarget(
                modelo=unit.modelo,
                filing_year=unit.filing_year,
                period=unit.period,
            )
        ),
        bucket_id=unit.bucket_id,
        catalogue_repository=WorkUnitCatalogueRepository(),
        authority=bundled_authority(),
        output_language=OutputLanguage(output_language()),
    )
    session, refusal = admit_workspace_session(result)
    if session is None:
        assert refusal is not None
        return refusal.reconsideration_condition
    # Hosted through the shared ``ScreenHostApp`` rather than a workspace-owned
    # host: resolving WHICH screen to show is this seam's job, and RUNNING one
    # is already solved. A second host would also have to re-derive the
    # tokenised base CSS and the awaited push that keeps a caller from racing
    # the mount.
    ScreenHostApp(resolve_destination(WORKSPACE_SELECTION_OUTCOME)(session)).run()
    return None


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
    workspace_refusal: str | None = None
    if tui_was_requested(ctx):
        selected_work_unit_id = _run_select_destination(tuple(units))
        if selected_work_unit_id is not None:
            workspace_refusal = _run_workspace_destination_for_selected_unit(
                work_unit_id=selected_work_unit_id, bucket_id=bucket_id
            )

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
    notices = [follow_up]
    if workspace_refusal is not None:
        # The operator asked for a screen and the workspace declined to admit
        # one. Reporting the refusal's own reconsideration condition is the
        # difference between "nothing happened" and knowing why.
        #
        # This notice is a considered choice, not an accretion: the rewire had
        # to do SOMETHING when admission declines, and the alternative --
        # returning early and emitting the envelope unchanged -- was rejected
        # because it introduces a silent under-declaration. There was no
        # neutral branch. Removing this restores the silence rather than
        # tidying a stray field.
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="modelo.workspace.not_admitted",
                message=workspace_refusal,
            )
        )
    emit_envelope(ctx, command="modelo.work.select", result=result, lines=lines, notices=notices)
