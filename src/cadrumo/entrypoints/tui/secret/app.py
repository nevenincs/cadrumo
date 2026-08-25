"""The profile-secret application surfaces: create once, then unlock.

This is the literal first surface of the application. Everything else —
the manager, the overview, filing — is behind it, because everything else
needs an unlocked encrypted bucket and this is where that bucket is
created.

The screen is deliberately a single page rather than a paged flow. The
three fields are one decision ("who am I on this machine, and what
protects it"), and a password field needs its confirmation and its
strength feedback visible at the same time as itself; splitting them
across pages would make the operator hold state in their head for no
gain. The paged substrate remains the right shape for the many-question
profile detail that follows, and is used there.

The copy carries what an offline CLI tool owes the operator at this
moment: what is being created, why a password is being asked for at all
when nothing is going over a network, and what happens if it is lost.
That last point is not decoration — the passphrase derives the
key-encryption key, so there is no reset path, and saying so before the
field rather than after a failure is the difference between an informed
choice and a trap.

See Also:
    :func:`~cadrumo.application.user_profile.register_profile_with_credentials`
        The application door this screen drives; it creates the profile,
        provisions the key material, and leaves the session unlocked.
    :func:`~cadrumo.core.credentials.assess_profile_password`
        The canonical assessment behind validation and the live strength line.
    :class:`LoginApp`
        The other credential surface; the two share their attempt
        lifecycle and panel layout through ``CredentialApp``.
"""

from __future__ import annotations

from contextvars import copy_context
from dataclasses import dataclass
from threading import Event
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, cast, override

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, Select, Static
from textual.worker import Worker, WorkerState

from ....core.credentials import (
    PROFILE_PASSWORD_MIN_SCALARS,
    PassphraseStrength,
    ProfilePasswordAssessment,
)
from ....core.external_constants import UTF_8_ENCODING
from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES, output_language, tr
from ....entrypoints.tui.components.status import PinnedStatusBar
from ....entrypoints.tui.components.theme import BASE_CSS, install_cadrumo_themes, toggle_appearance
from ....entrypoints.tui.components.widgets import ContentScroll

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from ....application.user_profile.login_interaction import ProfileLoginAttempt, ProfileLoginChoice
    from ....application.user_profile.login_session import ProfileLoginOutcome
    from ....application.user_profile.prospective_password import ProspectiveProfilePasswordRefusal
    from ....application.user_profile.recovery_custody import ProfileRecoveryEnrollment
    from ....application.user_profile.registration import ProfileRegistrationOutcome


CREDENTIAL_PANEL_CSS: Final[str] = """
.field-label { text-style: bold; margin: 0; }
.field-hint { color: $text-muted; margin: 0; }
.credential-actions { height: auto; align-horizontal: right; margin: 0; }
"""
"""Layout shared by the login and registration credential panels."""


class CredentialAttempt[OutcomeT](Protocol):
    """The secret-free result shape returned by an injected credential door."""

    @property
    def outcome(self) -> OutcomeT | None:
        """Successful outcome, or ``None`` when the door refused."""
        ...  # pragma: no cover

    @property
    def refusal(self) -> str | None:
        """Safe rendered refusal, or ``None`` when no detail was supplied."""
        ...  # pragma: no cover


