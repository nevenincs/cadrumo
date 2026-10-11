"""The repair acts, served by the real runtime over real storage roots, reply with what the commands print.

A reply is the document a frontend shows, with the real identifier of every
profile it names. Apart from the door's own coordinates it must equal the JSON
data its command prints for the same storage root when identifiers are
revealed, and the command's default print must be that same document after
the command line's own output redaction.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import pytest
from click.testing import Result

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation_client import RuntimeInstallationClient
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import publish_test_profile_capsule
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.diagnostics_repair_documents import RepairActionDocument, RepairCheckDocument
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.runtime.installation_requests import (
    InstallationAct,
    RuntimeInstallationCompleted,
    RuntimeInstallationRefused,
    RuntimeRepairLogsReply,
    RuntimeRepairLogsRequest,
    RuntimeRepairProfileReply,
    RuntimeRepairProfileRequest,
    RuntimeRepairReportReply,
    RuntimeRepairReportRequest,
)
from cadrumo.core.bucket_pointer import BucketPointer, pointer_path, read_pointer, write_pointer
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.errors.hierarchy import ActiveProfilePointerError
from cadrumo.core.i18n.render import tr
from cadrumo.core.logging import default_log_file_path
from cadrumo.core.redaction.rules import (
    CLI_BUCKET_ID_PLACEHOLDER,
    CLI_PROFILE_ID_PLACEHOLDER,
    redact_structured_for_cli_output,
)
from cadrumo.domain.user_profile.errors import ProfileNotFoundError
from cadrumo.entrypoints.cli.common import resolve_cli_precondition_action
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli, semantic_cli_output
from cadrumo.tests.env_scope import derived_storage_settings

from ..installation_repair import register_repair_acts
from .installation_registered_runtime import serving_registered_runtime
from .installation_runtime import InstallationLogin

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

type _RootKind = Literal["fresh", "healthy", "torn"]

_CLI = OperationFrontendProjection.CLI
_LABEL = "repair-acts"
_PROFILE = UUID("95959595-9595-4595-8595-959595959595")
_CORRUPT_POINTER = b"not = valid = toml"
_LOG_LINES = tuple(f"2026-04-02T09:30:{index:02d}Z synthetic repair log line {index}" for index in range(30))
_DOOR_COORDINATES = frozenset({"request_id", "runtime_boot_id", "connection_id", "kind"})


@contextmanager
def _installed(
    tmp_path: Path, kind: _RootKind, *, as_installed: bool = False
) -> Iterator[tuple[WindowsRuntimeEndpoint, Path]]:
    """Serve one storage root that the runtime and a command in this process both resolve.

    A healthy root holds one committed profile that is the active selection,
    with no session open for it in this process, as a runtime that hosts
    profiles in workers holds none. A torn root's pointer selects a profile
    that has no committed capsule.

    The acts resolve a verdict's recovery action through the command line's
    own resolver, which reads the command graph. With ``as_installed`` they
    are registered as the installed runtime registers them, and resolve
    against the recorded action targets.
    """
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    with derived_storage_settings(root), isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        assert storage_root == root
        if kind == "healthy":
            publish_test_profile_capsule(_PROFILE, label=_LABEL, root=root)
            write_pointer(root, BucketPointer.selected(bucket_id=str(_PROFILE), transition_revision=1))
        if kind == "torn":
            write_pointer(root, BucketPointer.selected(bucket_id=str(uuid4()), transition_revision=1))
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        register = (
            register_repair_acts
            if as_installed
            else partial(register_repair_acts, resolve_action=resolve_cli_precondition_action)
        )
        with serving_registered_runtime(endpoint, root, InstallationLogin(owner=owner_id()), register):
            yield endpoint, root


def _client(endpoint: WindowsRuntimeEndpoint) -> RuntimeInstallationClient:
    return RuntimeInstallationClient(
        VerifiedRuntimeConnection(
            endpoint.connect(timeout=3),
            expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
            deadline=time.monotonic() + 3,
        )
    )


def _run(*arguments: str) -> Result:
    return invoke_cached_cli(["--format", "json", *arguments])


@dataclass(frozen=True, slots=True)
class _Printed:
    """The JSON data one command prints, as it prints by default and with identifiers revealed."""

    default: dict[str, object]
    revealed: dict[str, object]


def _data(*arguments: str, exit_code: int = 0, reveal: bool = False) -> dict[str, object]:
    """Run the command once and return the JSON data it prints."""
    with override_settings(cadrumo_cli_reveal_identifiers=reveal):
        result = _run(*arguments)
    assert result.exit_code == exit_code, semantic_cli_output(result)
    envelope = json.loads(result.stdout)
    assert isinstance(envelope, dict)
    data = envelope["result"]
    assert isinstance(data, dict)
    members: dict[str, object] = {str(key): value for key, value in data.items()}
    return members


def _command(*arguments: str, exit_code: int = 0) -> _Printed:
    """Run a command that changes nothing twice: as it prints by default, and with identifiers revealed."""
    return _Printed(
        default=_data(*arguments, exit_code=exit_code),
        revealed=_data(*arguments, exit_code=exit_code, reveal=True),
    )


def _hidden(document: dict[str, object]) -> object:
    """Return ``document`` after the command line's own output redaction."""
    return redact_structured_for_cli_output(document, reveal_identifiers=False)


