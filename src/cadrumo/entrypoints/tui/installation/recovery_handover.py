"""Hand a recovery code the runtime minted to the person, and bring back proof they hold it.

The runtime delivers the code in one secret frame and installs nothing until
the same code is read back. This is the read-back: the code is shown once, on
the screen first registration uses, and the frame returned is produced only
once the person has typed the code back correctly.
"""

from __future__ import annotations

from threading import Event
from typing import TYPE_CHECKING, Self

from pydantic import SecretBytes

from ..secret.registration import RecoveryHandoverDeclinedError, confirm_recovery_possession

if TYPE_CHECKING:
    from textual.app import App

_ENCODING = "utf-8"


class _DeliveredRecoveryCode:
    """The delivered buffer, readable as the code only while the handover holds it."""

    __slots__ = ("_buffer",)

    def __init__(self, buffer: bytearray) -> None:
        self._buffer = buffer

    @property
    def code(self) -> str:
        """Decode the code from the buffer the connection still owns."""
        return self._buffer.decode(_ENCODING)

    def wipe(self) -> None:
        """Overwrite the delivered buffer."""
        self._buffer[:] = bytes(len(self._buffer))

    def __enter__(self) -> Self:
        """Hold the buffer for one handover."""
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Wipe the buffer however the handover ended."""
        self.wipe()


class RecoveryCodeHandover:
    """Hold one delivered recovery code until the person proves they copied it.

    An instance is the act's secret holder. It runs on the thread that
    performs the act and blocks there while the code screen is open.
    """

    def __init__(self, app: App[object], *, pending: set[Event], locale: str | None = None) -> None:
        """Bind the application that shows the code, the owner's open handovers, and the screen's language."""
        self._app = app
        self._pending = pending
        self._locale = locale

    def __call__(self, delivered: bytearray) -> SecretBytes | None:
        """Show the code and return the read-back copy, or ``None`` when it was not confirmed."""
        with _DeliveredRecoveryCode(delivered) as recovery_key:
            try:
                proof = confirm_recovery_possession(self._app, recovery_key, locale=self._locale, pending=self._pending)
            except RecoveryHandoverDeclinedError:
                return None
            return SecretBytes(proof.encode(_ENCODING))


__all__ = ["RecoveryCodeHandover"]
