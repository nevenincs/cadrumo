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
from collections.abc import Iterator, Sequence
from contextlib import suppress
from pathlib import Path
from textwrap import dedent
from typing import Any
from uuid import UUID

import pytest

from ....adapters.persistence.storage.master_key import close_active_bucket_session
from ....application.user_profile import (
    ProfileRecoveryEnrollment,
    export_profile_recovery_artifact,
    register_profile_with_credentials,
)
from ....core.config import override_settings
from ....tests._inventory import SRC_CADRUMO
from ....tests.secure_sql import reap_profile_session_keys
from ....tests.subprocess_cli import subprocess_cli_env

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_SECRET = "s13-profile-passphrase-that-must-never-escape"  # noqa: S105
_NEW_PROFILE_SECRET = "s13-new-profile-passphrase-that-must-never-escape"  # noqa: S105
_CERTIFICATE_SECRET = "s13-certificate-passphrase-that-must-never-escape"  # noqa: S105
_ALL_SECRETS = (_PROFILE_SECRET, _NEW_PROFILE_SECRET, _CERTIFICATE_SECRET)
_PROMPTS = (
    "profile passphrase:",
    "current profile passphrase:",
    "new profile passphrase:",
    "confirm new profile passphrase:",
    "pkcs#12 passphrase (input hidden):",
    "recovery phrase (24 words):",
)

_HARNESS = dedent(
    """
    import json
    import os
    import sys

    from cadrumo.core import config as config_module
    from cadrumo.core.config import Settings
    from cadrumo.core.logging import defer_logging_configuration, resume_logging_configuration

    payload = json.loads(sys.argv[1])
    settings = Settings(_env_file=None, **payload["settings"])
    token = config_module._settings_override.set(settings)
    exit_code = 0
    try:
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
        for descriptor in payload.get("assert_closed_descriptors", []):
            try:
                os.fstat(descriptor)
            except OSError:
                print("S13_DESCRIPTOR_CLOSED", file=sys.stderr)
            else:
                print("S13_DESCRIPTOR_OPEN", file=sys.stderr)
                exit_code = exit_code or 97
    finally:
        config_module._settings_override.reset(token)
    raise SystemExit(exit_code)
    """
)

_WINDOWS_HANDLE_HARNESS = dedent(
    """
    import json
    import os
    import sys

    from cadrumo.core import config as config_module
    from cadrumo.core.config import Settings
    from cadrumo.core.logging import defer_logging_configuration, resume_logging_configuration
    from cadrumo.entrypoints.cli._windows_profile_secret_bootstrap import bootstrap_argv

    payload = json.loads(sys.argv[1])
    settings = Settings(_env_file=None, **payload["settings"])
    argv = bootstrap_argv(
        profile_handle=payload.get("profile_handle"),
        secrets_handle=payload.get("secrets_handle"),
        command=sys.argv[2:],
    )
    descriptors = []
    for option in ("--profile-secrets-fd", "--secrets-fd"):
        if option in argv:
            descriptors.append(int(argv[argv.index(option) + 1]))
    token = config_module._settings_override.set(settings)
    exit_code = 0
    try:
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
        for descriptor in descriptors:
            try:
                os.fstat(descriptor)
            except OSError:
                print("S13_DESCRIPTOR_CLOSED", file=sys.stderr)
            else:
                print("S13_DESCRIPTOR_OPEN", file=sys.stderr)
                exit_code = exit_code or 97
    finally:
        config_module._settings_override.reset(token)
    raise SystemExit(exit_code)
    """
)


def _settings(storage_root: Path) -> dict[str, object]:
    return {
        "cadrumo_local_storage_root": str(storage_root),
        "cadrumo_secret_store_dir": str(storage_root / "fallback-store"),
        "cadrumo_secret_store_backend": "auto",
        "cadrumo_output_language": "en",
    }


