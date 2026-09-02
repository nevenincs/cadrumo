"""Behavior for the canonical modelo work-unit picker read surface.

In a scripted (non-``--tui``) invocation this behaves exactly like ``work
list``. Under ``--tui`` it additionally opens the keyboard-navigable picker,
and on a real selection chains into the workspace destination for the chosen
work unit -- the one path an operator has from "which filing do I want" to
"look at it" without leaving the full-screen session.

That session runs out of process. This command may not import the dedicated
full-screen frontend, so it requests the destination and reads back which
unit the operator chose; the chain from the picker to the workspace stays
inside the session, where the routing decision belongs.
"""

from __future__ import annotations

import typer

from ...application.modelo.work_lifecycle import lifecycle_continuation_for_work_list, list_work_units
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language
from ...core.json_contract import Notice, NoticeSeverity
from ._common import (
    activate_subcommand_output_language,
    active_profile_label,
    emit_envelope,
    resolve_lifecycle_continuation_notice,
)
from ._modelo_behavior_support import require_active_profile
from ._modelo_payloads import WorkSelectResult
from ._modelo_rendering import work_unit_list_lines, work_unit_payload
from ._tui_policy import tui_was_requested

__all__ = ["work_select"]


def _run_select_destination(*, bucket_id: str | None, include_discarded: bool) -> tuple[str | None, str | None]:
    """Open the picker destination and report the chosen unit and any refusal.

    Kept as its own seam so a test can substitute a non-blocking stand-in for
    the real full-screen session without touching the surrounding envelope
    logic.

    Returns the chosen work-unit id -- ``None`` when the operator left without
    choosing -- paired with the reconsideration condition of a workspace that
    declined to admit the choice, or ``None`` when none declined. The refusal
    is REPORTED rather than swallowed: an operator who asked for a screen and
    silently got none has been told nothing.

    The picker and the workspace it chains into both run out of process,
    because a CLI entrypoint may not import the dedicated full-screen
    frontend. The chain stays inside that one session: the destination reached
    from a selection is the frontend's own routing decision, and splitting it
    across the boundary would put it here instead.
    """
    from ..full_screen_session_protocol import FullScreenDestination, FullScreenOutcomeKind
    from ._tui_session import run_destination_session

    outcome = run_destination_session(
        destination=FullScreenDestination.MODELO_WORK_SELECT,
        bucket_id=bucket_id,
        include_discarded=include_discarded,
        output_language=output_language(),
    )
    if outcome.kind is FullScreenOutcomeKind.NOT_ADMITTED:
        return outcome.work_unit_id, outcome.detail
    if outcome.kind is FullScreenOutcomeKind.SELECTED:
        return outcome.work_unit_id, None
    return None, None


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
        selected_work_unit_id, workspace_refusal = _run_select_destination(
            bucket_id=bucket_id, include_discarded=include_discarded
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