def _assert_prints(reply: RuntimeInstallationCompleted, printed: _Printed) -> None:
    """Hold a command's two prints to the reply: whole when revealed, redacted by default."""
    document = _document(reply)
    assert printed.revealed == document
    assert printed.default == _hidden(document)


def _refusal(*arguments: str) -> dict[str, object]:
    """Return the error one refused command prints."""
    result = _run(*arguments)
    assert result.exit_code != 0, semantic_cli_output(result)
    assert result.stdout == ""
    envelope = json.loads(result.stderr)
    assert isinstance(envelope, dict)
    error = envelope["error"]
    assert isinstance(error, dict)
    members: dict[str, object] = {str(key): value for key, value in error.items()}
    return members


def _refusal_code(*arguments: str) -> str:
    code = _refusal(*arguments)["code"]
    assert isinstance(code, str)
    return code


def _refused(client: RuntimeInstallationClient, request: RuntimeRepairProfileRequest) -> RuntimeInstallationRefused:
    reply = client.perform(request, RuntimeRepairProfileReply)
    assert isinstance(reply, RuntimeInstallationRefused)
    assert reply.act is InstallationAct.REPAIR_PROFILE
    return reply


def _same_refusal(refused: RuntimeInstallationRefused, printed: dict[str, object]) -> None:
    """Hold an act's refusal to the code, message and context its command printed."""
    assert refused.detail.error_code == printed["code"]
    assert refused.detail.message_key is not None
    context = refused.detail.context_mapping()
    assert printed["message"] == tr(refused.detail.message_key, **context)
    assert {key: value for key, value in context.items()} == (printed.get("context") or {})


def _document(reply: RuntimeInstallationCompleted) -> dict[str, object]:
    """Return the reply as a frontend shows it, without the door's own coordinates."""
    shown = reply.model_dump(mode="json", exclude=set(_DOOR_COORDINATES))
    members: dict[str, object] = {str(name): value for name, value in shown.items()}
    return members


def _report(
    client: RuntimeInstallationClient, frontend: OperationFrontendProjection = _CLI
) -> RuntimeRepairReportReply:
    reply = client.perform(RuntimeRepairReportRequest(request_id=uuid4(), frontend=frontend), RuntimeRepairReportReply)
    assert isinstance(reply, RuntimeRepairReportReply)
    return reply


def _logs(
    client: RuntimeInstallationClient, lines: int, frontend: OperationFrontendProjection = _CLI
) -> RuntimeRepairLogsReply:
    reply = client.perform(
        RuntimeRepairLogsRequest(request_id=uuid4(), frontend=frontend, lines=lines), RuntimeRepairLogsReply
    )
    assert isinstance(reply, RuntimeRepairLogsReply)
    return reply


