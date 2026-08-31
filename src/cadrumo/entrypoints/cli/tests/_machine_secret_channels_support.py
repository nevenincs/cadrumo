"""Shared subprocess transport support for machine-secret channel integration tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from textwrap import dedent
from typing import Any
from uuid import UUID

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.user_profile.recovery_custody import ProfileRecoveryEnrollment, export_profile_recovery_artifact
from ....application.user_profile.registration import register_profile_with_credentials
from ....core.config import override_settings
from ....tests import SRC_CADRUMO
from ....tests.secure_sql import reap_profile_session_keys
from ....tests.subprocess_cli import subprocess_cli_env
from .._windows_profile_secret_bootstrap import bootstrap_interpreter

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

    from cadrumo.adapters.persistence.storage._profile_custody import build_profile_custody_port
    from cadrumo.adapters.persistence.storage._profile_login_session import build_profile_login_session_port
    from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
    from cadrumo.application.user_profile.login_session_port import bind_profile_login_session_port
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
            from cadrumo.application.user_profile.login_session import login_profile
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

    from cadrumo.adapters.persistence.storage._profile_custody import build_profile_custody_port
    from cadrumo.adapters.persistence.storage._profile_login_session import build_profile_login_session_port
    from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
    from cadrumo.application.user_profile.login_session_port import bind_profile_login_session_port
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
            from cadrumo.application.user_profile.login_session import login_profile
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


def cleanup_keychain(tmp_path: Path) -> None:
    """Reap test-owned profile session keys after a subprocess scenario."""
    for child in tmp_path.iterdir():
        if child.is_dir():
            reap_profile_session_keys(child)


def _restore_material(tmp_path: Path) -> tuple[Path, Path, str]:
    source = tmp_path / "restore-source"
    outcome, enrollments, phrases = _register(source, recovery=True)
    from ....adapters.persistence.storage.custody.capsule import load_committed_profile_password_material

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
