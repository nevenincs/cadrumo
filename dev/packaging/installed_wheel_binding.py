"""Bind an installed CLI environment to the exact immutable root wheel payload."""

from __future__ import annotations

import hashlib
import json
import struct
import zipfile
from pathlib import Path, PurePosixPath

from dev._paths import UTF_8
from dev.packaging.command_execution import run_command

_GENERATED_METADATA = frozenset({"INSTALLER", "RECORD", "REQUESTED", "direct_url.json", "uv_cache.json"})

# Portable-executable offsets used to project a Windows console launcher onto
# the bytes its embedded script cannot influence. Fixed by the PE/COFF format.
_PE_SIGNATURE_POINTER = 0x3C
_PE_SIGNATURE = b"PE\0\0"
_COFF_SECTION_COUNT_OFFSET = 6
_COFF_OPTIONAL_SIZE_OFFSET = 20
_COFF_HEADER_SIZE = 24
_PE32_MAGIC = 0x10B
_PE32_PLUS_MAGIC = 0x20B
_PE32_DATA_DIRECTORY_OFFSET = 96
_PE32_PLUS_DATA_DIRECTORY_OFFSET = 112
_PE32_NUMBER_OF_RVA_AND_SIZES_OFFSET = 92
_PE32_PLUS_NUMBER_OF_RVA_AND_SIZES_OFFSET = 108
_PE_SECTION_ALIGNMENT_OFFSET = 32
_PE_FILE_ALIGNMENT_OFFSET = 36
_PE_SIZE_OF_IMAGE_OFFSET = 56
_RESOURCE_DIRECTORY_INDEX = 2
_DATA_DIRECTORY_ENTRY_SIZE = 8
_SECTION_HEADER_SIZE = 40
_SECTION_VIRTUAL_SIZE_OFFSET = 8
_SECTION_RAW_SIZE_OFFSET = 16
_RESOURCE_DIRECTORY_HEADER_SIZE = 16
_RESOURCE_DIRECTORY_ENTRY_SIZE = 8
_RESOURCE_DATA_ENTRY_SIZE = 16
_RESOURCE_DIRECTORY_FLAG = 0x80000000
_RESOURCE_OFFSET_MASK = 0x7FFFFFFF
_RESOURCE_TYPE_RCDATA = 10
_UV_SCRIPT_RESOURCE_PATH = (("id", _RESOURCE_TYPE_RCDATA), ("name", "UV_SCRIPT_DATA"), ("id", 0))
_MAX_RESOURCE_DIRECTORY_DEPTH = 16
_WINDOWS_CONSOLE_ENTRY_POINTS = {
    "aeat": "cadrumo_runtime.host.frontend.cli.bootstrap:main",
    "cadrumo-mcp": "cadrumo_harness.mcp.main:main",
}


def _projection_digest(rows: list[tuple[str, str]]) -> str:
    payload = json.dumps(sorted(rows), ensure_ascii=False, separators=(",", ":")).encode(UTF_8)
    return hashlib.sha256(payload).hexdigest()


def _pe_unpack(image: bytes, offset: int, format_string: str, field: str) -> tuple[int, ...]:
    """Read a bounded PE field and turn truncation into a closed refusal."""
    try:
        fields = struct.unpack_from(format_string, image, offset)
    except (struct.error, OverflowError) as exc:
        raise RuntimeError(f"console entry-point launcher has a truncated {field}") from exc
    integers: list[int] = []
    for value in fields:
        if not isinstance(value, int):
            raise RuntimeError(f"console entry-point launcher has a non-integer {field}")
        integers.append(value)
    return tuple(integers)


