"""Fresh-process success proof for every explicit CLI secret channel.

The tests in this module cross the real ``main()`` boundary and use real
encrypted storage.  POSIX descriptor cases inherit anonymous pipes with
``pass_fds``.  Windows deliberately does not pretend that CRT descriptor
numbers are inherited: its platform case allowlists a HANDLE and enters via
the supported HANDLE-to-descriptor bootstrap.  ``--secrets-stdin`` is the
portable route and is exercised for every leaf on every platform.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from collections.abc import Iterator, Sequence
from contextlib import suppress
from pathlib import Path
from textwrap import dedent
from typing import Any
from uuid import UUID

import pytest

from ....adapters.persistence.storage.master_key import close_active_bucket_session
from ....application.user_profile.recovery_custody import ProfileRecoveryEnrollment, export_profile_recovery_artifact
from ....application.user_profile.registration import register_profile_with_credentials
from ....core.config import override_settings
from ....tests import SRC_CADRUMO
from ....tests.secure_sql import reap_profile_session_keys
from ....tests.subprocess_cli import subprocess_cli_env
from .._windows_profile_secret_bootstrap import bootstrap_interpreter

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_SECRET = "s13-profile-passphrase-that-must-never-escape"  # noqa: S105
_NEW_PROFILE_SECRET = "s13-new-profile-passphrase-that-must-never-escape"  # noqa: S105
_CERTIFICATE_SECRET = "s13-certificate-passphrase-that-must-never-escape"  # noqa: S105
_REFUSAL_SECRET = "s14-refusal-secret-that-must-never-escape"  # noqa: S105
_OVERSIZE_SECRET = "s14-oversize-secret-that-must-never-escape"  # noqa: S105
_ALL_SECRETS = (_PROFILE_SECRET, _NEW_PROFILE_SECRET, _CERTIFICATE_SECRET, _REFUSAL_SECRET)
_PROMPTS = (
    "profile passphrase:",
    "current profile passphrase:",
    "new profile passphrase:",
    "confirm new profile passphrase:",
    "pkcs#12 passphrase (input hidden):",
    "recovery phrase (24 words):",
)


def _base_interpreter_pythonpath() -> str:
    """Preserve the active environment's imports without launching its stub."""
    return os.pathsep.join(entry for entry in sys.path if entry)


_DURABLE_SNAPSHOT_SOURCE = dedent(
    """
    def durable_snapshot(root):
        return {
            str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
            and "log" not in path.name.lower()
        }
    """
)


_HARNESS = (
    dedent(
        """
    import json
    import os
    import sys
    from contextlib import ExitStack

    from cadrumo.adapters.persistence.storage import build_profile_custody_port, build_profile_login_session_port
    from cadrumo.application.user_profile import bind_profile_custody_port, bind_profile_login_session_port
    from cadrumo.core import config as config_module
    from cadrumo.core.config import Settings
    from cadrumo.core.logging import defer_logging_configuration, resume_logging_configuration
    """
    )
    + _DURABLE_SNAPSHOT_SOURCE
    + dedent(
        """
    payload = json.loads(sys.argv[1])
    settings = Settings(_env_file=None, **payload["settings"])
    composition = ExitStack()
    composition.enter_context(bind_profile_custody_port(build_profile_custody_port()))
    composition.enter_context(bind_profile_login_session_port(build_profile_login_session_port()))
    token = config_module._settings_override.set(settings)
    exit_code = 0
    try:
        if payload.get("preauthenticate_label") is not None:
            from cadrumo.application.user_profile import login_profile
            login_profile(
                name=payload["preauthenticate_label"],
                passphrase_callback=lambda: payload["preauthenticate_secret"],
            )
        before_dispatch = durable_snapshot(settings.cadrumo_local_storage_root)
        sys.argv = ["cadrumo", *sys.argv[2:]]
        defer_logging_configuration()
        try:
            from cadrumo.entrypoints.cli import main
            try:
                main()
            except SystemExit as exc:
                exit_code = int(exc.code or 0)
        finally:
            resume_logging_configuration()
        if payload.get("assert_stdin_unread"):
            remaining = sys.stdin.buffer.read().decode("utf-8")
            if remaining == payload["assert_unread_payload"]:
                print("S14_STDIN_UNREAD", file=sys.stderr)
            else:
                print("S14_STDIN_CONSUMED", file=sys.stderr)
                exit_code = exit_code or 96
        for descriptor in payload.get("assert_unread_descriptors", []):
            remaining = os.read(descriptor, 8192).decode("utf-8")
            if remaining == payload["assert_unread_payload"]:
                print("S14_DESCRIPTOR_UNREAD", file=sys.stderr)
            else:
                print("S14_DESCRIPTOR_CONSUMED", file=sys.stderr)
                exit_code = exit_code or 96
            os.close(descriptor)
        for descriptor in payload.get("assert_closed_descriptors", []):
            try:
                os.fstat(descriptor)
            except OSError:
                print("S13_DESCRIPTOR_CLOSED", file=sys.stderr)
            else:
                print("S13_DESCRIPTOR_OPEN", file=sys.stderr)
                exit_code = exit_code or 97
        if payload.get("assert_dispatch_state_unchanged"):
            if durable_snapshot(settings.cadrumo_local_storage_root) == before_dispatch:
                print("S14_STATE_UNCHANGED", file=sys.stderr)
            else:
                print("S14_STATE_CHANGED", file=sys.stderr)
                exit_code = exit_code or 98
    finally:
        try:
            config_module._settings_override.reset(token)
        finally:
            composition.__exit__(None, None, None)
    raise SystemExit(exit_code)
        """
    )
)

