"""The loopback download host: verified archives at their pinned paths, each fetched once, and nothing else.

A real server on a loopback port is read by a real HTTP client, as the vendor
installer reads it. The fetcher stands in for the verified download and
records how often it was asked.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from .....application.browser_archive_pins import BrowserArchivePin
from .....application.dependency_transfer import DependencyTransferError
from ..archive_server import VerifiedArchiveServer

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PATH = "builds/cft/156.0.8078.4/win64/chrome-win64.zip"
_BODY = bytes(range(256)) * 10_000


def _pin(body: bytes = _BODY) -> BrowserArchivePin:
    return BrowserArchivePin(
        platform="win-x64",
        directory_name="chromium-1248",
        path=_PATH,
        urls=(f"https://cdn.playwright.dev/{_PATH}",),
        download_bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
    )


class _Fetcher:
    """Writes ``content`` as the fetched archive, or raises ``failure``; counts every call."""

    def __init__(self, tmp_path: Path, content: bytes = _BODY, failure: DependencyTransferError | None = None) -> None:
        self.path = tmp_path / "staged.zip"
        self.content = content
        self.failure = failure
        self.calls = 0

    def __call__(self, pin: BrowserArchivePin) -> Path:
        del pin
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        self.path.write_bytes(self.content)
        return self.path


def test_the_pinned_path_serves_the_verified_archive_fetched_once_and_nothing_else(tmp_path: Path) -> None:
    fetcher = _Fetcher(tmp_path)

    with VerifiedArchiveServer((_pin(),), fetcher) as server, httpx.Client(trust_env=False) as client:
        served = client.get(f"{server.origin}/{_PATH}")
        again = client.get(f"{server.origin}/{_PATH}")
        other = client.get(f"{server.origin}/builds/cft/156.0.8078.4/win64/chrome-headless-shell-win64.zip")
        escaped = client.get(f"{server.origin}/{_PATH}/../../staged.zip")

    assert server.origin.startswith("http://127.0.0.1:")
    assert served.status_code == again.status_code == 200
    assert served.content == again.content == _BODY
    assert fetcher.calls == 1
    assert (other.status_code, escaped.status_code) == (404, 404)
    assert server.refused == 2
    assert server.mismatched == 0
    assert server.failure is None


def test_a_failed_fetch_is_remembered_and_never_tried_again(tmp_path: Path) -> None:
    refused = DependencyTransferError(DependencyFailureCategory.BLOCKED_BY_NETWORK, transient=False)
    fetcher = _Fetcher(tmp_path, failure=refused)

    with VerifiedArchiveServer((_pin(),), fetcher) as server, httpx.Client(trust_env=False) as client:
        statuses = [client.get(f"{server.origin}/{_PATH}").status_code for _ in range(3)]

    assert statuses == [502, 502, 502]
    assert fetcher.calls == 1
    assert server.failure is refused


def test_a_staged_file_that_differs_from_its_pin_is_never_delivered_whole(tmp_path: Path) -> None:
    fetcher = _Fetcher(tmp_path, content=_BODY[:-5] + b"evil!")
    received = bytearray()

    with (
        VerifiedArchiveServer((_pin(),), fetcher) as server,
        httpx.Client(trust_env=False) as client,
        pytest.raises(httpx.RemoteProtocolError),
        client.stream("GET", f"{server.origin}/{_PATH}") as response,
    ):
        for chunk in response.iter_raw():
            received += chunk

    assert len(received) < len(_BODY)
    assert not received.endswith(b"evil!")
    assert server.mismatched == 1
