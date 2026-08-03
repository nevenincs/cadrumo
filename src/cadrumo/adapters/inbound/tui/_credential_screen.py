"""What the two credential surfaces have in common.

Creating a profile and unlocking one ask for different things, but they
ask in the same shape: a secret typed into a masked field, one button
that hands it to storage, one place refusals appear, and one rule that a
second attempt cannot start on top of the first. Both also have to hand
the secret over *off* the event loop, because key derivation is
deliberately slow and a screen that derived on the loop would freeze
under the operator's hands.

That shared shape lives here so the two screens cannot drift apart on
it. What differs — which fields are collected, what the copy says, which
application door is driven — stays with each screen.

The module holds no application import. A screen is handed the door it
drives, so this tier keeps rendering and never reaches up.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final

from textual.app import App
from textual.binding import Binding
from textual.widgets import LoadingIndicator, Static
from textual.worker import Worker, WorkerState

from ._theme import toggle_appearance

if TYPE_CHECKING:
    from collections.abc import Callable


CREDENTIAL_PANEL_CSS: Final[str] = """
.field-label { text-style: bold; margin: 1 0 0 0; }
.field-hint { color: $text-muted; margin: 0 0 1 0; }
.credential-refusal { color: $error; margin: 0 0 1 0; }
.credential-busy { display: none; height: 1; margin: 0 0 1 0; }
.credential-busy.busy { display: block; }
.credential-actions { height: auto; align-horizontal: right; margin: 1 0 0 0; }
"""
"""Layout the two credential panels share.

Class selectors rather than id selectors: the ids stay screen-local (they
are what each screen's own tests and handlers address), while the
appearance of a labelled field, a refusal line, a busy line, and a button
row is one decision for both surfaces."""


@dataclass(frozen=True, slots=True)
class CredentialAttempt[OutcomeT]:
    """The outcome of asking the application to act on a credential.

    A refusal arrives as text the screen displays, not as an exception it
    has to recognise. That keeps refusal *classification* with the layer
    that owns the rules, and leaves the screen doing what a screen does:
    show the operator what happened.
    """

    outcome: OutcomeT | None = None
    refusal: str | None = None


class CredentialApp[OutcomeT](App[OutcomeT | None]):
    """Base for a full-screen surface that hands one secret to storage.

    Subclasses compose their own widgets and decide what to collect; this
    class owns the part that is identical either way — running the one
    in-flight attempt on a worker thread, refusing a second while it
    runs, settling its result back on the UI task, and leaving.
    """

    BINDINGS: ClassVar = [
        Binding("f3", "toggle_appearance", "", show=False),
        Binding("escape", "abandon", "", show=False),
    ]

    REFUSAL_ID: ClassVar[str]
    """Selector of the zone refusals are written into."""

    BUSY_ID: ClassVar[str]
    """Selector of the progress line shown while storage is working."""

    ATTEMPT_NAME: ClassVar[str]
    """Worker name, and the subject named in an unexpected-failure message."""

    def __init__(self) -> None:
        super().__init__()
        self.outcome: OutcomeT | None = None
        """What the screen achieved, or ``None`` when the operator left
        without achieving it. The caller distinguishes the two by this and
        never by an exception, because leaving is an ordinary choice."""
        self.error: BaseException | None = None
        """Unexpected failure, re-raised by the synchronous runner."""
        self._attempt: Worker[CredentialAttempt[OutcomeT]] | None = None
        """The one in-flight storage call; duplicate submissions are refused."""

    @property
    def attempt_in_flight(self) -> bool:
        """Whether a storage call is running and must not be joined by a second."""
        return self._attempt is not None

    # ── the one attempt ─────────────────────────────────────────────────

    def start_attempt(self, work: Callable[[], CredentialAttempt[OutcomeT]]) -> None:
        """Run ``work`` off the event loop as this screen's one attempt.

        Silently a no-op while an attempt is already running: the operator
        pressing the button twice means "get on with it", not "do it
        twice", and the second call would be a second storage mutation.
        """
        if self._attempt is not None:
            return
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
        """Settle the one attempt back on Textual's UI task."""
        worker = self._attempt
        if worker is None or event.worker is not worker or event.state not in {WorkerState.SUCCESS, WorkerState.ERROR}:
            return
        self._attempt = None
        if event.state is WorkerState.ERROR:
            self.error = worker.error or RuntimeError(f"{self.ATTEMPT_NAME} worker failed")
            self.leave(None)
            return
        attempt = worker.result
        if attempt is None:
            self.error = RuntimeError(f"{self.ATTEMPT_NAME} worker returned no result")
            self.leave(None)
            return
        if attempt.outcome is None:
            self.set_busy(busy=False)
            self.refuse(attempt.refusal or self.default_refusal())
            return
        self.outcome = attempt.outcome
        self.leave(attempt.outcome)

    def default_refusal(self) -> str:
        """Text shown when a refusal arrived carrying no message of its own.

        Reached only on a door that refused without saying why, which is a
        defect rather than a state the operator caused; the screen still
        has to put *something* readable in the refusal zone.
        """
        raise NotImplementedError

    # ── shared chrome ───────────────────────────────────────────────────

    def refuse(self, message: str) -> None:
        """Show one refusal without leaving, so the operator can retry in place."""
        self.query_one(self.REFUSAL_ID, Static).update(message)

    def set_busy(self, *, busy: bool) -> None:
        """Show progress and clear the previous refusal.

        Subclasses extend this to freeze their own inputs; they call up
        so the progress line and the refusal reset stay decided once.
        """
        self.query_one(self.REFUSAL_ID, Static).update("")
        self.query_one(self.BUSY_ID, LoadingIndicator).set_class(busy, "busy")

    def leave(self, outcome: OutcomeT | None) -> None:
        """Close the screen, handing ``outcome`` back to the runner."""
        self.exit(outcome)

    def action_abandon(self) -> None:
        """Leave without a result; the caller sees ``None``.

        Refused while an attempt is in flight: a thread-backed storage
        mutation cannot be cancelled safely, so leaving would only detach
        its result while the write may still land.
        """
        if self._attempt is not None:
            return
        self.outcome = None
        self.leave(None)

    def action_toggle_appearance(self) -> None:
        toggle_appearance(self)


def run_credential_app[OutcomeT](app: CredentialApp[OutcomeT]) -> OutcomeT | None:
    """Run one credential screen and return what it achieved, or ``None``.

    ``None`` means the operator left without completing — an ordinary
    outcome, so the caller decides what to do rather than catching an
    exception to find out. An *unexpected* failure is re-raised here
    instead, because the screen has already closed and there is no
    surface left to show it on.
    """
    app.run()
    if app.error is not None:
        raise app.error
    return app.outcome


__all__ = [
    "CREDENTIAL_PANEL_CSS",
    "CredentialApp",
    "CredentialAttempt",
    "run_credential_app",
]
