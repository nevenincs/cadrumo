"""Real filesystem tests for packaging-smoke evidence checkpointing."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from dev.packaging.cohort_manifest import (
    REQUIRED_ARTIFACT_KINDS,
    BuildIdentity,
    SourceIdentity,
    create_manifest,
    load_release_cohort,
    sha256_file,
    write_manifest,
)
from dev.packaging.evidence import (
    AcquisitionIdentity,
    ClientIdentity,
    CommandTranscript,
    DestinationIdentity,
    DistributionEvidence,
    EvidenceStatus,
    ExecutionIsolation,
    InstalledExecutableIdentity,
    ResultIdentity,
    RuntimeIdentity,
    checkpoint_smoke_evidence,
    create_distribution_evidence,
    load_distribution_evidence,
    write_distribution_evidence,
)
from dev.packaging.smoke_core import _write_smoke_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _release_cohort(root: Path):
    root.mkdir()
    artifacts = []
    for index, (name, kind) in enumerate(sorted(REQUIRED_ARTIFACT_KINDS.items())):
        path = root / "artifacts" / f"{name}.bin"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(f"{index}:{name}\n".encode())
        artifacts.append((name, kind, path))
    manifest = create_manifest(
        root=root,
        version="0.2.0",
        source=SourceIdentity(commit="a" * 40, tag="v0.2.0"),
        created_at=datetime.now(UTC),
        builder=BuildIdentity(
            implementation="dev.packaging.release_cohort",
            format_version=1,
            python=platform.python_version(),
            uv="0.11.29",
            platform=platform.system(),
            architecture=platform.machine(),
            build_constraints_sha256="b" * 64,
        ),
        artifacts=artifacts,
    )
    write_manifest(root, manifest)
    return load_release_cohort(root)


def _executed_transcript(tmp_path: Path) -> CommandTranscript:
    started_at = datetime.now(UTC)
    command = (sys.executable, "-c", "print('DP200014:00562=23000.00')")
    completed = subprocess.run(  # noqa: S603 - sys.executable is the current trusted interpreter
        command,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    completed_at = datetime.now(UTC)
    return CommandTranscript.from_output(
        argv=command,
        cwd=str(tmp_path),
        started_at=started_at,
        completed_at=completed_at,
        exit_status=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        relevant_output=(completed.stdout.strip(),),
    )


def _passing_evidence(tmp_path: Path) -> DistributionEvidence:
    cohort = _release_cohort(tmp_path / "cohort")
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
            name="cadrumo-mcp-sdk-client",
            version="1.26.0",
            executable=sys.executable,
        ),
        isolation=ExecutionIsolation(
            checkout_imports_removed=True,
            ambient_product_executables_removed=True,
            installed_executables=(
                InstalledExecutableIdentity(
                    name="cadrumo-mcp",
                    path=sys.executable,
                    sha256=sha256_file(Path(sys.executable)),
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
    artifact = next((tmp_path / "cohort" / "artifacts").iterdir())
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
    manifest = _write_smoke_manifest(
        work_dir,
        lane="docker-core",
        artifacts={"wheel": "wheel/cadrumo.whl"},
        checks=("clean Linux container install",),
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
    _write_smoke_manifest(
        completed,
        lane="browser-extra",
        artifacts={"wheel": "wheel/cadrumo.whl"},
        checks=("localhost browser health smoke",),
    )
    evidence_root = tmp_path / "packaging-smoke-evidence"

    checkpointed = checkpoint_smoke_evidence(smoke_root, evidence_root, prune_completed=True)

    assert checkpointed == (evidence_root / "browser-20260715T214000Z.json",)
    assert not completed.exists()
    assert (incomplete / "failure.log").read_text(encoding="utf-8") == "ENOSPC\n"