_WINDOWS_HANDLE_HARNESS = (
    dedent(
        """
    import json
    import os
    import sys
    from contextlib import ExitStack

    from cadrumo.adapters.persistence.storage import build_profile_custody_port, build_profile_login_session_port
    from cadrumo.application.user_profile import bind_profile_custody_port, bind_profile_login_session_port
    from cadrumo.core import config as config_module
    from cadrumo.core.config import Settings
    from cadrumo.core.logging import defer_logging_configuration, resume_logging_configuration
    from cadrumo.entrypoints.cli._windows_profile_secret_bootstrap import bootstrap_argv
    """
    )
    + _DURABLE_SNAPSHOT_SOURCE
    + dedent(
        """
    payload = json.loads(sys.argv[1])
    settings = Settings(_env_file=None, **payload["settings"])
    composition = ExitStack()
    composition.enter_context(bind_profile_custody_port(build_profile_custody_port()))
    composition.enter_context(bind_profile_login_session_port(build_profile_login_session_port()))
    argv = bootstrap_argv(
        profile_handle=payload.get("profile_handle"),
        secrets_handle=payload.get("secrets_handle"),
        recovery_handoff_handle=payload.get("recovery_handoff_handle"),
        recovery_verification_handle=payload.get("recovery_verification_handle"),
        command=sys.argv[2:],
    )
    descriptors = []
    for option in ("--profile-secrets-fd", "--secrets-fd", "--recovery-handoff-fd", "--recovery-verification-fd"):
        if option in argv:
            descriptor = int(argv[argv.index(option) + 1])
            if descriptor not in descriptors:
                descriptors.append(descriptor)
    token = config_module._settings_override.set(settings)
    exit_code = 0
    try:
        if payload.get("preauthenticate_label") is not None:
            from cadrumo.application.user_profile import login_profile
            login_profile(
                name=payload["preauthenticate_label"],
                passphrase_callback=lambda: payload["preauthenticate_secret"],
            )
        before_dispatch = durable_snapshot(settings.cadrumo_local_storage_root)
        sys.argv[:] = argv
        defer_logging_configuration()
        try:
            from cadrumo.entrypoints.cli import main
            try:
                main()
            except SystemExit as exc:
                exit_code = int(exc.code or 0)
        finally:
            resume_logging_configuration()
        if payload.get("assert_stdin_unread"):
            remaining = sys.stdin.buffer.read().decode("utf-8")
            if remaining == payload["assert_unread_payload"]:
                print("S14_STDIN_UNREAD", file=sys.stderr)
            else:
                print("S14_STDIN_CONSUMED", file=sys.stderr)
                exit_code = exit_code or 96
        if payload.get("assert_descriptors_unread"):
            for descriptor in descriptors:
                remaining = os.read(descriptor, 8192).decode("utf-8")
                if remaining == payload["assert_unread_payload"]:
                    print("S14_DESCRIPTOR_UNREAD", file=sys.stderr)
                else:
                    print("S14_DESCRIPTOR_CONSUMED", file=sys.stderr)
                    exit_code = exit_code or 96
                os.close(descriptor)
            descriptors.clear()
        for descriptor in descriptors:
            try:
                os.fstat(descriptor)
            except OSError:
                print("S13_DESCRIPTOR_CLOSED", file=sys.stderr)
            else:
                print("S13_DESCRIPTOR_OPEN", file=sys.stderr)
                exit_code = exit_code or 97
        if payload.get("assert_dispatch_state_unchanged"):
            if durable_snapshot(settings.cadrumo_local_storage_root) == before_dispatch:
                print("S14_STATE_UNCHANGED", file=sys.stderr)
            else:
                print("S14_STATE_CHANGED", file=sys.stderr)
                exit_code = exit_code or 98
    finally:
        try:
            config_module._settings_override.reset(token)
        finally:
            composition.__exit__(None, None, None)
    raise SystemExit(exit_code)
        """
    )
)


