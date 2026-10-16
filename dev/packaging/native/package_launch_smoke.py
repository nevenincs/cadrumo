"""Compare direct and CMD launch of the actual staged desktop executable."""

import json
import os
import sys
import time
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from cadrumo.core.storage_environment import (
    ChildEnvironmentProfile,
    authority_root_setting_names,
    child_environment,
)
from cadrumo.core.type_guards import is_str_keyed_dict
from cadrumo.domain.calculations.registry.authority_store import AUTHORITY_DESCRIPTOR_FILENAME, AuthorityDescriptor
from cadrumo_client.contracts.contracts import ClientHello, RefusalCode, RefusalError
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_client.transport.windows_native_io import owned_windows_handle
from cadrumo_runtime.adapters.boot_record import RuntimeBootRecord, read_runtime_boot_record
from cadrumo_runtime.adapters.windows_process import WindowsOwnedProcess, WindowsProcessScope

from ..command_execution import run_command
from .build_directory import require_enrolled_build, require_enrolled_output
from .build_paths import build_paths
from .hashing import digest
from .installation import member


def _health_events(root: Path) -> list[dict[str, object]]:
    events = []
    for log in root.rglob("cadrumo-native.jsonl"):
        with log.open("rb") as stream:
            stream.seek(max(0, log.stat().st_size - 65536))
            lines = stream.read(65536).splitlines()
        for line in lines:
            try:
                event = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if is_str_keyed_dict(event):
                events.append(event)
    return events


def _health_facts(root: Path) -> dict[str, object]:
    """Project bounded native codes and timings; discard messages and coordinates."""
    code_names = (
        "invalid_arguments package_unavailable environment_failed timed_out output_limit spawn_failed "
        "read_failed write_failed resize_failed cleanup_failed session_unavailable queue_full cli_busy "
        "cli_wait_timed_out lock_poisoned log_unavailable desktop_unavailable webview_failed "
        "webview_process_failed webview_monitor_unavailable unsupported_platform instance_lock_foreign "
        "manager_unavailable manager_dispatch_failed installation_unavailable installation_refused "
        "installation_cancelled installation_failed installation_unsettled panic "
    )
    codes = set(code_names.split())
    stage_names = (
        "admission environment manager window shutdown job_escape instance storage package session supervision "
    )
    stages = set(stage_names.split())
    operation_names = "launch package environment cli terminal logging webview shutdown manager installation "
    operations = set(operation_names.split())
    io_kind_names = (
        "NotFound PermissionDenied ConnectionRefused ConnectionReset HostUnreachable NetworkUnreachable "
        "ConnectionAborted NotConnected AddrInUse AddrNotAvailable NetworkDown BrokenPipe AlreadyExists "
        "WouldBlock NotADirectory IsADirectory DirectoryNotEmpty ReadOnlyFilesystem FilesystemLoop "
        "StaleNetworkFileHandle InvalidInput InvalidData TimedOut WriteZero StorageFull NotSeekable "
        "QuotaExceeded FileTooLarge ResourceBusy ExecutableFileBusy Deadlock CrossesDevices TooManyLinks "
        "InvalidFilename ArgumentListTooLong Interrupted Unsupported UnexpectedEof OutOfMemory InProgress Other "
    )
    io_kinds = set(io_kind_names.split())
    failures, helpers = [], []
    for event in _health_events(root):
        if is_str_keyed_dict(failure := event.get("failure")):
            fact: dict[str, object] = {
                "stage": event.get("stage")
                if isinstance(event.get("stage"), str) and event.get("stage") in stages
                else None,
                "code": failure.get("code")
                if isinstance(failure.get("code"), str) and failure.get("code") in codes
                else "unexpected",
                "operation": failure.get("operation")
                if isinstance(failure.get("operation"), str) and failure.get("operation") in operations
                else None,
                "ioKind": failure.get("ioKind")
                if isinstance(failure.get("ioKind"), str) and failure.get("ioKind") in io_kinds
                else None,
                "osCode": failure.get("osCode")
                if type(value := failure.get("osCode")) is int and -(2**31) <= value <= 2**31 - 1
                else None,
            }
            failures.append(fact)
        if event.get("kind") == "helper_timing" and is_str_keyed_dict(timing := event.get("helperTiming")):
            fact = {
                key: value
                for key, value in timing.items()
                if key in {"admissionWaitMs", "spawnMs", "executionMs", "cleanupMs", "outputJoinMs", "totalMs"}
                and type(value) is int
                and 0 <= value <= 2**64 - 1
            }
            for key, allowed in (
                ("helperKind", {"read", "mutation"}),
                ("outcome", {"admission_refused", "spawn_failed", "execution_failed", "completed"}),
            ):
                if isinstance(value := timing.get(key), str) and value in allowed:
                    fact[key] = value
            helpers.append(fact)
    return {"schema": 1, "failures": failures[-8:], "helpers": helpers[-8:]}


