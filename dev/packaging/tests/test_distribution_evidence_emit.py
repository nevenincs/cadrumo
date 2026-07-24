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
    build_client_evidence,
    build_installed_oracle_evidence,
    emit_client_evidence,
    emit_installed_oracle_evidence,
    main,
)
from dev.packaging.evidence import (
    AcquisitionIdentity,
    ClientIdentity,
    CommandTranscript,
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
_COHORT_VERSION = "0.2.1"


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
        version=_COHORT_VERSION,
        source=SourceIdentity(commit="c" * 40, tag=f"v{_COHORT_VERSION}"),
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


def _tax_evidence(cwd: Path, *, version: str = _COHORT_VERSION) -> InstalledTaxEvidence:
    """Build installed-CLI oracle evidence from real captured subprocess output.

    ``version`` seeds the real ``--version`` transcript so the capture carries the
    cohort version the binding guard checks; override it to forge a mismatch.
    """
    version_command = _captured_command((sys.executable, "-c", f"print('aeat {version}')"), cwd)
    calculate = _captured_command(
        (sys.executable, "-c", f"print('{_TARGET_CASILLA}={_TARGET_VALUE}')"),
        cwd,
    )
    return InstalledTaxEvidence(
        requested_executable=sys.executable,
        resolved_executable=sys.executable,
        version_output=version_command.stdout.strip(),
        storage_root=str(cwd / "state"),
        work_unit_id="e" * 64,
        calculation_revision_id=_REVISION,
        target_casilla=_TARGET_CASILLA,
        target_value=_TARGET_VALUE,
        formula_id=_FORMULA,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        notice_codes=_NOTICE,
        checkout_imports_removed=True,
        commands=(version_command, calculate),
    )


def _mcp_evidence(*, invoked_cli_sha256: str = "0" * 64) -> InstalledMcpEvidence:
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
        invoked_cli_sha256=invoked_cli_sha256,
        invoked_cli_sha256_by_command={"modelo.work.calculate": invoked_cli_sha256},
        checkout_imports_removed=True,
        ambient_product_executables_removed=True,
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


def _launch_transcript(cwd: Path) -> CommandTranscript:
    """Capture a real owned subprocess as a client server-launch transcript."""
    started_at = datetime.now(UTC)
    argv = (sys.executable, "-c", "print('cadrumo-mcp launched')")
    completed = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)  # noqa: S603
    completed_at = datetime.now(UTC)
    return CommandTranscript.from_output(
        argv=argv,
        cwd=str(cwd),
        started_at=started_at,
        completed_at=completed_at,
        exit_status=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        relevant_output=(completed.stdout.strip() or "launched",),
    )


def _client() -> ClientIdentity:
    return ClientIdentity(name="claude-desktop", version="1.22209", executable=sys.executable)


def _real_client_session() -> dict[str, object]:
    return {"connected": True, "status": "passed", "tool_called": "cadrumo_modelo_work_calculate", "model": "sonnet"}


def _sdk_client() -> ClientIdentity:
    from dev.packaging.distribution_evidence_emit import SDK_CLIENT_NAME

    return ClientIdentity(name=SDK_CLIENT_NAME, version="1.26.0", executable=sys.executable)


def test_sdk_client_cannot_satisfy_a_required_claude_row(tmp_path: Path) -> None:
    """The honesty guard refuses an SDK-client record under a real-client row id."""
    cohort = _release_cohort(tmp_path / "cohort")
    with pytest.raises(ValueError, match="cannot satisfy the real-client row"):
        build_client_evidence(
            row_id="claude-desktop-mcpb",
            cohort=cohort,
            mcp_evidence=_mcp_evidence(),
            launch_transcript=_launch_transcript(tmp_path),
            client=_sdk_client(),
            acquisition=AcquisitionIdentity(mechanism="mcpb", source="github-release"),
            destination=_destination(cohort),
        )


def test_sdk_client_emits_under_a_distinct_artifact_serves_id(tmp_path: Path) -> None:
    """The same SDK-client record is allowed under a distinct artifact-serves id."""
    cohort = _release_cohort(tmp_path / "cohort")
    evidence = build_client_evidence(
        row_id="claude-desktop-mcpb-artifact-serves",
        cohort=cohort,
        mcp_evidence=_mcp_evidence(),
        launch_transcript=_launch_transcript(tmp_path),
        client=_sdk_client(),
        acquisition=AcquisitionIdentity(mechanism="mcpb", source="github-release"),
        destination=_destination(cohort),
    )
    assert evidence.row_id == "claude-desktop-mcpb-artifact-serves"
    assert evidence.result.status is EvidenceStatus.PASSED


def test_required_real_client_row_needs_a_real_session(tmp_path: Path) -> None:
    """A required claude-* row cannot be minted from an owned launch alone."""
    cohort = _release_cohort(tmp_path / "cohort")
    with pytest.raises(ValueError, match="requires a real Claude client session"):
        build_client_evidence(
            row_id="claude-desktop-mcpb",
            cohort=cohort,
            mcp_evidence=_mcp_evidence(),
            launch_transcript=_launch_transcript(tmp_path),
            client=_client(),
            acquisition=AcquisitionIdentity(mechanism="mcpb", source="github-release"),
            destination=_destination(cohort),
            real_client_session=None,
        )


