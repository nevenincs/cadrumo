"""The way back in: pick a profile, type its password, and it opens.

Every profile the application holds is encrypted with a key derived from
the operator's password, so unlocking one is the gate in front of
everything else. The screen that asks for it is deliberately the same
surface as the one that created the profile — the operator met that page
once already, and meeting a recognisably different thing to get back into
their own data is how a password prompt starts feeling like a fault.

Two fields, because there are exactly two facts: *which* profile, and
*its* password. The chooser is present even when the machine holds only
one profile, since it is also the answer to "which of these am I about to
open" — a question the operator cannot otherwise ask without leaving.

A wrong password stays on this page. The screen refuses in place and
leaves the operator where they were, because being returned to a shell to
type the whole command again is a punishment for a typo, and the backoff
that guards repeated attempts belongs to the application door rather than
to how many times a screen was opened.

See Also:
    :func:`~cadrumo.application.user_profile.login_profile`
        The application door this screen drives; it owns selection, the
        failed-attempt backoff, the unwrap that IS the authentication,
        and the session it mints.
    :class:`~cadrumo.adapters.inbound.tui.RegistrationApp`
        The other credential surface, sharing this one's attempt
        lifecycle and panel layout.
"""

from __future__ import annotations

from contextvars import copy_context
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast, override

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Input, Label, Select, Static

from ....core.external_constants import UTF_8_ENCODING
from ....core.i18n import tr
from ....entrypoints.tui.components.status import PinnedStatusBar
from ....entrypoints.tui.components.theme import BASE_CSS, install_cadrumo_themes
from ....entrypoints.tui.components.widgets import ContentScroll
from ._credential_screen import (
    CREDENTIAL_PANEL_CSS,
    CredentialApp,
    CredentialAttempt,
    run_credential_app,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from ....application.user_profile import ProfileLoginOutcome


@dataclass(frozen=True, slots=True)
class LoginChoice:
    """One profile the operator can log in to.

    Carries only what a chooser row needs. The label is what the operator
    named the profile and the id is what the application resolves, so the
    screen never has to guess which of the two it is holding — the
    ambiguity that makes a name-or-uuid argument hard to type is resolved
    before the page is built.
    """

    profile_id: str
    label: str


class LoginAttempt(CredentialAttempt["ProfileLoginOutcome"]):
    """The outcome of asking the application to unlock a profile.

    Named rather than used as the bare generic so the seam that builds it
    and the screen that reads it agree on more than a shape.
    """


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
        choices: Sequence[LoginChoice],
        authenticate: Callable[[str, str], LoginAttempt],
        preselected: str | None = None,
    ) -> None:
        super().__init__()
        if not choices:
            # A chooser with no rows is not a page an operator can act on,
            # and the caller can tell there is nothing to log in to without
            # opening a screen to find out.
            raise ValueError("a login screen needs at least one profile to choose from")
        self._choices = tuple(choices)
        self._authenticate = authenticate
        """The unlock door, injected rather than imported: this tier
        renders and does not reach up into the application layer, and the
        injection is what lets the screen be driven against a real
        refusal without contriving one inside a widget."""
        known = {choice.profile_id for choice in self._choices}
        self._preselected = preselected if preselected in known else self._choices[0].profile_id
        """Which row opens selected.

        The active profile when there is one, and the first row otherwise.
        A pointer naming a profile this list does not carry (deleted, or
        on another machine) is not an error here — it simply does not
        preselect anything, and the operator picks."""

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
        install_cadrumo_themes(self)
        self._render_localised_copy()
        # Focus the password rather than the chooser: the profile is
        # already selected for the operator in the common case, and the
        # password is the field they came here to fill.
        self.query_one("#field-passphrase", Input).focus()

    def _render_localised_copy(self) -> None:
        """Resolve every operator-facing string on the page.

        One pass, written here rather than at compose time so the widgets
        holding the copy never have to be rebuilt to change it.
        """
        title = tr("flows.login.title")
        self.title = title
        self.sub_title = tr("flows.login.section")
        self.query_one("#login-banner", Static).update(title)
        self.query_one("#login-intro", Static).update(tr("flows.login.intro"))
        self.query_one("#login-body", Vertical).border_title = tr("flows.login.section")
        self.query_one("#label-profile", Label).update(tr("flows.login.profile_label"))
        self.query_one("#label-passphrase", Label).update(tr("flows.login.password_label"))
        self.query_one("#hint-passphrase", Static).update(tr("flows.login.password_hint"))

    # ── intents ─────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-unlock":
            self.action_unlock()
        elif event.button.id == "btn-cancel":
            self.action_abandon()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the password field is the unlock."""
        if event.input.id == "field-passphrase":
            self.action_unlock()

    def selected_profile_id(self) -> str:
        """The profile the chooser is currently on."""
        selected = cast("Select[str]", self.query_one("#field-profile", Select)).value
        return selected if isinstance(selected, str) else self._preselected

    def action_unlock(self) -> None:
        """Hand the typed password to the unlock door, off the event loop.

        The only check made here is that something was typed. Whether it
        is the RIGHT password is not knowable on this side — the answer is
        whether the AEAD unwrap succeeds — and the backoff that guards
        repeated wrong answers belongs to the door, so the screen refuses
        nothing it cannot see.
        """
        if self.attempt_in_flight:
            return

        passphrase = self.query_one("#field-passphrase", Input).value
        if not passphrase:
            self.refuse(tr("flows.login.refusal.password_required"))
            return

        profile_id = self.selected_profile_id()
        login_context = copy_context()
        # The typed secret is copied into a buffer this closure can
        # overwrite once the door has consumed it. It cannot unmake the
        # str the widget holds, but it keeps the screen from being the
        # thing that leaves an extra copy alive for the process lifetime.
        passphrase_buffer = bytearray(passphrase, UTF_8_ENCODING)

        def _unlock() -> LoginAttempt:
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
        """Show the refusal and hand the operator a clear field to retry in.

        Clearing is not tidiness: a rejected password left in place is one
        the next keystroke appends to, so the retry would carry the
        original mistake inside it.
        """
        super().refuse(message)
        field = self.query_one("#field-passphrase", Input)
        field.value = ""
        field.focus()

    @override
    def set_busy(self, *, busy: bool) -> None:
        """Render unlock progress and freeze inputs while key derivation runs."""
        super().set_busy(busy=busy)
        self.query_one("#field-passphrase", Input).disabled = busy
        self.query_one("#field-profile", Select).disabled = busy
        self.query_one("#btn-unlock", Button).disabled = busy
        self.query_one("#btn-cancel", Button).disabled = busy


def run_login_tui(
    *,
    choices: Sequence[LoginChoice],
    authenticate: Callable[[str, str], LoginAttempt],
    preselected: str | None = None,
) -> ProfileLoginOutcome | None:
    """Run the login screen and return the opened session, or ``None``.

    ``None`` means the operator left without logging in — an ordinary
    choice, so the caller decides what to report rather than catching an
    exception to find out.
    """
    return run_credential_app(
        LoginApp(choices=choices, authenticate=authenticate, preselected=preselected),
    )


__all__ = ["LoginApp", "LoginAttempt", "LoginChoice", "run_login_tui"]
