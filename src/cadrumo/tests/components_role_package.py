"""Run the real ``components`` role of a built Cadrumo binary from tests, against throwaway roots only.

``just test-components-role IMAGE`` names the built binary in
``CADRUMO_DEVELOPMENT_ROLE_IMAGE``. A binary already in a staged package runs
there; any other is staged beside the package's pin tables and the bundled
browser driver's manifest in a throwaway package, the layout the role resolves
from its own image. Each case gets its own storage root. A local proxy stands
in for the network, refusing or holding every tunnel, so nothing reaches a
publisher.
"""

from __future__ import annotations

import os
import shutil
import socket
import sys
import threading
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

import pytest

__all__ = [
    "components_role_fixture",
    "holding_proxy_fixture",
    "refusing_proxy_fixture",
    "stage_components_role",
    "staged_components_role_fixture",
]

_IMAGE_VARIABLE: Final = "CADRUMO_DEVELOPMENT_ROLE_IMAGE"
"""The name the components client reads in a checkout; shared support may not import the adapter that owns it."""

_PINS: Final = Path(__file__).resolve().parents[1] / "_data" / "dependencies"
_REFUSAL: Final = b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"


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
    """Point this process's client at the staged binary and a throwaway storage root, and return the root."""
    monkeypatch.setattr(sys, "_xoptions", {}, raising=False)
    monkeypatch.setenv(_IMAGE_VARIABLE, str(staged_components_role))
    root = tmp_path / "root"
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", str(root))
    monkeypatch.delenv("CADRUMO_PROXY_URL", raising=False)
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


@pytest.fixture(name="holding_proxy")
def holding_proxy_fixture(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Route the role through a proxy that never answers a tunnel."""
    with _proxy(None) as address:
        monkeypatch.setenv("CADRUMO_PROXY_URL", address)
        yield
