"""Acquire the pinned llama-server release archive and stage its program into the package.

The package ships the upstream ``llama-server`` program and never builds it. One
archive per build target is pinned by release tag, size and SHA-256 in
``native/llamacpp-pins.json``. :func:`acquire_llama_server` is the build action
that fetches it into the build tree, refuses bytes that differ from the pin,
keeps the program files it needs and writes a receipt naming them.
:func:`stage_llama_server` copies those files into the package during assembly,
after proving again that the receipt, the files and the committed pin agree.

The program is a small launcher plus shared libraries beside it. What is kept is
the launcher, every library it needs transitively inside the archive, and the
compute backends that ggml opens by scanning its own directory on ELF and PE
builds. The archive's other programs and their libraries stay behind. Library
links are kept as copies under the name a loader asks for, because an installed
package holds no links.

On Linux the program must run on the package's glibc floor. An archive whose
files need a newer glibc is refused here, before anything is staged.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import tarfile
import zipfile
from collections import deque
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import IO, Final

import httpx
from pydantic import BaseModel, Field, PositiveInt, ValidationError

from cadrumo.core.models import STRICT_FROZEN_CONFIG
from dev.env.llamacpp_pins import ServerArchivePin, ServerPins, load_server_pins

from ..runtime_wheelhouse_contract import target_platform
from .hashing import digest
from .package_inventory import checked_member
from .platforms.elf import read_elf_requirements
from .platforms.macos_macho import inspect_macho
from .platforms.pe import imports as pe_imports

RECEIPT_NAME: Final = "llama-server.json"
"""The receipt, beside the program and licence directories of the acquired tree."""
PROGRAM_DIRECTORY: Final = "program"
LICENSE_DIRECTORY: Final = "licenses"
ARCHIVE_DIRECTORY: Final = "archives"
"""The verified archive stays here between builds, like the CPython archive."""
_EXTRACTION_DIRECTORY: Final = "extraction"
_RECEIPT_SCHEMA: Final = 1
_MAX_REDIRECTS: Final = 3
_TIMEOUT_S: Final = 120.0
_REDIRECTS: Final = frozenset({301, 302, 303, 307, 308})
_LIBRARY_LINK_DEPTH: Final = 8
#: Backends ggml loads by scanning its own directory rather than by linking them.
_BACKEND: Final = re.compile(r"(?:lib)?ggml-[a-z0-9_.-]+\.(?:dll|so|dylib)")
_LICENSE: Final = re.compile(r"LICEN[CS]E(?:[-._].*)?", re.IGNORECASE)
_MACHO_MAGIC: Final = frozenset({b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"})
_ELF_MAGIC: Final = b"\x7fELF"

#: Libraries the operating system provides to every process, by case-folded name. The program may import these
#: without carrying them; the list is the set a Windows 10 or later installation always holds.
SYSTEM_LIBRARIES: Final = frozenset(
    {
        "advapi32.dll",
        "bcrypt.dll",
        "crypt32.dll",
        "dbghelp.dll",
        "gdi32.dll",
        "iphlpapi.dll",
        "kernel32.dll",
        "ntdll.dll",
        "ole32.dll",
        "oleaut32.dll",
        "psapi.dll",
        "secur32.dll",
        "shell32.dll",
        "shlwapi.dll",
        "ucrtbase.dll",
        "user32.dll",
        "userenv.dll",
        "version.dll",
        "ws2_32.dll",
    }
)
#: Forwarders to the operating system's universal C runtime and other API sets.
SYSTEM_PREFIXES: Final = ("api-ms-win-", "ext-ms-win-")
#: The Vulkan loader belongs to the graphics driver, not to Cadrumo or the operating system image, and a machine
#: without it is a machine without Vulkan. Only the Vulkan backend library may import it: ggml skips a backend
#: whose library fails to load, so an absent loader costs that backend and leaves the CPU backends running.
DRIVER_LIBRARIES: Final[Mapping[str, frozenset[str]]] = {"vulkan-1.dll": frozenset({"ggml-vulkan.dll"})}

type Fetch = Callable[[ServerArchivePin, tuple[str, ...]], bytes]


class LlamaServerError(ValueError):
    """The pinned llama-server cannot be admitted into the package."""


class ArchiveMismatchError(LlamaServerError):
    """An archive, an acquired tree or a receipt differs from the pin it must match."""


class GlibcFloorError(LlamaServerError):
    """A Linux archive needs a newer glibc than the package supports."""


class UnresolvedImportError(LlamaServerError):
    """A staged Windows image imports a library that is neither the operating system's nor in the program directory."""


