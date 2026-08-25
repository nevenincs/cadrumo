"""Subprocess isolation tests for the installed-core smoke environment."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT

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

        from .._smoke_common import isolated_product_env

        isolated = Path(sys.argv[1])
        env = isolated_product_env(isolated)
        assert env["CADRUMO_LOCAL_STORAGE_ROOT"] == str(isolated)
        assert env["CADRUMO_DATABASE_URL"] == f"sqlite:///{(isolated / 'cadrumo.db').as_posix()}"
        assert "CADRUMO_OUTPUT_LANGUAGE" not in env
        assert "CADRUMO_SECRET_PASSPHRASE" not in env
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
