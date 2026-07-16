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
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from cadrumo.agent import materialise_marketplace
from dev.packaging.installed_mcp_oracle import run_installed_mcp_oracle
from dev.packaging.installed_tax_oracle import run_installed_tax_oracle
from dev.packaging.python_cohort import load_python_cohort
from dev.packaging.smoke_core import _run, _venv_bin, _venv_python
from dev.packaging.smoke_pip_core import _create_pip_venv
from dev.packaging.smoke_split_install import (
    _build_data_wheels,
    _build_root_wheel,
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
    cohort_dir: Path
    source_commit: str
    artifact_sha256: dict[str, str]
    evidence_path: Path
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


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_evidence(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _extract_source_commit(repo_root: Path, work_dir: Path, source_commit: str) -> Path:
    """Extract one immutable source commit rather than resolving a moving HEAD twice."""
    archive = work_dir / "source-commit.zip"
    extract_root = work_dir / "source-commit"
    _run(
        ["git", "archive", "--format=zip", "-o", str(archive), source_commit],
        cwd=repo_root,
    )
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(extract_root)
    archive.unlink()
    return extract_root


@pytest.fixture(scope="module")
def installed_cohort(tmp_path_factory: pytest.TempPathFactory) -> InstalledCohort:
    """Build HEAD once, install one cohort once, and inspect installed metadata."""
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to build the installed oracle cohort"

    work_dir = tmp_path_factory.mktemp("installed-oracle-cohort")
    supplied_dir = _REPO_ROOT / "var" / "packaging-smoke-cohort" / "python"
    if (supplied_dir / "python-cohort.json").is_file():
        supplied = load_python_cohort(supplied_dir)
        cohort_dir = supplied.directory
        source_commit = supplied.source_commit
        root_wheel = supplied.root_wheel
        data_wheels = supplied.companion_wheels
        artifact_sha256 = {
            "cadrumo": supplied.sha256["cadrumo"],
            "cadrumo-data-manuals": supplied.sha256["cadrumo-data-manuals"],
            "cadrumo-data-official": supplied.sha256["cadrumo-data-official"],
        }
    else:
        source_commit_result = _run(["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT)
        source_commit = source_commit_result.stdout.strip()
        assert len(source_commit) == 40
        build_root = _extract_source_commit(_REPO_ROOT, work_dir, source_commit)
        root_wheel = _build_root_wheel(build_root, work_dir, uv)
        built_data_wheels = _build_data_wheels(build_root, work_dir, uv)
        assert len(built_data_wheels) == 2
        data_wheels = (built_data_wheels[0], built_data_wheels[1])
        cohort_dir = work_dir / "python-cohort"
        cohort_dir.mkdir()
        for artifact in (root_wheel, *data_wheels):
            shutil.copy2(artifact, cohort_dir / artifact.name)
        _run([uv, "build", "--sdist", "--out-dir", str(cohort_dir)], cwd=build_root)
        for project in ("cadrumo_data_manuals", "cadrumo_data_official"):
            _run(
                [
                    uv,
                    "build",
                    "--sdist",
                    "--project",
                    str(build_root / "packaging" / project),
                    "--out-dir",
                    str(cohort_dir),
                ],
                cwd=build_root,
            )
        artifacts = {
            "cadrumo": root_wheel.name,
            "cadrumo-sdist": next(cohort_dir.glob("cadrumo-*.tar.gz")).name,
            "cadrumo-data-manuals": data_wheels[0].name,
            "cadrumo-data-manuals-sdist": next(
                cohort_dir.glob("cadrumo_data_manuals-*.tar.gz"),
            ).name,
            "cadrumo-data-official": data_wheels[1].name,
            "cadrumo-data-official-sdist": next(
                cohort_dir.glob("cadrumo_data_official-*.tar.gz"),
            ).name,
        }
        project_metadata = tomllib.loads(
            (build_root / "pyproject.toml").read_text(encoding="utf-8"),
        )
        version = project_metadata["project"]["version"]
        assert isinstance(version, str)
        _write_evidence(
            cohort_dir / "python-cohort.json",
            {
                "artifacts": artifacts,
                "sha256": {name: _sha256(cohort_dir / filename) for name, filename in artifacts.items()},
                "source_commit": source_commit,
                "version": version,
            },
        )
        supplied = load_python_cohort(cohort_dir)
        root_wheel = supplied.root_wheel
        data_wheels = supplied.companion_wheels
        artifact_sha256 = {
            "cadrumo": supplied.sha256["cadrumo"],
            "cadrumo-data-manuals": supplied.sha256["cadrumo-data-manuals"],
            "cadrumo-data-official": supplied.sha256["cadrumo-data-official"],
        }

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
    evidence_path = (
        _REPO_ROOT / "var" / "distribution-install-readiness" / "installed-cohorts" / source_commit / "evidence.json"
    )
    _write_evidence(
        evidence_path,
        {
            "artifact_sha256": artifact_sha256,
            "source_commit": source_commit,
        },
    )
    return InstalledCohort(
        work_dir=work_dir,
        venv=venv,
        root_wheel=root_wheel,
        data_wheels=data_wheels,
        cli=cli,
        mcp_server=mcp_server,
        cohort_dir=cohort_dir,
        source_commit=source_commit,
        artifact_sha256=artifact_sha256,
        evidence_path=evidence_path,
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
        assert direct_url["archive_info"]["hashes"]["sha256"] == cohort.artifact_sha256[name]

    print(
        "installed-cohort-identity="
        + json.dumps(
            {
                "artifact_sha256": cohort.artifact_sha256,
                "evidence_path": str(cohort.evidence_path),
                "source_commit": cohort.source_commit,
            },
            sort_keys=True,
        ),
    )


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
    expected_cli_sha256 = _text_sha256(str(cohort.cli))
    assert mcp_evidence.invoked_cli_sha256 == expected_cli_sha256
    assert mcp_evidence.invoked_cli_sha256_by_command == {
        "config.profile.create": expected_cli_sha256,
        "modelo.work.calculate": expected_cli_sha256,
        "modelo.work.create": expected_cli_sha256,
        "modelo.work.observations": expected_cli_sha256,
    }
    assert any(call.command_key == "modelo.work.calculate" for call in mcp_evidence.calls)

    _write_evidence(
        cohort.evidence_path,
        {
            "artifact_sha256": cohort.artifact_sha256,
            "cli_oracle": cli_evidence.to_jsonable(),
            "mcp_oracle": mcp_evidence.to_jsonable(),
            "source_commit": cohort.source_commit,
        },
    )
    retained = json.loads(cohort.evidence_path.read_text(encoding="utf-8"))
    assert retained["mcp_oracle"]["invoked_cli_sha256"] == expected_cli_sha256
    assert retained["mcp_oracle"]["invoked_cli_sha256_by_command"] == {
        "config.profile.create": expected_cli_sha256,
        "modelo.work.calculate": expected_cli_sha256,
        "modelo.work.create": expected_cli_sha256,
        "modelo.work.observations": expected_cli_sha256,
    }


def test_marketplace_plugin_executes_the_independently_installed_service(
    installed_cohort: InstalledCohort,
) -> None:
    """The generated marketplace launches the exact installed service cohort."""
    cohort = installed_cohort
    marketplace = cohort.work_dir / "cohort-marketplace"
    manifest = materialise_marketplace(
        marketplace,
        cohort_dir=cohort.cohort_dir,
    )
    plugin_root = marketplace / "plugins" / "cadrumo"
    assert manifest.plugin.version == cohort.metadata["versions"]["cadrumo"]
    assert not (plugin_root / "artifacts").exists()

    mcp = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))
    server = mcp["mcpServers"]["cadrumo"]
    assert server["command"] == "cadrumo-mcp"
    assert server["args"] == []
    assert server["env"]["CADRUMO_MCP_REQUIRED_VERSION"] == manifest.plugin.version
    environment = {
        key: ("" if value == "${user_config.persona}" else "core" if value == "${user_config.surface}" else value)
        for key, value in server["env"].items()
    }
    evidence = run_installed_mcp_oracle(
        cohort.mcp_server,
        server_args=(),
        environment_overrides=environment,
        storage_root=cohort.work_dir / "plugin-mcp-state",
        work_dir=cohort.work_dir / "plugin-outside-checkout",
        timeout_seconds=420.0,
    )
    assert Path(evidence.resolved_executable) == cohort.mcp_server
    assert evidence.target_casilla == "DP200014:00562"
    assert evidence.target_value == "23000.00"
    assert evidence.formula_id == "modelo-200-cuota-integra"

    with pytest.raises(ValueError, match="does not match Python cohort version"):
        materialise_marketplace(
            cohort.work_dir / "wrong-version-marketplace",
            version="999.0.0",
            cohort_dir=cohort.cohort_dir,
        )
    with (cohort.cohort_dir / cohort.data_wheels[1].name).open("ab") as handle:
        handle.write(b"foreign same-name bytes")
    with pytest.raises(ValueError, match="cohort artifact digest mismatch"):
        materialise_marketplace(
            cohort.work_dir / "drifted-cohort-marketplace",
            cohort_dir=cohort.cohort_dir,
        )