class LlamaServerReceipt(BaseModel):
    """What one acquisition proved: the pin it matched and the files it kept, by SHA-256."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(alias="schema")
    target: str
    tag: str
    backend: str
    url: str
    archive_bytes: PositiveInt
    archive_sha256: str
    executable: str
    files: dict[str, str]
    licenses: dict[str, str]
    host_libraries: list[str]
    """Libraries the kept files import that the archive does not hold; the host must supply them."""


def pin_for_target(pins: ServerPins, target: str) -> ServerArchivePin:
    """Return the archive pinned for ``target``, refusing a target the pins do not cover."""
    for pin in pins.archives:
        if pin.target == target:
            return pin
    raise ArchiveMismatchError(f"no llama-server archive is pinned for {target}")


def verify_archive(content: bytes, pin: ServerArchivePin) -> None:
    """Refuse archive bytes whose size or SHA-256 differs from the pin."""
    actual = hashlib.sha256(content).hexdigest()
    if len(content) != pin.download_bytes or actual != pin.sha256:
        raise ArchiveMismatchError(
            f"the llama-server archive for {pin.target} does not match its pin: "
            f"expected {pin.download_bytes} bytes with SHA-256 {pin.sha256}, "
            f"got {len(content)} bytes with SHA-256 {actual}"
        )


def _admit_origin(url: httpx.URL, hosts: frozenset[str]) -> None:
    if url.scheme != "https" or url.host not in hosts or url.port not in {None, 443} or url.userinfo:
        raise ArchiveMismatchError(f"the llama-server download leaves the pinned HTTPS hosts at {url.host}")


def fetch_archive(pin: ServerArchivePin, hosts: tuple[str, ...]) -> bytes:
    """Download the pinned archive over HTTPS from the pinned hosts, never beyond the pinned size."""
    allowed = frozenset(hosts)
    current = httpx.URL(pin.url)
    redirects = 0
    try:
        while True:
            _admit_origin(current, allowed)
            with httpx.stream(
                "GET",
                current,
                timeout=_TIMEOUT_S,
                follow_redirects=False,
                trust_env=False,
                headers={"Accept-Encoding": "identity"},
            ) as response:
                if response.status_code in _REDIRECTS:
                    location = response.headers.get("location")
                    if not location or redirects == _MAX_REDIRECTS:
                        raise ArchiveMismatchError("the llama-server download redirect is missing or too long")
                    current = current.join(location)
                    redirects += 1
                    continue
                response.raise_for_status()
                parts: list[bytes] = []
                received = 0
                for chunk in response.iter_bytes():
                    received += len(chunk)
                    if received > pin.download_bytes:
                        raise ArchiveMismatchError(
                            f"the llama-server archive for {pin.target} exceeds its pinned {pin.download_bytes} bytes"
                        )
                    parts.append(chunk)
                return b"".join(parts)
    except httpx.HTTPError as error:
        raise LlamaServerError(f"the llama-server archive for {pin.target} could not be fetched: {error}") from error


def _flat_name(raw: str, base: PurePosixPath) -> str | None:
    """Return the file name of an archive member of the program directory, or ``None`` for the directory itself."""
    name = raw.removeprefix("./").rstrip("/")
    if name in {"", "."}:
        return None
    path = PurePosixPath(name)
    if path.is_absolute() or "\\" in name or "\x00" in name or any(part in {"", ".", ".."} for part in path.parts):
        raise ArchiveMismatchError(f"the llama-server archive holds an unsafe member name: {raw!r}")
    if path == base:
        return None
    if path.parent != base:
        raise ArchiveMismatchError(f"the llama-server archive holds a member outside its program directory: {raw!r}")
    return checked_member(path.name)


def _write(scratch: Path, name: str, source: IO[bytes], mode: int | None) -> None:
    target = scratch / name
    with target.open("xb") as output:
        shutil.copyfileobj(source, output)
    if mode is not None:
        target.chmod(mode & 0o777 | 0o400)


def _unpack_tar(content: bytes, base: PurePosixPath, scratch: Path) -> dict[str, str]:
    links: dict[str, str] = {}
    seen: set[str] = set()
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tar:
        for member in tar:
            name = _flat_name(member.name, base)
            if name is None:
                if not member.isdir():
                    raise ArchiveMismatchError(f"the llama-server archive holds a non-directory root: {member.name!r}")
                continue
            if name.casefold() in seen:
                raise ArchiveMismatchError(f"the llama-server archive repeats the member {name!r}")
            seen.add(name.casefold())
            if member.isfile():
                source = tar.extractfile(member)
                if source is None:
                    raise ArchiveMismatchError(f"the llama-server archive member is unreadable: {name!r}")
                _write(scratch, name, source, member.mode)
            elif member.issym():
                if "/" in member.linkname or member.linkname in {"", ".", ".."}:
                    raise ArchiveMismatchError(f"the llama-server archive links {name!r} beyond its directory")
                links[name] = member.linkname
            else:
                raise ArchiveMismatchError(f"the llama-server archive holds a special member: {name!r}")
    return links


def _unpack_zip(content: bytes, base: PurePosixPath, scratch: Path) -> dict[str, str]:
    seen: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for info in archive.infolist():
            name = _flat_name(info.orig_filename, base)
            if name is None:
                continue
            if info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ArchiveMismatchError(f"the llama-server archive holds a directory or link: {name!r}")
            if name.casefold() in seen:
                raise ArchiveMismatchError(f"the llama-server archive repeats the member {name!r}")
            seen.add(name.casefold())
            with archive.open(info) as source:
                _write(scratch, name, source, None)
    return {}


def _resolve(name: str, links: Mapping[str, str], scratch: Path) -> str:
    """Follow library links to the regular file that holds the bytes."""
    current = name
    for _ in range(_LIBRARY_LINK_DEPTH):
        if current not in links:
            if not (scratch / current).is_file():
                raise ArchiveMismatchError(f"the llama-server archive link {name!r} names no file")
            return current
        current = links[current]
    raise ArchiveMismatchError(f"the llama-server archive link {name!r} does not end in a file")


def _kind(path: Path) -> str:
    with path.open("rb") as stream:
        magic = stream.read(4)
    if magic.startswith(b"MZ"):
        return "pe"
    if magic == _ELF_MAGIC:
        return "elf"
    if magic in _MACHO_MAGIC:
        return "macho"
    return "data"


def _needs(path: Path, name: str) -> tuple[list[str], list[str]]:
    """Return the in-bundle names and the other names the image ``name`` asks the loader for."""
    kind = _kind(path)
    try:
        if kind == "pe":
            return sorted(pe_imports(path)), []
        if kind == "elf":
            return list(read_elf_requirements(path).needed), []
        if kind == "macho":
            bundled: list[str] = []
            system: list[str] = []
            for dependency in inspect_macho(path).dependencies:
                (bundled if dependency.startswith("@") else system).append(dependency)
            return [PurePosixPath(item).name for item in bundled], system
    except ValueError as error:
        raise ArchiveMismatchError(f"{name} in the llama-server archive cannot be read as an image: {error}") from error
    raise ArchiveMismatchError(f"{name} in the llama-server archive is not a program image")


def _select(scratch: Path, links: Mapping[str, str], executable: str) -> tuple[dict[str, str], tuple[str, ...]]:
    """Choose the program files: the launcher, its library closure and the ELF/PE backends beside it."""
    regular = {path.name for path in scratch.iterdir() if path.is_file()}
    by_fold = {name.casefold(): name for name in (*regular, *links)}
    if executable not in regular:
        raise ArchiveMismatchError(f"the llama-server archive holds no regular file {executable!r}")
    kind = _kind(scratch / executable)
    roots = [executable]
    if kind != "macho":
        roots += sorted(name for name in regular if _BACKEND.fullmatch(name.casefold()))
    selected: dict[str, str] = {}
    host: set[str] = set()
    queue = deque(roots)
    while queue:
        name = queue.popleft()
        if name in selected:
            continue
        source = _resolve(name, links, scratch)
        selected[name] = source
        bundled, system = _needs(scratch / source, name)
        host.update(system)
        for dependency in bundled:
            found = by_fold.get(dependency.casefold())
            if found is not None:
                queue.append(found)
            elif kind == "macho":
                raise ArchiveMismatchError(f"{name} needs {dependency}, which the archive does not hold")
            else:
                host.add(dependency)
    return selected, tuple(sorted(host))


def _require_glibc_floor(scratch: Path, selected: Mapping[str, str], pin: ServerArchivePin) -> None:
    platform = target_platform(pin.target)
    if platform.sys_platform != "linux":
        return
    floor = tuple(int(part) for part in platform.floor.removeprefix("glibc-").split("."))
    above: dict[str, tuple[int, ...]] = {}
    for name, source in sorted(selected.items()):
        path = scratch / source
        if _kind(path) != "elf":
            continue
        needed = read_elf_requirements(path).glibc
        if needed is not None and needed > floor:
            above[name] = needed
    if not above:
        return
    highest = max(above.values())
    worst = sorted(above.items(), key=lambda item: (item[1], item[0]), reverse=True)
    listed = ", ".join(f"{name} (glibc {'.'.join(map(str, version))})" for name, version in worst[:4])
    raise GlibcFloorError(
        f"the pinned llama-server archive for {pin.target} is built for a newer glibc than this package supports: "
        f"its files need glibc {'.'.join(map(str, highest))} and the {pin.target} floor is "
        f"glibc {'.'.join(map(str, floor))}; offending files: {listed}"
        f"{'' if len(above) <= 4 else f' and {len(above) - 4} more'}. "
        "Nothing is staged. Pin a Linux build made against the floor, or raise the floor by decision."
    )


def _discard_derived(destination: Path) -> None:
    for name in (PROGRAM_DIRECTORY, LICENSE_DIRECTORY, _EXTRACTION_DIRECTORY):
        path = destination / name
        if path.is_symlink() or path.is_junction():
            raise ArchiveMismatchError(f"derived llama-server state must not be a link: {path}")
        if path.is_dir():
            shutil.rmtree(path)
    (destination / RECEIPT_NAME).unlink(missing_ok=True)


def _cached(archive: Path, pin: ServerArchivePin) -> bool:
    if archive.is_symlink() or archive.is_junction() or not archive.is_file():
        return False
    try:
        verify_archive(archive.read_bytes(), pin)
    except ArchiveMismatchError:
        return False
    return True


def _obtain(destination: Path, pins: ServerPins, pin: ServerArchivePin, fetch: Fetch) -> bytes:
    """Return the verified archive bytes, kept in the build tree and fetched only when absent or damaged."""
    name = pin.url.rsplit("/", 1)[1]
    directory = destination / ARCHIVE_DIRECTORY
    archive = directory / name
    if _cached(archive, pin):
        return archive.read_bytes()
    directory.mkdir(parents=True, exist_ok=True)
    archive.unlink(missing_ok=True)
    content = fetch(pin, pins.hosts)
    verify_archive(content, pin)
    partial = archive.with_name(archive.name + ".partial")
    partial.write_bytes(content)
    partial.replace(archive)
    return content


def _tree_digests(root: Path) -> dict[str, str]:
    return {path.name: digest(path) for path in sorted(root.iterdir()) if path.is_file()} if root.is_dir() else {}


def acquire_llama_server(
    destination: Path, target: str, *, pins: ServerPins | None = None, fetch: Fetch = fetch_archive
) -> Path:
    """Fetch, verify and unpack the llama-server archive pinned for ``target`` into ``destination``.

    Raises:
        ArchiveMismatchError: The bytes differ from the pin, or the archive is unsafe or incomplete.
        GlibcFloorError: A Linux archive needs a newer glibc than the package floor.
    """
    pins = load_server_pins() if pins is None else pins
    pin = pin_for_target(pins, target)
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    content = _obtain(destination, pins, pin, fetch)
    _discard_derived(destination)
    scratch = destination / _EXTRACTION_DIRECTORY
    scratch.mkdir()
    base = PurePosixPath(pin.executable).parent
    links = _unpack_tar(content, base, scratch) if pin.format == "tar.gz" else _unpack_zip(content, base, scratch)
    for link in links:
        _resolve(link, links, scratch)
    executable = PurePosixPath(pin.executable).name
    selected, host = _select(scratch, links, executable)
    _require_glibc_floor(scratch, selected, pin)
    licenses = sorted(
        path.name for path in scratch.iterdir() if path.is_file() and _LICENSE.fullmatch(path.name) is not None
    )
    program, notices = destination / PROGRAM_DIRECTORY, destination / LICENSE_DIRECTORY
    program.mkdir()
    notices.mkdir()
    for name, source in sorted(selected.items()):
        shutil.copy2(scratch / source, program / name)
    for name in licenses:
        shutil.copy2(scratch / name, notices / name)
    receipt = LlamaServerReceipt.model_validate(
        {
            "schema": _RECEIPT_SCHEMA,
            "target": target,
            "tag": pins.tag,
            "backend": pin.backend,
            "url": pin.url,
            "archive_bytes": pin.download_bytes,
            "archive_sha256": pin.sha256,
            "executable": executable,
            "files": _tree_digests(program),
            "licenses": _tree_digests(notices),
            "host_libraries": list(host),
        }
    )
    (destination / RECEIPT_NAME).write_text(
        json.dumps(receipt.model_dump(by_alias=True), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    shutil.rmtree(scratch)
    return destination


def verify_acquired(source: Path, target: str, *, pins: ServerPins | None = None) -> LlamaServerReceipt:
    """Prove an acquired tree is exactly what its receipt names and what the committed pin pins for ``target``.

    Raises:
        ArchiveMismatchError: The receipt is missing or unreadable, names another archive than the pin,
            or the files differ from it.
    """
    pins = load_server_pins() if pins is None else pins
    pin = pin_for_target(pins, target)
    path = source / RECEIPT_NAME
    try:
        receipt = LlamaServerReceipt.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, ValidationError) as error:
        raise ArchiveMismatchError(
            f"the llama-server receipt is missing or unreadable at {path}; build the llama_server step"
        ) from error
    pinned = (
        target,
        pins.tag,
        pin.backend,
        pin.url,
        pin.download_bytes,
        pin.sha256,
        PurePosixPath(pin.executable).name,
    )
    recorded = (
        receipt.target,
        receipt.tag,
        receipt.backend,
        receipt.url,
        receipt.archive_bytes,
        receipt.archive_sha256,
        receipt.executable,
    )
    if receipt.schema_version != _RECEIPT_SCHEMA or recorded != pinned:
        raise ArchiveMismatchError(
            f"the acquired llama-server is not the archive pinned for {target}; build the llama_server step again"
        )
    if receipt.executable not in receipt.files:
        raise ArchiveMismatchError("the llama-server receipt names no program file for its executable")
    for directory, expected in ((PROGRAM_DIRECTORY, receipt.files), (LICENSE_DIRECTORY, receipt.licenses)):
        root = source / directory
        if root.is_symlink() or any(item.is_symlink() for item in root.rglob("*")):
            raise ArchiveMismatchError(f"the acquired llama-server holds a link under {directory}")
        if _tree_digests(root) != expected or len(list(root.rglob("*"))) != len(expected):
            raise ArchiveMismatchError(
                f"the acquired llama-server {directory} differ from the receipt; build the llama_server step again"
            )
    return receipt


def require_resolved_imports(program: Path) -> tuple[str, ...]:
    """Prove every library each PE image in ``program`` imports is the system's, the driver's or in ``program``.

    Returns the sorted case-folded names of the system and driver libraries the images import.

    Raises:
        UnresolvedImportError: An image imports a library that none of those provides, or the Vulkan loader
            from an image other than the Vulkan backend.
    """
    present = {path.name.casefold() for path in program.iterdir() if path.is_file()}
    system: set[str] = set()
    unresolved: list[str] = []
    for path in sorted(program.iterdir()):
        if not path.is_file() or _kind(path) != "pe":
            continue
        for name in sorted(pe_imports(path)):
            if name in present:
                continue
            if (
                name in SYSTEM_LIBRARIES
                or name.startswith(SYSTEM_PREFIXES)
                or path.name.casefold() in DRIVER_LIBRARIES.get(name, frozenset())
            ):
                system.add(name)
            else:
                unresolved.append(f"{path.name} imports {name}")
    if unresolved:
        raise UnresolvedImportError(
            f"the staged llama-server program in {program.name} imports libraries that neither the operating "
            f"system nor the program directory provides: {'; '.join(unresolved[:6])}"
            f"{'' if len(unresolved) <= 6 else f' and {len(unresolved) - 6} more'}"
        )
    return tuple(sorted(system))


def stage_llama_server(
    source: Path,
    root: Path,
    layout: Mapping[str, str],
    target: str,
    *,
    copy_function: Callable[[Path, Path], object] = shutil.copy2,
    pins: ServerPins | None = None,
    redistributable: Mapping[str, Path] | None = None,
) -> LlamaServerReceipt:
    """Copy the verified program files into the package's ``llama_server`` directory and its licences beside the others.

    ``layout`` is the package layout's ``paths``. The program directory must not exist yet in ``root``.
    ``redistributable`` maps the runtime libraries a Windows package carries beside the program to their
    verified files. Every PE image staged must then resolve its imports.
    """
    receipt = verify_acquired(source, target, pins=pins)
    program = root / layout["llama_server"]
    notices = root / layout["docs"] / "licenses" / "llama.cpp"
    for destination in (program, notices):
        if destination.exists():
            raise FileExistsError(f"the llama-server destination already exists: {destination}")
        destination.mkdir(parents=True)
    for name in receipt.files:
        copy_function(source / PROGRAM_DIRECTORY / name, program / name)
    for name, library in sorted((redistributable or {}).items()):
        if (program / name).exists():
            raise FileExistsError(f"the llama-server archive already holds the redistributable {name}")
        copy_function(library, program / name)
    require_resolved_imports(program)
    for name in receipt.licenses:
        copy_function(source / LICENSE_DIRECTORY / name, notices / name)
    return receipt


def read_receipt(source: Path) -> dict[str, object]:
    """Return the acquisition receipt as the package manifest records it."""
    receipt = LlamaServerReceipt.model_validate(json.loads((source / RECEIPT_NAME).read_text(encoding="utf-8")))
    return dict(receipt.model_dump(by_alias=True))
