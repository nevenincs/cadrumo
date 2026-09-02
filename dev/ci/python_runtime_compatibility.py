"""Run one isolated Python-runtime compatibility probe.

The compatibility workflow deliberately has two installation modes.  ``source``
builds an sdist (and the two mandatory data companions) from one source snapshot;
``binary`` installs the already sealed Python cohort.  The modes share the
installed import/CLI probes, but never share an installation or a verdict.  A
binary-wheel failure therefore remains a binary-wheel failure even when the
same runtime can install the source distribution.

The command emits one JSON document on both success and failure.  The document
contains the selected interpreter's observed identity, the lock digest used by
the install, and the exact artifact digests.  It is intentionally independent
of the release-cohort builder: compatibility runs consume a cohort and never
rebuild or restamp it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import sys
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, cast

from .._paths import REPO_ROOT, UTF_8
from ..packaging._command import CommandResult, run_command
from ..packaging._hashing import sha256_path
from ..packaging._smoke_common import (
    build_companion_wheels,
    build_sdist,
    clean_product_env,
    commit_defined_build_root,
    require_executable,
    resolve_work_dir,
    venv_bin_dir,
    venv_cadrumo_path,
    venv_python_path,
)
from ..packaging.python_cohort import digest_install_target, load_python_cohort

_UTF_8: Final[str] = UTF_8
_SCHEMA: Final[str] = "cadrumo.python-runtime-compatibility.v1"
_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_VERSION_RE: Final[re.Pattern[str]] = re.compile(r"^3\.(?P<minor>[0-9]+)")
_DEFAULT_BUILDER_PIN: Final[Path] = REPO_ROOT / ".python-version"
_MISSING_WHEEL_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\bno solution found\b"),
    re.compile(r"\bno matching distribution\b"),
    re.compile(r"\bno compatible wheels?\b"),
    re.compile(r"\bcould not find a version\b"),
    re.compile(r"\bno wheels? (?:are|were) available\b"),
)


class ProbeMode(StrEnum):
    """The two separately attributable installation modes."""

    SOURCE = "source"
    BINARY = "binary"


class ProbeStatus(StrEnum):
    """Closed compatibility verdicts; there is deliberately no ``skipped``."""

    PASSED = "passed"
    FAILED = "failed"


class DependencyStatus(StrEnum):
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
            stdout_sha256=hashlib.sha256(result.stdout.encode(_UTF_8)).hexdigest(),
            stderr_sha256=hashlib.sha256(result.stderr.encode(_UTF_8)).hexdigest(),
        )


@dataclass(frozen=True, slots=True)
class FocusedTestEvidence:
    """One named target-runtime behavior test and its subprocess evidence."""

    name: str
    status: str
    command: CommandEvidence
    detail: str | None = None


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
    source_commit: str | None
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
        if self.schema != _SCHEMA:
            raise CompatibilityProbeError(f"unsupported compatibility evidence schema: {self.schema!r}")
        if self.mode not in {item.value for item in ProbeMode}:
            raise CompatibilityProbeError(f"invalid compatibility mode: {self.mode!r}")
        if self.status not in {item.value for item in ProbeStatus}:
            raise CompatibilityProbeError(f"invalid compatibility status: {self.status!r}")
        if self.stability not in {"stable", "prerelease"}:
            raise CompatibilityProbeError(f"invalid runtime stability: {self.stability!r}")
        for name, digest in (("lock_sha256", self.lock_sha256), ("artifact_sha256", self.artifact_sha256)):
            if _SHA256_RE.fullmatch(digest) is None:
                raise CompatibilityProbeError(f"{name} must be a lowercase SHA-256 digest")
        if any(_SHA256_RE.fullmatch(digest) is None for digest in self.artifact_digests.values()):
            raise CompatibilityProbeError("artifact_digests contains an invalid SHA-256 digest")
        if self.status == ProbeStatus.PASSED.value and self.failure is not None:
            raise CompatibilityProbeError("passing compatibility evidence cannot contain a failure")
        if self.status == ProbeStatus.FAILED.value and not self.failure:
            raise CompatibilityProbeError("failed compatibility evidence must name its failure")
        if self.dependency.get("status") == "skipped":
            raise CompatibilityProbeError("compatibility dependency evidence cannot be skipped")
        names = tuple(test.name for test in self.focused_tests)
        if any(not name for name in names) or len(names) != len(set(names)):
            raise CompatibilityProbeError("focused runtime tests must have unique non-empty names")
        if any(test.status not in {item.value for item in FocusedTestStatus} for test in self.focused_tests):
            raise CompatibilityProbeError("focused runtime tests have an invalid status")
        if self.status == ProbeStatus.PASSED.value:
            if not self.focused_tests:
                raise CompatibilityProbeError("passing compatibility evidence must include focused runtime tests")
            if any(test.status != FocusedTestStatus.PASSED.value for test in self.focused_tests):
                raise CompatibilityProbeError("passing compatibility evidence cannot contain a failed focused test")

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON data suitable for workflow artifact upload."""
        return cast(dict[str, object], asdict(self))


