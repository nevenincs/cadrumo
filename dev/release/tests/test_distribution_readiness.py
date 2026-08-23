"""Real-file gates for complete same-cohort distribution readiness."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...packaging._hashing import sha256_path
from ...packaging.evidence import (
    AcquisitionIdentity,
    CommandTranscript,
    DestinationIdentity,
    EvidenceStatus,
    ExecutionIsolation,
    InstalledExecutableIdentity,
    ResultIdentity,
    RuntimeIdentity,
    create_distribution_evidence,
    current_runtime_identity,
    write_distribution_evidence,
)
from ...packaging.tests._release_cohort_support import release_cohort
from ..readiness import check_distribution_evidence_set

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROW = "current-platform-python"


def _run(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - tests invoke fixed git/Python commands directly
        arguments,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _git_repo(root: Path) -> str:
    root.mkdir()
    _run("git", "init", "--quiet", cwd=root)
    (root / "source.txt").write_text("release source\n", encoding="utf-8")
    _run("git", "add", "source.txt", cwd=root)
    _run(
        "git",
        "-c",
        "user.name=Cadrumo Readiness Test",
        "-c",
        "user.email=readiness@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "release source",
        cwd=root,
    )
    return _run("git", "rev-parse", "HEAD", cwd=root).stdout.strip()


def _cohort(directory: Path, *, commit: str, payload_suffix: str = ""):
    return release_cohort(directory, commit=commit, payload_suffix=payload_suffix)


def _transcript(root: Path) -> CommandTranscript:
    started_at = datetime.now(UTC)
    command = (sys.executable, "-c", "print('installed-oracle=passed')")
    completed = _run(*command, cwd=root)
    return CommandTranscript.from_output(
        argv=command,
        cwd=str(root),
        started_at=started_at,
        completed_at=datetime.now(UTC),
        exit_status=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        relevant_output=(completed.stdout.strip(),),
    )


def _record(
    root: Path,
    cohort,
    *,
    status: EvidenceStatus = EvidenceStatus.PASSED,
    row_id: str = _ROW,
    runtime: RuntimeIdentity | None = None,
):
    return create_distribution_evidence(
        row_id=row_id,
        cohort=cohort,
        runtime=runtime if runtime is not None else current_runtime_identity(),
        client=None,
        isolation=ExecutionIsolation(
            checkout_imports_removed=True,
            ambient_product_executables_removed=True,
            installed_executables=(
                InstalledExecutableIdentity(
                    name="cadrumo",
                    path=sys.executable,
                    sha256=sha256_path(Path(sys.executable)),
                ),
            ),
        ),
        acquisition=AcquisitionIdentity(
            mechanism="retained-release-cohort",
            source=cohort.manifest_path.as_uri(),
        ),
        commands=(_transcript(root),),
        result=ResultIdentity(
            status=status,
            assertions=("installed oracle completed",),
            observations={"oracle": "passed" if status is EvidenceStatus.PASSED else "failed"},
        ),
        observed_at=datetime.now(UTC),
        destination=DestinationIdentity(
            kind="isolated-environment",
            locator=str(root / "installed"),
            version=cohort.manifest.version,
        ),
    )


def _ready_tree(tmp_path: Path):
    repo = tmp_path / "repo"
    commit = _git_repo(repo)
    cohort = _cohort(repo / "var" / "release-cohort", commit=commit)
    evidence = repo / "var" / "distribution-install-readiness"
    evidence.mkdir(parents=True)
    return repo, cohort, evidence


def test_complete_exact_cohort_evidence_set_passes(tmp_path: Path) -> None:
    """A real executed row for the checked-out cohort satisfies its declared set."""
    repo, cohort, evidence = _ready_tree(tmp_path)
    write_distribution_evidence(evidence, _record(repo, cohort))

    check = check_distribution_evidence_set(repo, required_rows=(_ROW,))

    assert check.passed is True
    assert check.severity == "blocking"
    assert cohort.manifest.cohort_id in check.detail


def test_incomplete_or_failed_evidence_set_blocks(tmp_path: Path) -> None:
    """Missing and explicitly failed required rows can never authorize release."""
    repo, cohort, evidence = _ready_tree(tmp_path)

    missing = check_distribution_evidence_set(repo, required_rows=(_ROW,))
    assert missing.passed is False
    assert "empty" in missing.detail

    write_distribution_evidence(evidence, _record(repo, cohort, status=EvidenceStatus.FAILED))
    failed = check_distribution_evidence_set(repo, required_rows=(_ROW,))
    assert failed.passed is False
    assert "failed distribution rows" in failed.detail


def test_evidence_from_another_cohort_blocks(tmp_path: Path) -> None:
    """A valid record for different bytes is mismatched rather than reusable."""
    repo, first, evidence = _ready_tree(tmp_path)
    second = _cohort(repo / "var" / "other-release-cohort", commit=first.manifest.source.commit, payload_suffix="two")
    write_distribution_evidence(evidence, _record(repo, first))

    check = check_distribution_evidence_set(
        repo,
        cohort_directory=second.directory,
        evidence_directory=evidence,
        required_rows=(_ROW,),
    )

    assert check.passed is False
    assert "mismatched evidence" in check.detail


def test_evidence_for_an_older_source_commit_blocks(tmp_path: Path) -> None:
    """Even passing retained rows become stale after the checked-out source changes."""
    repo, cohort, evidence = _ready_tree(tmp_path)
    write_distribution_evidence(evidence, _record(repo, cohort))
    (repo / "source.txt").write_text("new source revision\n", encoding="utf-8")
    _run("git", "add", "source.txt", cwd=repo)
    _run(
        "git",
        "-c",
        "user.name=Cadrumo Readiness Test",
        "-c",
        "user.email=readiness@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "new source",
        cwd=repo,
    )

    check = check_distribution_evidence_set(repo, required_rows=(_ROW,))

    assert check.passed is False
    assert "does not match checked-out commit" in check.detail


@pytest.mark.parametrize(
    ("field_path", "invalid_value"),
    (("status", "skipped"), ("ambient_product_executables_removed", False)),
)
def test_skipped_or_ambient_evidence_document_blocks(
    tmp_path: Path,
    field_path: str,
    invalid_value: str | bool,
) -> None:
    """Invalid status and ambient execution remain blockers even beside a valid row."""
    repo, cohort, evidence = _ready_tree(tmp_path)
    valid_path = write_distribution_evidence(evidence, _record(repo, cohort))
    document = json.loads(valid_path.read_text(encoding="utf-8"))
    if field_path == "status":
        document["result"][field_path] = invalid_value
    else:
        document["isolation"][field_path] = invalid_value
    invalid_path = evidence / f"invalid-{field_path}.json"
    invalid_path.write_text(json.dumps(document), encoding="utf-8")

    check = check_distribution_evidence_set(repo, required_rows=(_ROW,))

    assert check.passed is False
    assert "invalid or mismatched evidence" in check.detail


def test_two_consistent_passing_captures_of_one_row_still_pass(tmp_path: Path) -> None:
    """A legitimate re-run writing a second immutable passing capture does not block.

    The two records differ in evidence_id, observed_at, and command
    transcript (an inherent re-run difference) but agree on runtime,
    and destination kind -- the identity axes that matter.
    """
    repo, cohort, evidence = _ready_tree(tmp_path)
    first = _record(repo, cohort)
    second = _record(repo, cohort)
    assert first.evidence_id != second.evidence_id, "the two captures must be genuinely distinct evidence"
    write_distribution_evidence(evidence, first)
    write_distribution_evidence(evidence, second)

    check = check_distribution_evidence_set(repo, required_rows=(_ROW,))

    assert check.passed is True


def test_two_conflicting_passing_captures_of_one_row_block(tmp_path: Path) -> None:
    """Two passing captures of the same row disagreeing on runtime identity block.

    The set-based collapse this test guards against would silently accept
    either capture as evidence for the row with no signal that they
    disagree on which platform actually produced it.
    """
    repo, cohort, evidence = _ready_tree(tmp_path)
    linux_runtime = RuntimeIdentity(
        operating_system="Linux",
        operating_system_release="6.8.0",
        architecture="x86_64",
        python="3.13.0",
        python_implementation="CPython",
    )
    write_distribution_evidence(evidence, _record(repo, cohort))
    write_distribution_evidence(evidence, _record(repo, cohort, runtime=linux_runtime))

    check = check_distribution_evidence_set(repo, required_rows=(_ROW,))

    assert check.passed is False
    assert "conflicting passing evidence" in check.detail
    assert _ROW in check.detail
