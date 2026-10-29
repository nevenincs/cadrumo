"""Observe account activity, retirement and session expiry on the TUI root."""

from __future__ import annotations

import time
from abc import abstractmethod
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, override

from textual import events

from ...application.overview.home import HomeSessionPosture
from ...core.time.clock import now
from .account import (
    AccountRecomposeReasonV1,
    AccountRecomposeRequiredV1,
    AccountSessionExpiredError,
    AccountSessionReaderV1,
    AccountSessionRetired,
    AccountSessionUnavailableError,
)
from .language_session import LanguageSessionApp

if TYPE_CHECKING:
    from textual.timer import Timer

    from ...application.overview.home import HomeAccountSession


class AccountSessionApp(LanguageSessionApp):
    """Own the admitted session's expiry and input activity observation."""

    _note_activity: Callable[[], Awaitable[None]] | None
    _last_activity_sent: float | None
    _activity_pending: bool
    _read_account_session: AccountSessionReaderV1 | None
    _account_session: HomeAccountSession | None
    _account_session_polling: bool
    _unsubscribe_retirement: Callable[[], None] | None
    _session_lapse_timer: Timer | None

    @abstractmethod
    def _request_recompose(self, outcome: AccountRecomposeRequiredV1) -> None:
        """Retire this profile root with the supplied public outcome."""

    @abstractmethod
    def _refresh_account_bars(self) -> None:
        """Refresh account bars after the admitted session changes."""

    def _post_session_retired(self) -> None:
        self.post_message(AccountSessionRetired())

    @override
    async def on_event(self, event: events.Event) -> None:
        """Report actual terminal input, including input consumed by a child."""
        if (
            isinstance(
                event, (events.Key, events.Paste, events.MouseDown, events.MouseScrollUp, events.MouseScrollDown)
            )
            and not event.is_forwarded
        ):
            self._note_person_activity()
        await super().on_event(event)

    def _note_person_activity(self) -> None:
        note = self._note_activity
        observed = time.monotonic()
        if (
            note is None
            or self._activity_pending
            or (self._last_activity_sent is not None and observed - self._last_activity_sent < 15)
        ):
            return
        self._activity_pending = True
        self._last_activity_sent = observed
        self.run_worker(self._send_person_activity(note), name="person-activity")

    async def _send_person_activity(self, note: Callable[[], Awaitable[None]]) -> None:
        try:
            await note()
        except Exception:
            if self._note_activity is note:
                self._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.UNAVAILABLE))
            return
        finally:
            self._activity_pending = False
        if self._session_lapse_timer is not None:
            # Activity may have extended the session; read the new expiry now.
            self._watch_account_session()

    def on_account_session_retired(self, _: AccountSessionRetired) -> None:
        """Clear on the UI thread; the transport callback never waits for rendering."""
        # The callback also covers a disconnected transport; no expiry was proven.
        self._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.UNAVAILABLE))

    def _watch_account_session(self) -> None:
        """End the session once it has lapsed, without waiting for the operator to act.

        Failed observation clears private views without claiming an expiry.
        """
        if self._read_account_session is None or self._account_session is None or self._account_session_polling:
            return
        self._account_session_polling = True
        self.run_worker(self._poll_account_session(), name="account-session-watch", exclusive=True)

    async def _poll_account_session(self) -> None:
        """Observe one session off the UI task and discard a stale root's result."""
        reader = self._read_account_session
        if reader is None:
            self._account_session_polling = False
            return
        try:
            session = await reader()
        except AccountSessionExpiredError as error:
            if self._read_account_session is reader:
                self._request_recompose(AccountRecomposeRequiredV1(reason=self._session_failure_reason(error)))
            return
        except Exception:
            if self._read_account_session is reader:
                self._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.UNAVAILABLE))
            return
        finally:
            self._account_session_polling = False
        if self._session_expired(session):
            self._expire_if_reader_current(reader)
            return
        self._renew_account_session(reader, session)
        if self._read_account_session is reader:
            self._arm_session_lapse()

    def _arm_session_lapse(self) -> None:
        """Wake once at the current expiry instead of polling for it."""
        if self._unsubscribe_retirement is None:
            return
        if self._session_lapse_timer is not None:
            self._session_lapse_timer.stop()
        session = self._account_session
        if self._read_account_session is None or session is None or session.expires_at is None:
            self._session_lapse_timer = None
            return
        delay = max(0.0, (session.expires_at - now()).total_seconds())
        self._session_lapse_timer = self.set_timer(delay, self._watch_account_session)

    @staticmethod
    def _session_failure_reason(error: AccountSessionExpiredError) -> AccountRecomposeReasonV1:
        return (
            AccountRecomposeReasonV1.UNAVAILABLE
            if isinstance(error, AccountSessionUnavailableError)
            else AccountRecomposeReasonV1.EXPIRED
        )

    @staticmethod
    def _session_expired(session: HomeAccountSession) -> bool:
        return (
            session.posture is not HomeSessionPosture.ACTIVE
            or session.expires_at is None
            or session.expires_at <= now()
        )

    def _expire_if_reader_current(self, reader: AccountSessionReaderV1) -> None:
        if self._read_account_session is reader:
            self._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED))

    def _renew_account_session(self, reader: AccountSessionReaderV1, session: HomeAccountSession) -> None:
        if (
            self._read_account_session is reader
            and self._account_session is not None
            and session.expires_at != self._account_session.expires_at
        ):
            self._account_session = session
            self._refresh_account_bars()
