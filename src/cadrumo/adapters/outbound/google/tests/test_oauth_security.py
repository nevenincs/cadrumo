"""Adversarial callback, PKCE and identity tests using synthetic credentials."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import socket
import time
import traceback
import webbrowser
from collections.abc import Callable, Mapping
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast, override
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import crypt, jwt
from google.auth.transport import requests as auth_requests
from google.oauth2.credentials import Credentials

from .. import oauth_callback, oauth_flow
from ..errors import GoogleAuthNetworkError, GoogleAuthScopeInsufficientError, GoogleAuthValidationError
from ..oauth_callback import OAuthCallbackRefusedError, receive_authorization_code, validate_callback
from ..records import REQUIRED_SCOPES, OAuthToken
from .test_oauth_flow import _BrowserStandIn, _valid_oauth_client
from .token_endpoint_server import token_endpoint

if TYPE_CHECKING:
    from google_auth_oauthlib.flow import OAuthCredentials

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.fixture(autouse=True)
def synthetic_browser_desktop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Callback adversarial tests use a stand-in browser, not the machine's Chrome profile."""
    monkeypatch.setattr(oauth_callback, "_require_browser_desktop", lambda: None)


_AUTHORITY = "127.0.0.1:49152"
_STATE = "synthetic-unpredictable-state"


@pytest.mark.parametrize(
    "target",
    [
        "/?code=value",
        "/?state=&code=value",
        "/?state=wrong&code=value",
        f"/?state={_STATE}&state={_STATE}&code=value",
        f"/?state={_STATE}&code=one&code=two",
        f"/?state={_STATE}",
        f"/?state={_STATE}&code=",
        f"/other?state={_STATE}&code=value",
        f"http://{_AUTHORITY}/?state={_STATE}&code=value",
        f"/?state={_STATE}&code=value#fragment",
        f"/?state={_STATE}&code=value&error=access_denied",
        "/?state=wrong&error=access_denied",
    ],
)
def test_callback_refuses_uncorrelated_or_ambiguous_response(target: str) -> None:
    request = f"GET {target} HTTP/1.1\r\nHost: {_AUTHORITY}".encode()
    with pytest.raises(OAuthCallbackRefusedError):
        validate_callback(request, authority=_AUTHORITY, state=_STATE)


@pytest.mark.parametrize("host", ["attacker.example", "localhost:49152", f"{_AUTHORITY}\r\nHost: {_AUTHORITY}"])
def test_callback_requires_exact_single_host(host: str) -> None:
    request = f"GET /?state={_STATE}&code=value HTTP/1.1\r\nHost: {host}".encode()
    with pytest.raises(OAuthCallbackRefusedError):
        validate_callback(request, authority=_AUTHORITY, state=_STATE)


def test_callback_accepts_only_the_expected_code() -> None:
    request = f"GET /?state={_STATE}&code=encoded%2Fcode HTTP/1.1\r\nHost: {_AUTHORITY}".encode()
    assert validate_callback(request, authority=_AUTHORITY, state=_STATE) == "encoded/code"


