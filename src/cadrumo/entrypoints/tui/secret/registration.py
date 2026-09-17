"""Registration: full-screen credential entry that creates and unlocks one profile.

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

Recovery is an explicit, skippable follow-up. Once the profile exists the
screen asks whether to set up a recovery code, says plainly what it buys
(a way to reset a forgotten passphrase) and what declining means, and
defaults to declining. Choosing it shows the code once and asks for it
back before anything is installed; cancelling at any point leaves the
freshly created profile exactly as it was, with its passphrase as its only
door.

See Also:
    :func:`~cadrumo.application.user_profile.registration.register_profile_with_credentials`
        The application door this screen drives; it creates the profile,
        provisions the key material, and leaves the session unlocked.
    :func:`~cadrumo.application.user_profile.recovery_custody.enroll_profile_recovery`
        The optional second door, driven from the offer that follows creation.
    :func:`~cadrumo.core.credentials.assess_profile_password`
        The canonical assessment behind validation and the live strength line.
    :class:`~cadrumo.entrypoints.tui.secret.login.LoginScreen`
        The other credential surface; the two share their attempt
        lifecycle and panel layout through ``CredentialScreen``.
"""

from __future__ import annotations

from contextvars import copy_context
from dataclasses import dataclass
from threading import Event
from typing import TYPE_CHECKING, ClassVar, cast, override

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, Select, Static
from textual.worker import Worker, WorkerState

