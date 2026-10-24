"""The product's setup composition performs no acquisition: every item reads only, and every effect refuses.

The registry is the one the runtime composes, on a fresh storage root with the
local AI endpoint pointed at a closed port; nothing here launches a browser,
runs an installer, starts a program or opens a download.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from pathlib import Path

import pytest

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ...application.dependency_contracts import DependencyBlockedReason, DependencyCheckMode, DependencyState
from ...application.dependency_transfer import DependencyTransferError
from ...application.dependency_withdrawal import (
    refused_browser_launch,
    refused_build_removal,
    refused_runtime_install,
    refused_runtime_spawn,
)
from ...application.operations.models import OperationIdentity
from ...application.provisioning_host import RuntimeInstaller
from ...core.config import override_settings
from ..dependency_operation_composition import build_dependency_registry_factory

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"


@pytest.fixture
def storage(tmp_path: Path) -> Generator[Path]:
    root = tmp_path / "storage"
    with override_settings(cadrumo_local_storage_root=root, cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        yield root


def _identity() -> OperationIdentity:
    return OperationIdentity(operation_id="c" * 64, definition_id="dependencies.setup", subject_ref="dependencies")


@pytest.mark.parametrize("mode", list(DependencyCheckMode))
def test_nothing_missing_is_offered_for_setup_in_either_check_mode(storage: Path, mode: DependencyCheckMode) -> None:
    async def scenario() -> None:
        registry = build_dependency_registry_factory()(_identity(), asyncio.get_running_loop())
        rows = await registry.read_rows(mode)
        assert rows, "the composed registry must declare its items"
        # No full check runs in Python, so a full request is answered, and labelled, as the quick check.
        assert all(row.mode is DependencyCheckMode.QUICK for row in rows), rows
        for row in rows:
            # What is already installed (a developer's browser builds) still reads usable, and a check that
            # did not answer in time reads unknown; nothing reads absent or failed, which would offer a setup.
            assert row.state not in {DependencyState.ABSENT, DependencyState.FAILED, DependencyState.STALE}, row
            if row.state is DependencyState.BLOCKED:
                assert row.blocked_reason in {
                    DependencyBlockedReason.NOT_IN_THIS_BUILD,
                    DependencyBlockedReason.HARDWARE,
                }, row

    asyncio.run(scenario())
    del storage


def test_planning_any_item_refuses_as_not_in_this_build(storage: Path) -> None:
    async def scenario() -> None:
        registry = build_dependency_registry_factory()(_identity(), asyncio.get_running_loop())
        for declaration in registry.declarations:
            provisioner = registry.provisioner(declaration.item_id)
            with pytest.raises(DependencyTransferError) as refused:
                await provisioner.plan(model_name=None)
            assert refused.value.category is DependencyFailureCategory.NOT_IN_THIS_BUILD

    asyncio.run(scenario())
    del storage


def test_every_effect_port_the_composition_binds_refuses(tmp_path: Path) -> None:
    calls = (
        lambda: refused_build_removal(tmp_path, ("chromium-1",)),
        lambda: refused_runtime_install(RuntimeInstaller.WINGET, tmp_path / "winget.exe", 1.0),
        lambda: refused_runtime_spawn(tmp_path / "ollama.exe", {}),
        lambda: asyncio.run(refused_browser_launch(tmp_path / "chrome.exe", timeout_s=1.0)),
    )
    for call in calls:
        with pytest.raises(DependencyTransferError) as refused:
            call()
        assert refused.value.category is DependencyFailureCategory.NOT_IN_THIS_BUILD
    assert list(tmp_path.iterdir()) == []
