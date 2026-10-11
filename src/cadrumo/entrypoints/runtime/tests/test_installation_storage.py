"""The storage acts, served by the real runtime over a real storage root, do the command line's work."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation_client import RuntimeInstallationClient
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.runtime.installation_requests import (
    InstallationAct,
    RuntimeInstallationCompleted,
    RuntimeInstallationRefused,
    RuntimeStorageCheckReply,
    RuntimeStorageCheckRequest,
    RuntimeStorageInitReply,
    RuntimeStorageInitRequest,
    RuntimeStorageInventoryReply,
    RuntimeStorageInventoryRequest,
    RuntimeStorageReclaimReply,
    RuntimeStorageReclaimRequest,
)
from cadrumo.application.storage_management.documents import ConfigStorageListResult, ConfigStorageViewResult
from cadrumo.application.storage_management.errors import StorageReclaimRefusedError, StorageReclaimUnconfirmedError
from cadrumo.application.storage_management.models import StorageCheckIssueKind
from cadrumo.application.storage_management.service import RECLAIMABLE_LIFECYCLES, collect_storage_area_inventory
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.storage_taxonomy import StorageArea, StorageScope
from cadrumo.core.storage_taxonomy_locations import STORAGE_TAXONOMY, storage_path
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli, semantic_cli_output
from cadrumo.tests.env_scope import derived_storage_settings

from ..installation_storage import register_storage_acts
from .installation_registered_runtime import serving_registered_runtime
from .installation_runtime import InstallationLogin

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
]

_CLI = OperationFrontendProjection.CLI


@contextmanager
def _installed(tmp_path: Path) -> Iterator[tuple[WindowsRuntimeEndpoint, Path]]:
    """Serve one storage root that the runtime and a command in this process both resolve."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    with derived_storage_settings(root):
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        with serving_registered_runtime(endpoint, root, InstallationLogin(owner=owner_id()), register_storage_acts):
            yield endpoint, root


def _client(endpoint: WindowsRuntimeEndpoint) -> RuntimeInstallationClient:
    return RuntimeInstallationClient(
        VerifiedRuntimeConnection(
            endpoint.connect(timeout=3),
            expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
            deadline=time.monotonic() + 3,
        )
    )


def _reclaimable_target(area: StorageArea) -> Path:
    category = next(
        category
        for category, location in STORAGE_TAXONOMY.items()
        if location.grouping.value == area.value
        and location.scope is StorageScope.ROOT
        and location.lifecycle in RECLAIMABLE_LIFECYCLES
    )
    return storage_path(category)


def _command(*arguments: str) -> dict[str, Any]:
    result = invoke_cached_cli(["--format", "json", *arguments])
    assert result.exit_code == 0, semantic_cli_output(result)
    printed: dict[str, Any] = json.loads(result.output)
    return printed["result"]


def _document(reply: object) -> dict[str, Any]:
    """The reply as a frontend hands it on: every member but the exchange's own coordinates."""
    assert isinstance(reply, RuntimeInstallationCompleted), reply
    return reply.model_dump(mode="json", exclude={"request_id", "runtime_boot_id", "connection_id", "kind"})


def test_check_init_and_inventory_answer_for_the_tree_the_runtime_serves(tmp_path: Path) -> None:
    with _installed(tmp_path) as (endpoint, root), _client(endpoint) as client:
        before = client.perform(RuntimeStorageCheckRequest(request_id=uuid4(), frontend=_CLI), RuntimeStorageCheckReply)
        created = client.perform(RuntimeStorageInitRequest(request_id=uuid4(), frontend=_CLI), RuntimeStorageInitReply)
        again = client.perform(RuntimeStorageInitRequest(request_id=uuid4(), frontend=_CLI), RuntimeStorageInitReply)
        after = client.perform(RuntimeStorageCheckRequest(request_id=uuid4(), frontend=_CLI), RuntimeStorageCheckReply)
        inventory = client.perform(
            RuntimeStorageInventoryRequest(request_id=uuid4(), frontend=_CLI), RuntimeStorageInventoryReply
        )
        expected = ConfigStorageListResult.from_report(collect_storage_area_inventory())

    assert isinstance(before, RuntimeStorageCheckReply)
    assert not before.healthy
    assert before.issues
    assert {issue.kind for issue in before.issues} == {StorageCheckIssueKind.MISSING_PATH}
    assert {issue.path for issue in before.issues} == {str(root)}
    assert isinstance(created, RuntimeStorageInitReply)
    assert created.storage_root == str(root)
    assert created.created_count
    assert isinstance(again, RuntimeStorageInitReply)
    assert again.created_count == 0
    assert again.already_present > created.already_present
    assert isinstance(after, RuntimeStorageCheckReply)
    assert after.healthy
    assert after.issues == []
    assert isinstance(inventory, RuntimeStorageInventoryReply)
    assert inventory.storage_root == str(root)
    assert inventory.area is None
    assert [row.area for row in inventory.areas or []] == list(StorageArea)
    assert inventory.areas == expected.areas


