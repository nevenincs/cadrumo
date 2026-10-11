"""The reset acts, served by the real runtime over real profiles, drain what the runtime hosts and keep the journal."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from click.testing import Result

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.installation_client import RuntimeInstallationClient
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application import config_reset
from cadrumo.application.config_reset import (
    ConfigResetConfirmationRequiredError,
    ConfigResetRequestProblem,
    ConfigResetRequestRefusedError,
)
from cadrumo.application.config_reset_models import (
    ConfigResetOperation,
    ConfigResetOperationStatus,
    ConfigResetTargetPhase,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.runtime.installation_requests import (
    InstallationAct,
    RuntimeInstallationCompleted,
    RuntimeInstallationFailed,
    RuntimeInstallationRefused,
    RuntimeResetResumeReply,
    RuntimeResetResumeRequest,
    RuntimeResetStartReply,
    RuntimeResetStartRequest,
    RuntimeResetStatusReply,
    RuntimeResetStatusRequest,
)
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileLogin
from cadrumo.application.user_profile.custody_transactions import (
    ProfileCustodyDeleteConfirmation,
    ProfileCustodyTransactionReceipt,
)
from cadrumo.application.user_profile.lifecycle import ProfileCapsuleLifecycle
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.entrypoints.cli.errors import CliOperationStillRunningError
from cadrumo.entrypoints.cli.runtime_installation import run_installation_act_if_runtime
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli, semantic_cli_output
from cadrumo.tests.env_scope import derived_storage_settings, scoped_env_var

from .. import installation_reset
from ..installation_reset import register_reset_acts
from ..profile_connections import RuntimeProfileConnections
from .installation_registered_runtime import serving_registered_runtime
from .installation_runtime import InstallationLogin

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_CLI = OperationFrontendProjection.CLI
_SETTLE_SECONDS = 180.0
"""How long a reset the client stopped waiting for may take to finish on a loaded host."""
_LOGIN_SECONDS = 120.0
"""Starting a profile worker is a process launch; a loaded host takes longer than the shared helper allows."""
_OVERRIDE_REASON = "Court order authorises deletion before the retention floor."


@dataclass(frozen=True)
class _Installation:
    endpoint: WindowsRuntimeEndpoint
    root: Path
    profiles: tuple[UUID, UUID]
    service: RuntimeProfileConnections


@contextmanager
def _installed(tmp_path: Path, *, product_version: str | None = None) -> Iterator[_Installation]:
    """Serve a storage root holding two real encrypted profiles, with the runtime's settings on that root.

    The runtime announces the installed product's version unless told otherwise, so a command in this
    process finds it as it would find the installed one.
    """
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        create, decode = profile_authority_contexts()
        second = register_profile_with_credentials(
            label="Second profile",
            passphrase=PROFILE_INPUT,
            profile_create_context=create,
            profile_decode_context=decode,
        )
        close_active_bucket_session()
        with (
            scoped_env_var("CADRUMO_LOCAL_STORAGE_ROOT", str(root)),
            serving_registered_runtime(
                endpoint,
                root,
                InstallationLogin(owner=owner_id()),
                register_reset_acts,
                secret_store=lambda: subject.native,
                product_version=product_version or version("cadrumo"),
            ) as service,
        ):
            yield _Installation(endpoint, root, (subject.store.binding.profile_id, UUID(second.profile_id)), service)


def _connection(endpoint: WindowsRuntimeEndpoint) -> VerifiedRuntimeConnection:
    return VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


def _client(endpoint: WindowsRuntimeEndpoint) -> RuntimeInstallationClient:
    return RuntimeInstallationClient(_connection(endpoint))


def _host(installation: _Installation, stack: ExitStack, profile: UUID) -> None:
    """Log one profile in over its own connection, so the runtime hosts a worker for it."""
    wire = _connection(installation.endpoint)
    stack.callback(wire.close)
    admitted = wire.login(
        RuntimeProfileLogin(request_id=uuid4(), profile_id=profile, frontend=_CLI, method="password"),
        bytearray(PROFILE_INPUT.encode()),
        deadline=time.monotonic() + _LOGIN_SECONDS,
    )
    assert not isinstance(admitted, RuntimeAccessRefusal), admitted


def _capsule(installation: _Installation, profile: UUID) -> Path:
    return load_committed_profile_password_material(profile, root=installation.root).capsule_path


def _start(
    frontend: OperationFrontendProjection = _CLI,
    *,
    confirmed: bool = True,
    acknowledge_retention_override: bool = False,
    retention_override_reason: str | None = None,
) -> RuntimeResetStartRequest:
    return RuntimeResetStartRequest(
        request_id=uuid4(),
        frontend=frontend,
        confirmed=confirmed,
        acknowledge_retention_override=acknowledge_retention_override,
        retention_override_reason=retention_override_reason,
    )


def _resume(
    frontend: OperationFrontendProjection = _CLI,
    *,
    confirmed: bool = True,
    operation_id: str | None = None,
) -> RuntimeResetResumeRequest:
    return RuntimeResetResumeRequest(
        request_id=uuid4(), frontend=frontend, confirmed=confirmed, operation_id=operation_id
    )


def _refused(reply: object) -> RuntimeInstallationRefused:
    assert isinstance(reply, RuntimeInstallationRefused), reply
    return reply


def _status(frontend: OperationFrontendProjection = _CLI, operation_id: str | None = None) -> RuntimeResetStatusRequest:
    return RuntimeResetStatusRequest(request_id=uuid4(), frontend=frontend, operation_id=operation_id)


def _interrupt_the_first_capsule_deletion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the first capsule deletion before it touches anything; every later one runs for real."""
    original_delete = ProfileCapsuleLifecycle.delete
    attempts: list[ProfileCustodyDeleteConfirmation] = []

    def interrupted_once(
        owner: ProfileCapsuleLifecycle, confirmation: ProfileCustodyDeleteConfirmation
    ) -> ProfileCustodyTransactionReceipt:
        attempts.append(confirmation)
        if len(attempts) == 1:
            raise OSError("synthetic interruption before the first capsule is deleted")
        return original_delete(owner, confirmation)

    monkeypatch.setattr(ProfileCapsuleLifecycle, "delete", interrupted_once)


