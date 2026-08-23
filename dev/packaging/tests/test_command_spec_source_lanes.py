"""Clean tracked-source and editable-install CommandSpec authority gates."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import cast

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REPOSITORY = Path(__file__).resolve().parents[3]
_FORBIDDEN_PATHS = (
    "src/cadrumo/entrypoints/cli/app_lazy_manifest.v1.json",
    "src/cadrumo/entrypoints/cli/command_registration_metadata.v1.json",
    "dev/quality/generate_app_lazy_manifest.py",
    "dev/quality/generate_command_registration_metadata.py",
)
_PROBE = r"""
import json
import sys
from click.testing import CliRunner
from typer.main import get_command
from cadrumo.entrypoints import cli
from cadrumo.entrypoints.cli.command_api import (
    build_verb_input_schemas,
    command_schema_refs,
    command_spec_nodes,
)
from cadrumo_harness.mcp import ConfirmationPolicy, build_tool_descriptors, confirmation_for_tool

nodes = command_spec_nodes()
specs = {node.spec.key: node.spec for node in nodes}
schemas = command_schema_refs()
inputs = build_verb_input_schemas(tuple(sorted(ref.command for ref in schemas)))
descriptors = build_tool_descriptors()
help_result = CliRunner().invoke(get_command(cli.app), ["--help"])
payload = {
    "nodes": len(nodes),
    "paths": len({node.path for node in nodes}),
    "help_exit": help_result.exit_code,
    "help_has_roots": all(token in help_result.output for token in ("config", "app")),
    "completion": specs["root"].invocation.add_completion,
    "schemas": len(schemas),
    "inputs": len(inputs),
    "descriptors": len(descriptors),
    "operator_exact": {ref.command for ref in schemas} == set(inputs),
    "mcp_exact": {item.command_key for item in descriptors}.issubset(set(inputs)),
    "hitl_read": confirmation_for_tool(command_key="registry.inspect") is ConfirmationPolicy.AUTO_APPROVE,
    "hitl_write": confirmation_for_tool(command_key="modelo.export") is ConfirmationPolicy.CONFIRM,
    "write_route": specs["config_profile_create"].policy.write_route,
    "dev_imports": sorted(name for name in sys.modules if name == "dev" or name.startswith("dev.")),
}
print(json.dumps(payload, sort_keys=True))
"""


def _tracked_checkout(tmp_path: Path) -> Path:
    archive = tmp_path / "tracked.tar"
    checkout = tmp_path / "checkout"
    git = shutil.which("git")
    assert git is not None
    subprocess.run(  # noqa: S603 - resolved Git executable and fixed authored arguments
        [git, "archive", "--format=tar", f"--output={archive}", "HEAD"],
        cwd=_REPOSITORY,
        check=True,
    )
    checkout.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(checkout, filter="data")
    return checkout


def _run_probe(*, python: Path, pythonpath: tuple[Path, ...], cwd: Path) -> dict[str, object]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(str(path) for path in pythonpath)
    completed = subprocess.run(  # noqa: S603 - selected lane interpreter and fixed probe
        [str(python), "-c", _PROBE],
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    decoded = json.loads(completed.stdout)
    assert isinstance(decoded, dict)
    return cast("dict[str, object]", decoded)


def _assert_complete_projection(payload: dict[str, object]) -> None:
    assert payload["nodes"] == payload["paths"] == 361
    assert payload["help_exit"] == 0
    assert payload["help_has_roots"] is True
    assert payload["completion"] is True
    assert payload["schemas"] == payload["inputs"] == 296
    assert isinstance(payload["descriptors"], int) and payload["descriptors"] > 0
    assert payload["operator_exact"] is True
    assert payload["mcp_exact"] is True
    assert payload["hitl_read"] is True
    assert payload["hitl_write"] is True
    assert payload["write_route"] == "bootstrap-root"
    assert payload["dev_imports"] == []


def test_clean_tracked_checkout_direct_source_and_editable_install(tmp_path: Path) -> None:
    checkout = _tracked_checkout(tmp_path)
    assert all(not (checkout / relative).exists() for relative in _FORBIDDEN_PATHS)
    assert not any(
        path.name in {"app_lazy_manifest.v1.json", "command_registration_metadata.v1.json"}
        for path in checkout.rglob("*.json")
    )

    source_paths = (checkout / "src", checkout / "src/cadrumo-harness/src")
    _assert_complete_projection(_run_probe(python=Path(sys.executable), pythonpath=source_paths, cwd=checkout))

    editable_target = checkout / ".editable-target"
    uv = shutil.which("uv")
    assert uv is not None
    subprocess.run(  # noqa: S603 - resolved uv executable and isolated authored checkout
        [uv, "pip", "install", "--target", str(editable_target), "--no-deps", "--editable", str(checkout)],
        check=True,
    )
    _assert_complete_projection(
        _run_probe(
            python=Path(sys.executable),
            pythonpath=(editable_target, checkout / "src/cadrumo-harness/src"),
            cwd=checkout,
        )
    )
