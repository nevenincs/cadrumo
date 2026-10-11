"""The command line sends an installation act to the running runtime and raises what its handler raised."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.installation_requests import (
    RuntimeStorageCheckReply,
    RuntimeStorageCheckRequest,
    RuntimeStorageInitReply,
    RuntimeStorageInitRequest,
    RuntimeStorageInventoryReply,
    RuntimeStorageInventoryRequest,
    RuntimeStorageReclaimReply,
    RuntimeStorageReclaimRequest,
)
from cadrumo.application.storage_management.errors import StorageReclaimUnconfirmedError
from cadrumo.application.user_profile.access_contracts import OsLockState
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.storage_taxonomy import StorageArea
from cadrumo.entrypoints.runtime.tests.installation_runtime import (
    FAULT_TEXT,
    InstallationLogin,
    serving_installation_runtime,
)

from ..errors import CliRecordedOperationError, CliRefusedBoundaryError, CliUnexpectedBoundaryError
from ..runtime_installation import run_installation_act

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
]

_CLI = OperationFrontendProjection.CLI


@contextmanager
def _installed_runtime(tmp_path: Path, login: InstallationLogin) -> Iterator[Path]:
    """Serve the effective storage root as the installed cohort, so the command line finds it."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        with serving_installation_runtime(endpoint, root, login, product_version=version("cadrumo")):
            yield root


def test_a_command_gets_the_acts_reply_from_the_running_runtime(tmp_path: Path) -> None:
    with _installed_runtime(tmp_path, InstallationLogin(owner=owner_id())) as root:
        reply = run_installation_act(
            RuntimeStorageCheckRequest(request_id=uuid4(), frontend=_CLI), RuntimeStorageCheckReply
        )

    assert isinstance(reply, RuntimeStorageCheckReply)
    assert reply.storage_root == str(root)
    assert reply.healthy


def test_a_refused_act_raises_the_error_its_handler_raised(tmp_path: Path) -> None:
    with (
        _installed_runtime(tmp_path, InstallationLogin(owner=owner_id())),
        pytest.raises(CliRecordedOperationError) as refused,
    ):
        run_installation_act(
            RuntimeStorageReclaimRequest(request_id=uuid4(), frontend=_CLI, area=StorageArea.LOGS),
            RuntimeStorageReclaimReply,
        )

    assert refused.value.recorded_code == get_registered_error_code(StorageReclaimUnconfirmedError).code
    context = refused.value.context or {}
    assert context["area"] == "logs"
    assert context["entry_count"] == "3"


def test_a_failed_act_is_reported_as_unexpected_with_an_unknown_effect_and_without_the_fault(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    with (
        _installed_runtime(tmp_path, InstallationLogin(owner=owner_id())),
        pytest.raises(CliRecordedOperationError) as failed,
    ):
        run_installation_act(RuntimeStorageInitRequest(request_id=uuid4(), frontend=_CLI), RuntimeStorageInitReply)

    assert failed.value.recorded_code == get_registered_error_code(CliUnexpectedBoundaryError).code
    assert failed.value.context == {"installation_act": "storage_init", "effect": "unknown"}
    assert FAULT_TEXT not in str(failed.value)
    assert FAULT_TEXT not in caplog.text


@pytest.mark.parametrize("fault", ["another-account", "locked"])
def test_an_admission_refusal_is_raised_with_its_code(tmp_path: Path, fault: str) -> None:
    login = (
        InstallationLogin(owner="another-account")
        if fault == "another-account"
        else InstallationLogin(owner=owner_id(), lock_state=OsLockState.LOCKED)
    )

    with _installed_runtime(tmp_path, login), pytest.raises(CliRefusedBoundaryError) as refused:
        run_installation_act(RuntimeStorageCheckRequest(request_id=uuid4(), frontend=_CLI), RuntimeStorageCheckReply)

    assert (refused.value.context or {})["reason"] == "needs_user"


def test_an_act_the_runtime_does_not_serve_is_refused_as_unavailable(tmp_path: Path) -> None:
    with (
        _installed_runtime(tmp_path, InstallationLogin(owner=owner_id())),
        pytest.raises(CliRefusedBoundaryError) as refused,
    ):
        run_installation_act(
            RuntimeStorageInventoryRequest(request_id=uuid4(), frontend=_CLI), RuntimeStorageInventoryReply
        )

    assert (refused.value.context or {})["reason"] == "operation_unavailable"


def test_a_command_never_starts_the_runtime_it_cannot_reach(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path), pytest.raises(RuntimeRefusalError) as refused:
        run_installation_act(RuntimeStorageCheckRequest(request_id=uuid4(), frontend=_CLI), RuntimeStorageCheckReply)

    assert refused.value.reason in {RuntimeRefusalCode.UNAVAILABLE, RuntimeRefusalCode.DEADLINE_EXCEEDED}