def test_one_area_is_reported_alone_as_the_view_command_prints_it(tmp_path: Path) -> None:
    with _installed(tmp_path) as (endpoint, root), _client(endpoint) as client:
        viewed = client.perform(
            RuntimeStorageInventoryRequest(request_id=uuid4(), frontend=_CLI, area=StorageArea.LOGS),
            RuntimeStorageInventoryReply,
        )
        expected = ConfigStorageViewResult.from_report(collect_storage_area_inventory(), StorageArea.LOGS)

    assert isinstance(viewed, RuntimeStorageInventoryReply)
    assert viewed.areas is None
    assert viewed.area == expected.area
    assert _document(viewed) == {"storage_root": str(root), "area": expected.area.model_dump(mode="json")}


def test_a_reclaim_without_confirmation_deletes_nothing_and_says_what_a_confirmed_one_would(tmp_path: Path) -> None:
    with _installed(tmp_path) as (endpoint, _root), _client(endpoint) as client:
        target = _reclaimable_target(StorageArea.CACHE)
        target.mkdir(parents=True)
        (target / "entry-one.bin").write_bytes(b"regenerable")
        (target / "entry-two.bin").write_bytes(b"regenerable")

        unconfirmed = client.perform(
            RuntimeStorageReclaimRequest(request_id=uuid4(), frontend=_CLI, area=StorageArea.CACHE),
            RuntimeStorageReclaimReply,
        )
        survivors = sorted(path.name for path in target.iterdir())
        confirmed = client.perform(
            RuntimeStorageReclaimRequest(request_id=uuid4(), frontend=_CLI, area=StorageArea.CACHE, confirmed=True),
            RuntimeStorageReclaimReply,
        )
        remaining = list(target.iterdir())

    assert isinstance(unconfirmed, RuntimeInstallationRefused)
    assert unconfirmed.act is InstallationAct.STORAGE_RECLAIM
    assert unconfirmed.detail.error_code == get_registered_error_code(StorageReclaimUnconfirmedError).code
    assert unconfirmed.detail.context_mapping()["entry_count"] == "2"
    assert survivors == ["entry-one.bin", "entry-two.bin"]
    assert isinstance(confirmed, RuntimeStorageReclaimReply)
    assert confirmed.area is StorageArea.CACHE
    assert confirmed.removed_entries == 2
    assert confirmed.retained_entries == 0
    assert remaining == []


@pytest.mark.parametrize("area", [StorageArea.STATE, StorageArea.EXPORTS])
def test_a_reclaim_of_an_area_holding_durable_state_is_refused_even_when_confirmed(
    tmp_path: Path, area: StorageArea
) -> None:
    with _installed(tmp_path) as (endpoint, _root), _client(endpoint) as client:
        category = next(
            category
            for category, location in STORAGE_TAXONOMY.items()
            if location.grouping.value == area.value and location.scope is StorageScope.ROOT
        )
        marker = storage_path(category) / "operator-data.bin"
        marker.parent.mkdir(parents=True)
        marker.write_bytes(b"must survive")

        refused = client.perform(
            RuntimeStorageReclaimRequest(request_id=uuid4(), frontend=_CLI, area=area, confirmed=True),
            RuntimeStorageReclaimReply,
        )

    assert isinstance(refused, RuntimeInstallationRefused)
    assert refused.detail.error_code == get_registered_error_code(StorageReclaimRefusedError).code
    assert refused.detail.context_mapping()["area"] == area.value
    assert marker.read_bytes() == b"must survive"


