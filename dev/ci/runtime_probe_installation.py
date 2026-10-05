"""Install sealed or source artifacts and retain attributable dependency outcomes."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from dev.packaging.command_execution import CommandResult, run_command
from dev.packaging.hashing import sha256_path
from dev.packaging.lane_verification_core import (
    venv_python_path,
)
from dev.packaging.python_cohort import digest_install_target
from dev.product_environment import clean_product_env

from .runtime_probe_contracts import (
    _SHA256_RE,
    CommandEvidence,
    CompatibilityProbeError,
    ProbeMode,
    PythonRuntimeDependencyStatus,
)
from .runtime_probe_environment import _binary_environment

_OBSERVED_RUNTIME_VERSION_RE: Final[re.Pattern[str]] = re.compile(
    r"^3\.(?P<minor>[0-9]+)(?:\.[0-9]+)?(?:[._-]?(?:a|b|rc|dev)[0-9]+)?$"
)


_MISSING_WHEEL_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\bno solution found\b"),
    re.compile(r"\bno matching distribution\b"),
    re.compile(r"\bno compatible wheels?\b"),
    re.compile(r"\bcould not find a version\b"),
    re.compile(r"\bno wheels? (?:are|were) available\b"),
)


def _wheel_record_identity(
    distribution: str, filename: str, wheels: Mapping[str, Any], platform_target: str
) -> tuple[str, int]:
    """Wheel record identity."""
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
    return (expected_digest, expected_size)


def _bind_sealed_install_arguments(
    argv: list[str],
    wheelhouse_dir: Path | None,
    wheelhouse_manifest: Mapping[str, Any] | None,
    wheelhouse_platform: str | None,
    work_dir: Path,
    mode: ProbeMode,
    targets: tuple[str, ...],
) -> tuple[str, ...]:
    """Bind sealed install arguments."""
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
    return targets


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


def _runtime_minor(runtime: Mapping[str, str]) -> str:
    """Return the observed interpreter's canonical ``3.N`` wheelhouse key."""
    observed = runtime.get("python", "")
    match = _OBSERVED_RUNTIME_VERSION_RE.fullmatch(observed)
    if match is None:
        raise CompatibilityProbeError(
            f"selected interpreter reported an invalid Python version: {observed!r}",
            category="runtime-identity-mismatch",
        )
    return f"3.{int(match.group('minor'))}"


def _select_runtime_wheelhouse(
    manifest: Mapping[str, Any],
    runtime: Mapping[str, str],
) -> tuple[str, Mapping[str, Any]]:
    """Select the ready wheelhouse entry matching the observed CPython minor."""
    python_minor = _runtime_minor(runtime)
    runtimes = manifest.get("runtimes")
    entry = runtimes.get(python_minor) if isinstance(runtimes, Mapping) else None
    if not isinstance(entry, Mapping):
        raise CompatibilityProbeError(
            f"sealed runtime wheelhouse has no entry for Python {python_minor}",
            category="missing-wheel",
        )
    status = entry.get("status")
    if status == "missing-wheel":
        missing = entry.get("missing")
        details = (
            "; ".join(
                f"{item.get('distribution')} ({item.get('platform')}, {item.get('requirement')})"
                for item in missing
                if isinstance(item, Mapping)
            )
            if isinstance(missing, list)
            else "unattributed dependency closure"
        )
        raise CompatibilityProbeError(
            f"sealed runtime wheelhouse for Python {python_minor} is missing wheels: {details}",
            category="missing-wheel",
        )
    if status != "ready":
        raise CompatibilityProbeError(
            f"sealed runtime wheelhouse entry for Python {python_minor} is not ready",
            category="cohort-invalid",
        )
    return python_minor, entry


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
        _bind_binary_wheel_target(distribution, filename, wheels, platform_target, wheelhouse_dir, targets)
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
) -> tuple[list[CommandEvidence], PythonRuntimeDependencyStatus, str | None]:
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
    targets = _bind_sealed_install_arguments(
        argv, wheelhouse_dir, wheelhouse_manifest, wheelhouse_platform, work_dir, mode, targets
    )
    argv.extend(targets)
    environment = _binary_environment() if mode is ProbeMode.BINARY else clean_product_env()
    result = run_command(tuple(argv), cwd=repo_root, environment=environment)
    command = [CommandEvidence.from_result(result)]
    if result.returncode != 0:
        return _failed_install_evidence(mode, result, command)
    check = run_command(
        (uv, "pip", "check", "--python", str(python)),
        cwd=repo_root,
        environment=environment,
    )
    command.append(CommandEvidence.from_result(check))
    if check.returncode != 0:
        return command, PythonRuntimeDependencyStatus.FAILED, check.stderr.strip()[-500:] or "dependency check failed"
    return command, PythonRuntimeDependencyStatus.RESOLVED, None


def _bind_binary_wheel_target(
    distribution: object,
    filename: object,
    wheels: Mapping[str, Any],
    platform_target: str,
    wheelhouse_dir: Path,
    targets: list[str],
) -> None:
    """Bind binary wheel target."""
    if not isinstance(distribution, str) or not distribution or not isinstance(filename, str):
        raise CompatibilityProbeError(
            f"sealed runtime wheelhouse has an invalid {platform_target!r} row",
            category="cohort-invalid",
        )
    expected_digest, expected_size = _wheel_record_identity(distribution, filename, wheels, platform_target)
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


def _failed_install_evidence(
    mode: ProbeMode, result: CommandResult, command: list[CommandEvidence]
) -> tuple[list[CommandEvidence], PythonRuntimeDependencyStatus, str]:
    """Attribute a failed install by resolver diagnostics and retain its bounded detail."""
    text = f"{result.stdout}\n{result.stderr}".lower()
    missing_wheel = mode is ProbeMode.BINARY and any(pattern.search(text) for pattern in _MISSING_WHEEL_PATTERNS)
    category = PythonRuntimeDependencyStatus.MISSING_WHEEL if missing_wheel else PythonRuntimeDependencyStatus.FAILED
    return command, category, result.stderr.strip()[-500:] or result.stdout.strip()[-500:] or "install failed"