def _invoke(*arguments: str) -> Result:
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        return invoke_cached_cli(["--format", "json", "config", "reset", *arguments])


def _command(*arguments: str) -> dict[str, Any]:
    result = _invoke(*arguments)
    assert result.exit_code == 0, semantic_cli_output(result)
    printed: dict[str, Any] = json.loads(result.output)
    return printed["result"]


def _document(reply: object) -> dict[str, Any]:
    """The reply as a frontend hands it on: every member but the exchange's own coordinates."""
    assert isinstance(reply, RuntimeInstallationCompleted), reply
    return reply.model_dump(mode="json", exclude={"request_id", "runtime_boot_id", "connection_id", "kind"})


def _forbid_the_in_process_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any reset the command line would do in its own process, leaving the runtime's own handlers alone."""

    def refuse(*_arguments: object, **_keywords: object) -> ConfigResetOperation:
        raise AssertionError("the command line must not reset in its own process beside a running runtime")

    monkeypatch.setattr(config_reset, "start_config_reset", refuse)
    monkeypatch.setattr(config_reset, "resume_config_reset", refuse)


def test_a_reset_drains_every_hosted_profile_before_storage_is_touched_and_keeps_them_fenced_until_it_settles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}
    real_start = config_reset.start_config_reset

    def observe_then_start(**arguments: Any) -> ConfigResetOperation:
        with installation.service._guard:
            seen["hosted"] = set(installation.service._profiles)
            seen["fenced"] = set(installation.service._custody_mutations)
        seen["capsules"] = [_capsule(installation, profile).exists() for profile in installation.profiles]
        return real_start(**arguments)

    monkeypatch.setattr(installation_reset, "start_config_reset", observe_then_start)
    with _installed(tmp_path) as installation, ExitStack() as hosts, _client(installation.endpoint) as client:
        capsules = [_capsule(installation, profile) for profile in installation.profiles]
        for profile in installation.profiles:
            _host(installation, hosts, profile)
        assert set(installation.service._profiles) == set(installation.profiles)

        reply = client.perform(_start(), RuntimeResetStartReply)

        hosted_after = set(installation.service._profiles)
        fenced_after = set(installation.service._custody_mutations)
        guard_after = installation.service._drain_guard._owner

    assert isinstance(reply, RuntimeResetStartReply)
    assert reply.operation.status is ConfigResetOperationStatus.COMPLETE
    assert {target.bucket_id for target in reply.operation.targets} == {str(p) for p in installation.profiles}
    assert all(target.phase is ConfigResetTargetPhase.DELETED for target in reply.operation.targets)
    assert not any(capsule.exists() for capsule in capsules)
    # At the moment the reset began, nothing was hosted, both profiles were fenced, and both capsules still stood.
    assert seen == {"hosted": set(), "fenced": set(installation.profiles), "capsules": [True, True]}
    assert hosted_after == set()
    assert fenced_after == set()
    assert guard_after is None


