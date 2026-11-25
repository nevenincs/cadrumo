"""Enrolled physical mappings admit existing backends and exclude SDK native ZIP inputs."""

from __future__ import annotations

import plistlib
import struct
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

from dev.paths import REPO_ROOT

from ...runtime_wheelhouse_contract import SUPPORTED_TARGETS
from ..layout import application_images, backend, distribution_target, load_layout
from ..platforms import macos, macos_macho
from ..stdlib import bundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("target", [target.name for target in SUPPORTED_TARGETS])
def test_enrolled_layout_has_a_real_backend_and_distinct_root_images(target: str) -> None:
    layout = load_layout(target)
    assert distribution_target(layout) == target
    implementation = backend(layout)
    for operation in ("provision_sdk", "assemble_native", "resources", "verify"):
        assert callable(getattr(implementation, operation))
    directories = {path.split("/", maxsplit=1)[0] for path in layout["paths"].values() if "/" in path}
    assert all(image.file not in directories for image in application_images(layout))


def test_backend_name_cannot_import_an_unenrolled_module() -> None:
    with pytest.raises(ValueError, match="no implemented enrollment"):
        backend({"backend": "os"})


@pytest.mark.parametrize("target", [target.name for target in SUPPORTED_TARGETS if target.os_name == "posix"])
def test_posix_stdlib_zip_cannot_redistribute_sdk_extension_payloads(tmp_path: Path, target: str) -> None:
    layout = load_layout(target)
    source = tmp_path / "stdlib"
    extensions = source / "lib-dynload"
    extensions.mkdir(parents=True)
    (source / "runtime_module.py").write_text("value = 42\n", encoding="utf-8")
    (extensions / "_dbm.cpython-313.so").write_bytes(b"native SDK input requiring separate admission")
    destination = tmp_path / "python.zip"
    version = ".".join(str(part) for part in sys.version_info[:3])
    bundle(source, destination, layout["stdlib_exclude"], {}, version)
    with zipfile.ZipFile(destination) as library:
        assert "runtime_module.pyc" in library.namelist()
        assert not any(name.startswith("lib-dynload/") for name in library.namelist())


@pytest.mark.parametrize(
    "dependency,admitted",
    [
        ("/usr/lib/libbz2.1.0.dylib", True),
        ("/usr/local/lib/libbz2.1.0.dylib", False),
        ("/usr/lib/libbz2.9.dylib", False),
        ("/System/Library/Frameworks/WebKit.framework/Versions/A/WebKit", True),
        ("/System/Library/Frameworks/ApplicationServices.framework/Versions/A/ApplicationServices", True),
        ("/System/Library/Frameworks/Carbon.framework/Versions/A/Carbon", True),
        ("/System/Library/Frameworks/CoreVideo.framework/Versions/A/CoreVideo", True),
        ("/System/Library/Frameworks/QuartzCore.framework/Versions/A/QuartzCore", True),
        ("/System/Library/Frameworks/ColorSync.framework/Versions/A/ColorSync", True),
        ("/System/Library/Frameworks/CoreServices.framework/Versions/A/CoreServices", True),
        ("/usr/lib/libobjc.A.dylib", True),
        ("/usr/lib/librdma.dylib", True),
        ("/System/Library/Frameworks/Accelerate.framework/Versions/A/Accelerate", True),
        ("/System/Library/Frameworks/Metal.framework/Versions/A/Metal", True),
        ("/System/Library/Frameworks/MetalKit.framework/Versions/A/MetalKit", True),
        ("/System/Library/Frameworks/Metal.framework/Versions/B/Metal", False),
        ("/Library/Frameworks/WebKit.framework/Versions/A/WebKit", False),
        ("/System/Library/Frameworks/WebKit.framework/Versions/B/WebKit", False),
        ("/usr/local/lib/libobjc.A.dylib", False),
    ],
)
def test_macos_system_admission_requires_the_measured_install_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dependency: str, admitted: bool
) -> None:
    """Exercise the live map with a Mach-O dependency and no host signing tools."""
    encoded = dependency.encode("utf-8") + b"\0"
    length = (24 + len(encoded) + 7) & ~7
    dylib = struct.pack("<6I", 0xC, length, 24, 0, 0, 0) + encoded
    commands = struct.pack("<6I", 0x32, 24, 1, 14 << 16, 0, 0) + dylib.ljust(length, b"\0")
    image = tmp_path / "libfreetype.dylib"
    image.write_bytes(struct.pack("<8I", 0xFEEDFACF, 0x0100000C, 0, 6, 2, len(commands), 0, 0) + commands)
    layout = load_layout("macos-arm64")
    layout["native_tools"] = {"codesign": "fixture-codesign"}
    layout["native_signing_identity"] = "-"
    tool_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(macos, "command", lambda *arguments: tool_calls.append(arguments))
    if admitted:
        macos.relocate([image], tmp_path, layout)
        assert len(tool_calls) == 2
        assert macos_macho.inspect_macho(image).dependencies == (dependency,)
    else:
        with pytest.raises(ValueError, match="Unresolved Mach-O dependency"):
            macos.relocate([image], tmp_path, layout)
        assert not tool_calls


