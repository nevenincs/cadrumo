"""The pinned llama-server archive is verified, reduced to its program and staged, or refused."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import zipfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from dev.env.llamacpp_pins import LicensePin, ServerArchivePin, ServerPins, load_server_pins

from ..llama_server import (
    ARCHIVE_DIRECTORY,
    LICENSE_DIRECTORY,
    LICENSE_NAME,
    PROGRAM_DIRECTORY,
    RECEIPT_NAME,
    ArchiveMismatchError,
    GlibcFloorError,
    LlamaServerError,
    UnresolvedImportError,
    acquire_llama_server,
    fetch_pinned,
    pin_for_target,
    require_resolved_imports,
    stage_llama_server,
    verify_acquired,
)
from ..platforms import posix_assembly
from .binary_fixtures import elf_with_requirements, macho_image, pe_with_imports

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LAYOUT = {"llama_server": "bin/llama", "docs": "docs"}
_TAG = "b1"
_LICENSE_TEXT = b"MIT License\n\nCopyright (c) the ggml authors (test)\n"


def _pins(target: str, archive_format: str, executable: str, content: bytes) -> ServerPins:
    suffix = "zip" if archive_format == "zip" else "tar.gz"
    document = {
        "program": "llama-server",
        "repository": "ggml-org/llama.cpp",
        "tag": _TAG,
        "hosts": ["github.com", "raw.githubusercontent.com"],
        "archives": [
            {
                "target": target,
                "url": f"https://github.com/ggml-org/llama.cpp/releases/download/{_TAG}/llama-{_TAG}-test.{suffix}",
                "format": archive_format,
                "backend": "vulkan",
                "executable": executable,
                "download_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        ],
        "license": {
            "url": f"https://raw.githubusercontent.com/ggml-org/llama.cpp/{_TAG}/LICENSE",
            "download_bytes": len(_LICENSE_TEXT),
            "sha256": hashlib.sha256(_LICENSE_TEXT).hexdigest(),
        },
    }
    return load_server_pins(json.dumps(document))


def _serving(archive: bytes, notice: bytes = _LICENSE_TEXT) -> Callable[[object, tuple[str, ...]], bytes]:
    """A fetch that answers the pinned licence with ``notice`` and the archive with ``archive``."""

    def fetch(pin: object, _hosts: tuple[str, ...]) -> bytes:
        return notice if isinstance(pin, LicensePin) else archive

    return fetch


def _zip(members: Mapping[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return stream.getvalue()


def _tar(members: Mapping[str, bytes], links: Mapping[str, str] | None = None, *, root: str = "llama-b1") -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        directory = tarfile.TarInfo(root)
        directory.type = tarfile.DIRTYPE
        directory.mode = 0o755
        archive.addfile(directory)
        for name, content in members.items():
            info = tarfile.TarInfo(f"{root}/{name}")
            info.size = len(content)
            info.mode = 0o755
            archive.addfile(info, io.BytesIO(content))
        for name, target in (links or {}).items():
            link = tarfile.TarInfo(f"{root}/{name}")
            link.type = tarfile.SYMTYPE
            link.linkname = target
            link.mode = 0o777
            archive.addfile(link)
    return stream.getvalue()


def _windows_archive(tmp_path: Path) -> bytes:
    images = tmp_path / "windows-images"
    images.mkdir()
    pe_with_imports(images / "llama-server.exe", "llama-server-impl.dll", "KERNEL32.dll")
    pe_with_imports(images / "llama-server-impl.dll", "ggml-base.dll", "VCRUNTIME140.dll")
    pe_with_imports(images / "ggml-base.dll")
    pe_with_imports(images / "ggml-cpu-x64.dll", "ggml-base.dll", "libomp.dll")
    pe_with_imports(images / "libomp.dll")
    pe_with_imports(images / "llama-cli.exe", "llama-cli-impl.dll")
    pe_with_imports(images / "llama-cli-impl.dll", "ggml-base.dll")
    (images / "LICENSE-LLVM-OpenMP").write_text("notice", encoding="utf-8")
    return _zip({path.name: path.read_bytes() for path in sorted(images.iterdir())})


def _linux_archive(tmp_path: Path, *, glibc: tuple[str, ...] = ("2.17",), notice: bytes = _LICENSE_TEXT) -> bytes:
    images = tmp_path / "linux-images"
    images.mkdir()
    elf_with_requirements(images / "llama-server", needed=("libllama.so.0", "libc.so.6"), glibc=glibc)
    elf_with_requirements(images / "libllama.so.0.1.0", needed=("libggml-base.so.0", "libvulkan.so.1"), glibc=glibc)
    elf_with_requirements(images / "libggml-base.so.0.1.0", needed=("libc.so.6",), glibc=glibc)
    elf_with_requirements(images / "libggml-cpu-x64.so", needed=("libggml-base.so.0",), glibc=glibc)
    elf_with_requirements(images / "llama-cli", needed=("libllama-cli-impl.so",), glibc=glibc)
    members = {path.name: path.read_bytes() for path in sorted(images.iterdir())}
    members["LICENSE"] = notice
    links = {
        "libllama.so.0": "libllama.so.0.1.0",
        "libllama.so": "libllama.so.0",
        "libggml-base.so.0": "libggml-base.so.0.1.0",
        "libggml-base.so": "libggml-base.so.0",
    }
    return _tar(members, links)


def _macos_archive(tmp_path: Path, *, executable_needs: tuple[str, ...] | None = None) -> bytes:
    images = tmp_path / "macos-images"
    images.mkdir()
    needs = executable_needs or ("@rpath/libllama.0.dylib", "/usr/lib/libSystem.B.dylib")
    macho_image(images / "llama-server", dependencies=needs)
    macho_image(
        images / "libllama.0.1.0.dylib",
        dependencies=("@rpath/libggml-base.0.dylib", "/usr/lib/libc++.1.dylib"),
        identity="@rpath/libllama.0.dylib",
    )
    macho_image(images / "libggml-base.0.1.0.dylib", identity="@rpath/libggml-base.0.dylib")
    macho_image(images / "libggml-cpu.0.1.0.dylib", dependencies=("@rpath/libggml-base.0.dylib",))
    macho_image(images / "llama-cli", dependencies=("@rpath/libggml-cpu.0.dylib",))
    members = {path.name: path.read_bytes() for path in sorted(images.iterdir())}
    members["LICENSE"] = _LICENSE_TEXT
    links = {
        "libllama.0.dylib": "libllama.0.1.0.dylib",
        "libggml-base.0.dylib": "libggml-base.0.1.0.dylib",
        "libggml-cpu.0.dylib": "libggml-cpu.0.1.0.dylib",
    }
    return _tar(members, links)


def _acquire(tmp_path: Path, target: str, archive_format: str, executable: str, content: bytes) -> Path:
    pins = _pins(target, archive_format, executable, content)
    return acquire_llama_server(tmp_path / "acquired", target, pins=pins, fetch=_serving(content))


def _receipt(tree: Path) -> dict[str, Any]:
    return json.loads((tree / RECEIPT_NAME).read_text(encoding="utf-8"))


def test_a_windows_archive_keeps_the_launcher_its_libraries_and_the_backends_beside_it(tmp_path: Path) -> None:
    content = _windows_archive(tmp_path)

    tree = _acquire(tmp_path, "windows-x86-64", "zip", "llama-server.exe", content)

    receipt = _receipt(tree)
    assert sorted(receipt["files"]) == [
        "ggml-base.dll",
        "ggml-cpu-x64.dll",
        "libomp.dll",
        "llama-server-impl.dll",
        "llama-server.exe",
    ]
    assert sorted(receipt["licenses"]) == [LICENSE_NAME, "LICENSE-LLVM-OpenMP"]
    assert receipt["host_libraries"] == ["kernel32.dll", "vcruntime140.dll"]
    assert not (tree / "extraction").exists()
    assert (tree / ARCHIVE_DIRECTORY / "llama-b1-test.zip").read_bytes() == content


def test_a_linux_archive_keeps_each_library_under_the_name_a_loader_asks_for_as_a_regular_file(tmp_path: Path) -> None:
    content = _linux_archive(tmp_path)

    tree = _acquire(tmp_path, "linux-x86-64", "tar.gz", "llama-b1/llama-server", content)

    program = tree / PROGRAM_DIRECTORY
    assert sorted(path.name for path in program.iterdir()) == [
        "libggml-base.so.0",
        "libggml-cpu-x64.so",
        "libllama.so.0",
        "llama-server",
    ]
    assert all(not path.is_symlink() for path in program.iterdir())
    images = tmp_path / "linux-images"
    assert (program / "libllama.so.0").read_bytes() == (images / "libllama.so.0.1.0").read_bytes()
    assert (program / "libggml-base.so.0").read_bytes() == (images / "libggml-base.so.0.1.0").read_bytes()
    assert sorted(path.name for path in (tree / LICENSE_DIRECTORY).iterdir()) == ["LICENSE"]
    assert _receipt(tree)["host_libraries"] == ["libc.so.6", "libvulkan.so.1"]


def test_a_macos_archive_keeps_only_what_the_launcher_links(tmp_path: Path) -> None:
    content = _macos_archive(tmp_path)

    tree = _acquire(tmp_path, "macos-arm64", "tar.gz", "llama-b1/llama-server", content)

    assert sorted(_receipt(tree)["files"]) == ["libggml-base.0.dylib", "libllama.0.dylib", "llama-server"]
    assert _receipt(tree)["host_libraries"] == ["/usr/lib/libSystem.B.dylib", "/usr/lib/libc++.1.dylib"]


def test_a_macos_launcher_that_links_a_library_the_archive_lacks_is_refused(tmp_path: Path) -> None:
    content = _macos_archive(tmp_path, executable_needs=("@rpath/libmissing.0.dylib",))
    pins = _pins("macos-arm64", "tar.gz", "llama-b1/llama-server", content)

    with pytest.raises(ArchiveMismatchError, match=r"libmissing\.0\.dylib, which the archive does not hold"):
        acquire_llama_server(tmp_path / "acquired", "macos-arm64", pins=pins, fetch=_serving(content))


def test_bytes_that_differ_from_the_pin_are_refused_and_never_cached(tmp_path: Path) -> None:
    pinned = _windows_archive(tmp_path)
    pins = _pins("windows-x86-64", "zip", "llama-server.exe", pinned)
    tampered = pinned[:-1] + bytes([pinned[-1] ^ 1])

    with pytest.raises(ArchiveMismatchError, match="does not match its pin"):
        acquire_llama_server(tmp_path / "acquired", "windows-x86-64", pins=pins, fetch=_serving(tampered))

    assert not list((tmp_path / "acquired" / ARCHIVE_DIRECTORY).glob("*"))
    assert not (tmp_path / "acquired" / PROGRAM_DIRECTORY).exists()
    assert not (tmp_path / "acquired" / RECEIPT_NAME).exists()


def test_a_wrong_size_alone_is_refused(tmp_path: Path) -> None:
    pinned = _windows_archive(tmp_path)
    pins = _pins("windows-x86-64", "zip", "llama-server.exe", pinned)

    with pytest.raises(ArchiveMismatchError, match=f"got {len(pinned) + 1} bytes"):
        acquire_llama_server(tmp_path / "acquired", "windows-x86-64", pins=pins, fetch=_serving(pinned + b"\0"))


def test_a_verified_archive_is_kept_and_a_damaged_one_is_fetched_again(tmp_path: Path) -> None:
    content = _windows_archive(tmp_path)
    pins = _pins("windows-x86-64", "zip", "llama-server.exe", content)
    fetched: list[str] = []

    def fetch(pin: ServerArchivePin | LicensePin, _hosts: tuple[str, ...]) -> bytes:
        if isinstance(pin, LicensePin):
            fetched.append("licence")
            return _LICENSE_TEXT
        fetched.append(pin.target)
        return content

    destination = tmp_path / "acquired"
    acquire_llama_server(destination, "windows-x86-64", pins=pins, fetch=fetch)
    acquire_llama_server(destination, "windows-x86-64", pins=pins, fetch=fetch)
    assert fetched == ["windows-x86-64", "licence"]

    (destination / ARCHIVE_DIRECTORY / "llama-b1-test.zip").write_bytes(b"damaged")
    acquire_llama_server(destination, "windows-x86-64", pins=pins, fetch=fetch)
    assert fetched == ["windows-x86-64", "licence", "windows-x86-64"]
    assert (destination / ARCHIVE_DIRECTORY / "llama-b1-test.zip").read_bytes() == content


def test_a_linux_archive_built_for_a_newer_glibc_than_the_floor_is_refused_before_anything_is_staged(
    tmp_path: Path,
) -> None:
    content = _linux_archive(tmp_path, glibc=("2.17", "2.34"))
    pins = _pins("linux-x86-64", "tar.gz", "llama-b1/llama-server", content)

    with pytest.raises(GlibcFloorError, match=r"glibc 2\.34 and the linux-x86-64 floor is glibc 2\.28") as refused:
        acquire_llama_server(tmp_path / "acquired", "linux-x86-64", pins=pins, fetch=_serving(content))

    assert "llama-server (glibc 2.34)" in str(refused.value)
    assert "Nothing is staged" in str(refused.value)
    assert not (tmp_path / "acquired" / PROGRAM_DIRECTORY).exists()
    assert not (tmp_path / "acquired" / RECEIPT_NAME).exists()


def test_a_linux_archive_at_the_floor_is_admitted(tmp_path: Path) -> None:
    content = _linux_archive(tmp_path, glibc=("2.17", "2.28"))

    tree = _acquire(tmp_path, "linux-aarch64", "tar.gz", "llama-b1/llama-server", content)

    assert (tree / PROGRAM_DIRECTORY / "llama-server").is_file()


@pytest.mark.parametrize(
    ("members", "links", "message"),
    [
        ({"../escape": b"x", "llama-server": b"x"}, {}, "unsafe member name"),
        ({"nested/llama-server": b"x"}, {}, "outside its program directory"),
        ({"llama-server": b"x"}, {"libloop.so": "../outside"}, "beyond its directory"),
        ({"llama-server": b"x"}, {"libloop.so": "libmissing.so"}, "names no file"),
        ({"llama-server": b"x"}, {"liba.so": "libb.so", "libb.so": "liba.so"}, "does not end in a file"),
    ],
)
def test_an_archive_that_could_write_or_link_outside_its_directory_is_refused(
    tmp_path: Path, members: dict[str, bytes], links: dict[str, str], message: str
) -> None:
    content = _tar(members, links)
    pins = _pins("macos-arm64", "tar.gz", "llama-b1/llama-server", content)

    with pytest.raises(ArchiveMismatchError, match=message):
        acquire_llama_server(tmp_path / "acquired", "macos-arm64", pins=pins, fetch=_serving(content))


def test_a_download_is_refused_unless_every_host_is_pinned(tmp_path: Path) -> None:
    content = _windows_archive(tmp_path)
    pin = pin_for_target(_pins("windows-x86-64", "zip", "llama-server.exe", content), "windows-x86-64")

    with pytest.raises(ArchiveMismatchError, match=r"leaves the pinned HTTPS hosts at github\.com"):
        fetch_pinned(pin, ())


def test_a_target_without_a_pin_is_refused() -> None:
    with pytest.raises(LlamaServerError, match="no llama-server archive is pinned for plan9-mips"):
        pin_for_target(load_server_pins(), "plan9-mips")


@pytest.mark.parametrize("target", ["windows-x86-64", "linux-x86-64", "linux-aarch64", "macos-arm64"])
def test_every_enrolled_native_target_has_a_committed_pin(target: str) -> None:
    pin = pin_for_target(load_server_pins(), target)

    assert pin.target == target
    assert pin.download_bytes > 0


def test_an_acquired_tree_is_staged_with_its_licence_and_the_package_holds_no_link(tmp_path: Path) -> None:
    content = _linux_archive(tmp_path)
    pins = _pins("linux-x86-64", "tar.gz", "llama-b1/llama-server", content)
    tree = acquire_llama_server(tmp_path / "acquired", "linux-x86-64", pins=pins, fetch=_serving(content))
    root = tmp_path / "package"

    receipt = stage_llama_server(tree, root, _LAYOUT, "linux-x86-64", pins=pins)

    assert sorted(path.name for path in (root / "bin/llama").iterdir()) == sorted(receipt.files)
    assert (root / "docs/licenses/llama.cpp/LICENSE").read_bytes() == _LICENSE_TEXT
    assert not [path for path in root.rglob("*") if path.is_symlink()]


def test_staging_refuses_a_file_that_differs_from_the_receipt(tmp_path: Path) -> None:
    content = _linux_archive(tmp_path)
    pins = _pins("linux-x86-64", "tar.gz", "llama-b1/llama-server", content)
    tree = acquire_llama_server(tmp_path / "acquired", "linux-x86-64", pins=pins, fetch=_serving(content))
    (tree / PROGRAM_DIRECTORY / "libllama.so.0").write_bytes(b"replaced")

    with pytest.raises(ArchiveMismatchError, match="differ from the receipt"):
        stage_llama_server(tree, tmp_path / "package", _LAYOUT, "linux-x86-64", pins=pins)

    assert not (tmp_path / "package").exists()


def test_staging_refuses_an_unreceipted_extra_file(tmp_path: Path) -> None:
    content = _linux_archive(tmp_path)
    pins = _pins("linux-x86-64", "tar.gz", "llama-b1/llama-server", content)
    tree = acquire_llama_server(tmp_path / "acquired", "linux-x86-64", pins=pins, fetch=_serving(content))
    (tree / PROGRAM_DIRECTORY / "implant.so").write_bytes(b"x")

    with pytest.raises(ArchiveMismatchError, match="differ from the receipt"):
        verify_acquired(tree, "linux-x86-64", pins=pins)


def test_staging_refuses_a_tree_acquired_for_another_pin(tmp_path: Path) -> None:
    content = _linux_archive(tmp_path)
    pins = _pins("linux-x86-64", "tar.gz", "llama-b1/llama-server", content)
    tree = acquire_llama_server(tmp_path / "acquired", "linux-x86-64", pins=pins, fetch=_serving(content))
    moved = _pins("linux-x86-64", "tar.gz", "llama-b1/llama-server", content + b"\0")

    with pytest.raises(ArchiveMismatchError, match="not the archive pinned for linux-x86-64"):
        verify_acquired(tree, "linux-x86-64", pins=moved)


def test_staging_refuses_a_missing_receipt(tmp_path: Path) -> None:
    (tmp_path / "acquired").mkdir()

    with pytest.raises(ArchiveMismatchError, match="missing or unreadable"):
        verify_acquired(tmp_path / "acquired", "linux-x86-64", pins=_pins("linux-x86-64", "tar.gz", "a/b", b"x"))


def test_the_native_image_walk_of_a_posix_assembly_reaches_every_staged_program_image(tmp_path: Path) -> None:
    content = _macos_archive(tmp_path)
    pins = _pins("macos-arm64", "tar.gz", "llama-b1/llama-server", content)
    tree = acquire_llama_server(tmp_path / "acquired", "macos-arm64", pins=pins, fetch=_serving(content))
    root = tmp_path / "package"
    sdk, native, packages = tmp_path / "sdk", root / "bin", root / "lib"
    for directory in (sdk / "extensions", native, packages):
        directory.mkdir(parents=True)
    stage_llama_server(tree, root, _LAYOUT, "macos-arm64", pins=pins)
    walked: list[list[Path]] = []

    contract = {"sdk": {"native_files": [], "extensions": "extensions", "extension_suffix": ".cpython-313-darwin.so"}}
    posix_assembly.assemble(
        sdk, packages, native, root, contract, lambda images, _root, _contract: walked.append(list(images))
    )

    staged = {root / "bin/llama" / name for name in _receipt(tree)["files"]}
    assert len(staged) == 3
    assert staged <= set(walked[0])


def _redistributable(tmp_path: Path) -> dict[str, Path]:
    directory = tmp_path / "redist"
    directory.mkdir()
    libraries = {}
    for name in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
        libraries[name] = pe_with_imports(directory / name, "KERNEL32.dll", "api-ms-win-crt-runtime-l1-1-0.dll")
    return libraries


def _staged_windows(tmp_path: Path, redistributable: dict[str, Path] | None) -> Path:
    content = _windows_archive(tmp_path)
    pins = _pins("windows-x86-64", "zip", "llama-server.exe", content)
    tree = acquire_llama_server(tmp_path / "acquired", "windows-x86-64", pins=pins, fetch=_serving(content))
    root = tmp_path / "package"
    stage_llama_server(tree, root, _LAYOUT, "windows-x86-64", pins=pins, redistributable=redistributable)
    return root / "bin/llama"


def test_a_windows_program_whose_imports_all_resolve_stages_with_the_runtime_beside_it(tmp_path: Path) -> None:
    program = _staged_windows(tmp_path, _redistributable(tmp_path))

    assert {"msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll", "llama-server.exe"} <= {
        path.name for path in program.iterdir()
    }
    assert (program / "vcruntime140.dll").read_bytes() == (tmp_path / "redist" / "vcruntime140.dll").read_bytes()


def test_a_windows_program_importing_a_library_nothing_provides_is_refused_naming_both(tmp_path: Path) -> None:
    with pytest.raises(UnresolvedImportError, match=r"llama-server-impl\.dll imports vcruntime140\.dll"):
        _staged_windows(tmp_path, None)


def test_an_import_of_a_library_that_is_neither_the_systems_nor_staged_fails_the_check(tmp_path: Path) -> None:
    program = tmp_path / "program"
    program.mkdir()
    pe_with_imports(program / "a.dll", "kernel32.dll", "api-ms-win-crt-heap-l1-1-0.dll", "b.dll", "unknown-runtime.dll")
    pe_with_imports(program / "b.dll", "ADVAPI32.dll")

    with pytest.raises(UnresolvedImportError, match=r"a\.dll imports unknown-runtime\.dll") as refused:
        require_resolved_imports(program)

    assert "b.dll imports" not in str(refused.value)


def test_every_import_resolving_returns_the_system_libraries_it_relies_on(tmp_path: Path) -> None:
    program = tmp_path / "program"
    program.mkdir()
    pe_with_imports(program / "a.dll", "KERNEL32.dll", "api-ms-win-crt-heap-l1-1-0.dll", "b.dll")
    pe_with_imports(program / "b.dll", "ws2_32.dll")

    assert require_resolved_imports(program) == ("api-ms-win-crt-heap-l1-1-0.dll", "kernel32.dll", "ws2_32.dll")


def test_the_vulkan_loader_is_a_driver_library_only_the_vulkan_backend_may_import(tmp_path: Path) -> None:
    program = tmp_path / "program"
    program.mkdir()
    pe_with_imports(program / "ggml-vulkan.dll", "vulkan-1.dll", "kernel32.dll")
    assert "vulkan-1.dll" in require_resolved_imports(program)

    pe_with_imports(program / "llama-server-impl.dll", "vulkan-1.dll")
    with pytest.raises(UnresolvedImportError, match=r"llama-server-impl\.dll imports vulkan-1\.dll"):
        require_resolved_imports(program)


def test_a_program_without_pe_images_has_nothing_to_resolve(tmp_path: Path) -> None:
    program = tmp_path / "program"
    program.mkdir()
    elf_with_requirements(program / "llama-server", needed=("libc.so.6",))

    assert require_resolved_imports(program) == ()


def test_a_windows_package_holds_the_pinned_llama_cpp_licence_beside_the_archive_notices(tmp_path: Path) -> None:
    program = _staged_windows(tmp_path, _redistributable(tmp_path))
    notices = program.parent.parent / "docs/licenses/llama.cpp"

    assert sorted(path.name for path in notices.iterdir()) == [LICENSE_NAME, "LICENSE-LLVM-OpenMP"]
    assert (notices / LICENSE_NAME).read_bytes() == _LICENSE_TEXT


def test_a_licence_download_that_differs_from_its_pin_is_refused(tmp_path: Path) -> None:
    content = _windows_archive(tmp_path)
    pins = _pins("windows-x86-64", "zip", "llama-server.exe", content)

    with pytest.raises(ArchiveMismatchError, match=r"the llama.cpp licence does not match its pin"):
        acquire_llama_server(
            tmp_path / "acquired", "windows-x86-64", pins=pins, fetch=_serving(content, _LICENSE_TEXT + b"x")
        )
    assert not (tmp_path / "acquired" / LICENSE_DIRECTORY).exists()


def test_an_archive_whose_own_licence_differs_from_the_pinned_one_is_refused(tmp_path: Path) -> None:
    content = _linux_archive(tmp_path, notice=b"MIT License\nother\n")
    pins = _pins("linux-x86-64", "tar.gz", "llama-b1/llama-server", content)

    with pytest.raises(ArchiveMismatchError, match="carries a LICENSE that differs from the pinned licence"):
        acquire_llama_server(tmp_path / "acquired", "linux-x86-64", pins=pins, fetch=_serving(content))


def _rewrite_receipt_licences(tree: Path, licences: dict[str, str]) -> None:
    receipt = _receipt(tree)
    receipt["licenses"] = licences
    (tree / RECEIPT_NAME).write_text(json.dumps(receipt), encoding="utf-8")


def test_staging_refuses_a_tree_whose_notices_lack_the_pinned_licence(tmp_path: Path) -> None:
    content = _windows_archive(tmp_path)
    pins = _pins("windows-x86-64", "zip", "llama-server.exe", content)
    tree = acquire_llama_server(tmp_path / "acquired", "windows-x86-64", pins=pins, fetch=_serving(content))
    (tree / LICENSE_DIRECTORY / LICENSE_NAME).unlink()
    licences = dict(_receipt(tree)["licenses"])
    del licences[LICENSE_NAME]
    _rewrite_receipt_licences(tree, licences)

    with pytest.raises(ArchiveMismatchError, match=r"do not hold the pinned llama.cpp LICENSE"):
        stage_llama_server(tree, tmp_path / "package", _LAYOUT, "windows-x86-64", pins=pins)
    assert not (tmp_path / "package").exists()


def test_staging_refuses_a_tree_whose_licence_is_not_the_pinned_text(tmp_path: Path) -> None:
    content = _windows_archive(tmp_path)
    pins = _pins("windows-x86-64", "zip", "llama-server.exe", content)
    tree = acquire_llama_server(tmp_path / "acquired", "windows-x86-64", pins=pins, fetch=_serving(content))
    replaced = b"Some other licence\n"
    (tree / LICENSE_DIRECTORY / LICENSE_NAME).write_bytes(replaced)
    licences = dict(_receipt(tree)["licenses"])
    licences[LICENSE_NAME] = hashlib.sha256(replaced).hexdigest()
    _rewrite_receipt_licences(tree, licences)

    with pytest.raises(ArchiveMismatchError, match=r"do not hold the pinned llama.cpp LICENSE"):
        stage_llama_server(tree, tmp_path / "package", _LAYOUT, "windows-x86-64", pins=pins)
    assert not (tmp_path / "package").exists()
