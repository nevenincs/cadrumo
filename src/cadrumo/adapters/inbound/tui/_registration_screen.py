"""The first screen: choose a name and a password, and the profile exists.

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
    :func:`~cadrumo.application.user_profile.assess_passphrase`
        The advisory banding behind the live strength line.
"""

from __future__ import annotations

from contextlib import ExitStack
from contextvars import copy_context
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, override

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Button, Footer, Input, Label, LoadingIndicator, Select, Static
from textual.worker import Worker, WorkerState

from ....core import PassphraseStrength
from ....core.config import override_settings
from ....core.external_constants import UTF_8_ENCODING
from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES, output_language, tr
from ._theme import BASE_CSS, ContentScroll, install_cadrumo_themes, toggle_appearance

if TYPE_CHECKING:
    from collections.abc import Callable

    from ....application.user_profile import ProfileRegistrationOutcome


class PassphraseVerdict(Protocol):
    """What the screen needs to know about a candidate passphrase.

    Structural rather than concrete: the application's assessment already
    has this shape, so it satisfies the protocol without the screen
    importing it. The strength banding itself stays where the policy lives
    — this surface only renders the verdict.
    """

    @property
    def strength(self) -> PassphraseStrength:
        """Advisory band the candidate falls in."""
        ...  # pragma: no cover

    @property
    def minimum_length(self) -> int:
        """Shortest passphrase the storage layer will accept."""
        ...  # pragma: no cover

    @property
    def acceptable(self) -> bool:
        """Whether a profile can be created with this passphrase."""
        ...  # pragma: no cover


@dataclass(frozen=True, slots=True)
class RegistrationAttempt:
    """The outcome of asking the application to create a profile.

    A refusal arrives as text the screen displays, not as an exception it
    has to recognise. That keeps refusal *classification* with the layer
    that owns the rules, and leaves this screen doing what a screen does:
    show the operator what happened.
    """

    outcome: ProfileRegistrationOutcome | None = None
    refusal: str | None = None


def strength_copy(strength: PassphraseStrength, *, minimum_length: int) -> str:
    """Resolve the advisory line for one band.

    Every key is written as a literal ``tr(...)`` argument rather than
    looked up through a mapping. That is not style: the locale scaffolder
    finds keys by static scan, so a key reached through a variable is
    invisible to it and silently never lands in the catalogues. Spelling
    them out here keeps the copy scaffoldable and greppable, and the
    exhaustive match means a new band cannot ship without its own line.
    """
    match strength:
        case PassphraseStrength.TOO_SHORT:
            return tr("flows.registration.strength.too_short", minimum_length=minimum_length)
        case PassphraseStrength.WEAK:
            return tr("flows.registration.strength.weak")
        case PassphraseStrength.FAIR:
            return tr("flows.registration.strength.fair")
        case PassphraseStrength.STRONG:
            return tr("flows.registration.strength.strong")


_STRENGTH_CLASSES: Final[dict[PassphraseStrength, str]] = {
    PassphraseStrength.TOO_SHORT: "strength-refused",
    PassphraseStrength.WEAK: "strength-weak",
    PassphraseStrength.FAIR: "strength-fair",
    PassphraseStrength.STRONG: "strength-strong",
}
"""CSS class per band. Colour is never the sole signal — the band's own
words carry the meaning, and the class only reinforces it."""


def _language_options() -> list[tuple[str, str]]:
    """The chooser's rows, named under whichever language is on screen.

    Resolved on each call rather than once at import, because this is the
    one widget whose own rows have to follow the choice made in it.
    """
    return [
        (tr(f"wizard.setup.profile.output-language.choices.{language}.label"), language)
        for language in SUPPORTED_OUTPUT_LANGUAGES
    ]


