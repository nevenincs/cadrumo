"""The shipped operation contract manifest against the real registry it describes.

The eager production registry is the validation authority: the shipped
manifest must equal what it generates, fingerprints included. The
manifest-backed registry answers contracts without composing any operation,
composes one group on first use, and refuses a group that no longer
reproduces the manifest.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest

from ...application.operations.contract_manifest import (
    OPERATION_CONTRACT_MANIFEST_PARTS,
    OperationContractManifestEntryV1,
    OperationContractManifestV1,
    load_operation_contract_manifest,
)
from ...core.errors.hierarchy import InternalInvariantError
from ...core.resources.bundled_data import packaged_data
from ..operation_composition import build_manifest_operation_registry, build_production_operation_contract_manifest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: A small group whose single operation composes cheaply.
_GROUP = "application.user_profile.recovery_status_operation"


def _entry_in(manifest: OperationContractManifestV1, group: str) -> OperationContractManifestEntryV1:
    return next(entry for entry in manifest.operations if entry.group == group)


def _with_entry(
    manifest: OperationContractManifestV1, replacement: OperationContractManifestEntryV1
) -> OperationContractManifestV1:
    """Return the manifest with one entry replaced, as a stale shipped file would record it."""
    operations = tuple(
        replacement if entry.contract.definition_id == replacement.contract.definition_id else entry
        for entry in manifest.operations
    )
    return OperationContractManifestV1.model_construct(
        manifest_version=manifest.manifest_version,
        contract_set_digest=manifest.contract_set_digest,
        operations=operations,
    )


def test_shipped_manifest_matches_the_eager_registry() -> None:
    shipped = packaged_data(*OPERATION_CONTRACT_MANIFEST_PARTS).read_bytes().replace(b"\r\n", b"\n")
    assert shipped.decode("utf-8") == build_production_operation_contract_manifest().render()


def test_every_shipped_group_is_a_composition_group_that_reproduces_it() -> None:
    manifest = load_operation_contract_manifest()
    registry = build_manifest_operation_registry()
    for group, definition_ids in manifest.groups.items():
        for definition_id in sorted(definition_ids):
            assert registry.lookup(definition_id).definition_id == definition_id, group
            assert (
                registry.lookup_public_registration(definition_id).contract == manifest.entries[definition_id].contract
            )


def test_contracts_are_answered_from_the_manifest() -> None:
    manifest = load_operation_contract_manifest()
    registry = build_manifest_operation_registry(manifest=manifest)
    assert registry.public_contract_set == manifest.contract_set
    for entry in manifest.operations:
        assert registry.lookup_public_contract(entry.contract.definition_id) == entry.contract


def test_a_manifest_recording_an_outdated_contract_refuses_composition() -> None:
    manifest = load_operation_contract_manifest()
    entry = _entry_in(manifest, _GROUP)
    stale_contract = entry.contract.model_copy(
        update={"ephemeral_secret_required": not entry.contract.ephemeral_secret_required}
    )
    stale = _with_entry(manifest, entry.model_copy(update={"contract": stale_contract}))
    registry = build_manifest_operation_registry(manifest=stale)
    with pytest.raises(InternalInvariantError, match="no longer matches the contract manifest"):
        registry.lookup(entry.contract.definition_id)


def test_a_manifest_naming_the_wrong_group_refuses_composition() -> None:
    manifest = load_operation_contract_manifest()
    entry = _entry_in(manifest, _GROUP)
    moved = _with_entry(manifest, entry.model_copy(update={"group": "application.user_profile.operations"}))
    registry = build_manifest_operation_registry(manifest=moved)
    with pytest.raises(InternalInvariantError, match="does not compose what the contract manifest names"):
        registry.lookup(entry.contract.definition_id)


def test_a_manifest_naming_an_unknown_group_refuses_composition() -> None:
    manifest = load_operation_contract_manifest()
    entry = _entry_in(manifest, _GROUP)
    renamed = _with_entry(manifest, entry.model_copy(update={"group": "application.retired_operation"}))
    registry = build_manifest_operation_registry(manifest=renamed)
    with pytest.raises(InternalInvariantError, match="no operation composition group"):
        registry.lookup(entry.contract.definition_id)


_CONTRACT_READ_PROBE = """
import json
import sys

from cadrumo.application.operations.contract_manifest import load_operation_contract_manifest
from cadrumo.entrypoints.operation_composition import build_manifest_operation_registry

manifest = load_operation_contract_manifest()
registry = build_manifest_operation_registry()
assert registry.public_contract_set.definitions
for entry in manifest.operations:
    registry.lookup_public_contract(entry.contract.definition_id)
registry.ephemeral_secret_lifetimes()
registry.declares_transient_financial_operands()
owned = {entry.module for entry in manifest.operations} | {"cadrumo." + entry.group for entry in manifest.operations}
after_contracts = sorted(owned.intersection(sys.modules))
used = next(entry for entry in manifest.operations if entry.group == sys.argv[1])
registry.lookup(used.contract.definition_id)
after_one_group = sorted(owned.intersection(sys.modules))
print(json.dumps([after_contracts, after_one_group, "cadrumo." + used.group, used.module]))
"""


@pytest.mark.asyncio
async def test_reading_every_contract_imports_no_operation_handler_module() -> None:
    """The module-graph gate: contract readers import no handler; one use composes only its group."""
    environment = {key: value for key, value in os.environ.items() if key.upper() in _PLATFORM_VARIABLES}
    environment["PYDANTIC_DISABLE_PLUGINS"] = "__all__"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-c",
        _CONTRACT_READ_PROBE,
        _GROUP,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=environment,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=None)
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
    assert process.returncode == 0, stderr.decode()
    after_contracts, after_one_group, group_module, handler_module = json.loads(stdout.decode().splitlines()[-1])
    assert after_contracts == []
    assert group_module in after_one_group
    assert handler_module in after_one_group
    assert set(after_one_group) <= {group_module, handler_module}


_PLATFORM_VARIABLES = frozenset({"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "COMSPEC", "USERNAME", "USERDOMAIN"})
