"""Retain an in-process test host while retrying its terminal resource drain."""

import time
from threading import Event
from typing import override
from uuid import UUID

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError, ShutdownIncompleteError
from cadrumo_runtime.contracts.profile_host import ProfileHandler

from ..server import RuntimeListener, RuntimeTransportServer


class RetainedRuntimeTransportServer(RuntimeTransportServer):
    """Add a retry driver for finite in-process fixtures after serve has returned."""

    def __init__(
        self,
        listener: RuntimeListener,
        *,
        product_version: str,
        stop: Event,
        profiles: ProfileHandler | None = None,
        boot_id: UUID | None = None,
        authority_generation: str | None = None,
    ) -> None:
        super().__init__(
            listener,
            product_version=product_version,
            stop=stop,
            profiles=profiles,
            boot_id=boot_id,
            authority_generation=authority_generation,
        )
        self._serve_finished = Event()

    @override
    def serve(self) -> None:
        try:
            super().serve()
        finally:
            self._serve_finished.set()

    def retry_drain(self, *, deadline: float) -> None:
        """Retry a terminal host's retained shutdown within the caller's absolute bound."""
        if not self._serve_finished.is_set():
            raise ShutdownIncompleteError()
        if not self._drain_guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise ShutdownIncompleteError()
        try:
            if not self._listener_owner.released:
                result = self._drain_owned_resources(deadline=deadline)
                if result is not None and result.missing_receipts:
                    self._failed.set()
                self._release_listener(None, deadline=deadline)
            if self._failed.is_set():
                raise RefusalError(RefusalCode.UNAVAILABLE)
        finally:
            self._drain_guard.release()
