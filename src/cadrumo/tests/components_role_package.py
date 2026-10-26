"""Run the real ``components`` role of a built Cadrumo binary from tests, against throwaway roots only.

``just test-components-role IMAGE`` names the built binary in
``CADRUMO_DEVELOPMENT_ROLE_IMAGE``. A binary already in a staged package runs
there; any other is staged beside the package's pin tables and the bundled
browser driver's manifest in a throwaway package, the layout the role resolves
from its own image. Each case gets its own storage root, and every relocated
storage member and proxy setting the test run holds is withdrawn, so the role
derives each location from that root and never reaches the run's shared browser
cache. A local proxy stands in for the network, refusing, holding or counting
every tunnel, so nothing reaches a publisher.
"""

from __future__ import annotations

import base64
import os
import secrets
import shutil
import socket
import sys
import threading
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import pytest

from ..core.config import Settings

__all__ = [
    "CountingProxy",
    "components_role_fixture",
    "counting_proxy_fixture",
    "holding_proxy_fixture",
    "refusing_proxy_fixture",
    "stage_components_role",
    "staged_components_role_fixture",
]

_IMAGE_VARIABLE: Final = "CADRUMO_DEVELOPMENT_ROLE_IMAGE"
"""The name the components client reads in a checkout; shared support may not import the adapter that owns it."""

_PINS: Final = Path(__file__).resolve().parents[1] / "_data" / "dependencies"
_REFUSAL: Final = b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
_CREDENTIALS_REQUIRED: Final = (
    b"HTTP/1.1 407 Proxy Authentication Required\r\n"
    b'Proxy-Authenticate: Basic realm="components-role"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'
)


def _driver_manifest() -> Path:
    import playwright

    return Path(playwright.__file__).parent / "driver" / "package"


def stage_components_role(image: Path, package: Path) -> Path:
    """Copy ``image`` into a package at ``package`` holding the pins and the driver manifest; return the copy."""
    staged = package / image.name
    package.mkdir(parents=True, exist_ok=True)
    shutil.copy2(image, staged)
    (package / "data").mkdir()
    (package / "data" / "package-manifest.json").write_text("{}", encoding="utf-8")
    shutil.copytree(_PINS, package / "cadrumo" / "site-packages" / "cadrumo" / "_data" / "dependencies")
    driver = package / "cadrumo" / "site-packages" / "playwright" / "driver" / "package"
    driver.mkdir(parents=True)
    for name in ("browsers.json", "package.json"):
        shutil.copy2(_driver_manifest() / name, driver / name)
    return staged