def _digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(_UTF_8)


def _canonical_artifact_digest(artifacts: Mapping[str, str]) -> str:
    """Hash an artifact-name/digest projection when a mode has several artifacts."""
    return _digest_bytes(_json_bytes(dict(sorted(artifacts.items()))))


def _read_lock_digest(path: Path) -> str:
    """Hash the exact lock bytes associated with the source or sealed cohort."""
    try:
        return sha256_path(path.resolve(strict=True))
    except OSError as exc:
        raise CompatibilityProbeError(f"uv.lock is unavailable: {path}", category="lock-missing") from exc


def _cohort_lock_digest(cohort: Any) -> str:
    """Read the lock digest from the cohort's sealed wheelhouse manifest."""
    value = cohort.runtime_wheelhouse_manifest.get("lock_sha256")
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise CompatibilityProbeError("Python cohort does not carry a valid lock digest", category="cohort-invalid")
    with zipfile.ZipFile(cohort.source_archive) as archive:
        try:
            source_lock_digest = _digest_bytes(archive.read("uv.lock"))
        except KeyError as exc:
            raise CompatibilityProbeError(
                "Python cohort source archive omits uv.lock",
                category="cohort-invalid",
            ) from exc
    if source_lock_digest != value:
        raise CompatibilityProbeError(
            "Python cohort wheelhouse lock digest disagrees with its source archive",
            category="cohort-invalid",
        )
    return value


def _builder_pin(repo_root: Path) -> str:
    """Return the exact release-builder interpreter identity, if declared."""
    try:
        value = (
            (_DEFAULT_BUILDER_PIN if repo_root == REPO_ROOT else repo_root / ".python-version")
            .read_text(
                encoding=_UTF_8,
            )
            .strip()
        )
    except OSError as exc:
        raise CompatibilityProbeError(".python-version is unavailable", category="builder-identity-missing") from exc
    if not value:
        raise CompatibilityProbeError(".python-version is empty", category="builder-identity-missing")
    return value


def _runtime_identity(python: Path, *, runtime_id: str, selector: str, stability: str, cwd: Path) -> dict[str, str]:
    """Ask the selected interpreter for its identity, never trusting the host process."""
    code = (
        "import json,platform,sys; "
        "print(json.dumps({'python': platform.python_version(), "
        "'implementation': platform.python_implementation(), "
        "'platform': sys.platform, 'machine': platform.machine()}, sort_keys=True))"
    )
    env = _isolated_environment(cwd, python.parent)
    result = run_command((str(python), "-I", "-W", "error::DeprecationWarning", "-c", code), cwd=cwd, environment=env)
    if result.returncode != 0:
        raise CompatibilityProbeError(
            f"selected interpreter identity probe failed: {result.stderr.strip() or result.stdout.strip()}",
            category="runtime-probe-failed",
        )
    try:
        identity = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CompatibilityProbeError(
            "selected interpreter identity was not JSON",
            category="runtime-probe-failed",
        ) from exc
    if not isinstance(identity, dict):
        raise CompatibilityProbeError(
            "selected interpreter identity was not an object",
            category="runtime-probe-failed",
        )
    observed_python = identity.get("python")
    implementation = identity.get("implementation")
    if not isinstance(observed_python, str) or not isinstance(implementation, str):
        raise CompatibilityProbeError(
            "selected interpreter identity omitted Python fields",
            category="runtime-probe-failed",
        )
    if implementation != "CPython":
        raise CompatibilityProbeError(
            f"compatibility matrix requires CPython, got {implementation!r}",
            category="implementation-unsupported",
        )
    selector_match = _RUNTIME_VERSION_RE.match(selector)
    observed_match = _RUNTIME_VERSION_RE.match(observed_python)
    if (
        selector_match is None
        or observed_match is None
        or selector_match.group("minor") != observed_match.group("minor")
    ):
        raise CompatibilityProbeError(
            f"selected interpreter {observed_python!r} does not satisfy selector {selector!r}",
            category="runtime-identity-mismatch",
        )
    return {
        "id": runtime_id,
        "selector": selector,
        "python": observed_python,
        "implementation": implementation,
        "stability": stability,
        "platform": str(identity.get("platform", "")),
        "machine": str(identity.get("machine", "")),
    }


