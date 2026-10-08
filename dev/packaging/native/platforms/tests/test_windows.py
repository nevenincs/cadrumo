"""Windows SDK provisioning owns its generated destination after origin admission."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import httpx
import pytest

from dev.packaging.native.platforms import windows

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _archive(members: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as package:
        for name, content in members.items():
            package.writestr(name, content)
    return stream.getvalue()


def _tools(content: bytes) -> dict[str, str]:
    return {
        "cpython_source": "https://api.nuget.org/v3-flatcontainer/python/{version}/python.{version}.nupkg",
        "cpython_sha256": hashlib.sha256(content).hexdigest(),
    }


def test_sdk_creates_absent_nested_destination_before_download_and_reuses_verified_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = _archive({"tools/python.exe": b"interpreter fixture", "tools/include/Python.h": b"SDK header fixture"})
    destination = tmp_path / "generated/nested/windows-sdk"
    assert not destination.parent.exists()
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=content)

    contract = {"sdk": {"root": "sdk/tools"}}
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(windows.httpx, "stream", client.stream)
        selected = windows.provision_sdk(destination, "3.13.11", _tools(content), contract)
        assert selected == destination / "sdk/tools"
        assert (selected / "python.exe").read_bytes() == b"interpreter fixture"
        assert (selected / "include/Python.h").read_bytes() == b"SDK header fixture"
        assert (destination / "python.3.13.11.nupkg").read_bytes() == content
        assert windows.provision_sdk(destination, "3.13.11", _tools(content), contract) == selected
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert str(requests[0].url) == "https://api.nuget.org/v3-flatcontainer/python/3.13.11/python.3.13.11.nupkg"


@pytest.mark.parametrize(
    "source", ["http://api.nuget.org/python/{version}", "https://foreign.invalid/python/{version}"]
)
def test_sdk_refuses_unadmitted_origin_before_creating_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    destination = tmp_path / "generated/nested/windows-sdk"
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=b"must not be requested")

    tools = _tools(b"unused") | {"cpython_source": source}
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(windows.httpx, "stream", client.stream)
        with pytest.raises(ValueError, match="pinned HTTPS NuGet origin"):
            windows.provision_sdk(destination, "3.13.11", tools, {"sdk": {"root": "sdk/tools"}})
    assert requests == []
    assert not destination.parent.exists()


@pytest.mark.parametrize("failure", ["digest", "escaping-member"])
def test_sdk_still_refuses_hash_mismatch_and_escaping_archive_before_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    content = _archive(
        {"../escaped.txt": b"escaping fixture"} if failure == "escaping-member" else {"tools/python.exe": b"fixture"}
    )
    tools = _tools(content)
    if failure == "digest":
        tools["cpython_sha256"] = "0" * 64
    destination = tmp_path / "generated/nested/windows-sdk"
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=content))) as client:
        monkeypatch.setattr(windows.httpx, "stream", client.stream)
        with pytest.raises(ValueError, match="SHA256 mismatch" if failure == "digest" else "escaping path"):
            windows.provision_sdk(destination, "3.13.11", tools, {"sdk": {"root": "sdk/tools"}})
    assert not (destination / "sdk").exists()
    assert not (destination / "escaped.txt").exists()
