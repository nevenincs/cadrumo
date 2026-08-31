"""Successful subprocess machine-secret channel integration paths."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from contextlib import suppress
from pathlib import Path

import pytest

from ....tests import SRC_CADRUMO
from ....tests.subprocess_cli import subprocess_cli_env
from .._windows_profile_secret_bootstrap import bootstrap_interpreter
from ._machine_secret_channels_support import (
    _CERTIFICATE_SECRET,
    _HARNESS,
    _NEW_PROFILE_SECRET,
    _PROFILE_SECRET,
    _WINDOWS_HANDLE_HARNESS,
    _assert_success,
    _base_interpreter_pythonpath,
    _register,
    _register_certificate_source,
    _restore_material,
    _run,
    _settings,
    cleanup_keychain,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _cleanup_keychain(tmp_path: Path) -> None:
    cleanup_keychain(tmp_path)


@pytest.mark.parametrize("channel", ("stdin", "fd"))
def test_login_succeeds_through_each_leaf_channel(tmp_path: Path, channel: str) -> None:
    root = tmp_path / "login"
    _register(root)
    payload = json.dumps({"passphrase": _PROFILE_SECRET})
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


def _run_profile_create_with_recovery(root: Path, *, channel: str, payload: str) -> subprocess.CompletedProcess[str]:
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
            assert len(json.loads(handed)["recovery_mnemonic"].split()) == 24
            os.write(verification_writer, handed)
        except BaseException as exc:
            supervisor_failure.append(exc)
        finally:
            handed[:] = b"\x00" * len(handed)
            os.close(handoff_reader)
            os.close(verification_writer)

    supervisor = threading.Thread(target=supervise, daemon=True)
    supervisor.start()
    command = ["--format", "json", "config", "profile", "create", f"created-{channel}", "--quiet"]
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
            result = subprocess.run(  # noqa: S603 - fixed interpreter and test-owned command
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
            result = subprocess.run(  # noqa: S603 - fixed interpreter and test-owned command
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
    return result


@pytest.mark.parametrize("channel", ("stdin", "fd"))
def test_profile_create_succeeds_through_each_leaf_channel(tmp_path: Path, channel: str) -> None:
    root = tmp_path / f"create-{channel}"
    payload = json.dumps({"passphrase": _PROFILE_SECRET, "passphrase_confirmation": _PROFILE_SECRET})
    result = _run_profile_create_with_recovery(root, channel=channel, payload=payload)
    document = _assert_success(result, root)
    assert document["result"]["status"] == "created"
    if channel == "fd":
        assert "S13_DESCRIPTOR_CLOSED" in result.stderr


@pytest.mark.parametrize("channel", ("stdin", "fd"))
def test_passphrase_change_succeeds_through_each_leaf_channel(tmp_path: Path, channel: str) -> None:
    root = tmp_path / f"rotate-{channel}"
    _register(root)
    payload = json.dumps(
        {
            "current_passphrase": _PROFILE_SECRET,
            "new_passphrase": _NEW_PROFILE_SECRET,
            "new_passphrase_confirmation": _NEW_PROFILE_SECRET,
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
@pytest.mark.parametrize("door", ("passphrase", "recovery"))
def test_both_restore_doors_succeed_through_each_leaf_channel(tmp_path: Path, channel: str, door: str) -> None:
    capsule, artifact, phrase = _restore_material(tmp_path / f"material-{channel}-{door}")
    root = tmp_path / f"restore-{channel}-{door}"
    args = [
        "--format",
        "json",
        "config",
        "profile",
        "archive",
        "import",
        f"restored-{channel}-{door}",
        "--file",
        str(capsule),
    ]
    if door == "recovery":
        args.extend(("--artifact", str(artifact)))
        payload = json.dumps({"recovery_secret": phrase})
    else:
        payload = json.dumps({"passphrase": _PROFILE_SECRET})
    result = (
        _run(root, [*args, "--secrets-stdin"], stdin=payload)
        if channel == "stdin"
        else _run(root, [*args, "--secrets-fd", "{fd:0}"], inherited_payloads=(payload,), assert_closed_index=0)
    )
    document = _assert_success(result, root, extra_secrets=(phrase,))
    assert document["result"]["authority"] == ("recovery_artifact" if door == "recovery" else "password")


def test_fd_zero_is_a_real_leaf_secret_channel(tmp_path: Path) -> None:
    root = tmp_path / "fd-zero"
    outcome, _, _ = _register(root)
    result = _run(
        root,
        ["--format", "json", "config", "login", outcome.profile_id, "--secrets-fd", "0"],
        stdin=json.dumps({"passphrase": _PROFILE_SECRET}),
        assert_closed_fd_zero=True,
    )
    assert _assert_success(result, root)["command"] == "config.login"
    assert "S13_DESCRIPTOR_CLOSED" in result.stderr


def test_keychain_free_root_auth_succeeds_for_real_read_via_stdin(tmp_path: Path) -> None:
    root = tmp_path / "root-read"
    _register(root, label="root-reader")
    result = _run(
        root,
        ["--format", "json", "--profile-secrets-stdin", "config", "profile", "history", "root-reader"],
        stdin=json.dumps({"profile_passphrase": _PROFILE_SECRET}),
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
    _register(root, label="cert-operator")
    _register_certificate_source(root, name="s13-cert")
    profile_payload = json.dumps({"profile_passphrase": _PROFILE_SECRET})
    leaf_payload = json.dumps({"certificate_passphrase": _CERTIFICATE_SECRET})
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
        _register(root, label="posix-reader")
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
            inherited_payloads=(json.dumps({"profile_passphrase": _PROFILE_SECRET}),),
            assert_closed_index=0,
        )
        document = _assert_success(result, root)
        assert document["command"] == "config.bucket.history"
        assert "S13_DESCRIPTOR_CLOSED" in result.stderr
        return

    import msvcrt

    root = tmp_path / "windows-handle"
    _register(root, label="windows-reader")
    reader, writer = os.pipe()
    try:
        os.write(writer, json.dumps({"profile_passphrase": _PROFILE_SECRET}).encode())
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
                "CADRUMO_SECRET_STORE_BACKEND": "auto",
                "CADRUMO_OUTPUT_LANGUAGE": "en",
            },
        )
        result = subprocess.run(  # noqa: S603 - fixed interpreter and module
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
    document = _assert_success(result, root)
    assert document["command"] == "config.bucket.history"
    assert [notice["code"] for notice in document["notices"]] == ["config.login.session_not_persisted"]


def _assert_windows_recovery_handles_complete_real_headless_creation(tmp_path: Path) -> None:
    """Writable handoff and readable proof HANDLEs survive a real process boundary."""
    import msvcrt

    root = tmp_path / "windows-recovery-create"
    handoff_reader, handoff_writer = os.pipe()
    verification_reader, verification_writer = os.pipe()
    handoff_handle = msvcrt.get_osfhandle(handoff_writer)
    verification_handle = msvcrt.get_osfhandle(verification_reader)
    os.set_handle_inheritable(msvcrt.get_osfhandle(handoff_reader), False)
    os.set_handle_inheritable(msvcrt.get_osfhandle(verification_writer), False)
    os.set_handle_inheritable(handoff_handle, True)
    os.set_handle_inheritable(verification_handle, True)
    startup = subprocess.STARTUPINFO()
    startup.lpAttributeList = {"handle_list": [handoff_handle, verification_handle]}
    env = subprocess_cli_env(
        strip_prefixes=("AEAT_", "CADRUMO_", "PYTEST_"),
        extra={
            "PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring",
            "PYTHONPATH": _base_interpreter_pythonpath(),
            "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
            "CADRUMO_SECRET_STORE_DIR": str(root / "fallback-store"),
            "CADRUMO_SECRET_STORE_BACKEND": "auto",
            "CADRUMO_OUTPUT_LANGUAGE": "en",
            "CADRUMO_PROFILE_KDF_MEASURE_CALIBRATION": "false",
        },
    )
    process = subprocess.Popen(  # noqa: S603 - fixed interpreter and module
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
            "create",
            "windows-recovery",
            "--quiet",
            "--secrets-stdin",
        ],
        cwd=SRC_CADRUMO,
        env=env,
        text=True,
        encoding="utf-8",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
        startupinfo=startup,
    )
    os.close(handoff_writer)
    os.close(verification_reader)
    supervisor_failure: list[BaseException] = []
    supervisor_state: list[str] = ["waiting-handoff"]

    def supervise_recovery() -> None:
        handed = bytearray()
        try:
            while chunk := os.read(handoff_reader, 8193 - len(handed)):
                handed.extend(chunk)
            supervisor_state[0] = "handoff-read"
            document = json.loads(handed)
            assert len(document["recovery_mnemonic"].split()) == 24
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
        stdout, stderr = process.communicate(
            input=json.dumps({"passphrase": _PROFILE_SECRET, "passphrase_confirmation": _PROFILE_SECRET}),
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        raise AssertionError(
            f"recovery bootstrap stalled at {supervisor_state[0]}; "
            f"supervisor_failure={supervisor_failure!r}; stderr={stderr[-2000:]!r}"
        ) from None
    supervisor.join(timeout=5)
    assert not supervisor.is_alive()
    assert supervisor_failure == [], stderr
    assert process.returncode == 0, stderr
    assert json.loads(stdout)["result"]["profile_name"] == "windows-recovery"


def _assert_posix_recovery_descriptors_complete_real_headless_creation(tmp_path: Path) -> None:
    """Writable handoff and readable proof descriptors cross a real POSIX boundary."""
    root = tmp_path / "posix-recovery-create"
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
            document = json.loads(handed)
            assert len(document["recovery_mnemonic"].split()) == 24
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
            "CADRUMO_SECRET_STORE_BACKEND": "auto",
            "CADRUMO_OUTPUT_LANGUAGE": "en",
            "CADRUMO_PROFILE_KDF_MEASURE_CALIBRATION": "false",
        },
    )
    try:
        result = subprocess.run(  # noqa: S603 - fixed interpreter and module
            [
                sys.executable,
                "-c",
                "from cadrumo.entrypoints.cli import main; main()",
                "--format",
                "json",
                "config",
                "profile",
                "create",
                "posix-recovery",
                "--quiet",
                "--secrets-stdin",
                "--recovery-handoff-fd",
                str(handoff_writer),
                "--recovery-verification-fd",
                str(verification_reader),
            ],
            cwd=SRC_CADRUMO,
            env=env,
            input=json.dumps({"passphrase": _PROFILE_SECRET, "passphrase_confirmation": _PROFILE_SECRET}),
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
    assert json.loads(result.stdout)["result"]["profile_name"] == "posix-recovery"


def test_platform_recovery_descriptors_complete_real_headless_creation(tmp_path: Path) -> None:
    """Run the native real-process recovery transport on every supported host."""
    if sys.platform == "win32":
        _assert_windows_recovery_handles_complete_real_headless_creation(tmp_path)
        return
    _assert_posix_recovery_descriptors_complete_real_headless_creation(tmp_path)


def test_platform_root_descriptor_plus_leaf_stdin_performs_real_certificate_write(
    tmp_path: Path,
) -> None:
    """The platform descriptor route composes with portable leaf stdin."""
    if sys.platform != "win32":
        root = tmp_path / "posix-descriptor-certificate"
        _register(root, label="posix-writer")
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
            stdin=json.dumps({"certificate_passphrase": _CERTIFICATE_SECRET}),
            inherited_payloads=(json.dumps({"profile_passphrase": _PROFILE_SECRET}),),
            assert_closed_index=0,
        )
        document = _assert_success(result, root)
        assert document["command"] == "config.auth.certificate.secret.set"
        assert document["result"]["has_secret"] is True
        assert "S13_DESCRIPTOR_CLOSED" in result.stderr
        return

    import msvcrt

    root = tmp_path / "windows-certificate"
    _register(root, label="windows-writer")
    _register_certificate_source(root, name="s13-windows-cert")
    reader, writer = os.pipe()
    try:
        os.write(writer, json.dumps({"profile_passphrase": _PROFILE_SECRET}).encode())
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
                "CADRUMO_SECRET_STORE_BACKEND": "auto",
                "CADRUMO_OUTPUT_LANGUAGE": "en",
            },
        )
        result = subprocess.run(  # noqa: S603 - fixed interpreter and module
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
            input=json.dumps({"certificate_passphrase": _CERTIFICATE_SECRET}),
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
    document = _assert_success(result, root)
    assert document["command"] == "config.auth.certificate.secret.set"
    assert document["result"]["has_secret"] is True
    assert [notice["code"] for notice in document["notices"]] == ["config.login.session_not_persisted"]
