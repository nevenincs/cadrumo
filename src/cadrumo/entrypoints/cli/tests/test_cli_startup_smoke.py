"""Subprocess startup smoke tests for public CLI discovery paths."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from ....tests import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_ACTIVE_PROFILE_WITHOUT_SECRET_HARNESS = dedent(
    """
    from __future__ import annotations

    import sys
    from pathlib import Path

    from cadrumo.core import config as config_module
    from cadrumo.core.config import Settings

    storage_root = Path(sys.argv[1])
    cli_args = sys.argv[2:]
    settings = Settings(
        _env_file=None,
        cadrumo_local_storage_root=storage_root,
        cadrumo_active_profile="11111111-1111-4111-8111-111111111111",
        cadrumo_secret_store_backend="auto",
        cadrumo_secret_store_dir=storage_root / "fallback-store",
        cadrumo_output_language="en",
    )
    token = config_module.settings_override.set(settings)
    try:
        sys.argv = ["aeat", *cli_args]
        from cadrumo.entrypoints.cli import main

        main()
    finally:
        config_module.settings_override.reset(token)
    """,
)


def _run_startup_smoke(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    return subprocess.run(  # noqa: S603 - fixed interpreter argv with controlled test inputs.
        [sys.executable, "-c", _ACTIVE_PROFILE_WITHOUT_SECRET_HARNESS, str(tmp_path), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=120.0,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def _assert_no_startup_crash(output: str) -> None:
    assert "Traceback" not in output
    assert "ImportError" not in output
    assert "cannot import name 'RescateType'" not in output
    assert "CADRUMO_SECRET_PASSPHRASE is not set" not in output


def test_app_modelo_list_starts_without_unlocking_active_profile(tmp_path: Path) -> None:
    """``aeat app modelo list`` renders bundled registry rows before profile unlock."""

    result = _run_startup_smoke(tmp_path, "app", "modelo", "list")

    output = _combined_output(result)
    assert result.returncode == 0, output
    _assert_no_startup_crash(output)
    assert "code\ttitle\tcadence\tdomain\trevisions\tlocal_work\tlocal_work_guidance" in output
    assert "303" in output


def test_config_repair_integrity_help_starts_without_unlocking_active_profile(tmp_path: Path) -> None:
    """``aeat config repair integrity --help`` renders command help before profile unlock."""

    result = _run_startup_smoke(tmp_path, "config", "repair", "integrity", "--help")

    output = _combined_output(result)
    assert result.returncode == 0, output
    _assert_no_startup_crash(output)
    assert "Usage: aeat config repair integrity" in output
    assert "objects" in output
    assert "registry" in output
