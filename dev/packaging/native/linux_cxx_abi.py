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
from pathlib import Path, PurePosixPath
from typing import Any

from ..command_execution import run_command
from ..runtime_wheelhouse_contract import target_platform
from .hashing import digest
from .linux_cxx_versions import ReadelfVersions, parse_readelf_versions
from .package_inventory import checked_member, package_inventory

SCHEMA = "cadrumo.linux-cxx-floor.v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_IMAGE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:+-]*@sha256:[0-9a-f]{64}")

_SONAME = "libstdc++.so.6"


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


def _read_versions(tool: Path, tool_sha256: str, path: Path) -> tuple[ReadelfVersions, str]:
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
    return parse_readelf_versions(result.stdout), hashlib.sha256(result.stdout.encode("utf-8")).hexdigest()


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
    _require_floor_proof_identity(proof, policy.name, policy.floor, admitted_image)
    provider = _fields(proof["provider"], {"path", "sha256", "source_path", "soname", "elf_machine"}, "floor provider")
    if provider["soname"] != _SONAME or type(provider["elf_machine"]) is not int or provider["elf_machine"] != machine:
        raise ValueError("Floor-provider SONAME/ELF machine mismatch")
    _require_floor_source_path(provider["source_path"])
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
    _require_admitted_readelf(
        readelf, readelf_sha256, manifest["inputs"]["build_toolchain"]["native_tool_sha256"].get("readelf")
    )
    definitions, provider_output_sha256 = _read_versions(readelf, readelf_sha256, path)
    if definitions.bases != {_SONAME}:
        raise ValueError("Floor-provider ELF version BASE does not identify libstdc++.so.6")
    exported = _floor_exported_versions(definitions)
    inventory = package_inventory(package, manifest)
    allowed = set(inventory)
    manifest_member = manifest["layout"].get("files", {}).get("package_manifest")
    if isinstance(manifest_member, str):
        allowed.add(checked_member(manifest_member))
    _require_delivered_inventory(package, inventory, allowed)
    images: dict[str, Any] = {}
    for relative, expected_sha256 in sorted(inventory.items()):
        image_evidence = _verify_inventory_elf(
            package, relative, expected_sha256, machine, readelf, readelf_sha256, exported
        )
        if image_evidence is not None:
            images[relative] = image_evidence
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


def _require_floor_source_path(source: object) -> None:
    if (
        not isinstance(source, str)
        or not PurePosixPath(source).is_absolute()
        or ".." in PurePosixPath(source).parts
        or "\\" in source
        or any(ord(character) < 0x20 for character in source)
        or not PurePosixPath(source).name.startswith(_SONAME)
    ):
        raise ValueError("Floor-provider source_path must identify its resolved system library")


def _require_delivered_inventory(package: Path, inventory: Mapping[str, str], allowed: set[str]) -> None:
    observed: set[str] = set()
    for member in package.rglob("*"):
        if member.is_symlink() or member.is_junction():
            raise ValueError(f"Package inventory contains a linked member: {member}")
        if member.is_file():
            observed.add(member.relative_to(package).as_posix())
        elif not member.is_dir():
            raise ValueError(f"Package inventory contains a special member: {member}")
    if not set(inventory) <= observed or observed - allowed:
        raise ValueError("Delivered files differ from the declared package inventory")


def _verify_inventory_elf(
    package: Path,
    relative: str,
    expected_sha256: str,
    machine: int,
    readelf: Path,
    readelf_sha256: str,
    exported: set[str],
) -> dict[str, object] | None:
    image = _member(package, relative)
    _unchanged(image, expected_sha256, "package member")
    if image.name == _SONAME:
        raise ValueError(f"Bundled image shadows system libstdc++ provider: {relative}")
    with image.open("rb") as stream:
        if stream.read(4) != b"\x7fELF":
            return None
    _elf_machine(image, machine)
    versions, output_sha256 = _read_versions(readelf, readelf_sha256, image)
    if _SONAME in versions.bases:
        raise ValueError(f"Bundled ELF shadows system libstdc++ provider: {relative}")
    required: set[str] = set()
    for dependency, names in versions.needs.items():
        cxx = {name for name in names if name.startswith(("GLIBCXX_", "CXXABI_"))}
        if cxx and dependency != _SONAME:
            raise ValueError(f"C++ ABI requirement names a different provider: {relative}: {dependency}")
        required.update(cxx)
    missing = sorted(required - exported)
    if missing:
        raise ValueError(f"ELF requires C++ ABI versions absent from target-floor provider: {relative}: {missing}")
    _unchanged(image, expected_sha256, "package member")
    return {"sha256": expected_sha256, "required": sorted(required), "readelf_sha256": output_sha256}


def _require_floor_proof_identity(
    proof: Mapping[str, object], target_name: str, floor: str, admitted_image: str
) -> None:
    if proof["schema"] != SCHEMA or proof["target"] != target_name or proof["floor"] != floor:
        raise ValueError("Floor-provider proof schema/target/floor mismatch")
    if not isinstance(proof["image"], str) or not _IMAGE.fullmatch(proof["image"]):
        raise ValueError("Floor-provider proof requires a digest-pinned source image")
    if not isinstance(admitted_image, str) or not _IMAGE.fullmatch(admitted_image) or proof["image"] != admitted_image:
        raise ValueError("Floor-provider image differs from separately admitted target-floor image")


def _floor_exported_versions(definitions: ReadelfVersions) -> set[str]:
    exported = {name for name in definitions.definitions if name.startswith(("GLIBCXX_", "CXXABI_"))}
    if any(not any(name.startswith(prefix) for name in exported) for prefix in ("GLIBCXX_", "CXXABI_")):
        raise ValueError("Floor provider lacks GLIBCXX/CXXABI version definitions")
    return exported


def _require_admitted_readelf(readelf: Path, readelf_sha256: str, admitted_tool: object) -> None:
    if not readelf.is_absolute():
        raise ValueError("C++ floor readelf must be an explicit absolute path")
    if readelf_sha256 != admitted_tool:
        raise ValueError("readelf tool SHA-256 differs from package build provenance")
