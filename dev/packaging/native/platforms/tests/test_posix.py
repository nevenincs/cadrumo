"""Focused native-format and dependency-policy tests; these are not target execution evidence."""

from __future__ import annotations

import copy
import io
import json
import struct
import tarfile
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from dev.packaging.native import layout as native_layout
from dev.packaging.native.hashing import digest
from dev.packaging.native.platforms import linux, macos, posix
from dev.packaging.native.platforms.posix import acquire_sdk, dependencies_by_name, relative_loader_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _verifier_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, object]]:
    """Provide a target contract without substituting any executable verification."""
    declared: dict[str, object] = {
        "platform": "linux-x86-64",
        "abi": 1,
        "paths": {"executable": "python", "native": "bin"},
        "files": {"package_manifest": "manifest.json", "runtime": "libpython3.13.so.1.0"},
        "sdk": {"extension_suffix": ".cpython-313-x86_64-linux-gnu.so"},
        "native_system_libraries": ["libc.so.6"],
        "native_tools": {"patchelf": "/verification-host/tools/patchelf"},
        "native_signing_identity": "verification-host-identity",
    }
    package = tmp_path / "package"
    package.mkdir()
    monkeypatch.setattr(posix.sys, "platform", "linux")
    monkeypatch.setattr(posix.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(native_layout, "load_layout", lambda target: declared)
    return package, declared


def test_extracted_runtime_layout_does_not_require_builder_tool_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package, declared = _verifier_layout(tmp_path, monkeypatch)
    layout = copy.deepcopy(declared)
    layout["native_tools"] = {"patchelf": "/builder/tools/patchelf"}
    layout["native_signing_identity"] = "builder-identity"
    (package / "manifest.json").write_text(json.dumps({"layout": layout}), encoding="utf-8")

    def reached_relocation(source: Path, destination: Path) -> None:
        assert source == package
        raise RuntimeError("layout admitted; target execution intentionally unavailable")

    monkeypatch.setattr(posix.shutil, "copytree", reached_relocation)
    with pytest.raises(RuntimeError, match="layout admitted"):
        posix.verify_package(package, tmp_path / "verification", "linux")


@pytest.mark.parametrize(
    "field,value",
    [
        ("platform", "linux-aarch64"),
        ("abi", 2),
        ("paths", {"executable": "ambient-python", "native": "host-bin"}),
        ("files", {"package_manifest": "manifest.json", "runtime": "libpython3.14.so.1.0"}),
        ("sdk", {"extension_suffix": ".cpython-314-x86_64-linux-gnu.so"}),
        ("native_system_libraries", ["unreviewed.so"]),
        ("unexpected_runtime_policy", True),
    ],
)
def test_extracted_layout_keeps_all_runtime_identity_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    package, declared = _verifier_layout(tmp_path, monkeypatch)
    layout = copy.deepcopy(declared)
    layout[field] = value
    (package / "manifest.json").write_text(json.dumps({"layout": layout}), encoding="utf-8")
    with pytest.raises(ValueError, match="Artifact layout differs"):
        posix.verify_package(package, tmp_path / "verification", "linux")
    assert not (tmp_path / "verification").exists()


def _macho(path: Path, *, cpu: int = 0x0100000C, subtype: int = 0, minimum: int = 14 << 16) -> Path:
    header = struct.pack("<8I", 0xFEEDFACF, cpu, subtype, 6, 1, 24, 0, 0)
    path.write_bytes(header + struct.pack("<6I", 0x32, 24, 1, minimum, 0, 0))
    return path


def test_macho_requires_arm64_and_explicit_deployment_floor(tmp_path: Path) -> None:
    image = _macho(tmp_path / "image")
    assert macos.inspect(image).minimum == (14, 0, 0)
    _macho(image, cpu=0x01000007)
    with pytest.raises(ValueError, match="ARM64"):
        macos.inspect(image)
    image.write_bytes(struct.pack("<8I", 0xFEEDFACF, 0x0100000C, 0, 6, 0, 0, 0, 0))
    with pytest.raises(ValueError, match="deployment floor"):
        macos.inspect(image)


@pytest.mark.parametrize("subtype", [1, 2, 0x80000002, 0x81000002, 0xFFFFFFFF])
def test_macho_generic_arm64_refuses_other_cpu_subtypes_before_tools(tmp_path: Path, subtype: int) -> None:
    image = _macho(tmp_path / "specialized", subtype=subtype)
    contract = {
        "platform": "macos-arm64",
        "native_tools": {},
        "native_signing_identity": "-",
        "native_system_libraries": [],
    }
    with pytest.raises(ValueError, match="ARM64 CPU subtype"):
        macos.relocate([image], tmp_path, contract)


@pytest.mark.parametrize("wide", [False, True])
@pytest.mark.parametrize("subtype", [2, 0x80000002, 0x81000002])
def test_universal_arm64e_refuses_before_thinning(tmp_path: Path, wide: bool, subtype: int) -> None:
    arm64e = _macho(tmp_path / "arm64e", subtype=subtype).read_bytes()
    table = struct.pack(">II", 0xCAFEBABF if wide else 0xCAFEBABE, 1)
    entry = struct.pack(">" + ("IIQQII" if wide else "IIIII"), 0x0100000C, subtype, 64, 56, 6, *([0] if wide else []))
    data = table + entry + bytes(64 - len(table + entry)) + arm64e
    image = tmp_path / "universal-arm64e.so"
    image.write_bytes(data)
    with pytest.raises(ValueError, match="ARM64 CPU subtype"):
        macos._select_arm64(image)
    assert image.read_bytes() == data


@pytest.mark.parametrize("endian,wide", [(">", False), ("<", False), (">", True), ("<", True)])
def test_universal_macho_selects_only_the_declared_arm64_slice(tmp_path: Path, endian: str, wide: bool) -> None:
    arm64 = _macho(tmp_path / "arm64").read_bytes()
    x86 = _macho(tmp_path / "x86", cpu=0x01000007).read_bytes()
    header = struct.pack(endian + "II", 0xCAFEBABF if wide else 0xCAFEBABE, 2)
    entries = b"".join(
        struct.pack(endian + ("IIQQII" if wide else "IIIII"), cpu, 0, start, 56, 7, *([0] if wide else []))
        for cpu, start in ((0x01000007, 128), (0x0100000C, 256))
    )
    data = bytearray(312)
    data[: len(header + entries)] = header + entries
    data[128:184], data[256:312] = x86, arm64
    universal = tmp_path / "universal.so"
    universal.write_bytes(data)
    macos._select_arm64(universal)
    assert universal.read_bytes() == arm64
    assert macos.inspect(universal).minimum == (14, 0, 0)


@pytest.mark.parametrize(
    "start,size,cpu", [(0, 56, 0x0100000C), (64, 1000, 0x0100000C), (64, 56, 0x01000007), (64, 56, 0x12345678)]
)
def test_universal_macho_invalid_target_or_bounds_refuse_without_mutation(
    tmp_path: Path, start: int, size: int, cpu: int
) -> None:
    selected = _macho(tmp_path / "selected", cpu=cpu).read_bytes()
    data = bytearray(120)
    data[:28] = struct.pack(">7I", 0xCAFEBABE, 1, cpu, 0, start, size, 6)
    data[64:120] = selected
    image = tmp_path / "invalid-universal.so"
    image.write_bytes(data)
    with pytest.raises(ValueError, match=r"universal|Universal"):
        macos._select_arm64(image)
    assert image.read_bytes() == data


@pytest.mark.parametrize("length", [0, 8, 16, 31, 33, 40, 55])
def test_macho_truncation_is_refused(tmp_path: Path, length: int) -> None:
    image = _macho(tmp_path / "truncated")
    image.write_bytes(image.read_bytes()[:length])
    with pytest.raises(ValueError):
        macos.inspect(image)


def test_macho_newer_deployment_refused_before_native_tools(tmp_path: Path) -> None:
    image = _macho(tmp_path / "newer", minimum=15 << 16)
    contract = {
        "platform": "macos-arm64",
        "native_tools": {},
        "native_signing_identity": "-",
        "native_system_libraries": [],
    }
    with pytest.raises(ValueError, match="deployment floor"):
        macos.relocate([image], tmp_path, contract)


def test_conflicting_native_basenames_are_refused(tmp_path: Path) -> None:
    first = tmp_path / "first/libdependency.so"
    second = tmp_path / "second/libdependency.so"
    for path, content in ((first, b"one"), (second, b"two")):
        path.parent.mkdir()
        path.write_bytes(content)
    with pytest.raises(ValueError, match="Ambiguous"):
        dependencies_by_name([first, second])


def test_loader_path_is_relative_to_each_requesting_object(tmp_path: Path) -> None:
    assert relative_loader_path(tmp_path / "bin/pkg", tmp_path / "bin/libs/a.so", "$ORIGIN") == "$ORIGIN/../libs/a.so"


def test_sdk_acquisition_requires_provenance_before_network_or_filesystem_effects(tmp_path: Path) -> None:
    destination = tmp_path / "uncreated"
    with pytest.raises(ValueError, match="provenance"):
        acquire_sdk(destination, "3.13.11", {}, {"platform": "linux-x86-64"})
    assert not destination.exists()


def _sdk_archive(destination: Path) -> dict[str, object]:
    archive = destination / "cpython-sdk.tar"
    content = b'#define PY_VERSION "3.13.11"\n'
    with tarfile.open(archive, "w") as target:
        member = tarfile.TarInfo("python/include/patchlevel.h")
        member.size = len(content)
        target.addfile(member, io.BytesIO(content))
    return {
        "cpython_source": "https://github.com/astral-sh/python-build-standalone/releases/download/fixture/cpython.tar",
        "cpython_sha256": digest(archive),
        "cpython_provenance": {
            "version": "3.13.11",
            "target": "linux-x86-64",
            "abi": "cp313",
            "provider": "test fixture",
            "release": "fixture",
            "license": "fixture",
            "compatibility_evidence": "fixture",
        },
    }


def test_sdk_result_is_the_declared_destination_after_archive_root_move(tmp_path: Path) -> None:
    selected = acquire_sdk(
        tmp_path,
        "3.13.11",
        _sdk_archive(tmp_path),
        {"platform": "linux-x86-64", "sdk": {"archive_root": "python", "root": "selected/python"}},
    )
    assert selected == tmp_path / "selected/python"
    assert (selected / "include/patchlevel.h").is_file()
    assert not (tmp_path / "sdk-extraction/python").exists()
    assert (tmp_path / "sdk-provenance.json").is_file()


@pytest.mark.parametrize("selected", ["sdk-extraction", "sdk-extraction/python", "sdk-extraction/python/nested"])
def test_sdk_move_rejects_overlapping_archive_and_destination_roots(tmp_path: Path, selected: str) -> None:
    with pytest.raises(ValueError, match="must not overlap"):
        acquire_sdk(
            tmp_path,
            "3.13.11",
            _sdk_archive(tmp_path),
            {"platform": "linux-x86-64", "sdk": {"archive_root": "python", "root": selected}},
        )
    assert (tmp_path / "sdk-extraction/python/include/patchlevel.h").is_file()
    assert not (tmp_path / "sdk-provenance.json").exists()


def test_sdk_download_follows_only_bounded_github_https_asset_redirects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = _sdk_archive(tmp_path)
    archive = tmp_path / "cpython-sdk.tar"
    content = archive.read_bytes()
    archive.unlink()
    seen = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        if request.url.host == "github.com":
            return httpx.Response(
                302, headers={"location": "https://release-assets.githubusercontent.com/sdk?signature=fixture"}
            )
        return httpx.Response(200, content=content)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(posix.httpx, "stream", client.stream)
        selected = acquire_sdk(
            tmp_path, "3.13.11", tools, {"platform": "linux-x86-64", "sdk": {"archive_root": "python", "root": "sdk"}}
        )
    assert seen == ["github.com", "release-assets.githubusercontent.com"]
    assert (selected / "include/patchlevel.h").is_file()
    assert not archive.with_name(archive.name + ".partial").exists()


@pytest.mark.parametrize(
    "location",
    [
        "http://release-assets.githubusercontent.com/sdk",
        "https://foreign.invalid/sdk",
        "https://github.com:444/sdk",
        "https://user:secret@github.com/sdk",
    ],
)
def test_sdk_download_rejects_redirect_before_contacting_unadmitted_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, location: str
) -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request.url)
        return httpx.Response(302, headers={"location": location})

    archive = tmp_path / "sdk.tar"
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(posix.httpx, "stream", client.stream)
        with pytest.raises(ValueError, match="admitted HTTPS"):
            posix._download_sdk(
                "https://github.com/astral-sh/python-build-standalone/releases/download/fixture/sdk", archive
            )
    assert len(requests) == 1
    assert not archive.exists()


