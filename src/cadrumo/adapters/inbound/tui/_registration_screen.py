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

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, override

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Button, Footer, Input, Label, Static

from ....core import PassphraseStrength
from ....core.i18n import tr
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
        register: Callable[[str, str], RegistrationAttempt],
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

            yield Label(tr("flows.registration.username_label"), classes="field-label")
            yield Static(tr("flows.registration.username_hint"), classes="field-hint")
            yield Input(id="field-username", value=self._suggested_name)

            yield Label(tr("flows.registration.password_label"), classes="field-label")
            # The hint names the floor, so it has to be told what the floor
            # is; the assessor already reports it, and asking it for the
            # empty string is how this surface learns it without importing
            # the policy that owns it.
            yield Static(
                tr("flows.registration.password_hint", minimum_length=self._assess_passphrase("").minimum_length),
                classes="field-hint",
            )
            yield Input(id="field-password", password=True)
            yield Static(id="strength-line")

            yield Label(tr("flows.registration.confirm_label"), classes="field-label")
            yield Input(id="field-confirm", password=True)

            yield Static(id="registration-refusal")
            with Vertical(id="registration-actions"):
                yield Button(tr("flows.registration.create_button"), id="btn-create", classes="-primary")
        yield Footer()

    def on_mount(self) -> None:
        install_cadrumo_themes(self)
        self.query_one("#registration-banner", Static).update(tr("flows.registration.title"))
        self.query_one("#registration-intro", Static).update(tr("flows.registration.intro"))
        self.query_one("#registration-why", Static).update(tr("flows.registration.why_password"))
        body = self.query_one("#registration-body", Vertical)
        body.border_title = tr("flows.registration.section")
        self.query_one("#field-username", Input).focus()

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

        attempt = self._create_profile(username, password)
        if attempt.outcome is None:
            self._refuse(attempt.refusal or tr("flows.registration.refusal.username_required"))
            return
        self.outcome = attempt.outcome
        self.exit(self.outcome)

    def action_abandon(self) -> None:
        """Leave without creating anything; the caller sees ``None``."""
        self.outcome = None
        self.exit(None)

    def action_toggle_appearance(self) -> None:
        toggle_appearance(self)

    def _refuse(self, message: str) -> None:
        self.query_one("#registration-refusal", Static).update(message)


def run_registration_tui(
    *,
    assess: Callable[[str], PassphraseVerdict],
    register: Callable[[str, str], RegistrationAttempt],
    suggested_name: str | None = None,
) -> ProfileRegistrationOutcome | None:
    """Run the registration screen and return the created profile, or ``None``.

    ``None`` means the operator abandoned the screen — an ordinary outcome,
    not an error, so the caller decides what to do rather than catching an
    exception to find out.
    """
    app = RegistrationApp(assess=assess, register=register, suggested_name=suggested_name)
    app.run()
    return app.outcome


__all__ = ["PassphraseVerdict", "RegistrationApp", "RegistrationAttempt", "run_registration_tui"]
