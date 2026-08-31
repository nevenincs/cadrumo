"""Passphrase change: re-wrap one profile's key under a new password.

This screen collects the current passphrase (proof), the replacement, and
its confirmation, then hands all three to the injected rotation door. It
decides nothing about whether a new password is acceptable or whether a
confirmation mismatch refuses the change -- both are re-checked inside
:func:`~cadrumo.application.user_profile.passphrase_rotation
.rotate_profile_passphrase` regardless of what this screen already validated,
per that door's own stated contract ("a caller reaching this function
directly must not be able to skip the check").

See Also:
    :func:`~cadrumo.application.user_profile.passphrase_rotation.rotate_profile_passphrase`
        The application door this screen drives.
    :class:`~cadrumo.entrypoints.tui.secret.registration.RegistrationApp`
        The sibling credential surface this one borrows its live strength
        feedback and attempt shape from.
"""

from __future__ import annotations

from contextvars import copy_context
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Input, Label, Static

from ....core.external_constants import UTF_8_ENCODING
from ....core.i18n.render import tr
from ....entrypoints.tui.components.status import PinnedStatusBar
from ....entrypoints.tui.components.theme import BASE_CSS, install_cadrumo_themes, tokenised
from ....entrypoints.tui.components.widgets import ContentScroll
from .credentials import (
    CREDENTIAL_PANEL_CSS,
    CredentialAttempt,
    CredentialScreen,
    assessment_copy,
    assessment_css_class,
    run_credential_screen,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from ....application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
    from ....core.credentials import ProfilePasswordAssessment

__all__ = [
    "PassphraseChangeAttempt",
    "PassphraseChangeRefusal",
    "PassphraseScreen",
    "run_passphrase_change_tui",
]


@dataclass(frozen=True, slots=True)
class PassphraseChangeRefusal:
    """Secret-free localized refusal retained as data until rendering."""

    message_key: str
    context: tuple[tuple[str, object], ...] = ()

    def render(self, *, locale: str | None = None) -> str:
        """Resolve the refusal under the screen's active language."""
        return tr(self.message_key, locale=locale, **dict(self.context))


@dataclass(frozen=True, slots=True)
class PassphraseChangeAttempt:
    """The outcome of asking the application to rotate a profile's passphrase.

    Same shape as :class:`~cadrumo.entrypoints.tui.secret.registration
    .RegistrationAttempt`: a refusal arrives as text the screen displays,
    not as an exception it has to recognise, keeping refusal classification
    with the layer that owns the rotation rules.
    """

    outcome: ProfilePassphraseRotationOutcome | None = None
    expected_refusal: PassphraseChangeRefusal | None = None

    @property
    def refusal(self) -> str | None:
        """Render expected refusal data only at the presentation boundary."""
        return self.expected_refusal.render() if self.expected_refusal is not None else None


class PassphraseScreen(CredentialScreen["ProfilePassphraseRotationOutcome"]):
    """Full-screen credential entry that re-wraps one profile's password."""

    SCOPED_CSS = False
    DEFAULT_CSS = tokenised(
        BASE_CSS
        + CREDENTIAL_PANEL_CSS
        + """
    #passphrase-intro { margin: $cadrumo-space-0; }
    #passphrase-actions Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
    #strength-line { margin: $cadrumo-space-0; }
    .strength-refused { color: $error; }
    .strength-weak { color: $warning; }
    .strength-fair { color: $accent; }
    .strength-strong { color: $success; }
    """
    )

    ATTEMPT_NAME = "profile-passphrase-change"

    def __init__(
        self,
        *,
        assess: Callable[[str], ProfilePasswordAssessment],
        rotate: Callable[[str, str, str], PassphraseChangeAttempt],
    ) -> None:
        """Bind the password assessment and rotation presentation callbacks."""
        super().__init__()
        self._assess_profile_password = assess
        self._rotate_passphrase = rotate
        """Applies the typed current/new/confirmation triple and returns the
        presentation-ready attempt. Injected rather than imported, exactly
        like registration's ``register`` door: the profile identity is
        already closed over by whatever composed this screen."""

    @override
    def compose(self) -> ComposeResult:
        """Yield the banner, the three credential fields, and the footer."""
        yield Static(id="passphrase-banner", classes="cadrumo-banner")
        yield PinnedStatusBar(id="credential-status")
        with (
            ContentScroll(classes="cadrumo-scroll"),
            Vertical(classes="cadrumo-column"),
            Vertical(id="passphrase-body", classes="cadrumo-panel"),
        ):
            yield Static(id="passphrase-intro")

            yield Label(id="label-current", classes="field-label")
            yield Input(id="field-current", password=True)

            yield Label(id="label-new", classes="field-label")
            yield Static(id="hint-new", classes="field-hint")
            yield Input(id="field-new", password=True)
            yield Static(id="strength-line")

            yield Label(id="label-confirm", classes="field-label")
            yield Input(id="field-confirm", password=True)

            with Horizontal(id="passphrase-actions", classes="credential-actions"):
                yield Button(tr("flows.passphrase.cancel_button"), id="btn-cancel")
                yield Button(tr("flows.passphrase.change_button"), id="btn-change", classes="-primary")
        yield Footer()

    def on_mount(self) -> None:
        """Install the theme, render copy, and focus the current-password field."""
        install_cadrumo_themes(self.app)
        self._render_localised_copy()
        self.query_one("#field-current", Input).focus()

    def _render_localised_copy(self) -> None:
        """Resolve every operator-facing string on the page."""
        title = tr("flows.passphrase.title")
        self.title = title
        self.sub_title = tr("flows.passphrase.section")
        self.query_one("#passphrase-banner", Static).update(title)
        self.query_one("#passphrase-intro", Static).update(tr("flows.passphrase.intro"))
        self.query_one("#passphrase-body", Vertical).border_title = tr("flows.passphrase.section")
        self.query_one("#label-current", Label).update(tr("flows.passphrase.current_label"))
        self.query_one("#label-new", Label).update(tr("flows.passphrase.new_label"))
        self.query_one("#hint-new", Static).update(tr("flows.passphrase.new_hint"))
        self.query_one("#label-confirm", Label).update(tr("flows.passphrase.confirm_label"))
        self._render_strength(self.query_one("#field-new", Input).value)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Re-render the advisory strength line as the new password is typed."""
        if event.input.id == "field-new":
            self._render_strength(event.value)

    def _render_strength(self, candidate: str) -> None:
        """Update the band line, or clear it while the field is empty."""
        line = self.query_one("#strength-line", Static)
        line.remove_class("strength-refused", "strength-weak", "strength-fair", "strength-strong")
        if not candidate:
            line.update("")
            return
        assessment = self._assess_profile_password(candidate)
        line.add_class(assessment_css_class(assessment))
        line.update(assessment_copy(assessment))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route a change or cancellation button intent."""
        if event.button.id == "btn-change":
            self.action_change()
        elif event.button.id == "btn-cancel":
            self.action_abandon()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter advances to the next field, and submits from the last one."""
        order = ("field-current", "field-new", "field-confirm")
        current = event.input.id
        if current == order[-1]:
            self.action_change()
            return
        if current in order:
            self.query_one(f"#{order[order.index(current) + 1]}", Input).focus()

    def action_change(self) -> None:
        """Validate the form locally, then rotate the passphrase and exit.

        Local checks only catch what the screen can see -- a blank current
        password, an unacceptable new one, a mismatched confirmation.
        Everything else (a wrong current passphrase, a storage refusal) is
        the application door's decision, surfaced here as its translated
        message rather than re-derived.
        """
        if self.attempt_in_flight:
            return

        current_passphrase = self.query_one("#field-current", Input).value
        new_passphrase = self.query_one("#field-new", Input).value
        confirm = self.query_one("#field-confirm", Input).value

        if not current_passphrase:
            self.refuse(tr("flows.passphrase.refusal.current_required"))
            self.query_one("#field-current", Input).focus()
            return
        assessment = self._assess_profile_password(new_passphrase)
        if not assessment.accepted:
            self.refuse(assessment_copy(assessment))
            self.query_one("#field-new", Input).focus()
            return
        if new_passphrase != confirm:
            self.refuse(tr("flows.passphrase.refusal.confirmation_mismatch"))
            self.query_one("#field-confirm", Input).focus()
            return

        change_context = copy_context()
        current_buffer = bytearray(current_passphrase, UTF_8_ENCODING)
        new_buffer = bytearray(new_passphrase, UTF_8_ENCODING)
        confirm_buffer = bytearray(confirm, UTF_8_ENCODING)

        def _rotate() -> CredentialAttempt[ProfilePassphraseRotationOutcome]:
            try:
                return change_context.run(
                    self._rotate_passphrase,
                    current_buffer.decode(UTF_8_ENCODING),
                    new_buffer.decode(UTF_8_ENCODING),
                    confirm_buffer.decode(UTF_8_ENCODING),
                )
            finally:
                current_buffer[:] = b"\x00" * len(current_buffer)
                new_buffer[:] = b"\x00" * len(new_buffer)
                confirm_buffer[:] = b"\x00" * len(confirm_buffer)

        self.start_attempt(_rotate)

    @override
    def resolve_attempt_refusal(self, attempt: CredentialAttempt[ProfilePassphraseRotationOutcome]) -> str | None:
        """Render structured rotation refusals under this screen's locale."""
        if isinstance(attempt, PassphraseChangeAttempt) and attempt.expected_refusal is not None:
            return attempt.expected_refusal.render()
        return attempt.refusal

    @override
    def default_refusal(self) -> str:
        return tr("flows.passphrase.refusal.change_failed")

    @override
    def progress_message(self) -> str:
        return tr("flows.passphrase.change_button")

    @override
    def set_busy(self, *, busy: bool) -> None:
        """Render change progress and freeze inputs while storage mutates."""
        super().set_busy(busy=busy)
        for field_id in ("field-current", "field-new", "field-confirm"):
            self.query_one(f"#{field_id}", Input).disabled = busy
        self.query_one("#btn-change", Button).disabled = busy
        self.query_one("#btn-cancel", Button).disabled = busy


def run_passphrase_change_tui(
    *,
    assess: Callable[[str], ProfilePasswordAssessment],
    rotate: Callable[[str, str, str], PassphraseChangeAttempt],
) -> ProfilePassphraseRotationOutcome | None:
    """Run the passphrase-change screen and return the new posture, or ``None``.

    ``None`` means the operator abandoned the screen -- an ordinary outcome,
    not an error.
    """
    return run_credential_screen(PassphraseScreen(assess=assess, rotate=rotate))
