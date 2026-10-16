"""Checkout bootstrap preserves application storage and machine-owned tool settings."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from cadrumo.core.storage_environment import TOOL_STORAGE_LOCATIONS, tool_storage_environment
from dev._paths import REPO_ROOT
from dev.docs.build_paths import DOCS_BUILD_ROOT_ENV, docs_build_root
from dev.packaging.command_execution import run_command
from dev.product_environment import clean_product_env

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_source_bootstrap_retains_console_root_and_authority_from_another_cwd(tmp_path: Path) -> None:
    """Checkout tooling inherits the console root without selecting another runtime store."""
    root = tmp_path / "console storage"
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    authority = tmp_path / "selected authority"
    authority.mkdir()
    environment = clean_product_env()
    environment["CARGO_HOME"] = str(tmp_path / "machine cargo")
    environment.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
            "CADRUMO_STORAGE_ROOT": str(tmp_path / "different checkout storage"),
            "CADRUMO_AUTHORITY_ROOT": str(authority),
        }
    )
    # Import the actual checkout bootstrap from an unrelated working directory.
    # No profile identifiers, passwords or runtime credentials are supplied.
    script = "\n".join(
        (
            "import json, os, sys",
            f"sys.path.insert(0, {str(REPO_ROOT)!r})",
            "import dev._paths",
            "from cadrumo.core.storage_environment import configured_storage_root",
            "print(json.dumps({'root': str(configured_storage_root()),",
            "'authority': os.environ['CADRUMO_AUTHORITY_ROOT'],",
            "'temp': os.environ['TEMP'], 'cargo': os.environ['CARGO_HOME']}))",
        )
    )
    completed = run_command(
        [sys.executable, "-c", script], cwd=workspace, environment=environment, timeout_seconds=None
    )
    assert completed.returncode == 0, completed.stderr
    observed = json.loads(completed.stdout)
    assert Path(observed["root"]) == root.resolve()
    assert Path(observed["authority"]) == authority
    assert Path(observed["temp"]) == Path(environment["TEMP"])
    assert Path(observed["temp"]).is_dir()
    assert Path(observed["cargo"]) == Path(environment["CARGO_HOME"])


@pytest.mark.parametrize("member", ["", "relative-docs", "absolute-docs"])
def test_just_and_python_resolve_the_documentation_build_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, member: str
) -> None:
    executable = shutil.which("just")
    assert executable is not None, "the repository task runner is required"
    storage_root = tmp_path / "shared storage"
    monkeypatch.setenv("CADRUMO_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", "")
    override = str(tmp_path / member) if member == "absolute-docs" else member
    monkeypatch.setenv(DOCS_BUILD_ROOT_ENV, override)
    environment = dict(os.environ)
    expected = docs_build_root(REPO_ROOT, environ=environment)

    completed = run_command(
        [executable, "--justfile", str(REPO_ROOT / "justfile"), "--evaluate", DOCS_BUILD_ROOT_ENV],
        cwd=REPO_ROOT,
        environment=environment,
        timeout_seconds=None,
    )
    assert completed.returncode == 0, completed.stderr
    assert Path(completed.stdout.strip()).resolve() == expected
    if not override:
        assert expected == REPO_ROOT / "build" / "docs"


def test_just_preserves_machine_uv_paths_and_ignores_retired_cadrumo_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = shutil.which("just")
    assert executable is not None, "the repository task runner is required"
    machine_paths = {
        "UV_CACHE_DIR": str(tmp_path / "machine-cache"),
        "UV_PYTHON_INSTALL_DIR": str(tmp_path / "machine-python"),
        "UV_TOOL_DIR": str(tmp_path / "machine-tools"),
        "UV_TOOL_BIN_DIR": str(tmp_path / "machine-tool-bin"),
        "UV_PROJECT_ENVIRONMENT": str(tmp_path / "machine-project-env"),
    }
    retired_controls = {
        "CADRUMO_UV_CACHE_DIR": str(tmp_path / "retired-cache"),
        "CADRUMO_UV_PYTHON_DIR": str(tmp_path / "retired-python"),
        "CADRUMO_UV_TOOL_DIR": str(tmp_path / "retired-tools"),
        "CADRUMO_UV_TOOL_BIN_DIR": str(tmp_path / "retired-tool-bin"),
    }
    for name, value in {**machine_paths, **retired_controls}.items():
        monkeypatch.setenv(name, value)

    call_operator = "& " if os.name == "nt" else ""
    probe = tmp_path / "uv_environment_probe.py"
    probe.write_text(
        "import json, os\n"
        f"names = {tuple(machine_paths) + tuple(retired_controls)!r}\n"
        "print(json.dumps({name: os.environ.get(name) for name in names}))\n",
        encoding="utf-8",
    )
    justfile = tmp_path / "Justfile"
    justfile.write_text(
        f"_probe_python := quote({json.dumps(Path(sys.executable).as_posix())})\n"
        f"_probe_script := quote({json.dumps(probe.as_posix())})\n"
        + (REPO_ROOT / "justfile").read_text(encoding="utf-8")
        + f"\nuv-machine-env-probe:\n    {call_operator}{{{{_probe_python}}}} -I -B {{{{_probe_script}}}}\n",
        encoding="utf-8",
    )
    completed = run_command(
        [executable, "--justfile", str(justfile), "uv-machine-env-probe"],
        cwd=REPO_ROOT,
        environment=dict(os.environ),
        timeout_seconds=None,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout) == {**machine_paths, **retired_controls}

    native_variables = set(tool_storage_environment())
    refinement_variables = {variable for variable, _default in TOOL_STORAGE_LOCATIONS.values()}
    assert not set(machine_paths) & native_variables
    assert not set(retired_controls) & refinement_variables