def test_a_reclaim_target_that_was_redirected_elsewhere_is_refused_and_the_destination_is_left_alone(
    tmp_path: Path,
) -> None:
    import _winapi

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.bin").write_bytes(b"not the runtime's to delete")
    with _installed(tmp_path) as (endpoint, _root), _client(endpoint) as client:
        target = _reclaimable_target(StorageArea.CACHE)
        target.parent.mkdir(parents=True, exist_ok=True)
        create_junction = getattr(_winapi, "CreateJunction", None)
        assert create_junction is not None, "this Windows runtime cannot create a junction"
        create_junction(str(outside), str(target))

        refused = client.perform(
            RuntimeStorageReclaimRequest(request_id=uuid4(), frontend=_CLI, area=StorageArea.CACHE, confirmed=True),
            RuntimeStorageReclaimReply,
        )
        target.rmdir()

    assert isinstance(refused, RuntimeInstallationRefused)
    assert refused.detail.error_code == get_registered_error_code(StorageReclaimRefusedError).code
    assert (outside / "precious.bin").read_bytes() == b"not the runtime's to delete"


def test_every_frontend_is_admitted_and_answered_the_same_way(tmp_path: Path) -> None:
    answers: dict[OperationFrontendProjection, dict[str, dict[str, Any]]] = {}
    with _installed(tmp_path) as (endpoint, _root):
        with _client(endpoint) as client:
            client.perform(RuntimeStorageInitRequest(request_id=uuid4(), frontend=_CLI), RuntimeStorageInitReply)
        for frontend in OperationFrontendProjection:
            with _client(endpoint) as client:
                settled = {
                    "inventory": client.perform(
                        RuntimeStorageInventoryRequest(request_id=uuid4(), frontend=frontend),
                        RuntimeStorageInventoryReply,
                    ),
                    "check": client.perform(
                        RuntimeStorageCheckRequest(request_id=uuid4(), frontend=frontend), RuntimeStorageCheckReply
                    ),
                    "unconfirmed": client.perform(
                        RuntimeStorageReclaimRequest(request_id=uuid4(), frontend=frontend, area=StorageArea.CACHE),
                        RuntimeStorageReclaimReply,
                    ),
                }
            answers[frontend] = {
                name: reply.model_dump(mode="json", exclude={"request_id", "connection_id"})
                for name, reply in settled.items()
            }

    assert len(answers) == 3
    assert answers[_CLI]["check"]["healthy"] is True
    assert answers[_CLI]["unconfirmed"]["kind"] == "installation_refused"
    for frontend in OperationFrontendProjection:
        assert answers[frontend] == answers[_CLI]


def test_each_storage_command_prints_the_document_its_act_replies_with(tmp_path: Path) -> None:
    with _installed(tmp_path) as (endpoint, _root), _client(endpoint) as client:
        # The tree is materialised first so that every command and act below meets the same state.
        _command("config", "storage", "init")
        listed = _command("config", "storage", "list")
        viewed = _command("config", "storage", "view", StorageArea.LOGS.value)
        checked = _command("config", "storage", "check")
        initialised = _command("config", "storage", "init")
        inventory = client.perform(
            RuntimeStorageInventoryRequest(request_id=uuid4(), frontend=_CLI), RuntimeStorageInventoryReply
        )
        view = client.perform(
            RuntimeStorageInventoryRequest(request_id=uuid4(), frontend=_CLI, area=StorageArea.LOGS),
            RuntimeStorageInventoryReply,
        )
        check = client.perform(RuntimeStorageCheckRequest(request_id=uuid4(), frontend=_CLI), RuntimeStorageCheckReply)
        init = client.perform(RuntimeStorageInitRequest(request_id=uuid4(), frontend=_CLI), RuntimeStorageInitReply)

        target = _reclaimable_target(StorageArea.CACHE)
        target.mkdir(parents=True, exist_ok=True)
        (target / "entry.bin").write_bytes(b"regenerable")
        reclaimed = _command("config", "storage", "reclaim", StorageArea.CACHE.value, "--yes")
        (target / "entry.bin").write_bytes(b"regenerable")
        reclaim = client.perform(
            RuntimeStorageReclaimRequest(request_id=uuid4(), frontend=_CLI, area=StorageArea.CACHE, confirmed=True),
            RuntimeStorageReclaimReply,
        )

    # No projection stands between an act's reply and the command's printed result.
    assert listed == _document(inventory)
    assert viewed == _document(view)
    assert checked == _document(check)
    assert initialised == _document(init)
    assert reclaimed == _document(reclaim)