def test_a_reset_that_is_interrupted_leaves_its_journal_and_a_resume_finishes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _interrupt_the_first_capsule_deletion(monkeypatch)
    with _installed(tmp_path) as installation, ExitStack() as hosts, _client(installation.endpoint) as client:
        capsules = [_capsule(installation, profile) for profile in installation.profiles]
        for profile in installation.profiles:
            _host(installation, hosts, profile)

        interrupted = client.perform(_start(), RuntimeResetStartReply)
        left = client.perform(_status(), RuntimeResetStatusReply)
        assert isinstance(left, RuntimeResetStatusReply)
        assert left.operation is not None
        fenced_between = set(installation.service._custody_mutations)
        hosted_between = set(installation.service._profiles)
        capsules_between = [capsule.exists() for capsule in capsules]
        resumed = client.perform(_resume(), RuntimeResetResumeReply)
        capsules_after = [capsule.exists() for capsule in capsules]
        replayed = client.perform(_resume(operation_id=left.operation.operation_id), RuntimeResetResumeReply)

    assert isinstance(interrupted, RuntimeInstallationFailed)
    assert interrupted.act is InstallationAct.RESET_START
    assert left.operation.status is ConfigResetOperationStatus.INCOMPLETE
    assert ConfigResetTargetPhase.DELETING in {target.phase for target in left.operation.targets}
    assert fenced_between == set()
    assert hosted_between == set()
    assert capsules_between == [True, True]
    assert isinstance(resumed, RuntimeResetResumeReply)
    assert resumed.operation.operation_id == left.operation.operation_id
    assert resumed.operation.status is ConfigResetOperationStatus.COMPLETE
    assert resumed.operation.summary is not None
    assert resumed.operation.summary.deleted_count == 2
    assert capsules_after == [False, False]
    # A journal that is already complete comes back as it stands.
    assert isinstance(replayed, RuntimeResetResumeReply)
    assert replayed.operation == resumed.operation


def test_a_resume_of_a_complete_journal_returns_it_and_drains_nobody(tmp_path: Path) -> None:
    with _installed(tmp_path) as installation, ExitStack() as hosts, _client(installation.endpoint) as client:
        done = client.perform(_start(), RuntimeResetStartReply)
        assert isinstance(done, RuntimeResetStartReply)
        create, decode = profile_authority_contexts()
        later = UUID(
            register_profile_with_credentials(
                label="Registered after the reset",
                passphrase=PROFILE_INPUT,
                profile_create_context=create,
                profile_decode_context=decode,
            ).profile_id
        )
        close_active_bucket_session()
        _host(installation, hosts, later)

        replayed = client.perform(_resume(operation_id=done.operation.operation_id), RuntimeResetResumeReply)

        hosted_after = set(installation.service._profiles)
        later_capsule_exists = _capsule(installation, later).exists()

    assert isinstance(replayed, RuntimeResetResumeReply)
    assert replayed.operation == done.operation
    assert hosted_after == {later}
    assert later_capsule_exists