@pytest.mark.parametrize("mode", ["timeout", "partial", "oversized", "browser_refused", "cancelled"])
def test_listener_closes_on_every_abandoned_flow(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    address: list[tuple[str, int]] = []
    connections: list[socket.socket] = []

    def browser_open(url: str, **kwargs: object) -> bool:
        parsed = urlsplit(url)
        assert parsed.hostname == "127.0.0.1" and parsed.port
        address.append((parsed.hostname, parsed.port))
        if mode in {"partial", "oversized"}:
            connection = socket.create_connection(address[0], timeout=1)
            connection.sendall(b"GET /?state=" if mode == "partial" else b"GET /?" + b"x" * 17000)
            connections.append(connection)
        if mode == "cancelled":
            raise KeyboardInterrupt
        return mode != "browser_refused"

    monkeypatch.setattr(webbrowser, "get", lambda: SimpleNamespace(open=browser_open))
    expected = (
        KeyboardInterrupt if mode == "cancelled" else webbrowser.Error if mode == "browser_refused" else TimeoutError
    )
    if mode == "oversized":
        expected = OAuthCallbackRefusedError
    started = time.monotonic()
    try:
        with pytest.raises(expected):
            receive_authorization_code(lambda uri: uri, state=_STATE, timeout_seconds=0.1)
        assert time.monotonic() - started < 2
        with pytest.raises(OSError):
            socket.create_connection(address[0], timeout=0.1)
    finally:
        for connection in connections:
            connection.close()


def test_real_flow_uses_fresh_s256_and_never_logs_callback(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("OAUTHLIB_INSECURE_TRANSPORT", "1")
    caplog.set_level(logging.INFO)
    urls: list[str] = []
    verifiers: list[str] = []
    for _attempt in range(2):
        browser = _BrowserStandIn("code=synthetic-intercepted-code")
        original_open = browser.open

        def open_browser(
            url: str, new: int = 0, autoraise: bool = True, *, delegate: Callable[..., bool] = original_open
        ) -> bool:
            urls.append(url)
            return delegate(url, new=new, autoraise=autoraise)

        monkeypatch.setattr(browser, "open", open_browser)
        monkeypatch.setattr(webbrowser, "get", lambda using=None, selected=browser: selected)
        with token_endpoint(status=200, body={"access_token": "synthetic-access", "expires_in": "3600"}) as endpoint:
            client = _valid_oauth_client().model_copy(update={"token_uri": endpoint.url})
            with pytest.raises(GoogleAuthValidationError):
                oauth_flow._run_local_server(client)
            for visit in browser.visits:
                visit.join(timeout=2)
            request = endpoint.grant_requests[0]
            verifier = request["code_verifier"][0]
            verifiers.append(verifier)
            query = parse_qs(urlsplit(urls[-1]).query)
            expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            assert query["code_challenge"] == [expected]
            assert query["code_challenge_method"] == ["S256"]
            assert set(query["scope"][0].split()) == set(REQUIRED_SCOPES)
            assert request["redirect_uri"] == query["redirect_uri"]
            redirect = urlsplit(query["redirect_uri"][0])
            assert redirect.hostname and redirect.port
            # No replay can be received after the first callback, even during token validation.
            with pytest.raises(OSError):
                socket.create_connection((redirect.hostname, redirect.port), timeout=0.1)
    first, second = [parse_qs(urlsplit(url).query) for url in urls]
    assert first["state"] != second["state"] and first["nonce"] != second["nonce"]
    assert verifiers[0] != verifiers[1]
    output = caplog.text + capsys.readouterr().out
    for secret in ["synthetic-intercepted-code", *verifiers, first["state"][0], second["state"][0]]:
        assert secret not in output


@pytest.mark.parametrize("granted", [None, (), REQUIRED_SCOPES[:2], (*REQUIRED_SCOPES, "extra-scope")])
def test_requested_scopes_cannot_substitute_for_the_returned_grant(granted: tuple[str, ...] | None) -> None:
    credentials = Credentials(
        token="synthetic-access", refresh_token="synthetic-refresh", scopes=REQUIRED_SCOPES, granted_scopes=granted
    )
    with pytest.raises(GoogleAuthScopeInsufficientError):
        oauth_flow._oauth_loopback_records(
            cast("OAuthCredentials", credentials),
            _valid_oauth_client(),
            before_handoff=None,
            acknowledged=None,
            expected_nonce="synthetic-nonce",
        )


@pytest.fixture
def signing_key() -> bytes:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def _signed_identity(monkeypatch: pytest.MonkeyPatch, key: bytes, claims: Mapping[str, object]) -> Credentials:
    private_key = serialization.load_pem_private_key(key, password=None)
    assert isinstance(private_key, rsa.RSAPrivateKey)
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    certificates = json.dumps({"synthetic-key": public_key.decode()}).encode()
    monkeypatch.setattr(
        auth_requests, "Request", lambda: lambda *args, **kwargs: SimpleNamespace(status=200, data=certificates)
    )
    token = jwt.encode(crypt.RSASigner.from_string(key, key_id="synthetic-key"), dict(claims))
    return Credentials(token="synthetic-access", id_token=token.decode())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("aud", "other-client"),
        ("iss", "https://attacker.example"),
        ("exp", 1),
        ("email_verified", False),
        ("email", None),
        ("sub", ""),
        ("nonce", "replayed-nonce"),
        ("azp", "other-client"),
    ],
)
def test_real_google_verifier_and_claim_checks_refuse_invalid_identity(
    monkeypatch: pytest.MonkeyPatch, signing_key: bytes, field: str, value: object
) -> None:
    claims: dict[str, object] = {
        "aud": "test-client",
        "iss": "https://accounts.google.com",
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
        "email": "synthetic@example.com",
        "email_verified": True,
        "sub": "synthetic-subject",
        "nonce": "fresh-nonce",
    }
    credentials = _signed_identity(monkeypatch, signing_key, claims)
    assert (
        oauth_flow._decode_email_from_id_token(credentials, audience="test-client", expected_nonce="fresh-nonce")
        == "synthetic@example.com"
    )
    claims[field] = value
    credentials = _signed_identity(monkeypatch, signing_key, claims)
    with pytest.raises((GoogleAuthNetworkError, GoogleAuthValidationError)):
        oauth_flow._decode_email_from_id_token(credentials, audience="test-client", expected_nonce="fresh-nonce")