def _desktop_image(path: Path, plist: bytes | None) -> None:
    """Write a dependency-free ARM64 image that embeds ``plist`` the way the desktop link does."""
    build = struct.pack("<6I", 0x32, 24, 1, 14 << 16, 0, 0)
    sections = b""
    if plist is not None:
        sections = (
            b"__info_plist".ljust(16, b"\0")
            + b"__TEXT".ljust(16, b"\0")
            + struct.pack("<QQIIIIIIII", 0, len(plist), 0, 0, 0, 0, 0, 0, 0, 0)
        )
    segment = b"".join(
        [
            struct.pack("<2I", 0x19, 72 + len(sections)),
            b"__TEXT".ljust(16, b"\0"),
            struct.pack("<4Q", 0, 0, 0, 0),
            struct.pack("<4I", 0, 0, 1 if plist is not None else 0, 0),
            sections,
        ]
    )
    commands = build + segment
    offset = 32 + len(commands)
    if plist is not None:
        segment = segment[: 72 + 48] + struct.pack("<I", offset) + segment[72 + 52 :]
        commands = build + segment
    header = struct.pack("<8I", 0xFEEDFACF, 0x0100000C, 0, 2, 2, len(commands), 0, 0)
    path.write_bytes(header + commands + (plist or b""))


def _desktop_layout(tmp_path: Path, expected: bytes, is_desktop: bool) -> dict[str, Any]:
    layout = load_layout("macos-arm64")
    layout["native_tools"] = {"codesign": "fixture-codesign"}
    layout["native_signing_identity"] = "-"
    generated = tmp_path / "desktop-info.plist"
    generated.write_bytes(expected)
    layout["desktop_info_plist"] = str(generated)
    for declared in layout["application_images"]:
        declared["desktop"] = declared["name"] == "cadrumo" and is_desktop
    return layout


@pytest.mark.parametrize(("is_desktop", "hardened"), [(True, True), (False, False)])
def test_only_the_desktop_image_is_sealed_with_the_hardened_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, is_desktop: bool, hardened: bool
) -> None:
    """Drive the live relocation of an image declared as the desktop or not."""
    identity = b"<plist>identity</plist>"
    image = tmp_path / "cadrumo"
    _desktop_image(image, identity)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(macos, "command", lambda *arguments: calls.append(arguments))
    macos.relocate([image], tmp_path, _desktop_layout(tmp_path, identity, is_desktop))
    signing = next(call for call in calls if "--sign" in call)
    assert ("--options" in signing and "runtime" in signing) is hardened
    # The declared entitlements ride on the desktop image alone, and are the minimal set.
    assert ("--entitlements" in signing) is hardened
    if hardened:
        entitlements = Path(signing[signing.index("--entitlements") + 1])
        assert plistlib.loads(entitlements.read_bytes()) == {"com.apple.security.cs.disable-library-validation": True}


@pytest.mark.parametrize("embedded", [None, b"<plist>another</plist>"])
def test_the_desktop_image_must_embed_the_generated_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, embedded: bytes | None
) -> None:
    image = tmp_path / "cadrumo"
    _desktop_image(image, embedded)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(macos, "command", lambda *arguments: calls.append(arguments))
    layout = _desktop_layout(tmp_path, b"<plist>identity</plist>", True)
    with pytest.raises(ValueError, match="does not embed the generated identity"):
        macos.relocate([image], tmp_path, layout)
    assert not calls
    # The same image is acceptable when it is not the desktop: nothing is compared.
    macos.relocate([image], tmp_path, _desktop_layout(tmp_path, b"<plist>identity</plist>", False))


@pytest.mark.parametrize("declared", ["../escape.entitlements", "/abs/path", "has space", ".hidden", 7])
def test_image_entitlements_must_be_a_plain_relative_path(declared: object) -> None:
    layout = load_layout("macos-arm64")
    layout["application_images"][0]["entitlements"] = declared
    with pytest.raises(ValueError, match="entitlements must be a plain relative path"):
        application_images(layout)


def test_the_macos_desktop_image_declares_the_one_library_validation_entitlement() -> None:
    desktop = next(image for image in application_images(load_layout("macos-arm64")) if image.desktop)
    assert desktop.entitlements is not None
    assert plistlib.loads((REPO_ROOT / desktop.entitlements).read_bytes()) == {
        "com.apple.security.cs.disable-library-validation": True
    }