def _profile(
    client: RuntimeInstallationClient,
    *,
    profile: str | None = None,
    clear_active: bool = False,
    confirmed: bool = False,
    frontend: OperationFrontendProjection = _CLI,
) -> RuntimeRepairProfileReply:
    reply = client.perform(
        RuntimeRepairProfileRequest(
            request_id=uuid4(), frontend=frontend, profile=profile, clear_active=clear_active, confirmed=confirmed
        ),
        RuntimeRepairProfileReply,
    )
    assert isinstance(reply, RuntimeRepairProfileReply)
    return reply


def _recommended(action: RepairActionDocument | None) -> str | None:
    """Name the catalogue action one printed recovery action recommends."""
    if action is None:
        return None
    reference = action["action"]
    if reference is None:
        return None
    assert isinstance(reference, dict)
    action_id = reference["action_id"]
    assert isinstance(action_id, str)
    return action_id


def _check(reply: RuntimeRepairReportReply, name: str) -> RepairCheckDocument:
    return next(item for item in reply.checks if item.name == name)


def _write_log() -> None:
    path = default_log_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(_LOG_LINES) + "\n", encoding="utf-8")


@pytest.mark.parametrize(
    ("kind", "storage", "readiness_action"),
    [
        ("fresh", "ok", "operator.profile.create"),
        ("healthy", "warn", "operator.profile.login"),
        ("torn", "warn", "operator.profile.repair_active_pointer"),
    ],
)
def test_the_report_act_replies_with_the_diagnosis_the_command_prints(
    tmp_path: Path, kind: _RootKind, storage: str, readiness_action: str
) -> None:
    with _installed(tmp_path, kind) as (endpoint, root), _client(endpoint) as client:
        reply = _report(client)
        commanded = _command("config", "repair")
        pointer_after = read_pointer(root)

    assert {check.name for check in reply.checks} >= {
        "environment.python",
        "logging.file",
        "secure_state.load",
        "profile.storage",
        "profile.readiness",
        "auth.readiness",
        "secure_objects.integrity",
    }
    assert _check(reply, "profile.storage").status == storage
    readiness = _check(reply, "profile.readiness")
    assert (readiness.status, _recommended(readiness.precondition_action)) == ("warn", readiness_action)
    assert reply.overall == ("fail" if any(check.status == "fail" for check in reply.checks) else "warn")
    # No profile is open in the process that serves the act, so it reads no profile's rows.
    assert (reply.setup, reply.secure_objects.namespaces) == (None, ())
    assert Path(reply.log_file).is_relative_to(root)
    assert (pointer_after.bucket_id is None) == (kind == "fresh")
    _assert_prints(reply, commanded)


@pytest.mark.parametrize("kind", ["fresh", "healthy", "torn"])
def test_the_logs_act_replies_with_the_tail_the_command_prints(tmp_path: Path, kind: _RootKind) -> None:
    with _installed(tmp_path, kind) as (endpoint, root), _client(endpoint) as client:
        before_any_log = _logs(client, 5)
        commanded_before = _command("config", "repair", "logs", "--lines", "5")
        _write_log()
        tail = _logs(client, 5)
        commanded = _command("config", "repair", "logs", "--lines", "5")
        nothing = _logs(client, 0)
        commanded_nothing = _command("config", "repair", "logs", "--lines", "0")
        everything = _logs(client, 500)

    assert Path(tail.path) == root / "logs" / "cadrumo.log"
    assert (before_any_log.path, before_any_log.lines) == (tail.path, ())
    assert tail.lines == _LOG_LINES[-5:]
    assert nothing.lines == ()
    assert everything.lines == _LOG_LINES
    _assert_prints(before_any_log, commanded_before)
    _assert_prints(tail, commanded)
    _assert_prints(nothing, commanded_nothing)


