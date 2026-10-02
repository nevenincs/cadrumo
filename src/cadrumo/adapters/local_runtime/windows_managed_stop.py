"""Prepare exact-task ownership, then finalize native stop after runtime drain."""

from __future__ import annotations

from threading import Event, Lock
from types import TracebackType
from typing import Self

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.management import RuntimeServiceBinding
from .windows_manager import WindowsTaskManager, WindowsTaskStopIdentity


class WindowsManagedRuntimeStop:
    """Keep native stop separate from consent acknowledgement and private drain.

    Preparation reads exact native ownership without stopping any process.
    The server invokes finalization only after its accepted stop has drained
    application resources, while listener ownership and watchdog remain held.
    Neither phase changes persistent task provisioning or login autostart.
    """

    def __init__(self, binding: RuntimeServiceBinding, stop: Event) -> None:
        """Bind the owner task and the server's shutdown signal.

        Args:
            binding: Canonical service definition and native owner identity.
            stop: Signal set by the server after accepting stop preparation.
        """
        self._manager = WindowsTaskManager(binding)
        self._stop = stop
        self._identity: WindowsTaskStopIdentity | None = None
        self._finalized = False
        self._guard = Lock()

    def __enter__(self) -> Self:
        """Keep the lifecycle interface without creating an unrelated stop window."""
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """Retain no native handle or COM wrapper requiring context cleanup."""

    def __call__(self) -> None:
        """Prepare exact ownership without invoking native Stop."""
        with self._guard:
            if self._identity is not None or self._finalized or self._stop.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            self._identity = self._manager.prepare_current_process_stop()

    def finalize(self) -> None:
        """Reverify and stop the prepared instance after the server's drain fence.

        A native refusal or uncertain failure retains the prepared identity.
        A retry must pass the complete native ownership checks again; no
        unsuccessful attempt is presented as a completed stop.
        """
        with self._guard:
            identity = self._identity
            if identity is None or self._finalized or not self._stop.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            self._manager.finalize_current_process_stop(identity)
            self._identity = None
            self._finalized = True
