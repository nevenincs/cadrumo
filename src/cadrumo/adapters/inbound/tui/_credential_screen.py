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
from typing import TYPE_CHECKING, ClassVar, Final, cast

from textual.app import App
from textual.binding import Binding
from textual.worker import Worker, WorkerState

from ....core.i18n import tr
from ....entrypoints.tui.components.theme import toggle_appearance
from ._status_bar import PinnedStatusBar

if TYPE_CHECKING:
    from collections.abc import Callable


CREDENTIAL_PANEL_CSS: Final[str] = """
.field-label { text-style: bold; margin: 0; }
.field-hint { color: $text-muted; margin: 0; }
.credential-actions { height: auto; align-horizontal: right; margin: 0; }
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

    STATUS_ID: ClassVar[str] = "#credential-status"
    """Selector of the pinned progress and diagnostic channel."""

    ATTEMPT_NAME: ClassVar[str]
    """Worker name, and the subject named in an unexpected-failure message."""

    def __init__(self) -> None:
        super().__init__()
        self.outcome: OutcomeT | None = None
        """What the screen achieved, or ``None`` when the operator left
        without achieving it. The caller distinguishes the two by this and
        never by an exception, because leaving is an ordinary choice."""
        self.error: BaseException | None = None
        """Last unexpected failure, retained for diagnostics but never re-raised."""
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
        """Settle the one attempt back on Textual's UI task."""
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
            self.refuse(attempt.refusal or self.default_refusal())
            return
        self.outcome = attempt.outcome
        self.leave(attempt.outcome)

    @staticmethod
    def _resolved_worker_failure(error: BaseException) -> str:
        """Render one unexpected failure with a durable next step.

        Domain errors have registered, translated messages. A low-level
        failure does not, and its exception text is diagnostic vocabulary
        rather than operator guidance. The fallback therefore renders only
        the shared recovery instruction; the original exception remains on
        ``self.error`` for diagnostics.
        """
        try:
            from ....core.errors import resolve_error_message

            detail = resolve_error_message(error).strip()
        except (LookupError, TypeError, ValueError):
            detail = ""
        guidance = tr("errors.internal.internal_cli_unexpected_boundary")
        return f"{detail} {guidance}".strip()

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
        self.query_one(self.STATUS_ID, PinnedStatusBar).show_error(message)

    def set_busy(self, *, busy: bool) -> None:
        """Show progress and clear the previous refusal.

        Subclasses extend this to freeze their own inputs; they call up
        so the progress line and the refusal reset stay decided once.
        """
        status = self.query_one(self.STATUS_ID, PinnedStatusBar)
        if busy:
            status.show_progress(self.progress_message())
        else:
            status.clear_message()

    def progress_message(self) -> str:
        """Operator-facing description of the subclass's in-flight attempt."""
        raise NotImplementedError

    def leave(self, outcome: OutcomeT | None) -> None:
        """Close the screen, handing ``outcome`` back to the runner.

        This is the only place the screens themselves close, but it is NOT
        a teardown hook and nothing may be made to depend on it running.
        ``App.exit`` is public, so a caller holding the app can close it
        without coming through here — the tests that drive these screens
        do exactly that. A subclass may override this to release something
        it holds, and registration does, but only where the release is
        hygiene: anything whose CORRECTNESS needs it would be silently
        wrong on the bypass, and no test would show it.

        Where a real guarantee is needed, bind it to something that cannot
        be stepped over. The typed secret is the worked example — it is
        overwritten in the worker callable's own ``finally``, so it is
        bounded by the attempt rather than by how the screen was closed.
        """
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
    exception to find out. An unexpected worker failure is rendered in the
    pinned channel and leaves this app running for retry; it never reaches
    this boundary as an exception.
    """
    app.run()
    return app.outcome


__all__ = [
    "CREDENTIAL_PANEL_CSS",
    "CredentialApp",
    "CredentialAttempt",
    "run_credential_app",
]
