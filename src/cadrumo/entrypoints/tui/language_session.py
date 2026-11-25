"""Language refresh lifecycle for an account-bound TUI root."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from textual.screen import Screen

from ...core.logging import get_logger
from .account import AccountFactoriesV1, AccountRecomposeRequiredV1, LanguageRefreshable, ProfileLanguageInvalidated
from .components.quiet_app import QuietApp

if TYPE_CHECKING:
    from textual.timer import Timer
    from textual.worker import Worker


class LanguageSessionApp(QuietApp[AccountRecomposeRequiredV1 | None]):
    """Own language invalidation, presentation retries and their epoch fence."""

    _account_factories: AccountFactoriesV1 | None
    _language_pending: bool
    _language_refreshing: bool
    _language_revision: int
    _language_epoch: int
    _language_retry_attempt: int
    _language_retry_timer: Timer | None
    _language_worker: Worker[None] | None
    _language_pending_screens: set[Screen[object]]

    @abstractmethod
    def refresh_account_chrome(self) -> None:
        """Refresh the account controls after a canonical language read."""

    def _post_language_invalidated(self) -> None:
        self.post_message(ProfileLanguageInvalidated())

    def on_profile_language_invalidated(self, _: ProfileLanguageInvalidated) -> None:
        """Coalesce invalidations; transient reads retain their pending work."""
        self._language_revision += 1
        self._language_pending = True
        self._language_retry_attempt = 0
        if self._language_retry_timer is not None:
            self._language_retry_timer.stop()
            self._language_retry_timer = None
        self._start_language_refresh()

    def _start_language_refresh(self) -> None:
        self._language_retry_timer = None
        factories = self._account_factories
        if self._language_refreshing or factories is None or factories.refresh_language is None:
            return
        self._language_refreshing = True
        self._language_worker = self.run_worker(
            self._refresh_language_projection(factories, self._language_epoch), name="language-refresh"
        )

    async def _refresh_language_projection(self, factories: AccountFactoriesV1, epoch: int) -> None:
        """Retry only failed presentation owners after a successful canonical read."""
        revision = self._language_revision
        try:
            if self._language_pending:
                refresh = factories.refresh_language
                if refresh is None:
                    return
                try:
                    await refresh()
                except Exception as error:
                    get_logger(__name__).debug(
                        "canonical language refresh unavailable error_type=%s", type(error).__name__
                    )
                    return
                if self._account_factories is not factories or self._language_epoch != epoch:
                    return
                self._language_pending = self._language_revision != revision
                self._language_pending_screens.update(self.screen_stack)
                self.refresh_account_chrome()
            await self._refresh_pending_screens(factories, epoch)
        finally:
            # The worker still owns this epoch when Home replaces the account
            # factories. Release its slot and retry through the new doors;
            # retirement increments the epoch and fences an old worker out.
            if self._language_epoch == epoch:
                if self._account_factories is not factories:
                    self._language_pending = True
                self._language_refreshing = False
                self._language_worker = None
                if self._language_pending or self._language_pending_screens:
                    delay = min(0.5 * (2 ** min(self._language_retry_attempt, 4)), 5.0)
                    self._language_retry_attempt += 1
                    self._language_retry_timer = self.set_timer(delay, self._start_language_refresh)
                else:
                    self._language_retry_attempt = 0

    async def _refresh_pending_screens(self, factories: AccountFactoriesV1, epoch: int) -> None:
        for screen in tuple(self._language_pending_screens):
            if self._account_factories is not factories or self._language_epoch != epoch:
                return
            if screen not in self.screen_stack:
                self._language_pending_screens.discard(screen)
                continue
            if isinstance(screen, LanguageRefreshable):
                try:
                    await screen.refresh_language()
                except Exception as error:
                    get_logger(__name__).debug(
                        "language presentation refresh unavailable error_type=%s", type(error).__name__
                    )
                    continue
            self._language_pending_screens.discard(screen)
