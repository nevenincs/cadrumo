"""Downloading a pinned archive: only approved HTTPS hops, only the pinned bytes, nothing kept on refusal.

The network is an ``httpx.MockTransport`` that plays the vendor's mirrors and
a hostile responder; the redirect admission, the streaming size and digest
checks and the file handling all run for real.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from .....application.browser_archive_pins import BrowserArchivePin
from .....application.dependency_transfer import DependencyTransferError
from ..archive_fetch import ARCHIVE_FETCH_MAX_REDIRECTS, fetch_pinned_archive

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_HOSTS = ("cdn.playwright.dev", "playwright.download.prss.microsoft.com", "storage.googleapis.com")
_PATH = "builds/ffmpeg/1013/ffmpeg-win64.zip"
_PRIMARY = f"https://cdn.playwright.dev/dbazure/download/playwright/{_PATH}"
_FALLBACK = f"https://cdn.playwright.dev/{_PATH}"
_BODY = bytes(range(256)) * 9000 + b"tail"


def _pin(body: bytes = _BODY) -> BrowserArchivePin:
    return BrowserArchivePin(
        platform="win-x64",
        directory_name="ffmpeg-1013",
        path=_PATH,
        urls=(_PRIMARY, _FALLBACK),
        download_bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
    )


type _Route = Callable[[httpx.Request], httpx.Response]


class _Network:
    """Answers each URL from a table and records every request that reached it."""

    def __init__(self, routes: dict[str, _Route]) -> None:
        self.routes = routes
        self.requested: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requested.append(url)
        route = self.routes.get(url)
        return httpx.Response(404) if route is None else route(request)


def _redirect(location: str) -> _Route:
    return lambda _request: httpx.Response(307, headers={"location": location})


def _serve(body: bytes, *, length: str | None = None) -> _Route:
    headers = {"content-length": str(len(body)) if length is None else length}
    return lambda _request: httpx.Response(200, stream=httpx.ByteStream(body), headers=headers)


def _fetch(
    network: _Network, destination: Path, *, pin: BrowserArchivePin | None = None, cancel: bool = False
) -> list[int]:
    seen: list[int] = []
    fetch_pinned_archive(
        pin or _pin(),
        destination,
        allowed_hosts=_HOSTS,
        proxy=None,
        progress=seen.append,
        cancelled=lambda: cancel,
        deadline=time.monotonic() + 30,
        transport=httpx.MockTransport(network),
    )
    return seen


def _refused(network: _Network, destination: Path) -> DependencyTransferError:
    with pytest.raises(DependencyTransferError) as raised:
        _fetch(network, destination)
    assert not destination.exists()
    return raised.value


def test_a_redirect_between_approved_hosts_yields_exactly_the_pinned_bytes(tmp_path: Path) -> None:
    blob = f"https://playwright.download.prss.microsoft.com/dbazure/download/playwright/{_PATH}"
    network = _Network({_PRIMARY: _redirect(blob), blob: _serve(_BODY)})
    destination = tmp_path / "archive.zip"

    seen = _fetch(network, destination)

    assert destination.read_bytes() == _BODY
    assert seen[-1] == len(_BODY)
    assert network.requested == [_PRIMARY, blob]


@pytest.mark.parametrize(
    "location",
    (
        f"https://downloads.attacker.example/{_PATH}",
        f"http://storage.googleapis.com/{_PATH}",
        f"https://storage.googleapis.com:8443/{_PATH}",
        f"https://user:secret@storage.googleapis.com/{_PATH}",
    ),
)
def test_a_redirect_off_the_approved_hosts_is_refused_before_it_is_followed(tmp_path: Path, location: str) -> None:
    network = _Network({_PRIMARY: _redirect(location), _FALLBACK: _serve(_BODY)})

    refused = _refused(network, tmp_path / "archive.zip")

    assert refused.category is DependencyFailureCategory.BLOCKED_BY_NETWORK
    assert refused.transient is False
    # Neither the unapproved hop nor another mirror is tried once a source has redirected off the plan.
    assert network.requested == [_PRIMARY]


def test_an_endless_redirect_chain_is_refused(tmp_path: Path) -> None:
    network = _Network({_PRIMARY: _redirect(_PRIMARY)})

    refused = _refused(network, tmp_path / "archive.zip")

    assert refused.category is DependencyFailureCategory.BLOCKED_BY_NETWORK
    assert len(network.requested) == ARCHIVE_FETCH_MAX_REDIRECTS + 1


@pytest.mark.parametrize(
    "route",
    (
        _serve(_BODY[:-4] + b"evil"),
        _serve(_BODY + b"more"),
        _serve(_BODY[:-1]),
        _serve(_BODY, length=str(len(_BODY) + 1)),
    ),
    ids=("substituted", "longer", "shorter", "declared-size"),
)
def test_bytes_other_than_the_pinned_archive_are_refused_and_discarded(tmp_path: Path, route: _Route) -> None:
    network = _Network({_PRIMARY: route, _FALLBACK: _serve(_BODY)})

    refused = _refused(network, tmp_path / "archive.zip")

    assert refused.category is DependencyFailureCategory.DAMAGED_DOWNLOAD
    assert refused.transient is False
    assert network.requested == [_PRIMARY]


def test_a_failing_mirror_gives_way_to_the_next(tmp_path: Path) -> None:
    network = _Network({_PRIMARY: lambda _request: httpx.Response(503), _FALLBACK: _serve(_BODY)})
    destination = tmp_path / "archive.zip"

    _fetch(network, destination)

    assert destination.read_bytes() == _BODY
    assert network.requested == [_PRIMARY, _FALLBACK]


def test_when_every_mirror_fails_the_last_failure_is_reported_as_retryable(tmp_path: Path) -> None:
    network = _Network(
        {_PRIMARY: lambda _request: httpx.Response(503), _FALLBACK: lambda _request: httpx.Response(429)}
    )

    refused = _refused(network, tmp_path / "archive.zip")

    assert refused.category is DependencyFailureCategory.HOST_UNREACHABLE
    assert refused.transient is True


def test_a_cancel_stops_the_download_and_keeps_nothing(tmp_path: Path) -> None:
    destination = tmp_path / "archive.zip"

    with pytest.raises(DependencyTransferError) as raised:
        _fetch(_Network({_PRIMARY: _serve(_BODY)}), destination, cancel=True)

    assert raised.value.category is DependencyFailureCategory.CANCELLED
    assert not destination.exists()