def _settings(storage_root: Path, *, output_language: str = "en") -> dict[str, object]:
    return {
        "cadrumo_local_storage_root": str(storage_root),
        "cadrumo_secret_store_dir": str(storage_root / "fallback-store"),
        "cadrumo_secret_store_backend": "auto",
        "cadrumo_output_language": output_language,
    }


def _run(
    storage_root: Path,
    args: Sequence[str],
    *,
    stdin: str | None = None,
    inherited_payloads: Sequence[str | bytes] = (),
    assert_closed_index: int | None = None,
    assert_closed_indices: Sequence[int] = (),
    assert_closed_fd_zero: bool = False,
    hostile_env: dict[str, str] | None = None,
    preauthenticate_label: str | None = None,
    assert_dispatch_state_unchanged: bool = False,
    output_language: str = "en",
    assert_unread_indices: Sequence[int] = (),
    assert_stdin_unread: bool = False,
    unread_payload: str = _REFUSAL_SECRET,
) -> subprocess.CompletedProcess[str]:
    """Run the real CLI, mapping payload pipes to argv ``{fd}`` tokens."""
    if inherited_payloads and os.name == "nt":
        return _run_windows_handles(
            storage_root,
            args,
            stdin=stdin,
            inherited_payloads=inherited_payloads,
            hostile_env=hostile_env,
            preauthenticate_label=preauthenticate_label,
            assert_dispatch_state_unchanged=assert_dispatch_state_unchanged,
            output_language=output_language,
            assert_descriptors_unread=bool(assert_unread_indices),
            assert_stdin_unread=assert_stdin_unread,
            unread_payload=unread_payload,
        )
    readers: list[int] = []
    writers: list[int] = []
    temporary_paths: list[str] = []
    try:
        for payload in inherited_payloads:
            encoded = payload if isinstance(payload, bytes) else payload.encode("utf-8")
            if len(encoded) > 4096:
                reader, path = tempfile.mkstemp(prefix="cadrumo-s14-secret-")
                temporary_paths.append(path)
                os.write(reader, encoded)
                os.lseek(reader, 0, os.SEEK_SET)
                readers.append(reader)
                continue
            reader, writer = os.pipe()
            readers.append(reader)
            writers.append(writer)
            os.write(writer, encoded)
            os.close(writer)
            writers.remove(writer)
        rendered_args = [
            str(readers[int(value[4:-1])]) if value.startswith("{fd:") and value.endswith("}") else value
            for value in args
        ]
        payload = {
            "settings": _settings(storage_root, output_language=output_language),
            "assert_closed_descriptors": [
                *(() if assert_closed_index is None else (readers[assert_closed_index],)),
                *(readers[index] for index in assert_closed_indices),
                *((0,) if assert_closed_fd_zero else ()),
            ],
            "preauthenticate_label": preauthenticate_label,
            "preauthenticate_secret": _PROFILE_SECRET if preauthenticate_label is not None else None,
            "assert_dispatch_state_unchanged": assert_dispatch_state_unchanged,
            "assert_unread_descriptors": [readers[index] for index in assert_unread_indices],
            "assert_stdin_unread": assert_stdin_unread,
            "assert_unread_payload": unread_payload,
        }
        return subprocess.run(  # noqa: S603 - fixed interpreter plus test-owned argv
            [sys.executable, "-c", _HARNESS, json.dumps(payload), *rendered_args],
            cwd=SRC_CADRUMO,
            env=subprocess_cli_env(
                strip_prefixes=("AEAT_", "CADRUMO_", "PYTEST_"),
                extra={
                    "PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring",
                    **(hostile_env or {}),
                },
            ),
            input=stdin,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=180,
            pass_fds=tuple(readers),
        )
    finally:
        for descriptor in (*readers, *writers):
            with suppress(OSError):
                os.close(descriptor)
        for path in temporary_paths:
            with suppress(OSError):
                os.unlink(path)


