"""Single-use, bounded loopback receiver for a desktop authorization response."""

from __future__ import annotations

import secrets
import socket
import sys
import time
import webbrowser
from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit

from ....application.runtime.contracts import RuntimeRefusalError
from ...local_runtime.windows_desktop_logon import current_windows_desktop_logon
from .errors import GoogleAuthLoopbackBindError, GoogleAuthValidationError

LOOPBACK_HOST = "127.0.0.1"
_MAX_REQUEST_BYTES = 16_384


class OAuthCallbackRefusedError(GoogleAuthValidationError):
    """A callback failed correlation; its contents must not enter diagnostics."""


class OAuthConsentDeclinedError(OAuthCallbackRefusedError):
    """The correlated authorization response reports denied consent."""


class OAuthCallbackBindError(GoogleAuthLoopbackBindError):
    """The loopback listener could not acquire its ephemeral address."""


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("OAuth callback expired")
    return remaining


def validate_callback(request: bytes, *, authority: str, state: str) -> str:
    """Accept one unambiguous GET response for the exact redirect and state."""
    try:
        lines = request.decode("ascii").split("\r\n")
        method, target, version = lines[0].split(" ")
        headers = [line.split(":", 1) for line in lines[1:] if line]
        if any(len(header) != 2 for header in headers):
            raise ValueError
        hosts = [value.strip() for name, value in headers if name.lower() == "host"]
        parsed = urlsplit(target)
        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=32)
    except (ValueError, UnicodeError):
        raise OAuthCallbackRefusedError("Malformed OAuth callback") from None
    if (
        method != "GET"
        or version not in {"HTTP/1.0", "HTTP/1.1"}
        or hosts != [authority]
        or parsed.scheme
        or parsed.netloc
        or parsed.path != "/"
        or parsed.fragment
        or any(ord(character) <= 32 or ord(character) == 127 for character in target)
        or any(len(values) != 1 for values in query.values())
    ):
        raise OAuthCallbackRefusedError("Unexpected OAuth callback target")
    received_state = query.get("state", [""])[0]
    if not received_state or not secrets.compare_digest(received_state.encode(), state.encode()):
        raise OAuthCallbackRefusedError("OAuth callback state mismatch")
    code = query.get("code", [""])[0]
    error = query.get("error", [""])[0]
    if "error" in query:
        if "code" not in query and error == "access_denied":
            raise OAuthConsentDeclinedError("Google consent declined")
        raise OAuthCallbackRefusedError("OAuth callback reported an error")
    if not code.strip():
        raise OAuthCallbackRefusedError("OAuth callback has no authorization code")
    return code


def receive_authorization_code(authorization_url: Callable[[str], str], *, state: str, timeout_seconds: float) -> str:
    """Open the external browser and consume exactly one callback, without logging URLs.

    One monotonic deadline covers accept and every read, including slow partial
    headers. Socket ownership ends before the caller exchanges the code.
    """
    _require_browser_desktop()
    deadline = time.monotonic() + timeout_seconds
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind((LOOPBACK_HOST, 0))
        except OSError:
            raise OAuthCallbackBindError("OAuth loopback bind failed") from None
        listener.listen(1)
        authority = f"{LOOPBACK_HOST}:{listener.getsockname()[1]}"
        url = authorization_url(f"http://{authority}/")
        if not webbrowser.get().open(url, new=1, autoraise=True):
            raise webbrowser.Error("OS browser launcher refused")
        listener.settimeout(_remaining(deadline))
        connection, _peer = listener.accept()
        with connection:
            request = bytearray()
            while b"\r\n\r\n" not in request:
                connection.settimeout(_remaining(deadline))
                chunk = connection.recv(min(4096, _MAX_REQUEST_BYTES - len(request)))
                if not chunk:
                    raise OAuthCallbackRefusedError("Incomplete or oversized OAuth callback")
                request.extend(chunk)
            _remaining(deadline)
            try:
                code = validate_callback(bytes(request).split(b"\r\n\r\n", 1)[0], authority=authority, state=state)
            except OAuthCallbackRefusedError:
                _respond(connection, accepted=False, deadline=deadline)
                raise
            _respond(connection, accepted=True, deadline=deadline)
            return code


def _require_browser_desktop() -> None:
    """Never start the default browser/profile from Windows Session 0 or an unverified desktop."""
    if sys.platform != "win32":
        return
    try:
        current_windows_desktop_logon()
    except RuntimeRefusalError:
        raise webbrowser.Error("OS browser launcher requires the user's interactive desktop") from None


def _respond(connection: socket.socket, *, accepted: bool, deadline: float) -> None:
    status = "200 OK" if accepted else "400 Bad Request"
    body = b"Response received. Return to Cadrumo." if accepted else b"Authorization response refused."
    response = (
        f"HTTP/1.1 {status}\r\nContent-Type: text/plain; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\nCache-Control: no-store\r\n"
        "Referrer-Policy: no-referrer\r\nConnection: close\r\n\r\n"
    ).encode("ascii") + body
    try:
        connection.settimeout(_remaining(deadline))
        connection.sendall(response)
    except OSError:
        # A browser closing its tab cannot turn a validated response into a retry.
        pass