def _require_health_running(process: WindowsOwnedProcess, root: Path, deadline: float) -> None:
    try:
        code = process.wait(timeout=0)
    except RefusalError as error:
        if error.reason != RefusalCode.DEADLINE_EXCEEDED:
            raise
    else:
        facts = json.dumps(_health_facts(root), sort_keys=True)
        raise AssertionError(f"Packaged health exited before recovery: exit={code}, facts={facts}")
    if time.monotonic() >= deadline:
        raise AssertionError("Packaged health did not restore verified runtime supervision within its deadline")


def _recover_runtime(
    process: WindowsOwnedProcess, scope: WindowsProcessScope, package: Path, root: Path, deadline: float
) -> None:
    import win32api
    import win32con
    import win32event
    import win32process

    manifest = json.loads((package / "data/package-manifest.json").read_text(encoding="utf-8"))
    authority = member(package, manifest["layout"]["paths"]["authority"])
    generation = AuthorityDescriptor.read(authority / AUTHORITY_DESCRIPTOR_FILENAME).logical_generation
    # Startup repair is not ongoing recovery: inject only after the shipping
    # desktop has observed its own controlled supervisor and runtime readiness.
    while not any(
        event.get("hostPid") == process.pid
        and event.get("source") == "desktop"
        and event.get("stage") == "manager"
        and event.get("kind") == "stage_completed"
        and event.get("outcome") == "ready"
        for event in _health_events(root)
    ):
        _require_health_running(process, root, deadline)
        time.sleep(0.05)
    with closing(WindowsEndpoint(storage_root=root)) as endpoint:
        expected = ClientHello(
            product_version=manifest["build"]["version"],
            storage_identity=endpoint.storage_identity,
            authority_generation=generation,
        )
        old_boot = None
        injected_after = 0
        while True:
            _require_health_running(process, root, deadline)
            try:
                native = endpoint.connect(timeout=0.2, expected_image=package / "bin/cadrumo-runtime.exe")
                try:
                    wire = VerifiedConnection(native, expected=expected, deadline=min(deadline, time.monotonic() + 2))
                except BaseException:
                    native.close()
                    raise
            except RefusalError as error:
                if error.reason not in {
                    RefusalCode.ENDPOINT_NOT_READY,
                    RefusalCode.CONNECTION_CLOSED,
                    RefusalCode.DEADLINE_EXCEEDED,
                }:
                    raise
                time.sleep(0.05)
                continue
            try:
                if wire.hello.authority_generation != generation:
                    raise AssertionError("Packaged runtime did not attest the selected authority generation")
                record = read_runtime_boot_record(storage_root=root)
                if (
                    not isinstance(record, RuntimeBootRecord)
                    or record.boot_id != wire.hello.boot_id
                    or record.pid != native.peer.process_id
                ):
                    # Endpoint serving precedes the supervisor's atomic boot publication.
                    time.sleep(0.05)
                    continue
                handle = owned_windows_handle(
                    win32api.OpenProcess(
                        win32con.PROCESS_TERMINATE | win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE,
                        False,
                        record.pid,
                    )
                )
                try:
                    native.verify_peer_process(int(handle))
                    if not scope.contains_process(int(handle)):
                        raise AssertionError("Packaged runtime is outside the health-owned native process job")
                    if old_boot is None:
                        old_boot = record.boot_id
                        injected_after = max(
                            (
                                sequence
                                for event in _health_events(root)
                                if event.get("hostPid") == process.pid
                                and isinstance(sequence := event.get("sequence"), int)
                            ),
                            default=0,
                        )
                        win32process.TerminateProcess(int(handle), 73)
                        if win32event.WaitForSingleObject(int(handle), 10_000) != win32event.WAIT_OBJECT_0:
                            raise AssertionError("Packaged health could not confirm exact runtime termination")
                    elif record.boot_id != old_boot and any(
                        event.get("hostPid") == process.pid
                        and event.get("stage") == "supervision"
                        and isinstance(sequence := event.get("sequence"), int)
                        and sequence > injected_after
                        and is_str_keyed_dict(fact := event.get("lifecycle"))
                        and fact.get("event") == "boot_record_confirmed"
                        and fact.get("pid") == record.pid
                        for event in _health_events(root)
                    ):
                        _require_health_running(process, root, deadline)
                        return
                finally:
                    handle.Close()
            finally:
                wire.close()
            time.sleep(0.05)


