"""Real Import Linter proofs for the dedicated TUI dependency contracts."""

from __future__ import annotations

import configparser
import io
import os
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from importlinter.cli import lint_imports

from .._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

IMPORTLINTER_CONFIG = REPO_ROOT / ".importlinter"
CONTRACTS = (
    "tui-backend-prohibition",
    "tui-sibling-entrypoint-prohibition",
    "tui-launcher-only-adapter-wiring",
    "tui-components-independent",
    "tui-feature-independence",
)
_FIXTURE_ROOT = "tui_boundary_fixture"


def _fixture_module(relative: str) -> str:
    return relative.replace("cadrumo", _FIXTURE_ROOT, 1)


def _write_package(root: Path, relative: str, source: str = "") -> None:
    relative = _fixture_module(relative)
    path = root / Path(*relative.split("."))
    path.mkdir(parents=True, exist_ok=True)
    (path / "__init__.py").write_text(source, encoding="utf-8")


def _write_module(root: Path, relative: str, source: str = "") -> None:
    relative = _fixture_module(relative)
    source = source.replace("cadrumo", _FIXTURE_ROOT)
    parts = relative.split(".")
    path = root.joinpath(*parts[:-1], f"{parts[-1]}.py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _write_contract_config(root: Path) -> None:
    live = configparser.ConfigParser(interpolation=None)
    live.read(IMPORTLINTER_CONFIG, encoding="utf-8")

    selected = configparser.ConfigParser(interpolation=None)
    selected["importlinter"] = {
        key: value.replace("cadrumo", _FIXTURE_ROOT) for key, value in live["importlinter"].items()
    }
    for contract in CONTRACTS:
        section = f"importlinter:contract:{contract}"
        selected[section] = {key: value.replace("cadrumo", _FIXTURE_ROOT) for key, value in live[section].items()}

    with (root / ".importlinter").open("w", encoding="utf-8") as stream:
        selected.write(stream)


def _write_real_tui_topology(root: Path) -> None:
    for package in (
        "cadrumo",
        "cadrumo.adapters",
        "cadrumo.adapters.persistence",
        "cadrumo.application",
        "cadrumo.core",
        "cadrumo.domain",
        "cadrumo.llm",
        "cadrumo.tests",
        "cadrumo.entrypoints",
        "cadrumo.entrypoints.cli",
        "cadrumo.entrypoints.tui",
        "cadrumo.entrypoints.tui.launcher",
        "cadrumo.entrypoints.tui.components",
        "cadrumo.entrypoints.tui.operations",
        "cadrumo.entrypoints.tui.profile",
        "cadrumo.entrypoints.tui.secret",
        "cadrumo.entrypoints.tui.flows",
    ):
        _write_package(root, package)

    _write_package(root, "cadrumo.entrypoints.tui.launcher", "import cadrumo.adapters\n")
    _write_module(root, "cadrumo.entrypoints.tui.app")
    _write_module(root, "cadrumo.entrypoints.tui.components.forms")
    _write_module(root, "cadrumo.entrypoints.tui.operations.worker")
    _write_module(root, "cadrumo.entrypoints.tui.profile.screen")
    _write_module(root, "cadrumo.entrypoints.tui.secret.screen")
    _write_module(root, "cadrumo.entrypoints.tui.flows.screen")


def _run_import_linter(root: Path) -> tuple[int, str]:
    previous_cwd = Path.cwd()
    output = io.StringIO()
    try:
        os.chdir(root)
        with redirect_stdout(output):
            return_code = lint_imports(no_cache=True)
    finally:
        os.chdir(previous_cwd)
    return return_code, output.getvalue()


def test_tui_contracts_accept_the_declared_hexagonal_topology(tmp_path: Path) -> None:
    _write_contract_config(tmp_path)
    _write_real_tui_topology(tmp_path)

    return_code, output = _run_import_linter(tmp_path)

    assert return_code == 0, output
    assert "Contracts: 5 kept, 0 broken." in output


def test_launcher_descendant_may_wire_an_adapter_descendant(tmp_path: Path) -> None:
    _write_contract_config(tmp_path)
    _write_real_tui_topology(tmp_path)
    _write_module(
        tmp_path,
        "cadrumo.entrypoints.tui.launcher.wiring",
        "import cadrumo.adapters.persistence\n",
    )

    return_code, output = _run_import_linter(tmp_path)

    assert return_code == 0, output
    assert "Contracts: 5 kept, 0 broken." in output


@pytest.mark.parametrize(
    ("module", "source", "broken_contract"),
    (
        (
            "cadrumo.application.service",
            "from cadrumo.entrypoints.tui import launcher\n",
            "Backend and sibling entrypoints must not depend on the dedicated TUI",
        ),
        (
            "cadrumo.entrypoints.cli.command",
            "from cadrumo.entrypoints.tui import launcher\n",
            "Backend and sibling entrypoints must not depend on the dedicated TUI",
        ),
        (
            "cadrumo.entrypoints.tui.app",
            "import cadrumo.adapters.persistence\n",
            "Only the TUI launcher may wire concrete adapters",
        ),
        (
            "cadrumo.entrypoints.tui.components.forms",
            "from cadrumo.entrypoints.tui.operations import worker\n",
            "TUI component implementations depend only on Textual and neutral core presentation",
        ),
        (
            # Two ENROLLED features. `operations` is deliberately not among
            # them -- it is the shared surface every feature may run -- so an
            # edge out of it no longer crosses this boundary and would prove
            # nothing here.
            "cadrumo.entrypoints.tui.secret.vault",
            "from cadrumo.entrypoints.tui.profile import screen\n",
            "TUI feature implementations share components rather than each other",
        ),
    ),
)
def test_each_tui_boundary_rejects_a_real_import_edge(
    tmp_path: Path,
    module: str,
    source: str,
    broken_contract: str,
) -> None:
    _write_contract_config(tmp_path)
    _write_real_tui_topology(tmp_path)
    _write_module(tmp_path, module, source)

    return_code, output = _run_import_linter(tmp_path)

    assert return_code == 1, output
    assert broken_contract in " ".join(output.split())
    assert "Contracts: 4 kept, 1 broken." in output
