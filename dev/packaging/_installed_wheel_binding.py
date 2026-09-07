"""Bind an installed CLI environment to the exact immutable root wheel payload."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

from .._paths import UTF_8

_GENERATED_METADATA = frozenset({"INSTALLER", "RECORD", "REQUESTED", "direct_url.json", "uv_cache.json"})

# Portable-executable offsets used to project a Windows console launcher onto
# the bytes its embedded script cannot influence. Fixed by the PE/COFF format.
_PE_SIGNATURE_POINTER = 0x3C
_PE_SIGNATURE = b"PE\0\0"
_COFF_SECTION_COUNT_OFFSET = 6
_COFF_OPTIONAL_SIZE_OFFSET = 20
_COFF_HEADER_SIZE = 24
_PE32_PLUS_MAGIC = 0x20B
_PE32_DATA_DIRECTORY_OFFSET = 96
_PE32_PLUS_DATA_DIRECTORY_OFFSET = 112
_RESOURCE_DIRECTORY_INDEX = 2
_DATA_DIRECTORY_ENTRY_SIZE = 8
_SECTION_HEADER_SIZE = 40
_SECTION_NAME_SIZE = 8
_SECTION_VIRTUAL_SIZE_OFFSET = 8
_SECTION_RAW_SIZE_OFFSET = 16
_RESOURCE_SECTION_NAME = b".rsrc"


def _projection_digest(rows: list[tuple[str, str]]) -> str:
    payload = json.dumps(sorted(rows), ensure_ascii=False, separators=(",", ":")).encode(UTF_8)
    return hashlib.sha256(payload).hexdigest()


def _launcher_stub_projection(image: bytes) -> bytes:
    """Project a Windows console launcher onto bytes its embedded script cannot change.

    A console launcher is one installer-fixed stub carrying the script's zip as
    a Windows resource, so the resource section and the two header fields that
    state its size track the compressed script's length. Two genuine launchers
    installed side by side therefore differ there whenever their scripts differ
    in length, and comparing the raw stubs compares the payload rather than the
    stub. The payload is already compared byte-for-byte against the expected
    script by the caller, so this elides the resource section and those two size
    fields and leaves every remaining byte - entry point, code, imports, data,
    relocations, and the whole section layout including the resource section's
    address and file offset - compared exactly.
    """
    signature = struct.unpack_from("<I", image, _PE_SIGNATURE_POINTER)[0]
    if image[signature : signature + len(_PE_SIGNATURE)] != _PE_SIGNATURE:
        raise RuntimeError("console entry-point launcher is not a portable executable")
    section_count = struct.unpack_from("<H", image, signature + _COFF_SECTION_COUNT_OFFSET)[0]
    optional_size = struct.unpack_from("<H", image, signature + _COFF_OPTIONAL_SIZE_OFFSET)[0]
    optional = signature + _COFF_HEADER_SIZE
    magic = struct.unpack_from("<H", image, optional)[0]
    directories = optional + (
        _PE32_PLUS_DATA_DIRECTORY_OFFSET if magic == _PE32_PLUS_MAGIC else _PE32_DATA_DIRECTORY_OFFSET
    )
    resource_size_field = directories + _RESOURCE_DIRECTORY_INDEX * _DATA_DIRECTORY_ENTRY_SIZE + 4
    table = optional + optional_size
    headers = (table + index * _SECTION_HEADER_SIZE for index in range(section_count))
    resource = next(
        (
            header
            for header in headers
            if image[header : header + _SECTION_NAME_SIZE].rstrip(b"\0") == _RESOURCE_SECTION_NAME
        ),
        None,
    )
    if resource is None:
        raise RuntimeError("console entry-point launcher carries no embedded script resource")
    raw_size, raw_offset = struct.unpack_from("<II", image, resource + _SECTION_RAW_SIZE_OFFSET)
    projected = bytearray(image)
    struct.pack_into("<I", projected, resource_size_field, 0)
    struct.pack_into("<I", projected, resource + _SECTION_VIRTUAL_SIZE_OFFSET, 0)
    del projected[raw_offset : raw_offset + raw_size]
    return bytes(projected)


def sealed_wheel_payload_sha256(wheel: Path) -> str:
    """Return the canonical digest of immutable install payload members."""
    rows: list[tuple[str, str]] = []
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if info.is_dir() or path.name in _GENERATED_METADATA:
                continue
            rows.append((path.as_posix(), hashlib.sha256(archive.read(info)).hexdigest()))
    return _projection_digest(rows)


def _existing_interpreter(interpreter: Path, *, cli: Path) -> Path:
    """Accept an absolute, existing interpreter path without dereferencing it.

    A POSIX environment's ``bin/python`` is an absolute symlink to the base
    installation it was built from, and the link itself is the environment: the
    interpreter behind it has no adjacent ``pyvenv.cfg``, so it starts on the
    base ``sys.prefix`` and cannot see the environment's ``site-packages``.
    Following that final link therefore swaps the installation under attestation
    for the one that seeded it, and the probe reports an empty environment
    rather than the installed payload. The link is also load-bearing on macOS,
    where a copied python-build-standalone binary loses its
    ``@executable_path``-relative ``libpython``, so the path is checked for
    existence and otherwise left exactly as the launcher names it.
    """
    if not interpreter.is_absolute():
        raise RuntimeError(f"installed CLI names a relative interpreter: {interpreter} ({cli})")
    if not interpreter.is_file():
        raise RuntimeError(f"installed CLI names a missing interpreter: {interpreter} ({cli})")
    return interpreter


def installed_python_for_cli(cli: Path) -> Path:
    """Resolve the interpreter that owns an installed console entry point."""
    resolved = cli.resolve(strict=True)
    if resolved.suffix.lower() == ".exe":
        return _existing_interpreter(resolved.parent / "python.exe", cli=resolved)
    first_line = resolved.read_bytes().splitlines()[0].decode(UTF_8)
    if not first_line.startswith("#!"):
        raise RuntimeError(f"installed CLI has no absolute Python shebang: {resolved}")
    interpreter = first_line[2:].strip().split(" ", 1)[0]
    return _existing_interpreter(Path(interpreter), cli=resolved)


def installed_distribution_payload_sha256(cli: Path, distribution: str) -> str:
    """Hash one installed distribution through the executable-owning interpreter."""
    python = installed_python_for_cli(cli)
    script = r"""
