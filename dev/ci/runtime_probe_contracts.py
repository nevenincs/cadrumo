"""Closed runtime compatibility evidence records and validation boundaries."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Final, TypedDict, cast

from dev._paths import UTF_8
from dev.packaging.command_execution import CommandResult
from dev.packaging.evidence import artifact_map_digest
from dev.packaging.hashing import sha256_text

_UTF_8: Final[str] = UTF_8


_SCHEMA: Final[str] = "cadrumo.python-runtime-compatibility.v1"


_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


def _validate_passing_focused_probe(evidence: ProbeEvidence) -> None:
    """Validate passing focused probe."""
    if evidence.status == ProbeStatus.PASSED.value:
        if not evidence.focused_tests:
            raise CompatibilityProbeError("passing compatibility evidence must include focused runtime tests")
        if any(test.status != FocusedTestStatus.PASSED.value for test in evidence.focused_tests):
            raise CompatibilityProbeError("passing compatibility evidence cannot contain a failed focused test")


def _validate_probe_identity(evidence: ProbeEvidence) -> None:
    """Validate probe identity."""
    if evidence.schema != _SCHEMA:
        raise CompatibilityProbeError(f"unsupported compatibility evidence schema: {evidence.schema!r}")
    if evidence.mode not in {item.value for item in ProbeMode}:
        raise CompatibilityProbeError(f"invalid compatibility mode: {evidence.mode!r}")
    if evidence.status not in {item.value for item in ProbeStatus}:
        raise CompatibilityProbeError(f"invalid compatibility status: {evidence.status!r}")
    if evidence.stability not in {"stable", "prerelease"}:
        raise CompatibilityProbeError(f"invalid runtime stability: {evidence.stability!r}")


def _validate_probe_artifacts(evidence: ProbeEvidence) -> None:
    """Validate probe artifacts."""
    for name, digest in (("lock_sha256", evidence.lock_sha256), ("artifact_sha256", evidence.artifact_sha256)):
        if _SHA256_RE.fullmatch(digest) is None:
            raise CompatibilityProbeError(f"{name} must be a lowercase SHA-256 digest")
    if any(_SHA256_RE.fullmatch(digest) is None for digest in evidence.artifact_digests.values()):
        raise CompatibilityProbeError("artifact_digests contains an invalid SHA-256 digest")
    if evidence.artifact_digests and evidence.artifact_sha256 != artifact_map_digest(evidence.artifact_digests):
        raise CompatibilityProbeError("artifact_sha256 must bind the canonical artifact digest map")


def _validate_probe_outcome(evidence: ProbeEvidence) -> None:
    """Validate probe outcome."""
    if evidence.status == ProbeStatus.PASSED.value and evidence.failure is not None:
        raise CompatibilityProbeError("passing compatibility evidence cannot contain a failure")
    if evidence.status == ProbeStatus.FAILED.value and not evidence.failure:
        raise CompatibilityProbeError("failed compatibility evidence must name its failure")
    if evidence.dependency.get("status") == "skipped":
        raise CompatibilityProbeError("compatibility dependency evidence cannot be skipped")


def _validate_binary_probe(evidence: ProbeEvidence) -> None:
    """Validate binary probe."""
    if evidence.mode == ProbeMode.BINARY.value and evidence.status == ProbeStatus.PASSED.value:
        if evidence.cohort_manifest_sha256 is None:
            raise CompatibilityProbeError("passing binary evidence must bind a cohort manifest")
        if "runtime-wheelhouse" not in evidence.artifact_digests:
            raise CompatibilityProbeError("passing binary evidence must bind the runtime wheelhouse bytes")
        if evidence.dependency.get("source") != "sealed-runtime-wheelhouse":
            raise CompatibilityProbeError("passing binary evidence must name the sealed wheelhouse source")
        if not re.fullmatch(r"3\.[0-9]+", evidence.dependency.get("wheelhouse_runtime", "")):
            raise CompatibilityProbeError("passing binary evidence must name the selected runtime wheelhouse")


def _validate_focused_probe(evidence: ProbeEvidence) -> None:
    """Validate focused probe."""
    names = tuple(test.name for test in evidence.focused_tests)
    if any(not name for name in names) or len(names) != len(set(names)):
        raise CompatibilityProbeError("focused runtime tests must have unique non-empty names")
    if any(test.status not in {item.value for item in FocusedTestStatus} for test in evidence.focused_tests):
        raise CompatibilityProbeError("focused runtime tests have an invalid status")
    _validate_passing_focused_probe(evidence)


class ProbeMode(StrEnum):
    """The two separately attributable installation modes."""

    SOURCE = "source"
    BINARY = "binary"


class ProbeStatus(StrEnum):
    """Closed compatibility verdicts; there is deliberately no ``skipped``."""

    PASSED = "passed"
    FAILED = "failed"


class PythonRuntimeDependencyStatus(StrEnum):
    """Dependency-resolution outcomes retained in the compatibility record."""

    RESOLVED = "resolved"
    MISSING_WHEEL = "missing-wheel"
    FAILED = "failed"


class FocusedTestStatus(StrEnum):
    """Outcomes for the small behavioral suite run by a target interpreter."""

    PASSED = "passed"
    FAILED = "failed"


class CompatibilityProbeError(RuntimeError):
    """A probe could not establish the requested compatibility claim."""

    def __init__(self, message: str, *, category: str = "probe-failure") -> None:
        """Create a failure carrying a machine-readable category."""
        super().__init__(message)
        self.category = category


@dataclass(frozen=True, slots=True)
class CommandEvidence:
    """Safe command projection retaining complete-stream digests."""

    argv: tuple[str, ...]
    cwd: str
    started_at: str
    completed_at: str
    exit_status: int
    stdout_sha256: str
    stderr_sha256: str

    @classmethod
    def from_result(cls, result: CommandResult) -> CommandEvidence:
        """Project one shared-runner result without retaining potentially sensitive output."""
        return cls(
            argv=result.argv,
            cwd=result.cwd,
            started_at=result.started_at.isoformat(),
            completed_at=result.completed_at.isoformat(),
            exit_status=result.returncode,
            stdout_sha256=sha256_text(result.stdout),
            stderr_sha256=sha256_text(result.stderr),
        )


@dataclass(frozen=True, slots=True)
class FocusedTestEvidence:
    """One named target-runtime behavior test and its subprocess evidence."""

    name: str
    status: str
    command: CommandEvidence
    detail: str | None = None


class ProbeEvidenceData(TypedDict):
    """The evidence record as plain data, field for field.

    `asdict` produces exactly these keys, so naming their types keeps a
    round trip through the mapping checkable: a caller that splats this
    back into :class:`ProbeEvidence` is verified per field rather than
    widened to `object` at every one.
    """

    schema: str
    runtime: dict[str, str]
    mode: str
    status: str
    stability: str
    lock_sha256: str
    artifact_sha256: str
    artifact_digests: dict[str, str]
    source_digest: str | None
    cohort_manifest_sha256: str | None
    builder_python: str | None
    dependency: dict[str, str]
    isolation: dict[str, bool]
    commands: tuple[CommandEvidence, ...]
    focused_tests: tuple[FocusedTestEvidence, ...]
    failure: dict[str, str] | None
    observed_at: str


@dataclass(frozen=True, slots=True)
class ProbeEvidence:
    """One immutable JSON-compatible compatibility verdict."""

    schema: str
    runtime: dict[str, str]
    mode: str
    status: str
    stability: str
    lock_sha256: str
    artifact_sha256: str
    artifact_digests: dict[str, str]
    source_digest: str | None
    cohort_manifest_sha256: str | None
    builder_python: str | None
    dependency: dict[str, str]
    isolation: dict[str, bool]
    commands: tuple[CommandEvidence, ...]
    focused_tests: tuple[FocusedTestEvidence, ...] = ()
    failure: dict[str, str] | None = None
    observed_at: str = ""

    def __post_init__(self) -> None:
        """Reject malformed records before they can be written or emitted."""
        _validate_probe_identity(self)
        _validate_probe_artifacts(self)
        _validate_probe_outcome(self)
        _validate_binary_probe(self)
        _validate_focused_probe(self)

    def to_dict(self) -> ProbeEvidenceData:
        """Return deterministic JSON data suitable for workflow artifact upload."""
        return cast(ProbeEvidenceData, asdict(self))