def test_sdk_redirect_loop_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request.url)
        return httpx.Response(307, headers={"location": str(request.url)})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(posix.httpx, "stream", client.stream)
        with pytest.raises(ValueError, match="redirect limit"):
            posix._download_sdk(
                "https://github.com/astral-sh/python-build-standalone/releases/download/fixture/sdk",
                tmp_path / "sdk.tar",
            )
    assert len(requests) == 4


def test_failed_download_preserves_an_existing_partial_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "sdk.tar"
    partial = tmp_path / "sdk.tar.partial"
    partial.write_bytes(b"existing owner data")
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"new"))) as client:
        monkeypatch.setattr(posix.httpx, "stream", client.stream)
        with pytest.raises(FileExistsError):
            posix._download_sdk(
                "https://github.com/astral-sh/python-build-standalone/releases/download/fixture/sdk", archive
            )
    assert partial.read_bytes() == b"existing owner data"
    assert not archive.exists()


def test_sdk_download_size_limit_removes_only_its_partial_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "sdk.tar"
    monkeypatch.setattr(posix, "_SDK_DOWNLOAD_LIMIT", 3)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"four"))) as client:
        monkeypatch.setattr(posix.httpx, "stream", client.stream)
        with pytest.raises(ValueError, match="size limit"):
            posix._download_sdk(
                "https://github.com/astral-sh/python-build-standalone/releases/download/fixture/sdk", archive
            )
    assert not archive.exists()
    assert not (tmp_path / "sdk.tar.partial").exists()


