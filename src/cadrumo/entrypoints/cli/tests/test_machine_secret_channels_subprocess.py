"""Successful subprocess machine-secret channel integration paths."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.recovery_key import (
    RECOVERY_CODE_ALPHABET,
    RECOVERY_CODE_GROUP_COUNT,
    RECOVERY_CODE_GROUP_LENGTH,
    RECOVERY_CODE_SEPARATOR,
)
from cadrumo.tests.audited_process import WindowsStartupInfo, run_audited_process

from ....tests.inventory import SRC_CADRUMO
from ..config.tests.isolated_storage_fixture import COMPLETE_NATURAL_PERSON_FLAGS
from ._machine_secret_channels_support import (
    _CERTIFICATE_INPUT,
    _HARNESS,
    _NEW_PROFILE_INPUT,
    _WINDOWS_HANDLE_HARNESS,
    _assert_success,
    _base_interpreter_pythonpath,
    _combined,
    _complete_registered_profile,
    _envelope,
    _register_certificate_source,
    _restore_material,
    _run,
    _settings,
    bootstrap_interpreter,
    cleanup_keychain,
)
from .password_only_profile import FIXTURE_PROFILE_INPUT, register_password_only_profile
from .subprocess_cli import as_text_completed_process, subprocess_cli_env

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _cleanup_keychain(tmp_path: Path) -> None:
    cleanup_keychain(tmp_path)


def _assert_recovery_code_shape(document: bytes | bytearray) -> None:
    """The handed-over document is exactly one grouped recovery code and nothing else."""
    parsed = json.loads(bytes(document))
    assert set(parsed) == {"recovery_code"}
    groups = parsed["recovery_code"].split(RECOVERY_CODE_SEPARATOR)
    assert len(groups) == RECOVERY_CODE_GROUP_COUNT
    assert all(len(group) == RECOVERY_CODE_GROUP_LENGTH for group in groups)
    assert all(symbol in RECOVERY_CODE_ALPHABET for group in groups for symbol in group)


@pytest.mark.parametrize("channel", ("stdin", "fd"))
def test_login_succeeds_through_each_leaf_channel(tmp_path: Path, channel: str) -> None:
    root = tmp_path / "login"
    register_password_only_profile(root)
    payload = json.dumps({"passphrase": FIXTURE_PROFILE_INPUT})
    args = ["--format", "json", "config", "login", "s13-operator"]
    result = (
        _run(root, [*args, "--secrets-stdin"], stdin=payload)
        if channel == "stdin"
        else _run(root, [*args, "--secrets-fd", "{fd:0}"], inherited_payloads=(payload,), assert_closed_index=0)
    )
    document = _assert_success(result, root)
    assert document["command"] == "config.login"
    if channel == "fd":
        assert "S13_DESCRIPTOR_CLOSED" in result.stderr


def _run_profile_recovery_enable(root: Path, *, channel: str, payload: str) -> subprocess.CompletedProcess[str]:
    """Drive ``config profile recovery enable`` headlessly over the real two-pipe handoff."""
    passphrase_reader = passphrase_writer = -1
    handoff_reader, handoff_writer = os.pipe()
    verification_reader, verification_writer = os.pipe()
    if channel == "fd":
        passphrase_reader, passphrase_writer = os.pipe()
        os.write(passphrase_writer, payload.encode())
        os.close(passphrase_writer)
        passphrase_writer = -1
    supervisor_failure: list[BaseException] = []

    def supervise() -> None:
        handed = bytearray()
        try:
            while not handed.endswith(b"\n"):
                chunk = os.read(handoff_reader, 8193 - len(handed))
                if not chunk:
                    break
                handed.extend(chunk)
            _assert_recovery_code_shape(handed)
            os.write(verification_writer, handed)
        except BaseException as exc:
            supervisor_failure.append(exc)
        finally:
            handed[:] = b"\x00" * len(handed)
            os.close(handoff_reader)
            os.close(verification_writer)

    supervisor = threading.Thread(target=supervise, daemon=True)
    supervisor.start()
    command = ["--format", "json", "config", "profile", "recovery", "enable"]
    env = subprocess_cli_env(
        strip_prefixes=("AEAT_", "CADRUMO_", "PYTEST_"),
        extra={"PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring", "PYTHONPATH": _base_interpreter_pythonpath()},
    )
    settings = _settings(root)
    try:
        if os.name == "nt":
            import msvcrt

            handles = [msvcrt.get_osfhandle(handoff_writer), msvcrt.get_osfhandle(verification_reader)]
            secrets_handle = None if channel == "stdin" else msvcrt.get_osfhandle(passphrase_reader)
            if secrets_handle is not None:
                handles.append(secrets_handle)
            for handle in handles:
                os.set_handle_inheritable(handle, True)
            startup = subprocess.STARTUPINFO()
            startup.lpAttributeList = {"handle_list": handles}
            harness_payload = {
                "settings": settings,
                "secrets_handle": secrets_handle,
                "recovery_handoff_handle": handles[0],
                "recovery_verification_handle": handles[1],
            }
            args = [*command, *(("--secrets-stdin",) if channel == "stdin" else ())]
            result = run_audited_process(
                [bootstrap_interpreter(), "-c", _WINDOWS_HANDLE_HARNESS, json.dumps(harness_payload), *args],
                cwd=SRC_CADRUMO,
                env=env,
                input=payload if channel == "stdin" else None,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
                timeout=120,
                close_fds=True,
                startupinfo=startup,
            )
        else:
            descriptors = [handoff_writer, verification_reader, *(() if channel == "stdin" else (passphrase_reader,))]
            args = [
                *command,
                *(("--secrets-stdin",) if channel == "stdin" else ("--secrets-fd", str(passphrase_reader))),
                "--recovery-handoff-fd",
                str(handoff_writer),
                "--recovery-verification-fd",
                str(verification_reader),
            ]
            harness_payload = {"settings": settings, "assert_closed_descriptors": descriptors}
            result = run_audited_process(
                [sys.executable, "-c", _HARNESS, json.dumps(harness_payload), *args],
                cwd=SRC_CADRUMO,
                env=env,
                input=payload if channel == "stdin" else None,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
                timeout=120,
                pass_fds=tuple(descriptors),
            )
    finally:
        for descriptor in (handoff_writer, verification_reader, passphrase_reader, passphrase_writer):
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
        supervisor.join(timeout=5)
    assert not supervisor.is_alive()
    assert supervisor_failure == [], result.stderr
    return as_text_completed_process(result)


@pytest.mark.parametrize("channel", ("stdin", "fd"))
def test_profile_create_succeeds_through_each_leaf_channel(tmp_path: Path, channel: str) -> None:
    """Creation needs only the passphrase payload; a machine caller is never asked about recovery."""
    root = tmp_path / f"create-{channel}"
    payload = json.dumps({"passphrase": FIXTURE_PROFILE_INPUT, "passphrase_confirmation": FIXTURE_PROFILE_INPUT})
    args = ["--format", "json", "config", "profile", "create", f"created-{channel}", "--quiet"]
    result = (
        _run(root, [*args, "--secrets-stdin"], stdin=payload)
        if channel == "stdin"
        else _run(root, [*args, "--secrets-fd", "{fd:0}"], inherited_payloads=(payload,), assert_closed_index=0)
    )
    document = _assert_success(result, root)
    assert document["result"]["status"] == "created"
    codes = [notice["code"] for notice in document["notices"]]
    assert "PROFILE_RECOVERY_NOT_ENROLLED" in codes
    assert "PROFILE_RECOVERY_ENABLED" not in codes
    if channel == "fd":
        assert "S13_DESCRIPTOR_CLOSED" in result.stderr


@pytest.mark.parametrize("channel", ("stdin", "fd"))
def test_profile_recovery_enable_succeeds_through_each_leaf_channel(tmp_path: Path, channel: str) -> None:
    """The optional recovery door enrols headlessly over the descriptor pair, after the profile exists."""
    root = tmp_path / f"recovery-{channel}"
    register_password_only_profile(root)
    payload = json.dumps({"passphrase": FIXTURE_PROFILE_INPUT})
    result = _run_profile_recovery_enable(root, channel=channel, payload=payload)
    document = _assert_success(result, root)
    assert document["command"] == "config.profile.recovery.enable"
    assert document["result"]["enrolled"] is True
    assert document["result"]["changed"] is True
    assert [notice["code"] for notice in document["notices"]] == ["PROFILE_RECOVERY_ENABLED"]
    assert "recovery_code" not in result.stdout
    if os.name != "nt":
        assert result.stderr.count("S13_DESCRIPTOR_CLOSED") == (2 if channel == "stdin" else 3)


@pytest.mark.parametrize("channel", ("stdin", "fd"))
def test_passphrase_change_succeeds_through_each_leaf_channel(tmp_path: Path, channel: str) -> None:
    root = tmp_path / f"rotate-{channel}"
    register_password_only_profile(root)
    payload = json.dumps(
        {
            "current_passphrase": FIXTURE_PROFILE_INPUT,
            "new_passphrase": _NEW_PROFILE_INPUT,
            "new_passphrase_confirmation": _NEW_PROFILE_INPUT,
        }
    )
    args = ["--format", "json", "config", "passphrase", "change"]
    result = (
        _run(root, [*args, "--secrets-stdin"], stdin=payload)
        if channel == "stdin"
        else _run(root, [*args, "--secrets-fd", "{fd:0}"], inherited_payloads=(payload,), assert_closed_index=0)
    )
    document = _assert_success(result, root)
    assert document["result"]["changed"] is True


@pytest.mark.parametrize("channel", ("stdin", "fd"))
def test_restore_succeeds_through_each_leaf_channel(tmp_path: Path, channel: str) -> None:
    capsule = _restore_material(tmp_path / f"material-{channel}")
    root = tmp_path / f"restore-{channel}"
    args = [
        "--format",
        "json",
        "config",
        "profile",
        "archive",
        "import",
        f"restored-{channel}",
        "--file",
        str(capsule),
    ]
    payload = json.dumps({"passphrase": FIXTURE_PROFILE_INPUT})
    result = (
        _run(root, [*args, "--secrets-stdin"], stdin=payload)
        if channel == "stdin"
        else _run(root, [*args, "--secrets-fd", "{fd:0}"], inherited_payloads=(payload,), assert_closed_index=0)
    )
    document = _assert_success(result, root)
    assert document["result"]["authority"] == "password"
    assert document["result"]["recovery_enrolled"] is False


def test_fd_zero_is_a_real_leaf_secret_channel(tmp_path: Path) -> None:
    root = tmp_path / "fd-zero"
    outcome = register_password_only_profile(root)
    result = _run(
        root,
        ["--format", "json", "config", "login", outcome.profile_id, "--secrets-fd", "0"],
        stdin=json.dumps({"passphrase": FIXTURE_PROFILE_INPUT}),
        assert_closed_fd_zero=True,
    )
    assert _assert_success(result, root)["command"] == "config.login"
    assert "S13_DESCRIPTOR_CLOSED" in result.stderr


def test_keychain_free_root_auth_succeeds_for_real_read_via_stdin(tmp_path: Path) -> None:
    root = tmp_path / "root-read"
    register_password_only_profile(root, label="root-reader")
    result = _run(
        root,
        ["--format", "json", "--profile-secrets-stdin", "config", "profile", "history", "root-reader"],
        stdin=json.dumps({"profile_passphrase": FIXTURE_PROFILE_INPUT}),
    )
    document = _assert_success(result, root)
    assert document["command"] == "config.bucket.history"
    assert [notice["code"] for notice in document["notices"]] == ["config.login.session_not_persisted"]


@pytest.mark.parametrize(
    "sources", (("profile-fd", "leaf-stdin"), ("profile-stdin", "leaf-fd"), ("profile-fd", "leaf-fd"))
)
def test_certificate_write_accepts_every_valid_dual_source_combination(
    tmp_path: Path, sources: tuple[str, str]
) -> None:
    root = tmp_path / "certificate"
    register_password_only_profile(root, label="cert-operator")
    _register_certificate_source(root, name="s13-cert")
    profile_payload = json.dumps({"profile_passphrase": FIXTURE_PROFILE_INPUT})
    leaf_payload = json.dumps({"certificate_passphrase": _CERTIFICATE_INPUT})
    args = ["--format", "json"]
    inherited: list[str] = []
    stdin: str | None = None
    if sources[0] == "profile-fd":
        args.extend(("--profile-secrets-fd", f"{{fd:{len(inherited)}}}"))
        inherited.append(profile_payload)
    else:
        args.append("--profile-secrets-stdin")
        stdin = profile_payload
    args.extend(("config", "auth", "certificate", "secret", "set", "--name", "s13-cert"))
    if sources[1] == "leaf-fd":
        args.extend(("--secrets-fd", f"{{fd:{len(inherited)}}}"))
        inherited.append(leaf_payload)
    else:
        args.append("--secrets-stdin")
        stdin = leaf_payload
    result = _run(
        root,
        args,
        stdin=stdin,
        inherited_payloads=inherited,
        assert_closed_indices=tuple(range(len(inherited))),
    )
    document = _assert_success(result, root)
    assert document["command"] == "config.auth.certificate.secret.set"
    assert document["result"]["has_secret"] is True
    assert [notice["code"] for notice in document["notices"]] == ["config.login.session_not_persisted"]
    assert result.stderr.count("S13_DESCRIPTOR_CLOSED") == len(inherited)


def test_platform_descriptor_bootstrap_authenticates_real_read(tmp_path: Path) -> None:
    if sys.platform != "win32":
        root = tmp_path / "posix-descriptor-reader"
        register_password_only_profile(root, label="posix-reader")
        result = _run(
            root,
            [
                "--format",
                "json",
                "--profile-secrets-fd",
                "{fd:0}",
                "config",
                "profile",
                "history",
                "posix-reader",
            ],
            inherited_payloads=(json.dumps({"profile_passphrase": FIXTURE_PROFILE_INPUT}),),
            assert_closed_index=0,
        )
        document = _assert_success(result, root)
        assert document["command"] == "config.bucket.history"
        assert "S13_DESCRIPTOR_CLOSED" in result.stderr
        return

    import msvcrt

    root = tmp_path / "windows-handle"
    register_password_only_profile(root, label="windows-reader")
    reader, writer = os.pipe()
    try:
        os.write(writer, json.dumps({"profile_passphrase": FIXTURE_PROFILE_INPUT}).encode())
        os.close(writer)
        writer = -1
        handle = msvcrt.get_osfhandle(reader)
        os.set_handle_inheritable(handle, True)
        startup = subprocess.STARTUPINFO()
        startup.lpAttributeList = {"handle_list": [handle]}
        env = subprocess_cli_env(
            strip_prefixes=("AEAT_", "CADRUMO_", "PYTEST_"),
            extra={
                "PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring",
                "PYTHONPATH": _base_interpreter_pythonpath(),
                "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
                "CADRUMO_SECRET_STORE_DIR": str(root / "fallback-store"),
                "CADRUMO_OUTPUT_LANGUAGE": "en",
            },
        )
        result = run_audited_process(
            [
                bootstrap_interpreter(),
                "-m",
                "cadrumo.entrypoints.cli._windows_profile_secret_bootstrap",
                "--profile-handle",
                str(handle),
                "--",
                "--format",
                "json",
                "config",
                "profile",
                "history",
                "windows-reader",
            ],
            cwd=SRC_CADRUMO,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=180,
            close_fds=True,
            startupinfo=startup,
        )
    finally:
        if writer >= 0:
            os.close(writer)
        os.close(reader)
    document = _assert_success(as_text_completed_process(result), root)
    assert document["command"] == "config.bucket.history"
    assert [notice["code"] for notice in document["notices"]] == ["config.login.session_not_persisted"]


def _windows_recovery_handle_allowlist(
    *,
    handoff_reader: int,
    handoff_writer: int,
    verification_reader: int,
    verification_writer: int,
) -> tuple[int, int, WindowsStartupInfo]:
    """Return the inheritable handoff/verification HANDLEs and their startup allowlist.

    The ``sys.platform == "win32"`` block, rather than the caller's guard, is
    what establishes the platform for :mod:`msvcrt` and ``STARTUPINFO``: it is
    the only guard shape every checker this project runs narrows on.
    """
    if sys.platform == "win32":
        import msvcrt

        handoff_handle = msvcrt.get_osfhandle(handoff_writer)
        verification_handle = msvcrt.get_osfhandle(verification_reader)
        os.set_handle_inheritable(msvcrt.get_osfhandle(handoff_reader), False)
        os.set_handle_inheritable(msvcrt.get_osfhandle(verification_writer), False)
        os.set_handle_inheritable(handoff_handle, True)
        os.set_handle_inheritable(verification_handle, True)
        startup = subprocess.STARTUPINFO()
        startup.lpAttributeList = {"handle_list": [handoff_handle, verification_handle]}
        return handoff_handle, verification_handle, startup
    raise RuntimeError("Windows HANDLE transport requested on a non-Windows host")


def _assert_windows_recovery_handles_complete_real_headless_enrolment(tmp_path: Path) -> None:
    """Writable handoff and readable proof HANDLEs survive a real process boundary."""
    root = tmp_path / "windows-recovery-enable"
    register_password_only_profile(root, label="windows-recovery")
    handoff_reader, handoff_writer = os.pipe()
    verification_reader, verification_writer = os.pipe()
    handoff_handle, verification_handle, startup = _windows_recovery_handle_allowlist(
        handoff_reader=handoff_reader,
        handoff_writer=handoff_writer,
        verification_reader=verification_reader,
        verification_writer=verification_writer,
    )
    env = subprocess_cli_env(
        strip_prefixes=("AEAT_", "CADRUMO_", "PYTEST_"),
        extra={
            "PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring",
            "PYTHONPATH": _base_interpreter_pythonpath(),
            "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
            "CADRUMO_SECRET_STORE_DIR": str(root / "fallback-store"),
            "CADRUMO_OUTPUT_LANGUAGE": "en",
            "CADRUMO_PROFILE_KDF_MEASURE_CALIBRATION": "false",
        },
    )
    supervisor_failure: list[BaseException] = []
    supervisor_state: list[str] = ["waiting-handoff"]

    def release_parent_copies(_process: object) -> None:
        # Only once the child holds its inherited HANDLEs: closing them before
        # the launch invalidates the handle list, and keeping them open after it
        # withholds end-of-stream from the supervisor reading the handoff pipe.
        os.close(handoff_writer)
        os.close(verification_reader)

    def supervise_recovery() -> None:
        handed = bytearray()
        try:
            while chunk := os.read(handoff_reader, 8193 - len(handed)):
                handed.extend(chunk)
            supervisor_state[0] = "handoff-read"
            _assert_recovery_code_shape(handed)
            os.write(verification_writer, bytes(handed))
            supervisor_state[0] = "verification-written"
        except BaseException as exc:
            supervisor_failure.append(exc)
        finally:
            handed[:] = b"\x00" * len(handed)
            os.close(handoff_reader)
            os.close(verification_writer)

    supervisor = threading.Thread(target=supervise_recovery, daemon=True)
    supervisor.start()
    try:
        result = run_audited_process(
            [
                bootstrap_interpreter(),
                "-m",
                "cadrumo.entrypoints.cli._windows_profile_secret_bootstrap",
                "--recovery-handoff-handle",
                str(handoff_handle),
                "--recovery-verification-handle",
                str(verification_handle),
                "--",
                "--format",
                "json",
                "config",
                "profile",
                "recovery",
                "enable",
                "--secrets-stdin",
            ],
            cwd=SRC_CADRUMO,
            env=env,
            input=json.dumps({"passphrase": FIXTURE_PROFILE_INPUT}),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=45,
            close_fds=True,
            startupinfo=startup,
            after_spawn=release_parent_copies,
        )
    except subprocess.TimeoutExpired:
        raise AssertionError(
            f"recovery bootstrap stalled at {supervisor_state[0]}; supervisor_failure={supervisor_failure!r}"
        ) from None
    supervisor.join(timeout=5)
    assert not supervisor.is_alive()
    assert supervisor_failure == [], result.stderr
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["result"]["enrolled"] is True


def _assert_posix_recovery_descriptors_complete_real_headless_enrolment(tmp_path: Path) -> None:
    """Writable handoff and readable proof descriptors cross a real POSIX boundary."""
    root = tmp_path / "posix-recovery-enable"
    register_password_only_profile(root, label="posix-recovery")
    handoff_reader, handoff_writer = os.pipe()
    verification_reader, verification_writer = os.pipe()
    supervisor_failure: list[BaseException] = []

    def supervise_recovery() -> None:
        handed = bytearray()
        try:
            while not handed.endswith(b"\n"):
                chunk = os.read(handoff_reader, 8193 - len(handed))
                if not chunk:
                    break
                handed.extend(chunk)
            _assert_recovery_code_shape(handed)
            os.write(verification_writer, bytes(handed))
        except BaseException as exc:
            supervisor_failure.append(exc)
        finally:
            handed[:] = b"\x00" * len(handed)
            os.close(handoff_reader)
            os.close(verification_writer)

    supervisor = threading.Thread(target=supervise_recovery, daemon=True)
    supervisor.start()
    env = subprocess_cli_env(
        strip_prefixes=("AEAT_", "CADRUMO_", "PYTEST_"),
        extra={
            "PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring",
            "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
            "CADRUMO_SECRET_STORE_DIR": str(root / "fallback-store"),
            "CADRUMO_OUTPUT_LANGUAGE": "en",
            "CADRUMO_PROFILE_KDF_MEASURE_CALIBRATION": "false",
        },
    )
    try:
        result = run_audited_process(
            [
                sys.executable,
                "-c",
                "from cadrumo.entrypoints.cli.main import main; main()",
                "--format",
                "json",
                "config",
                "profile",
                "recovery",
                "enable",
                "--secrets-stdin",
                "--recovery-handoff-fd",
                str(handoff_writer),
                "--recovery-verification-fd",
                str(verification_reader),
            ],
            cwd=SRC_CADRUMO,
            env=env,
            input=json.dumps({"passphrase": FIXTURE_PROFILE_INPUT}),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            timeout=45,
            pass_fds=(handoff_writer, verification_reader),
        )
    finally:
        os.close(handoff_writer)
        os.close(verification_reader)
    supervisor.join(timeout=5)
    assert not supervisor.is_alive()
    assert supervisor_failure == [], result.stderr
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["result"]["enrolled"] is True


def test_platform_recovery_descriptors_complete_real_headless_enrolment(tmp_path: Path) -> None:
    """Run the native real-process recovery transport on every supported host."""
    if sys.platform == "win32":
        _assert_windows_recovery_handles_complete_real_headless_enrolment(tmp_path)
        return
    _assert_posix_recovery_descriptors_complete_real_headless_enrolment(tmp_path)


def test_platform_root_descriptor_plus_leaf_stdin_performs_real_certificate_write(
    tmp_path: Path,
) -> None:
    """The platform descriptor route composes with portable leaf stdin."""
    if sys.platform != "win32":
        root = tmp_path / "posix-descriptor-certificate"
        register_password_only_profile(root, label="posix-writer")
        _register_certificate_source(root, name="s13-posix-cert")
        result = _run(
            root,
            [
                "--format",
                "json",
                "--profile-secrets-fd",
                "{fd:0}",
                "config",
                "auth",
                "certificate",
                "secret",
                "set",
                "--name",
                "s13-posix-cert",
                "--secrets-stdin",
            ],
            stdin=json.dumps({"certificate_passphrase": _CERTIFICATE_INPUT}),
            inherited_payloads=(json.dumps({"profile_passphrase": FIXTURE_PROFILE_INPUT}),),
            assert_closed_index=0,
        )
        document = _assert_success(result, root)
        assert document["command"] == "config.auth.certificate.secret.set"
        assert document["result"]["has_secret"] is True
        assert "S13_DESCRIPTOR_CLOSED" in result.stderr
        return

    import msvcrt

    root = tmp_path / "windows-certificate"
    register_password_only_profile(root, label="windows-writer")
    _register_certificate_source(root, name="s13-windows-cert")
    reader, writer = os.pipe()
    try:
        os.write(writer, json.dumps({"profile_passphrase": FIXTURE_PROFILE_INPUT}).encode())
        os.close(writer)
        writer = -1
        handle = msvcrt.get_osfhandle(reader)
        os.set_handle_inheritable(handle, True)
        startup = subprocess.STARTUPINFO()
        startup.lpAttributeList = {"handle_list": [handle]}
        env = subprocess_cli_env(
            strip_prefixes=("AEAT_", "CADRUMO_", "PYTEST_"),
            extra={
                "PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring",
                "PYTHONPATH": _base_interpreter_pythonpath(),
                "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
                "CADRUMO_SECRET_STORE_DIR": str(root / "fallback-store"),
                "CADRUMO_OUTPUT_LANGUAGE": "en",
            },
        )
        result = run_audited_process(
            [
                bootstrap_interpreter(),
                "-m",
                "cadrumo.entrypoints.cli._windows_profile_secret_bootstrap",
                "--profile-handle",
                str(handle),
                "--",
                "--format",
                "json",
                "config",
                "auth",
                "certificate",
                "secret",
                "set",
                "--name",
                "s13-windows-cert",
                "--secrets-stdin",
            ],
            cwd=SRC_CADRUMO,
            env=env,
            input=json.dumps({"certificate_passphrase": _CERTIFICATE_INPUT}),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=180,
            close_fds=True,
            startupinfo=startup,
        )
    finally:
        if writer >= 0:
            os.close(writer)
        os.close(reader)
    document = _assert_success(as_text_completed_process(result), root)
    assert document["command"] == "config.auth.certificate.secret.set"
    assert document["result"]["has_secret"] is True
    assert [notice["code"] for notice in document["notices"]] == ["config.login.session_not_persisted"]


_PROFILE_AUTHENTICATION = json.dumps({"profile_passphrase": FIXTURE_PROFILE_INPUT})
_LOGIN_AUTHENTICATION = json.dumps({"passphrase": FIXTURE_PROFILE_INPUT})

#: Every profile leaf, as (id, argv after ``--format json``, stdin). ``{archive}``
#: names the sealed file the export leaf writes and the inspect leaf reads.
_COLD_LEAVES: tuple[tuple[str, tuple[str, ...], str | None], ...] = (
    ("status", ("--profile-secrets-stdin", "config", "profile", "status"), _PROFILE_AUTHENTICATION),
    ("view", ("--profile-secrets-stdin", "config", "profile", "view"), _PROFILE_AUTHENTICATION),
    ("validate", ("--profile-secrets-stdin", "config", "profile", "validate"), _PROFILE_AUTHENTICATION),
    (
        "edit",
        ("--profile-secrets-stdin", "config", "profile", "edit", "--quiet", "--notes", "cold"),
        _PROFILE_AUTHENTICATION,
    ),
    ("complete-setup", ("--profile-secrets-stdin", "config", "profile", "complete-setup"), _PROFILE_AUTHENTICATION),
    (
        "add-row",
        ("--profile-secrets-stdin", "config", "profile", "add-row", "activities", "--value", "description=Taller"),
        _PROFILE_AUTHENTICATION,
    ),
    (
        "descendiente-list",
        ("--profile-secrets-stdin", "config", "profile", "descendiente", "list"),
        _PROFILE_AUTHENTICATION,
    ),
    (
        "descendiente-add",
        (
            "--profile-secrets-stdin",
            "config",
            "profile",
            "descendiente",
            "add",
            "--descendiente",
            "NACIMIENTO=2015-01-01",
        ),
        _PROFILE_AUTHENTICATION,
    ),
    (
        "descendiente-remove",
        ("--profile-secrets-stdin", "config", "profile", "descendiente", "remove", "0"),
        _PROFILE_AUTHENTICATION,
    ),
    (
        "capabilities-view",
        ("--profile-secrets-stdin", "config", "profile", "capabilities", "view"),
        _PROFILE_AUTHENTICATION,
    ),
    (
        "capabilities-set",
        ("--profile-secrets-stdin", "config", "profile", "capabilities", "set", "llm_vision", "off"),
        _PROFILE_AUTHENTICATION,
    ),
    ("history", ("--profile-secrets-stdin", "config", "profile", "history"), _PROFILE_AUTHENTICATION),
    (
        "archive-export",
        ("--profile-secrets-stdin", "config", "profile", "archive", "export", "--output", "{archive}"),
        _PROFILE_AUTHENTICATION,
    ),
    ("archive-inspect", ("config", "profile", "archive", "inspect", "--file", "{archive}"), None),
    ("delete-preflight", ("config", "profile", "delete", "s13-operator"), None),
    ("list", ("config", "profile", "list"), None),
    ("login", ("config", "login", "s13-operator", "--secrets-stdin"), _LOGIN_AUTHENTICATION),
    ("logout", ("config", "logout"), None),
)

#: The leaves that refuse by contract rather than succeed, per setup state:
#: an unfinished record cannot pass ``validate`` or be promoted, the profile
#: has no descendant at index 0, and the selected profile cannot be deleted.
_COLD_REFUSALS = {
    "incomplete": {"validate", "complete-setup", "descendiente-remove", "delete-preflight"},
    "complete": {"descendiente-remove", "delete-preflight"},
}


@pytest.fixture(scope="module")
def _cold_profile_templates(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Path]]:
    """One registered profile per setup state, each built by separate processes."""
    base = tmp_path_factory.mktemp("cold-profile-templates")
    incomplete = base / "incomplete"
    complete = base / "complete"
    register_password_only_profile(incomplete)
    register_password_only_profile(complete)
    _complete_registered_profile(complete, flags=COMPLETE_NATURAL_PERSON_FLAGS)
    try:
        yield {"incomplete": incomplete, "complete": complete}
    finally:
        cleanup_keychain(base)


@pytest.mark.parametrize("state", ("incomplete", "complete"))
@pytest.mark.parametrize(("leaf", "argv", "stdin"), _COLD_LEAVES, ids=[leaf for leaf, _, _ in _COLD_LEAVES])
def test_each_profile_leaf_answers_as_the_first_command_of_a_process(
    tmp_path: Path,
    _cold_profile_templates: dict[str, Path],
    state: str,
    leaf: str,
    argv: tuple[str, ...],
    stdin: str | None,
) -> None:
    """No profile leaf may depend on an earlier command having warmed the process.

    Governed vocabularies (entity types, IRPF income categories, the retention
    floor) resolve only inside a pinned authority operation. Reproduction:
    ``config profile status`` on a completed profile, and before it the
    overview projection and the retention floor, resolved one with no
    operation open and failed with an internal error -- but only as the first
    command of a process; in a process where a leased call had already run,
    the same command succeeded. So every leaf runs here as the first command
    of its own fresh process, against a record in each setup state.
    """
    root = tmp_path / "storage"
    shutil.copytree(_cold_profile_templates[state], root)
    archive = tmp_path / "profile.cadrumo-bucket.tar.gz"
    if leaf == "archive-inspect":
        exported = _run(
            root,
            [
                "--format",
                "json",
                "--profile-secrets-stdin",
                "config",
                "profile",
                "archive",
                "export",
                "--output",
                str(archive),
            ],
            stdin=_PROFILE_AUTHENTICATION,
        )
        assert exported.returncode == 0, _combined(exported)

    result = _run(
        root,
        ["--format", "json", *(str(archive) if argument == "{archive}" else argument for argument in argv)],
        stdin=stdin,
    )

    envelope = _envelope(result)
    error_code = str((envelope.get("error") or {}).get("code", ""))
    assert not error_code.startswith("INTERNAL"), _combined(result)
    expected = 2 if leaf in _COLD_REFUSALS[state] else 0
    assert result.returncode == expected, _combined(result)
    if stdin is _PROFILE_AUTHENTICATION and expected == 0:
        # No keychain is usable here, so authenticating spent the passphrase on
        # this process alone. Reproduction: ``config profile edit`` succeeded
        # without saying so, because the wizard emits its own envelope and
        # never received the notice root authentication had staged.
        codes = [notice["code"] for notice in envelope["notices"]]
        assert "config.login.session_not_persisted" in codes, _combined(result)