from ....core.credentials import PROFILE_PASSWORD_MIN_SCALARS
from ....core.errors.hierarchy import CadrumoError, InternalInvariantError
from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, UTF_8_ENCODING
from ....core.i18n.render import output_language, tr
from ....entrypoints.tui.components.status import PinnedStatusBar
from ....entrypoints.tui.components.theme import BASE_CSS, install_cadrumo_themes, toggle_appearance, tokenised
from .credentials import (
    CREDENTIAL_PANEL_CSS,
    CredentialAttempt,
    CredentialScreen,
    assessment_copy,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from ....application.user_profile.recovery_custody import ProfileRecoveryEnrollment
    from ....application.user_profile.registration import ProfileRegistrationOutcome
    from ....core.credentials import ProfilePasswordAssessment

__all__ = [
    "RecoveryCodeScreen",
    "RecoveryEnrollmentAttempt",
    "RecoveryHandoverDeclinedError",
    "RecoveryOfferScreen",
    "RegistrationAttempt",
    "RegistrationRefusal",
    "RegistrationScreen",
    "build_profile_recovery_enrollment_attempt",
    "build_profile_registration_attempt",
]


@dataclass(frozen=True, slots=True)
class RegistrationRefusal:
    """Secret-free localized refusal retained as data until rendering."""

    message_key: str
    context: tuple[tuple[str, object], ...] = ()

    def render(self, *, locale: str | None = None) -> str:
        """Resolve the refusal under the screen's active language."""
        return tr(self.message_key, locale=locale, **dict(self.context))


#: Application refusals whose canonical wording addresses a command-line
#: operator. The door's classification is kept; only the rendered sentence is
#: exchanged for one a full-screen operator can act on, because a TUI offers no
#: prompt at which to run the command the shared message recommends.
_SURFACE_REFUSAL_LOCALE_KEYS: dict[str, str] = {
    "application.user_profile.errors.profile_already_exists": ("flows.registration.refusal.profile_already_exists"),
}

#: Poll interval for the recovery code handoff. This paces the liveness check
#: only; it is never a deadline on the operator, who may take as long as
#: copying down a code actually requires.
_RECOVERY_HANDOFF_POLL_SECONDS = 0.1

_RECOVERY_ENROLLMENT_WORKER = "profile-recovery-enrollment"


class RecoveryHandoverDeclinedError(CadrumoError):
    """The operator did not confirm the code; raised inside the handover to abort enrolment.

    The application treats any exception from the handover as "nothing was
    installed", which is exactly the outcome a decline wants. The enrolment
    door in this module catches it and reports a decline, not a refusal.
    """


@dataclass(frozen=True, slots=True)
class RegistrationAttempt:
    """The outcome of asking the application to create a profile.

    A refusal arrives as text the screen displays, not as an exception it
    has to recognise. That keeps refusal *classification* with the layer
    that owns the rules, and leaves the screen doing what a screen does:
    show the operator what happened.
    """

    outcome: ProfileRegistrationOutcome | None = None
    expected_refusal: RegistrationRefusal | None = None

    @property
    def refusal(self) -> str | None:
        """Render expected refusal data only at the presentation boundary."""
        return self.expected_refusal.render() if self.expected_refusal is not None else None


@dataclass(frozen=True, slots=True)
class RecoveryEnrollmentAttempt:
    """The outcome of asking the application to enrol recovery after creation.

    ``enrolled`` is true only when the wrapper was installed after the
    operator confirmed the code. ``declined`` records a deliberate cancel,
    which is not a refusal and shows nothing. Anything else is an expected
    refusal carried as localized data.
    """

    enrolled: bool = False
    declined: bool = False
    expected_refusal: RegistrationRefusal | None = None


def _language_options() -> list[tuple[str, str]]:
    """The chooser's rows, each language named in that language.

    An operator who cannot read the language the page opened in cannot read
    that language's name for their own either, so "Húngaro" on a Spanish page
    helps nobody who needs the chooser; "Magyar" does. The rows therefore do
    not depend on the language on screen, and never need re-wording when it
    changes. The profile manager's language picker follows the same rule.
    """
    return [
        (tr(f"wizard.setup.profile.output-language.choices.{language}.label", locale=language), language)
        for language in SUPPORTED_OUTPUT_LANGUAGES
    ]


class RegistrationScreen(CredentialScreen["ProfileRegistrationOutcome"]):
    """Full-screen credential entry that creates and unlocks one profile."""

    SCOPED_CSS = False
    DEFAULT_CSS = tokenised(
        BASE_CSS
        + CREDENTIAL_PANEL_CSS
        + """
    #registration-intro { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-stack $cadrumo-space-0; }
    #registration-why {
        color: $text-muted;
        border-left: $cadrumo-rule $accent;
        padding: $cadrumo-tight $cadrumo-space-0 $cadrumo-tight $cadrumo-space-1;
        margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-stack $cadrumo-space-0;
    }
    /* Belongs to the password field above it, so it stays tight. */
    #strength-line { margin: $cadrumo-tight $cadrumo-space-0; }
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
        register: Callable[[str, str, str], RegistrationAttempt],
        enroll_recovery: Callable[[str, str, Callable[[ProfileRecoveryEnrollment], str]], RecoveryEnrollmentAttempt]
        | None = None,
        suggested_name: str | None = None,
    ) -> None:
        """Bind the password assessment, registration and optional recovery doors."""
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
        self._enroll_recovery = enroll_recovery
        """The optional recovery door. ``None`` means the screen never offers
        recovery and leaves as soon as the profile exists, which is what a
        host without a way to enrol wants."""
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
        self._pending_passphrase: bytearray | None = None
        """The passphrase kept only between creation and the recovery offer.

        Enrolment proves the current passphrase, and asking the operator to
        retype it seconds after choosing it would be a pointless hurdle. The
        buffer is wiped the moment the offer is resolved either way."""
        self._created_outcome: ProfileRegistrationOutcome | None = None
        self._pending_recovery_handoffs: set[Event] = set()
        self._enrollment_worker: Worker[RecoveryEnrollmentAttempt] | None = None

    @override
    def compose(self) -> ComposeResult:
        """Yield the banner, the credential form, and the footer."""
        yield Static(id="registration-banner", classes="cadrumo-banner")
        yield PinnedStatusBar(id="credential-status")
        with self.credential_panel(panel_id="registration-body"):
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

            with Vertical(id="registration-actions", classes="credential-actions"):
                yield Button(
                    tr("flows.registration.create_button", locale=self._active_language),
                    id="btn-create",
                    classes="-primary",
                )
        yield Footer()

    def on_mount(self) -> None:
        """Install the theme, render copy, and focus profile-name entry."""
        install_cadrumo_themes(self.app)
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
        self.describe_appearance_key()
        self._render_strength(
            self.query_one("#field-password", Input).value,
            assess=self._assess_profile_password,
            locale=locale,
        )

    # ── live feedback ───────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        """Re-render the advisory strength line as the password is typed."""
        if event.input.id == "field-password":
            self._render_strength(
                event.value,
                assess=self._assess_profile_password,
                locale=self._active_language,
            )

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
            refusal = attempt.expected_refusal
            surface_key = _SURFACE_REFUSAL_LOCALE_KEYS.get(refusal.message_key)
            if surface_key is not None:
                refusal = RegistrationRefusal(message_key=surface_key, context=refusal.context)
            return refusal.render(locale=self._active_language)
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
        """Validate the form locally, then create the profile.

        Local checks cover only what the screen can see — a blank name, a
        mismatched confirmation, an invalid password. Everything else
        (a duplicate label, a storage refusal) is the application door's
        decision, surfaced here as its translated message rather than
        re-derived, so the screen never becomes a second authority on what
        a valid registration is.
        """
        if self.attempt_in_flight or self._created_outcome is not None:
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
        self._wipe_pending_passphrase()
        self._pending_passphrase = bytearray(password, UTF_8_ENCODING)

        def _register() -> CredentialAttempt[ProfileRegistrationOutcome]:
            attempt = registration_context.run(
                self._create_profile,
                username,
                password,
                selected_language,
            )
            return cast("CredentialAttempt[ProfileRegistrationOutcome]", attempt)

        self.start_attempt(_register)

    @override
    def default_refusal(self) -> str:
        return tr("flows.registration.refusal.username_required", locale=self._active_language)

    @override
    def progress_message(self) -> str:
        return tr("flows.registration.create_button", locale=self._active_language)

    @override
    def refuse(self, message: str) -> None:
        """Show refusal and return the keyboard to the form.

        A refusal the application door raises -- a duplicate label, a storage
        refusal -- arrives while the fields are disabled, so re-enabling them
        leaves nothing focused and the operator cannot type without reaching
        for the mouse. The local checks focus the field they name immediately
        after calling this, so the name field is only the landing place for a
        refusal that named none.
        """
        super().refuse(message)
        self.query_one("#field-username", Input).focus()

    # ── recovery offer ──────────────────────────────────────────────────

    @override
    def leave(self, outcome: ProfileRegistrationOutcome | None) -> None:
        """Offer recovery once the profile exists; leave immediately otherwise.

        The base lifecycle calls this with the successful outcome. Instead of
        closing straight away, the screen holds the outcome and puts the
        one optional question to the operator. Declining, cancelling, and
        finishing enrolment all end here again through
        :meth:`_finish_registration`, which is the only path that closes.
        """
        if outcome is None or self._enroll_recovery is None:
            self._wipe_pending_passphrase()
            super().leave(outcome)
            return
        if self._created_outcome is not None:
            super().leave(outcome)
            return
        self._created_outcome = outcome
        self.app.push_screen(
            RecoveryOfferScreen(
                locale=self._active_language,
                on_accept=self._start_recovery_enrollment,
                on_skip=self._finish_registration,
            )
        )

    def _start_recovery_enrollment(self) -> None:
        """Run the enrolment door off the event loop with the retained passphrase."""
        outcome = self._created_outcome
        door = self._enroll_recovery
        buffer = self._pending_passphrase
        if outcome is None or door is None or buffer is None:
            self._finish_registration()
            return
        self.set_busy(busy=True)
        self.query_one(self.STATUS_ID, PinnedStatusBar).show_progress(
            tr("flows.registration.recovery.progress", locale=self._active_language)
        )
        enrollment_context = copy_context()
        passphrase = buffer.decode(UTF_8_ENCODING)
        profile_id = outcome.profile_id
        handover = self._confirm_recovery_possession

        def _enroll() -> RecoveryEnrollmentAttempt:
            return enrollment_context.run(door, profile_id, passphrase, handover)

        self._enrollment_worker = self.run_worker(
            _enroll,
            name=_RECOVERY_ENROLLMENT_WORKER,
            group=_RECOVERY_ENROLLMENT_WORKER,
            exit_on_error=False,
            exclusive=True,
            thread=True,
        )

    @override
    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Settle the enrolment worker here; everything else is the base attempt."""
        worker = self._enrollment_worker
        if worker is None or event.worker is not worker:
            super().on_worker_state_changed(event)
            return
        if event.state not in {WorkerState.SUCCESS, WorkerState.ERROR}:
            return
        self._enrollment_worker = None
        attempt = worker.result if event.state is WorkerState.SUCCESS else None
        if attempt is not None and attempt.expected_refusal is not None:
            self.refuse(attempt.expected_refusal.render(locale=self._active_language))
        elif event.state is WorkerState.ERROR:
            self.refuse(
                self._resolved_worker_failure(worker.error or InternalInvariantError(_RECOVERY_ENROLLMENT_WORKER))
            )
        self._finish_registration()

    def _finish_registration(self) -> None:
        """Wipe the retained passphrase and hand the created profile to the host."""
        self._wipe_pending_passphrase()
        outcome = self._created_outcome
        self.outcome = outcome
        super().leave(outcome)

    def _wipe_pending_passphrase(self) -> None:
        buffer = self._pending_passphrase
        if buffer is not None:
            buffer[:] = b"\x00" * len(buffer)
        self._pending_passphrase = None

    def _confirm_recovery_possession(self, enrollment: ProfileRecoveryEnrollment) -> str:
        """Show the code, block for confirmation, and return exact proof.

        Runs on the enrolment worker thread. The code screen is pushed on the
        UI task and the worker waits on an event the screen resolves. A
        decline raises so the application installs nothing.
        """
        resolved = Event()
        self._pending_recovery_handoffs.add(resolved)
        supplied_proof: str | None = None

        def _accept(proof: str) -> None:
            nonlocal supplied_proof
            supplied_proof = proof
            resolved.set()

        def _refuse() -> None:
            resolved.set()

        code_screen: RecoveryCodeScreen | None = None

        def _show() -> None:
            nonlocal code_screen
            code_screen = RecoveryCodeScreen(
                enrollment=enrollment,
                locale=self._active_language,
                on_confirm=_accept,
                on_cancel=_refuse,
            )
            self.app.push_screen(code_screen)

        try:
            self.app.call_from_thread(_show)
            # The operator is copying down a code, so elapsed time is not a
            # failure condition. The one real failure is a message loop that
            # stopped without releasing this handoff through ``on_unmount``,
            # so wait on that condition instead: poll the event, and give up
            # only once the app is no longer running or the screen left the
            # stack without answering.
            unstacked_polls = 0
            while not resolved.wait(timeout=_RECOVERY_HANDOFF_POLL_SECONDS):
                if not self.app.is_running:
                    break
                if code_screen is not None and code_screen not in self.app.screen_stack:
                    unstacked_polls += 1
                    if unstacked_polls > 1:
                        break
                else:
                    unstacked_polls = 0
            if supplied_proof is None:
                raise RecoveryHandoverDeclinedError
            return supplied_proof
        finally:
            self._pending_recovery_handoffs.discard(resolved)

    def on_unmount(self) -> None:
        """Release every pending handoff and wipe the passphrase when the application stops."""
        for pending in tuple(self._pending_recovery_handoffs):
            pending.set()
        self._wipe_pending_passphrase()

    @override
    def set_busy(self, *, busy: bool) -> None:
        """Render registration progress and freeze inputs while storage mutates."""
        super().set_busy(busy=busy)
        for field_id in ("field-username", "field-password", "field-confirm"):
            self.query_one(f"#{field_id}", Input).disabled = busy
        self.query_one("#field-output-language", Select).disabled = busy
        self.query_one("#btn-create", Button).disabled = busy


class RecoveryOfferScreen(Screen[None]):
    """Ask once whether to set up recovery, with the trade-off stated plainly."""

    BINDINGS: ClassVar = [
        Binding("f3", "toggle_appearance", "", show=False),
        Binding("escape", "skip_recovery", "", show=False),
    ]

    DEFAULT_CSS = tokenised("""
    RecoveryOfferScreen {
        align: center middle;
    }
    #offer-panel {
        width: 100%;
        height: auto;
        border: $cadrumo-radius $primary;
        padding: $cadrumo-space-1 $cadrumo-gutter;
    }
    #offer-heading { text-style: bold; margin-bottom: $cadrumo-stack; }
    #offer-explanation { margin-bottom: $cadrumo-stack; }
    #offer-consequence { color: $text-muted; margin-bottom: $cadrumo-stack; }
    #offer-actions { height: auto; align-horizontal: right; }
    """)

    def __init__(self, *, locale: str, on_accept: Callable[[], None], on_skip: Callable[[], None]) -> None:
        """Bind the two terminal choices of the offer."""
        super().__init__()
        self._locale = locale
        self._on_accept = on_accept
        self._on_skip = on_skip
        self._resolved = False

    @override
    def compose(self) -> ComposeResult:
        with Container(id="offer-panel"):
            yield Static(tr("flows.registration.recovery.offer_heading", locale=self._locale), id="offer-heading")
            yield Static(
                tr("flows.registration.recovery.offer_explanation", locale=self._locale), id="offer-explanation"
            )
            yield Static(
                tr("flows.registration.recovery.offer_consequence", locale=self._locale), id="offer-consequence"
            )
            with Container(id="offer-actions"):
                yield Button(tr("flows.registration.recovery.skip_button", locale=self._locale), id="btn-skip-recovery")
                yield Button(
                    tr("flows.registration.recovery.setup_button", locale=self._locale),
                    id="btn-setup-recovery",
                    classes="-primary",
                )

    def on_mount(self) -> None:
        """Focus the skip choice: declining is the default and costs nothing."""
        self.query_one("#btn-skip-recovery", Button).focus()

    @on(Button.Pressed, "#btn-setup-recovery")
    def _accept(self) -> None:
        if self._resolved:
            return
        self._resolved = True
        self.dismiss(None)
        self._on_accept()

    @on(Button.Pressed, "#btn-skip-recovery")
    def _skip(self) -> None:
        self._skip_once()
        self.dismiss(None)

    def action_skip_recovery(self) -> None:
        """Escape declines the offer, which is what leaving it already means."""
        self._skip()

    def action_toggle_appearance(self) -> None:
        """Switch appearance here as on every other credential surface."""
        toggle_appearance(self.app)

    def on_unmount(self) -> None:
        """Treat escape, shutdown, and every non-accept exit as a skip."""
        self._skip_once()

    def _skip_once(self) -> None:
        if self._resolved:
            return
        self._resolved = True
        self._on_skip()


class RecoveryCodeScreen(Screen[None]):
    """Show the recovery code once and return masked exact re-entry proof."""

    BINDINGS: ClassVar = [
        Binding("f3", "toggle_appearance", "", show=False),
        Binding("escape", "cancel_code", "", show=False),
    ]

    DEFAULT_CSS = tokenised("""
    RecoveryCodeScreen {
        align: center middle;
    }
    #code-panel {
        width: 100%;
        height: auto;
        border: $cadrumo-radius $primary;
        padding: $cadrumo-space-1 $cadrumo-gutter;
    }
    #code-heading { text-style: bold; margin-bottom: $cadrumo-stack; }
    #code-value { color: $warning; text-style: bold; margin-bottom: $cadrumo-stack; }
    #code-warning { color: $text-muted; margin-bottom: $cadrumo-stack; }
    #code-mismatch { color: $error; height: auto; margin-bottom: $cadrumo-stack; }
    #code-actions { height: auto; align-horizontal: right; }
    """)

    def __init__(
        self,
        *,
        enrollment: ProfileRecoveryEnrollment,
        locale: str,
        on_confirm: Callable[[str], None],
        on_cancel: Callable[[], None],
    ) -> None:
        """Bind one ephemeral recovery enrolment and its terminal callbacks."""
        super().__init__()
        self._enrollment = enrollment
        self._locale = locale
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._resolved = False

    @override
    def compose(self) -> ComposeResult:
        with Container(id="code-panel"):
            yield Static(tr("cli.config.profile.recovery.code_heading", locale=self._locale), id="code-heading")
            yield Static(self._enrollment.recovery_key.code, id="code-value")
            yield Static(tr("cli.config.profile.recovery.code_warning", locale=self._locale), id="code-warning")
            # The mismatch notice has its own line: writing it over the warning
            # above would retire the one-time-display caveat for the rest of
            # the screen, and a typo is exactly when that caveat still matters.
            yield Static(id="code-mismatch")
            yield Input(
                placeholder=tr("cli.config.profile.recovery.verification_prompt", locale=self._locale),
                id="field-recovery-verification",
            )
            with Container(id="code-actions"):
                yield Button(tr("flows.registration.recovery.cancel_button", locale=self._locale), id="btn-cancel-code")
                yield Button(
                    tr("flows.registration.recovery.confirm_button", locale=self._locale),
                    id="btn-confirm-code",
                    classes="-primary",
                )

    @on(Button.Pressed, "#btn-confirm-code")
    def _confirm(self) -> None:
        if self._resolved:
            return
        field = self.query_one("#field-recovery-verification", Input)
        supplied = field.value
        expected = self._enrollment.recovery_key.code
        try:
            if _bare_code(supplied) != _bare_code(expected):
                field.value = ""
                self.query_one("#code-mismatch", Static).update(
                    tr("cli.config.profile.recovery.verification_mismatch", locale=self._locale)
                )
                field.focus()
                return
        finally:
            del expected
        field.value = ""
        self.query_one("#code-mismatch", Static).update("")
        self._resolved = True
        self.dismiss(None)
        self._on_confirm(self._enrollment.recovery_key.code)

    @on(Input.Submitted, "#field-recovery-verification")
    def _submit(self) -> None:
        self._confirm()

    @on(Button.Pressed, "#btn-cancel-code")
    def _cancel(self) -> None:
        self._refuse_once()
        self.dismiss(None)

    def action_cancel_code(self) -> None:
        """Escape declines enrolment, so nothing is installed for this code."""
        self._cancel()

    def action_toggle_appearance(self) -> None:
        """Switch appearance here as on every other credential surface."""
        toggle_appearance(self.app)

    def on_unmount(self) -> None:
        """Treat escape, shutdown, and every non-confirm exit as refusal."""
        self._refuse_once()

    def _refuse_once(self) -> None:
        if self._resolved:
            return
        self._resolved = True
        self._on_cancel()


def _bare_code(text: str) -> str:
    """Reduce a typed code to its symbols so case and separators are cosmetic."""
    return "".join(character for character in text.upper() if character.isalnum())


def build_profile_registration_attempt(
    label: str,
    candidate_passphrase: str,
    output_language: str,
) -> RegistrationAttempt:
    """Adapt the public registration door into this screen's result contract.

    This is the production ``register`` door. It classifies nothing itself:
    the application owns which refusals are expected, and this only carries
    the localized message key and its context forward as data. No passphrase
    is retained beyond the call.
    """
    from ....application.user_profile.registration import ProfileRegistrationError, register_profile_with_credentials
    from ....domain.calculations.registry.authority import bundled_indexed_authority
    from ....domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
    from ....domain.user_profile.values import UserProfileFact

    try:
        with bundled_indexed_authority().operation() as operation:
            outcome = register_profile_with_credentials(
                label=label,
                passphrase=candidate_passphrase,
                facts=(UserProfileFact(path=PROFILE_OUTPUT_LANGUAGE_PATH, value=output_language),),
                profile_create_context=operation.profile_create_context(),
                profile_decode_context=operation.profile_decode_context(),
            )
    except ProfileRegistrationError as refusal:
        if refusal.translated_message is None:
            raise
        return RegistrationAttempt(
            expected_refusal=RegistrationRefusal(
                message_key=refusal.translated_message,
                context=tuple((refusal.context or {}).items()),
            )
        )
    return RegistrationAttempt(outcome=outcome)


def build_profile_recovery_enrollment_attempt(
    profile_id: str,
    current_passphrase: str,
    recovery_handover: Callable[[ProfileRecoveryEnrollment], str],
) -> RecoveryEnrollmentAttempt:
    """Adapt the public enrolment door into this screen's result contract.

    A declined handover is not a refusal: the operator chose to keep the
    profile passphrase-only, and the application installed nothing.
    """
    from uuid import UUID

    from ....application.user_profile.recovery_custody import ProfileRecoveryError, enroll_profile_recovery

    try:
        enroll_profile_recovery(
            profile_id=UUID(profile_id),
            current_passphrase=current_passphrase,
            recovery_handover=recovery_handover,
        )
    except RecoveryHandoverDeclinedError:
        return RecoveryEnrollmentAttempt(declined=True)
    except ProfileRecoveryError as refusal:
        if refusal.translated_message is None:
            raise
        return RecoveryEnrollmentAttempt(
            expected_refusal=RegistrationRefusal(
                message_key=refusal.translated_message,
                context=tuple((refusal.context or {}).items()),
            )
        )
    return RecoveryEnrollmentAttempt(enrolled=True)