@pytest.mark.parametrize(
    "decoder",
    [
        None,
        {"executable": "zstd"},
        {
            "executable": "zstd",
            "sha256": "0" * 64,
            "provenance": {
                "provider": "fixture",
                "release": "fixture",
                "source": "https://fixture.invalid/decoder.tar.gz",
                "source_sha256": "0" * 64,
            },
        },
    ],
)
def test_zstd_sdk_requires_explicit_pinned_decoder_before_acquisition(tmp_path: Path, decoder: object) -> None:
    tools = _sdk_archive(tmp_path)
    tools.update(cpython_archive_format="tar.zst", cpython_archive_decoder=decoder)
    destination = tmp_path / "uncreated"
    with pytest.raises(ValueError, match="decoder"):
        acquire_sdk(destination, "3.13.11", tools, {"platform": "linux-x86-64"})
    assert not destination.exists()


def test_zstd_sdk_decoder_pin_is_checked_and_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tools = _sdk_archive(tmp_path)
    decoder = tmp_path / "zstd"
    decoder.write_bytes(b"explicit decoder fixture")
    declaration = {
        "executable": str(decoder),
        "sha256": digest(decoder),
        "provenance": {
            "provider": "fixture",
            "release": "fixture",
            "source": "https://fixture.invalid/decoder.tar.gz",
            "source_sha256": "0" * 64,
        },
    }
    tools.update(cpython_archive_format="tar.zst", cpython_archive_decoder=declaration)
    called = []

    def decode(tool: str, *arguments: str) -> str:
        called.append((tool, arguments))
        assert arguments[:3] == ("--decompress", "--no-progress", "-o")
        Path(arguments[3]).write_bytes(Path(arguments[-1]).read_bytes())
        return ""

    monkeypatch.setattr(posix, "command", decode)
    contract = {"platform": "linux-x86-64", "sdk": {"archive_root": "python", "root": "sdk"}}
    selected = acquire_sdk(tmp_path, "3.13.11", tools, contract)
    assert (selected / "include/patchlevel.h").is_file()
    assert len(called) == 1
    provenance = json.loads((tmp_path / "sdk-provenance.json").read_text())
    assert provenance["archive_decoder"] == declaration
    decoder.write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash-pinned"):
        acquire_sdk(tmp_path / "changed", "3.13.11", tools, contract)
    assert not (tmp_path / "changed").exists()