def _isolated_environment(work_dir: Path, executable_dir: Path) -> dict[str, str]:
    """Construct a child environment with checkout imports and ambient commands removed."""
    environment = clean_product_env()
    for name in (
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONUSERBASE",
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "CONDA_DEFAULT_ENV",
        "UV_PROJECT_ENVIRONMENT",
    ):
        environment.pop(name, None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PATH"] = str(executable_dir)
    environment["CADRUMO_COMPATIBILITY_WORK_DIR"] = str(work_dir.resolve())
    return environment


def _venv(uv: str, *, repo_root: Path, work_dir: Path, selector: str) -> tuple[Path, list[CommandEvidence]]:
    """Create one fresh target-runtime virtualenv and retain the command result."""
    environment = clean_product_env()
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
        environment.pop(name, None)
    venv = work_dir / "venv"
    result = run_command((uv, "venv", str(venv), "--python", selector), cwd=repo_root, environment=environment)
    command = CommandEvidence.from_result(result)
    if result.returncode != 0:
        raise CompatibilityProbeError(
            f"target virtualenv creation failed: {result.stderr.strip() or result.stdout.strip()}",
            category="runtime-provisioning-failed",
        )
    return venv, [command]


def _install(
    uv: str,
    *,
    repo_root: Path,
    work_dir: Path,
    venv: Path,
    artifacts: tuple[tuple[str, Path], ...],
    mode: ProbeMode,
) -> tuple[list[CommandEvidence], DependencyStatus, str | None]:
    """Install exact local artifacts, forcing wheels only in binary mode."""
    python = venv_python_path(venv)
    targets = tuple(digest_install_target(name, path) for name, path in artifacts)
    argv: list[str] = [uv, "pip", "install", "--python", str(python)]
    if mode is ProbeMode.BINARY:
        argv.extend(("--only-binary", ":all:"))
    argv.extend(targets)
    environment = clean_product_env()
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
        environment.pop(name, None)
    result = run_command(tuple(argv), cwd=repo_root, environment=environment)
    command = [CommandEvidence.from_result(result)]
    if result.returncode != 0:
        text = f"{result.stdout}\n{result.stderr}".lower()
        missing_wheel = mode is ProbeMode.BINARY and any(pattern.search(text) for pattern in _MISSING_WHEEL_PATTERNS)
        category = DependencyStatus.MISSING_WHEEL if missing_wheel else DependencyStatus.FAILED
        return command, category, result.stderr.strip()[-500:] or result.stdout.strip()[-500:] or "install failed"
    check = run_command(
        (uv, "pip", "check", "--python", str(python)),
        cwd=repo_root,
        environment=environment,
    )
    command.append(CommandEvidence.from_result(check))
    if check.returncode != 0:
        return command, DependencyStatus.FAILED, check.stderr.strip()[-500:] or "dependency check failed"
    return command, DependencyStatus.RESOLVED, None


def _installed_probe(venv: Path, *, work_dir: Path) -> tuple[list[CommandEvidence], dict[str, bool]]:
    """Prove package origins and CLI execution from the target venv outside checkout."""
    python = venv_python_path(venv)
    install_root = None
    for root in (venv / "Lib" / "site-packages", venv / "lib"):
        if root.is_dir():
            install_root = (
                root
                if root.name == "site-packages"
                else next(
                    (path for path in root.rglob("site-packages") if path.is_dir()),
                    None,
                )
            )
            if install_root is not None:
                break
    if install_root is None:
        # Windows has already been handled above; this message remains explicit
        # on unusual virtualenv layouts rather than silently weakening the probe.
        install_root = venv / ("Lib" / "site-packages" if os.name == "nt" else "lib")
    code = (
        "import json,sys; from pathlib import Path; import cadrumo; "
        "origins=[str(Path(m.__file__).resolve()) for n,m in sys.modules.items() "
        "if (n == 'cadrumo' or n.startswith('cadrumo.')) and getattr(m,'__file__',None)]; "
        "root=Path(sys.argv[1]).resolve(); "
        "assert origins and all(Path(p).is_relative_to(root) for p in origins), origins; "
        "assert not any(n == 'dev' or n.startswith('dev.') for n in sys.modules); "
        "print(json.dumps({'origins_inside':True,'checkout_imports_removed':True}, sort_keys=True))"
    )
    env = _isolated_environment(work_dir, venv_bin_dir(venv))
    result = run_command(
        (str(python), "-I", "-W", "error::DeprecationWarning", "-c", code, str(install_root)),
        cwd=work_dir,
        environment=env,
    )
    commands = [CommandEvidence.from_result(result)]
    if result.returncode != 0:
        raise CompatibilityProbeError(
            f"installed import probe failed: {result.stderr.strip() or result.stdout.strip()}",
            category="import-probe-failed",
        )
    cli = venv_cadrumo_path(venv)
    cli_result = run_command(
        (str(cli), "--version"),
        cwd=work_dir,
        environment=env,
    )
    commands.append(CommandEvidence.from_result(cli_result))
    if cli_result.returncode != 0:
        raise CompatibilityProbeError(
            f"installed CLI probe failed: {cli_result.stderr.strip() or cli_result.stdout.strip()}",
            category="cli-probe-failed",
        )
    if not cli_result.stdout.startswith("CADRUMO "):
        raise CompatibilityProbeError("installed CLI returned an invalid product identity", category="cli-probe-failed")
    return commands, {"checkout_imports_removed": True, "ambient_product_executables_removed": True}


def _load_binary_artifacts(
    cohort_dir: Path,
    *,
    repo_root: Path,
) -> tuple[Any, tuple[tuple[str, Path], ...], str, str, str | None]:
    """Load an existing Python cohort and return its exact install artifacts."""
    resolved = cohort_dir.resolve(strict=True)
    # The compatibility workflow normally receives the extracted Python cohort;
    # accepting a full release-cohort root is useful for local invocation and
    # lets us validate the wrapper's exact builder identity when it is present.
    python_dir = resolved / "python" if (resolved / "python" / "python-cohort.json").is_file() else resolved
    cohort = load_python_cohort(python_dir)
    lock_sha256 = _cohort_lock_digest(cohort)
    builder_python: str | None = None
    release_manifest = resolved / "release-cohort.json"
    if release_manifest.is_file():
        from ..packaging.cohort_manifest import load_release_cohort

        release = load_release_cohort(resolved)
        builder_python = release.manifest.builder.python
        expected = _builder_pin(repo_root)
        if builder_python != expected:
            raise CompatibilityProbeError(
                f"sealed release cohort builder drifted: expected {expected!r}, got {builder_python!r}",
                category="builder-identity-mismatch",
            )
    artifacts = (
        ("cadrumo", cohort.root_wheel),
        ("cadrumo-data-manuals", cohort.manuals_wheel),
        ("cadrumo-data-official", cohort.official_wheel),
    )
    digests = {
        name: cohort.sha256[key]
        for name, key in (
            ("cadrumo", "cadrumo"),
            ("cadrumo-data-manuals", "cadrumo-data-manuals"),
            ("cadrumo-data-official", "cadrumo-data-official"),
        )
    }
    return cohort, artifacts, lock_sha256, _canonical_artifact_digest(digests), builder_python


def _source_artifacts(
    repo_root: Path,
    work_dir: Path,
) -> tuple[tuple[tuple[str, Path], ...], str, dict[str, str], str | None]:
    """Build source artifacts from one commit-defined snapshot and hash them."""
    build_root = commit_defined_build_root(repo_root, work_dir / "source-snapshot")
    sdist = build_sdist(work_dir, require_executable("uv"), build_root=build_root)
    manuals, official = build_companion_wheels(work_dir, require_executable("uv"), build_root=build_root)
    artifacts = (
        ("cadrumo", sdist),
        ("cadrumo-data-manuals", manuals),
        ("cadrumo-data-official", official),
    )
    digests = {name: sha256_path(path) for name, path in artifacts}
    commit_result = run_command(
        (require_executable("git"), "rev-parse", "HEAD"),
        cwd=build_root,
        environment=clean_product_env(),
    )
    if commit_result.returncode != 0:
        raise CompatibilityProbeError("could not identify source commit", category="source-identity-missing")
    commit = commit_result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise CompatibilityProbeError(f"invalid source commit {commit!r}", category="source-identity-missing")
    return artifacts, _read_lock_digest(build_root / "uv.lock"), digests, commit


def run_probe(
    *,
    mode: ProbeMode | str,
    python: str,
    runtime_id: str,
    stability: str = "stable",
    repo_root: Path = REPO_ROOT,
    work_dir: Path,
    cohort_dir: Path | None = None,
) -> ProbeEvidence:
    """Run one mode-specific compatibility probe and return JSON evidence.

    A failed dependency installation is returned as a failed record rather than
    raised as a skip.  Provisioning and validation failures still return a
    record with placeholder digests only when the associated bytes could not be
    reached; the caller can therefore upload the failure and fail the job.
    """
    selected_mode = ProbeMode(mode)
    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    uv = require_executable("uv")
    commands: list[CommandEvidence] = []
    artifacts: tuple[tuple[str, Path], ...] = ()
    artifact_digests: dict[str, str] = {}
    lock_sha256 = _read_lock_digest(repo_root / "uv.lock")
    source_commit: str | None = None
    cohort_manifest_sha256: str | None = None
    builder_python: str | None = None
    artifact_sha256 = _digest_bytes(b"unavailable")
    dependency = {"status": DependencyStatus.FAILED.value, "detail": "probe did not reach installation"}
    isolation = {"checkout_imports_removed": False, "ambient_product_executables_removed": False}
    failure: dict[str, str] | None = None
    runtime: dict[str, str] = {
        "id": runtime_id,
        "selector": python,
        "python": "unknown",
        "implementation": "unknown",
        "stability": stability,
        "platform": platform.system(),
        "machine": platform.machine(),
    }
    try:
        if selected_mode is ProbeMode.SOURCE:
            artifacts, lock_sha256, artifact_digests, source_commit = _source_artifacts(repo_root, work_dir)
            artifact_sha256 = _canonical_artifact_digest(artifact_digests)
        else:
            if cohort_dir is None:
                raise CompatibilityProbeError("binary mode requires --cohort-dir", category="cohort-missing")
            cohort, artifacts, lock_sha256, artifact_sha256, builder_python = _load_binary_artifacts(
                cohort_dir,
                repo_root=repo_root,
            )
            artifact_digests = {
                name: cohort.sha256[key]
                for name, key in (
                    ("cadrumo", "cadrumo"),
                    ("cadrumo-data-manuals", "cadrumo-data-manuals"),
                    ("cadrumo-data-official", "cadrumo-data-official"),
                )
            }
            cohort_manifest_sha256 = sha256_path(cohort.manifest)
            source_commit = cohort.source_commit
        venv, created = _venv(uv, repo_root=repo_root, work_dir=work_dir, selector=python)
        commands.extend(created)
        runtime = _runtime_identity(
            venv_python_path(venv),
            runtime_id=runtime_id,
            selector=python,
            stability=stability,
            cwd=work_dir,
        )
        install_commands, dependency_status, dependency_detail = _install(
            uv,
            repo_root=repo_root,
            work_dir=work_dir,
            venv=venv,
            artifacts=artifacts,
            mode=selected_mode,
        )
        commands.extend(install_commands)
        dependency = {"status": dependency_status.value, "detail": dependency_detail or "resolved"}
        if dependency_status is not DependencyStatus.RESOLVED:
            raise CompatibilityProbeError(
                dependency_detail or "dependency installation failed",
                category=dependency_status.value,
            )
        probe_commands, isolation = _installed_probe(venv, work_dir=work_dir)
        commands.extend(probe_commands)
    except (CompatibilityProbeError, OSError, ValueError, SystemExit) as exc:
        category = exc.category if isinstance(exc, CompatibilityProbeError) else "probe-failure"
        failure = {"category": category, "detail": str(exc)}
    status = ProbeStatus.FAILED.value if failure is not None else ProbeStatus.PASSED.value
    return ProbeEvidence(
        schema=_SCHEMA,
        runtime=runtime,
        mode=selected_mode.value,
        status=status,
        stability=stability,
        lock_sha256=lock_sha256,
        artifact_sha256=artifact_sha256,
        artifact_digests=artifact_digests,
        source_commit=source_commit,
        cohort_manifest_sha256=cohort_manifest_sha256,
        builder_python=builder_python,
        dependency=dependency,
        isolation=isolation,
        commands=tuple(commands),
        failure=failure,
        observed_at=datetime.now(UTC).isoformat(),
    )


def write_probe_evidence(path: Path, evidence: ProbeEvidence) -> Path:
    """Write one immutable evidence document without replacing an earlier run."""
    destination = path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"compatibility evidence already exists: {destination}")
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(evidence.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    temporary.replace(destination)
    return destination


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode_positional", nargs="?", choices=tuple(item.value for item in ProbeMode))
    parser.add_argument("--mode", dest="mode_option", choices=tuple(item.value for item in ProbeMode))
    parser.add_argument("--python", default=None, help="Target interpreter path or uv Python selector.")
    parser.add_argument("--runtime-id", default=None)
    parser.add_argument(
        "--stability",
        "--phase",
        dest="stability",
        choices=("stable", "prerelease"),
        default="stable",
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--cohort-dir", type=Path, default=None)
    parser.add_argument("--evidence", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one selected compatibility mode and print its evidence JSON."""
    args = _parser().parse_args(argv)
    mode = args.mode_option or args.mode_positional
    if mode is None:
        print("compatibility probe requires --mode source|binary (or a mode positional)", file=sys.stderr)
        return 2
    repo_root = args.repo_root.resolve()
    selector = args.python or _builder_pin(repo_root)
    runtime_id = args.runtime_id or "cp" + selector.replace(".", "").replace("-", "").replace("+", "")
    work_dir = args.work_dir or (repo_root / "var" / "python-runtime-compatibility" / f"{runtime_id}-{mode}")
    try:
        work_dir = resolve_work_dir(repo_root, str(work_dir))
        evidence = run_probe(
            mode=mode,
            python=selector,
            runtime_id=runtime_id,
            stability=args.stability,
            repo_root=repo_root,
            work_dir=work_dir,
            cohort_dir=args.cohort_dir,
        )
        destination = args.evidence or work_dir / "compatibility-evidence.json"
        write_probe_evidence(destination, evidence)
    except (CompatibilityProbeError, FileExistsError, OSError, ValueError, SystemExit) as exc:
        # Even argument/provisioning failures should remain attributable.  A
        # fully formed failed record is emitted when the run reached run_probe;
        # parser/setup failures are reported plainly and return non-zero.
        print(f"compatibility probe failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(evidence.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if evidence.status == ProbeStatus.PASSED.value else 1


__all__ = [
    "CommandEvidence",
    "CompatibilityProbeError",
    "DependencyStatus",
    "ProbeEvidence",
    "ProbeMode",
    "ProbeStatus",
    "main",
    "run_probe",
    "write_probe_evidence",
]


if __name__ == "__main__":  # pragma: no cover - CLI dispatch
    raise SystemExit(main())