def _run_windows_handles(
    storage_root: Path,
    args: Sequence[str],
    *,
    stdin: str | None,
    inherited_payloads: Sequence[str | bytes],
    hostile_env: dict[str, str] | None,
    preauthenticate_label: str | None,
    assert_dispatch_state_unchanged: bool,
    output_language: str,
    assert_descriptors_unread: bool,
    assert_stdin_unread: bool,
    unread_payload: str,
) -> subprocess.CompletedProcess[str]:
    """Run the shipped bootstrap with an explicit STARTUPINFOEX HANDLE allowlist."""
    if sys.platform != "win32":
        raise RuntimeError("Windows HANDLE transport requested on a non-Windows host")
    import msvcrt

    readers: list[int] = []
    writers: list[int] = []
    temporary_paths: list[str] = []
    try:
        for payload in inherited_payloads:
            encoded = payload if isinstance(payload, bytes) else payload.encode("utf-8")
            if len(encoded) > 4096:
                reader, path = tempfile.mkstemp(prefix="cadrumo-s14-secret-")
                temporary_paths.append(path)
                os.write(reader, encoded)
                os.lseek(reader, 0, os.SEEK_SET)
                readers.append(reader)
                continue
            reader, writer = os.pipe()
            readers.append(reader)
            writers.append(writer)
            os.write(writer, encoded)
            os.close(writer)
            writers.remove(writer)

        command: list[str] = []
        profile_handle: int | None = None
        secrets_handle: int | None = None
        index = 0
        while index < len(args):
            value = args[index]
            if value in {"--profile-secrets-fd", "--secrets-fd"}:
                placeholder = args[index + 1]
                descriptor_index = int(placeholder[4:-1])
                handle = msvcrt.get_osfhandle(readers[descriptor_index])
                if value == "--profile-secrets-fd":
                    profile_handle = handle
                else:
                    secrets_handle = handle
                index += 2
                continue
            command.append(value)
            index += 1

        handles = [msvcrt.get_osfhandle(reader) for reader in readers]
        for handle in handles:
            os.set_handle_inheritable(handle, True)
        startup = subprocess.STARTUPINFO()
        startup.lpAttributeList = {"handle_list": handles}
        payload = {
            "settings": _settings(storage_root, output_language=output_language),
            "profile_handle": profile_handle,
            "secrets_handle": secrets_handle,
            "preauthenticate_label": preauthenticate_label,
            "preauthenticate_secret": _PROFILE_SECRET if preauthenticate_label is not None else None,
            "assert_dispatch_state_unchanged": assert_dispatch_state_unchanged,
            "assert_descriptors_unread": assert_descriptors_unread,
            "assert_stdin_unread": assert_stdin_unread,
            "assert_unread_payload": unread_payload,
        }
        return subprocess.run(  # noqa: S603 - fixed interpreter and production bootstrap
            [
                bootstrap_interpreter(),
                "-c",
                _WINDOWS_HANDLE_HARNESS,
                json.dumps(payload),
                *command,
            ],
            cwd=SRC_CADRUMO,
            env=subprocess_cli_env(
                strip_prefixes=("AEAT_", "CADRUMO_", "PYTEST_"),
                extra={
                    "PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring",
                    "PYTHONPATH": _base_interpreter_pythonpath(),
                    **(hostile_env or {}),
                },
            ),
            input=stdin,
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
        for descriptor in (*readers, *writers):
            with suppress(OSError):
                os.close(descriptor)
        for path in temporary_paths:
            with suppress(OSError):
                os.unlink(path)


def _combined(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def _storage_snapshot(root: Path) -> dict[str, bytes]:
    """Capture every durable custody artifact except diagnostic logs."""
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and "log" not in path.name.lower()
    }


def _assert_refused(
    result: subprocess.CompletedProcess[str],
    root: Path,
    *,
    before: dict[str, bytes] | None = None,
    extra_secrets: Sequence[str] = (),
) -> str:
    combined = _combined(result)
    assert result.returncode == 2, combined
    envelope_lines = [
        line for stream in (result.stdout, result.stderr) for line in stream.splitlines() if line.startswith("{")
    ]
    assert len(envelope_lines) == 1, combined
    envelope = json.loads(envelope_lines[0])
    assert envelope["status"] == "error"
    assert isinstance(envelope["error"], dict)
    assert isinstance(envelope["error"].get("message"), str)
    assert not any(prompt in combined.lower() for prompt in _PROMPTS)
    for secret in (*_ALL_SECRETS, *extra_secrets):
        assert secret not in combined
    for path in root.rglob("*") if root.exists() else ():
        if path.is_file() and "log" in path.name.lower():
            contents = path.read_text(encoding="utf-8", errors="replace")
            for secret in (*_ALL_SECRETS, *extra_secrets):
                assert secret not in contents
    if before is not None:
        assert _storage_snapshot(root) == before
    return combined


def _assert_success(
    result: subprocess.CompletedProcess[str],
    storage_root: Path,
    *,
    extra_secrets: Sequence[str] = (),
) -> dict[str, Any]:
    combined = _combined(result)
    assert result.returncode == 0, combined
    assert not any(prompt in combined.lower() for prompt in _PROMPTS)
    secrets = (*_ALL_SECRETS, *extra_secrets)
    for secret in secrets:
        assert secret not in combined
    for path in storage_root.rglob("*"):
        if path.is_file() and "log" in path.name.lower():
            contents = path.read_text(encoding="utf-8", errors="replace")
            for secret in secrets:
                assert secret not in contents
    document = json.loads(result.stdout)
    assert isinstance(document, dict)
    return document


def _register(
    storage_root: Path,
    *,
    label: str = "s13-operator",
    recovery: bool = False,
):
    captured: list[ProfileRecoveryEnrollment] = []
    phrases: list[str] = []

    def handover(enrollment: ProfileRecoveryEnrollment) -> str:
        mnemonic = str(enrollment.recovery_key.mnemonic)
        if recovery:
            phrases.append(mnemonic)
            captured.append(enrollment)
        return mnemonic

    with override_settings(cadrumo_local_storage_root=storage_root):
        outcome = register_profile_with_credentials(
            label=label,
            passphrase=_PROFILE_SECRET,
            recovery_handover=handover,
        )
        close_active_bucket_session()
    return outcome, captured, phrases


def _register_certificate_source(storage_root: Path, *, name: str) -> None:
    certificate_path = storage_root / "s13-certificate.p12"
    certificate_path.write_bytes(b"registered source placeholder")
    result = _run(
        storage_root,
        [
            "--format",
            "json",
            "--profile-secrets-stdin",
            "config",
            "auth",
            "certificate",
            "register",
            "--name",
            name,
            "--file",
            str(certificate_path),
        ],
        stdin=json.dumps({"profile_passphrase": _PROFILE_SECRET}),
    )
    assert result.returncode == 0, _combined(result)


@pytest.fixture(autouse=True)
def _cleanup_keychain(tmp_path: Path) -> Iterator[None]:
    yield
    for child in tmp_path.iterdir():
        if child.is_dir():
            reap_profile_session_keys(child)


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


def _restore_material(tmp_path: Path) -> tuple[Path, Path, str]:
    source = tmp_path / "restore-source"
    outcome, enrollments, phrases = _register(source, recovery=True)
    from ....adapters.persistence.storage.custody import load_committed_profile_password_material

    material = load_committed_profile_password_material(UUID(outcome.profile_id), root=source)
    artifact = tmp_path / "recovery.artifact.json"
    export_profile_recovery_artifact(
        enrollments[0],
        current_password=_PROFILE_SECRET,
        password_envelope=material.envelope,
        sentinel=material.sentinel,
        target=artifact,
    )
    phrase = phrases[0]
    assert isinstance(phrase, str)
    return material.capsule_path, artifact, phrase


@pytest.mark.parametrize("channel", ("stdin", "fd"))
@pytest.mark.parametrize("door", ("passphrase", "recovery"))
def test_both_restore_doors_succeed_through_each_leaf_channel(tmp_path: Path, channel: str, door: str) -> None:
    capsule, artifact, phrase = _restore_material(tmp_path / f"material-{channel}-{door}")
    root = tmp_path / f"restore-{channel}-{door}"
    args = ["--format", "json", "config", "profile", "restore", f"restored-{channel}-{door}", "--file", str(capsule)]
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


_FIVE_LEAF_CONFLICT_COMMANDS = (
    ("config", "login", "unread-target"),
    ("config", "profile", "create", "unread-created", "--quiet"),
    ("config", "passphrase", "change"),
    ("config", "profile", "restore", "unread-restored", "--file", "unread-capsule"),
    ("config", "auth", "certificate", "secret", "set", "--name", "unread-certificate"),
)


@pytest.mark.parametrize("command", _FIVE_LEAF_CONFLICT_COMMANDS)
def test_each_leaf_refuses_same_scope_channel_conflict_before_state_or_read(
    tmp_path: Path, command: tuple[str, ...]
) -> None:
    root = tmp_path / "same-scope"
    result = _run(
        root,
        ["--format", "json", *command, "--secrets-stdin", "--secrets-fd", "{fd:0}"],
        stdin=_REFUSAL_SECRET,
        inherited_payloads=(_REFUSAL_SECRET,),
        assert_unread_indices=(0,),
        assert_stdin_unread=True,
    )
    combined = _assert_refused(result, root, before={})
    assert '"status":"error"' in combined
    assert "S14_STDIN_UNREAD" in result.stderr
    assert "S14_DESCRIPTOR_UNREAD" in result.stderr


def test_root_refuses_same_scope_channel_conflict_before_state_or_read(tmp_path: Path) -> None:
    root = tmp_path / "root-same-scope"
    result = _run(
        root,
        [
            "--format",
            "json",
            "--profile-secrets-stdin",
            "--profile-secrets-fd",
            "{fd:0}",
            "config",
            "profile",
            "history",
        ],
        stdin=_REFUSAL_SECRET,
        inherited_payloads=(_REFUSAL_SECRET,),
        assert_unread_indices=(0,),
        assert_stdin_unread=True,
    )
    combined = _assert_refused(result, root, before={})
    assert '"status":"error"' in combined
    assert "S14_STDIN_UNREAD" in result.stderr
    assert "S14_DESCRIPTOR_UNREAD" in result.stderr


@pytest.mark.parametrize("collision", ("two-stdin", "root-fd0", "leaf-fd0", "same-fd"))
def test_cross_scope_collision_refuses_before_read_authentication_or_mutation(tmp_path: Path, collision: str) -> None:
    root = tmp_path / f"cross-scope-{collision}"
    _register(root, label="collision-operator")
    _register_certificate_source(root, name="collision-cert")
    before = _storage_snapshot(root)
    args = ["--format", "json"]
    inherited: tuple[str, ...] = ()
    stdin: str | None = None
    if collision == "two-stdin":
        args.append("--profile-secrets-stdin")
        leaf = ("--secrets-stdin",)
        stdin = _REFUSAL_SECRET
    elif collision == "root-fd0":
        args.extend(("--profile-secrets-fd", "0"))
        leaf = ("--secrets-stdin",)
        stdin = _REFUSAL_SECRET
    elif collision == "leaf-fd0":
        args.append("--profile-secrets-stdin")
        leaf = ("--secrets-fd", "0")
        stdin = _REFUSAL_SECRET
    else:
        args.extend(("--profile-secrets-fd", "{fd:0}"))
        leaf = ("--secrets-fd", "{fd:0}")
        inherited = (_REFUSAL_SECRET,)
    args.extend(
        (
            "config",
            "auth",
            "certificate",
            "secret",
            "set",
            "--name",
            "collision-cert",
            *leaf,
        )
    )
    result = _run(
        root,
        args,
        stdin=stdin,
        inherited_payloads=inherited,
        assert_unread_indices=(0,) if inherited else (),
        assert_stdin_unread=stdin is not None,
    )
    combined = _assert_refused(result, root, before=before)
    assert '"status":"error"' in combined
    if stdin is not None:
        assert "S14_STDIN_UNREAD" in result.stderr
    else:
        assert "S14_DESCRIPTOR_UNREAD" in result.stderr


@pytest.mark.parametrize(
    ("descriptor", "expected"),
    ((-1, "reserved"), (1, "reserved"), (2, "reserved"), (999_999, "Failed to read")),
)
def test_leaf_descriptor_refusals_are_typed_secret_free_and_state_free(
    tmp_path: Path, descriptor: int, expected: str
) -> None:
    root = tmp_path / f"leaf-fd-{descriptor}"
    result = _run(
        root,
        [
            "--format",
            "json",
            "config",
            "profile",
            "create",
            "descriptor-refusal",
            "--quiet",
            "--secrets-fd",
            str(descriptor),
        ],
    )
    assert expected in _assert_refused(result, root, before={})


@pytest.mark.parametrize(
    ("descriptor", "expected"),
    (
        (-1, "cannot be used"),
        (1, "cannot be used"),
        (2, "cannot be used"),
        (999_999, "not an inherited readable"),
    ),
)
def test_root_descriptor_refusals_are_typed_secret_free_and_non_mutating(
    tmp_path: Path, descriptor: int, expected: str
) -> None:
    root = tmp_path / f"root-fd-{descriptor}"
    _register(root, label="root-fd-operator")
    before = _storage_snapshot(root)
    result = _run(
        root,
        [
            "--format",
            "json",
            "--profile-secrets-fd",
            str(descriptor),
            "config",
            "profile",
            "history",
            "root-fd-operator",
        ],
    )
    assert expected in _assert_refused(result, root, before=before)


_MALFORMED_CREATE_PAYLOADS = (
    pytest.param(b"\xff", "invalid", (), id="invalid-utf8"),
    pytest.param(f"{_REFUSAL_SECRET}{{broken", "invalid", (_REFUSAL_SECRET,), id="invalid-json"),
    pytest.param(json.dumps(_REFUSAL_SECRET), "invalid", (_REFUSAL_SECRET,), id="non-object"),
    pytest.param(
        '{"passphrase":"s14-duplicate-first","passphrase":"s14-duplicate-second",'
        '"passphrase_confirmation":"s14-duplicate-second"}',
        "invalid",
        ("s14-duplicate-first", "s14-duplicate-second"),
        id="duplicate-top-level",
    ),
    pytest.param(
        '{"passphrase":"s14-recursive-secret","passphrase_confirmation":"s14-recursive-secret",'
        '"extra":{"nested":"s14-nested-first","nested":"s14-nested-second"}}',
        "invalid",
        ("s14-recursive-secret", "s14-nested-first", "s14-nested-second"),
        id="duplicate-recursive",
    ),
    pytest.param("{}", "fields", (), id="missing-fields"),
    pytest.param(
        '{"passphrase":"s14-extra-secret","passphrase_confirmation":"s14-extra-secret","extra":"s14-forbidden-extra"}',
        "fields",
        ("s14-extra-secret", "s14-forbidden-extra"),
        id="extra-field",
    ),
    pytest.param(
        json.dumps(
            {
                "passphrase": _OVERSIZE_SECRET * 220,
                "passphrase_confirmation": _OVERSIZE_SECRET * 220,
            }
        ),
        "large",
        (_OVERSIZE_SECRET,),
        id="oversize-valid-json",
    ),
    pytest.param("", "invalid", (), id="empty"),
)


@pytest.mark.parametrize(("payload", "diagnostic", "planted_secrets"), _MALFORMED_CREATE_PAYLOADS)
def test_leaf_strict_payload_refusals_close_descriptor_without_mutation(
    tmp_path: Path,
    payload: str | bytes,
    diagnostic: str,
    planted_secrets: tuple[str, ...],
) -> None:
    root = tmp_path / "malformed-leaf"
    result = _run(
        root,
        [
            "--format",
            "json",
            "config",
            "profile",
            "create",
            "malformed-refusal",
            "--quiet",
            "--secrets-fd",
            "{fd:0}",
        ],
        inherited_payloads=(payload,),
        assert_closed_index=0,
    )
    combined = _assert_refused(result, root, before={}, extra_secrets=planted_secrets)
    assert "S13_DESCRIPTOR_CLOSED" in result.stderr
    assert {
        "invalid": "not a valid JSON object",
        "fields": "missing required fields or has unexpected ones",
        "large": "exceeds the maximum allowed size",
    }[diagnostic] in combined


@pytest.mark.parametrize(("payload", "diagnostic", "planted_secrets"), _MALFORMED_CREATE_PAYLOADS)
def test_root_strict_payload_refusals_close_descriptor_without_mutation(
    tmp_path: Path,
    payload: str | bytes,
    diagnostic: str,
    planted_secrets: tuple[str, ...],
) -> None:
    root = tmp_path / "malformed-root"
    _register(root, label="malformed-root-operator")
    before = _storage_snapshot(root)
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
            "malformed-root-operator",
        ],
        inherited_payloads=(payload,),
        assert_closed_index=0,
    )
    combined = _assert_refused(result, root, before=before, extra_secrets=planted_secrets)
    assert "S13_DESCRIPTOR_CLOSED" in result.stderr
    assert {
        "invalid": "one strict UTF-8 JSON object",
        "fields": "contain exactly these fields",
        "large": "exceeds the 8192-byte limit",
    }[diagnostic] in combined


