"""Gate: the committed llama.cpp pins are well formed, declared and exactly what the tool renders.

Nothing here reaches the network. The defect cases change a copy of the committed
file or build a real archive in memory, and must each be reported or refused by
the same parser and verifier the generator runs.
"""

from __future__ import annotations

import hashlib
import io
import tarfile
import zipfile
from collections.abc import Mapping

import httpx
import pytest
from pydantic import ValidationError

from ..llamacpp_pins import (
    PINS_PATH,
    TARGET_ASSETS,
    ReleaseAsset,
    ServerPins,
    _fetch,
    _Listed,
    check_pins,
    declared_hosts,
    load_server_pins,
    render_pins,
    select_release,
    verify_archive,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def committed() -> ServerPins:
    return load_server_pins()


def test_the_committed_file_pins_every_target_from_declared_hosts(committed: ServerPins) -> None:
    assert check_pins(committed, PINS_PATH.read_text(encoding="utf-8")) == []
    assert {pin.target for pin in committed.archives} == set(TARGET_ASSETS)
    assert set(committed.hosts) <= declared_hosts()


def test_the_committed_file_is_exactly_what_the_generator_renders(committed: ServerPins) -> None:
    assert PINS_PATH.read_text(encoding="utf-8") == render_pins(committed)


def test_windows_and_linux_pin_the_vulkan_build_and_macos_its_own(committed: ServerPins) -> None:
    backends = {pin.target: pin.backend for pin in committed.archives}

    assert backends == {
        "windows-x86-64": "vulkan",
        "linux-x86-64": "vulkan",
        "linux-aarch64": "vulkan",
        "macos-arm64": "metal",
        "macos-x86-64": "cpu",
    }


def test_the_pinned_tag_is_a_numbered_build_not_a_version_tag(committed: ServerPins) -> None:
    assert committed.tag.startswith("b")
    assert committed.tag[1:].isdigit()


def test_a_missing_target_is_reported(committed: ServerPins) -> None:
    pins = committed.model_copy(update={"archives": committed.archives[1:]})

    assert any("no archive is pinned" in problem for problem in check_pins(pins, render_pins(pins)))


def test_an_undeclared_host_is_reported(committed: ServerPins) -> None:
    pins = committed.model_copy(update={"hosts": tuple(sorted((*committed.hosts, "mirror.example")))})

    assert any("undeclared hosts" in problem for problem in check_pins(pins, render_pins(pins)))


def test_another_backend_is_reported(committed: ServerPins) -> None:
    moved = committed.archives[0].model_copy(update={"backend": "cpu"})
    pins = committed.model_copy(update={"archives": (moved, *committed.archives[1:])})

    assert any("another asset" in problem for problem in check_pins(pins, render_pins(pins)))


def test_another_executable_is_reported(committed: ServerPins) -> None:
    moved = committed.archives[0].model_copy(update={"executable": "llama-server-impl"})
    pins = committed.model_copy(update={"archives": (moved, *committed.archives[1:])})

    assert any("executable other than" in problem for problem in check_pins(pins, render_pins(pins)))


def test_a_hand_edited_file_is_reported(committed: ServerPins) -> None:
    rendered = render_pins(committed).replace('"program": ', '"program":  ')

    assert any("not what the generator renders" in problem for problem in check_pins(committed, rendered))


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ('"https://github.com/ggml-org/', '"https://mirror.example/ggml-org/'),
        ("releases/download/b12184/", "releases/download/b12000/"),
        ('"tag": "b12184"', '"tag": "v0.9.0"'),
        ('"sha256": "', '"sha256": "AB'),
        ('"format": "zip"', '"format": "rar"'),
        ('"backend": "metal"', '"backend": "cuda"'),
        ('"executable": "llama-server.exe"', '"executable": "../llama-server.exe"'),
        ('"program": "llama-server"', '"program": "llama-server", "program": "llama-server"'),
        ('    "github.com",\n', '    "github.com",\n    "github.com",\n'),
        ('"download_bytes": 37709845', '"download_bytes": 0'),
    ),
)
def test_a_file_that_could_admit_other_bytes_or_sources_is_refused(old: str, new: str) -> None:
    text = PINS_PATH.read_text(encoding="utf-8")
    assert old in text

    with pytest.raises((ValidationError, ValueError)):
        load_server_pins(text.replace(old, new, 1))