def test_unconfirmed_and_unpaired_requests_are_refused_before_any_profile_is_touched(tmp_path: Path) -> None:
    with _installed(tmp_path) as installation, ExitStack() as hosts, _client(installation.endpoint) as client:
        for profile in installation.profiles:
            _host(installation, hosts, profile)
        capsules = [_capsule(installation, profile) for profile in installation.profiles]

        unconfirmed = client.perform(_start(confirmed=False), RuntimeResetStartReply)
        unconfirmed_resume = client.perform(_resume(confirmed=False), RuntimeResetResumeReply)
        no_reason = client.perform(_start(acknowledge_retention_override=True), RuntimeResetStartReply)
        reason_alone = client.perform(_start(retention_override_reason=_OVERRIDE_REASON), RuntimeResetStartReply)
        nothing = client.perform(_resume(), RuntimeResetResumeReply)
        journal = client.perform(_status(), RuntimeResetStatusReply)
        hosted_after = set(installation.service._profiles)

    unconfirmed_code = get_registered_error_code(ConfigResetConfirmationRequiredError).code
    request_code = get_registered_error_code(ConfigResetRequestRefusedError).code
    assert _refused(unconfirmed).detail.error_code == unconfirmed_code
    assert _refused(unconfirmed_resume).detail.error_code == unconfirmed_code
    assert _refused(no_reason).detail.error_code == request_code
    assert _refused(reason_alone).detail.error_code == request_code
    assert _refused(nothing).detail.error_code == request_code
    assert _refused(no_reason).detail.context_mapping()["problem"] == (
        ConfigResetRequestProblem.OVERRIDE_REASON_REQUIRED.value
    )
    assert _refused(reason_alone).detail.context_mapping()["problem"] == (
        ConfigResetRequestProblem.OVERRIDE_REASON_WITHOUT_OVERRIDE.value
    )
    assert _refused(nothing).detail.context_mapping()["problem"] == ConfigResetRequestProblem.NOTHING_TO_RESUME.value
    assert isinstance(journal, RuntimeResetStatusReply)
    assert journal.operation is None
    assert all(capsule.exists() for capsule in capsules)
    assert hosted_after == set(installation.profiles)


def test_every_frontend_is_admitted_and_answered_the_same_way(tmp_path: Path) -> None:
    answers: dict[OperationFrontendProjection, dict[str, dict[str, Any]]] = {}
    with _installed(tmp_path) as installation:
        for frontend in OperationFrontendProjection:
            with _client(installation.endpoint) as client:
                settled = {
                    "status": client.perform(_status(frontend), RuntimeResetStatusReply),
                    "unconfirmed": client.perform(_start(frontend, confirmed=False), RuntimeResetStartReply),
                    "nothing": client.perform(_resume(frontend), RuntimeResetResumeReply),
                }
            answers[frontend] = {
                name: reply.model_dump(mode="json", exclude={"request_id", "connection_id"})
                for name, reply in settled.items()
            }

    assert len(answers) == 3
    assert answers[_CLI]["status"]["operation"] is None
    assert answers[_CLI]["unconfirmed"]["kind"] == "installation_refused"
    for frontend in OperationFrontendProjection:
        assert answers[frontend] == answers[_CLI]


def test_each_reset_act_replies_with_the_document_its_command_prints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _interrupt_the_first_capsule_deletion(monkeypatch)
    with _installed(tmp_path) as installation, _client(installation.endpoint) as client:
        silent = client.perform(_status(), RuntimeResetStatusReply)
        silent_command = _command("status")

        started = client.perform(_start(), RuntimeResetStartReply)
        interrupted_command = _command("status")
        interrupted = client.perform(_status(), RuntimeResetStatusReply)
        resumed = client.perform(_resume(), RuntimeResetResumeReply)
        finished_command = _command("status")
        finished = client.perform(_status(), RuntimeResetStatusReply)

    assert silent_command == {"operation": None}
    assert silent_command == _document(silent)
    assert isinstance(started, RuntimeInstallationFailed)
    assert interrupted_command["operation"]["status"] == "incomplete"
    assert interrupted_command == _document(interrupted)
    # A resume replies with the journal the status command prints once it has settled.
    assert finished_command["operation"]["status"] == "complete"
    assert finished_command == _document(finished)
    assert finished_command == _document(resumed)


