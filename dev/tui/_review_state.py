"""Own the synchronized catalogue, store, and review change generation."""

from __future__ import annotations

import threading

from ._review_catalogue import ReviewCatalogue
from ._review_store import (
    ReviewStore,
)
from ._review_thumbnails import ThumbnailCache


class ReviewState:
    """What every request thread shares: the catalogue, the store, a change counter."""

    def __init__(self, catalogue: ReviewCatalogue, store: ReviewStore) -> None:
        """Share ``catalogue`` and ``store`` across the server's threads."""
        self.catalogue = catalogue
        self.store = store
        self.thumbnails = ThumbnailCache()
        self.stopping = threading.Event()
        self._changed = threading.Condition()
        self._generation = 0

    @property
    def generation(self) -> int:
        """How many changes the server has announced; clients refetch when it moves."""
        with self._changed:
            return self._generation

    def bump(self) -> int:
        """Announce a change to every waiting event stream."""
        with self._changed:
            self._generation += 1
            self._changed.notify_all()
            return self._generation

    def wait_for_change(self, seen: int, timeout: float) -> int:
        """Block until the generation moves past ``seen``, the server stops, or ``timeout`` passes."""
        with self._changed:
            self._changed.wait_for(lambda: self._generation != seen or self.stopping.is_set(), timeout)
            return self._generation

    def refresh(self) -> bool:
        """Rescan the runs, announcing a change when one is found."""
        changed = self.catalogue.refresh()
        if changed:
            self.bump()
        return changed

    def watch(self, interval: float) -> None:
        """Rescan every ``interval`` seconds until the server stops."""
        while not self.stopping.wait(interval):
            self.refresh()

    def stop(self) -> None:
        """Release every waiting event stream and end the watch loop."""
        self.stopping.set()
        with self._changed:
            self._changed.notify_all()