class CredentialApp[OutcomeT](App[OutcomeT | None]):
    """Host one bounded, thread-backed credential attempt at a time."""

    BINDINGS: ClassVar = [
        Binding("f3", "toggle_appearance", "", show=False),
        Binding("escape", "abandon", "", show=False),
    ]

    STATUS_ID: ClassVar[str] = "#credential-status"
    ATTEMPT_NAME: ClassVar[str]

    def __init__(self) -> None:
        """Initialise an empty ephemeral attempt result."""
        super().__init__()
        self.outcome: OutcomeT | None = None
        self.error: BaseException | None = None
        self._attempt: Worker[CredentialAttempt[OutcomeT]] | None = None

    @property
    def attempt_in_flight(self) -> bool:
        """Whether a storage call is running and cannot be duplicated."""
        return self._attempt is not None

    def start_attempt(self, work: Callable[[], CredentialAttempt[OutcomeT]]) -> None:
        """Run ``work`` off the event loop as this screen's sole attempt."""
        if self._attempt is not None:
            return
        self.error = None
        self.set_busy(busy=True)
        self._attempt = self.run_worker(
            work,
            name=self.ATTEMPT_NAME,
            group=self.ATTEMPT_NAME,
            exit_on_error=False,
            exclusive=True,
            thread=True,
        )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Settle the sole attempt back on Textual's UI task."""
        worker = self._attempt
        event_worker = cast("Worker[CredentialAttempt[OutcomeT]]", event.worker)
        if worker is None or event_worker is not worker or event.state not in {WorkerState.SUCCESS, WorkerState.ERROR}:
            return
        self._attempt = None
        if event.state is WorkerState.ERROR:
            self.error = worker.error or RuntimeError(f"{self.ATTEMPT_NAME} worker failed")
            self.set_busy(busy=False)
            self.refuse(self._resolved_worker_failure(self.error))
            return
        attempt = worker.result
        if attempt is None:
            self.error = RuntimeError(f"{self.ATTEMPT_NAME} worker returned no result")
            self.set_busy(busy=False)
            self.refuse(self._resolved_worker_failure(self.error))
            return
        if attempt.outcome is None:
            self.set_busy(busy=False)
            self.refuse(self.resolve_attempt_refusal(attempt) or self.default_refusal())
            return
        self.outcome = attempt.outcome
        self.leave(attempt.outcome)

    def _resolved_worker_failure(self, error: BaseException) -> str:
        """Render an unexpected failure without leaking diagnostic prose."""
        try:
            from ....core.errors import resolve_error_message

            detail = resolve_error_message(error, locale=self.output_locale()).strip()
        except (LookupError, TypeError, ValueError):
            detail = ""
        guidance = tr("errors.internal.internal_cli_unexpected_boundary", locale=self.output_locale())
        return f"{detail} {guidance}".strip()

    def output_locale(self) -> str | None:
        """Return this app's explicit presentation locale, if it owns one."""
        return None

    def resolve_attempt_refusal(self, attempt: CredentialAttempt[OutcomeT]) -> str | None:
        """Render one door refusal at this app's presentation boundary."""
        return attempt.refusal

    def default_refusal(self) -> str:
        """Text shown when a refusal carries no message."""
        raise NotImplementedError

    def refuse(self, message: str) -> None:
        """Show one refusal without leaving, allowing an in-place retry."""
        self.query_one(self.STATUS_ID, PinnedStatusBar).show_error(message)

    def set_busy(self, *, busy: bool) -> None:
        """Show progress and clear the previous refusal."""
        status = self.query_one(self.STATUS_ID, PinnedStatusBar)
        if busy:
            status.show_progress(self.progress_message())
        else:
            status.clear_message()

    def progress_message(self) -> str:
        """Operator-facing description of the subclass's in-flight attempt."""
        raise NotImplementedError

    def leave(self, outcome: OutcomeT | None) -> None:
        """Close the screen and return its optional outcome."""
        self.exit(outcome)

    def action_abandon(self) -> None:
        """Leave without a result unless storage work is still in flight."""
        if self._attempt is not None:
            return
        self.outcome = None
        self.leave(None)

    def action_toggle_appearance(self) -> None:
        """Switch the rendered terminal appearance."""
        toggle_appearance(self)


def run_credential_app[OutcomeT](app: CredentialApp[OutcomeT]) -> OutcomeT | None:
    """Run one credential screen and return its optional outcome."""
    app.run()
    return app.outcome