def test_retired_restore_password_field_is_refused_without_publication(tmp_path: Path) -> None:
    capsule, _artifact, _phrase = _restore_material(tmp_path / "legacy-restore-material")
    root = tmp_path / "legacy-restore"
    result = _run(
        root,
        [
            "--format",
            "json",
            "config",
            "profile",
            "restore",
            "legacy-restore",
            "--file",
            str(capsule),
            "--secrets-stdin",
        ],
        stdin=json.dumps({"password": _PROFILE_SECRET}),
    )
    assert "unexpected ones" in _assert_refused(result, root, before={})


def test_retired_certificate_secret_field_is_refused_without_mutation(tmp_path: Path) -> None:
    root = tmp_path / "legacy-certificate"
    _register(root, label="legacy-cert-operator")
    _register_certificate_source(root, name="legacy-cert")
    before = _storage_snapshot(root)
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
            "legacy-cert",
            "--secrets-stdin",
        ],
        stdin=json.dumps({"secret": _REFUSAL_SECRET}),
        inherited_payloads=(json.dumps({"profile_passphrase": _PROFILE_SECRET}),),
        assert_closed_index=0,
    )
    assert "unexpected ones" in _assert_refused(result, root, before=before)


def test_hostile_environment_secret_is_ignored_by_leaf_cli(tmp_path: Path) -> None:
    root = tmp_path / "hostile-environment"
    result = _run(
        root,
        ["--format", "json", "config", "profile", "create", "hostile-env", "--quiet"],
        stdin="",
        hostile_env={"CADRUMO_SECRET_PASSPHRASE": _REFUSAL_SECRET},
    )
    combined = _assert_refused(result, root, before={})
    assert "No passphrase channel is available." in combined


