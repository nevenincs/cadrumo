"""Bind the installed CLI and MCP tax oracles to one real wheel cohort.

The test builds one committed three-wheel cohort, installs it once with the
``agent`` extra, records the installed metadata origins and hashes, then runs
both public tax-work oracles from that same environment. This closes the gap
where independently passing probes could accidentally exercise different
virtual environments, rebuilt wheels, or ambient commands.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from dev.packaging.installed_mcp_oracle import run_installed_mcp_oracle
from dev.packaging.installed_tax_oracle import run_installed_tax_oracle
from dev.packaging.smoke_core import _run, _venv_bin, _venv_python
from dev.packaging.smoke_pip_core import _create_pip_venv
from dev.packaging.smoke_split_install import (
    _build_data_wheels,
    _build_root_wheel,
    _head_extract,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DISTRIBUTIONS = (
    "cadrumo",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)
_COHORT_PROBE = """
import json
import sysconfig
from importlib.metadata import distribution
from pathlib import Path

names = ("cadrumo", "cadrumo-data-manuals", "cadrumo-data-official")
distributions = {name: distribution(name) for name in names}
root = distributions["cadrumo"]
print(json.dumps({
    "scripts_dir": str(Path(sysconfig.get_path("scripts")).resolve()),
    "versions": {name: item.version for name, item in distributions.items()},
    "site_roots": {
        name: str(Path(item.locate_file("")).resolve())
        for name, item in distributions.items()
    },
    "direct_urls": {
        name: json.loads(item.read_text("direct_url.json") or "null")
        for name, item in distributions.items()
    },
    "root_requirements": list(root.requires or ()),
    "console_scripts": {
        entry.name: entry.value
        for entry in root.entry_points
        if entry.group == "console_scripts"
    },
}, sort_keys=True))
"""


@dataclass(frozen=True)
class InstalledCohort:
    """One built and installed command/data/agent cohort."""

    work_dir: Path
    venv: Path
    root_wheel: Path
    data_wheels: tuple[Path, Path]
    cli: Path
    mcp_server: Path
    metadata: dict[str, Any]


def _installed_script(venv: Path, name: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return (_venv_bin(venv) / f"{name}{suffix}").resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.fixture(scope="module")
def installed_cohort(tmp_path_factory: pytest.TempPathFactory) -> InstalledCohort:
    """Build HEAD once, install one cohort once, and inspect installed metadata."""
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to build the installed oracle cohort"

    work_dir = tmp_path_factory.mktemp("installed-oracle-cohort")
    build_root = _head_extract(_REPO_ROOT, work_dir)
    root_wheel = _build_root_wheel(build_root, work_dir, uv)
    built_data_wheels = _build_data_wheels(build_root, work_dir, uv)
    assert len(built_data_wheels) == 2
    data_wheels = (built_data_wheels[0], built_data_wheels[1])

    venv = _create_pip_venv(work_dir, f"{sys.version_info.major}.{sys.version_info.minor}")
    _run(
        [
            str(_venv_python(venv)),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            f"{root_wheel.resolve()}[agent]",
            *(str(wheel.resolve()) for wheel in data_wheels),
        ],
        cwd=work_dir,
    )
    _run([str(_venv_python(venv)), "-m", "pip", "check"], cwd=work_dir)
    metadata_result = _run(
        [str(_venv_python(venv)), "-c", _COHORT_PROBE],
        cwd=work_dir,
    )
    metadata = json.loads(metadata_result.stdout)
    assert isinstance(metadata, dict)

    cli = _installed_script(venv, "aeat")
    mcp_server = _installed_script(venv, "cadrumo-mcp")
    assert cli.is_file()
    assert mcp_server.is_file()
    return InstalledCohort(
        work_dir=work_dir,
        venv=venv,
        root_wheel=root_wheel,
        data_wheels=data_wheels,
        cli=cli,
        mcp_server=mcp_server,
        metadata=metadata,
    )


def test_installed_cli_and_mcp_are_one_hashed_cohort(installed_cohort: InstalledCohort) -> None:
    """Both commands and all mandatory distributions have one installed origin."""
    cohort = installed_cohort
    metadata = cohort.metadata
    scripts_dir = Path(metadata["scripts_dir"]).resolve()

    assert cohort.cli.parent == scripts_dir
    assert cohort.mcp_server.parent == scripts_dir
    assert cohort.cli.parent == cohort.mcp_server.parent
    assert len(set(metadata["site_roots"].values())) == 1
    assert len(set(metadata["versions"].values())) == 1

    version = metadata["versions"]["cadrumo"]
    requirements = set(metadata["root_requirements"])
    assert {
        f"cadrumo-data-manuals=={version}",
        f"cadrumo-data-official=={version}",
    } <= requirements
    assert metadata["console_scripts"]["aeat"] == "cadrumo.entrypoints.cli:main"
    assert metadata["console_scripts"]["cadrumo-mcp"] == "cadrumo.entrypoints.mcp:main"

    artifacts = {
        "cadrumo": cohort.root_wheel,
        "cadrumo-data-manuals": cohort.data_wheels[0],
        "cadrumo-data-official": cohort.data_wheels[1],
    }
    assert set(artifacts) == set(_DISTRIBUTIONS)
    for name, artifact in artifacts.items():
        direct_url = metadata["direct_urls"][name]
        assert direct_url["url"] == artifact.resolve().as_uri()
        assert direct_url["archive_info"]["hashes"]["sha256"] == _sha256(artifact)


def test_cli_and_mcp_complete_the_same_grounded_oracle_from_that_cohort(
    installed_cohort: InstalledCohort,
) -> None:
    """One installation completes the direct and protocol tax-work claims."""
    cohort = installed_cohort
    execution_root = cohort.work_dir / "outside-checkout"
    execution_root.mkdir()

    cli_evidence = run_installed_tax_oracle(
        cohort.cli,
        storage_root=cohort.work_dir / "cli-state",
        work_dir=execution_root / "cli",
        timeout_seconds=240.0,
    )
    mcp_evidence = run_installed_mcp_oracle(
        cohort.mcp_server,
        storage_root=cohort.work_dir / "mcp-state",
        work_dir=execution_root / "mcp",
        timeout_seconds=240.0,
    )

    assert Path(cli_evidence.resolved_executable) == cohort.cli
    assert Path(mcp_evidence.resolved_executable) == cohort.mcp_server
    assert (
        Path(cli_evidence.resolved_executable).parent
        == Path(
            mcp_evidence.resolved_executable,
        ).parent
    )
    assert cli_evidence.target_casilla == mcp_evidence.target_casilla
    assert cli_evidence.target_value == mcp_evidence.target_value == "23000.00"
    assert cli_evidence.formula_id == mcp_evidence.formula_id == "modelo-200-cuota-integra"
    assert cli_evidence.legal_refs == mcp_evidence.legal_refs
    assert cli_evidence.source_refs == mcp_evidence.source_refs
    assert cli_evidence.notice_codes == mcp_evidence.notice_codes
    assert any(call.command_key == "modelo.work.calculate" for call in mcp_evidence.calls)