_STRENGTH_CLASSES: Final[dict[PassphraseStrength, str]] = {
    PassphraseStrength.WEAK: "strength-weak",
    PassphraseStrength.FAIR: "strength-fair",
    PassphraseStrength.STRONG: "strength-strong",
}


def assessment_refusal(
    assessment: ProfilePasswordAssessment,
) -> ProspectiveProfilePasswordRefusal | None:
    """Project a canonical assessment through the application facade."""
    from ....application.user_profile.prospective_password import prospective_profile_password_refusal

    return prospective_profile_password_refusal(assessment)


def assessment_copy(assessment: ProfilePasswordAssessment, *, locale: str | None = None) -> str:
    """Resolve localized validation or advisory copy for one assessment."""
    refusal = assessment_refusal(assessment)
    if refusal is not None:
        return tr(refusal.translated_message, locale=locale, **dict(refusal.context))
    match assessment.strength:
        case PassphraseStrength.WEAK:
            return tr("flows.registration.strength.weak", locale=locale)
        case PassphraseStrength.FAIR:
            return tr("flows.registration.strength.fair", locale=locale)
        case PassphraseStrength.STRONG:
            return tr("flows.registration.strength.strong", locale=locale)


def assessment_css_class(assessment: ProfilePasswordAssessment) -> str:
    """Return the presentation class for a secret-free assessment."""
    if not assessment.accepted:
        return "strength-refused"
    return _STRENGTH_CLASSES[assessment.strength]


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


@dataclass(frozen=True, slots=True)
class RegistrationRefusal:
    """Secret-free localized refusal retained as data until rendering."""

    message_key: str
    context: tuple[tuple[str, object], ...] = ()

    def render(self, *, locale: str | None = None) -> str:
        """Resolve the refusal under the screen's active language."""
        return tr(self.message_key, locale=locale, **dict(self.context))


class RecoveryHandoverCancelledError(Exception):
    """The operator declined the one-time recovery possession gate."""

    __bare_base_rationale__: ClassVar[str] = (
        "internal-recovery-handover-cancellation-signal: this reports a deliberate operator choice, not a "
        "fault; the frontend catches it by name and renders a RegistrationRefusal message key"
    )


@dataclass(frozen=True, slots=True)
class RegistrationAttempt:
    """The outcome of asking the application to create a profile.

    A refusal arrives as text the screen displays, not as an exception it
    has to recognise. That keeps refusal *classification* with the layer
    that owns the rules, and leaves the screen doing what a screen does:
    show the operator what happened.

    Recovery material never rides this post-registration result. The screen's
    blocking handoff runs inside the application callback, before publication,
    and the application owns wiping the material on every exit.
    """

    outcome: ProfileRegistrationOutcome | None = None
    expected_refusal: RegistrationRefusal | None = None

    @property
    def refusal(self) -> str | None:
        """Render expected refusal data only at the presentation boundary."""
        return self.expected_refusal.render() if self.expected_refusal is not None else None


def _language_options(*, locale: str | None = None) -> list[tuple[str, str]]:
    """The chooser's rows, named under whichever language is on screen.

    Resolved on each call rather than once at import, because this is the
    one widget whose own rows have to follow the choice made in it.
    """
    return [
        (tr(f"wizard.setup.profile.output-language.choices.{language}.label", locale=locale), language)
        for language in SUPPORTED_OUTPUT_LANGUAGES
    ]