def test_live_session_makes_root_source_unused_and_leaves_it_unread(
    tmp_path: Path,
) -> None:
    root = tmp_path / "live-session-unused"
    _register(root, label="live-session-operator")
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
            "live-session-operator",
        ],
        inherited_payloads=(_REFUSAL_SECRET,),
        preauthenticate_label="live-session-operator",
        assert_dispatch_state_unchanged=True,
        assert_unread_indices=(0,),
    )
    combined = _assert_refused(result, root)
    assert '"status":"error"' in combined
    assert "S14_DESCRIPTOR_UNREAD" in result.stderr
    assert "S14_STATE_UNCHANGED" in result.stderr


@pytest.mark.parametrize(
    ("command", "payload", "consumed", "expected"),
    (
        (
            ("config", "profile", "history", "missing-profile"),
            {"profile_passphrase": _PROFILE_SECRET},
            False,
            "Unknown profile",
        ),
        (
            ("config", "profile", "history", ""),
            {"profile_passphrase": _PROFILE_SECRET},
            False,
            "Unknown profile",
        ),
        (
            ("config", "profile", "history"),
            {"profile_passphrase": _PROFILE_SECRET},
            False,
            "requires an exact profile target",
        ),
        (
            ("config", "profile", "history", "wrong-secret-target"),
            {"profile_passphrase": ""},
            True,
            "The profile password was not accepted.",
        ),
        (
            ("config", "profile", "history", "wrong-nonblank-secret-target"),
            {"profile_passphrase": _REFUSAL_SECRET},
            True,
            "The profile password was not accepted.",
        ),
    ),
    ids=("wrong-target", "blank-target", "no-target", "blank-secret", "wrong-secret"),
)
def test_root_wrong_blank_target_or_secret_refuses_without_secret_disclosure(
    tmp_path: Path,
    command: tuple[str, ...],
    payload: dict[str, str],
    consumed: bool,
    expected: str,
) -> None:
    root = tmp_path / "wrong-blank-root"
    if command[-1] in {"wrong-secret-target", "wrong-nonblank-secret-target"}:
        _register(root, label=command[-1])
    before = _storage_snapshot(root)
    serialized_payload = json.dumps(payload)
    result = _run(
        root,
        ["--format", "json", "--profile-secrets-fd", "{fd:0}", *command],
        inherited_payloads=(serialized_payload,),
        assert_closed_index=0 if consumed else None,
        assert_unread_indices=() if consumed else (0,),
        unread_payload=serialized_payload,
    )
    combined = _assert_refused(result, root, before=before)
    assert ("S13_DESCRIPTOR_CLOSED" if consumed else "S14_DESCRIPTOR_UNREAD") in result.stderr
    if expected:
        assert expected in combined


