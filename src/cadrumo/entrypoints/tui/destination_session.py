"""Run one requested full-screen destination as this process's whole session.

Module execution is how a sibling entrypoint reaches a full-screen surface,
because it may not import this package. That leaves this module holding the
work the requesting command used to do in its own process: resolve the
subject the request names, open the destination, and record how it ended.

Everything about a subject arrives as identifiers, so every record rendered
here is read from persistence in THIS process. The requesting command hands
over what to look at, never what was found.

The outcome is written to the file the request names rather than printed.
This process inherits the requester's streams so a session can own the
terminal, so standard output belongs to Textual for the session's lifetime
and is not available as a result channel.
"""

from __future__ import annotations

import re
from contextlib import ExitStack
from typing import TYPE_CHECKING

from ..full_screen_session_protocol import (
    FullScreenDestination,
    FullScreenOutcomeKind,
    FullScreenSessionOutcome,
    FullScreenSessionProtocolError,
    FullScreenSessionRequest,
    render_outcome,
)

if TYPE_CHECKING:
    from textual.pilot import Pilot

    from ...core.external_constants import OutputLanguage
    from ...domain.modelos.work_unit import WorkUnit


async def _leave_at_once(pilot: Pilot[object]) -> None:
    """Drive a mounted session straight back out again.

    The self-test proves that a destination's surface really starts and that
    its outcome really reaches the requester. Both need a session that ends by
    itself, and no operator is present to end one, so the pilot settles the
    mount and then leaves exactly as a cancelling operator would.
    """
    await pilot.pause()
    pilot.app.exit(None)


def _require_work_unit_id(request: FullScreenSessionRequest) -> str:
    """Validate the subject identifier this request must carry."""
    from ...core.hex import HEX_PATTERN_64

    work_unit_id = (request.work_unit_id or "").strip()
    if not re.fullmatch(HEX_PATTERN_64, work_unit_id):
        raise FullScreenSessionProtocolError(
            f"destination {request.destination.value} needs one work-unit identifier, got {request.work_unit_id!r}"
        )
    return work_unit_id


def _resolved_output_language() -> OutputLanguage:
    """Read the language this session renders in, as a typed value."""
    from ...core.external_constants import OutputLanguage
    from ...core.i18n.render import output_language

    return OutputLanguage(output_language())


def _run_work_review(request: FullScreenSessionRequest) -> FullScreenSessionOutcome:
    """Open the bounded review for the unit this request names."""
    from .launcher import build_modelo_work_review_for_unit, resolve_modelo_work_unit
    from .modelo.view.work_review import ModeloWorkReviewApp

    unit = resolve_modelo_work_unit(work_unit_id=_require_work_unit_id(request), bucket_id=request.bucket_id)
    application = ModeloWorkReviewApp(build_modelo_work_review_for_unit(unit))
    if request.self_test:
        application.run(headless=True, auto_pilot=_leave_at_once)
    else:
        application.run()
    return FullScreenSessionOutcome(kind=FullScreenOutcomeKind.COMPLETED, work_unit_id=unit.work_unit_id)


def _selectable_work_units(request: FullScreenSessionRequest) -> tuple[WorkUnit, ...]:
    """Read the units the picker offers, or none at all under self-test.

    The self-test proves the protocol, not a profile. Reading persistence
    would make the proof depend on provisioned work, and an empty catalogue is
    a state the picker already renders honestly, so the surface under test is
    the real one either way.
    """
    if request.self_test:
        return ()
    from .launcher import load_modelo_work_units

    return load_modelo_work_units(bucket_id=request.bucket_id, include_discarded=request.include_discarded)


def _run_work_select(request: FullScreenSessionRequest) -> FullScreenSessionOutcome:
    """Open the picker, and land a real choice on its workspace destination."""
    from .components.host import ScreenHostApp
    from .launcher import resolve_modelo_work_unit, resolve_modelo_workspace_static_inspection
    from .modelo.routes import WORKSPACE_SELECTION_OUTCOME, resolve_destination
    from .modelo.view.controller import admit_workspace_session
    from .modelo.view.work_select import ModeloWorkSelectApp

    picker = ModeloWorkSelectApp(_selectable_work_units(request))
    selected = picker.run(headless=True, auto_pilot=_leave_at_once) if request.self_test else picker.run()
    if selected is None:
        return FullScreenSessionOutcome(kind=FullScreenOutcomeKind.CANCELLED)

    unit = resolve_modelo_work_unit(work_unit_id=selected, bucket_id=request.bucket_id)
    result = resolve_modelo_workspace_static_inspection(unit, output_language=_resolved_output_language())
    session, refusal = admit_workspace_session(result)
    if session is None:
        if refusal is None:
            raise FullScreenSessionProtocolError(
                "workspace admission returned neither a read session nor a refusal to display"
            )
        # The refusal is REPORTED, not swallowed. An operator who picked a unit
        # and silently got no screen has been told nothing, so the requesting
        # command receives the refusal's own reconsideration condition and
        # renders it beside the envelope it already emits.
        return FullScreenSessionOutcome(
            kind=FullScreenOutcomeKind.NOT_ADMITTED,
            work_unit_id=unit.work_unit_id,
            detail=refusal.reconsideration_condition,
        )
    # Hosted through the shared ``ScreenHostApp`` rather than a workspace-owned
    # host: resolving WHICH screen to show is this module's job, and RUNNING
    # one is already solved.
    workspace = ScreenHostApp(resolve_destination(WORKSPACE_SELECTION_OUTCOME)(session))
    if request.self_test:
        workspace.run(headless=True, auto_pilot=_leave_at_once)
    else:
        workspace.run()
    return FullScreenSessionOutcome(kind=FullScreenOutcomeKind.SELECTED, work_unit_id=unit.work_unit_id)


_DESTINATION_SESSIONS = {
    FullScreenDestination.MODELO_WORK_REVIEW: _run_work_review,
    FullScreenDestination.MODELO_WORK_SELECT: _run_work_select,
}
"""Every requestable destination, keyed by its protocol token.

Kept as a table so a request resolves to exactly one session rather than
falling through a chain of comparisons, and so the completeness check below
compares the table against the protocol's own closed set.
"""

if set(_DESTINATION_SESSIONS) != set(FullScreenDestination):
    raise ValueError("every declared full-screen destination must resolve to exactly one session")


def run_requested_destination(request: FullScreenSessionRequest) -> int:
    """Run one requested destination and report the session's exit status.

    The outcome record is written before returning, so a caller reading it
    after a zero status always finds a complete record. A non-zero status
    leaves no record: a session that did not finish has no outcome to report,
    and inventing one would let a failure read as a cancellation.
    """
    from ...core.config import override_settings
    from ...core.i18n.render import clear_output_language_cache
    from ..adapter_composition import profile_adapter_composition

    with ExitStack() as scope:
        scope.enter_context(profile_adapter_composition())
        if request.output_language is not None:
            scope.enter_context(override_settings(cadrumo_output_language=request.output_language))
            clear_output_language_cache()
        outcome = _DESTINATION_SESSIONS[request.destination](request)
    request.outcome_file.write_text(render_outcome(outcome), encoding="utf-8")
    return 0


__all__ = ["run_requested_destination"]
