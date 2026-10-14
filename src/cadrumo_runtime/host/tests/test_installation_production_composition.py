"""The installed runtime serves every installation act, and serves it through the door the frontends open.

The first half holds the composed registry to the table of acts in both
directions. The second half serves that same composition from a real runtime
that announces the installed product's version, and reaches one act of every
family with the opener the command line, the terminal interface and the
harness use.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.modelo.review_package import ReviewPackageIntegrityError
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.tests.env_scope import derived_storage_settings
from cadrumo_client.contracts.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    InstallationAct,
    InstallationActRequest,
    InstallationCompleted,
    InstallationRefused,
    ProfileListReply,
    ProfileListRequest,
    RepairLogsReply,
    RepairLogsRequest,
    ResetStatusReply,
    ResetStatusRequest,
    ReviewPackageVerifyReply,
    ReviewPackageVerifyRequest,
    StorageCheckReply,
    StorageCheckRequest,
    StorageInitReply,
    StorageInitRequest,
)
from cadrumo_client.transport.installation_client import open_installed_installation_client
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import owner_id
from ..installation_composition import InstallationActRegistry, production_installation_acts
from ..installation_door import InstallationActExchange
from .installation_registered_runtime import serving_installed_composition
from .installation_runtime import InstallationLogin

pytestmark = [pytest.mark.hex_entrypoint]


@pytest.mark.unit
def test_the_installed_registry_serves_every_act_of_the_table_and_nothing_else() -> None:
    served = production_installation_acts().served_acts

    assert served == frozenset(INSTALLATION_ACT_CONTRACTS)
    assert served == frozenset(InstallationAct)


@pytest.mark.unit
def test_the_census_detects_an_act_the_registry_does_not_serve() -> None:
    def serve(request: StorageCheckRequest, exchange: InstallationActExchange, /) -> StorageCheckReply:
        raise AssertionError("the census never calls a handler")

    partial = InstallationActRegistry()
    partial.register(StorageCheckRequest, serve)

    assert partial.served_acts == {InstallationAct.STORAGE_CHECK}
    assert partial.served_acts != frozenset(INSTALLATION_ACT_CONTRACTS)


@contextmanager
def _installed_runtime(tmp_path: Path) -> Generator[Path]:
    """Serve one storage root that the runtime's handlers and the frontends' opener both resolve."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    with derived_storage_settings(root):
        endpoint = WindowsEndpoint(storage_root=root)
        with serving_installed_composition(endpoint, root, InstallationLogin(owner=owner_id())):
            yield root


def _perform[ReplyT: InstallationCompleted](request: InstallationActRequest, reply_type: type[ReplyT]) -> object:
    """Send one act through the opener every frontend uses and return whatever the door answered."""
    with asyncio.run(open_installed_installation_client()) as client:
        return client.perform(request, reply_type)


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes")
@pytest.mark.usefixtures("authority_operation")
@pytest.mark.parametrize("frontend", [OperationFrontendProjection.CLI, OperationFrontendProjection.TUI])
def test_the_installed_composition_serves_an_act_of_every_family_to_every_frontend(
    tmp_path: Path, frontend: OperationFrontendProjection
) -> None:
    absent_package = tmp_path / "absent-review-package.zip"
    with _installed_runtime(tmp_path) as root:
        created = _perform(StorageInitRequest(request_id=uuid4(), frontend=frontend), StorageInitReply)
        checked = _perform(StorageCheckRequest(request_id=uuid4(), frontend=frontend), StorageCheckReply)
        listed = _perform(ProfileListRequest(request_id=uuid4(), frontend=frontend), ProfileListReply)
        reset = _perform(ResetStatusRequest(request_id=uuid4(), frontend=frontend), ResetStatusReply)
        logs = _perform(RepairLogsRequest(request_id=uuid4(), frontend=frontend, lines=5), RepairLogsReply)
        verified = _perform(
            ReviewPackageVerifyRequest(request_id=uuid4(), frontend=frontend, package=str(absent_package)),
            ReviewPackageVerifyReply,
        )

    assert isinstance(created, StorageInitReply), created
    assert created.storage_root == str(root)
    assert isinstance(checked, StorageCheckReply), checked
    assert (checked.storage_root, checked.healthy, checked.issues) == (str(root), True, [])
    assert isinstance(listed, ProfileListReply), listed
    assert (listed.active_profile, listed.profiles) == (None, ())
    assert isinstance(reset, ResetStatusReply), reset
    assert reset.operation is None
    assert isinstance(logs, RepairLogsReply), logs
    assert len(logs.lines) <= 5
    assert isinstance(verified, InstallationRefused), verified
    assert verified.act is InstallationAct.REVIEW_PACKAGE_VERIFY
    assert verified.detail.error_code == get_registered_error_code(ReviewPackageIntegrityError).code
