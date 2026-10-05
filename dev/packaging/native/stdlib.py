"""Assemble the pinned standard library as a deterministic bytecode ZIP."""

from __future__ import annotations

import importlib.util
import marshal
import struct
import sys
import zipfile
from pathlib import Path


def bytecode(source: bytes, name: str) -> bytes:
    """Use hash-based legacy pyc entries, understood directly by zipimport."""
    code = compile(source, f"python.zip/{name}", "exec", dont_inherit=True)
    return importlib.util.MAGIC_NUMBER + struct.pack("<I", 3) + importlib.util.source_hash(source) + marshal.dumps(code)


def bundle(source: Path, destination: Path, excluded: list[str], bootstrap: dict[str, bytes], version: str) -> None:
    """Keep runtime stdlib modules and resources; omit declared development components."""
    if tuple(map(int, version.split("."))) != sys.version_info[:3]:
        raise ValueError("Bytecode assembly requires the exact pinned development Python")
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
