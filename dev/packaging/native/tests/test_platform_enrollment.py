"""Enrolled physical mappings admit existing backends and exclude SDK native ZIP inputs."""

from __future__ import annotations

import struct
import sys
import zipfile
from pathlib import Path

import pytest

from ...runtime_wheelhouse_contract import SUPPORTED_TARGETS
from ..layout import application_images, backend, distribution_target, load_layout
from ..platforms import macos
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
    ],
)
def test_macos_pillow_bzip2_admission_requires_the_measured_system_install_name(
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
        assert macos.inspect(image).dependencies == (dependency,)
    else:
        with pytest.raises(ValueError, match="Unresolved Mach-O dependency"):
            macos.relocate([image], tmp_path, layout)
        assert not tool_calls