def test_the_logs_act_withholds_a_secret_from_a_line_and_keeps_an_identifier(tmp_path: Path) -> None:
    identifier = "7c1d7f0e-5a52-4f0e-9d53-0b8f6f6f2a11"

    with _installed(tmp_path, "fresh") as (endpoint, _root), _client(endpoint) as client:
        path = default_log_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "synthetic line fetching https://example.org/path?token=synthetic-secret-value\n"
            f"synthetic line about profile {identifier}\n"
            "synthetic line that names nothing private\n",
            encoding="utf-8",
        )
        tail = _logs(client, 5)
        commanded = _command("config", "repair", "logs", "--lines", "5")

    assert len(tail.lines) == 3
    assert tail.lines[1:] == (f"synthetic line about profile {identifier}", "synthetic line that names nothing private")
    # The secret leaves the process for no reader; the identifier is hidden only where the command prints.
    assert "synthetic-secret-value" not in json.dumps(_document(tail))
    assert identifier not in json.dumps(commanded.default)
    _assert_prints(tail, commanded)


def test_the_profile_act_on_a_fresh_root_reports_no_selection_and_refuses_an_unknown_name(tmp_path: Path) -> None:
    with _installed(tmp_path, "fresh") as (endpoint, _root), _client(endpoint) as client:
        bare = _profile(client)
        commanded = _command("config", "repair", "profile")
        unknown = client.perform(
            RuntimeRepairProfileRequest(request_id=uuid4(), frontend=_CLI, profile="nobody-by-this-name"),
            RuntimeRepairProfileReply,
        )
        commanded_unknown = _refusal_code("config", "repair", "profile", "--profile", "nobody-by-this-name")

    assert (bare.dry_run, bare.cleared_pointer, bare.after, bare.profile_id) == (True, False, None, None)
    assert bare.before is not None
    assert (bare.before.status, bare.before.source, bare.before.active_profile) == ("none", "none", None)
    _assert_prints(bare, commanded)
    assert isinstance(unknown, RuntimeInstallationRefused)
    assert unknown.act is InstallationAct.REPAIR_PROFILE
    assert unknown.detail.error_code == get_registered_error_code(ProfileNotFoundError).code == commanded_unknown


def test_the_profile_act_on_a_healthy_root_inspects_the_named_record_and_clears_nothing(tmp_path: Path) -> None:
    with _installed(tmp_path, "healthy") as (endpoint, root), _client(endpoint) as client:
        selected = read_pointer(root)
        bare = _profile(client)
        commanded = _command("config", "repair", "profile")
        named = _profile(client, profile=_LABEL)
        commanded_named = _command("config", "repair", "profile", "--profile", _LABEL, exit_code=2)
        asked_to_clear = _profile(client, profile=_LABEL, clear_active=True, confirmed=True)
        commanded_clear = _command("config", "repair", "profile", "--profile", _LABEL, "--clear-active", "--yes")
        still_selected = read_pointer(root)

    assert bare.before is not None
    assert (bare.before.status, bare.before.active_profile) == ("profile_locked", _LABEL)
    assert not bare.before.repairable_by_clearing_pointer
    assert _recommended(bare.before.precondition_action) == "operator.profile.login"
    _assert_prints(bare, commanded)
    # The serving process holds no session for the profile, so its record is not read here.
    assert (named.before, named.dry_run) == (None, None)
    assert (named.display_name, named.profile_record_present, named.status) == (
        _LABEL,
        False,
        "missing_profile_record",
    )
    # The reply carries the profile's real identifier; the command hides it unless identifiers are revealed.
    assert (named.profile_id, named.bucket_id) == (str(_PROFILE), str(_PROFILE))
    assert (commanded_named.default["profile_id"], commanded_named.default["bucket_id"]) == (
        CLI_PROFILE_ID_PLACEHOLDER,
        CLI_BUCKET_ID_PLACEHOLDER,
    )
    assert commanded_named.revealed["profile_id"] == str(_PROFILE)
    _assert_prints(named, commanded_named)
    # A sound selection is not repairable, so a confirmed clear reports and leaves it selected.
    assert (asked_to_clear.dry_run, asked_to_clear.cleared_pointer) == (True, False)
    _assert_prints(asked_to_clear, commanded_clear)
    assert still_selected == selected