def health_environment(root: Path, received: Mapping[str, str]) -> dict[str, str]:
    """Build the packaged desktop's environment for a health run in disposable storage at ``root``.

    The desktop is a packaged image: its package alone supplies registry authority, and it
    refuses an inherited authority root, such as the one developer tooling exports.
    """
    authority = authority_root_setting_names()
    kept = {key: value for key, value in received.items() if key.upper() not in authority}
    return child_environment(ChildEnvironmentProfile.STRICT, root, received=kept)


def verify_health(executable: Path, storage_variable: str, *, scratch_root: Path) -> None:
    """Exercise shipping supervision and verified IPC in disposable native storage."""
    executable = executable.resolve(strict=True)
    scratch_root = scratch_root.resolve(strict=True)
    temporary = TemporaryDirectory(prefix="cadrumo-package-health-", dir=scratch_root, delete=False)
    with temporary as directory:
        root = Path(directory) / "storage"
        temporary_root = Path(directory) / "temporary"
        temporary_root.mkdir()
        environment = health_environment(root, os.environ)
        environment.update(
            {
                "CADRUMO_TEMP_DIR": str(temporary_root),
                "TEMP": str(temporary_root),
                "TMP": str(temporary_root),
                "TMPDIR": str(temporary_root),
            }
        )
        if environment.get(storage_variable) != str(root):
            raise AssertionError("Package health storage variable does not match the canonical root setting")
        scope = WindowsProcessScope()
        primary: BaseException | None = None
        try:
            process = scope.launch(
                executable=executable,
                arguments=("--check-health", "--hold-seconds", "60"),
                directory=executable.parent,
                environment=environment,
            )
            # Observe the existing 180s admission ceiling, 60s health hold and
            # bounded owned shutdown; individual IPC/probe budgets stay unchanged.
            deadline = time.monotonic() + 300
            _recover_runtime(process, scope, executable.parent, root, deadline)
            code = process.wait(timeout=max(0, deadline - time.monotonic()))
            if code != 0:
                raise AssertionError(f"Packaged runtime health failed: exit={code}")
            deadline = time.monotonic() + 5
            while scope.active_process_ids():
                if time.monotonic() >= deadline:
                    raise AssertionError("Packaged health returned success with surviving owned processes")
                time.sleep(0.05)
        except BaseException as error:
            primary = error
            try:
                facts = _health_facts(root)
                retained = json.dumps(facts, sort_keys=True)
                (Path(directory) / "health-failure.json").write_text(retained, encoding="utf-8")
                error.add_note(f"Packaged health failure facts before process settlement: {retained}")
            except BaseException as retention:
                error.add_note(f"Packaged health evidence retention failed: {type(retention).__name__}")
            raise
        finally:
            try:
                scope.terminate(timeout=10)
            except BaseException as cleanup:
                if primary is None:
                    raise
                primary.add_note(f"Packaged health process settlement failed: {type(cleanup).__name__}")
    temporary.cleanup()
    print("Packaged supervision and verified runtime IPC passed without installation; exact runtime crash recovered")


def _require_public_kit_file(path: Path) -> None:
    """Refuse private scratch ACLs retained on published Windows kit files."""
    if sys.platform != "win32":
        return
    import win32security

    descriptor = win32security.GetNamedSecurityInfo(
        str(path), win32security.SE_FILE_OBJECT, win32security.DACL_SECURITY_INFORMATION
    )
    control, _ = descriptor.GetSecurityDescriptorControl()
    if control & win32security.SE_DACL_PROTECTED:
        raise AssertionError(f"Public installation kit retains a private temporary ACL: {path.name}")