def test_sdk_extensions_follow_declared_exclusions_with_recorded_reasons(tmp_path: Path) -> None:
    sdk = tmp_path / "sdk"
    root = tmp_path / "package"
    native = root / "native"
    packages = root / "packages"
    for directory in (sdk / "extensions", native, packages):
        directory.mkdir(parents=True)
    _elf(sdk / "runtime.so")
    suffix = ".cpython-313-x86_64-linux-gnu.so"
    for name in ("_tkinter", "_ctypes_test", "_dbm", "_sqlite3"):
        _elf(sdk / "extensions" / (name + suffix))
    contract = {
        "sdk": {
            "native_files": ["runtime.so"],
            "extensions": "extensions",
            "extension_suffix": suffix,
            "extension_exclusions": [
                {"pattern": name + ".*.so", "reason": name + " excluded"}
                for name in ("_tkinter", "_ctypes_test", "_dbm")
            ],
        }
    }
    result = posix.assemble(sdk, packages, native, root, contract, lambda *_: None)
    assert result["modules"] == {"_sqlite3": "native/_sqlite3" + suffix}
    assert {path.name for path in native.iterdir()} == {"runtime.so", "_sqlite3" + suffix}
    assert {entry["reasons"][0] for entry in result["sdk_extension_exclusions"]} == {
        name + " excluded" for name in ("_tkinter", "_ctypes_test", "_dbm")
    }
    assert all(entry["sha256"] == digest(sdk / entry["file"]) for entry in result["sdk_extension_exclusions"])


