"""Admit Linux C++ ABI requirements against explicit target-floor provider bytes.

The provider proof is a build/verification input, never a runtime dependency or
host-library discovery instruction. Its SHA-256 must be admitted by the caller.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from ..command_execution import run_command
from ..runtime_wheelhouse_contract import target_platform
from .hashing import digest
from .package_inventory import checked_member, package_inventory

SCHEMA = "cadrumo.linux-cxx-floor.v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_IMAGE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:+-]*@sha256:[0-9a-f]{64}")
_SECTION = re.compile(r"Version (definition|needs|symbols) section '[^']+' contains (\d+) entr(?:y|ies):")
_DEFINITION = re.compile(
    r"\s*(?:0x)?[0-9a-fA-F]+:\s+Rev: \d+\s+Flags: (.*?)\s+Index: \d+\s+Cnt: \d+\s+Name: ([A-Za-z0-9_.+-]+)"
)
_NEED = re.compile(r"\s*(?:0x)?[0-9a-fA-F]+:\s+Version: \d+\s+File: (\S+)\s+Cnt: (\d+)")
_NAME = re.compile(r"\s*(?:0x)?[0-9a-fA-F]+:\s+Name: ([A-Za-z0-9_.+-]+)\s+Flags: .*?\s+Version: \d+")
_PARENT = re.compile(r"\s*(?:0x)?[0-9a-fA-F]+:\s+Parent \d+: [A-Za-z0-9_.+-]+")
_SYMBOL_ROW = re.compile(r"\s*([0-9a-fA-F]+):(.*)")
_SYMBOL = re.compile(r"\s*[0-9a-fA-F]+h?\s*\(([^()\s]+)\)")
_SONAME = "libstdc++.so.6"


@dataclass(frozen=True)
class _Versions:
    needs: dict[str, set[str]]
    definitions: set[str]
    bases: set[str]


def _versions(output: str) -> _Versions:
    """Parse GNU readelf sections, including their declared entry/name counts."""
    needs: dict[str, set[str]] = {}
    definitions: set[str] = set()
    bases: set[str] = set()
    symbol_names: set[str] = set()
    mode: str | None = None
    expected = seen = group_expected = group_seen = 0
    dependency: str | None = None
    recognized = False

    def finish_group() -> None:
        if dependency is not None and group_expected != group_seen:
            raise ValueError("Truncated readelf version-needs group")

    def finish_section() -> None:
        if mode is not None:
            finish_group()
            if expected != seen:
                raise ValueError("Truncated readelf version section")

    for line in output.splitlines():
        if line.startswith("Version "):
            finish_section()
            section = _SECTION.fullmatch(line)
            mode = None
            dependency = None
            if section:
                mode = str(section[1])
                expected, seen = int(section[2]), 0
                recognized = True
            elif line.startswith(("Version definition section", "Version needs section", "Version symbols section")):
                raise ValueError("Malformed readelf version section")
            continue
        if line == "No version information found in this file.":
            recognized = True
            continue
        if mode is None:
            if "Name: GLIBCXX_" in line or "Name: CXXABI_" in line:
                raise ValueError("C++ ABI name outside a readelf version section")
            continue
        if not line.strip() or line.lstrip().startswith("Addr:"):
            continue
        if mode == "symbols":
            row = _SYMBOL_ROW.fullmatch(line)
            if not row or int(row[1], 16) != seen:
                raise ValueError("Malformed readelf version-symbols row")
            entries = _SYMBOL.findall(row[2])
            if not entries or _SYMBOL.sub("", row[2]).strip():
                raise ValueError("Malformed readelf version symbol")
            symbol_names.update(name for name in entries if name not in {"*local*", "*global*"})
            seen += len(entries)
        elif mode == "definition":
            definition = _DEFINITION.fullmatch(line)
            if definition:
                flags, name = definition.groups()
                if name in definitions:
                    raise ValueError("Duplicate readelf version definition")
                definitions.add(name)
                if "BASE" in flags.split():
                    bases.add(name)
                seen += 1
            elif not _PARENT.fullmatch(line):
                raise ValueError("Malformed readelf version definition")
        else:
            group = _NEED.fullmatch(line)
            name = _NAME.fullmatch(line)
            if group:
                finish_group()
                dependency = str(group[1])
                if dependency in needs:
                    raise ValueError("Duplicate readelf version-needs provider")
                needs[dependency] = set()
                group_expected, group_seen = int(group[2]), 0
                seen += 1
            elif name and dependency is not None:
                value = name[1]
                if value in needs[dependency]:
                    raise ValueError("Duplicate readelf required version")
                needs[dependency].add(value)
                group_seen += 1
            else:
                raise ValueError("Malformed readelf version need")
    finish_section()
    if not recognized:
        raise ValueError("Missing readelf version information")
    declared = definitions.union(*(names for names in needs.values()))
    if symbol_names - declared:
        raise ValueError("Readelf symbols reference missing version definitions/needs")
    return _Versions(needs, definitions, bases)


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate floor-provider proof field: {key}")
        result[key] = value
    return result


def _fields(value: object, keys: set[str], owner: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"Malformed {owner} fields")
    return value


def _unchanged(path: Path, expected: object, owner: str) -> None:
    if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
        raise ValueError(f"Missing or malformed {owner} SHA-256")
    if not path.is_file() or digest(path) != expected:
        raise ValueError(f"{owner} bytes differ from admitted SHA-256: {path}")


def _member(root: Path, relative: object) -> Path:
    if not isinstance(relative, str):
        raise ValueError("Floor-provider/package member must be a relative string")
    path = root
    for part in checked_member(relative).split("/"):
        path /= part
        if path.is_symlink() or path.is_junction():
            raise ValueError(f"Floor-provider/package member is linked: {relative}")
    if not path.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
        raise ValueError(f"Floor-provider/package member escapes its root: {relative}")
    return path


def _elf_machine(path: Path, machine: int) -> None:
    with path.open("rb") as stream:
        header = stream.read(20)
    if len(header) != 20 or header[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", header, 18)[0] != machine:
        raise ValueError(f"Wrong target ELF architecture or ABI: {path}")


def _read_versions(tool: Path, tool_sha256: str, path: Path) -> tuple[_Versions, str]:
    _unchanged(tool, tool_sha256, "readelf tool")
    result = run_command(
        [str(tool), "--version-info", "--wide", str(path)],
        cwd=path.parent,
        environment=dict(os.environ, LC_ALL="C"),
        timeout_seconds=30,
    )
    _unchanged(tool, tool_sha256, "readelf tool")
    if result.returncode:
        raise ValueError(f"readelf failed for {path}: {result.stderr}")
    return _versions(result.stdout), hashlib.sha256(result.stdout.encode("utf-8")).hexdigest()


def admit_linux_cxx_proof(
    provider_evidence: Path,
    provider_evidence_sha256: str,
    *,
    target: str,
    admitted_image: str,
) -> tuple[dict[str, Any], Path]:
    """Admit the explicit proof/provider inputs for configure and artifact verification.

    Proof schema has exactly ``schema,target,floor,image,provider``. Provider has
    exactly ``path,sha256,source_path,soname,elf_machine``; its path is relative
    to the proof directory. ``source_path`` records the original resolved floor
    system file. Exports are recomputed from those actual retained bytes.
    """
    policy = target_platform(target)
    if policy.sys_platform != "linux":
        raise ValueError("C++ floor admission requires a canonical Linux target")
    machine = {"x86_64": 62, "aarch64": 183}[policy.platform_machine]
    if not provider_evidence.is_absolute():
        raise ValueError("C++ floor proof must be an explicit absolute path")
    _unchanged(provider_evidence, provider_evidence_sha256, "floor-provider proof")
    proof = _fields(
        json.loads(provider_evidence.read_text(encoding="utf-8"), object_pairs_hook=_object),
        {"schema", "target", "floor", "image", "provider"},
        "floor-provider proof",
    )
    if proof["schema"] != SCHEMA or proof["target"] != policy.name or proof["floor"] != policy.floor:
        raise ValueError("Floor-provider proof schema/target/floor mismatch")
    if not isinstance(proof["image"], str) or not _IMAGE.fullmatch(proof["image"]):
        raise ValueError("Floor-provider proof requires a digest-pinned source image")
    if not isinstance(admitted_image, str) or not _IMAGE.fullmatch(admitted_image) or proof["image"] != admitted_image:
        raise ValueError("Floor-provider image differs from separately admitted target-floor image")
    provider = _fields(proof["provider"], {"path", "sha256", "source_path", "soname", "elf_machine"}, "floor provider")
    if provider["soname"] != _SONAME or type(provider["elf_machine"]) is not int or provider["elf_machine"] != machine:
        raise ValueError("Floor-provider SONAME/ELF machine mismatch")
    source = provider["source_path"]
    if (
        not isinstance(source, str)
        or not PurePosixPath(source).is_absolute()
        or ".." in PurePosixPath(source).parts
        or "\\" in source
        or any(ord(character) < 0x20 for character in source)
        or not PurePosixPath(source).name.startswith(_SONAME)
    ):
        raise ValueError("Floor-provider source_path must identify its resolved system library")
    path = _member(provider_evidence.parent, provider["path"])
    _unchanged(path, provider["sha256"], "floor provider")
    _elf_machine(path, machine)
    _unchanged(path, provider["sha256"], "floor provider")
    _unchanged(provider_evidence, provider_evidence_sha256, "floor-provider proof")
    return proof, path


def verify_linux_cxx_abi(
    package: Path,
    manifest: Mapping[str, Any],
    *,
    provider_evidence: Path,
    provider_evidence_sha256: str,
    admitted_image: str,
    readelf: Path,
    readelf_sha256: str,
) -> dict[str, Any]:
    """Check every delivered ELF against the reviewed floor provider, refusing missing evidence."""
    target = target_platform(manifest["build"]["target"])
    if target.sys_platform != "linux" or manifest["layout"]["platform"] != target.name:
        raise ValueError("C++ floor admission requires a canonical Linux target")
    if _SONAME not in manifest["layout"]["native_system_libraries"]:
        raise ValueError("C++ floor admission requires the declared system libstdc++ policy")
    machine = {"x86_64": 62, "aarch64": 183}[target.platform_machine]
    proof, path = admit_linux_cxx_proof(
        provider_evidence, provider_evidence_sha256, target=target.name, admitted_image=admitted_image
    )
    provider = proof["provider"]
    if not readelf.is_absolute():
        raise ValueError("C++ floor readelf must be an explicit absolute path")
    admitted_tool = manifest["inputs"]["build_toolchain"]["native_tool_sha256"].get("readelf")
    if readelf_sha256 != admitted_tool:
        raise ValueError("readelf tool SHA-256 differs from package build provenance")
    definitions, provider_output_sha256 = _read_versions(readelf, readelf_sha256, path)
    if definitions.bases != {_SONAME}:
        raise ValueError("Floor-provider ELF version BASE does not identify libstdc++.so.6")
    exported = {name for name in definitions.definitions if name.startswith(("GLIBCXX_", "CXXABI_"))}
    if any(not any(name.startswith(prefix) for name in exported) for prefix in ("GLIBCXX_", "CXXABI_")):
        raise ValueError("Floor provider lacks GLIBCXX/CXXABI version definitions")
    inventory = package_inventory(package, manifest)
    allowed = set(inventory)
    manifest_member = manifest["layout"].get("files", {}).get("package_manifest")
    if isinstance(manifest_member, str):
        allowed.add(checked_member(manifest_member))
    observed = set()
    for member in package.rglob("*"):
        if member.is_symlink() or member.is_junction():
            raise ValueError(f"Package inventory contains a linked member: {member}")
        if member.is_file():
            observed.add(member.relative_to(package).as_posix())
        elif not member.is_dir():
            raise ValueError(f"Package inventory contains a special member: {member}")
    if not set(inventory) <= observed or observed - allowed:
        raise ValueError("Delivered files differ from the declared package inventory")
    images: dict[str, Any] = {}
    for relative, expected_sha256 in sorted(inventory.items()):
        image = _member(package, relative)
        _unchanged(image, expected_sha256, "package member")
        if image.name == _SONAME:
            raise ValueError(f"Bundled image shadows system libstdc++ provider: {relative}")
        with image.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        _elf_machine(image, machine)
        versions, output_sha256 = _read_versions(readelf, readelf_sha256, image)
        if _SONAME in versions.bases:
            raise ValueError(f"Bundled ELF shadows system libstdc++ provider: {relative}")
        required = set()
        for dependency, names in versions.needs.items():
            cxx = {name for name in names if name.startswith(("GLIBCXX_", "CXXABI_"))}
            if cxx and dependency != _SONAME:
                raise ValueError(f"C++ ABI requirement names a different provider: {relative}: {dependency}")
            required.update(cxx)
        missing = sorted(required - exported)
        if missing:
            raise ValueError(f"ELF requires C++ ABI versions absent from target-floor provider: {relative}: {missing}")
        _unchanged(image, expected_sha256, "package member")
        images[relative] = {"sha256": expected_sha256, "required": sorted(required), "readelf_sha256": output_sha256}
    if not images:
        raise ValueError("Package inventory contains no target ELF images")
    _unchanged(path, provider["sha256"], "floor provider")
    _unchanged(provider_evidence, provider_evidence_sha256, "floor-provider proof")
    return {
        "schema": SCHEMA,
        "target": target.name,
        "floor": target.floor,
        "image": proof["image"],
        "proof_sha256": provider_evidence_sha256,
        "provider_sha256": provider["sha256"],
        "provider_source_path": provider["source_path"],
        "elf_machine": machine,
        "tool_sha256": readelf_sha256,
        "provider_readelf_sha256": provider_output_sha256,
        "exported": sorted(exported),
        "images": images,
        "passed": True,
    }