@pytest.fixture(name="staged_components_role", scope="module")
def staged_components_role_fixture(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The built binary, in a package: its own staged one, or a throwaway one assembled here."""
    named = os.environ.get(_IMAGE_VARIABLE, "")
    if not named:
        pytest.fail(f"Name a built Cadrumo binary in {_IMAGE_VARIABLE}: just test-components-role IMAGE")
    image = Path(named)
    if not image.is_absolute() or not image.is_file():
        pytest.fail(f"{_IMAGE_VARIABLE} names no built binary: {image}")
    if (image.parent / "data" / "package-manifest.json").is_file():
        return image
    return stage_components_role(image, tmp_path_factory.mktemp("package"))


@pytest.fixture(name="components_role")
def components_role_fixture(staged_components_role: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point this process's client at the staged binary and a throwaway storage root, and return the root.

    The client hands the role every location and proxy setting this process
    holds, and the test run pins the browser member to the shared browser cache
    every test launches from. Left in place, the role would plan, adopt and
    remove that shared cache's builds instead of the throwaway root's.
    """
    monkeypatch.setattr(sys, "_xoptions", {}, raising=False)
    monkeypatch.setenv(_IMAGE_VARIABLE, str(staged_components_role))
    for name in Settings.storage_env_var_names() | Settings.proxy_env_var_names():
        monkeypatch.delenv(name, raising=False)
    root = tmp_path / "root"
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", str(root))
    return root


@contextmanager
def _proxy(answer: bytes | None) -> Generator[str]:
    """A local proxy that answers every tunnel request with ``answer``, or holds it open unanswered."""
    server = socket.create_server(("127.0.0.1", 0))
    held: list[socket.socket] = []

    def serve() -> None:
        while True:
            try:
                client, _ = server.accept()
            except OSError:
                return
            client.recv(65536)
            if answer is None:
                held.append(client)
                continue
            client.sendall(answer)
            client.close()

    threading.Thread(target=serve, name="components-role-proxy", daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.getsockname()[1]}"
    finally:
        server.close()
        for client in held:
            client.close()


@pytest.fixture(name="refusing_proxy")
def refusing_proxy_fixture(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Route the role through a proxy that refuses every tunnel, as a network filter does."""
    with _proxy(_REFUSAL) as address:
        monkeypatch.setenv("CADRUMO_PROXY_URL", address)
        yield


def _read_head(client: socket.socket) -> bytes:
    """Read one request head, however the client splits it across writes."""
    received = b""
    while b"\r\n\r\n" not in received and len(received) <= 16384:
        chunk = client.recv(4096)
        if not chunk:
            break
        received += chunk
    return received.split(b"\r\n\r\n", 1)[0]


@dataclass(slots=True)
class CountingProxy:
    """A local proxy that demands ``user:password`` and refuses every tunnel it is asked for.

    A tunnel request without the credentials is answered 407; one carrying them
    is counted by its host and answered 403, as a network filter does, so no
    request leaves the computer. ``address`` carries the credentials, the only
    way a proxy password crosses a process boundary.
    """

    user: str
    password: str
    tunnels: dict[str, int] = field(default_factory=dict)
    unauthenticated: int = 0
    _server: socket.socket | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def address(self) -> str:
        """The proxy address the role is given, credentials included."""
        if self._server is None:
            raise RuntimeError("the proxy is not started")
        return f"http://{self.user}:{self.password}@127.0.0.1:{self._server.getsockname()[1]}"

    def credential_forms(self) -> tuple[str, ...]:
        """Every spelling of the credentials a careless log line could carry: plain, in the address, encoded."""
        pair = f"{self.user}:{self.password}"
        return (self.password, f"{pair}@", base64.b64encode(pair.encode()).decode())

    def _answer(self, client: socket.socket) -> None:
        with client:
            request, *headers = _read_head(client).decode("latin-1").split("\r\n")
            expected = "Basic " + base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
            authorized = any(
                name.strip().lower() == "proxy-authorization" and value.strip() == expected
                for name, _, value in (header.partition(":") for header in headers)
            )
            with self._lock:
                if not authorized:
                    self.unauthenticated += 1
                elif request.startswith("CONNECT "):
                    host = request.split(" ")[1].rpartition(":")[0]
                    self.tunnels[host] = self.tunnels.get(host, 0) + 1
            client.sendall(_REFUSAL if authorized else _CREDENTIALS_REQUIRED)

    def _serve(self, server: socket.socket) -> None:
        while True:
            try:
                client, _ = server.accept()
            except OSError:
                return
            threading.Thread(target=self._answer, args=(client,), daemon=True).start()

    @contextmanager
    def running(self) -> Generator[CountingProxy]:
        """Listen on a loopback port for the block."""
        server = socket.create_server(("127.0.0.1", 0))
        self._server = server
        threading.Thread(target=self._serve, args=(server,), name="components-role-counting-proxy", daemon=True).start()
        try:
            yield self
        finally:
            server.close()


@pytest.fixture(name="counting_proxy")
def counting_proxy_fixture(monkeypatch: pytest.MonkeyPatch) -> Iterator[CountingProxy]:
    """Route the role through a proxy that demands credentials carried in its address and counts each tunnel."""
    # A fresh value each run, so a match anywhere can only be this run's leak.
    with CountingProxy(user="synthetic-user", password=secrets.token_hex(16)).running() as proxy:
        monkeypatch.setenv("CADRUMO_PROXY_URL", proxy.address)
        yield proxy


@pytest.fixture(name="holding_proxy")
def holding_proxy_fixture(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Route the role through a proxy that never answers a tunnel."""
    with _proxy(None) as address:
        monkeypatch.setenv("CADRUMO_PROXY_URL", address)
        yield
