"""A keyring backend that looks usable and then refuses every call, as a logon-less Windows session does.

``keyring.backends.fail.Keyring`` reports priority 0, so it only ever reaches
the class-level "no usable keychain" refusal. A real Windows credential store
reached from a process without a logon session is worse: it reports a positive
priority, passes that probe, and then raises
``win32ctypes.pywin32.pywintypes.error`` (1312, "a specified logon session does
not exist") from every call. That type derives directly from ``Exception``, so
it is neither a ``KeyringError`` nor an ``OSError``. This backend reproduces
exactly that shape, selectable in a child process through
``PYTHON_KEYRING_BACKEND``.
"""

from __future__ import annotations

from typing import override

from keyring.backend import KeyringBackend

CALL_TIME_REFUSING_KEYRING = f"{__name__}.CallTimeRefusingKeyring"


class CredentialManagerLogonSessionError(Exception):
    """Stands in for ``pywintypes.error``: an ``Exception`` outside every keyring and OS error family."""


class CallTimeRefusingKeyring(KeyringBackend):
    """Passes the usability probe, then refuses each credential call with error 1312."""

    priority = 1

    @override
    def get_password(self, service: str, username: str) -> str | None:
        raise CredentialManagerLogonSessionError(1312, "CredRead", "A specified logon session does not exist.")

    @override
    def set_password(self, service: str, username: str, password: str) -> None:
        raise CredentialManagerLogonSessionError(1312, "CredWrite", "A specified logon session does not exist.")

    @override
    def delete_password(self, service: str, username: str) -> None:
        raise CredentialManagerLogonSessionError(1312, "CredDelete", "A specified logon session does not exist.")


__all__ = ["CALL_TIME_REFUSING_KEYRING", "CallTimeRefusingKeyring", "CredentialManagerLogonSessionError"]
