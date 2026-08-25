"""Full-screen Textual frontend for the paged interactive-flow substrate.

This package is a rendering adapter over
:class:`~cadrumo.application.flows.FlowState` and the engine transitions:
it contains zero flow logic. Every semantic — visibility, validation,
staleness, deferral, checkpoint availability, submit eligibility — is an
engine call whose result the screens render. The substrate never imports
this package; a host that cannot run the full-screen application
degrades to the line-mode frontend.
"""

from __future__ import annotations

from ._app import FlowTuiApp, run_flow_tui
from ._confirm_screen import ConfirmScreen, confirm_restart_dialog
from ._form_screen import (
    FormApp,
    FormPresenter,
    FormScreen,
    active_form_presenter,
    presenting_forms_through,
    run_form_tui,
)
from ._modelo_work_review_screen import ModeloWorkReviewApp, ModeloWorkReviewScreen
from ._select import select_flow_frontend

__all__ = [
    "ConfirmScreen",
    "FlowTuiApp",
    "FormApp",
    "FormPresenter",
    "FormScreen",
    "ModeloWorkReviewApp",
    "ModeloWorkReviewScreen",
    "active_form_presenter",
    "confirm_restart_dialog",
    "presenting_forms_through",
    "run_flow_tui",
    "run_form_tui",
    "select_flow_frontend",
]
