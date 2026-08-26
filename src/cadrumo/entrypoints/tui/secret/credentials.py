"""The shared credential-attempt host and password-assessment presentation.

``CredentialApp`` is the base every secret-entry screen mounts: it owns the
bounded, thread-backed attempt lifecycle (start once, settle back on the UI
task, refuse or leave) so :class:`~cadrumo.entrypoints.tui.secret.login
.LoginApp` and :class:`~cadrumo.entrypoints.tui.secret.registration
.RegistrationApp` differ only in their form and their injected door, never
in how an attempt is run or reported.

The assessment helpers below project a canonical
:class:`~cadrumo.core.credentials.ProfilePasswordAssessment` into presentation
copy and CSS class -- the strength banding policy itself stays with
:func:`~cadrumo.core.credentials.assess_profile_password`, which callers
inject rather than import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Final, Protocol, cast

from textual.app import App
from textual.binding import Binding
from textual.worker import Worker, WorkerState

from ....core.credentials import PassphraseStrength, ProfilePasswordAssessment
from ....core.i18n import tr
from ....entrypoints.tui.components.status import PinnedStatusBar
from ....entrypoints.tui.components.theme import cadrumo_css_variables, toggle_appearance

if TYPE_CHECKING:
    from collections.abc import Callable

    from ....application.user_profile.prospective_password import ProspectiveProfilePasswordRefusal

__all__ = [
    "CREDENTIAL_PANEL_CSS",
    "CredentialApp",
    "CredentialAttempt",
    "assessment_copy",
    "assessment_css_class",
    "assessment_refusal",
    "run_credential_app",
]

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

    def get_css_variables(self) -> dict[str, str]:
        """Expose the canonical Cadrumo tokens to every stylesheet.

        Textual resolves this once per app and hands the result to app-level
        ``CSS`` and every widget's ``DEFAULT_CSS`` alike, which is why the
        design tokens travel here rather than in the theme's own variables.
        """
        return cadrumo_css_variables(super().get_css_variables())

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
