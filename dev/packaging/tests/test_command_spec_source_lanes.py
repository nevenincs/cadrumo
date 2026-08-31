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
import os
import sys
from pathlib import Path
sys.path.append(os.environ["AEAT_DEPENDENCY_SITE"])
if editable_site := os.environ.get("AEAT_EDITABLE_SITE"):
    import site
    site.addsitedir(editable_site)
from click.testing import CliRunner
from typer.main import get_command
import cadrumo
from cadrumo.entrypoints import cli
from cadrumo.entrypoints.cli.command_api import (
    build_verb_input_schemas,
    command_schema_refs,
    command_schema_types,
    command_spec_nodes,
)
from cadrumo.core.json_contract import ENVELOPE_SCHEMA_VERSION
from cadrumo.entrypoints.cli.command_spec import SchemaState

nodes = command_spec_nodes()
specs = {node.spec.key: node.spec for node in nodes}
expected_results = {
    node.spec.result_schema.identity
    for node in nodes
    if node.spec.result_schema.state is SchemaState.TARGET
}
schemas = command_schema_refs()
inputs = build_verb_input_schemas(tuple(sorted(expected_results)))
schema_types = command_schema_types()
help_result = CliRunner().invoke(get_command(cli.app), ["--help"])
completion_result = CliRunner().invoke(get_command(cli.app), ["--show-completion", "bash"])
payload = {
    "nodes": len(nodes),
    "paths": len({node.path for node in nodes}),
    "help_exit": help_result.exit_code,
    "help_has_roots": all(token in help_result.output for token in ("config", "app")),
    "completion_exit": completion_result.exit_code,
    "completion_content": "_AEAT_COMPLETE" in completion_result.output,
    "schemas": len(schemas),
    "inputs": len(inputs),
    "schema_types": len(schema_types),
    "refs_exact": {ref.command for ref in schemas} == expected_results,
    "inputs_exact": set(inputs) == expected_results,
    "types_exact": set(schema_types) == expected_results,
    "write_route": specs["config_profile_create"].policy.write_route,
    "dev_imports": sorted(name for name in sys.modules if name == "dev" or name.startswith("dev.")),
    "origins": [
        str(Path(cadrumo.__file__).resolve()),
        str(Path(cli.__file__).resolve()),
    ],
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


def _run_probe(
    *, python: Path, pythonpath: tuple[Path, ...], cwd: Path, editable_site: Path | None = None
) -> dict[str, object]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(str(path) for path in pythonpath)
    dependency_site = next(path for path in map(Path, sys.path) if path.name == "site-packages" and path.is_dir())
    environment["AEAT_DEPENDENCY_SITE"] = str(dependency_site)
    if editable_site is not None:
        environment["AEAT_EDITABLE_SITE"] = str(editable_site)
    completed = subprocess.run(  # noqa: S603 - selected lane interpreter and fixed probe
        [str(python), "-S", "-c", _PROBE],
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


def _assert_complete_projection(payload: dict[str, object], *, checkout: Path) -> None:
    assert payload["nodes"] == payload["paths"]
    assert payload["help_exit"] == 0
    assert payload["help_has_roots"] is True
    assert payload["completion_exit"] == 0
    assert payload["completion_content"] is True
    assert payload["schemas"] == payload["inputs"] == payload["schema_types"]
    assert payload["refs_exact"] is True
    assert payload["inputs_exact"] is True
    assert payload["types_exact"] is True
    assert payload["write_route"] == "bootstrap-root"
    assert payload["dev_imports"] == []
    assert all(Path(origin).is_relative_to(checkout) for origin in cast("list[str]", payload["origins"]))


def test_clean_tracked_checkout_direct_source_and_editable_install(tmp_path: Path) -> None:
    checkout = _tracked_checkout(tmp_path)
    assert all(not (checkout / relative).exists() for relative in _FORBIDDEN_PATHS)
    assert not any(
        path.name in {"app_lazy_manifest.v1.json", "command_registration_metadata.v1.json"}
        for path in checkout.rglob("*.json")
    )

    source_paths = (checkout / "src",)
    _assert_complete_projection(
        _run_probe(python=Path(sys.executable), pythonpath=source_paths, cwd=checkout), checkout=checkout
    )

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
            pythonpath=(),
            cwd=checkout,
            editable_site=editable_target,
        ),
        checkout=checkout,
    )