def _run(
    storage_root: Path,
    args: Sequence[str],
    *,
    stdin: str | None = None,
    inherited_payloads: Sequence[str] = (),
    assert_closed_index: int | None = None,
    assert_closed_indices: Sequence[int] = (),
    assert_closed_fd_zero: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run the real CLI, mapping payload pipes to argv ``{fd}`` tokens."""
    if inherited_payloads and os.name == "nt":
        return _run_windows_handles(
            storage_root,
            args,
            stdin=stdin,
            inherited_payloads=inherited_payloads,
        )
    readers: list[int] = []
    writers: list[int] = []
    try:
        for payload in inherited_payloads:
            reader, writer = os.pipe()
            readers.append(reader)
            writers.append(writer)
            os.write(writer, payload.encode("utf-8"))
            os.close(writer)
            writers.remove(writer)
        rendered_args = [
            str(readers[int(value[4:-1])]) if value.startswith("{fd:") and value.endswith("}") else value
            for value in args
        ]
        payload = {
            "settings": _settings(storage_root),
            "assert_closed_descriptors": [
                *(() if assert_closed_index is None else (readers[assert_closed_index],)),
                *(readers[index] for index in assert_closed_indices),
                *((0,) if assert_closed_fd_zero else ()),
            ],
        }
        return subprocess.run(  # noqa: S603 - fixed interpreter plus test-owned argv
            [sys.executable, "-c", _HARNESS, json.dumps(payload), *rendered_args],
            cwd=SRC_CADRUMO,
            env=subprocess_cli_env(
                strip_prefixes=("AEAT_", "CADRUMO_", "PYTEST_"),
                extra={"PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring"},
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


def _run_windows_handles(
    storage_root: Path,
    args: Sequence[str],
    *,
    stdin: str | None,
    inherited_payloads: Sequence[str],
) -> subprocess.CompletedProcess[str]:
    """Run the shipped bootstrap with an explicit STARTUPINFOEX HANDLE allowlist."""
    if sys.platform != "win32":
        raise RuntimeError("Windows HANDLE transport requested on a non-Windows host")
    import msvcrt

    readers: list[int] = []
    writers: list[int] = []
    try:
        for payload in inherited_payloads:
            reader, writer = os.pipe()
            readers.append(reader)
            writers.append(writer)
            os.write(writer, payload.encode("utf-8"))
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
            "settings": _settings(storage_root),
            "profile_handle": profile_handle,
            "secrets_handle": secrets_handle,
        }
        return subprocess.run(  # noqa: S603 - fixed interpreter and production bootstrap
            [
                sys.executable,
                "-c",
                _WINDOWS_HANDLE_HARNESS,
                json.dumps(payload),
                *command,
            ],
            cwd=SRC_CADRUMO,
            env=subprocess_cli_env(
                strip_prefixes=("AEAT_", "CADRUMO_", "PYTEST_"),
                extra={"PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring"},
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


def _combined(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


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

    def handover(enrollment: ProfileRecoveryEnrollment) -> None:
        phrases.append(str(enrollment.recovery_key.mnemonic))
        captured.append(enrollment)

    with override_settings(cadrumo_local_storage_root=storage_root):
        outcome = register_profile_with_credentials(
            label=label,
            passphrase=_PROFILE_SECRET,
            recovery_handover=handover if recovery else None,
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


@pytest.mark.parametrize("channel", ("stdin", "fd"))
def test_profile_create_succeeds_through_each_leaf_channel(tmp_path: Path, channel: str) -> None:
    root = tmp_path / f"create-{channel}"
    payload = json.dumps({"passphrase": _PROFILE_SECRET, "passphrase_confirmation": _PROFILE_SECRET})
    args = ["--format", "json", "config", "profile", "create", f"created-{channel}", "--quiet"]
    result = (
        _run(root, [*args, "--secrets-stdin"], stdin=payload)
        if channel == "stdin"
        else _run(root, [*args, "--secrets-fd", "{fd:0}"], inherited_payloads=(payload,), assert_closed_index=0)
    )
    document = _assert_success(result, root)
    assert document["result"]["status"] == "created"


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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows STARTUPINFOEX HANDLE allowlist contract")
def test_windows_allowlisted_handle_bootstrap_authenticates_real_read(tmp_path: Path) -> None:
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
                "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
                "CADRUMO_SECRET_STORE_DIR": str(root / "fallback-store"),
                "CADRUMO_SECRET_STORE_BACKEND": "auto",
                "CADRUMO_OUTPUT_LANGUAGE": "en",
            },
        )
        result = subprocess.run(  # noqa: S603 - fixed interpreter and module
            [
                sys.executable,
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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows STARTUPINFOEX HANDLE allowlist contract")
def test_windows_profile_handle_plus_leaf_stdin_performs_real_certificate_write(
    tmp_path: Path,
) -> None:
    """The Windows bootstrap composes with portable leaf stdin without fd-parity claims."""
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
                "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
                "CADRUMO_SECRET_STORE_DIR": str(root / "fallback-store"),
                "CADRUMO_SECRET_STORE_BACKEND": "auto",
                "CADRUMO_OUTPUT_LANGUAGE": "en",
            },
        )
        result = subprocess.run(  # noqa: S603 - fixed interpreter and module
            [
                sys.executable,
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
