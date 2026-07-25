"""Recovery-code lifecycle proof over a real encrypted vault.

Proves ``config recovery status`` / ``create`` / ``rotate`` / ``verify`` and
the flat ``config recover`` against real encrypted secret-store files, with no
mnemonic ever serialized: the 24 words never ride ``argv``, a JSON envelope,
stdout, stderr, or the persisted wrapper file.

The CLI ``create`` / ``rotate`` verbs are inherently interactive — the
candidate words are written to the controlling terminal and must be fully
retyped with echo suppressed before the enrollment commits — so a captured
subprocess (no TTY) proves their clean refusal and the untouched prior
envelope. The enrollment itself is exercised through the production
application operations (``create_recovery_code`` / ``rotate_recovery_code``)
with a real ``confirm`` callback in the same settings context the CLI
harness installs: real master-key provider, real BIP-39 mint, real atomic
envelope install. The verify/recover halves then run through the real CLI
with ``--secrets-stdin``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLI_HARNESS = dedent(
    """
    from __future__ import annotations

    import sys
    from pathlib import Path

    from cadrumo.core import config as config_module
    from cadrumo.core.config import Settings

    storage_root = Path(sys.argv[1])
    passphrase_arg = sys.argv[2]
    cli_args = sys.argv[3:]
    base_settings = Settings(_env_file=None)
    passphrase = passphrase_arg or base_settings.cadrumo_dev_test_database_password
    settings = Settings(
        _env_file=None,
        cadrumo_local_storage_root=storage_root,
        cadrumo_secret_store_dir=storage_root / "secrets",
        cadrumo_secret_store_backend="file",
        cadrumo_secret_passphrase=passphrase,
        cadrumo_output_language="en",
    )
    token = config_module._settings_override.set(settings)
    try:
        sys.argv = ["cadrumo", *cli_args]
        from cadrumo.entrypoints.cli import main

        main()
    finally:
        config_module._settings_override.reset(token)
    """,
)

# Enrollment harness: same settings context as the CLI harness, but drives the
# production application enrollment operation with a real ``confirm`` callback
# (the exact contract the CLI's terminal confirm implements). The mnemonic is
# printed on a marker line so the TEST can capture it; production surfaces
# never serialize it.
_ENROLL_HARNESS = dedent(
    """
    from __future__ import annotations

    import sys
    from pathlib import Path

    from cadrumo.core import config as config_module
    from cadrumo.core.config import Settings

    storage_root = Path(sys.argv[1])
    mode = sys.argv[2]
    base_settings = Settings(_env_file=None)
    settings = Settings(
        _env_file=None,
        cadrumo_local_storage_root=storage_root,
        cadrumo_secret_store_dir=storage_root / "secrets",
        cadrumo_secret_store_backend="file",
        cadrumo_secret_passphrase=base_settings.cadrumo_dev_test_database_password,
        cadrumo_output_language="en",
    )
    token = config_module._settings_override.set(settings)
    try:
        from cadrumo.application.user_profile import create_recovery_code, rotate_recovery_code

        enroll = rotate_recovery_code if mode == "rotate" else create_recovery_code
        shown: dict[str, str] = {}

        def confirm(words: str) -> str:
            shown["words"] = words
            return words

        result = enroll(confirm=confirm)
        print("MNEMONIC\\t" + shown["words"])
        print("FINGERPRINT\\t" + result.recovery_fingerprint)
        print("ROTATED\\t" + ("yes" if result.rotated else "no"))
    finally:
        config_module._settings_override.reset(token)
    """,
)


def _env() -> dict[str, str]:
    env = {
        key: value for key, value in os.environ.items() if not key.startswith("AEAT_") and not key.startswith("PYTEST_")
    }
    env.update(
        {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        },
    )
    return env


def _run_cli(
    storage_root: Path,
    args: tuple[str, ...],
    *,
    passphrase: str | None = None,
    stdin_payload: str | None = None,
) -> subprocess.CompletedProcess[str]:
    # Always pipe stdin (empty when no payload): the child must NOT inherit
    # the parent console — an inherited console handle reports a TTY and a
    # hidden prompt would block the captured run forever — and Windows'
    # ``NUL`` device also reports as a TTY, so ``DEVNULL`` is no refuge. A
    # pipe is the genuine redirected-stdin operator condition.
    return subprocess.run(
        [sys.executable, "-c", _CLI_HARNESS, str(storage_root), passphrase or "", *args],
        cwd=Path(__file__).parents[3],
        env=_env(),
        input=stdin_payload if stdin_payload is not None else "",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=60.0,
    )


def _enroll(storage_root: Path, mode: str) -> tuple[str, str, subprocess.CompletedProcess[str]]:
    """Run the production enrollment operation; return ``(mnemonic, fingerprint, result)``."""
    result = subprocess.run(
        [sys.executable, "-c", _ENROLL_HARNESS, str(storage_root), mode],
        cwd=Path(__file__).parents[3],
        env=_env(),
        input="",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=60.0,
    )
    mnemonic = ""
    fingerprint = ""
    for line in result.stdout.splitlines():
        if line.startswith("MNEMONIC\t"):
            mnemonic = line.split("\t", 1)[1]
        if line.startswith("FINGERPRINT\t"):
            fingerprint = line.split("\t", 1)[1]
    return mnemonic, fingerprint, result


def _combined(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def _create_profile(storage_root: Path) -> None:
    created = _run_cli(
        storage_root,
        (
            "config",
            "profile",
            "create",
            "custody",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--name",
            "Custody Operator",
            "--entity-type",
            "natural_person",
            "--surnames",
            "Operator",
            "--activity",
            "design",
            "--iva-regime",
            "GENERAL",
        ),
    )
    assert created.returncode == 0, _combined(created)


def test_recovery_lifecycle_round_trips_without_serialized_mnemonic(tmp_path: Path) -> None:
    """status/create/rotate/verify/recover round-trip a real vault; no surface leaks the words."""

    _create_profile(tmp_path)
    recovery_path = tmp_path / "secrets" / "master.recovery.key"

    unenrolled = _run_cli(tmp_path, ("config", "recovery", "status"))
    assert unenrolled.returncode == 0, _combined(unenrolled)
    assert "recovery_enrolled\tno" in unenrolled.stdout

    mnemonic, fingerprint, enroll_result = _enroll(tmp_path, "create")
    assert enroll_result.returncode == 0, _combined(enroll_result)
    assert len(mnemonic.split()) == 24
    assert fingerprint
    assert recovery_path.is_file()
    envelope_document = recovery_path.read_text(encoding="utf-8")
    assert mnemonic not in envelope_document
    for word in mnemonic.split():
        assert word not in envelope_document.split('"')  # no plaintext word leaks as a JSON token

    # Create refuses a second enrollment; the rotate verb owns replacement.
    _, _, second_create = _enroll(tmp_path, "create")
    assert second_create.returncode != 0
    assert "rotate" in _combined(second_create)

    enrolled = _run_cli(tmp_path, ("config", "recovery", "status"))
    assert enrolled.returncode == 0, _combined(enrolled)
    assert "recovery_enrolled\tyes" in enrolled.stdout
    assert f"recovery_fingerprint\t{fingerprint}" in enrolled.stdout
    assert mnemonic not in _combined(enrolled)

    enrolled_json = _run_cli(tmp_path, ("--format", "json", "config", "recovery", "status"))
    assert enrolled_json.returncode == 0, _combined(enrolled_json)
    envelope = json.loads(enrolled_json.stdout)
    assert envelope["command"] == "config.recovery.status"
    assert envelope["result"]["recovery_enrolled"] is True
    assert mnemonic not in enrolled_json.stdout

    verified = _run_cli(
        tmp_path,
        ("config", "recovery", "verify", "--secrets-stdin"),
        stdin_payload=json.dumps({"recovery_code": mnemonic}),
    )
    assert verified.returncode == 0, _combined(verified)
    assert "verified\tyes" in verified.stdout
    assert mnemonic not in _combined(verified)

    rejected = _run_cli(
        tmp_path,
        ("config", "recovery", "verify", "--secrets-stdin"),
        stdin_payload=json.dumps({"recovery_code": "not a valid recovery code"}),
    )
    assert rejected.returncode == 2, _combined(rejected)
    assert "verified\tno" in rejected.stdout

    rotated_mnemonic, rotated_fingerprint, rotate_result = _enroll(tmp_path, "rotate")
    assert rotate_result.returncode == 0, _combined(rotate_result)
    assert rotated_mnemonic != mnemonic
    assert rotated_fingerprint != fingerprint
    assert "ROTATED\tyes" in rotate_result.stdout

    old_rejected = _run_cli(
        tmp_path,
        ("config", "recovery", "verify", "--secrets-stdin"),
        stdin_payload=json.dumps({"recovery_code": mnemonic}),
    )
    assert old_rejected.returncode == 2, _combined(old_rejected)
    assert "verified\tno" in old_rejected.stdout

    new_verified = _run_cli(
        tmp_path,
        ("config", "recovery", "verify", "--secrets-stdin"),
        stdin_payload=json.dumps({"recovery_code": rotated_mnemonic}),
    )
    assert new_verified.returncode == 0, _combined(new_verified)
    assert "verified\tyes" in new_verified.stdout

    recovered_value = "fresh recovery passphrase"
    recovered = _run_cli(
        tmp_path,
        ("config", "recover", "--secrets-stdin"),
        stdin_payload=json.dumps(
            {
                "recovery_code": rotated_mnemonic,
                "new_passphrase": recovered_value,
                "new_passphrase_confirmation": recovered_value,
            },
        ),
    )
    assert recovered.returncode == 0, _combined(recovered)
    assert "recovered\tyes" in recovered.stdout
    assert rotated_mnemonic not in _combined(recovered)
    assert recovered_value not in _combined(recovered)

    shown_after_recover = _run_cli(
        tmp_path,
        ("config", "profile", "show"),
        passphrase=recovered_value,
    )
    assert shown_after_recover.returncode == 0, _combined(shown_after_recover)
    assert "display_name\tcustody" in shown_after_recover.stdout

    # Recover reads, never rewrites, the envelope: fingerprint is preserved.
    status_after_recover = _run_cli(tmp_path, ("config", "recovery", "status"), passphrase=recovered_value)
    assert status_after_recover.returncode == 0, _combined(status_after_recover)
    assert f"recovery_fingerprint\t{rotated_fingerprint}" in status_after_recover.stdout


def test_recovery_create_and_rotate_refuse_without_interactive_terminal(tmp_path: Path) -> None:
    """Captured-stdio create/rotate refuse cleanly and leave the envelope untouched."""

    _create_profile(tmp_path)
    recovery_path = tmp_path / "secrets" / "master.recovery.key"

    refused_create = _run_cli(tmp_path, ("config", "recovery", "create"))
    assert refused_create.returncode == 2, _combined(refused_create)
    assert "interactive terminal" in _combined(refused_create)
    assert "Traceback" not in _combined(refused_create)
    assert not recovery_path.exists()

    mnemonic, _, enroll_result = _enroll(tmp_path, "create")
    assert enroll_result.returncode == 0, _combined(enroll_result)
    envelope_before = recovery_path.read_bytes()

    refused_rotate = _run_cli(tmp_path, ("config", "recovery", "rotate"))
    assert refused_rotate.returncode == 2, _combined(refused_rotate)
    assert "interactive terminal" in _combined(refused_rotate)
    assert recovery_path.read_bytes() == envelope_before

    still_verified = _run_cli(
        tmp_path,
        ("config", "recovery", "verify", "--secrets-stdin"),
        stdin_payload=json.dumps({"recovery_code": mnemonic}),
    )
    assert still_verified.returncode == 0, _combined(still_verified)
    assert "verified\tyes" in still_verified.stdout


def test_recovery_secrets_stdin_is_strict_bounded_json(tmp_path: Path) -> None:
    """Malformed, non-object, or wrong-field stdin payloads refuse before any custody read."""

    _create_profile(tmp_path)

    malformed = _run_cli(
        tmp_path,
        ("config", "recovery", "verify", "--secrets-stdin"),
        stdin_payload="this is not json",
    )
    assert malformed.returncode == 2, _combined(malformed)
    assert "Traceback" not in _combined(malformed)

    wrong_fields = _run_cli(
        tmp_path,
        ("config", "recovery", "verify", "--secrets-stdin"),
        stdin_payload=json.dumps({"recovery_code": "a b c", "unexpected": "field"}),
    )
    assert wrong_fields.returncode == 2, _combined(wrong_fields)

    non_object = _run_cli(
        tmp_path,
        ("config", "recover", "--secrets-stdin"),
        stdin_payload=json.dumps(["recovery", "code"]),
    )
    assert non_object.returncode == 2, _combined(non_object)


def test_recovery_secrets_stdin_refuses_oversize_payload(tmp_path: Path) -> None:
    """A payload past the 8192-byte cap refuses before any JSON parsing is attempted.

    The one branch written specifically to stop an unbounded hostile stream
    from being read into memory (``_MAX_SECRETS_STDIN_BYTES`` in
    ``_secure_input.py``) had no regression; this proves it drives the real
    CLI to a clean refusal rather than hanging, crashing, or reading past the
    bound.
    """

    _create_profile(tmp_path)

    oversize_payload = json.dumps({"recovery_code": "a" * 9000})
    assert len(oversize_payload.encode("utf-8")) > 8192

    oversize = _run_cli(
        tmp_path,
        ("config", "recovery", "verify", "--secrets-stdin"),
        stdin_payload=oversize_payload,
    )
    assert oversize.returncode == 2, _combined(oversize)
    assert "Traceback" not in _combined(oversize)


def test_recovery_secrets_stdin_refuses_duplicate_key(tmp_path: Path) -> None:
    """A repeated JSON key refuses instead of silently resolving to the last value.

    Plain ``json.loads`` collapses a duplicate object key to its last
    occurrence before the strict ``extra="forbid"`` model can ever observe the
    collision, so a payload assembled from concatenated fragments or a
    templating bug could silently rewrap the secret store under a value the
    caller never intended. Two conflicting ``recovery_code`` values prove the
    refusal fires rather than the second value being silently accepted.
    """

    _create_profile(tmp_path)
    mnemonic, _, enroll_result = _enroll(tmp_path, "create")
    assert enroll_result.returncode == 0, _combined(enroll_result)

    duplicated_payload = (
        '{"recovery_code": "definitely not the enrolled recovery code", "recovery_code": ' + json.dumps(mnemonic) + "}"
    )

    duplicate_key = _run_cli(
        tmp_path,
        ("config", "recovery", "verify", "--secrets-stdin"),
        stdin_payload=duplicated_payload,
    )
    assert duplicate_key.returncode == 2, _combined(duplicate_key)
    assert "Traceback" not in _combined(duplicate_key)
    # The duplicate is refused outright; the SECOND (real) value must not
    # have been silently accepted and reported as a successful verification.
    assert "verified\tyes" not in duplicate_key.stdout


def test_recover_refuses_passphrase_mismatch_and_wrong_code(tmp_path: Path) -> None:
    """A confirmation mismatch or a wrong recovery code leaves the vault untouched."""

    _create_profile(tmp_path)
    mnemonic, _, enroll_result = _enroll(tmp_path, "create")
    assert enroll_result.returncode == 0, _combined(enroll_result)

    mismatch = _run_cli(
        tmp_path,
        ("config", "recover", "--secrets-stdin"),
        stdin_payload=json.dumps(
            {
                "recovery_code": mnemonic,
                "new_passphrase": "first candidate value",
                "new_passphrase_confirmation": "second different value",
            },
        ),
    )
    assert mismatch.returncode == 2, _combined(mismatch)

    wrong_code = _run_cli(
        tmp_path,
        ("config", "recover", "--secrets-stdin"),
        stdin_payload=json.dumps(
            {
                "recovery_code": "definitely not the enrolled recovery code",
                "new_passphrase": "candidate value",
                "new_passphrase_confirmation": "candidate value",
            },
        ),
    )
    assert wrong_code.returncode == 2, _combined(wrong_code)

    # The provisioning passphrase still opens the vault after both refusals.
    shown = _run_cli(tmp_path, ("config", "profile", "show"))
    assert shown.returncode == 0, _combined(shown)
    assert "display_name\tcustody" in shown.stdout


def test_recovery_verbs_accept_no_mnemonic_argv(tmp_path: Path) -> None:
    """The retired ``--recovery-key`` argv channel is gone from every recovery verb."""

    for args in (
        ("config", "recover", "--recovery-key", "a b c"),
        ("config", "recovery", "verify", "--recovery-key", "a b c"),
    ):
        result = _run_cli(tmp_path, args)
        assert result.returncode != 0, _combined(result)
        assert "recovered\tyes" not in result.stdout
