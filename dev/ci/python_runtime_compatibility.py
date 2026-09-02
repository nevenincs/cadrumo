"""Run one isolated Python-runtime compatibility probe.

The compatibility workflow deliberately has two installation modes.  ``source``
builds an sdist (and the two mandatory data companions) from one source snapshot;
``binary`` installs the already sealed Python cohort.  The modes share the
installed import/CLI/focused-behavior probes, but never share an installation or a verdict.  A
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
import subprocess
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
from ..packaging.runtime_wheelhouse import extract_runtime_wheelhouse, load_runtime_wheelhouse

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
_REQUIRED_FOCUSED_TESTS: Final[frozenset[str]] = frozenset(
    {
        "installed-package-behavior",
        "installed-cadrumo-mcp-help",
    },
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
        if self.artifact_digests and self.artifact_sha256 != _canonical_artifact_digest(self.artifact_digests):
            raise CompatibilityProbeError("artifact_sha256 must bind the canonical artifact digest map")
        if self.status == ProbeStatus.PASSED.value and self.failure is not None:
            raise CompatibilityProbeError("passing compatibility evidence cannot contain a failure")
        if self.status == ProbeStatus.FAILED.value and not self.failure:
            raise CompatibilityProbeError("failed compatibility evidence must name its failure")
        if self.dependency.get("status") == "skipped":
            raise CompatibilityProbeError("compatibility dependency evidence cannot be skipped")
        if self.mode == ProbeMode.BINARY.value and self.status == ProbeStatus.PASSED.value:
            if self.cohort_manifest_sha256 is None:
                raise CompatibilityProbeError("passing binary evidence must bind a cohort manifest")
            if "runtime-wheelhouse" not in self.artifact_digests:
                raise CompatibilityProbeError("passing binary evidence must bind the runtime wheelhouse bytes")
            if self.dependency.get("source") != "sealed-runtime-wheelhouse":
                raise CompatibilityProbeError("passing binary evidence must name the sealed wheelhouse source")
        names = tuple(test.name for test in self.focused_tests)
        if any(not name for name in names) or len(names) != len(set(names)):
            raise CompatibilityProbeError("focused runtime tests must have unique non-empty names")
        if any(test.status not in {item.value for item in FocusedTestStatus} for test in self.focused_tests):
            raise CompatibilityProbeError("focused runtime tests have an invalid status")
        if self.status == ProbeStatus.PASSED.value:
            if not self.focused_tests:
                raise CompatibilityProbeError("passing compatibility evidence must include focused runtime tests")
            if set(names) != _REQUIRED_FOCUSED_TESTS:
                raise CompatibilityProbeError(
                    "passing compatibility evidence must include the complete focused runtime test set",
                )
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


_RESOLVER_ENVIRONMENT: Final[tuple[str, ...]] = (
    "UV_DEFAULT_INDEX",
    "UV_EXTRA_INDEX_URL",
    "UV_FIND_LINKS",
    "UV_INDEX",
    "UV_INDEX_URL",
    "UV_NATIVE_TLS",
    "UV_NO_INDEX",
    "UV_OFFLINE",
    "UV_REQUEST_TIMEOUT",
    "PIP_EXTRA_INDEX_URL",
    "PIP_FIND_LINKS",
    "PIP_INDEX_URL",
    "PIP_NO_INDEX",
    "PIP_TRUSTED_HOST",
)


def _binary_environment() -> dict[str, str]:
    """Return an installer environment with every ambient resolver input removed.

    The command-line ``--offline --no-index`` switches are the authoritative
    closure, but ambient ``UV_*`` and ``PIP_*`` values must not be allowed to
    add another candidate source or change resolver behavior.  Keeping this
    scrub local to the binary installer also leaves source probes free to use
    their normal networked build path.
    """
    environment = clean_product_env()
    for name in _RESOLVER_ENVIRONMENT:
        environment.pop(name, None)
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
        environment.pop(name, None)
    return environment


def _wheelhouse_platform(runtime: Mapping[str, str]) -> str:
    """Map the selected interpreter identity to one sealed wheelhouse target."""
    operating_system = runtime.get("platform")
    machine = runtime.get("machine", "").lower().replace("-", "_")
    if operating_system == "linux":
        if machine in {"x86_64", "amd64"}:
            return "linux-x86-64"
        if machine in {"aarch64", "arm64"}:
            return "linux-aarch64"
    elif operating_system == "darwin" and machine in {"arm64", "aarch64"}:
        return "macos-arm64"
    elif operating_system in {"win32", "win64"} and machine in {"amd64", "x86_64"}:
        return "windows-x86-64"
    raise CompatibilityProbeError(
        f"sealed runtime wheelhouse has no target for {operating_system!r}/{machine!r}",
        category="platform-unsupported",
    )


def _binary_wheel_targets(
    wheelhouse_dir: Path,
    manifest: Mapping[str, Any],
    *,
    platform_target: str,
) -> tuple[str, ...]:
    """Return digest-pinned direct requirements for one sealed target closure.

    ``--find-links`` supplies the validated wheelhouse as the only candidate
    directory.  Direct requirements are still emitted for every platform-row
    wheel so ``--require-hashes`` constrains each installed dependency to the
    exact bytes recorded by the wheelhouse manifest, rather than merely proving
    that some compatible wheel happened to be found there.
    """
    platforms = manifest.get("platforms")
    wheels = manifest.get("wheels")
    rows = platforms.get(platform_target) if isinstance(platforms, Mapping) else None
    if not isinstance(rows, Mapping) or not rows:
        raise CompatibilityProbeError(
            f"sealed runtime wheelhouse has no dependency rows for {platform_target!r}",
            category="cohort-invalid",
        )
    if not isinstance(wheels, Mapping) or not wheels:
        raise CompatibilityProbeError(
            "sealed runtime wheelhouse declares no wheel records",
            category="cohort-invalid",
        )

    targets: list[str] = []
    for distribution, filename in sorted(rows.items(), key=lambda item: str(item[0])):
        if not isinstance(distribution, str) or not distribution or not isinstance(filename, str):
            raise CompatibilityProbeError(
                f"sealed runtime wheelhouse has an invalid {platform_target!r} row",
                category="cohort-invalid",
            )
        record = wheels.get(filename)
        if not isinstance(record, Mapping) or record.get("distribution") != distribution:
            raise CompatibilityProbeError(
                f"sealed runtime wheelhouse target swaps distribution bytes: {platform_target!r}/{distribution!r}",
                category="cohort-invalid",
            )
        expected_digest = record.get("sha256")
        expected_size = record.get("size")
        if (
            not isinstance(expected_digest, str)
            or _SHA256_RE.fullmatch(expected_digest) is None
            or not isinstance(expected_size, int)
            or expected_size < 0
        ):
            raise CompatibilityProbeError(
                f"sealed runtime wheelhouse wheel record is invalid: {filename!r}",
                category="cohort-invalid",
            )
        try:
            path = (wheelhouse_dir / filename).resolve(strict=True)
        except OSError as exc:
            raise CompatibilityProbeError(
                f"sealed runtime wheelhouse omitted {filename!r}",
                category="cohort-invalid",
            ) from exc
        if path.parent != wheelhouse_dir.resolve():
            raise CompatibilityProbeError(
                f"sealed runtime wheelhouse wheel escapes its extraction directory: {filename!r}",
                category="cohort-invalid",
            )
        if path.stat().st_size != expected_size or sha256_path(path) != expected_digest:
            raise CompatibilityProbeError(
                f"sealed runtime wheelhouse wheel bytes drifted: {filename!r}",
                category="cohort-invalid",
            )
        targets.append(digest_install_target(distribution, path))
    return tuple(targets)


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
    wheelhouse_dir: Path | None = None,
    wheelhouse_manifest: Mapping[str, Any] | None = None,
    wheelhouse_platform: str | None = None,
) -> tuple[list[CommandEvidence], DependencyStatus, str | None]:
    """Install exact artifacts, closing binary dependency resolution to the cohort.

    Source mode deliberately keeps its normal resolver behavior while binary
    mode is required to receive an extracted, manifest-validated wheelhouse.
    Every selected third-party wheel is passed as a digest-pinned direct
    requirement in addition to ``--find-links``.  This makes the wheelhouse
    directory the only candidate source and makes its recorded bytes the
    install constraint, rather than a post-install observation.
    """
    python = venv_python_path(venv)
    targets = tuple(digest_install_target(name, path) for name, path in artifacts)
    argv: list[str] = [uv, "pip", "install", "--python", str(python)]
    if mode is ProbeMode.BINARY:
        if wheelhouse_dir is None or wheelhouse_manifest is None or wheelhouse_platform is None:
            raise CompatibilityProbeError(
                "binary mode requires an extracted sealed runtime wheelhouse",
                category="cohort-invalid",
            )
        try:
            wheelhouse = wheelhouse_dir.resolve(strict=True)
        except OSError as exc:
            raise CompatibilityProbeError(
                f"sealed runtime wheelhouse extraction is unavailable: {wheelhouse_dir}",
                category="cohort-invalid",
            ) from exc
        if not wheelhouse.is_dir():
            raise CompatibilityProbeError(
                f"sealed runtime wheelhouse extraction is not a directory: {wheelhouse}",
                category="cohort-invalid",
            )
        targets += _binary_wheel_targets(
            wheelhouse,
            wheelhouse_manifest,
            platform_target=wheelhouse_platform,
        )
        argv.extend(
            (
                "--offline",
                "--no-index",
                "--find-links",
                str(wheelhouse),
                "--only-binary",
                ":all:",
                "--require-hashes",
            )
        )
    argv.extend(targets)
    environment = _binary_environment() if mode is ProbeMode.BINARY else clean_product_env()
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


def _mcp_executable_path(venv: Path) -> Path:
    """Return the installed MCP console-script path for one target venv."""
    executable = "cadrumo-mcp.exe" if os.name == "nt" else "cadrumo-mcp"
    return venv_bin_dir(venv) / executable


def _run_focused_test(
    name: str,
    argv: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    stdout_marker: str | None = None,
) -> FocusedTestEvidence:
    """Run one named target-runtime behavior test and retain its truthful result."""
    try:
        result = run_command(argv, cwd=cwd, environment=environment, timeout_seconds=120)
    except subprocess.TimeoutExpired as exc:
        raise CompatibilityProbeError(
            f"focused runtime test timed out after 120 seconds: {name}",
            category="focused-test-timeout",
        ) from exc
    detail: str | None = None
    passed = result.returncode == 0
    if passed and stdout_marker is not None and stdout_marker not in result.stdout:
        passed = False
        detail = f"expected stdout marker {stdout_marker!r} was absent"
    if not passed and detail is None:
        detail = result.stderr.strip()[-500:] or result.stdout.strip()[-500:] or "focused test failed"
    status = FocusedTestStatus.PASSED.value if passed else FocusedTestStatus.FAILED.value
    return FocusedTestEvidence(
        name=name,
        status=status,
        command=CommandEvidence.from_result(result),
        detail=detail,
    )


def _focused_runtime_tests(
    venv: Path,
    *,
    work_dir: Path,
) -> tuple[tuple[FocusedTestEvidence, ...], list[CommandEvidence], str | None]:
    """Run the small behavior suite under the selected interpreter.

    These checks intentionally run from the target venv with the checkout absent
    from both ``sys.path`` and ``PATH``.  The first command exercises the installed
    package's import/TOML behavior and the MCP module contract; the second invokes
    the actual installed ``cadrumo-mcp`` console script.  They are deliberately
    dependency-light and deterministic so every source and binary matrix row can
    execute the same focused set, including the advisory prerelease row.
    """
    python = venv_python_path(venv)
    environment = _isolated_environment(work_dir, venv_bin_dir(venv))
    behavior_code = (
        "import json\n"
        "import cadrumo\n"
        "import cadrumo_harness.mcp as mcp\n"
        "from cadrumo.core.toml import parse_toml_text\n"
        "parsed = parse_toml_text('value = 42\\n', error_factory=ValueError)\n"
        "assert parsed == {'value': 42}, parsed\n"
        "assert cadrumo.__version__\n"
        "assert callable(mcp.main) and callable(mcp.build_server)\n"
        "print(json.dumps({'runtime_behavior_ok': True}, sort_keys=True))\n"
    )
    tests = (
        _run_focused_test(
            "installed-package-behavior",
            (str(python), "-I", "-W", "error::DeprecationWarning", "-c", behavior_code),
            cwd=work_dir,
            environment=environment,
            stdout_marker="runtime_behavior_ok",
        ),
        _run_focused_test(
            "installed-cadrumo-mcp-help",
            (str(_mcp_executable_path(venv)), "--help"),
            cwd=work_dir,
            environment=environment,
            stdout_marker="usage:",
        ),
    )
    commands = [test.command for test in tests]
    failures = tuple(f"{test.name}: {test.detail or 'failed'}" for test in tests if test.status != "passed")
    return tests, commands, "; ".join(failures) if failures else None


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
    wheelhouse_dir: Path | None = None
    wheelhouse_manifest: Mapping[str, Any] | None = None
    wheelhouse_platform: str | None = None
    source_commit: str | None = None
    cohort_manifest_sha256: str | None = None
    builder_python: str | None = None
    artifact_sha256 = _digest_bytes(b"unavailable")
    dependency = {"status": DependencyStatus.FAILED.value, "detail": "probe did not reach installation"}
    if selected_mode is ProbeMode.BINARY:
        dependency.update(
            {
                "source": "sealed-runtime-wheelhouse",
                "wheelhouse_platform": "unresolved",
            }
        )
    isolation = {"checkout_imports_removed": False, "ambient_product_executables_removed": False}
    focused_tests: tuple[FocusedTestEvidence, ...] = ()
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
            # ``load_python_cohort`` has already checked the source archive,
            # cohort manifest, and wheelhouse member bytes.  Validate the
            # wheelhouse against the same lock digest once more at this
            # handoff, then extract it into the target run's private working
            # directory.  The installer receives only this extracted directory
            # and never gets a registry/index fallback.
            load_runtime_wheelhouse(
                cohort.runtime_wheelhouse,
                expected_lock_sha256=lock_sha256,
            )
            wheelhouse_dir = work_dir / "runtime-wheelhouse"
            wheelhouse = extract_runtime_wheelhouse(cohort.runtime_wheelhouse, wheelhouse_dir)
            wheelhouse_manifest = wheelhouse.manifest
            artifact_digests["runtime-wheelhouse"] = cohort.sha256["runtime-wheelhouse"]
            artifact_sha256 = _canonical_artifact_digest(artifact_digests)
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
        if selected_mode is ProbeMode.BINARY:
            wheelhouse_platform = _wheelhouse_platform(runtime)
            dependency["wheelhouse_platform"] = wheelhouse_platform
        install_commands, dependency_status, dependency_detail = _install(
            uv,
            repo_root=repo_root,
            work_dir=work_dir,
            venv=venv,
            artifacts=artifacts,
            mode=selected_mode,
            wheelhouse_dir=wheelhouse_dir,
            wheelhouse_manifest=wheelhouse_manifest,
            wheelhouse_platform=wheelhouse_platform,
        )
        commands.extend(install_commands)
        dependency = {
            **dependency,
            "status": dependency_status.value,
            "detail": dependency_detail or "resolved",
        }
        if dependency_status is not DependencyStatus.RESOLVED:
            raise CompatibilityProbeError(
                dependency_detail or "dependency installation failed",
                category=dependency_status.value,
            )
        probe_commands, isolation = _installed_probe(venv, work_dir=work_dir)
        commands.extend(probe_commands)
        focused_tests, focused_commands, focused_failure = _focused_runtime_tests(venv, work_dir=work_dir)
        commands.extend(focused_commands)
        if focused_failure is not None:
            raise CompatibilityProbeError(focused_failure, category="focused-test-failed")
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
        focused_tests=focused_tests,
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
    "FocusedTestEvidence",
    "FocusedTestStatus",
    "ProbeEvidence",
    "ProbeMode",
    "ProbeStatus",
    "main",
    "run_probe",
    "write_probe_evidence",
]


if __name__ == "__main__":  # pragma: no cover - CLI dispatch
    raise SystemExit(main())