@pytest.mark.parametrize(
    "source,source_hash",
    [
        ("https://fixture.invalid/source", "not a sha256"),
        ("http://fixture.invalid/source", "0" * 64),
        ("https://secret:token@fixture.invalid/source", "0" * 64),
    ],
)
def test_sdk_decoder_rejects_invalid_source_provenance(tmp_path: Path, source: str, source_hash: str) -> None:
    decoder = tmp_path / "zstd"
    decoder.write_bytes(b"decoder fixture")
    with pytest.raises(ValueError, match="decoder"):
        posix._archive_decoder(
            {
                "cpython_archive_decoder": {
                    "executable": str(decoder),
                    "sha256": digest(decoder),
                    "provenance": {
                        "provider": "fixture",
                        "release": "fixture",
                        "source": source,
                        "source_sha256": source_hash,
                    },
                }
            }
        )


@pytest.mark.parametrize("probe_factory", [linux.external_probe, macos.external_probe])
def test_external_probe_is_fresh_executable_outside_the_package(
    tmp_path: Path, probe_factory: Callable[[Path], list[str]]
) -> None:
    arguments = probe_factory(tmp_path)
    assert arguments == ["cadrumo-override-probe"]
    probe = tmp_path / arguments[0]
    assert probe.read_bytes() == b"#!/bin/sh\nexit 0\n"
    with pytest.raises(FileExistsError):
        probe_factory(tmp_path)


def _elf(path: Path, machine: int = 62) -> Path:
    data = bytearray(64)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", data, 18, machine)
    path.write_bytes(data)
    return path


def test_elf_wrong_machine_is_refused_before_tools(tmp_path: Path) -> None:
    image = _elf(tmp_path / "wrong.so", 183)
    with pytest.raises(ValueError, match="architecture"):
        linux.relocate(
            [image], tmp_path, {"platform": "linux-x86-64", "native_tools": {}, "native_system_libraries": []}
        )


def test_elf_dependency_search_is_assigned_to_every_requesting_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "libs").mkdir()
    (tmp_path / "vendor").mkdir()
    application = _elf(tmp_path / "app")
    library = _elf(tmp_path / "libs/dependency.so")
    nested = _elf(tmp_path / "vendor/nested.so")
    needed = {str(application): "dependency.so", str(library): "nested.so", str(nested): "libc.so.6"}
    written: dict[str, str] = {}

    def native_tool(tool: str, *arguments: str) -> str:
        operation, path = arguments[0], arguments[-1]
        if operation == "--version-info":
            return "GLIBC_2.28"
        if operation == "--print-needed":
            return needed[path]
        if operation == "--set-rpath":
            written[path] = arguments[1]
            return ""
        if operation == "--remove-rpath":
            written[path] = ""
            return ""
        assert operation == "--print-rpath"
        return written[path]

    monkeypatch.setattr(linux, "command", native_tool)
    linux.relocate(
        [application, library, nested],
        tmp_path,
        {
            "platform": "linux-x86-64",
            "native_tools": {"readelf": "readelf", "patchelf": "patchelf"},
            "native_system_libraries": ["libc.so.6"],
        },
    )
    assert written == {str(application): "$ORIGIN/libs", str(library): "$ORIGIN/../vendor", str(nested): ""}


@pytest.mark.parametrize(
    "versions,needed,reason",
    [
        ("GLIBC_2.29", "", "glibc floor"),
        ("GLIBC_PRIVATE", "", "unadmitted glibc ABI"),
        ("GLIBC_ABI_DT_RELR", "", "unadmitted glibc ABI"),
        ("GLIBC_2.28", "missing.so", "Unresolved ELF"),
        ("GLIBC_2.28", "/host/libdependency.so", "Unresolved ELF"),
    ],
)
def test_elf_floor_and_missing_dependency_refusals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    versions: str,
    needed: str,
    reason: str,
) -> None:
    image = _elf(tmp_path / "image.so")

    def read_tool(tool: str, *arguments: str) -> str:
        assert arguments[0] in {"--version-info", "--print-needed"}, "must refuse before mutation"
        return versions if arguments[0] == "--version-info" else needed

    monkeypatch.setattr(linux, "command", read_tool)
    with pytest.raises(ValueError, match=reason):
        linux.relocate(
            [image],
            tmp_path,
            {
                "platform": "linux-x86-64",
                "native_tools": {"readelf": "readelf", "patchelf": "patchelf"},
                "native_system_libraries": [],
            },
        )
