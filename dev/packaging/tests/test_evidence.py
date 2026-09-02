"""Real filesystem tests for packaging-smoke evidence checkpointing."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.directory_scan import iter_directory

from .._command import run_command
from .._hashing import sha256_path
from .._proof_ledger import record_proof, reset_proof_ledger
from .._smoke_common import write_smoke_manifest
from ..cohort_manifest import (
    REQUIRED_ARTIFACT_KINDS,
    ArtifactRecord,
    BuildIdentity,
    CohortManifest,
    LoadedReleaseCohort,
    SourceIdentity,
    cohort_identifier,
    load_release_cohort,
)
from ..evidence import (
    AcquisitionIdentity,
    ClientIdentity,
    CommandTranscript,
    DestinationIdentity,
    DistributionEvidence,
    EvidenceStatus,
    ExecutionIsolation,
    InstallationOutcome,
    InstalledExecutableIdentity,
    ResultIdentity,
    RuntimeIdentity,
    checkpoint_smoke_evidence,
    create_distribution_evidence,
    load_distribution_evidence,
    write_distribution_evidence,
)
from ._release_cohort_support import release_cohort

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _executed_transcript(tmp_path: Path) -> CommandTranscript:
    command = (sys.executable, "-c", "print('DP200014:00562=23000.00')")
    completed = run_command(command, cwd=tmp_path)
    return CommandTranscript.from_result(
        completed,
        relevant_output=(completed.stdout.strip(),),
    )


def test_command_transcript_projects_canonical_result_with_independent_stream_oracles(tmp_path: Path) -> None:
    """The durable projection hashes the real shared-runner streams without retiming them."""
    result = run_command(
        (sys.executable, "-c", "import sys; print('stdout'); print('stderr', file=sys.stderr)"),
        cwd=tmp_path,
    )
    transcript = CommandTranscript.from_result(result, relevant_output=("command completed",))

    assert transcript.argv == result.argv
    assert transcript.cwd == result.cwd
    assert transcript.started_at == result.started_at
    assert transcript.completed_at == result.completed_at
    assert transcript.exit_status == result.returncode
    assert transcript.stdout_sha256 == hashlib.sha256(result.stdout.encode("utf-8")).hexdigest()
    assert transcript.stderr_sha256 == hashlib.sha256(result.stderr.encode("utf-8")).hexdigest()


def _passing_evidence_for_cohort(tmp_path: Path, cohort: LoadedReleaseCohort) -> DistributionEvidence:
    observed_at = datetime.now(UTC)
    return create_distribution_evidence(
        row_id="windows-x86-64-python",
        cohort=cohort,
        runtime=RuntimeIdentity(
            operating_system=platform.system(),
            operating_system_release=platform.release(),
            architecture=platform.machine(),
            python=platform.python_version(),
            python_implementation=platform.python_implementation(),
        ),
        client=ClientIdentity(
            name="release-probe",
            version="1.26.0",
            executable=sys.executable,
        ),
        isolation=ExecutionIsolation(
            checkout_imports_removed=True,
            ambient_product_executables_removed=True,
            installed_executables=(
                InstalledExecutableIdentity(
                    name="aeat",
                    path=sys.executable,
                    sha256=sha256_path(Path(sys.executable)),
                ),
            ),
        ),
        acquisition=AcquisitionIdentity(
            mechanism="local-immutable-cohort",
            source=cohort.manifest_path.as_uri(),
        ),
        commands=(_executed_transcript(tmp_path),),
        result=ResultIdentity(
            status=EvidenceStatus.PASSED,
            assertions=("installed tax oracle returned DP200014:00562 == 23000.00",),
            observations={"target_casilla": "DP200014:00562", "target_value": "23000.00"},
        ),
        observed_at=observed_at,
        destination=DestinationIdentity(
            kind="isolated-python-environment",
            locator=str(tmp_path / "installed"),
            version=cohort.manifest.version,
        ),
    )


def _passing_evidence(tmp_path: Path) -> DistributionEvidence:
    return _passing_evidence_for_cohort(tmp_path, release_cohort(tmp_path / "cohort"))


def _synthetic_cohort(tmp_path: Path) -> LoadedReleaseCohort:
    """Create a valid in-memory cohort binding without rebuilding distributions."""
    root = tmp_path / "synthetic-cohort"
    root.mkdir()
    source = SourceIdentity(commit="c" * 40, tag="v0.2.1")
    artifacts = tuple(
        ArtifactRecord(
            name=name,
            kind=kind,
            path=f"{name}.bin",
            sha256=hashlib.sha256(name.encode("utf-8")).hexdigest(),
            size=len(name),
        )
        for name, kind in sorted(REQUIRED_ARTIFACT_KINDS.items())
    )
    manifest = CohortManifest(
        schema_name="cadrumo.release-cohort.v1",
        cohort_id=cohort_identifier(version="0.2.1", source=source, artifacts=artifacts),
        version="0.2.1",
        source=source,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        builder=BuildIdentity(
            implementation="dev.packaging.release_cohort",
            format_version=1,
            python="3.13.11",
            uv="0.11.29",
            platform=platform.system(),
            architecture=platform.machine(),
            build_constraints_sha256="d" * 64,
        ),
        artifacts=artifacts,
    )
    manifest_path = root / "release-cohort.json"
    manifest_path.write_text("synthetic cohort binding\n", encoding="utf-8")
    return LoadedReleaseCohort(directory=root, manifest_path=manifest_path, manifest=manifest)


def _installation_outcome(
    evidence: DistributionEvidence,
    *,
    mode: str = "source",
    status: str = "resolved",
    cohort_manifest_sha256: str | None = None,
) -> InstallationOutcome:
    """Build a digest-bound installation result for evidence contract tests."""
    artifact_digests = {
        "cadrumo": "a" * 64,
        "cadrumo-data-manuals": "b" * 64,
        "cadrumo-data-official": "c" * 64,
    }
    canonical = json.dumps(
        artifact_digests,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return InstallationOutcome(
        mode=mode,
        status=status,
        lock_sha256="d" * 64,
        artifact_sha256=hashlib.sha256(canonical).hexdigest(),
        artifact_digests=artifact_digests,
        cohort_manifest_sha256=cohort_manifest_sha256
        if cohort_manifest_sha256 is not None
        else (evidence.cohort.manifest_sha256 if mode == "binary" else None),
    )


def _evidence_with_installation(
    evidence: DistributionEvidence,
    installation: InstallationOutcome,
    cohort: LoadedReleaseCohort,
) -> DistributionEvidence:
    """Re-mint one row while retaining its exact executed proof."""
    return create_distribution_evidence(
        row_id=evidence.row_id,
        cohort=cohort,
        runtime=evidence.runtime,
        client=evidence.client,
        isolation=evidence.isolation,
        acquisition=evidence.acquisition,
        commands=evidence.commands,
        result=evidence.result,
        observed_at=evidence.observed_at,
        destination=evidence.destination,
        installation=installation,
    )


def test_distribution_evidence_keeps_source_and_binary_outcomes_separate(tmp_path: Path) -> None:
    """A source success cannot stand in for the independently proven wheel mode."""
    cohort = _synthetic_cohort(tmp_path)
    evidence = _passing_evidence_for_cohort(tmp_path, cohort)
    source = _evidence_with_installation(
        evidence,
        _installation_outcome(evidence, mode="source"),
        cohort,
    )
    binary = _evidence_with_installation(
        evidence,
        _installation_outcome(evidence, mode="binary"),
        cohort,
    )

    assert source.installation is not None
    assert source.installation.mode == "source"
    assert binary.installation is not None
    assert binary.installation.mode == "binary"
    assert source.evidence_id != binary.evidence_id


def test_distribution_evidence_refuses_missing_wheel_as_passing(tmp_path: Path) -> None:
    """A missing binary wheel remains a failed installation outcome, not a skip."""
    cohort = _synthetic_cohort(tmp_path)
    evidence = _passing_evidence_for_cohort(tmp_path, cohort)
    missing_wheel = _installation_outcome(evidence, mode="binary", status="missing-wheel")

    with pytest.raises(ValidationError, match="resolved installation outcome"):
        _evidence_with_installation(evidence, missing_wheel, cohort)

    with pytest.raises(ValidationError):
        InstallationOutcome.model_validate(
            {
                "mode": "binary",
                "status": "skipped",
                "lock_sha256": "d" * 64,
                "artifact_sha256": "e" * 64,
                "artifact_digests": {"cadrumo": "a" * 64},
            },
        )


def test_distribution_evidence_refuses_installation_from_a_foreign_cohort(tmp_path: Path) -> None:
    """A binary result naming another cohort cannot be attached to this row."""
    cohort = _synthetic_cohort(tmp_path)
    evidence = _passing_evidence_for_cohort(tmp_path, cohort)
    foreign = _installation_outcome(evidence, mode="binary", cohort_manifest_sha256="e" * 64)

    with pytest.raises(ValidationError, match="does not bind the supplied release cohort"):
        _evidence_with_installation(evidence, foreign, cohort)


def test_distribution_evidence_roundtrips_against_exact_real_cohort(tmp_path: Path) -> None:
    """A retained result binds source, every digest, runtime, command, and destination."""
    evidence = _passing_evidence(tmp_path)
    destination = write_distribution_evidence(tmp_path / "evidence", evidence)

    loaded = load_distribution_evidence(destination, cohort_directory=tmp_path / "cohort")

    assert loaded == evidence
    assert loaded.result.status is EvidenceStatus.PASSED
    assert loaded.commands[0].relevant_output == ("DP200014:00562=23000.00",)
    assert loaded.cohort.artifacts == load_release_cohort(tmp_path / "cohort").manifest.artifacts


def test_distribution_evidence_rejects_content_changed_after_recording(tmp_path: Path) -> None:
    """Editing a command result without recomputing authority invalidates the record."""
    evidence = _passing_evidence(tmp_path)
    destination = write_distribution_evidence(tmp_path / "evidence", evidence)
    document = json.loads(destination.read_text(encoding="utf-8"))
    document["commands"][0]["relevant_output"] = ["DP200014:00562=0.00"]
    destination.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValidationError, match="evidence identifier mismatch"):
        load_distribution_evidence(destination)


def test_distribution_evidence_rejects_different_or_mutated_cohort(tmp_path: Path) -> None:
    """Evidence cannot be presented with cohort bytes other than those it records."""
    evidence = _passing_evidence(tmp_path)
    destination = write_distribution_evidence(tmp_path / "evidence", evidence)
    artifact = next(iter_directory(tmp_path / "cohort" / "artifacts"))
    artifact.write_bytes(b"x" * artifact.stat().st_size)

    with pytest.raises(SystemExit, match="digest mismatch"):
        load_distribution_evidence(destination, cohort_directory=tmp_path / "cohort")


def test_passing_evidence_rejects_nonzero_command_and_skipped_status(tmp_path: Path) -> None:
    """A failed command or skipped row cannot become passing release evidence."""
    evidence = _passing_evidence(tmp_path)
    payload = evidence.model_dump(exclude={"evidence_id"})
    payload["commands"][0]["exit_status"] = 17

    with pytest.raises(ValidationError, match="passing evidence cannot contain a failed command"):
        create_distribution_evidence(
            row_id=payload["row_id"],
            cohort=load_release_cohort(tmp_path / "cohort"),
            runtime=evidence.runtime,
            client=evidence.client,
            isolation=evidence.isolation,
            acquisition=evidence.acquisition,
            commands=(CommandTranscript.model_validate(payload["commands"][0]),),
            result=evidence.result,
            observed_at=evidence.observed_at,
            destination=evidence.destination,
        )

    with pytest.raises(ValidationError):
        ResultIdentity.model_validate(
            {"status": "skipped", "assertions": ["not executed"], "observations": {}},
        )


def test_passing_evidence_rejects_ambient_or_checkout_execution(tmp_path: Path) -> None:
    """A successful oracle still fails evidence validation without installed isolation."""
    evidence = _passing_evidence(tmp_path)
    unsafe = evidence.isolation.model_copy(update={"ambient_product_executables_removed": False})

    with pytest.raises(ValidationError, match="checkout and ambient executable isolation"):
        create_distribution_evidence(
            row_id=evidence.row_id,
            cohort=load_release_cohort(tmp_path / "cohort"),
            runtime=evidence.runtime,
            client=evidence.client,
            isolation=unsafe,
            acquisition=evidence.acquisition,
            commands=evidence.commands,
            result=evidence.result,
            observed_at=evidence.observed_at,
            destination=evidence.destination,
        )


def test_checkpoint_copies_manifest_without_traversing_secure_runtime(tmp_path) -> None:
    """The checkpoint reads the known manifest leaf, not protected runtime descendants."""
    smoke_root = tmp_path / "packaging-smoke"
    work_dir = smoke_root / "docker-core-20260715T214242Z"
    secrets_dir = work_dir / "profile-root" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "encrypted.bin").write_bytes(b"ciphertext")
    (secrets_dir / "packaging-smoke-manifest.json").write_text("not-json", encoding="utf-8")
    reset_proof_ledger()
    record_proof("clean Linux container install")
    manifest = write_smoke_manifest(
        work_dir,
        lane="docker-core",
        artifacts={"wheel": "wheel/cadrumo.whl"},
        declared=("clean Linux container install",),
    )
    evidence_root = tmp_path / "packaging-smoke-evidence"

    checkpointed = checkpoint_smoke_evidence(smoke_root, evidence_root, prune_completed=False)

    assert checkpointed == (evidence_root / "docker-core-20260715T214242Z.json",)
    assert json.loads(checkpointed[0].read_text(encoding="utf-8")) == json.loads(manifest.read_text(encoding="utf-8"))
    assert secrets_dir.is_dir()


def test_checkpoint_prunes_only_completed_work_directories(tmp_path) -> None:
    """Successful runtime trees are released while incomplete diagnostic state remains."""
    smoke_root = tmp_path / "packaging-smoke"
    completed = smoke_root / "browser-20260715T214000Z"
    incomplete = smoke_root / "docker-browser-20260715T214500Z"
    completed.mkdir(parents=True)
    incomplete.mkdir(parents=True)
    (completed / "large-browser-payload.bin").write_bytes(b"browser-cache")
    (incomplete / "failure.log").write_text("ENOSPC\n", encoding="utf-8")
    reset_proof_ledger()
    record_proof("localhost browser health smoke")
    write_smoke_manifest(
        completed,
        lane="browser-extra",
        artifacts={"wheel": "wheel/cadrumo.whl"},
        declared=("localhost browser health smoke",),
    )
    evidence_root = tmp_path / "packaging-smoke-evidence"

    checkpointed = checkpoint_smoke_evidence(smoke_root, evidence_root, prune_completed=True)

    assert checkpointed == (evidence_root / "browser-20260715T214000Z.json",)
    assert not completed.exists()
    assert (incomplete / "failure.log").read_text(encoding="utf-8") == "ENOSPC\n"


def test_checkpoint_refuses_to_replace_existing_immutable_evidence(tmp_path: Path) -> None:
    """A checkpoint collision preserves both the retained artifact and its smoke work directory."""
    smoke_root = tmp_path / "packaging-smoke"
    work_dir = smoke_root / "browser-20260715T214000Z"
    work_dir.mkdir(parents=True)
    reset_proof_ledger()
    record_proof("localhost browser health smoke")
    write_smoke_manifest(
        work_dir,
        lane="browser-extra",
        artifacts={"wheel": "wheel/cadrumo.whl"},
        declared=("localhost browser health smoke",),
    )
    evidence_root = tmp_path / "packaging-smoke-evidence"
    evidence_root.mkdir()
    target = evidence_root / "browser-20260715T214000Z.json"
    sentinel = b'{"retained":"immutable evidence"}\n'
    target.write_bytes(sentinel)

    with pytest.raises(FileExistsError, match="smoke evidence already exists"):
        checkpoint_smoke_evidence(smoke_root, evidence_root, prune_completed=True)

    assert target.read_bytes() == sentinel
    assert work_dir.is_dir()
    assert not target.with_suffix(".json.tmp").exists()
