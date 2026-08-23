"""Bind the installed CLI and MCP tax oracles to one real wheel cohort.

The test builds one committed three-wheel cohort plus the sibling
``cadrumo-harness`` wheel that now carries the MCP server, installs them once
into a single environment, records the installed metadata origins and hashes,
then runs both public tax-work oracles from that same environment. This closes
the gap where independently passing probes could accidentally exercise
different virtual environments, rebuilt wheels, or ambient commands.

The ``cadrumo-mcp`` console script is a ``cadrumo-harness`` entry point: the
``cadrumo`` wheel is a pure CLI and ships no agent-harness runtime, so nothing
here may reach for an extra on the root distribution to obtain the server.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, cast

import pytest
from cadrumo_harness import materialise_marketplace

from cadrumo.core import iter_directory, scan_directory
from dev._paths import REPO_ROOT

from .._hashing import sha256_path
from .._smoke_common import (
    build_companion_wheels,
    build_harness_wheel,
    build_wheel,
    create_pip_venv,
    extract_source_commit,
    run_checked,
    venv_bin_dir,
    venv_python_path,
)
from ..installed_mcp_oracle import run_installed_mcp_oracle
from ..installed_tax_oracle import run_installed_tax_oracle
from ..python_cohort import PythonCohort, _attest_installed_command_specs, load_python_cohort

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_REPO_ROOT = REPO_ROOT
_DISTRIBUTIONS = (
    "cadrumo",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)
#: The sibling agent-harness distribution. It is versioned independently of the
#: command/data cohort, so it is probed on its own rather than folded into the
#: one-version cohort assertions below.
_HARNESS_DISTRIBUTION = "cadrumo-harness"
_HARNESS_WHEEL_GLOB = "cadrumo_harness-*.whl"
_REQUIREMENT_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_COHORT_PROBE = """
import json
import sysconfig
from importlib.metadata import distribution
from pathlib import Path