def verify_installation_kit(package: Path) -> None:
    """Reject desktop deliveries that cannot provision their background services."""
    manifest_path = package / "data/package-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    definition = manifest["layout"]["installation"]["bootstrap"]
    directory = member(package.parent, definition["directory"])
    descriptor = member(directory, definition["manifest"])
    _require_public_kit_file(descriptor)
    kit = json.loads(descriptor.read_text(encoding="utf-8"))
    maintenance = kit["maintenance"]
    if (
        kit["schema"] != 2
        or not maintenance["desktop_present"]
        or maintenance["manifest_sha256"] != digest(manifest_path)
    ):
        raise AssertionError("Desktop installation kit does not match this application package")
    expected = {"application"}
    if set(kit["artifacts"]) != expected:
        raise AssertionError("Desktop installation kit lacks its scope-aware release product")
    for artifact in (kit["runner"], *kit["artifacts"].values()):
        path = member(directory, artifact["path"])
        _require_public_kit_file(path)
        if digest(path) != artifact["sha256"]:
            raise AssertionError("Desktop installation kit contains a missing or changed artifact")


def main() -> None:
    """Require the staged image to launch identically through direct and CMD dispatch."""
    if sys.argv[1] == "--kit":
        verify_installation_kit(Path(sys.argv[2]).resolve(strict=True))
        return
    if sys.argv[1] == "--health":
        import argparse

        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--health", action="store_true")
        parser.add_argument(
            "--build", required=True, type=require_enrolled_build, help="The owning CMake binary directory."
        )
        parser.add_argument("executable", type=Path)
        parser.add_argument("storage_variable")
        arguments = parser.parse_args()
        testing = build_paths(arguments.build)["testing"]
        testing.mkdir(parents=True, exist_ok=True)
        verify_health(arguments.executable, arguments.storage_variable, scratch_root=testing)
        return
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build", required=True, type=require_enrolled_build, help="The owning CMake binary directory."
    )
    parser.add_argument("executable", type=Path)
    parser.add_argument("version")
    parser.add_argument("storage_variable")
    parser.add_argument("directory", type=require_enrolled_output)
    arguments = parser.parse_args()
    executable = arguments.executable.resolve(strict=True)
    version = arguments.version
    storage_variable = arguments.storage_variable
    testing = build_paths(arguments.build)["testing"]
    directory = arguments.directory
    if directory == testing or not directory.is_relative_to(testing):
        raise ValueError(f"Packaged launch scratch directory must be below the build testing output: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    shell = Path(os.environ["SYSTEMROOT"]) / "System32" / "cmd.exe"
    if not shell.is_absolute() or not shell.is_file():
        raise AssertionError("The Windows system command interpreter is unavailable")

    for explicit_storage in (False, True):
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() != "CADRUMO_DESKTOP_PACKAGE_ROOT"
            and (explicit_storage or key.upper() != storage_variable.upper())
        }
        environment["CADRUMO_TEST_IMAGE"] = f'"{executable}"'
        for argument in ("--version", "--help"):
            results = []
            for command in (
                [str(executable), argument],
                [str(shell), "/d", "/c", "%CADRUMO_TEST_IMAGE%", argument],
            ):
                result = run_command(
                    command,
                    cwd=directory,
                    environment=environment,
                    input_text="",
                    timeout_seconds=60,
                )
                if result.returncode != 0 or result.stderr or not result.stdout:
                    raise AssertionError(
                        f"Packaged launch failed (CMD={command[0] == str(shell)}, "
                        f"explicit_storage={explicit_storage}, argument={argument}): "
                        f"exit={result.returncode}, stderr={result.stderr!r}"
                    )
                results.append(result.stdout)
            if results[0] != results[1]:
                raise AssertionError("CMD and direct packaged launch produced different output")
            if argument == "--version" and results[0].strip() != f"CADRUMO {version}":
                raise AssertionError("Packaged launch reported an unexpected product version")
        sys.stdout.write(f"Direct/CMD packaged launch passed (explicit_storage={explicit_storage})\n")


if __name__ == "__main__":
    main()