class RegistrationApp(App["ProfileRegistrationOutcome | None"]):
    """Full-screen credential entry that creates and unlocks one profile."""

    CSS = (
        BASE_CSS
        + """
    #registration-intro { margin: 0 0 1 0; }
    #registration-why {
        color: $text-muted;
        border-left: outer $accent;
        padding: 0 0 0 2;
        margin: 0 0 1 0;
    }
    .field-label { text-style: bold; margin: 1 0 0 0; }
    .field-hint { color: $text-muted; margin: 0 0 1 0; }
    #strength-line { margin: 0 0 1 0; }
    .strength-refused { color: $error; }
    .strength-weak { color: $warning; }
    .strength-fair { color: $accent; }
    .strength-strong { color: $success; }
    #registration-refusal { color: $error; margin: 0 0 1 0; }
    #registration-busy { display: none; height: 1; margin: 0 0 1 0; }
    #registration-busy.busy { display: block; }
    #registration-actions { height: auto; align-horizontal: right; margin: 1 0 0 0; }
    """
    )

    BINDINGS: ClassVar = [
        Binding("f3", "toggle_appearance", "", show=False),
        Binding("escape", "abandon", "", show=False),
    ]

    def __init__(
        self,
        *,
        assess: Callable[[str], PassphraseVerdict],
        register: Callable[[str, str, str], RegistrationAttempt],
        suggested_name: str | None = None,
    ) -> None:
        super().__init__()
        self._assess_passphrase = assess
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
        self.outcome: ProfileRegistrationOutcome | None = None
        """The created profile, or ``None`` when the operator abandoned the
        screen. The caller distinguishes the two by this, never by an
        exception, because abandoning registration is an ordinary choice."""
        self.error: BaseException | None = None
        """Unexpected registration failure, re-raised by the synchronous runner."""
        self._registration_worker: Worker[RegistrationAttempt] | None = None
        """The one in-flight profile mutation; duplicate submissions are refused."""
        self._active_language = output_language()
        """The language the screen is currently written in.

        Held rather than re-read because the chooser has to be able to
        recognise its own writes: rewriting its rows re-seeds its value
        and reports that back as a selection, and this is what tells the
        two apart."""
        self._language_overrides = ExitStack()
        """Holds the settings override the screen is rendering under.

        A stack rather than a bare handle so each choice closes the one
        before it instead of nesting another block for every selection."""

    @override
    def compose(self) -> ComposeResult:
        """Yield the banner, the credential form, and the footer."""
        yield Static(id="registration-banner", classes="cadrumo-banner")
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
                _language_options(),
                value=self._active_language,
                allow_blank=False,
                id="field-output-language",
            )

            yield Static(id="registration-refusal")
            yield LoadingIndicator(id="registration-busy")
            with Vertical(id="registration-actions"):
                yield Button(tr("flows.registration.create_button"), id="btn-create", classes="-primary")
        yield Footer()

    def on_mount(self) -> None:
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
        """Make ``tr()`` resolve in the chosen language for this screen.

        Registration is the one surface with no profile behind it, so the
        profile-owned language preference the rest of the application
        reads does not exist yet. The settings-level override is the
        remaining door — the same one a ``--output-language`` flag opens
        for a single invocation — and it drops the resolver's language
        cache at both of its own boundaries, so nothing further is
        needed to make the next ``tr()`` see the change.

        The override lives in the message pump's context, which is why it
        is opened and closed from handlers running there and never from a
        caller outside them.
        """
        self._language_overrides.close()
        self._language_overrides.enter_context(override_settings(cadrumo_output_language=language))
        self._active_language = language

    def _render_localised_copy(self) -> None:
        """Resolve every operator-facing string under the active language.

        One pass over the page, re-runnable, so a language change re-words
        the chrome and the labels in place while the fields keep what the
        operator has already typed into them.
        """
        title = tr("flows.registration.title")
        self.title = title
        self.sub_title = tr("flows.registration.section")
        self.query_one("#registration-banner", Static).update(title)
        self.query_one("#registration-intro", Static).update(tr("flows.registration.intro"))
        self.query_one("#registration-why", Static).update(tr("flows.registration.why_password"))
        self.query_one("#registration-body", Vertical).border_title = tr("flows.registration.section")
        self.query_one("#label-username", Label).update(tr("flows.registration.username_label"))
        self.query_one("#hint-username", Static).update(tr("flows.registration.username_hint"))
        self.query_one("#label-password", Label).update(tr("flows.registration.password_label"))
        # The hint names the floor, so it has to be told what the floor
        # is; the assessor already reports it, and asking it for the
        # empty string is how this surface learns it without importing
        # the policy that owns it.
        self.query_one("#hint-password", Static).update(
            tr("flows.registration.password_hint", minimum_length=self._assess_passphrase("").minimum_length)
        )
        self.query_one("#label-confirm", Label).update(tr("flows.registration.confirm_label"))
        self.query_one("#label-output-language", Label).update(tr("wizard.setup.profile.output-language.prompt"))
        self.query_one("#btn-create", Button).label = tr("flows.registration.create_button")
        self._render_language_choices()
        self._render_strength(self.query_one("#field-password", Input).value)

    def _render_language_choices(self) -> None:
        """Re-word the chooser's own rows, keeping the current selection.

        Textual offers no way to re-word options in place, and replacing
        them re-seeds the selection, so the selection is put back
        afterwards — the echo that causes is what
        :meth:`on_select_changed` guards against.
        """
        chooser = self.query_one("#field-output-language", Select)
        chooser.set_options(_language_options())
        chooser.value = self._active_language

    # ── live feedback ───────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        """Re-render the advisory strength line as the password is typed."""
        if event.input.id == "field-password":
            self._render_strength(event.value)

    def _render_strength(self, candidate: str) -> None:
        """Update the band line, or clear it while the field is empty."""
        line = self.query_one("#strength-line", Static)
        line.remove_class(*_STRENGTH_CLASSES.values())
        if not candidate:
            line.update("")
            return
        assessment = self._assess_passphrase(candidate)
        line.add_class(_STRENGTH_CLASSES[assessment.strength])
        line.update(strength_copy(assessment.strength, minimum_length=assessment.minimum_length))

    def selected_output_language(self) -> str:
        """Return the closed language selection for the profile being created."""
        selected = self.query_one("#field-output-language", Select).value
        return selected if isinstance(selected, str) else output_language()

    # ── intents ─────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
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
        mismatched confirmation, a too-short password. Everything else
        (a duplicate label, a storage refusal) is the application door's
        decision, surfaced here as its translated message rather than
        re-derived, so the screen never becomes a second authority on what
        a valid registration is.
        """
        if self._registration_worker is not None:
            return

        username = self.query_one("#field-username", Input).value.strip()
        password = self.query_one("#field-password", Input).value
        confirm = self.query_one("#field-confirm", Input).value

        if not username:
            self._refuse(tr("flows.registration.refusal.username_required"))
            self.query_one("#field-username", Input).focus()
            return
        assessment = self._assess_passphrase(password)
        if not assessment.acceptable:
            self._refuse(strength_copy(assessment.strength, minimum_length=assessment.minimum_length))
            self.query_one("#field-password", Input).focus()
            return
        if password != confirm:
            self._refuse(tr("flows.registration.refusal.confirmation_mismatch"))
            self.query_one("#field-confirm", Input).focus()
            return

        selected_language = self.selected_output_language()
        self._set_busy(True)
        registration_context = copy_context()
        password_buffer = bytearray(password, UTF_8_ENCODING)

        def _register() -> RegistrationAttempt:
            try:
                return registration_context.run(
                    self._create_profile,
                    username,
                    password_buffer.decode(UTF_8_ENCODING),
                    selected_language,
                )
            finally:
                password_buffer[:] = b"\x00" * len(password_buffer)

        self._registration_worker = self.run_worker(
            _register,
            name="profile-registration",
            group="profile-registration",
            exit_on_error=False,
            exclusive=True,
            thread=True,
        )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Finish the one registration attempt back on Textual's UI task."""
        worker = self._registration_worker
        if worker is None or event.worker is not worker or event.state not in {WorkerState.SUCCESS, WorkerState.ERROR}:
            return
        self._registration_worker = None
        if event.state is WorkerState.ERROR:
            self.error = worker.error or RuntimeError("profile registration worker failed")
            self._leave(None)
            return
        attempt = worker.result
        if attempt is None:
            self.error = RuntimeError("profile registration worker returned no result")
            self._leave(None)
            return
        if attempt.outcome is None:
            self._set_busy(False)
            self._refuse(attempt.refusal or tr("flows.registration.refusal.username_required"))
            return
        self.outcome = attempt.outcome
        self._leave(self.outcome)

    def _leave(self, outcome: ProfileRegistrationOutcome | None) -> None:
        """Close the screen, releasing the language it was rendering under.

        Released here rather than at teardown because the override is
        bound to the message pump's context, and every caller of this is
        a handler running there. The created profile carries the chosen
        language of its own, so nothing downstream needs the override to
        survive the screen.
        """
        self._language_overrides.close()
        self.exit(outcome)

    def _set_busy(self, busy: bool) -> None:
        """Render registration progress and freeze inputs while storage mutates."""
        self.query_one("#registration-refusal", Static).update("")
        self.query_one("#registration-busy", LoadingIndicator).set_class(busy, "busy")
        for field_id in ("field-username", "field-password", "field-confirm"):
            self.query_one(f"#{field_id}", Input).disabled = busy
        self.query_one("#field-output-language", Select).disabled = busy
        self.query_one("#btn-create", Button).disabled = busy

    def action_abandon(self) -> None:
        """Leave without creating anything; the caller sees ``None``."""
        if self._registration_worker is not None:
            # A thread-backed mutation cannot be cancelled safely: cancellation
            # would only detach its result while encrypted storage may still land.
            return
        self.outcome = None
        self._leave(None)

    def action_toggle_appearance(self) -> None:
        toggle_appearance(self)

    def _refuse(self, message: str) -> None:
        self.query_one("#registration-refusal", Static).update(message)


def run_registration_tui(
    *,
    assess: Callable[[str], PassphraseVerdict],
    register: Callable[[str, str, str], RegistrationAttempt],
    suggested_name: str | None = None,
) -> ProfileRegistrationOutcome | None:
    """Run the registration screen and return the created profile, or ``None``.

    ``None`` means the operator abandoned the screen — an ordinary outcome,
    not an error, so the caller decides what to do rather than catching an
    exception to find out.
    """
    app = RegistrationApp(assess=assess, register=register, suggested_name=suggested_name)
    app.run()
    if app.error is not None:
        raise app.error
    return app.outcome


__all__ = ["PassphraseVerdict", "RegistrationApp", "RegistrationAttempt", "run_registration_tui"]
