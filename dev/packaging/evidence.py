"""Persist cohort-bound distribution evidence and checkpoint legacy smoke runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import sys
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory

from .._paths import REPO_ROOT, UTF_8
from ._command import CommandResult
from ._hashing import sha256_path
from .cohort_manifest import (
    ArtifactRecord,
    LoadedReleaseCohort,
    SourceIdentity,
    load_release_cohort,
)

_MANIFEST_NAME: Final[str] = "packaging-smoke-manifest.json"
_EVIDENCE_SCHEMA: Final[Literal["cadrumo.distribution-evidence.v1"]] = "cadrumo.distribution-evidence.v1"
_SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"
_SHA256_RE: Final[re.Pattern[str]] = re.compile(_SHA256_PATTERN)
_UTF_8: Final[str] = UTF_8


def _is_sha256(value: str) -> bool:
    """Return whether a value is a canonical lowercase SHA-256 digest."""
    return _SHA256_RE.fullmatch(value) is not None


def _artifact_digest(artifacts: Mapping[str, str]) -> str:
    """Hash an artifact-name/digest map using the compatibility-runner format."""
    canonical = json.dumps(
        dict(sorted(artifacts.items())),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode(_UTF_8)
    return hashlib.sha256(canonical).hexdigest()


class EvidenceStatus(StrEnum):
    """Closed result taxonomy; an absent or skipped row is never evidence."""

    PASSED = "passed"
    FAILED = "failed"


class CohortBinding(BaseModel):
    """Exact immutable cohort identity repeated in every result record."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    cohort_id: str = Field(pattern=_SHA256_PATTERN)
    version: str = Field(min_length=1)
    source: SourceIdentity
    created_at: datetime
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    artifacts: tuple[ArtifactRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _timezone_aware(self) -> Self:
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("cohort created_at must carry a timezone")
        return self


class RuntimeIdentity(BaseModel):
    """Platform and Python identity that actually executed the row."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    operating_system: str = Field(min_length=1)
    operating_system_release: str = Field(min_length=1)
    architecture: str = Field(min_length=1)
    python: str = Field(min_length=1)
    python_implementation: str = Field(min_length=1)
    stability: Literal["stable", "prerelease"] = "stable"


class InstallationOutcome(BaseModel):
    """Attributable dependency outcome for one source or binary install.

    The compatibility runner records source and binary installs independently.
    Keeping that distinction in the distribution evidence prevents a successful
    source build from being mistaken for native-wheel availability.  Every
    outcome carries the lock and artifact digests used for the attempt; a
    missing wheel is a recorded binary failure, never a skipped row.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    mode: Literal["source", "binary"]
    status: Literal["resolved", "missing-wheel", "failed"]
    lock_sha256: str = Field(pattern=_SHA256_PATTERN)
    artifact_sha256: str = Field(pattern=_SHA256_PATTERN)
    artifact_digests: dict[str, str] = Field(min_length=1)
    cohort_manifest_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _complete_and_canonical(self) -> Self:
        """Reject hidden skips and ensure the aggregate names exact artifacts."""
        if self.status == "missing-wheel" and self.mode != "binary":
            raise ValueError("a missing wheel is only an attributable binary installation outcome")
        if any(not name for name in self.artifact_digests):
            raise ValueError("installation artifact names cannot be empty")
        if any(not _is_sha256(digest) for digest in self.artifact_digests.values()):
            raise ValueError("installation artifact digests must be lowercase SHA-256 values")
        expected = _artifact_digest(self.artifact_digests)
        if self.artifact_sha256 != expected:
            raise ValueError(
                "installation artifact_sha256 must bind the canonical artifact digest map",
            )
        return self


class ClientIdentity(BaseModel):
    """Real client identity for a client-dependent result row."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    executable: str = Field(min_length=1)


class InstalledExecutableIdentity(BaseModel):
    """One exact installed command invoked by the retained transcript."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=_SHA256_PATTERN)


class ExecutionIsolation(BaseModel):
    """Proof that installed bytes, not checkout or ambient commands, executed."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    checkout_imports_removed: bool
    ambient_product_executables_removed: bool
    installed_executables: tuple[InstalledExecutableIdentity, ...] = Field(min_length=1)


class AcquisitionIdentity(BaseModel):
    """Mechanism and source from which the tested bytes were acquired."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    mechanism: str = Field(min_length=1)
    source: str = Field(min_length=1)


class DestinationIdentity(BaseModel):
    """Installation or promotion destination reached by the commands."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    version: str = Field(min_length=1)


class CommandTranscript(BaseModel):
    """One executed command with output digests and safe verdict excerpts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    argv: tuple[str, ...] = Field(min_length=1)
    cwd: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    exit_status: int
    stdout_sha256: str = Field(pattern=_SHA256_PATTERN)
    stderr_sha256: str = Field(pattern=_SHA256_PATTERN)
    relevant_output: tuple[str, ...] = Field(min_length=1)

    @classmethod
    def from_output(
        cls,
        *,
        argv: tuple[str, ...],
        cwd: str,
        started_at: datetime,
        completed_at: datetime,
        exit_status: int,
        stdout: str,
        stderr: str,
        relevant_output: tuple[str, ...],
    ) -> Self:
        """Digest full streams while retaining only explicitly safe excerpts."""
        return cls(
            argv=argv,
            cwd=cwd,
            started_at=started_at,
            completed_at=completed_at,
            exit_status=exit_status,
            stdout_sha256=hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
            stderr_sha256=hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
            relevant_output=relevant_output,
        )

    @classmethod
    def from_result(
        cls,
        result: CommandResult,
        *,
        relevant_output: tuple[str, ...],
    ) -> Self:
        """Project one owned subprocess result into durable evidence."""
        return cls.from_output(
            argv=result.argv,
            cwd=result.cwd,
            started_at=result.started_at,
            completed_at=result.completed_at,
            exit_status=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            relevant_output=relevant_output,
        )

    @model_validator(mode="after")
    def _chronological_and_timezone_aware(self) -> Self:
        for field_name, value in (
            ("started_at", self.started_at),
            ("completed_at", self.completed_at),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must carry a timezone")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        if any(not argument for argument in self.argv):
            raise ValueError("command arguments cannot be empty")
        if any(not excerpt for excerpt in self.relevant_output):
            raise ValueError("relevant output excerpts cannot be empty")
        return self


class ResultIdentity(BaseModel):
    """Machine result and the concrete assertions supporting its verdict."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: EvidenceStatus
    assertions: tuple[str, ...] = Field(min_length=1)
    observations: dict[str, JsonValue]


class EvidenceIdentityPayload(BaseModel):
    """Canonical content whose digest is the evidence identifier."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_name: Literal["cadrumo.distribution-evidence.v1"]
    row_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    cohort: CohortBinding
    runtime: RuntimeIdentity
    client: ClientIdentity | None
    isolation: ExecutionIsolation
    acquisition: AcquisitionIdentity
    commands: tuple[CommandTranscript, ...] = Field(min_length=1)
    result: ResultIdentity
    observed_at: datetime
    destination: DestinationIdentity
    installation: InstallationOutcome | None = None

    @model_validator(mode="after")
    def _passing_commands_and_time_are_valid(self) -> Self:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must carry a timezone")
        if self.result.status is EvidenceStatus.PASSED and any(command.exit_status != 0 for command in self.commands):
            raise ValueError("passing evidence cannot contain a failed command")
        if self.result.status is EvidenceStatus.PASSED and not (
            self.isolation.checkout_imports_removed and self.isolation.ambient_product_executables_removed
        ):
            raise ValueError("passing evidence requires checkout and ambient executable isolation")
        if self.result.status is EvidenceStatus.PASSED and self.destination.version != self.cohort.version:
            raise ValueError("passing evidence destination version must match the cohort")
        if self.installation is not None:
            if self.result.status is EvidenceStatus.PASSED and self.installation.status != "resolved":
                raise ValueError("passing evidence requires a resolved installation outcome")
            if (
                self.installation.cohort_manifest_sha256 is not None
                and self.installation.cohort_manifest_sha256 != self.cohort.manifest_sha256
            ):
                raise ValueError("installation evidence does not bind the supplied release cohort")
            if self.installation.mode == "binary" and self.installation.cohort_manifest_sha256 is None:
                raise ValueError("binary installation evidence must bind a release-cohort manifest")
        if self.observed_at < self.cohort.created_at:
            raise ValueError("evidence cannot predate cohort construction")
        return self


class DistributionEvidence(EvidenceIdentityPayload):
    """Tamper-evident result for one platform, channel, or client row."""

    evidence_id: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _identifier_matches_content(self) -> Self:
        expected = evidence_identifier(self)
        if self.evidence_id != expected:
            raise ValueError(
                f"evidence identifier mismatch: expected {expected}, got {self.evidence_id}",
            )
        return self


def _canonical_json(document: Mapping[str, object]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode(_UTF_8)


def evidence_identifier(evidence: EvidenceIdentityPayload) -> str:
    """Return the SHA-256 identifier for all evidence content except its id."""
    document = evidence.model_dump(mode="json", exclude={"evidence_id"})
    return hashlib.sha256(_canonical_json(document)).hexdigest()


def bind_cohort(cohort: LoadedReleaseCohort) -> CohortBinding:
    """Copy the validated release authority into one evidence binding."""
    manifest = cohort.manifest
    return CohortBinding(
        cohort_id=manifest.cohort_id,
        version=manifest.version,
        source=manifest.source,
        created_at=manifest.created_at,
        manifest_sha256=sha256_path(cohort.manifest_path),
        artifacts=manifest.artifacts,
    )


def current_runtime_identity() -> RuntimeIdentity:
    """Describe the interpreter and platform executing the current row."""
    return RuntimeIdentity(
        operating_system=platform.system(),
        operating_system_release=platform.release(),
        architecture=platform.machine(),
        python=platform.python_version(),
        python_implementation=platform.python_implementation(),
        stability="stable" if sys.version_info.releaselevel == "final" else "prerelease",
    )


def create_distribution_evidence(
    *,
    row_id: str,
    cohort: LoadedReleaseCohort,
    runtime: RuntimeIdentity,
    client: ClientIdentity | None,
    isolation: ExecutionIsolation,
    acquisition: AcquisitionIdentity,
    commands: tuple[CommandTranscript, ...],
    result: ResultIdentity,
    observed_at: datetime,
    destination: DestinationIdentity,
    installation: InstallationOutcome | None = None,
) -> DistributionEvidence:
    """Create a validated record bound to real, already-verified cohort bytes."""
    payload = EvidenceIdentityPayload(
        schema_name=_EVIDENCE_SCHEMA,
        row_id=row_id,
        cohort=bind_cohort(cohort),
        runtime=runtime,
        client=client,
        isolation=isolation,
        acquisition=acquisition,
        commands=commands,
        result=result,
        observed_at=observed_at,
        destination=destination,
        installation=installation,
    )
    return DistributionEvidence(
        **payload.model_dump(),
        evidence_id=evidence_identifier(payload),
    )


def write_distribution_evidence(directory: Path, evidence: DistributionEvidence) -> Path:
    """Persist one immutable result without replacing prior evidence."""
    root = directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{evidence.row_id}-{evidence.evidence_id}.json"
    if destination.exists():
        raise FileExistsError(f"distribution evidence already exists: {destination}")
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(evidence.model_dump_json(indent=2) + "\n", encoding=_UTF_8, newline="\n")
    temporary.replace(destination)
    return destination


def load_distribution_evidence(
    path: Path,
    *,
    cohort_directory: Path | None = None,
) -> DistributionEvidence:
    """Load evidence and optionally prove it names the exact retained cohort."""
    evidence_path = path.resolve(strict=True)
    evidence = DistributionEvidence.model_validate_json(evidence_path.read_text(encoding=_UTF_8))
    if cohort_directory is not None:
        expected = bind_cohort(load_release_cohort(cohort_directory))
        if evidence.cohort != expected:
            raise ValueError("distribution evidence does not bind the supplied release cohort")
    return evidence


class PackagingSmokeManifest(BaseModel):
    """One packaging-smoke lane's machine-readable run record.

    The single typed shape shared by every ``smoke_*.py`` writer (via
    ``dev.packaging._smoke_common.write_smoke_manifest``) and by every reader that
    decides whether a manifest reports a genuine successful run
    (:func:`checkpoint_smoke_evidence`,
    :func:`dev.release.readiness.check_latest_packaging_smoke_evidence`). A
    manifest that fails this schema — a non-boolean ``ok``, an empty ``lane``, or
    a naive ``completed_at`` — is not evidence, regardless of what its raw JSON
    claims.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    ok: bool
    lane: str = Field(min_length=1)
    completed_at: datetime
    work_dir: str = Field(min_length=1)
    artifacts: Mapping[str, str] = Field(default_factory=dict)
    checks: tuple[str, ...] = Field(default_factory=tuple)
    details: Mapping[str, JsonValue] | None = None

    @model_validator(mode="after")
    def _timezone_aware(self) -> Self:
        if self.completed_at.tzinfo is None or self.completed_at.utcoffset() is None:
            raise ValueError("packaging smoke manifest completed_at must carry a timezone")
        return self


def checkpoint_smoke_evidence(
    smoke_root: Path,
    evidence_root: Path,
    *,
    prune_completed: bool,
) -> tuple[Path, ...]:
    """Copy direct-child manifests and optionally remove their completed work dirs.

    Looking up only the known manifest leaf avoids recursively traversing secure
    runtime directories created by container probes. A work directory is pruned
    only after its manifest has been validated and atomically checkpointed, so failed or
    incomplete runs remain available for diagnosis.
    """
    if not smoke_root.is_dir():
        return ()

    evidence_root.mkdir(parents=True, exist_ok=True)
    checkpointed: list[Path] = []
    for work_dir in scan_directory(smoke_root, select=DirectoryEntryKind.DIRECTORIES):
        manifest = work_dir / _MANIFEST_NAME
        if not manifest.is_file():
            continue
        payload = manifest.read_bytes()
        document = json.loads(payload)
        if not isinstance(document, dict) or document.get("ok") is not True:
            raise ValueError(f"packaging smoke manifest is not successful: {manifest}")

        target = evidence_root / f"{work_dir.name}.json"
        if target.exists():
            raise FileExistsError(f"packaging smoke evidence already exists: {target}")
        temporary = target.with_suffix(".json.tmp")
        temporary.write_bytes(payload)
        temporary.replace(target)
        checkpointed.append(target)
        if prune_completed:
            shutil.rmtree(work_dir)

    return tuple(checkpointed)


def main(argv: list[str] | None = None) -> int:
    """Checkpoint packaging-smoke evidence for CI artifact retention."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prune-completed",
        action="store_true",
        help="Remove only work directories whose successful manifest was checkpointed.",
    )
    args = parser.parse_args(argv)

    repo_root = REPO_ROOT
    smoke_root = repo_root / "var" / "packaging-smoke"
    evidence_root = repo_root / "var" / "packaging-smoke-evidence"
    checkpointed = checkpoint_smoke_evidence(
        smoke_root,
        evidence_root,
        prune_completed=args.prune_completed,
    )
    print(f"checkpointed packaging smoke manifests: {len(checkpointed)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