def _pe_align(value: int, alignment: int) -> int:
    if alignment <= 0 or alignment & (alignment - 1):
        raise RuntimeError("console entry-point launcher has an invalid PE alignment")
    return ((value + alignment - 1) // alignment) * alignment


def _launcher_stub_projection(image: bytes) -> bytes:
    """Compare every launcher byte except UV's separately checked script resource.

    UV stores its Windows console script as ``RCDATA/UV_SCRIPT_DATA`` in the
    final PE resource section. Different entry-point scripts shift later
    resource data and change the resource-directory and section sizes. This
    parses that resource tree and retains every other resource name, directory
    field, data-entry field, and payload. It also keeps every byte outside the
    resource section, including PE headers, code, imports, relocations, section
    properties, and resource padding only after proving the padding is zero. The
    caller checks each launcher's script ZIP against its expected entry point
    before comparing these projections.
    """
    if len(image) < 64 or image[:2] != b"MZ":
        raise RuntimeError("console entry-point launcher is not a portable executable")
    signature = _pe_unpack(image, _PE_SIGNATURE_POINTER, "<I", "DOS header")[0]
    if image[signature : signature + len(_PE_SIGNATURE)] != _PE_SIGNATURE:
        raise RuntimeError("console entry-point launcher is not a portable executable")
    section_count = _pe_unpack(image, signature + _COFF_SECTION_COUNT_OFFSET, "<H", "COFF header")[0]
    optional_size = _pe_unpack(image, signature + _COFF_OPTIONAL_SIZE_OFFSET, "<H", "COFF header")[0]
    if section_count == 0:
        raise RuntimeError("console entry-point launcher has no PE sections")
    optional = signature + _COFF_HEADER_SIZE
    optional_end = optional + optional_size
    if optional_end > len(image):
        raise RuntimeError("console entry-point launcher has a truncated optional header")
    magic = _pe_unpack(image, optional, "<H", "optional header")[0]
    if magic == _PE32_PLUS_MAGIC:
        directories_offset = _PE32_PLUS_DATA_DIRECTORY_OFFSET
        directory_count_offset = _PE32_PLUS_NUMBER_OF_RVA_AND_SIZES_OFFSET
    elif magic == _PE32_MAGIC:
        directories_offset = _PE32_DATA_DIRECTORY_OFFSET
        directory_count_offset = _PE32_NUMBER_OF_RVA_AND_SIZES_OFFSET
    else:
        raise RuntimeError("console entry-point launcher has an unsupported PE optional header")
    directory_end = directories_offset + (_RESOURCE_DIRECTORY_INDEX + 1) * _DATA_DIRECTORY_ENTRY_SIZE
    if optional_size < max(directory_end, _PE_SIZE_OF_IMAGE_OFFSET + 4):
        raise RuntimeError("console entry-point launcher has a truncated optional header")
    directory_count = _pe_unpack(image, optional + directory_count_offset, "<I", "data-directory count")[0]
    if directory_count <= _RESOURCE_DIRECTORY_INDEX:
        raise RuntimeError("console entry-point launcher has no resource data directory")
    directories = optional + directories_offset
    resource_rva, resource_size = _pe_unpack(
        image,
        directories + _RESOURCE_DIRECTORY_INDEX * _DATA_DIRECTORY_ENTRY_SIZE,
        "<II",
        "resource data directory",
    )
    if resource_rva == 0 or resource_size == 0:
        raise RuntimeError("console entry-point launcher carries no embedded script resource")

    table = optional_end
    table_end = table + section_count * _SECTION_HEADER_SIZE
    if table_end > len(image):
        raise RuntimeError("console entry-point launcher has a truncated section table")
    section_alignment = _pe_unpack(image, optional + _PE_SECTION_ALIGNMENT_OFFSET, "<I", "section alignment")[0]
    file_alignment = _pe_unpack(image, optional + _PE_FILE_ALIGNMENT_OFFSET, "<I", "file alignment")[0]
    section_headers: list[tuple[int, int, int, int, int, int]] = []
    for index in range(section_count):
        header = table + index * _SECTION_HEADER_SIZE
        virtual_size, virtual_address, raw_size, raw_offset = _pe_unpack(
            image, header + _SECTION_VIRTUAL_SIZE_OFFSET, "<IIII", "section header"
        )
        if raw_size and (raw_offset < table_end or raw_offset + raw_size > len(image)):
            raise RuntimeError("console entry-point launcher has an invalid section extent")
        section_headers.append((header, virtual_size, virtual_address, raw_size, raw_offset, index))

    owners = [
        section
        for section in section_headers
        if section[2] <= resource_rva and resource_rva + resource_size <= section[2] + section[1]
    ]
    if len(owners) != 1:
        raise RuntimeError("console entry-point launcher resource directory has no unique section")
    resource = owners[0]
    resource_header, virtual_size, virtual_address, raw_size, raw_offset, section_index = resource
    if resource_rva != virtual_address or resource_size != virtual_size:
        raise RuntimeError("console entry-point launcher resource section is not fully described")
    if raw_size != _pe_align(virtual_size, file_alignment):
        raise RuntimeError("console entry-point launcher resource section has an invalid raw size")
    if raw_offset + raw_size != len(image):
        raise RuntimeError("console entry-point launcher has bytes after its resource section")
    if any(
        other[3] and raw_offset < other[4] + other[3] and other[4] < raw_offset + raw_size
        for other in section_headers
        if other is not resource
    ):
        raise RuntimeError("console entry-point launcher sections overlap")
    if any(other[2] + other[1] > virtual_address for other in section_headers if other is not resource):
        raise RuntimeError("console entry-point launcher resource section is not the final image section")
    if section_index != max(section[5] for section in section_headers):
        raise RuntimeError("console entry-point launcher resource section is not last in the section table")

    image_size = _pe_unpack(image, optional + _PE_SIZE_OF_IMAGE_OFFSET, "<I", "image size")[0]
    image_end = max(section[2] + section[1] for section in section_headers)
    if image_size != _pe_align(image_end, section_alignment):
        raise RuntimeError("console entry-point launcher has an inconsistent image size")
    if any(image[raw_offset + resource_size : raw_offset + raw_size]):
        raise RuntimeError("console entry-point launcher resource padding is not zero")

    resource_root = raw_offset
    resource_end = resource_root + resource_size
    used_ranges: list[tuple[int, int]] = []

    def mark_used(start: int, size: int) -> None:
        relative_start = start - resource_root
        relative_end = relative_start + size
        if size < 0 or relative_start < 0 or relative_end > resource_size:
            raise RuntimeError("console entry-point launcher resource offset is out of bounds")
        if size:
            used_ranges.append((relative_start, relative_end))

    def resource_name(field: int) -> tuple[str, int | str]:
        if field & _RESOURCE_DIRECTORY_FLAG:
            name_offset = resource_root + (field & _RESOURCE_OFFSET_MASK)
            mark_used(name_offset, 2)
            length = _pe_unpack(image, name_offset, "<H", "resource name")[0]
            byte_length = length * 2
            mark_used(name_offset + 2, byte_length)
            try:
                name = image[name_offset + 2 : name_offset + 2 + byte_length].decode("utf-16le")
            except UnicodeDecodeError as exc:
                raise RuntimeError("console entry-point launcher resource name is malformed") from exc
            return ("name", name)
        if field & 0xFFFF0000:
            raise RuntimeError("console entry-point launcher resource identifier is malformed")
        return ("id", field)

    visited_directories: set[int] = set()
    script_resources = 0

    def read_directory(
        relative_offset: int,
        path: tuple[tuple[str, int | str], ...],
        depth: int,
    ) -> dict[str, object]:
        nonlocal script_resources
        if depth > _MAX_RESOURCE_DIRECTORY_DEPTH:
            raise RuntimeError("console entry-point launcher resource tree is too deep")
        if relative_offset in visited_directories:
            raise RuntimeError("console entry-point launcher resource tree has a cycle or alias")
        visited_directories.add(relative_offset)
        directory = resource_root + relative_offset
        mark_used(directory, _RESOURCE_DIRECTORY_HEADER_SIZE)
        fields = _pe_unpack(image, directory, "<IIHHHH", "resource directory")
        characteristics, timestamp, major, minor, named_count, id_count = fields
        entry_count = named_count + id_count
        entries_offset = directory + _RESOURCE_DIRECTORY_HEADER_SIZE
        mark_used(entries_offset, entry_count * _RESOURCE_DIRECTORY_ENTRY_SIZE)
        entries: list[list[object]] = []
        for index in range(entry_count):
            entry_offset = entries_offset + index * _RESOURCE_DIRECTORY_ENTRY_SIZE
            name_field, target_field = _pe_unpack(image, entry_offset, "<II", "resource directory entry")
            key = resource_name(name_field)
            child_path = (*path, key)
            target_offset = target_field & _RESOURCE_OFFSET_MASK
            if target_field & _RESOURCE_DIRECTORY_FLAG:
                value: object = read_directory(target_offset, child_path, depth + 1)
            else:
                data_entry = resource_root + target_offset
                mark_used(data_entry, _RESOURCE_DATA_ENTRY_SIZE)
                data_rva, data_size, codepage, reserved = _pe_unpack(image, data_entry, "<IIII", "resource data entry")
                if data_rva < resource_rva or data_rva + data_size > resource_rva + resource_size:
                    raise RuntimeError("console entry-point launcher resource payload is out of bounds")
                payload_offset = resource_root + data_rva - resource_rva
                mark_used(payload_offset, data_size)
                is_script = child_path == _UV_SCRIPT_RESOURCE_PATH
                if is_script:
                    script_resources += 1
                value = {
                    "kind": "data",
                    "codepage": codepage,
                    "reserved": reserved,
                    "payload": None if is_script else image[payload_offset : payload_offset + data_size].hex(),
                }
            entries.append([[key[0], key[1]], value])
        return {
            "kind": "directory",
            "metadata": [characteristics, timestamp, major, minor, named_count, id_count],
            "entries": entries,
        }

    tree = read_directory(0, (), 0)
    if script_resources != 1:
        raise RuntimeError("console entry-point launcher has no unique UV script resource")
    previous_end = 0
    for start, end in sorted(used_ranges):
        if start < previous_end:
            raise RuntimeError("console entry-point launcher resource extents overlap")
        if any(image[resource_root + previous_end : resource_root + start]):
            raise RuntimeError("console entry-point launcher has unreferenced resource bytes")
        previous_end = end
    if any(image[resource_root + previous_end : resource_end]):
        raise RuntimeError("console entry-point launcher has unreferenced resource bytes")

    canonical_resources = json.dumps(tree, ensure_ascii=False, separators=(",", ":")).encode(UTF_8)
    base_image_end = max(section[2] + section[1] for section in section_headers if section is not resource)
    projected = bytearray(image)
    struct.pack_into(
        "<I",
        projected,
        directories + _RESOURCE_DIRECTORY_INDEX * _DATA_DIRECTORY_ENTRY_SIZE + 4,
        0,
    )
    struct.pack_into("<I", projected, resource_header + _SECTION_VIRTUAL_SIZE_OFFSET, 0)
    struct.pack_into("<I", projected, resource_header + _SECTION_RAW_SIZE_OFFSET, 0)
    struct.pack_into("<I", projected, optional + _PE_SIZE_OF_IMAGE_OFFSET, _pe_align(base_image_end, section_alignment))
    del projected[raw_offset : raw_offset + raw_size]
    projection = bytes(projected)
    return (
        len(projection).to_bytes(8, "little")
        + projection
        + len(canonical_resources).to_bytes(8, "little")
        + canonical_resources
    )


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


def environment_interpreter(python: Path) -> Path:
    """Return an environment's interpreter with its directories resolved and its final link kept.

    The final ``bin/python`` link is the environment itself (see
    :func:`_existing_interpreter`), so resolving the whole path would launch
    the base installation that seeded it. Only the directories above it are
    made canonical, which keeps a comparison with a sibling console script's
    resolved directory sound.

    Raises:
        RuntimeError: When no interpreter exists at that path.
    """
    interpreter = python.parent.resolve(strict=True) / python.name
    if not interpreter.is_file():
        raise RuntimeError(f"no interpreter exists at {interpreter}")
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
    completed = run_command(
        [str(python), "-I", "-c", script, distribution],
        cwd=Path.cwd(),
        errors="strict",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"could not attest installed cadrumo payload: {completed.stderr.strip()}")
    digest = completed.stdout.strip()
    if len(digest) != 64:
        raise RuntimeError(f"installed payload returned invalid digest: {digest!r}")
    return digest


def _windows_entry_point_script(python: Path, expected_value: str) -> bytes:
    module_name, callable_name = expected_value.split(":", 1)
    return (
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


def _assert_windows_launcher_script(resolved: Path, expected_script: bytes) -> None:
    with zipfile.ZipFile(resolved) as launcher:
        if launcher.namelist() != ["__main__.py"] or launcher.read("__main__.py") != expected_script:
            raise RuntimeError("console entry-point launcher semantics drifted")


def _assert_windows_launcher(resolved: Path, entry_point: str, expected_script: bytes) -> None:
    try:
        peer_name = "cadrumo-mcp.exe" if entry_point == "aeat" else "aeat.exe"
        peer = resolved.with_name(peer_name).resolve(strict=True)
        _assert_windows_launcher_script(resolved, expected_script)
        peer_expected_value = _WINDOWS_CONSOLE_ENTRY_POINTS[Path(peer_name).stem]
        peer_python = installed_python_for_cli(peer)
        _assert_windows_launcher_script(peer, _windows_entry_point_script(peer_python, peer_expected_value))
        if _launcher_stub_projection(resolved.read_bytes()) != _launcher_stub_projection(peer.read_bytes()):
            raise RuntimeError("console entry-point launcher stub drifted")
    except (OSError, struct.error, zipfile.BadZipFile) as exc:
        raise RuntimeError("console entry-point launcher is malformed") from exc


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
    expected_script = _windows_entry_point_script(python, expected_value)
    if resolved.suffix.lower() == ".exe":
        _assert_windows_launcher(resolved, entry_point, expected_script)
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
    completed = run_command(
        [str(python), "-I", "-c", script, distribution, entry_point, expected_value],
        cwd=Path.cwd(),
        errors="strict",
        timeout_seconds=15,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"installed console entry-point binding failed: {completed.stderr.strip()}")


def installed_wheel_payload_sha256(cli: Path) -> str:
    """Hash the installed ``cadrumo`` payload through the CLI-owning interpreter."""
    return installed_distribution_payload_sha256(cli, "cadrumo")
