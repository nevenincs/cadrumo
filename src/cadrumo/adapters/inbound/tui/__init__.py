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
from ._credential_screen import (
    CREDENTIAL_PANEL_CSS,
    CredentialApp,
    CredentialAttempt,
    run_credential_app,
)
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
    FieldEditScreen,
    ManagerAction,
    ManagerActionOutcome,
    ProfileManagerApp,
    run_profile_manager_tui,
)
from ._registration_screen import (
    PassphraseVerdict,
    RegistrationApp,
    RegistrationAttempt,
    run_registration_tui,
)
from ._select import select_flow_frontend
from ._status_screen import (
    StatusApp,
    StatusAuthView,
    StatusFactRow,
    StatusPageData,
    StatusProfileRow,
    StatusRecoveryView,
)
from ._theme import (
    BASE_CSS,
    CADRUMO_DARK,
    CADRUMO_DARK_THEME_NAME,
    CADRUMO_LIGHT,
    CADRUMO_LIGHT_THEME_NAME,
    CADRUMO_THEMES,
    CONTENT_WIDTH_PERCENT,
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
    "ChoiceEditScreen",
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
    "ManagerActionOutcome",
    "PassphraseVerdict",
    "ProfileManagerApp",
    "RegistrationApp",
    "RegistrationAttempt",
    "StatusApp",
    "StatusAuthView",
    "StatusFactRow",
    "StatusPageData",
    "StatusProfileRow",
    "StatusRecoveryView",
    "TextEditScreen",
    "active_form_presenter",
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
