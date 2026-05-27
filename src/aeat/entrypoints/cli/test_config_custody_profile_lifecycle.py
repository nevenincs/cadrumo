"""Real-entrypoint custody coverage for the profile lifecycle surface."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path
from textwrap import dedent

import pytest

from aeat.core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_CLI_HARNESS = dedent(
    """
    from __future__ import annotations

    import sys
    from pathlib import Path

    from aeat.core import config as config_module
    from aeat.core.config import Settings

    storage_root = Path(sys.argv[1])
    cli_args = sys.argv[2:]
    base_settings = Settings(_env_file=None)
    settings = Settings(
        _env_file=None,
        aeat_local_storage_root=storage_root,
        aeat_secret_store_dir=storage_root / "secrets",
        aeat_secret_store_backend="file",
        aeat_secret_passphrase=base_settings.aeat_dev_test_database_password,
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
    env = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
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
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = _env()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(  # noqa: S603 - trusted interpreter and literal test harness.
        [sys.executable, "-c", _CLI_HARNESS, str(storage_root), *args],
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


def test_profile_create_provisions_file_custody_and_switch_reopens_it(tmp_path: Path) -> None:
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
    assert "status\tcreated" in created.stdout
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

    switched = _run_aeat(tmp_path, ("config", "profile", "switch", "custody"))
    assert switched.returncode == 0, _combined_output(switched)
    assert "active_profile\tcustody" in switched.stdout

    deleted = _run_aeat(tmp_path, ("config", "profile", "delete", "custody", "--yes"))
    assert deleted.returncode == 0, _combined_output(deleted)
    assert "status\ttombstoned" in deleted.stdout
    assert "active_profile\t<none>" in deleted.stdout

    retired = _run_aeat(tmp_path, ("config", "init", "--help"))
    assert retired.returncode != 0
    assert "config.init" not in _combined_output(retired)


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
        extra_env={"AEAT_ACTIVE_PROFILE": next(
            bucket_id for bucket_id, label in labels_by_id.items() if label == "beta"
        )},
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

    pointer_write = _run_aeat(tmp_path, ("config", "auth", "configure", "--provider", "clave_movil"))
    assert pointer_write.returncode == 0, _combined_output(pointer_write)
    assert f"active_profile\t{beta_id}" in pointer_write.stdout
    assert "No active profile" not in _combined_output(pointer_write)

    env_write = _run_aeat(
        tmp_path,
        ("config", "auth", "configure", "--provider", "clave_movil"),
        extra_env={"AEAT_ACTIVE_PROFILE": alpha_id},
    )
    assert env_write.returncode == 0, _combined_output(env_write)
    assert f"active_profile\t{alpha_id}" in env_write.stdout
    assert "No active profile" not in _combined_output(env_write)

    explicit_write = _run_aeat(
        tmp_path,
        ("--profile", "beta", "config", "auth", "configure", "--provider", "clave_movil"),
        extra_env={"AEAT_ACTIVE_PROFILE": alpha_id},
    )
    assert explicit_write.returncode == 0, _combined_output(explicit_write)
    assert f"active_profile\t{beta_id}" in explicit_write.stdout
    assert "No active profile" not in _combined_output(explicit_write)


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