def test_required_real_client_rows_match_readiness() -> None:
    """The guard's required-row set stays in lock-step with the readiness authority."""
    from dev.packaging.distribution_evidence_emit import _REQUIRED_REAL_CLIENT_ROW_IDS
    from dev.release.readiness import REQUIRED_DISTRIBUTION_ROWS

    claude_rows = frozenset(row for row in REQUIRED_DISTRIBUTION_ROWS if row.startswith("claude-"))
    assert claude_rows == _REQUIRED_REAL_CLIENT_ROW_IDS


def test_client_row_uses_owned_launch_transcript_and_mcp_proof(tmp_path: Path) -> None:
    """A pure-client row carries the real launch subprocess + MCP proof, client-bound."""
    cohort = _release_cohort(tmp_path / "cohort")
    evidence = build_client_evidence(
        row_id="claude-desktop-mcpb",
        cohort=cohort,
        mcp_evidence=_mcp_evidence(),
        launch_transcript=_launch_transcript(tmp_path),
        client=_client(),
        acquisition=AcquisitionIdentity(mechanism="mcpb", source="github-release"),
        destination=_destination(cohort),
        real_client_session=_real_client_session(),
    )

    assert evidence.row_id == "claude-desktop-mcpb"
    assert evidence.result.status is EvidenceStatus.PASSED
    assert evidence.client is not None
    assert evidence.client.name == "claude-desktop"
    # Exactly one command: the real owned server-launch subprocess.
    assert len(evidence.commands) == 1
    assert evidence.commands[0].exit_status == 0
    # One installed executable (the client server); MCP proof in observations.
    assert [exe.name for exe in evidence.isolation.installed_executables] == ["cadrumo-mcp"]
    mcp_oracle = evidence.result.observations["mcp_oracle"]
    assert isinstance(mcp_oracle, dict)
    assert mcp_oracle["target_value"] == _TARGET_VALUE
    # The operator's real Claude client session is retained as the real-client proof.
    session = evidence.result.observations["real_client_session"]
    assert isinstance(session, dict)
    assert session["tool_called"] == "cadrumo_modelo_work_calculate"


def test_emit_client_evidence_writes_flat_record(tmp_path: Path) -> None:
    """The client-row record lands flat where both gates read and re-validates."""
    cohort = _release_cohort(tmp_path / "cohort")
    evidence_dir = tmp_path / "distribution-install-readiness"
    path = emit_client_evidence(
        directory=evidence_dir,
        row_id="claude-code-plugin",
        cohort=cohort,
        mcp_evidence=_mcp_evidence(),
        launch_transcript=_launch_transcript(tmp_path),
        client=_client(),
        acquisition=AcquisitionIdentity(mechanism="claude-plugin", source="marketplace"),
        destination=_destination(cohort),
        real_client_session=_real_client_session(),
    )
    assert path.name.startswith("claude-code-plugin-")
    reloaded = DistributionEvidence.model_validate_json(path.read_text(encoding="utf-8"))
    assert reloaded.row_id == "claude-code-plugin"
    assert reloaded.client is not None


def test_version_mismatched_capture_against_cohort_is_refused(tmp_path: Path) -> None:
    """An oracle captured from a different build cannot be minted against the cohort.

    The cohort is version 0.2.1 but the installed CLI reported 0.1.0, so the
    capture is not this cohort's build: minting must refuse rather than copy the
    cohort version onto a foreign capture.
    """
    from dev.packaging.distribution_evidence_emit import EvidenceCohortBindingError

    cohort = _release_cohort(tmp_path / "cohort")
    with pytest.raises(EvidenceCohortBindingError, match="does not carry the cohort version"):
        build_installed_oracle_evidence(
            row_id="python-macos-arm64",
            cohort=cohort,
            tax_evidence=_tax_evidence(tmp_path, version="0.1.0"),
            mcp_evidence=_mcp_evidence(),
            acquisition=_acquisition(),
            destination=_destination(cohort),
        )


def test_cli_refuses_a_version_mismatched_capture_against_the_cohort(tmp_path: Path) -> None:
    """The reconstitution CLI refuses a foreign capture, closing the mint-against-any-cohort hole."""
    import json

    cohort_dir = tmp_path / "cohort"
    _release_cohort(cohort_dir)
    tax_json = tmp_path / "tax-evidence.json"
    mcp_json = tmp_path / "mcp-evidence.json"
    tax_json.write_text(json.dumps(_tax_evidence(tmp_path, version="0.1.0").to_jsonable()), encoding="utf-8")
    mcp_json.write_text(json.dumps(_mcp_evidence().to_jsonable()), encoding="utf-8")
    evidence_dir = tmp_path / "distribution-install-readiness"

    from dev.packaging.distribution_evidence_emit import EvidenceCohortBindingError

    with pytest.raises(EvidenceCohortBindingError, match="does not carry the cohort version"):
        main(
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
    assert not list(evidence_dir.glob("*.json")) if evidence_dir.exists() else True


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
