"""Project explicit Linux floor evidence into configured artifact verification."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dev._paths import REPO_ROOT

from ..runtime_wheelhouse_contract import target_platform
from .build_toolchain import builder_inputs
from .hashing import digest
from .linux_cxx_abi import admit_linux_cxx_proof, verify_linux_cxx_abi
from .target import toolchain_for_target

_FIELDS = {"target", "floor", "admitted_image", "proof", "proof_sha256", "provider", "provider_sha256"}


def _floor(target: str, root: Path) -> dict[str, str]:
    policy = target_platform(target)
    pin = toolchain_for_target(target, root=root).get("cpp_abi_floor")
    if policy.sys_platform != "linux" or not isinstance(pin, dict) or set(pin) != {"floor", "image"}:
        raise ValueError("Linux C++ ABI verification requires separately admitted target-floor pins")
    if pin["floor"] != policy.floor or not isinstance(pin["image"], str):
        raise ValueError("Linux C++ ABI floor pin differs from the canonical target")
    return {"floor": policy.floor, "image": pin["image"]}


def linux_cpp_abi_inputs(target: str, proof: Path, *, root: Path = REPO_ROOT) -> dict[str, Any]:
    """Admit the declared provider bytes without discovering a host system library."""
    pin = _floor(target, root)
    if not proof.is_absolute() or not proof.is_file():
        raise ValueError("Supply an existing absolute Linux C++ ABI proof path")
    proof_sha256 = digest(proof)
    declaration, provider = admit_linux_cxx_proof(proof, proof_sha256, target=target, admitted_image=pin["image"])
    return {
        "target": target,
        "floor": pin["floor"],
        "admitted_image": pin["image"],
        "proof": str(proof),
        "proof_sha256": proof_sha256,
        "provider": str(provider),
        "provider_sha256": declaration["provider"]["sha256"],
    }


def verify_linux_cpp_abi_inputs(
    package: Path,
    manifest: Mapping[str, Any],
    configured: Mapping[str, Any],
    *,
    root: Path = REPO_ROOT,
) -> dict[str, Any] | None:
    """Require configured proof/tool identities before executing a Linux package image."""
    target = manifest["build"]["target"]
    if target_platform(target).sys_platform != "linux":
        return None
    selection = configured.get("linux_cpp_abi")
    if not isinstance(selection, dict) or set(selection) != _FIELDS:
        raise ValueError("Linux artifact verification requires CADRUMO_LINUX_CPP_ABI_PROOF; reconfigure CMake")
    pin = _floor(target, root)
    if (
        selection["target"] != target
        or selection["floor"] != pin["floor"]
        or selection["admitted_image"] != pin["image"]
    ):
        raise ValueError("Configured Linux C++ ABI target-floor admission differs from canonical pins")
    shipped = manifest.get("inputs", {}).get("build_toolchain", {})
    if shipped.get("linux_cpp_abi") != selection:
        raise ValueError("Packaged Linux C++ ABI evidence differs from the configured builder")
    labels = {
        "linux_cpp_abi/proof": (selection["proof"], selection["proof_sha256"]),
        "linux_cpp_abi/provider": (selection["provider"], selection["provider_sha256"]),
        "native/readelf": (
            configured.get("native_tools", {}).get("readelf"),
            configured.get("native_tool_sha256", {}).get("readelf"),
        ),
    }
    records = {}
    for name, (path, sha256) in labels.items():
        record = configured.get("builder_files", {}).get(name)
        if not isinstance(record, dict) or record.get("path") != path or record.get("sha256") != sha256:
            raise ValueError(f"Linux C++ ABI input lacks its configured builder identity: {name}")
        if shipped.get("builder_files", {}).get(name) != record:
            raise ValueError(f"Packaged Linux C++ ABI builder input differs: {name}")
        records[name] = record
    builder_inputs({"builder_files": records})
    proof = Path(selection["proof"])
    declaration, provider = admit_linux_cxx_proof(
        proof, selection["proof_sha256"], target=target, admitted_image=pin["image"]
    )
    if str(provider) != selection["provider"] or declaration["provider"]["sha256"] != selection["provider_sha256"]:
        raise ValueError("Configured Linux C++ ABI provider differs from the admitted proof")
    result = verify_linux_cxx_abi(
        package,
        manifest,
        provider_evidence=proof,
        provider_evidence_sha256=selection["proof_sha256"],
        admitted_image=pin["image"],
        readelf=Path(labels["native/readelf"][0]),
        readelf_sha256=labels["native/readelf"][1],
    )
    builder_inputs({"builder_files": records})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    print(json.dumps(linux_cpp_abi_inputs(args.target, args.proof, root=args.root)))