def test_the_profile_act_clears_a_torn_selection_only_when_asked_and_confirmed(tmp_path: Path) -> None:
    with _installed(tmp_path, "torn") as (endpoint, root), _client(endpoint) as client:
        torn = read_pointer(root)
        bare = _profile(client)
        commanded = _command("config", "repair", "profile")
        unconfirmed = _refused(
            client, RuntimeRepairProfileRequest(request_id=uuid4(), frontend=_CLI, clear_active=True)
        )
        commanded_unconfirmed = _refusal("config", "repair", "profile", "--clear-active")
        confirmed_only = _profile(client, confirmed=True)
        commanded_confirmed_only = _command("config", "repair", "profile", "--yes")
        untouched = read_pointer(root)
        cleared = _profile(client, clear_active=True, confirmed=True)
        after_act = read_pointer(root)
        # The command meets the same torn selection the act met, once for each way it prints.
        write_pointer(root, torn.model_copy(update={"transition_revision": after_act.transition_revision + 1}))
        revealed_clear = _data("config", "repair", "profile", "--clear-active", "--yes", reveal=True)
        after_command = read_pointer(root)
        write_pointer(root, torn.model_copy(update={"transition_revision": after_command.transition_revision + 1}))
        default_clear = _data("config", "repair", "profile", "--clear-active", "--yes")
        after_default_command = read_pointer(root)

    # A clear that is not confirmed is refused as the command refuses it without ``--yes``.
    _same_refusal(unconfirmed, commanded_unconfirmed)
    assert unconfirmed.detail.message_key == "cli.config.repair.profile_requires_yes"
    _assert_prints(confirmed_only, commanded_confirmed_only)
    for probe in (bare, confirmed_only):
        assert (probe.dry_run, probe.cleared_pointer, probe.after) == (True, False, None)
        assert probe.before is not None
        assert (probe.before.status, probe.before.repairable_by_clearing_pointer) == ("dangling_pointer", True)
        # The dangling selection has no label, so the reply names it by its real identifier.
        assert probe.before.active_profile == torn.bucket_id
    _assert_prints(bare, commanded)
    # The command hides that identifier unless identifiers are revealed.
    assert str(torn.bucket_id) not in json.dumps(commanded.default)
    assert CLI_PROFILE_ID_PLACEHOLDER in json.dumps(commanded.default)
    assert untouched == torn
    assert (cleared.dry_run, cleared.cleared_pointer) == (False, True)
    assert cleared.before is not None and cleared.before.status == "dangling_pointer"
    assert cleared.after is not None and cleared.after.status == "none"
    assert after_act.bucket_id is None
    assert revealed_clear == _document(cleared)
    assert default_clear == _hidden(_document(cleared))
    assert (after_command.bucket_id, after_default_command.bucket_id) == (None, None)


def test_a_pointer_repair_that_names_another_profile_is_refused_and_the_selection_stays(tmp_path: Path) -> None:
    with _installed(tmp_path, "healthy") as (endpoint, root), _client(endpoint) as client:
        elsewhere = BucketPointer.selected(
            bucket_id=str(uuid4()), transition_revision=read_pointer(root).transition_revision + 1
        )
        write_pointer(root, elsewhere)
        refused = _refused(
            client,
            RuntimeRepairProfileRequest(
                request_id=uuid4(), frontend=_CLI, profile=_LABEL, clear_active=True, confirmed=True
            ),
        )
        commanded = _refusal("config", "repair", "profile", "--profile", _LABEL, "--clear-active", "--yes")
        selection = read_pointer(root)

    _same_refusal(refused, commanded)
    assert refused.detail.message_key == "cli.config.repair.profile_clear_active_mismatch"
    assert refused.detail.context_mapping() == {"profile": _LABEL}
    assert selection == elsewhere


