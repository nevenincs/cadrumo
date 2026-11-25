"""The capture language a runtime TUI root reads in, and the newest profile overview read in it."""

from __future__ import annotations

from threading import Lock
from typing import TYPE_CHECKING

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

if TYPE_CHECKING:
    from uuid import UUID

    from cadrumo.application.user_profile.overview import ProfileOverview
    from cadrumo.core.external_constants import OutputLanguage


class RuntimeProfileLanguage:
    """Hold one root's capture language, its change epoch and its cached profile overview.

    A language change bumps the epoch and drops the cached overview, so a read
    begun in the earlier language can never be adopted afterwards. Subclasses
    take ``_language_guard`` around every read or change of these fields,
    together with any state of their own that must change with them.
    """

    def __init__(self, profile_id: UUID, language: OutputLanguage) -> None:
        """Start at epoch zero in the admitted language, with no overview yet."""
        self._profile_id = profile_id
        self._language = language
        self._language_guard = Lock()
        self._language_epoch: int = 0
        self._latest_profile: ProfileOverview | None = None

    def _adopt_language_profile(self, profile: ProfileOverview, epoch: int) -> None:
        """Fence the result and keep any newer same-epoch read cached during I/O."""
        with self._language_guard:
            if epoch != self._language_epoch or profile.profile_id != str(self._profile_id):
                raise RefusalError(RefusalCode.UNAVAILABLE)
            if self._latest_profile is None or profile.record_revision >= self._latest_profile.record_revision:
                self._latest_profile = profile


__all__ = ["RuntimeProfileLanguage"]
