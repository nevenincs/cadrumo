"""Real-behavior tests for the flat distribution-evidence emitter.

These tests build a genuine release cohort on disk, capture real subprocess
output for the installed-CLI command transcripts, and drive the emitter end to
end. No mocks: the oracle evidence dataclasses are populated with real captured
values, and the produced record is validated by the tamper-evident
:class:`~dev.packaging.evidence.DistributionEvidence` schema itself.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dev.packaging.cohort_manifest import (
    REQUIRED_ARTIFACT_KINDS,
    BuildIdentity,
    LoadedReleaseCohort,
    SourceIdentity,
    create_manifest,
    load_release_cohort,
    write_manifest,
)
from dev.packaging.distribution_evidence_emit import (
    build_installed_oracle_evidence,
    emit_installed_oracle_evidence,
    main,
)
from dev.packaging.evidence import (
    AcquisitionIdentity,
    DestinationIdentity,
    DistributionEvidence,
    EvidenceStatus,
)
from dev.packaging.installed_mcp_oracle import InstalledMcpEvidence, McpCallEvidence
from dev.packaging.installed_tax_oracle import CommandEvidence, InstalledTaxEvidence

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TARGET_CASILLA = "DP200014:00562"
_TARGET_VALUE = "23000.00"
_FORMULA = "modelo-200-cuota-integra"
_LEGAL_REFS = ("ley-27-2014:art-29",)
_SOURCE_REFS = ("aeat-modelo-200-manual-2024",)
_NOTICE = ("modelo.work.calculate.plazo_vencido_unassessed_preview",)
_REVISION = "a" * 64


def _release_cohort(root: Path) -> LoadedReleaseCohort:
    """Materialise a genuine release cohort with every required artifact kind."""
    root.mkdir()
    artifacts = []
    for index, (name, kind) in enumerate(sorted(REQUIRED_ARTIFACT_KINDS.items())):
        path = root / "artifacts" / f"{name}.bin"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(f"{index}:{name}\n".encode())
        artifacts.append((name, kind, path))
    manifest = create_manifest(
        root=root,
        version="0.2.1",
        source=SourceIdentity(commit="c" * 40, tag="v0.2.1"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        builder=BuildIdentity(
            implementation="dev.packaging.release_cohort",
            format_version=1,
            python=platform.python_version(),
            uv="0.11.29",
            platform=platform.system(),
            architecture=platform.machine(),
            build_constraints_sha256="d" * 64,
        ),
        artifacts=artifacts,
    )
    write_manifest(root, manifest)
    return load_release_cohort(root)


def _captured_command(argv: tuple[str, ...], cwd: Path) -> CommandEvidence:
    """Run a real subprocess and retain it as enriched command evidence."""
    started_at = datetime.now(UTC)
    completed = subprocess.run(  # noqa: S603 - sys.executable is the trusted current interpreter
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    completed_at = datetime.now(UTC)
    return CommandEvidence(
        argv=argv,
        duration_seconds=round((completed_at - started_at).total_seconds(), 3),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat(),
        cwd=str(cwd),
    )


def _tax_evidence(cwd: Path) -> InstalledTaxEvidence:
    """Build installed-CLI oracle evidence from real captured subprocess output."""
    version = _captured_command((sys.executable, "--version"), cwd)
    calculate = _captured_command(
        (sys.executable, "-c", f"print('{_TARGET_CASILLA}={_TARGET_VALUE}')"),
        cwd,
    )
    return InstalledTaxEvidence(
        requested_executable=sys.executable,
        resolved_executable=sys.executable,
        version_output=version.stdout.strip(),
        storage_root=str(cwd / "state"),
        work_unit_id="e" * 64,
        calculation_revision_id=_REVISION,
        target_casilla=_TARGET_CASILLA,
        target_value=_TARGET_VALUE,
        formula_id=_FORMULA,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        notice_codes=_NOTICE,
        commands=(version, calculate),
    )


def _mcp_evidence() -> InstalledMcpEvidence:
    """Build installed-MCP oracle evidence with a real cadrumo-mcp exe stand-in."""
    return InstalledMcpEvidence(
        requested_executable=sys.executable,
        resolved_executable=sys.executable,
        server_name="cadrumo",
        storage_root="mcp-state",
        work_unit_id="f" * 64,
        calculation_revision_id=_REVISION,
        observations_resource=f"cadrumo://observations/{_REVISION}",
        target_casilla=_TARGET_CASILLA,
        target_value=_TARGET_VALUE,
        formula_id=_FORMULA,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        notice_codes=_NOTICE,
        advertised_tools=("cadrumo_modelo_work_calculate", "execute"),
        calls=(
            McpCallEvidence(
                tool_name="cadrumo_modelo_work_calculate",
                command_key="modelo.work.calculate",
                duration_seconds=0.01,
                is_error=False,
                status="warning",
            ),
        ),
        invoked_cli_sha256="0" * 64,
        invoked_cli_sha256_by_command={"modelo.work.calculate": "0" * 64},
    )


def _acquisition() -> AcquisitionIdentity:
    return AcquisitionIdentity(mechanism="pip", source="https://pypi.org/simple")


def _destination(cohort: LoadedReleaseCohort) -> DestinationIdentity:
    return DestinationIdentity(
        kind="pypi-index-install",
        locator="venv",
        version=cohort.manifest.version,
    )


def test_build_binds_cohort_and_retains_both_transports(tmp_path: Path) -> None:
    """The record binds the exact cohort and carries CLI transcripts + MCP proof."""
    cohort = _release_cohort(tmp_path / "cohort")
    tax = _tax_evidence(tmp_path)
    mcp = _mcp_evidence()

    evidence = build_installed_oracle_evidence(
        row_id="python-windows-x86-64",
        cohort=cohort,
        tax_evidence=tax,
        mcp_evidence=mcp,
        acquisition=_acquisition(),
        destination=_destination(cohort),
    )

    assert evidence.row_id == "python-windows-x86-64"
    assert evidence.result.status is EvidenceStatus.PASSED
    assert evidence.cohort.cohort_id == cohort.manifest.cohort_id
    assert evidence.destination.version == cohort.manifest.version
    # Every captured CLI command became one transcript.
    assert len(evidence.commands) == len(tax.commands)
    assert all(transcript.exit_status == 0 for transcript in evidence.commands)
    # Both installed executables are attested with a real on-disk digest.
    exe_names = {exe.name for exe in evidence.isolation.installed_executables}
    assert exe_names == {"aeat", "cadrumo-mcp"}
    assert all(len(exe.sha256) == 64 for exe in evidence.isolation.installed_executables)
    # The MCP protocol proof is retained in observations, not fabricated as a command.
    mcp_oracle = evidence.result.observations["mcp_oracle"]
    cli_oracle = evidence.result.observations["cli_oracle"]
    assert isinstance(mcp_oracle, dict)
    assert isinstance(cli_oracle, dict)
    assert mcp_oracle["target_value"] == _TARGET_VALUE
    assert cli_oracle["target_value"] == _TARGET_VALUE


def test_emit_writes_a_flat_record_both_gates_can_read(tmp_path: Path) -> None:
    """The record lands flat as {row_id}-{evidence_id}.json and re-validates."""
    cohort = _release_cohort(tmp_path / "cohort")
    evidence_dir = tmp_path / "distribution-install-readiness"

    path = emit_installed_oracle_evidence(
        directory=evidence_dir,
        row_id="python-linux-x86-64",
        cohort=cohort,
        tax_evidence=_tax_evidence(tmp_path),
        mcp_evidence=_mcp_evidence(),
        acquisition=_acquisition(),
        destination=_destination(cohort),
    )

    assert path.parent == evidence_dir.resolve()
    assert path.name.startswith("python-linux-x86-64-")
    # The flat glob both gates use finds exactly this record.
    flat = sorted(evidence_dir.glob("*.json"))
    assert flat == [path]
    # It re-validates through the tamper-evident schema, PASSED, correct row.
    reloaded = DistributionEvidence.model_validate_json(path.read_text(encoding="utf-8"))
    assert reloaded.row_id == "python-linux-x86-64"
    assert reloaded.result.status is EvidenceStatus.PASSED


def test_cli_emits_from_oracle_json_a_lane_already_produced(tmp_path: Path) -> None:
    """The CLI reconstructs oracle evidence from JSON and emits the flat record.

    Mirrors the PowerShell Scoop path: the lane writes tax-evidence.json /
    mcp-evidence.json (the oracles' to_jsonable output), then the thin CLI binds
    the cohort and emits without re-running the oracle.
    """
    import json

    cohort_dir = tmp_path / "cohort"
    _release_cohort(cohort_dir)
    tax_json = tmp_path / "tax-evidence.json"
    mcp_json = tmp_path / "mcp-evidence.json"
    tax_json.write_text(json.dumps(_tax_evidence(tmp_path).to_jsonable()), encoding="utf-8")
    mcp_json.write_text(json.dumps(_mcp_evidence().to_jsonable()), encoding="utf-8")
    evidence_dir = tmp_path / "distribution-install-readiness"

    exit_code = main(
        [
            "--row-id",
            "scoop-windows-x86-64",
            "--release-cohort-dir",
            str(cohort_dir),
            "--tax-evidence",
            str(tax_json),
            "--mcp-evidence",
            str(mcp_json),
            "--acquisition-mechanism",
            "scoop",
            "--acquisition-source",
            "https://github.com/nevenincs/scoop-cadrumo",
            "--destination-kind",
            "scoop-install",
            "--destination-locator",
            "C:/scoop/apps/cadrumo",
            "--distribution-evidence-dir",
            str(evidence_dir),
        ],
    )

    assert exit_code == 0
    records = sorted(evidence_dir.glob("scoop-windows-x86-64-*.json"))
    assert len(records) == 1
    reloaded = DistributionEvidence.model_validate_json(records[0].read_text(encoding="utf-8"))
    assert reloaded.row_id == "scoop-windows-x86-64"
    assert reloaded.result.status is EvidenceStatus.PASSED
    assert reloaded.acquisition.mechanism == "scoop"


def test_destination_version_mismatch_is_refused(tmp_path: Path) -> None:
    """A destination version that is not the cohort version cannot pass validation."""
    cohort = _release_cohort(tmp_path / "cohort")
    with pytest.raises(ValueError, match="destination version"):
        build_installed_oracle_evidence(
            row_id="python-macos-arm64",
            cohort=cohort,
            tax_evidence=_tax_evidence(tmp_path),
            mcp_evidence=_mcp_evidence(),
            acquisition=_acquisition(),
            destination=DestinationIdentity(kind="pypi-index-install", locator="venv", version="9.9.9"),
        )