def test_a_corrupt_pointer_refuses_every_act_but_the_one_that_repairs_it(tmp_path: Path) -> None:
    corrupt = get_registered_error_code(ActiveProfilePointerError).code

    with _installed(tmp_path, "fresh") as (endpoint, root), _client(endpoint) as client:
        pointer_path(root).write_bytes(_CORRUPT_POINTER)
        report = client.perform(RuntimeRepairReportRequest(request_id=uuid4(), frontend=_CLI), RuntimeRepairReportReply)
        logs = client.perform(RuntimeRepairLogsRequest(request_id=uuid4(), frontend=_CLI), RuntimeRepairLogsReply)
        probed = _profile(client)
        confirmed = client.perform(
            RuntimeRepairProfileRequest(request_id=uuid4(), frontend=_CLI, clear_active=True, confirmed=True),
            RuntimeRepairProfileReply,
        )
        record = pointer_path(root).read_bytes()

    for refused in (report, logs):
        assert isinstance(refused, RuntimeInstallationRefused)
        assert refused.detail.error_code == corrupt
    assert probed.before is not None
    assert (probed.before.status, probed.before.repairable_by_clearing_pointer) == ("pointer_unreadable", True)
    assert _recommended(probed.before.precondition_action) == "operator.profile.repair_active_pointer"
    # A record that cannot be parsed is left for manual recovery; the act refuses as the command does.
    assert isinstance(confirmed, RuntimeInstallationRefused)
    assert confirmed.detail.error_code == "REFUSED_ACTIVE_PROFILE_POINTER_MANUAL_RECOVERY"
    assert record == _CORRUPT_POINTER


@pytest.mark.parametrize("kind", ["fresh", "healthy", "torn"])
def test_the_installed_registration_names_the_recovery_commands_the_command_line_names(
    tmp_path: Path, kind: _RootKind
) -> None:
    with _installed(tmp_path, kind, as_installed=True) as (endpoint, _root), _client(endpoint) as client:
        report = _report(client)
        commanded_report = _command("config", "repair")
        profile = _profile(client)
        commanded_profile = _command("config", "repair", "profile")

    paths = [
        reference["cli_path"]
        for check in report.checks
        if check.precondition_action is not None
        for reference in (check.precondition_action["action"],)
        if isinstance(reference, dict)
    ]
    assert paths and all(paths)
    _assert_prints(report, commanded_report)
    _assert_prints(profile, commanded_profile)


@pytest.mark.parametrize("kind", ["fresh", "healthy", "torn"])
def test_every_frontend_is_admitted_and_answered_the_same_way(tmp_path: Path, kind: _RootKind) -> None:
    answers: dict[OperationFrontendProjection, dict[str, object]] = {}
    tails: list[tuple[str, ...]] = []
    named_kinds: list[str] = []

    with _installed(tmp_path, kind) as (endpoint, _root):
        _write_log()
        for frontend in OperationFrontendProjection:
            with _client(endpoint) as client:
                logs = _logs(client, 7, frontend)
                named = client.perform(
                    RuntimeRepairProfileRequest(request_id=uuid4(), frontend=frontend, profile=_LABEL),
                    RuntimeRepairProfileReply,
                )
                settled = {
                    "report": _report(client, frontend),
                    "logs": logs,
                    "profile": _profile(client, frontend=frontend),
                    "unconfirmed": _refused(
                        client, RuntimeRepairProfileRequest(request_id=uuid4(), frontend=frontend, clear_active=True)
                    ),
                    "named": named,
                }
            answers[frontend] = {
                name: reply.model_dump(mode="json", exclude={"request_id", "connection_id"})
                for name, reply in settled.items()
            }
            tails.append(logs.lines)
            named_kinds.append(named.kind)

    assert len(answers) == 3
    assert tails == [_LOG_LINES[-7:]] * 3
    assert named_kinds == ["repair_profile_reply" if kind == "healthy" else "installation_refused"] * 3
    for frontend in OperationFrontendProjection:
        assert answers[frontend] == answers[_CLI], frontend
