"""Admit configured builder file identities before executing or reusing build actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .hashing import digest


def sysroot_inventory(root: Path, *, excluded: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Hash SDK files once, retaining contained link targets and refusing cycles or escapes."""
    root = root.resolve(strict=True)
    if not root.is_dir() or root == Path(root.anchor):
        raise ValueError("Sysroot must be an explicit SDK directory below the filesystem root")
    files: dict[str, str] = {}
    links: dict[str, dict[str, str]] = {}
    seen: set[Path] = set()
    entries = 0

    def visit(directory: Path, ancestors: frozenset[Path]) -> None:
        nonlocal entries
        canonical = directory.resolve(strict=True)
        if canonical in ancestors:
            raise ValueError("Sysroot contains a directory link cycle")
        if canonical in seen:
            return
        seen.add(canonical)
        for member in sorted(canonical.iterdir()):
            lexical = member.relative_to(root).as_posix()
            if lexical in excluded:
                continue
            entries += 1
            if entries > 250_000:
                raise ValueError("Sysroot exceeds the bounded SDK inventory limit")
            resolved = member.resolve(strict=True)
            if not resolved.is_relative_to(root):
                raise ValueError("Sysroot link escapes the selected SDK")
            relative = resolved.relative_to(root).as_posix()
            if member.is_symlink() or member.is_junction():
                links[lexical] = {
                    "text": os.readlink(member),
                    "target": relative,
                    "kind": "directory" if resolved.is_dir() else "file",
                }
            if resolved.is_dir():
                visit(resolved, ancestors | {canonical})
            elif resolved.is_file():
                if relative not in files:
                    files[relative] = digest(resolved)
            else:
                raise ValueError("Sysroot contains a special filesystem member")

    visit(root, frozenset())
    for record in links.values():
        if record["kind"] == "file":
            record["sha256"] = files[record["target"]]
    return {"schema": 1, "root": str(root), "files": files, "links": links}


def _inventory_bytes(inventory: Mapping[str, Any]) -> bytes:
    return (json.dumps(inventory, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_sysroot_inventory(root: Path, output: Path) -> dict[str, Any]:
    """Keep the complete SDK evidence in a builder sidecar and return one aggregate identity."""
    inventory = sysroot_inventory(root)
    content = _inventory_bytes(inventory)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.is_file() or output.read_bytes() != content:
        output.write_bytes(content)
    inputs = output.with_suffix(".inputs.txt")
    names = sorted(inventory["files"] | inventory["links"])
    inputs.write_text("".join((Path(inventory["root"]) / name).as_posix() + "\n" for name in names), encoding="utf-8")
    return {
        "root": inventory["root"],
        "inventory": str(output.resolve()),
        "sha256": hashlib.sha256(content).hexdigest(),
        "inputs": str(inputs.resolve()),
        "files": len(inventory["files"]),
    }


def builder_inputs(toolchain: Mapping[str, Any]) -> tuple[Path, ...]:
    """Validate selected compiler, SDK and wrapper bytes; never search the ambient PATH."""
    paths: list[Path] = []
    for name, record in toolchain.get("builder_files", {}).items():
        value = record.get("path")
        if not isinstance(value, str) or not Path(value).is_absolute() or not Path(value).is_file():
            raise ValueError(f"Selected builder input is missing: {name}; reconfigure CMake")
        path = Path(value)
        resolved = record.get("resolved")
        if not isinstance(resolved, str) or path.resolve(strict=True) != Path(resolved):
            raise ValueError(f"Selected builder input resolution changed: {name}; reconfigure CMake")
        link_text = os.readlink(path) if path.is_symlink() else ""
        if os.name == "nt":
            # CMake READ_SYMLINK removes the Win32 extended-path prefix.
            if link_text.startswith("\\\\?\\UNC\\"):
                link_text = "\\\\" + link_text[len("\\\\?\\UNC\\") :]
            else:
                link_text = link_text.removeprefix("\\\\?\\")
        if link_text != record.get("link_text"):
            raise ValueError(f"Selected builder input link changed: {name}; reconfigure CMake")
        if digest(path) != record.get("sha256"):
            raise ValueError(f"Selected builder input changed: {name}; reconfigure CMake")
        paths.append(path)
    for name, record in toolchain.get("sysroots", {}).items():
        inventory = Path(record["inventory"])
        if not inventory.is_absolute() or not inventory.is_file() or digest(inventory) != record["sha256"]:
            raise ValueError(f"Selected {name} inventory changed; reconfigure CMake")
        current = sysroot_inventory(Path(record["root"]))
        if hashlib.sha256(_inventory_bytes(current)).hexdigest() != record["sha256"]:
            raise ValueError(f"Selected {name} resources changed; reconfigure CMake")
        paths.append(inventory)
        root = Path(str(current["root"]))
        for member in sorted(current["files"]):
            if not isinstance(member, str):
                raise ValueError("Selected SDK inventory has a non-string member; reconfigure CMake")
            paths.append(root / member)
    decoder = toolchain.get("cpython_archive_decoder")
    if isinstance(decoder, dict):
        value = decoder.get("executable")
        if not isinstance(value, str) or not Path(value).is_absolute() or not Path(value).is_file():
            raise ValueError("Selected SDK archive decoder is missing; reconfigure CMake")
        path = Path(value)
        if digest(path) != decoder.get("sha256"):
            raise ValueError("Selected SDK archive decoder changed; reconfigure CMake")
        paths.append(path)
    return tuple(paths)


def selected_uv(toolchain: Mapping[str, Any] | None = None, *, executable: Path | None = None) -> str:
    """Use the admitted configured tool; standalone commands may select an explicit executable."""
    if toolchain is not None:
        record = toolchain.get("builder_files", {}).get("CADRUMO_UV")
        if not isinstance(record, dict) or record.get("path") != toolchain.get("CADRUMO_UV"):
            raise ValueError("Configured uv requires its selected builder identity; reconfigure CMake")
        if executable is not None and executable != Path(record["path"]):
            raise ValueError("Explicit uv differs from the configured builder selection")
        builder_inputs({"builder_files": {"CADRUMO_UV": record}})
        return str(record["path"])
    selected = str(executable) if executable is not None else shutil.which("uv")
    if selected is None:
        raise FileNotFoundError("uv is required")
    if not Path(selected).is_absolute() or not Path(selected).is_file():
        raise ValueError("uv requires an existing absolute builder executable")
    return selected


def native_toolchain_identity(toolchain: Mapping[str, Any]) -> str:
    """Name the selected native producer inputs without changing compiler flags or ABI."""
    selected = {
        "builder_files": {
            name: record
            for name, record in toolchain.get("builder_files", {}).items()
            if name != "CADRUMO_UV" and not name.startswith("desktop/")
        },
        "sysroots": toolchain.get("sysroots", {}),
        "target_configuration": toolchain.get("target_configuration", {}),
    }
    return hashlib.sha256(json.dumps(selected, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(write_sysroot_inventory(arguments.root, arguments.output)))