import hashlib, importlib.metadata, json
generated = {"INSTALLER", "RECORD", "direct_url.json", "REQUESTED"}
dist = importlib.metadata.distribution(__import__("sys").argv[1])
rows = []
for item in dist.files or ():
    path = item.as_posix()
    if (
        item.name in generated | {"uv_cache.json"}
        or ".." in item.parts
        or path.endswith(".pyc")
        or "/__pycache__/" in path
    ):
        continue
    resolved = dist.locate_file(item).resolve(strict=True)
    if resolved.is_file():
        rows.append((path, hashlib.sha256(resolved.read_bytes()).hexdigest()))
payload = json.dumps(sorted(rows), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
print(hashlib.sha256(payload).hexdigest())
"""
    completed = subprocess.run(  # noqa: S603 - interpreter is resolved from the installed CLI.
        [str(python), "-I", "-c", script, distribution],
        check=False,
        capture_output=True,
        text=True,
        encoding=UTF_8,
        errors="strict",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"could not attest installed cadrumo payload: {completed.stderr.strip()}")
    digest = completed.stdout.strip()
    if len(digest) != 64:
        raise RuntimeError(f"installed payload returned invalid digest: {digest!r}")
    return digest


def assert_installed_console_entry_point(
    executable: Path,
    *,
    distribution: str,
    entry_point: str,
    expected_value: str,
) -> None:
    """Resolve an entry point independently through the confined interpreter."""
    resolved = executable.resolve(strict=True)
    python = installed_python_for_cli(resolved)
    launcher_name = f"{entry_point}.exe" if resolved.suffix.lower() == ".exe" else entry_point
    if resolved != (python.parent / launcher_name).resolve(strict=True):
        raise RuntimeError("console entry point is not the confined environment launcher")
    module_name, callable_name = expected_value.split(":", 1)
    expected_script = (
        f"#!{python}\n"
        "# -*- coding: utf-8 -*-\n"
        "import sys\n"
        f"from {module_name} import {callable_name}\n"
        'if __name__ == "__main__":\n'
        '    if sys.argv[0].endswith("-script.pyw"):\n'
        "        sys.argv[0] = sys.argv[0][:-11]\n"
        '    elif sys.argv[0].endswith(".exe"):\n'
        "        sys.argv[0] = sys.argv[0][:-4]\n"
        f"    sys.exit({callable_name}())\n"
    ).encode(UTF_8)
    if resolved.suffix.lower() == ".exe":
        try:
            with zipfile.ZipFile(resolved) as launcher:
                if launcher.namelist() != ["__main__.py"] or launcher.read("__main__.py") != expected_script:
                    raise RuntimeError("console entry-point launcher semantics drifted")
            peer_name = "cadrumo-mcp.exe" if entry_point == "aeat" else "aeat.exe"
            peer = resolved.with_name(peer_name).resolve(strict=True)
            if _launcher_stub_projection(resolved.read_bytes()) != _launcher_stub_projection(peer.read_bytes()):
                raise RuntimeError("console entry-point launcher stub drifted")
        except (OSError, struct.error, zipfile.BadZipFile) as exc:
            raise RuntimeError("console entry-point launcher is malformed") from exc
    elif resolved.read_bytes() != expected_script:
        raise RuntimeError("console entry-point launcher semantics drifted")
    script = r"""
import importlib, importlib.metadata, pathlib, sys
distribution, entry_name, expected = sys.argv[1:]
dist = importlib.metadata.distribution(distribution)
matches = [ep for ep in dist.entry_points if ep.group == "console_scripts" and ep.name == entry_name]
if len(matches) != 1 or matches[0].value != expected:
    raise SystemExit("console entry-point metadata drifted")
module = importlib.import_module(expected.split(":", 1)[0])
origin = pathlib.Path(module.__file__).resolve(strict=True)
site_root = pathlib.Path(dist.locate_file("")).resolve(strict=True)
if not origin.is_relative_to(site_root):
    raise SystemExit("console entry-point module escaped installed distribution root")
target = module
for component in expected.split(":", 1)[1].split("."):
    target = getattr(target, component)
if not callable(target):
    raise SystemExit("console entry-point target is not callable")
"""
    completed = subprocess.run(  # noqa: S603 - interpreter belongs to the confined installed environment.
        [str(python), "-I", "-c", script, distribution, entry_point, expected_value],
        check=False,
        capture_output=True,
        text=True,
        encoding=UTF_8,
        errors="strict",
        timeout=15,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"installed console entry-point binding failed: {completed.stderr.strip()}")


def installed_wheel_payload_sha256(cli: Path) -> str:
    """Hash the installed ``cadrumo`` payload through the CLI-owning interpreter."""
    return installed_distribution_payload_sha256(cli, "cadrumo")
