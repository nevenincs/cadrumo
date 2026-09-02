"""Bind the installed CLI and MCP tax oracles to one real wheel cohort.

The test builds one closed-world cohort including the exact
``cadrumo-harness`` wheel that carries the MCP server, installs it once
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
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, cast

import pytest

from ..._paths import REPO_ROOT
from .._hashing import sha256_path
from .._smoke_common import (
    create_pip_venv,
    run_checked,
    venv_bin_dir,
    venv_python_path,
)
from ..installed_mcp_oracle import run_installed_mcp_oracle
from ..installed_tax_oracle import run_installed_tax_oracle
from ..python_cohort import PythonCohort, build_python_cohort

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_REPO_ROOT = REPO_ROOT
_DISTRIBUTIONS = (
    "cadrumo",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)
#: The independently versioned harness cohort member is probed separately from
#: the root/data members' shared-version assertions below.
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


def _legacy_cohort_fallbacks(source: str) -> tuple[str, ...]:
    forbidden = (
        "var/packaging-smoke-cohort",
        "packaging/cadrumo_harness",
        "_attest_installed_command_specs",
    )
    normalized = source.replace("\\", "/")
    return tuple(token for token in forbidden if token in normalized)


def test_installed_oracle_has_no_prebuilt_or_manual_cohort_fallback() -> None:
    """A pre-existing var cohort cannot bypass the canonical clean cohort builder."""
    assert _legacy_cohort_fallbacks('root = "var/packaging-smoke-cohort"')
    assert _legacy_cohort_fallbacks(inspect.getsource(installed_cohort)) == ()


@pytest.fixture(scope="module")
def installed_cohort(tmp_path_factory: pytest.TempPathFactory) -> InstalledCohort:
    """Build HEAD once, install one cohort once, and inspect installed metadata."""
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to build the installed oracle cohort"

    work_dir = tmp_path_factory.mktemp("installed-oracle-cohort")
    clean_repo = work_dir / "clean-repository"
    run_checked(
        ["git", "clone", "--local", "--no-hardlinks", str(_REPO_ROOT), str(clean_repo)],
        cwd=work_dir,
    )
    cohort_dir = work_dir / "python-cohort"
    supplied = build_python_cohort(clean_repo, cohort_dir)
    source_commit = supplied.source_commit
    root_wheel = supplied.root_wheel
    harness_wheel = supplied.harness_wheel
    data_wheels = supplied.companion_wheels
    artifact_sha256 = dict(supplied.sha256)

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
    assert metadata["console_scripts"]["aeat"] == "cadrumo.entrypoints._cli_main:main"
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
        cohort_root_wheel_sha256=cohort.artifact_sha256["cadrumo"],
        timeout_seconds=240.0,
    )
    mcp_evidence = run_installed_mcp_oracle(
        cohort.mcp_server,
        storage_root=cohort.work_dir / "mcp-state",
        work_dir=execution_root / "mcp",
        cohort_source_commit=cohort.source_commit,
        cohort_manifest_sha256=sha256_path(cohort.python_cohort.manifest),
        cohort_root_wheel_sha256=cohort.artifact_sha256["cadrumo"],
        cohort_harness_wheel_sha256=cohort.artifact_sha256["cadrumo-harness"],
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