def test_oauth_failures_and_record_repr_do_not_disclose_credentials() -> None:
    secret = "synthetic-sensitive-provider-response"
    try:
        oauth_flow._raise_local_server_error(ValueError(secret))
    except GoogleAuthNetworkError as error:
        assert secret not in "".join(traceback.format_exception(error))
        assert secret not in str(error.context)
    token = OAuthToken(refresh_token=secret, client_id="client", token_uri="https://oauth2.googleapis.com/token")
    assert secret not in repr(token)


def test_identity_with_a_forged_signature_is_refused(monkeypatch: pytest.MonkeyPatch, signing_key: bytes) -> None:
    credentials = _signed_identity(
        monkeypatch,
        signing_key,
        {
            "aud": "test-client",
            "iss": "https://accounts.google.com",
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            "email": "synthetic@example.com",
            "email_verified": True,
            "sub": "synthetic-subject",
            "nonce": "fresh-nonce",
        },
    )
    header, payload, signature = credentials.id_token.split(".")
    altered = ("A" if signature[0] != "A" else "B") + signature[1:]
    forged = Credentials(token="synthetic-access", id_token=f"{header}.{payload}.{altered}")
    with pytest.raises(GoogleAuthNetworkError):
        oauth_flow._decode_email_from_id_token(forged, audience="test-client", expected_nonce="fresh-nonce")


def test_complete_authorization_validates_signed_nonce_and_returns_records(
    monkeypatch: pytest.MonkeyPatch, signing_key: bytes
) -> None:
    monkeypatch.setenv("OAUTHLIB_INSECURE_TRANSPORT", "1")
    body = {
        "access_token": "synthetic-access",
        "refresh_token": "synthetic-refresh",
        "token_type": "Bearer",
        "expires_in": "3600",
        "scope": " ".join(REQUIRED_SCOPES),
    }
    client = _valid_oauth_client()

    class SignedBrowser(_BrowserStandIn):
        @override
        def open(self, url: str, new: int = 0, autoraise: bool = True) -> bool:
            query = parse_qs(urlsplit(url).query)
            credentials = _signed_identity(
                monkeypatch,
                signing_key,
                {
                    "aud": client.client_id,
                    "iss": "https://accounts.google.com",
                    "iat": int(time.time()),
                    "exp": int(time.time()) + 300,
                    "email": "synthetic@example.com",
                    "email_verified": True,
                    "sub": "synthetic-subject",
                    "nonce": query["nonce"][0],
                },
            )
            body["id_token"] = credentials.id_token
            return super().open(url, new=new, autoraise=autoraise)

    browser = SignedBrowser("code=synthetic-code")
    monkeypatch.setattr(webbrowser, "get", lambda: browser)
    with token_endpoint(status=200, body=body) as endpoint:
        loopback_client = client.model_copy(update={"token_uri": endpoint.url})
        refresh, _uri, email, scopes = oauth_flow._run_local_server(loopback_client)
        for visit in browser.visits:
            visit.join(timeout=2)
        assert len(endpoint.grant_requests) == 1
    from .....core.time.clock import now

    token, metadata = oauth_flow.credentials_to_records(
        refresh_token=refresh,
        token_uri=client.token_uri,
        client_id=client.client_id,
        account_email=email,
        granted_scopes=scopes,
        issued_at=now(),
    )
    assert token.refresh_token == "synthetic-refresh" and token.client_id == client.client_id
    assert metadata.account_email == "synthetic@example.com" and set(metadata.granted_scopes) == set(REQUIRED_SCOPES)


@pytest.mark.parametrize(
    "answer",
    [
        "code=first&code=second",
        "code=",
        "code=value&state=another",
    ],
)
def test_invalid_wire_callback_never_reaches_token_endpoint(monkeypatch: pytest.MonkeyPatch, answer: str) -> None:
    browser = _BrowserStandIn(answer)
    monkeypatch.setattr(webbrowser, "get", lambda: browser)
    with token_endpoint(status=200, body={"access_token": "must-not-be-requested"}) as endpoint:
        client = _valid_oauth_client().model_copy(update={"token_uri": endpoint.url})
        with pytest.raises(GoogleAuthNetworkError):
            oauth_flow._run_local_server(client)
        for visit in browser.visits:
            visit.join(timeout=2)
        assert endpoint.grant_requests == []
