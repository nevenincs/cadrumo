"""Local OAuth token endpoint for tests that drive a real credential refresh."""

from __future__ import annotations

import json
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import override
from urllib.parse import parse_qs

from google.oauth2.credentials import Credentials

ENDED_GRANT_RESPONSE: Mapping[str, str] = {
    "error": "invalid_grant",
    "error_description": "Token has been expired or revoked.",
}
"""Google's answer to a refresh for a grant the user revoked or that expired."""

SYNTHETIC_REFRESH_VALUE = "1//synthetic-refresh-value"
_SYNTHETIC_CLIENT_CREDENTIAL = "synthetic-client-credential"


@dataclass(frozen=True)
class TokenEndpoint:
    url: str
    grant_requests: list[dict[str, list[str]]] = field(default_factory=list)


@contextmanager
def token_endpoint(*, status: int, body: Mapping[str, str]) -> Generator[TokenEndpoint]:
    """Serve one fixed answer to every token request on the loopback interface."""
    grant_requests: list[dict[str, list[str]]] = []

    class TokenRequestHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            grant_requests.append(parse_qs(self.rfile.read(length).decode("utf-8")))
            encoded = json.dumps(dict(body)).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        @override
        def log_message(self, format: str, *args: object) -> None:
            return

    with ThreadingHTTPServer(("127.0.0.1", 0), TokenRequestHandler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield TokenEndpoint(f"http://127.0.0.1:{server.server_port}/token", grant_requests)
        finally:
            server.shutdown()
            thread.join(timeout=5)


def credentials_needing_refresh(endpoint_url: str, *, client_id: str) -> Credentials:
    """Return credentials with no access token, so the first request has to refresh."""
    return Credentials(
        token=None,
        refresh_token=SYNTHETIC_REFRESH_VALUE,
        token_uri=endpoint_url,
        client_id=client_id,
        client_secret=_SYNTHETIC_CLIENT_CREDENTIAL,
    )
