"""Install the MCPB through its client runtime and require the real tax oracle.

The built ``.mcpb`` bundle must install through the runtime each claimed
MCP-bundle client uses, start its cohort-pinned server, and complete the
grounded Modelo 200 tax-work tool call. The bundle carries no client or
operating-system
compatibility row: every MCP-bundle client provisions the same unpacked
extension through the manifest's declared ``uv`` launcher after the official
``@anthropic-ai/mcpb`` validator accepts it, then speaks the public MCP
protocol to the bundled server.

This integration test drives that exact runtime once against a real product
cohort — official MCPB validation, host-style ``uv`` provisioning into the
bundle-local environment, concurrent server launches, and the real MCP
protocol oracle from :func:`dev.packaging.smoke_mcpb.run_mcpb_smoke` — and
binds the result to the grounded expectation ``DP200014:00562 == 23000.00``
from ``modelo-200-cuota-integra``. There is no mock, stub, patch, or skip: a
missing runtime piece (``uv``, ``npx``, or the official validator) fails
loudly.

The graphical per-client install acceptance — the Claude Desktop UI install and
the Cowork host-loop session — is performed by hand and is not automated here;
this test proves the shared install runtime those clients consume, so a bundle
that cannot install and calculate through that runtime can never pass a
per-client check.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Final

import pytest
from dev.packaging._hashing import sha256_path
from dev.packaging._smoke_common import (
    build_companion_wheels,
    build_sdist,
    build_wheel,
    commit_defined_build_root,
    run_checked,
)
from dev.packaging.python_cohort import load_python_cohort
from dev.packaging.smoke_mcpb import MCPB_CLI_VERSION, run_mcpb_smoke
from dev.packaging.tests._cohort_attestation import (
    add_test_source_archive,
    make_test_command_spec_attestation,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_SUPPLIED_COHORT_ENV: Final[str] = "CADRUMO_MCPB_CLIENT_COHORT_DIR"
_SUPPLIED_COHORT_DIR: Final[Path] = _REPO_ROOT / "var" / "packaging-smoke-cohort" / "python"
_CLIENT_INSTALL_TIMEOUT_SECONDS: Final[float] = 1200.0

# The MCP-bundle clients the product claims. They share one MCPB install
# runtime (the official validator plus the manifest's ``uv`` launcher); this
# test proves that shared runtime, while each client's graphical install is
# checked by hand and is not automated here.
_CLAIMED_MCPB_CLIENTS: Final[tuple[str, ...]] = ("Claude Desktop", "Cowork")

_EXPECTED_TARGET_CASILLA: Final[str] = "DP200014:00562"
_EXPECTED_TARGET_VALUE: Final[str] = "23000.00"
_EXPECTED_FORMULA_ID: Final[str] = "modelo-200-cuota-integra"
_EXPECTED_PYTHON_RUNTIME: Final[str] = ">=3.13,<3.14"


def _write_cohort_manifest(
    cohort_dir: Path,
    *,
    artifacts: dict[str, Path],
    version: str,
) -> None:
    """Retain the six built artifacts under one immutable digest manifest."""
    names: dict[str, str] = {}
    digests: dict[str, str] = {}
    for label, artifact in artifacts.items():
        retained = cohort_dir / artifact.name
        if retained.resolve() != artifact.resolve():
            shutil.copy2(artifact, retained)
        names[label] = retained.name
        digests[label] = sha256_path(retained)
    git = shutil.which("git")
    assert git is not None, "git is required to bind the client-install cohort to a source commit"
    source_commit = subprocess.run(  # noqa: S603 - resolved Git with a fixed repository argv
        [git, "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    add_test_source_archive(cohort_dir, names, digests)
    (cohort_dir / "python-cohort.json").write_text(
        json.dumps(
            {
                "artifacts": names,
                "sha256": digests,
                "source_commit": source_commit,
                "version": version,
                "command_spec_attestation": make_test_command_spec_attestation(
                    cohort_dir, names, source_commit=source_commit
                ),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _build_real_cohort(work: Path) -> Path:
    """Build the six-file canonical cohort from a commit-defined root.

    Mirrors the build test: the cohort the installed client is bound to must
    correspond to a commit, or a peer's uncommitted edit in this shared worktree
    rides into the wheels and the install proof describes bytes matching no
    commit. On a clean checkout the extract is the tree, so CI pays nothing.
    """
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to build the MCPB client-install cohort"
    cohort_dir = work / "cohort"
    cohort_dir.mkdir()
    build_root = commit_defined_build_root(_REPO_ROOT, work)
    root_wheel = build_wheel(_REPO_ROOT, work, uv, build_root=build_root)
    manuals_wheel, official_wheel = build_companion_wheels(work, uv, build_root=build_root)
    root_sdist = build_sdist(work, uv, build_root=build_root)
    companion_sdists = work / "companion-sdists"
    run_checked(
        [uv, "build", "--sdist", "--out-dir", str(companion_sdists)],
        cwd=build_root / "packaging" / "cadrumo_data_manuals",
    )
    run_checked(
        [uv, "build", "--sdist", "--out-dir", str(companion_sdists)],
        cwd=build_root / "packaging" / "cadrumo_data_official",
    )
    manuals_sdist = next(companion_sdists.glob("cadrumo_data_manuals-*.tar.gz"))
    official_sdist = next(companion_sdists.glob("cadrumo_data_official-*.tar.gz"))
    version = tomllib.loads(
        (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"),
    )["project"]["version"]
    assert isinstance(version, str)
    _write_cohort_manifest(
        cohort_dir,
        artifacts={
            "cadrumo": root_wheel,
            "cadrumo-sdist": root_sdist,
            "cadrumo-data-manuals": manuals_wheel,
            "cadrumo-data-manuals-sdist": manuals_sdist,
            "cadrumo-data-official": official_wheel,
            "cadrumo-data-official-sdist": official_sdist,
        },
        version=version,
    )
    return load_python_cohort(cohort_dir).directory


def _resolve_cohort_dir(work: Path) -> Path:
    """Reuse a supplied cohort when offered, otherwise build one from the tree."""
    supplied_env = os.environ.get(_SUPPLIED_COHORT_ENV)
    if supplied_env:
        return load_python_cohort(Path(supplied_env).expanduser()).directory
    if (_SUPPLIED_COHORT_DIR / "python-cohort.json").is_file():
        return load_python_cohort(_SUPPLIED_COHORT_DIR).directory
    return _build_real_cohort(work)


@pytest.fixture(scope="module")
def client_install_evidence(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Install the built MCPB through its client runtime and drive the tax oracle."""
    uv = shutil.which("uv")
    npx = shutil.which("npx")
    assert uv is not None, "uv is required to provision the MCPB the way a client does"
    assert npx is not None, "npx is required to run the official @anthropic-ai/mcpb validator"

    work = tmp_path_factory.mktemp("mcpb-client-install")
    cohort_dir = _resolve_cohort_dir(work)
    evidence_path = run_mcpb_smoke(
        cohort_dir=cohort_dir,
        evidence_dir=work / "evidence",
        uv_executable=Path(uv),
        npx_executable=Path(npx),
        timeout_seconds=_CLIENT_INSTALL_TIMEOUT_SECONDS,
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert isinstance(evidence, dict)
    return evidence


def test_mcpb_client_runtime_completes_the_grounded_tax_oracle(
    client_install_evidence: dict[str, Any],
) -> None:
    """The installed bundle completes the Modelo 200 tax oracle through real MCP."""
    oracle = client_install_evidence["mcp_oracle"]

    assert oracle["target_casilla"] == _EXPECTED_TARGET_CASILLA
    assert oracle["target_value"] == _EXPECTED_TARGET_VALUE
    assert oracle["formula_id"] == _EXPECTED_FORMULA_ID
    assert oracle["server_name"] == "cadrumo"
    assert tuple(oracle["legal_refs"]), "grounded oracle must carry legal references"
    assert tuple(oracle["source_refs"]), "grounded oracle must carry source references"

    calculate_calls = [call for call in oracle["calls"] if call["command_key"] == "modelo.work.calculate"]
    assert calculate_calls, "the oracle must include the real work-calculate tool call"
    assert all(not call["is_error"] for call in oracle["calls"])
    assert oracle["notice_codes"] == ["modelo.work.calculate.plazo_vencido_unassessed_preview"]


def test_mcpb_launches_from_the_unpacked_extension_through_the_manifest_command(
    client_install_evidence: dict[str, Any],
) -> None:
    """The client runtime launches the manifest command adapted to the extracted dir."""
    launch = client_install_evidence["resolved_launch"]
    args = launch["args"]

    assert client_install_evidence["official_validator"] == f"@anthropic-ai/mcpb@{MCPB_CLI_VERSION}"
    # ``uv run --no-project`` runs the bootstrap with no per-session project
    # resolution; the bootstrap provisions once and direct-execs thereafter.
    assert args[0] == "run"
    assert args[1] == "--no-project"
    assert args[2] == "--directory"
    assert args[4] == "src/server.py"

    # The manifest's ``${__dirname}`` placeholder resolves to the unpacked
    # extension the client provisioned, never to the source checkout.
    extension_dir = Path(args[3]).resolve()
    assert extension_dir.is_dir()
    assert extension_dir != _REPO_ROOT
    assert _REPO_ROOT not in extension_dir.parents
    assert (extension_dir / "manifest.json").is_file()
    assert (extension_dir / "pyproject.toml").is_file()
    assert (extension_dir / "src" / "server.py").is_file()
    assert (extension_dir / "src" / "_serve.py").is_file()

    proof = client_install_evidence["proof"]
    assert proof["archive_construction"] == "passed"
    assert proof["first_launch_provisioning"] == "passed into bundle .venv"
    assert proof["second_launch_direct_exec"] == "passed with no re-resolution"
    assert proof["concurrent_server_launches"] == "passed"
    # The provisioned interpreter was asserted against the bundle's pinned
    # constraint closure before the tax oracle ran, so a lock-drifted install
    # can never mint client-install evidence.
    assert proof["constraint_effect"] == "passed against the provisioned bundle interpreter"
    assert proof["bundle_runtime_oracle"] == "passed outside a desktop client"


def test_installed_bundle_binds_the_exact_client_install_cohort(
    client_install_evidence: dict[str, Any],
) -> None:
    """The installed bundle is the exact retained cohort, not a rebuild."""
    bundle_sha256 = client_install_evidence["bundle_sha256"]
    cohort = client_install_evidence["cohort"]
    manifest_env = client_install_evidence["manifest"]["server"]["mcp_config"]["env"]
    stamped_sha256 = json.loads(manifest_env["CADRUMO_MCP_COHORT_SHA256"])

    assert len(bundle_sha256) == 64
    assert client_install_evidence["manifest"]["version"] == cohort["version"]
    assert manifest_env["CADRUMO_MCP_REQUIRED_VERSION"] == cohort["version"]
    assert stamped_sha256 == {
        "cadrumo": cohort["sha256"]["cadrumo"],
        "cadrumo-data-manuals": cohort["sha256"]["cadrumo-data-manuals"],
        "cadrumo-data-official": cohort["sha256"]["cadrumo-data-official"],
    }
    assert len(cohort["source_commit"]) == 40


def test_mcpb_advertises_no_unexecuted_client_or_platform_support(
    client_install_evidence: dict[str, Any],
) -> None:
    """The bundle claims only the executed Python runtime, no unproven client rows."""
    manifest = client_install_evidence["manifest"]

    assert manifest["compatibility"] == {"runtimes": {"python": _EXPECTED_PYTHON_RUNTIME}}
    # The MCPB never advertises an operating-system or client support surface it
    # did not execute; the claimed clients below share the one proven runtime.
    assert "platforms" not in manifest["compatibility"]
    assert "clients" not in manifest
    assert _CLAIMED_MCPB_CLIENTS