def test_the_start_command_beside_a_running_runtime_sends_the_act_and_prints_its_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}
    real_start = config_reset.start_config_reset

    def observe_then_start(**arguments: Any) -> ConfigResetOperation:
        with installation.service._guard:
            seen["hosted"] = set(installation.service._profiles)
            seen["fenced"] = set(installation.service._custody_mutations)
        seen["capsules"] = [_capsule(installation, profile).exists() for profile in installation.profiles]
        return real_start(**arguments)

    monkeypatch.setattr(installation_reset, "start_config_reset", observe_then_start)
    _forbid_the_in_process_reset(monkeypatch)
    with _installed(tmp_path) as installation, ExitStack() as hosts, _client(installation.endpoint) as client:
        capsules = [_capsule(installation, profile) for profile in installation.profiles]
        for profile in installation.profiles:
            _host(installation, hosts, profile)
        assert set(installation.service._profiles) == set(installation.profiles)

        printed = _command("start", "--yes")

        settled = client.perform(_status(), RuntimeResetStatusReply)
        hosted_after = set(installation.service._profiles)

    assert seen == {"hosted": set(), "fenced": set(installation.profiles), "capsules": [True, True]}
    assert printed["operation"]["status"] == "complete"
    assert printed == _document(settled)
    assert not any(capsule.exists() for capsule in capsules)
    assert hosted_after == set()


def test_a_command_beside_a_running_runtime_never_repeats_in_process_what_the_runtime_answered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _interrupt_the_first_capsule_deletion(monkeypatch)
    _forbid_the_in_process_reset(monkeypatch)
    with _installed(tmp_path) as installation, ExitStack() as hosts, _client(installation.endpoint) as client:
        capsules = [_capsule(installation, profile) for profile in installation.profiles]
        for profile in installation.profiles:
            _host(installation, hosts, profile)

        stopped = _invoke("start", "--yes")
        left = _command("status")
        resumed = _command("resume", "--yes")
        settled = client.perform(_status(), RuntimeResetStatusReply)

    # The runtime's fault is reported with the effect unknown, and nothing ran a second time here.
    assert stopped.exit_code != 0
    assert "unknown" in stopped.output.lower()
    assert left["operation"]["status"] == "incomplete"
    assert resumed["operation"]["status"] == "complete"
    assert resumed == _document(settled)
    assert not any(capsule.exists() for capsule in capsules)


def test_a_runtime_that_cannot_be_verified_is_not_a_reason_to_reset_in_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _forbid_the_in_process_reset(monkeypatch)
    with _installed(tmp_path, product_version="0.0.0-another-cohort") as installation:
        capsules = [_capsule(installation, profile) for profile in installation.profiles]

        refused = _invoke("start", "--yes")
        journal = _command("status")

    assert refused.exit_code != 0
    assert journal == {"operation": None}
    assert all(capsule.exists() for capsule in capsules)


def test_with_no_runtime_the_command_resets_in_process_as_it_always_did(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    with derived_storage_settings(root):
        answered = run_installation_act_if_runtime(_status(), RuntimeResetStatusReply)

    assert answered is None


def test_a_client_that_stops_waiting_for_a_reset_is_told_the_outcome_is_unknown_and_where_to_read_it(
    tmp_path: Path,
) -> None:
    with _installed(tmp_path) as installation, _client(installation.endpoint) as client:
        capsules = [_capsule(installation, profile) for profile in installation.profiles]

        with pytest.raises(CliOperationStillRunningError) as unsettled:
            run_installation_act_if_runtime(_start(), RuntimeResetStartReply, timeout=0.05)
        deadline = time.monotonic() + _SETTLE_SECONDS
        reading = client.perform(_status(), RuntimeResetStatusReply)
        while not (isinstance(reading, RuntimeResetStatusReply) and _is_complete(reading)):
            assert time.monotonic() < deadline, "the reset the client stopped waiting for did not settle"
            time.sleep(0.5)
            reading = client.perform(_status(), RuntimeResetStatusReply)

    context = unsettled.value.context or {}
    assert context["effect"] == "unknown"
    assert context["check_command"] == "config reset status"
    assert not any(capsule.exists() for capsule in capsules)


def _is_complete(reply: RuntimeResetStatusReply) -> bool:
    return reply.operation is not None and reply.operation.status is ConfigResetOperationStatus.COMPLETE