def _tar(members: Mapping[str, bytes], links: Mapping[str, str] | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        for name, target in (links or {}).items():
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            archive.addfile(info)
    return buffer.getvalue()


def _zip(members: Mapping[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _listed(content: bytes) -> _Listed:
    return _Listed(url="https://github.com/x", size=len(content), sha256=hashlib.sha256(content).hexdigest())


_TAR_ASSET = ReleaseAsset("x-{tag}.tar.gz", "tar.gz", "vulkan", "llama-server")
_ZIP_ASSET = ReleaseAsset("x-{tag}.zip", "zip", "vulkan", "llama-server.exe")


def test_a_tar_archive_that_matches_its_listing_yields_its_executable_path() -> None:
    content = _tar({"b1/llama-server": b"x", "b1/libggml.so": b"y"})

    assert verify_archive(content, _listed(content), _TAR_ASSET, "x") == "b1/llama-server"


def test_a_zip_archive_that_matches_its_listing_yields_its_executable_path() -> None:
    content = _zip({"llama-server.exe": b"x", "ggml.dll": b"y"})

    assert verify_archive(content, _listed(content), _ZIP_ASSET, "x") == "llama-server.exe"


def test_an_archive_whose_digest_differs_from_its_listing_is_refused() -> None:
    content = _tar({"b1/llama-server": b"x"})
    listed = _Listed(url="https://github.com/x", size=len(content), sha256="0" * 64)

    with pytest.raises(RuntimeError, match="size and digest"):
        verify_archive(content, listed, _TAR_ASSET, "x")


def test_an_archive_whose_size_differs_from_its_listing_is_refused() -> None:
    content = _tar({"b1/llama-server": b"x"})
    listed = _Listed(url="https://github.com/x", size=len(content) + 1, sha256=hashlib.sha256(content).hexdigest())

    with pytest.raises(RuntimeError, match="size and digest"):
        verify_archive(content, listed, _TAR_ASSET, "x")


def test_an_archive_without_the_executable_is_refused() -> None:
    content = _tar({"b1/libggml.so": b"y"})

    with pytest.raises(RuntimeError, match="not one"):
        verify_archive(content, _listed(content), _TAR_ASSET, "x")


def test_an_archive_with_two_executables_is_refused() -> None:
    content = _tar({"a/llama-server": b"x", "b/llama-server": b"y"})

    with pytest.raises(RuntimeError, match="not one"):
        verify_archive(content, _listed(content), _TAR_ASSET, "x")


def test_a_link_is_not_accepted_as_the_executable() -> None:
    content = _tar({"b1/other": b"x"}, links={"b1/llama-server": "other"})

    with pytest.raises(RuntimeError, match="not one"):
        verify_archive(content, _listed(content), _TAR_ASSET, "x")


def test_a_download_that_redirects_off_the_declared_hosts_is_refused() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "github.com":
            return httpx.Response(302, headers={"Location": "https://mirror.example/a.zip"})
        return httpx.Response(200, content=b"bytes")

    with (
        httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client,
        pytest.raises(RuntimeError, match="left the declared hosts"),
    ):
        _fetch(client, "https://github.com/a.zip", declared_hosts(), set())


def test_a_download_through_the_declared_hosts_is_returned_and_its_hosts_recorded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "github.com":
            return httpx.Response(302, headers={"Location": "https://release-assets.githubusercontent.com/a.zip"})
        return httpx.Response(200, content=b"bytes")

    visited: set[str] = set()
    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        assert _fetch(client, "https://github.com/a.zip", declared_hosts(), visited) == b"bytes"

    assert visited == set(declared_hosts())


def _release(tag: str, names: list[str], *, draft: bool = False) -> dict[str, object]:
    assets = [{"name": name, "size": 1, "digest": f"sha256:{'a' * 64}"} for name in names]
    return {"tag_name": tag, "draft": draft, "prerelease": True, "assets": assets}


def _complete(tag: str) -> list[str]:
    return [asset.name(tag) for asset in TARGET_ASSETS.values()]


def test_the_newest_build_with_every_asset_is_selected() -> None:
    releases = [
        _release("b3", _complete("b3")[1:]),
        _release("v0.9.0", []),
        _release("b2", _complete("b2"), draft=True),
        _release("b1", _complete("b1")),
    ]

    tag, assets = select_release(releases)

    assert tag == "b1"
    assert set(assets) == set(_complete("b1"))


def test_a_listing_with_no_complete_build_is_refused() -> None:
    with pytest.raises(RuntimeError, match="no build tag"):
        select_release([_release("b3", _complete("b3")[1:]), _release("v0.9.0", [])])