names = ("cadrumo", "cadrumo-data-manuals", "cadrumo-data-official")
distributions = {name: distribution(name) for name in names}
root = distributions["cadrumo"]
harness = distribution("cadrumo-harness")
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
    "harness_version": harness.version,
    "harness_site_root": str(Path(harness.locate_file("")).resolve()),
    "harness_direct_url": json.loads(harness.read_text("direct_url.json") or "null"),
    "harness_requirements": list(harness.requires or ()),
    "harness_console_scripts": {
        entry.name: entry.value
        for entry in harness.entry_points
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
    harness_wheel: Path
    data_wheels: tuple[Path, Path]
    cli: Path
    mcp_server: Path
    cohort_dir: Path
    source_commit: str
    artifact_sha256: dict[str, str]
    evidence_path: Path
    metadata: dict[str, Any]
    python_cohort: PythonCohort


def _installed_script(venv: Path, name: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return (venv_bin_dir(venv) / f"{name}{suffix}").resolve()


def _requirement_name(requirement: str) -> str:
    """Return the distribution name of one core-metadata ``Requires-Dist`` line."""
    match = _REQUIREMENT_NAME_PATTERN.match(requirement)
    return match.group(0).lower().replace("_", "-") if match else ""


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_evidence(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
        # The harness is not a cohort member, so a supplied cohort directory may
        # or may not carry its wheel. Prefer the supplied one; otherwise build it
        # from the SAME source commit the supplied cohort was built from, never
        # from the shared working tree.
        prebuilt_harness = scan_directory(cohort_dir, pattern=_HARNESS_WHEEL_GLOB)
        if len(prebuilt_harness) == 1:
            harness_wheel = prebuilt_harness[0]
        else:
            harness_wheel = build_harness_wheel(
                work_dir,
                uv,
                build_root=extract_source_commit(_REPO_ROOT, work_dir, source_commit),
            )
    else:
        source_commit_result = run_checked(["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT)
        source_commit = source_commit_result.stdout.strip()
        assert len(source_commit) == 40
        build_root = extract_source_commit(_REPO_ROOT, work_dir, source_commit)
        root_wheel = build_wheel(_REPO_ROOT, work_dir, uv, build_root=build_root)
        harness_wheel = build_harness_wheel(work_dir, uv, build_root=build_root)
        built_data_wheels = build_companion_wheels(work_dir, uv, build_root=build_root)
        assert len(built_data_wheels) == 2
        data_wheels = (built_data_wheels[0], built_data_wheels[1])
        cohort_dir = work_dir / "python-cohort"
        cohort_dir.mkdir()
        for artifact in (root_wheel, *data_wheels):
            shutil.copy2(artifact, cohort_dir / artifact.name)
        run_checked([uv, "build", "--sdist", "--out-dir", str(cohort_dir)], cwd=build_root)
        for project in ("cadrumo_data_manuals", "cadrumo_data_official"):
            run_checked(
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
            "cadrumo-sdist": next(iter_directory(cohort_dir, pattern="cadrumo-*.tar.gz")).name,
            "cadrumo-data-manuals": data_wheels[0].name,
            "cadrumo-data-manuals-sdist": next(
                iter_directory(cohort_dir, pattern="cadrumo_data_manuals-*.tar.gz"),
            ).name,
            "cadrumo-data-official": data_wheels[1].name,
            "cadrumo-data-official-sdist": next(
                iter_directory(cohort_dir, pattern="cadrumo_data_official-*.tar.gz"),
            ).name,
        }
        source_archive = cohort_dir / f"cadrumo-source-{source_commit}.zip"
        with zipfile.ZipFile(source_archive, "w") as archive:
            archive.writestr("pyproject.toml", "[project]\nname='cadrumo'\n")
        artifacts["source-archive"] = source_archive.name
        project_metadata = tomllib.loads(
            (build_root / "pyproject.toml").read_text(encoding="utf-8"),
        )
        version = project_metadata["project"]["version"]
        assert isinstance(version, str)
        _write_evidence(
            cohort_dir / "python-cohort.json",
            {
                "artifacts": artifacts,
                "sha256": {name: sha256_path(cohort_dir / filename) for name, filename in artifacts.items()},
                "source_commit": source_commit,
                "version": version,
                "command_spec_attestation": _attest_installed_command_specs(
                    root_wheel,
                    cohort_dir / artifacts["cadrumo-sdist"],
                    source_commit,
                    source_archive,
                    work_root=work_dir,
                    uv=uv,
                ),
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

    venv = create_pip_venv(work_dir, f"{sys.version_info.major}.{sys.version_info.minor}")
    run_checked(
        [
            str(venv_python_path(venv)),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            str(root_wheel.resolve()),
            str(harness_wheel.resolve()),
            *(str(wheel.resolve()) for wheel in data_wheels),
        ],
        cwd=work_dir,
    )
    run_checked([str(venv_python_path(venv)), "-m", "pip", "check"], cwd=work_dir)
    metadata_result = run_checked(
        [str(venv_python_path(venv)), "-c", _COHORT_PROBE],
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
        harness_wheel=harness_wheel,
        data_wheels=data_wheels,
        cli=cli,
        mcp_server=mcp_server,
        cohort_dir=cohort_dir,
        source_commit=source_commit,
        artifact_sha256=artifact_sha256,
        evidence_path=evidence_path,
        metadata=metadata,
        python_cohort=supplied,
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
    # The split is load-bearing, not cosmetic: the command-bearing wheel is a
    # pure CLI, so the server script must come from the harness distribution and
    # must NOT also be declared by the root one.
    assert "cadrumo-mcp" not in metadata["console_scripts"]
    assert metadata["harness_console_scripts"]["cadrumo-mcp"] == "cadrumo_harness.mcp:main"
    assert Path(metadata["harness_site_root"]).resolve() == Path(metadata["site_roots"]["cadrumo"]).resolve()
    assert metadata["harness_direct_url"]["url"] == cohort.harness_wheel.resolve().as_uri()
    # Dependency direction: the harness consumes the CLI distribution.
    assert any(_requirement_name(requirement) == "cadrumo" for requirement in metadata["harness_requirements"])

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
        cohort_source_commit=cohort.source_commit,
        cohort_manifest_sha256=sha256_path(cohort.evidence_path),
        cohort_root_wheel_sha256=cohort.artifact_sha256,
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


def _as_plugin_cohort(cohort: PythonCohort) -> Any:
    """Adapt a PythonCohort to the marketplace materialiser's protocol.

    PythonCohort satisfies the runtime protocol exactly; the materialiser
    annotates its mutable digest mapping as a read-only Mapping protocol,
    which static structural typing cannot prove for a frozen dataclass
    (same documented cast as the release-cohort builder).
    """
    return cast("Any", cohort)


def test_marketplace_plugin_embeds_and_executes_the_exact_built_cohort(
    installed_cohort: InstalledCohort,
) -> None:
    """The generated marketplace launches its copied three-wheel cohort via uvx."""
    cohort = installed_cohort
    marketplace = cohort.work_dir / "cohort-marketplace"
    manifest = materialise_marketplace(
        marketplace,
        cohort=_as_plugin_cohort(cohort.python_cohort),
    )
    plugin_root = marketplace / "plugins" / "cadrumo"
    assert manifest.plugin.version == cohort.metadata["versions"]["cadrumo"]
    embedded = plugin_root / "artifacts" / "python"
    retained = json.loads(
        (embedded / "plugin-python-cohort.json").read_text(encoding="utf-8"),
    )
    assert retained["source_commit"] == cohort.source_commit
    assert retained["sha256"] == cohort.artifact_sha256
    for distribution, filename in retained["artifacts"].items():
        assert sha256_path(embedded / filename) == cohort.artifact_sha256[distribution]

    mcp = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))
    server = mcp["mcpServers"]["cadrumo"]
    assert server["command"] == "uvx"
    assert [argument for argument in server["args"] if argument == "--with"] == [
        "--with",
        "--with",
    ]
    for wheel in (
        cohort.root_wheel,
        cohort.data_wheels[0],
        cohort.data_wheels[1],
    ):
        assert any(wheel.name in argument for argument in server["args"])
    assert server["env"]["CADRUMO_MCP_REQUIRED_VERSION"] == manifest.plugin.version
    uvx = shutil.which("uvx")
    assert uvx is not None
    resolved_args = tuple(argument.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root)) for argument in server["args"])
    environment = {
        key: ("" if value == "${user_config.persona}" else "core" if value == "${user_config.surface}" else value)
        for key, value in server["env"].items()
    }
    evidence = run_installed_mcp_oracle(
        Path(uvx),
        server_args=resolved_args,
        environment_overrides=environment,
        storage_root=cohort.work_dir / "plugin-mcp-state",
        work_dir=cohort.work_dir / "plugin-outside-checkout",
        timeout_seconds=420.0,
    )
    assert Path(evidence.resolved_executable) == Path(uvx).resolve()
    assert evidence.target_casilla == "DP200014:00562"
    assert evidence.target_value == "23000.00"
    assert evidence.formula_id == "modelo-200-cuota-integra"

    with pytest.raises(ValueError, match="does not match Python cohort version"):
        materialise_marketplace(
            cohort.work_dir / "wrong-version-marketplace",
            version="999.0.0",
            cohort=_as_plugin_cohort(cohort.python_cohort),
        )
    # Tamper a COPY of the cohort, never the shared supplied directory: this
    # probe previously appended the drift bytes to the real
    # ``var/packaging-smoke-cohort`` member in place and left it corrupted,
    # which poisoned every later same-cohort lane in the campaign (the Docker
    # lane's digest gate refused the mutated ``cadrumo-data-official`` wheel).
    drift_dir = cohort.work_dir / "drift-probe-cohort"
    shutil.copytree(cohort.cohort_dir, drift_dir)
    drift_cohort = load_python_cohort(drift_dir)
    with (drift_dir / cohort.data_wheels[1].name).open("ab") as handle:
        handle.write(b"foreign same-name bytes")
    with pytest.raises(ValueError, match="cohort artifact digest mismatch"):
        materialise_marketplace(
            cohort.work_dir / "drifted-cohort-marketplace",
            cohort=_as_plugin_cohort(drift_cohort),
        )


def test_real_client_emission_cli_mints_a_sanctioned_record(
    installed_cohort: InstalledCohort,
    tmp_path: Path,
) -> None:
    """The operator real-client emission hook mints a valid claude-* record.

    Drives dev.packaging.emit_real_client_evidence end to end: a synthetic release
    cohort, the operator's captured protocol_oracle + real client session, and a
    REAL owned launch of the installed cohort server. The produced record must
    validate through the tamper-evident schema, be client-bound to the real
    Claude client, and retain the real client session as its real-client proof.
    """
    from datetime import UTC, datetime

    from .. import emit_real_client_evidence
    from ..cohort_manifest import (
        REQUIRED_ARTIFACT_KINDS,
        BuildIdentity,
        SourceIdentity,
        create_manifest,
        write_manifest,
    )
    from ..evidence import DistributionEvidence, EvidenceStatus

    cohort_dir = tmp_path / "release-cohort"
    cohort_dir.mkdir()
    artifacts = []
    for index, (name, kind) in enumerate(sorted(REQUIRED_ARTIFACT_KINDS.items())):
        artifact = cohort_dir / "artifacts" / f"{name}.bin"
        artifact.parent.mkdir(exist_ok=True)
        artifact.write_bytes(f"{index}:{name}\n".encode())
        artifacts.append((name, kind, artifact))
    manifest = create_manifest(
        root=cohort_dir,
        version="0.2.1",
        source=SourceIdentity(commit="c" * 40, tag="v0.2.1"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        builder=BuildIdentity(
            implementation="dev.packaging.release_cohort",
            format_version=1,
            python=sys.version.split()[0],
            uv="0.11.29",
            platform=sys.platform,
            architecture="test",
            build_constraints_sha256="d" * 64,
        ),
        artifacts=artifacts,
    )
    write_manifest(cohort_dir, manifest)

    protocol_oracle = tmp_path / "protocol-oracle.json"
    protocol_oracle.write_text(
        json.dumps(
            {
                "requested_executable": str(installed_cohort.mcp_server),
                "resolved_executable": str(installed_cohort.mcp_server),
                "server_name": "cadrumo",
                "storage_root": "state",
                "work_unit_id": "f" * 64,
                "calculation_revision_id": "a" * 64,
                "observations_resource": f"cadrumo://observations/{'a' * 64}",
                "target_casilla": "DP200014:00562",
                "target_value": "23000.00",
                "formula_id": "modelo-200-cuota-integra",
                "legal_refs": ["ley-27-2014:art-29"],
                "source_refs": ["aeat-modelo-200-manual-2024"],
                "notice_codes": ["modelo.work.calculate.plazo_vencido_unassessed_preview"],
                "advertised_tools": ["cadrumo_modelo_work_calculate"],
                "calls": [
                    {
                        "tool_name": "cadrumo_modelo_work_calculate",
                        "command_key": "modelo.work.calculate",
                        "duration_seconds": 0.5,
                        "is_error": False,
                        "status": "warning",
                    }
                ],
                "invoked_cli_sha256": "0" * 64,
                "invoked_cli_sha256_by_command": {"modelo.work.calculate": "0" * 64},
                "checkout_imports_removed": True,
                "ambient_product_executables_removed": True,
            }
        ),
        encoding="utf-8",
    )
    session = tmp_path / "session.json"
    session.write_text(
        json.dumps({"connected": True, "status": "passed", "tool_called": "cadrumo_modelo_work_calculate"}),
        encoding="utf-8",
    )
    evidence_dir = tmp_path / "distribution-install-readiness"

    exit_code = emit_real_client_evidence.main(
        [
            "--row-id",
            "claude-desktop-mcpb",
            "--release-cohort-dir",
            str(cohort_dir),
            "--protocol-oracle",
            str(protocol_oracle),
            "--real-client-session",
            str(session),
            "--server",
            str(installed_cohort.mcp_server),
            "--client-name",
            "claude-desktop",
            "--client-version",
            "1.22209",
            "--client-executable",
            str(installed_cohort.mcp_server),
            "--acquisition-source",
            "operator-in-app-capture",
            "--destination-kind",
            "claude-desktop-mcpb",
            "--destination-locator",
            "claude-desktop",
            "--launch-work-dir",
            str(tmp_path / "launch"),
            "--distribution-evidence-dir",
            str(evidence_dir),
        ],
    )

    assert exit_code == 0
    records = scan_directory(evidence_dir, pattern="claude-desktop-mcpb-*.json")
    assert len(records) == 1
    record = DistributionEvidence.model_validate_json(records[0].read_text(encoding="utf-8"))
    assert record.row_id == "claude-desktop-mcpb"
    assert record.result.status is EvidenceStatus.PASSED
    assert record.client is not None
    assert record.client.name == "claude-desktop"
    assert record.commands[0].exit_status == 0
    assert "real_client_session" in record.result.observations


def test_owned_server_launch_capture_is_a_clean_real_subprocess(installed_cohort: InstalledCohort) -> None:
    """The A-client launch capture spawns the real server and it exits 0 on stdin EOF.

    Proves the option-A pure-client command transcript is a genuinely-owned
    subprocess: real argv, a real ``initialize`` handshake identifying the server
    as ``cadrumo``, and a clean exit (a killed server would be non-zero and could
    never sit in a passing distribution-evidence record).
    """
    from .._acquire_common import capture_owned_server_launch
    from ..installed_mcp_oracle import isolated_mcp_environment

    work = installed_cohort.work_dir / "owned-launch-capture"
    work.mkdir()
    environment = isolated_mcp_environment(work / "state")
    transcript = capture_owned_server_launch(
        server=installed_cohort.mcp_server,
        env=environment,
        cwd=work,
        timeout_seconds=180.0,
    )
    assert Path(transcript.argv[0]) == installed_cohort.mcp_server
    assert transcript.exit_status == 0
    assert transcript.relevant_output == ("initialize serverInfo.name=cadrumo",)
    assert transcript.completed_at >= transcript.started_at


def _retired_state_environment(base: Path) -> dict[str, str]:
    """A per-OS platform-data root whose retired ``aeat`` state triggers the refusal.

    Mirrors the ``smoke_mcpb`` hostile-platform fixture: the resolver refuses on
    the retired directory's existence alone, and refusal fires only in INSTALLED
    run mode - which this file's wheel-installed cohort guarantees, unlike an
    editable checkout whose resolver never inspects the platform data dir.
    """
    environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}
    hostile_root = base / "platform-data-with-retired-state"
    if sys.platform == "win32":
        former_product_root = hostile_root / "aeat"
        environment["LOCALAPPDATA"] = str(hostile_root)
    elif sys.platform == "darwin":
        hostile_home = base / "home-with-retired-state"
        former_product_root = hostile_home / "Library" / "Application Support" / "aeat"
        environment["HOME"] = str(hostile_home)
    else:
        former_product_root = hostile_root / "aeat"
        environment["XDG_DATA_HOME"] = str(hostile_root)
    former_product_root.mkdir(parents=True)
    (former_product_root / "custody-marker.bin").write_bytes(b"retired-aeat-state-must-remain")
    return environment


def _read_mcp_response(stdout: IO[str], target_id: int) -> dict[str, Any]:
    while True:
        line = stdout.readline()
        if not line:
            raise AssertionError(f"server closed stdout before answering request id {target_id}")
        stripped = line.strip()
        if not stripped:
            continue
        message = json.loads(stripped)
        if isinstance(message, dict) and message.get("id") == target_id:
            return message


def test_installed_mcp_server_serves_when_storage_root_refuses(installed_cohort: InstalledCohort) -> None:
    """The installed server completes initialize/tools-list on a retired-state machine.

    Storage-root resolution on a machine carrying retired former-product state
    raises the refusal; that must surface on the tool calls that need storage,
    never kill the server pre-protocol. This drives the REAL installed
    ``cadrumo-mcp`` console script over stdio with a fabricated retired-state
    platform root and no ``CADRUMO_*`` overrides - the environment a real
    client on an upgrader's machine provides. It pins the startup chain that
    died four separate ways during the distribution campaign: import-time
    registry settings, the schema-build config subtree, the adapter module
    constants, and the eager telemetry-directory resolution.
    """
    cohort = installed_cohort
    environment = _retired_state_environment(cohort.work_dir / "storage-root-refusal")
    process = subprocess.Popen(  # noqa: S603 - the executable is the cohort's own installed console script
        [str(cohort.mcp_server)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        text=True,
        encoding="utf-8",
    )
    watchdog = threading.Timer(300.0, process.kill)
    watchdog.start()
    try:
        assert process.stdin is not None
        assert process.stdout is not None
        initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "storage-root-regression", "version": "0"},
            },
        }
        process.stdin.write(json.dumps(initialize_request) + "\n")
        process.stdin.flush()
        initialize = _read_mcp_response(process.stdout, 1)
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n")
        process.stdin.flush()
        tools = _read_mcp_response(process.stdout, 2)
    finally:
        watchdog.cancel()
        process.kill()
        stderr_text = process.stderr.read() if process.stderr is not None else ""
    assert initialize["result"]["serverInfo"]["name"] == "cadrumo"
    assert len(tools["result"]["tools"]) > 0
    # The degradation is visible, never silent: the startup note names the
    # storage-root refusal on stderr, which the client's MCP log captures.
    assert "serving without telemetry" in stderr_text
