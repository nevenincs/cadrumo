"""Login: full-screen credential entry that unlocks one existing profile.

See Also:
    :class:`~cadrumo.entrypoints.tui.secret.credentials.CredentialApp`
        The shared attempt lifecycle and panel layout this screen builds on.
    :class:`~cadrumo.entrypoints.tui.secret.registration.RegistrationApp`
        The other credential surface, sharing the same base.
"""

from __future__ import annotations

from contextvars import copy_context
from typing import TYPE_CHECKING, cast, override

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Input, Label, Select, Static

from ....core.external_constants import UTF_8_ENCODING
from ....core.i18n import tr
from ....entrypoints.tui.components.status import PinnedStatusBar
from ....entrypoints.tui.components.theme import BASE_CSS, install_cadrumo_themes
from ....entrypoints.tui.components.widgets import ContentScroll
from .credentials import CREDENTIAL_PANEL_CSS, CredentialApp, run_credential_app

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from ....application.user_profile.login_interaction import ProfileLoginAttempt, ProfileLoginChoice
    from ....application.user_profile.login_session import ProfileLoginOutcome

__all__ = ["LoginApp", "run_login_tui"]


class LoginApp(CredentialApp["ProfileLoginOutcome"]):
    """Full-screen credential entry that unlocks one existing profile."""

    CSS = (
        BASE_CSS
        + CREDENTIAL_PANEL_CSS
        + """
    #login-intro { margin: 0; }
    #login-actions Button { margin: 0 0 0 1; }
    """
    )

    ATTEMPT_NAME = "profile-login"

    def __init__(
        self,
        *,
        choices: Sequence[ProfileLoginChoice],
        authenticate: Callable[[str, str], ProfileLoginAttempt],
        preselected: str | None = None,
    ) -> None:
        """Bind the supplied profile choices and authentication callback."""
        super().__init__()
        if not choices:
            raise ValueError("a login screen needs at least one profile to choose from")
        self._choices = tuple(choices)
        self._authenticate = authenticate
        known = {choice.profile_id for choice in self._choices}
        self._preselected = (
            preselected if preselected is not None and preselected in known else self._choices[0].profile_id
        )

    @override
    def compose(self) -> ComposeResult:
        """Yield the banner, the two credential fields, and the footer."""
        yield Static(id="login-banner", classes="cadrumo-banner")
        yield PinnedStatusBar(id="credential-status")
        with (
            ContentScroll(classes="cadrumo-scroll"),
            Vertical(classes="cadrumo-column"),
            Vertical(id="login-body", classes="cadrumo-panel"),
        ):
            yield Static(id="login-intro")

            yield Label(id="label-profile", classes="field-label")
            yield Select[str](
                [(choice.label, choice.profile_id) for choice in self._choices],
                value=self._preselected,
                allow_blank=False,
                id="field-profile",
            )

            yield Label(id="label-passphrase", classes="field-label")
            yield Static(id="hint-passphrase", classes="field-hint")
            yield Input(id="field-passphrase", password=True)

            with Horizontal(id="login-actions", classes="credential-actions"):
                yield Button(tr("flows.login.cancel_button"), id="btn-cancel")
                yield Button(tr("flows.login.unlock_button"), id="btn-unlock", classes="-primary")
        yield Footer()

    def on_mount(self) -> None:
        """Install the theme, render copy, and focus password entry."""
        install_cadrumo_themes(self)
        self._render_localised_copy()
        self.query_one("#field-passphrase", Input).focus()

    def _render_localised_copy(self) -> None:
        """Resolve every operator-facing string on the page."""
        title = tr("flows.login.title")
        self.title = title
        self.sub_title = tr("flows.login.section")
        self.query_one("#login-banner", Static).update(title)
        self.query_one("#login-intro", Static).update(tr("flows.login.intro"))
        self.query_one("#login-body", Vertical).border_title = tr("flows.login.section")
        self.query_one("#label-profile", Label).update(tr("flows.login.profile_label"))
        self.query_one("#label-passphrase", Label).update(tr("flows.login.password_label"))
        self.query_one("#hint-passphrase", Static).update(tr("flows.login.password_hint"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route an unlock or cancellation button intent."""
        if event.button.id == "btn-unlock":
            self.action_unlock()
        elif event.button.id == "btn-cancel":
            self.action_abandon()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the password field is the unlock."""
        if event.input.id == "field-passphrase":
            self.action_unlock()

    def selected_profile_id(self) -> str:
        """Return the profile the chooser currently addresses."""
        selected = cast("Select[str]", self.query_one("#field-profile", Select)).value
        return selected if isinstance(selected, str) else self._preselected

    def action_unlock(self) -> None:
        """Hand the typed password to the injected unlock door off-loop."""
        if self.attempt_in_flight:
            return

        passphrase = self.query_one("#field-passphrase", Input).value
        if not passphrase:
            self.refuse(tr("flows.login.refusal.password_required"))
            return

        profile_id = self.selected_profile_id()
        login_context = copy_context()
        passphrase_buffer = bytearray(passphrase, UTF_8_ENCODING)

        def _unlock() -> ProfileLoginAttempt:
            try:
                return login_context.run(
                    self._authenticate,
                    profile_id,
                    passphrase_buffer.decode(UTF_8_ENCODING),
                )
            finally:
                passphrase_buffer[:] = b"\x00" * len(passphrase_buffer)

        self.start_attempt(_unlock)

    @override
    def default_refusal(self) -> str:
        return tr("flows.login.refusal.unlock_failed")

    @override
    def progress_message(self) -> str:
        return tr("flows.login.unlock_button")

    @override
    def refuse(self, message: str) -> None:
        """Show refusal, clear the rejected password, and focus retry."""
        super().refuse(message)
        field = self.query_one("#field-passphrase", Input)
        field.value = ""
        field.focus()

    @override
    def set_busy(self, *, busy: bool) -> None:
        """Render unlock progress and freeze inputs during derivation."""
        super().set_busy(busy=busy)
        self.query_one("#field-passphrase", Input).disabled = busy
        self.query_one("#field-profile", Select).disabled = busy
        self.query_one("#btn-unlock", Button).disabled = busy
        self.query_one("#btn-cancel", Button).disabled = busy


def run_login_tui(
    *,
    choices: Sequence[ProfileLoginChoice],
    authenticate: Callable[[str, str], ProfileLoginAttempt],
    preselected: str | None = None,
) -> ProfileLoginOutcome | None:
    """Run the login screen and return the opened session, or ``None``."""
    return run_credential_app(
        LoginApp(choices=choices, authenticate=authenticate, preselected=preselected),
    )
