"""Assemble the pinned standard library as a deterministic bytecode ZIP."""

from __future__ import annotations

import hashlib
import importlib.util
import marshal
import os
import struct
import sys
import zipfile
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BYTECODE_WORKERS = 12
"""Threads publishing package bytecode; the work is mostly reading, hashing and linking files."""


def bytecode(source: bytes, name: str, *, prefix: str = "python.zip") -> bytes:
    """Compile checked-hash bytecode with a portable package-relative filename."""
    code = compile(source, f"{prefix}/{name}", "exec", dont_inherit=True, optimize=0)
    return importlib.util.MAGIC_NUMBER + struct.pack("<I", 3) + importlib.util.source_hash(source) + marshal.dumps(code)


def compiler_identity() -> str:
    """Identify the bytecode producer as well as the exact interpreter."""
    return hashlib.sha256(Path(__file__).read_bytes() + sys.version.encode() + importlib.util.MAGIC_NUMBER).hexdigest()


def require_bytecode_compiler(version: str) -> None:
    """Refuse to compile bytecode for a ``version`` runtime unless this CPython may produce it.

    Bytecode is portable within a CPython minor, so the producer must share the
    runtime's minor and be at least as new as its patch.
    """
    required = tuple(map(int, version.split(".")))
    if required[:2] != sys.version_info[:2] or sys.version_info[:3] < required:
        raise ValueError("Bytecode assembly requires compatible development Python at least as new as the runtime")


def compile_packages_bytecode(
    source: Path,
    *,
    prefix: str,
    version: str,
    previous: Path | None = None,
    previous_files: Mapping[str, str] | None = None,
) -> None:
    """Publish caches with the same CPython minor and no older patch than the runtime."""
    require_bytecode_compiler(version)
    tag = sys.implementation.cache_tag
    files = sorted(source.rglob("*.py"))
    # Developer tools redirect cache_from_source through sys.pycache_prefix;
    # published bytecode belongs beside its source in the immutable package.
    for directory in sorted({file.parent / "__pycache__" for file in files}):
        directory.mkdir(parents=True, exist_ok=True)

    def publish(file: Path) -> None:
        destination = file.parent / "__pycache__" / f"{file.stem}.{tag}.pyc"
        destination.unlink(missing_ok=True)
        content = file.read_bytes()
        relative = destination.relative_to(source)
        old = None if previous is None else previous / relative
        expected = (previous_files or {}).get(f"{prefix}/{relative.as_posix()}")
        if (
            old is not None
            and expected is not None
            and old.is_file()
            and not any(path.is_symlink() or path.is_junction() for path in (old, *old.parents))
        ):
            cached = old.read_bytes()
            header = importlib.util.MAGIC_NUMBER + struct.pack("<I", 3) + importlib.util.source_hash(content)
            if cached[:16] == header and hashlib.sha256(cached).hexdigest() == expected:
                try:
                    os.link(old, destination)
                except OSError:
                    destination.write_bytes(cached)
                return
        destination.write_bytes(bytecode(content, file.relative_to(source).as_posix(), prefix=prefix))

    # Each file's cache is decided and written on its own, and most of the work
    # is reading and linking, so the files are taken by a pool of threads.
    with ThreadPoolExecutor(max_workers=BYTECODE_WORKERS, thread_name_prefix="bytecode") as pool:
        for future in [pool.submit(publish, file) for file in files]:
            future.result()


def bundle_identity(source: Path, excluded: list[str], bootstrap: dict[str, bytes], version: str) -> str:
    """Bind ZIP reuse to every selected source byte, compiler and exclusion."""
    identity = hashlib.sha256((compiler_identity() + version + repr(excluded)).encode())
    for file in sorted(source.rglob("*")):
        relative = file.relative_to(source)
        if not file.is_file() or any(part in excluded for part in relative.parts) or file.suffix == ".pyc":
            continue
        identity.update(relative.as_posix().encode() + b"\0" + hashlib.sha256(file.read_bytes()).digest())
    for name, content in sorted(bootstrap.items()):
        identity.update(name.encode() + b"\0" + hashlib.sha256(content).digest())
    return identity.hexdigest()


def bundle(source: Path, destination: Path, excluded: list[str], bootstrap: dict[str, bytes], version: str) -> None:
    """Keep runtime stdlib modules and resources; omit declared development components."""
    required = tuple(map(int, version.split(".")))
    if required[:2] != sys.version_info[:2] or sys.version_info[:3] < required:
        raise ValueError("Bytecode assembly requires compatible development Python at least as new as the runtime")
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(source.rglob("*")):
            relative = file.relative_to(source)
            if not file.is_file() or any(part in excluded for part in relative.parts) or file.suffix == ".pyc":
                continue
            name = relative.as_posix()
            content = file.read_bytes()
            if file.suffix == ".py":
                content = bytecode(content, name)
                name += "c"
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
        for module, source_bytes in bootstrap.items():
            info = zipfile.ZipInfo(module + ".pyc", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, bytecode(source_bytes, module + ".py"))
