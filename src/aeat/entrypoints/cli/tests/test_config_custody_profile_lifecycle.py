"""Real-entrypoint custody coverage for the profile lifecycle surface."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path
from textwrap import dedent

import pytest

from ....adapters.persistence.storage.master_key import RecoveryRecord
from ....core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLI_HARNESS = dedent(
    """
    from __future__ import annotations

    import sys
    from pathlib import Path

    from aeat.core import config as config_module
    from aeat.core.config import Settings

    storage_root = Path(sys.argv[1])
    passphrase_arg = sys.argv[2]
    cli_args = sys.argv[3:]
    base_settings = Settings(_env_file=None)
    passphrase = passphrase_arg or base_settings.aeat_dev_test_database_password
    settings = Settings(
        _env_file=None,
        aeat_local_storage_root=storage_root,
        aeat_secret_store_dir=storage_root / "secrets",
        aeat_secret_store_backend="file",
        aeat_secret_passphrase=passphrase,
        aeat_output_language="en",
    )
    token = config_module._settings_override.set(settings)
    try:
        sys.argv = ["aeat", *cli_args]
        from aeat.entrypoints.cli import main

        main()
    finally:
        config_module._settings_override.reset(token)
    """
)


def _env() -> dict[str, str]:
    env = {
        key: value for key, value in os.environ.items() if not key.startswith("AEAT_") and not key.startswith("PYTEST_")
    }
    env.update(
        {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }
    )
    return env


def _run_aeat(
    storage_root: Path,
    args: tuple[str, ...],
    *,
    passphrase: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = _env()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", _CLI_HARNESS, str(storage_root), passphrase or "", *args],
        cwd=Path(__file__).parents[3],
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=45.0,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def test_profile_create_provisions_file_custody_and_unlock_reopens_it(tmp_path: Path) -> None:
    """Profile lifecycle is the custody surface; no legacy bootstrap command is reintroduced."""

    created = _run_aeat(
        tmp_path,
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
            "--activity",
            "design",
            "--iva-regime",
            "GENERAL",
        ),
    )

    assert created.returncode == 0, _combined_output(created)
    assert "Status\tcreated" in created.stdout
    secret_dir = tmp_path / "secrets"
    assert (secret_dir / "master.key").is_file()
    assert (secret_dir / "master.kdf").is_file()
    assert (secret_dir / "salt").is_file()
    bucket_dirs = list((tmp_path / "buckets").iterdir())
    assert len(bucket_dirs) == 1
    bucket_id = bucket_dirs[0].name
    manifest = tomllib.loads((bucket_dirs[0] / "manifest.toml").read_text(encoding="utf-8"))
    assert manifest["key_schedule"] == "bucket-dek-v1"
    assert (tmp_path / "keystore" / bucket_id / "bucket.dek.json").is_file()

    logged_out = _run_aeat(tmp_path, ("config", "profile", "logout"))
    assert logged_out.returncode == 0, _combined_output(logged_out)
    assert "logged_out_profile" in logged_out.stdout

    switched = _run_aeat(tmp_path, ("config", "switch", "custody"))
    assert switched.returncode == 0, _combined_output(switched)
    assert "active_profile\tcustody" in switched.stdout

    deleted = _run_aeat(tmp_path, ("config", "profile", "delete", "custody", "--yes"))
    assert deleted.returncode == 0, _combined_output(deleted)
    assert "status\ttombstoned" in deleted.stdout
    assert "active_profile\t<none>" in deleted.stdout

    retired = _run_aeat(tmp_path, ("config", "init", "--help"))
    assert retired.returncode != 0
    assert "config.init" not in _combined_output(retired)


def test_config_lock_switch_drive_profile_lifecycle(tmp_path: Path) -> None:
    """Root custody verbs use the profile lifecycle session path."""

    created = _run_aeat(
        tmp_path,
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
            "--activity",
            "design",
            "--iva-regime",
            "GENERAL",
        ),
    )
    assert created.returncode == 0, _combined_output(created)

    locked = _run_aeat(tmp_path, ("config", "lock"))
    assert locked.returncode == 0, _combined_output(locked)
    assert "locked_profile\t" in locked.stdout

    missing_default = _run_aeat(tmp_path, ("config", "switch"))
    assert missing_default.returncode != 0
    assert "No active profile" in _combined_output(missing_default) or "active profile" in _combined_output(
        missing_default
    )

    switched_by_name = _run_aeat(tmp_path, ("config", "switch", "custody"))
    assert switched_by_name.returncode == 0, _combined_output(switched_by_name)
    assert "active_profile\tcustody" in switched_by_name.stdout

    switched_default = _run_aeat(tmp_path, ("config", "switch"))
    assert switched_default.returncode == 0, _combined_output(switched_default)
    assert "active_profile\tcustody" in switched_default.stdout


def test_config_recovery_and_rekey_verbs_round_trip_file_custody(tmp_path: Path) -> None:
    """First-class custody verbs recover the same encrypted profile under rotated passphrases."""

    created = _run_aeat(
        tmp_path,
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
            "--activity",
            "design",
            "--iva-regime",
            "GENERAL",
        ),
    )
    assert created.returncode == 0, _combined_output(created)

    enrolled = _run_aeat(tmp_path, ("config", "show-recovery"))
    assert enrolled.returncode == 0, _combined_output(enrolled)
    recovery_line = next(line for line in enrolled.stdout.splitlines() if line.startswith("recovery_key\t"))
    recovery_key = recovery_line.split("\t", 1)[1]
    assert len(recovery_key.split()) == 24
    recovery_path = tmp_path / "secrets" / "master.recovery.key"
    assert recovery_path.is_file()
    recovery_document = recovery_path.read_text(encoding="utf-8")
    recovery_record = RecoveryRecord.model_validate_json(recovery_document)
    assert recovery_record.mnemonic_word_count == 24
    assert recovery_record.hkdf_info == "aeat.recovery-key.master-wrap.v1"
    assert recovery_key not in recovery_document
    bucket_dir = next((tmp_path / "buckets").iterdir())
    manifest = tomllib.loads((bucket_dir / "manifest.toml").read_text(encoding="utf-8"))
    assert manifest["recovery_enrolled"] is True

    verified = _run_aeat(tmp_path, ("config", "verify-recovery", "--recovery-key", recovery_key))
    assert verified.returncode == 0, _combined_output(verified)
    assert "verified\tyes" in verified.stdout

    rejected = _run_aeat(tmp_path, ("config", "verify-recovery", "--recovery-key", "not a valid recovery key"))
    assert rejected.returncode == 2, _combined_output(rejected)
    assert "verified\tno" in rejected.stdout

    rotated_value = "correct horse battery staple"
    rekeyed = _run_aeat(
        tmp_path,
        (
            "config",
            "rekey",
            "--new-passphrase",
            rotated_value,
            "--confirm-new-passphrase",
            rotated_value,
        ),
    )
    assert rekeyed.returncode == 0, _combined_output(rekeyed)
    assert "rekeyed\tyes" in rekeyed.stdout

    verified_after_rekey = _run_aeat(tmp_path, ("config", "verify-recovery", "--recovery-key", recovery_key))
    assert verified_after_rekey.returncode == 0, _combined_output(verified_after_rekey)
    assert "verified\tyes" in verified_after_rekey.stdout

    shown_after_rekey = _run_aeat(
        tmp_path,
        ("config", "profile", "show"),
        passphrase=rotated_value,
    )
    assert shown_after_rekey.returncode == 0, _combined_output(shown_after_rekey)
    assert "display_name\tcustody" in shown_after_rekey.stdout

    recovered_value = "fresh recovery passphrase"
    recovered = _run_aeat(
        tmp_path,
        (
            "config",
            "recover",
            "--recovery-key",
            recovery_key,
            "--new-passphrase",
            recovered_value,
            "--confirm-new-passphrase",
            recovered_value,
        ),
        passphrase=rotated_value,
    )
    assert recovered.returncode == 0, _combined_output(recovered)
    assert "recovered\tyes" in recovered.stdout

    shown_after_recover = _run_aeat(
        tmp_path,
        ("config", "profile", "show"),
        passphrase=recovered_value,
    )
    assert shown_after_recover.returncode == 0, _combined_output(shown_after_recover)
    assert "display_name\tcustody" in shown_after_recover.stdout


def test_config_help_exposes_first_class_custody_verbs(tmp_path: Path) -> None:
    """The accepted custody verbs are mounted under the config root."""

    for verb in ("lock", "switch", "rekey", "recover", "show-recovery", "verify-recovery"):
        help_result = _run_aeat(tmp_path, ("config", verb, "--help"))
        assert help_result.returncode == 0, _combined_output(help_result)
        assert verb in _combined_output(help_result)


def test_profile_selection_precedence_uses_explicit_env_then_pointer(tmp_path: Path) -> None:
    """CLI profile reads resolve explicit name, env override, then pointer default."""

    first = _run_aeat(
        tmp_path,
        (
            "config",
            "profile",
            "create",
            "alpha",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--name",
            "Alpha Operator",
            "--activity",
            "consulting",
            "--iva-regime",
            "GENERAL",
        ),
    )
    assert first.returncode == 0, _combined_output(first)
    second = _run_aeat(
        tmp_path,
        (
            "config",
            "profile",
            "create",
            "beta",
            "--quiet",
            "--tax-id",
            "87654321X",
            "--name",
            "Beta Operator",
            "--activity",
            "design",
            "--iva-regime",
            "GENERAL",
        ),
    )
    assert second.returncode == 0, _combined_output(second)

    bucket_dirs = sorted(path for path in (tmp_path / "buckets").iterdir() if path.is_dir())
    labels_by_id: dict[str, str] = {}
    for bucket_dir in bucket_dirs:
        manifest = tomllib.loads((bucket_dir / "manifest.toml").read_text(encoding="utf-8"))
        labels_by_id[bucket_dir.name] = manifest["label"]
    alpha_id = next(bucket_id for bucket_id, label in labels_by_id.items() if label == "alpha")
    beta_id = next(bucket_id for bucket_id, label in labels_by_id.items() if label == "beta")

    pointer_default = _run_aeat(tmp_path, ("config", "profile", "show"))
    assert pointer_default.returncode == 0, _combined_output(pointer_default)
    assert "display_name\tbeta" in pointer_default.stdout

    env_default = _run_aeat(
        tmp_path,
        ("config", "profile", "show"),
        extra_env={"AEAT_ACTIVE_PROFILE": alpha_id},
    )
    assert env_default.returncode == 0, _combined_output(env_default)
    assert "display_name\talpha" in env_default.stdout

    explicit_name = _run_aeat(
        tmp_path,
        ("--profile", "alpha", "config", "profile", "show", "beta"),
        extra_env={"AEAT_ACTIVE_PROFILE": alpha_id},
    )
    assert explicit_name.returncode == 0, _combined_output(explicit_name)
    assert "display_name\tbeta" in explicit_name.stdout

    explicit_root = _run_aeat(
        tmp_path,
        ("--profile", "alpha", "config", "profile", "show"),
        extra_env={
            "AEAT_ACTIVE_PROFILE": next(bucket_id for bucket_id, label in labels_by_id.items() if label == "beta")
        },
    )
    assert explicit_root.returncode == 0, _combined_output(explicit_root)
    assert "display_name\talpha" in explicit_root.stdout

    explicit_root_by_id = _run_aeat(
        tmp_path,
        ("--profile", alpha_id, "config", "profile", "show"),
        extra_env={"AEAT_ACTIVE_PROFILE": alpha_id},
    )
    assert explicit_root_by_id.returncode == 0, _combined_output(explicit_root_by_id)
    assert "display_name\talpha" in explicit_root_by_id.stdout

    # Write-side precedence: configure-auth writes an
    # ``AUTH_PROVIDER_CONFIGURED`` event into the resolved bucket's
    # event history. The configure verb's stdout redacts the bucket id
    # to a literal ``<profile-id>`` placeholder (security: bucket ids
    # are sha256 fingerprints that must never reach stdout), so the
    # stdout cannot distinguish alpha from beta. Read each bucket's
    # event history via ``config bucket history`` to count writes per
    # bucket; the bucket whose count increases by 1 is the one the
    # configure verb resolved to.

    def _auth_event_counts() -> dict[str, int]:
        counts: dict[str, int] = {}
        for bucket_id in (alpha_id, beta_id):
            result = _run_aeat(
                tmp_path,
                (
                    "--profile",
                    bucket_id,
                    "config",
                    "bucket",
                    "history",
                    bucket_id,
                    "--event-type",
                    "auth.provider.configured",
                ),
            )
            assert result.returncode == 0, _combined_output(result)
            counts[bucket_id] = sum(1 for line in result.stdout.splitlines() if "\tauth.provider.configured\t" in line)
        return counts

    before = _auth_event_counts()

    # Pointer-default precedence: pointer points at beta (last create wins).
    pointer_write = _run_aeat(tmp_path, ("config", "auth", "configure", "--provider", "clave_movil"))
    assert pointer_write.returncode == 0, _combined_output(pointer_write)
    assert "No active profile" not in _combined_output(pointer_write)
    after_pointer = _auth_event_counts()
    assert after_pointer[beta_id] == before[beta_id] + 1, (
        f"pointer default should resolve to beta; counts before={before}, after={after_pointer}"
    )
    assert after_pointer[alpha_id] == before[alpha_id], (
        f"pointer default should not write to alpha; counts before={before}, after={after_pointer}"
    )

    # Env-override precedence: AEAT_ACTIVE_PROFILE wins over the pointer.
    env_write = _run_aeat(
        tmp_path,
        ("config", "auth", "configure", "--provider", "clave_movil"),
        extra_env={"AEAT_ACTIVE_PROFILE": alpha_id},
    )
    assert env_write.returncode == 0, _combined_output(env_write)
    assert "No active profile" not in _combined_output(env_write)
    after_env = _auth_event_counts()
    assert after_env[alpha_id] == after_pointer[alpha_id] + 1, (
        f"env override should resolve to alpha; counts before={after_pointer}, after={after_env}"
    )
    assert after_env[beta_id] == after_pointer[beta_id], (
        f"env override should not write to beta; counts before={after_pointer}, after={after_env}"
    )

    # Explicit-flag precedence: --profile wins over env override.
    explicit_write = _run_aeat(
        tmp_path,
        ("--profile", "beta", "config", "auth", "configure", "--provider", "clave_movil"),
        extra_env={"AEAT_ACTIVE_PROFILE": alpha_id},
    )
    assert explicit_write.returncode == 0, _combined_output(explicit_write)
    assert "No active profile" not in _combined_output(explicit_write)
    after_explicit = _auth_event_counts()
    assert after_explicit[beta_id] == after_env[beta_id] + 1, (
        f"--profile flag should resolve to beta; counts before={after_env}, after={after_explicit}"
    )
    assert after_explicit[alpha_id] == after_env[alpha_id], (
        f"--profile flag should not write to alpha; counts before={after_env}, after={after_explicit}"
    )


def test_profile_lifecycle_storage_spans_are_application_owned() -> None:
    """CLI and wizard code delegate custody spans to application profile lifecycle operations."""

    scanned = {
        "src/aeat/entrypoints/cli/_config/__init__.py": (
            "activate_master_key_provider",
            "get_master_key_provider",
            "_write_active_profile_pointer",
            "_clear_active_profile_pointer",
            "capture_active_profile_pointer",
            "restore_active_profile_pointer",
            "override_settings(aeat_active_profile",
        ),
        "src/aeat/application/wizard/_commands.py": (
            "activate_master_key_provider",
            "get_master_key_provider",
            "_write_active_profile_pointer",
            "_clear_active_profile_pointer",
            "capture_active_profile_pointer",
            "restore_active_profile_pointer",
            "override_settings(aeat_active_profile",
        ),
        "src/aeat/application/setup/_service.py": (
            "_write_active_profile_pointer",
            "capture_active_profile_pointer",
            "restore_active_profile_pointer",
        ),
    }
    offenders: list[str] = []
    for relative_path, forbidden_tokens in scanned.items():
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                offenders.append(f"{relative_path}: {token}")

    assert offenders == []