class RegistrationApp(CredentialApp["ProfileRegistrationOutcome"]):
    """Full-screen credential entry that creates and unlocks one profile."""

    CSS = (
        BASE_CSS
        + CREDENTIAL_PANEL_CSS
        + """
    #registration-intro { margin: 0; }
    #registration-why {
        color: $text-muted;
        border-left: outer $accent;
        padding: 0 0 0 1;
        margin: 0;
    }
    #strength-line { margin: 0; }
    .strength-refused { color: $error; }
    .strength-weak { color: $warning; }
    .strength-fair { color: $accent; }
    .strength-strong { color: $success; }
    """
    )

    ATTEMPT_NAME = "profile-registration"

    def __init__(
        self,
        *,
        assess: Callable[[str], ProfilePasswordAssessment],
        register: Callable[
            [str, str, str, Callable[[ProfileRecoveryEnrollment], str]],
            RegistrationAttempt,
        ],
        suggested_name: str | None = None,
    ) -> None:
        """Bind the password assessment and registration presentation callbacks."""
        super().__init__()
        self._assess_profile_password = assess
        """Passphrase banding, injected rather than imported.

        The adapter tier renders; it does not reach up into the application
        layer for its own data. Injection is the same shape the status page
        already uses, and it also makes the screen drivable against a
        deliberate refusal without contriving one in real storage."""
        self._create_profile = register
        """Named to avoid ``App._register``, a Textual internal that
        silently swallowed the door and passed the app itself as the
        profile label."""
        self._suggested_name = suggested_name or ""
        """Name carried in from the command line, prefilled into the field.

        A prefill, never a commitment: this screen is where the decision is
        made, so the operator can still change it before creating."""
        self._active_language = output_language()
        """The language the screen is currently written in.

        Held rather than re-read because the chooser has to be able to
        recognise its own writes: rewriting its rows re-seeds its value
        and reports that back as a selection, and this is what tells the
        two apart."""
        self._pending_recovery_handoffs: set[Event] = set()

    @override
    def compose(self) -> ComposeResult:
        """Yield the banner, the credential form, and the footer."""
        yield Static(id="registration-banner", classes="cadrumo-banner")
        yield PinnedStatusBar(id="credential-status")
        with (
            ContentScroll(classes="cadrumo-scroll"),
            Vertical(classes="cadrumo-column"),
            Vertical(id="registration-body", classes="cadrumo-panel"),
        ):
            yield Static(id="registration-intro")
            yield Static(id="registration-why")

            # Every translated string on this page is written by
            # :meth:`_render_localised_copy` rather than here, because the
            # operator chooses the page's language on the page itself and
            # each of these has to be able to change without the widget
            # holding it being rebuilt — a rebuild would discard what has
            # already been typed into the fields between them. Composing
            # them empty keeps one place that decides what they say.
            yield Label(id="label-username", classes="field-label")
            yield Static(id="hint-username", classes="field-hint")
            yield Input(id="field-username", value=self._suggested_name)

            yield Label(id="label-password", classes="field-label")
            yield Static(id="hint-password", classes="field-hint")
            yield Input(id="field-password", password=True)
            yield Static(id="strength-line")

            yield Label(id="label-confirm", classes="field-label")
            yield Input(id="field-confirm", password=True)

            yield Label(id="label-output-language", classes="field-label")
            # The one widget that cannot be composed empty: a chooser that
            # refuses a blank selection also refuses an empty option set.
            yield Select[str](
                _language_options(locale=self._active_language),
                value=self._active_language,
                allow_blank=False,
                id="field-output-language",
            )

            with Vertical(id="registration-actions", classes="credential-actions"):
                yield Button(
                    tr("flows.registration.create_button", locale=self._active_language),
                    id="btn-create",
                    classes="-primary",
                )
        yield Footer()

    def on_mount(self) -> None:
        """Install the theme, render copy, and focus profile-name entry."""
        install_cadrumo_themes(self)
        self._render_localised_copy()
        self.query_one("#field-username", Input).focus()

    # ── language ────────────────────────────────────────────────────────

    def on_select_changed(self, event: Select.Changed) -> None:
        """Re-word the whole page in the language the operator just picked.

        The choice has to reach the screen and not only the profile it
        will create: this is the first surface of the application, so an
        operator who cannot read the language it opened in has nothing
        else to go to. Applying it here is also what makes the chooser
        legible as a chooser — the page answering in the chosen language
        is the confirmation that the setting took.
        """
        if event.select.id != "field-output-language":
            return
        language = event.value
        if not isinstance(language, str):
            return
        # Rewriting the chooser's own rows re-seeds its value, so the
        # widget reports its own rewrite back here. An event carrying
        # anything but the widget's current value has been superseded,
        # and one naming the language already on screen has nothing left
        # to do; both are that echo rather than an operator's choice.
        if language != event.select.value or language == self._active_language:
            return
        self._activate_output_language(language)
        self._render_localised_copy()

    def _activate_output_language(self, language: str) -> None:
        """Select the explicit locale used by this registration surface.

        Textual dispatches lifecycle hooks through distinct asyncio contexts,
        so a context-local settings token cannot be owned by the app lifecycle.
        Registration passes its selected locale at every translation boundary;
        the choice is app-local and leaves no ambient setting to restore.
        """
        self._active_language = language

    def _render_localised_copy(self) -> None:
        """Resolve every operator-facing string under the active language.

        One pass over the page, re-runnable, so a language change re-words
        the chrome and the labels in place while the fields keep what the
        operator has already typed into them.
        """
        locale = self._active_language
        title = tr("flows.registration.title", locale=locale)
        self.title = title
        self.sub_title = tr("flows.registration.section", locale=locale)
        self.query_one("#registration-banner", Static).update(title)
        self.query_one("#registration-intro", Static).update(tr("flows.registration.intro", locale=locale))
        self.query_one("#registration-why", Static).update(tr("flows.registration.why_password", locale=locale))
        self.query_one("#registration-body", Vertical).border_title = tr("flows.registration.section", locale=locale)
        self.query_one("#label-username", Label).update(tr("flows.registration.username_label", locale=locale))
        self.query_one("#hint-username", Static).update(tr("flows.registration.username_hint", locale=locale))
        self.query_one("#label-password", Label).update(tr("flows.registration.password_label", locale=locale))
        self.query_one("#hint-password", Static).update(
            tr("flows.registration.password_hint", locale=locale, minimum_length=PROFILE_PASSWORD_MIN_SCALARS)
        )
        self.query_one("#label-confirm", Label).update(tr("flows.registration.confirm_label", locale=locale))
        self.query_one("#label-output-language", Label).update(
            tr("wizard.setup.profile.output-language.prompt", locale=locale)
        )
        self.query_one("#btn-create", Button).label = tr("flows.registration.create_button", locale=locale)
        self._render_language_choices()
        self._render_strength(self.query_one("#field-password", Input).value)

    def _render_language_choices(self) -> None:
        """Re-word the chooser's own rows, keeping the current selection.

        Textual offers no way to re-word options in place, and replacing
        them re-seeds the selection, so the selection is put back
        afterwards — the echo that causes is what
        :meth:`on_select_changed` guards against.
        """
        chooser = cast("Select[str]", self.query_one("#field-output-language", Select))
        chooser.set_options(_language_options(locale=self._active_language))
        chooser.value = self._active_language

    # ── live feedback ───────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        """Re-render the advisory strength line as the password is typed."""
        if event.input.id == "field-password":
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
        line.update(assessment_copy(assessment, locale=self._active_language))

    def selected_output_language(self) -> str:
        """Return the closed language selection for the profile being created."""
        selected = cast("Select[str]", self.query_one("#field-output-language", Select)).value
        return selected if isinstance(selected, str) else self._active_language

    @override
    def output_locale(self) -> str:
        """Return the registration surface's task-independent locale."""
        return self._active_language

    @override
    def resolve_attempt_refusal(self, attempt: CredentialAttempt[ProfileRegistrationOutcome]) -> str | None:
        """Render structured registration refusals under this screen's locale."""
        if isinstance(attempt, RegistrationAttempt) and attempt.expected_refusal is not None:
            return attempt.expected_refusal.render(locale=self._active_language)
        return attempt.refusal

    # ── intents ─────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route the create-profile button intent."""
        if event.button.id == "btn-create":
            self.action_create()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter advances to the next field, and submits from the last one."""
        order = ("field-username", "field-password", "field-confirm")
        current = event.input.id
        if current == order[-1]:
            self.action_create()
            return
        if current in order:
            self.query_one(f"#{order[order.index(current) + 1]}", Input).focus()

    def action_create(self) -> None:
        """Validate the form locally, then create the profile and exit.

        Local checks cover only what the screen can see — a blank name, a
        mismatched confirmation, an invalid password. Everything else
        (a duplicate label, a storage refusal) is the application door's
        decision, surfaced here as its translated message rather than
        re-derived, so the screen never becomes a second authority on what
        a valid registration is.
        """
        if self.attempt_in_flight:
            return

        username = self.query_one("#field-username", Input).value.strip()
        password = self.query_one("#field-password", Input).value
        confirm = self.query_one("#field-confirm", Input).value

        if not username:
            self.refuse(tr("flows.registration.refusal.username_required", locale=self._active_language))
            self.query_one("#field-username", Input).focus()
            return
        assessment = self._assess_profile_password(password)
        if not assessment.accepted:
            self.refuse(assessment_copy(assessment, locale=self._active_language))
            self.query_one("#field-password", Input).focus()
            return
        if password != confirm:
            self.refuse(tr("flows.registration.refusal.confirmation_mismatch", locale=self._active_language))
            self.query_one("#field-confirm", Input).focus()
            return

        selected_language = self.selected_output_language()
        registration_context = copy_context()
        password_buffer = bytearray(password, UTF_8_ENCODING)

        def _register() -> CredentialAttempt[ProfileRegistrationOutcome]:
            try:
                attempt = registration_context.run(
                    self._create_profile,
                    username,
                    password_buffer.decode(UTF_8_ENCODING),
                    selected_language,
                    self._confirm_recovery_possession,
                )
            finally:
                password_buffer[:] = b"\x00" * len(password_buffer)
            return cast("CredentialAttempt[ProfileRegistrationOutcome]", attempt)

        self.start_attempt(_register)

    @override
    def default_refusal(self) -> str:
        return tr("flows.registration.refusal.username_required", locale=self._active_language)

    @override
    def progress_message(self) -> str:
        return tr("flows.registration.create_button", locale=self._active_language)

    def _confirm_recovery_possession(self, enrollment: ProfileRecoveryEnrollment) -> str:
        """Show words, block for confirmation, and return exact proof."""
        resolved = Event()
        self._pending_recovery_handoffs.add(resolved)
        supplied_proof: str | None = None

        def _accept(proof: str) -> None:
            nonlocal supplied_proof
            supplied_proof = proof
            resolved.set()

        def _refuse() -> None:
            resolved.set()

        def _show() -> None:
            self.push_screen(
                RecoveryWordsScreen(
                    enrollment=enrollment,
                    locale=self._active_language,
                    on_confirm=_accept,
                    on_cancel=_refuse,
                )
            )

        try:
            self.call_from_thread(_show)
            # Shutdown explicitly releases this event in ``on_unmount``; the
            # bound is a final guard for a failed message-loop lifecycle.
            if not resolved.wait(timeout=30.0) or supplied_proof is None:
                raise RecoveryHandoverCancelledError
            return supplied_proof
        finally:
            self._pending_recovery_handoffs.discard(resolved)

    def on_unmount(self) -> None:
        """Release every pre-publication handoff when the application stops."""
        for pending in tuple(self._pending_recovery_handoffs):
            pending.set()

    @override
    def set_busy(self, *, busy: bool) -> None:
        """Render registration progress and freeze inputs while storage mutates."""
        super().set_busy(busy=busy)
        for field_id in ("field-username", "field-password", "field-confirm"):
            self.query_one(f"#{field_id}", Input).disabled = busy
        self.query_one("#field-output-language", Select).disabled = busy
        self.query_one("#btn-create", Button).disabled = busy


class RecoveryWordsScreen(Screen[None]):
    """Show the mnemonic once and return masked exact re-entry proof."""

    DEFAULT_CSS = """
    RecoveryWordsScreen {
        align: center middle;
    }
    #words-panel {
        width: 100%;
        height: auto;
        border: round $primary;
        padding: 1 2;
    }
    #words-heading { text-style: bold; margin-bottom: 1; }
    #words-value { color: $warning; margin-bottom: 1; }
    #words-warning { color: $text-muted; margin-bottom: 1; }
    #words-actions { height: auto; align-horizontal: right; }
    """

    def __init__(
        self,
        *,
        enrollment: ProfileRecoveryEnrollment,
        locale: str,
        on_confirm: Callable[[str], None],
        on_cancel: Callable[[], None],
    ) -> None:
        """Bind one ephemeral recovery enrollment and its terminal callbacks."""
        super().__init__()
        self._enrollment = enrollment
        self._locale = locale
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._resolved = False

    @override
    def compose(self) -> ComposeResult:
        with Container(id="words-panel"):
            yield Static(tr("cli.config.custody.recovery_words_heading", locale=self._locale), id="words-heading")
            yield Static(self._enrollment.recovery_key.mnemonic, id="words-value")
            yield Static(tr("cli.config.custody.recovery_words_warning", locale=self._locale), id="words-warning")
            yield Input(
                password=True,
                placeholder=tr("cli.config.profile.create_recovery_verification_prompt", locale=self._locale),
                id="field-recovery-verification",
            )
            with Container(id="words-actions"):
                yield Button(tr("cli.config.custody.recovery_words_cancel", locale=self._locale), id="btn-cancel-words")
                yield Button(
                    tr("cli.config.custody.recovery_words_confirm", locale=self._locale), id="btn-confirm-words"
                )

    @on(Button.Pressed, "#btn-confirm-words")
    def _confirm(self) -> None:
        if self._resolved:
            return
        supplied = self.query_one("#field-recovery-verification", Input).value
        expected = self._enrollment.recovery_key.mnemonic
        try:
            if supplied != expected:
                self._refuse_once()
                self.dismiss(None)
                return
        finally:
            self.query_one("#field-recovery-verification", Input).value = ""
            del expected
        self._resolved = True
        self.dismiss(None)
        self._on_confirm(supplied)

    @on(Button.Pressed, "#btn-cancel-words")
    def _cancel(self) -> None:
        self._refuse_once()
        self.dismiss(None)

    def on_unmount(self) -> None:
        """Treat escape, shutdown, and every non-confirm exit as refusal."""
        self._refuse_once()

    def _refuse_once(self) -> None:
        if self._resolved:
            return
        self._resolved = True
        self._enrollment.recovery_key.wipe()
        self._on_cancel()


def run_registration_tui(
    *,
    assess: Callable[[str], ProfilePasswordAssessment],
    register: Callable[
        [str, str, str, Callable[[ProfileRecoveryEnrollment], str]],
        RegistrationAttempt,
    ],
    suggested_name: str | None = None,
) -> ProfileRegistrationOutcome | None:
    """Run the registration screen and return the created profile, or ``None``.

    ``None`` means the operator abandoned the screen — an ordinary outcome,
    not an error, so the caller decides what to do rather than catching an
    exception to find out.
    """
    return run_credential_app(
        RegistrationApp(assess=assess, register=register, suggested_name=suggested_name),
    )


__all__ = [
    "LoginApp",
    "RecoveryHandoverCancelledError",
    "RecoveryWordsScreen",
    "RegistrationApp",
    "RegistrationAttempt",
    "RegistrationRefusal",
    "assessment_refusal",
    "run_login_tui",
    "run_registration_tui",
]
