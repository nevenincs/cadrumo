"""The shipped operation contract manifest reads back and renders to its own bytes in every process.

Set-valued contract fields iterate in the process's string hash order, so a
render that kept that order would change the file between runs and make the
drift gate flap. Each case renders in a fresh interpreter under a fixed seed.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.resources.bundled_data import packaged_data
from .. import contract_manifest
from ..contract_manifest import (
    OPERATION_CONTRACT_MANIFEST_PARTS,
    OperationContractManifestV1,
    load_operation_contract_manifest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_RENDER = """
import sys
from cadrumo.application.operations.contract_manifest import load_operation_contract_manifest
sys.stdout.buffer.write(load_operation_contract_manifest().render().encode("utf-8"))
"""

#: Only what the platform needs to start an interpreter passes through; the
#: child's home, storage and scratch locations are the test's own directory.
_PLATFORM_VARIABLES = frozenset({"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "COMSPEC"})


def _shipped() -> bytes:
    return packaged_data(*OPERATION_CONTRACT_MANIFEST_PARTS).read_bytes().replace(b"\r\n", b"\n")


def _child_environment(root: Path, seed: str) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if key.upper() in _PLATFORM_VARIABLES}
    environment.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(root / "storage"),
            "CADRUMO_STORAGE_ROOT": str(root / "storage"),
            "PYDANTIC_DISABLE_PLUGINS": "__all__",
            "PYTHONHASHSEED": seed,
            "HOME": str(root),
            "USERPROFILE": str(root),
            "APPDATA": str(root),
            "LOCALAPPDATA": str(root),
            "TEMP": str(root),
            "TMP": str(root),
        }
    )
    return environment


async def _render_under(root: Path, seed: str) -> bytes:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-B",
        "-c",
        _RENDER,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=root,
        env=_child_environment(root, seed),
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=None)
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
    assert process.returncode == 0, stderr.decode()
    return stdout


def test_the_shipped_manifest_validates_and_renders_to_its_own_bytes() -> None:
    manifest = load_operation_contract_manifest()
    assert manifest.render().encode("utf-8") == _shipped()
    assert set(manifest.groups) == {entry.group for entry in manifest.operations}


@pytest.mark.asyncio
@pytest.mark.parametrize("seed", ["0", "1", "4711"])
async def test_rendering_does_not_depend_on_the_hash_seed(tmp_path: Path, seed: str) -> None:
    assert await _render_under(tmp_path, seed) == _shipped()


def test_a_set_field_carries_more_than_one_member_so_the_seed_cases_can_differ() -> None:
    manifest = load_operation_contract_manifest()
    assert any(len(entry.contract.permitted_effects) > 1 for entry in manifest.operations)


@pytest.mark.parametrize("defect", ["version", "digest", "duplicate", "empty", "truncated"])
def test_invalid_manifest_bytes_refuse_before_a_registry_can_be_bound(defect: str) -> None:
    document = json.loads(_shipped())
    if defect == "version":
        document["manifest_version"] = 2
    elif defect == "digest":
        document["contract_set_digest"] = "0" * 64
    elif defect == "duplicate":
        document["operations"].insert(0, document["operations"][0])
    elif defect == "empty":
        document["operations"] = []
    payload = json.dumps(document).encode()
    if defect == "truncated":
        payload = payload[: len(payload) // 2]
    with pytest.raises(ValidationError):
        OperationContractManifestV1.model_validate_json(payload)


def test_a_missing_shipped_manifest_refuses_loading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_resource(*parts: str) -> Path:
        assert parts == OPERATION_CONTRACT_MANIFEST_PARTS
        return tmp_path / "missing-contract-manifest.json"

    load_operation_contract_manifest.cache_clear()
    monkeypatch.setattr(contract_manifest, "packaged_data", missing_resource)
    try:
        with pytest.raises(FileNotFoundError):
            load_operation_contract_manifest()
    finally:
        load_operation_contract_manifest.cache_clear()