def test_root_source_is_inapplicable_to_self_authenticating_rotation_and_unread(
    tmp_path: Path,
) -> None:
    root = tmp_path / "self-auth-exemption"
    _register(root, label="self-auth-operator")
    before = _storage_snapshot(root)
    leaf_payload = json.dumps(
        {
            "current_passphrase": _PROFILE_SECRET,
            "new_passphrase": _NEW_PROFILE_SECRET,
            "new_passphrase_confirmation": _NEW_PROFILE_SECRET,
        }
    )
    result = _run(
        root,
        [
            "--format",
            "json",
            "--profile-secrets-fd",
            "{fd:0}",
            "config",
            "passphrase",
            "change",
            "--secrets-stdin",
        ],
        stdin=leaf_payload,
        inherited_payloads=(_REFUSAL_SECRET,),
        assert_unread_indices=(0,),
    )
    combined = _assert_refused(result, root, before=before)
    assert '"status":"error"' in combined
    assert "S14_DESCRIPTOR_UNREAD" in result.stderr


@pytest.mark.parametrize(
    ("command", "expected_code", "expected_diagnostic"),
    (
        (("--help",), 0, "CADRUMO - local-first workflow"),
        (("config", "profile", "history", "--unknown"), 2, "No such option"),
    ),
    ids=("help", "parse-error"),
)
def test_help_and_parse_failures_never_read_root_secret_source(
    tmp_path: Path,
    command: tuple[str, ...],
    expected_code: int,
    expected_diagnostic: str,
) -> None:
    root = tmp_path / "parse-precedence"
    result = _run(
        root,
        ["--profile-secrets-fd", "{fd:0}", *command],
        inherited_payloads=(_REFUSAL_SECRET,),
        assert_unread_indices=(0,),
    )
    combined = _combined(result)
    assert result.returncode == expected_code, combined
    assert expected_diagnostic in combined
    assert "S14_DESCRIPTOR_UNREAD" in result.stderr
    assert not any(prompt in combined.lower() for prompt in _PROMPTS)
    assert _REFUSAL_SECRET not in combined
    assert _storage_snapshot(root) == {}


@pytest.mark.parametrize(
    ("locale", "expected"),
    (
        ("en", "Cannot specify both --secrets-stdin and --secrets-fd."),
        ("es", "No se puede especificar --secrets-stdin y --secrets-fd a la vez."),
        ("ca", "No es pot especificar --secrets-stdin i --secrets-fd alhora."),
        ("hu", "A --secrets-stdin és a --secrets-fd nem adható meg egyszerre."),
    ),
)
def test_four_locale_conflict_snapshots_are_localized_and_secret_free(
    tmp_path: Path, locale: str, expected: str
) -> None:
    root = tmp_path / f"locale-{locale}"
    result = _run(
        root,
        [
            "--format",
            "json",
            "config",
            "profile",
            "create",
            "locale-refusal",
            "--quiet",
            "--secrets-stdin",
            "--secrets-fd",
            "999999",
        ],
        stdin=_REFUSAL_SECRET,
        output_language=locale,
    )
    combined = _assert_refused(result, root, before={})
    assert expected in combined
