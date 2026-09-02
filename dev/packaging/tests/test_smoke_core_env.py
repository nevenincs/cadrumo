"""Subprocess isolation tests for the installed-core smoke environment."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from .._smoke_common import installed_product_env, venv_bin_dir

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_isolated_product_env_refuses_host_settings_and_former_state(tmp_path: Path) -> None:
    """A real child receives only isolated Cadrumo state despite hostile host inputs."""
    local_app_data = tmp_path / "host-local-app-data"
    former_state = local_app_data / "aeat"
    former_state.mkdir(parents=True)
    hostile_storage = tmp_path / "host-cadrumo-state"
    isolated_storage = tmp_path / "isolated-cadrumo-state"
    worker = textwrap.dedent(
        """
        import os
        import subprocess
        import sys
        from pathlib import Path

        from dev.packaging._smoke_common import isolated_product_env

        isolated = Path(sys.argv[1])
        os.environ.update(
            {
                "PYTHONHOME": str(isolated / "host-python"),
                "PYTHONUSERBASE": str(isolated / "host-userbase"),
                "VIRTUAL_ENV": str(isolated / "host-venv"),
                "CONDA_PREFIX": str(isolated / "host-conda"),
                "CONDA_DEFAULT_ENV": "host",
                "UV_PROJECT_ENVIRONMENT": str(isolated / "host-uv"),
            }
        )
        env = isolated_product_env(isolated)
        assert env["CADRUMO_LOCAL_STORAGE_ROOT"] == str(isolated)
        assert env["CADRUMO_DATABASE_URL"] == f"sqlite:///{(isolated / 'cadrumo.db').as_posix()}"
        assert "CADRUMO_OUTPUT_LANGUAGE" not in env
        assert "CADRUMO_SECRET_PASSPHRASE" not in env
        for name in (
            "PYTHONPATH",
            "PYTHONHOME",
            "PYTHONUSERBASE",
            "VIRTUAL_ENV",
            "CONDA_PREFIX",
            "CONDA_DEFAULT_ENV",
            "UV_PROJECT_ENVIRONMENT",
        ):
            assert name not in env
        code = "\\n".join(
            (
                "import sys",
                "from pathlib import Path",
                "from cadrumo.core.config import load_settings",
                "settings = load_settings()",
                "expected = Path(sys.argv[1])",
                "assert settings.cadrumo_local_storage_root == expected",
                'print("isolated-product-env-ok")',
            )
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(isolated)], env=env, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            raise SystemExit(result.returncode)
        print(result.stdout, end="")
        """
    )
    host_env = {
        **os.environ,
        "LOCALAPPDATA": str(local_app_data),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(hostile_storage),
        "CADRUMO_DATABASE_URL": f"sqlite:///{(hostile_storage / 'host.db').as_posix()}",
        "CADRUMO_OUTPUT_LANGUAGE": "hostile-language",
        "CADRUMO_SECRET_PASSPHRASE": "hostile-passphrase",
        "PYTHONPATH": str(tmp_path / "checkout-imports"),
    }
    result = subprocess.run(  # noqa: S603 - fixed interpreter and test-authored worker source.
        [sys.executable, "-c", worker, str(isolated_storage)],
        cwd=REPO_ROOT,
        env=host_env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "isolated-product-env-ok\n"


def test_installed_product_env_removes_checkout_imports_and_ambient_executables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Installed acceptance exposes only the selected venv, never host paths."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    ambient_bin = tmp_path / "ambient-bin"
    ambient_bin.mkdir()
    ambient_executable = ambient_bin / ("aeat.cmd" if os.name == "nt" else "aeat")
    ambient_executable.write_text("ambient product executable\n", encoding="utf-8")
    if os.name != "nt":
        ambient_executable.chmod(0o700)
    monkeypatch.setenv("PYTHONPATH", str(checkout))
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "host-venv"))
    monkeypatch.setenv("PATH", str(ambient_bin))

    target_venv = tmp_path / "target-venv"
    target_bin = venv_bin_dir(target_venv)
    target_bin.mkdir(parents=True)
    environment = installed_product_env(tmp_path / "state", target_venv)

    assert environment["PATH"] == str(target_bin.resolve())
    assert str(checkout) not in environment["PATH"]
    assert shutil.which("aeat", path=environment["PATH"]) is None
    for name in (
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONUSERBASE",
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "CONDA_DEFAULT_ENV",
        "UV_PROJECT_ENVIRONMENT",
    ):
        assert name not in environment

    worker = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import os; assert 'PYTHONPATH' not in os.environ; print('installed-env-ok')",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert worker.returncode == 0, worker.stderr
    assert worker.stdout == "installed-env-ok\n"
