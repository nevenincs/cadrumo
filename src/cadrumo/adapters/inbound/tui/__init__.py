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
from ._credential_screen import (
    CREDENTIAL_PANEL_CSS,
    CredentialApp,
    CredentialAttempt,
    run_credential_app,
)
from ._field_edit_screen import FieldEditScreen, accepted_shape_hint
from ._form_screen import (
    ChoiceEditScreen,
    FormApp,
    FormChoice,
    FormField,
    FormFieldKind,
    FormPage,
    FormPresenter,
    FormScreen,
    TextEditScreen,
    active_form_presenter,
    form_choices,
    multi_choice_tokens,
    presenting_forms_through,
    run_form_tui,
)
from ._login_screen import (
    LoginApp,
    LoginAttempt,
    LoginChoice,
    run_login_tui,
)
from ._manager_screen import (
    ManagerAction,
    ManagerActionDisposition,
    ManagerActionOutcome,
    ManagerProgressSinkBinder,
    ProfileManagerApp,
    run_profile_manager_tui,
)
from ._modelo_work_review_screen import ModeloWorkReviewApp, ModeloWorkReviewScreen
from ._registration_screen import (
    ProfilePasswordVerdict,
    RegistrationApp,
    RegistrationAttempt,
    RegistrationRefusal,
    run_registration_tui,
)
from ._select import select_flow_frontend
from ._status_bar import PinnedStatusBar, StatusTone
from ._status_screen import (
    StatusApp,
    StatusAuthView,
    StatusFactRow,
    StatusPageData,
    StatusProfileRow,
)
from ._theme import (
    BASE_CSS,
    CADRUMO_DARK,
    CADRUMO_DARK_THEME_NAME,
    CADRUMO_LIGHT,
    CADRUMO_LIGHT_THEME_NAME,
    CADRUMO_THEMES,
    CONTENT_WIDTH_PERCENT,
    NOTICE_BAND_CSS,
    NoticeBand,
    install_cadrumo_themes,
    resolve_theme_name,
    toggle_appearance,
)

__all__ = [
    "BASE_CSS",
    "CADRUMO_DARK",
    "CADRUMO_DARK_THEME_NAME",
    "CADRUMO_LIGHT",
    "CADRUMO_LIGHT_THEME_NAME",
    "CADRUMO_THEMES",
    "CONTENT_WIDTH_PERCENT",
    "CREDENTIAL_PANEL_CSS",
    "NOTICE_BAND_CSS",
    "ChoiceEditScreen",
    "ConfirmScreen",
    "CredentialApp",
    "CredentialAttempt",
    "FieldEditScreen",
    "FlowTuiApp",
    "FormApp",
    "FormChoice",
    "FormField",
    "FormFieldKind",
    "FormPage",
    "FormPresenter",
    "FormScreen",
    "LoginApp",
    "LoginAttempt",
    "LoginChoice",
    "ManagerAction",
    "ManagerActionDisposition",
    "ManagerActionOutcome",
    "ManagerProgressSinkBinder",
    "ModeloWorkReviewApp",
    "ModeloWorkReviewScreen",
    "NoticeBand",
    "PinnedStatusBar",
    "ProfileManagerApp",
    "ProfilePasswordVerdict",
    "RegistrationApp",
    "RegistrationAttempt",
    "RegistrationRefusal",
    "StatusApp",
    "StatusAuthView",
    "StatusFactRow",
    "StatusPageData",
    "StatusProfileRow",
    "StatusTone",
    "TextEditScreen",
    "accepted_shape_hint",
    "active_form_presenter",
    "confirm_restart_dialog",
    "form_choices",
    "install_cadrumo_themes",
    "multi_choice_tokens",
    "presenting_forms_through",
    "resolve_theme_name",
    "run_credential_app",
    "run_flow_tui",
    "run_form_tui",
    "run_login_tui",
    "run_profile_manager_tui",
    "run_registration_tui",
    "select_flow_frontend",
    "toggle_appearance",
]
