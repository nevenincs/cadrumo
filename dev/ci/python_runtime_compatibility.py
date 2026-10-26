"""Run one isolated Python-runtime compatibility probe."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cadrumo.core.hashing import sha256_hex
from dev._paths import REPO_ROOT, UTF_8
from dev.packaging.evidence import artifact_map_digest
from dev.packaging.hashing import sha256_path
from dev.packaging.lane_verification_core import (
    require_executable,
    resolve_work_dir,
    venv_python_path,
)
from dev.packaging.runtime_wheelhouse_reader import extract_runtime_wheelhouse, load_runtime_wheelhouse

from .runtime_probe_artifacts import _cohort_digests, _load_binary_artifacts, _source_artifacts
from .runtime_probe_checks import _focused_runtime_tests, _installed_probe
from .runtime_probe_contracts import (
    _SCHEMA,
    CommandEvidence,
    CompatibilityProbeError,
    FocusedTestEvidence,
    ProbeEvidence,
    ProbeMode,
    ProbeStatus,
    PythonRuntimeDependencyStatus,
)
from .runtime_probe_identity import _builder_pin, _read_lock_digest, _runtime_identity
from .runtime_probe_installation import (
    _install,
    _runtime_minor,
    _select_runtime_wheelhouse,
    _venv,
    _wheelhouse_platform,
)


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
    wheelhouse_runtime: str | None = None
    wheelhouse_bundle: Any | None = None
    source_digest: str | None = None
    cohort_manifest_sha256: str | None = None
    builder_python: str | None = None
    artifact_sha256 = sha256_hex(b"unavailable")
    dependency = {
        "status": PythonRuntimeDependencyStatus.FAILED.value,
        "detail": "probe did not reach installation",
    }
    if selected_mode is ProbeMode.BINARY:
        dependency.update(
            {
                "source": "sealed-runtime-wheelhouse",
                "wheelhouse_platform": "unresolved",
                "wheelhouse_runtime": "unresolved",
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
            artifacts, lock_sha256, artifact_digests, source_digest = _source_artifacts(repo_root, work_dir)
            artifact_sha256 = artifact_map_digest(artifact_digests)
        else:
            if cohort_dir is None:
                raise CompatibilityProbeError("binary mode requires --cohort-dir", category="cohort-missing")
            cohort, artifacts, lock_sha256, artifact_sha256, builder_python = _load_binary_artifacts(
                cohort_dir,
                repo_root=repo_root,
            )
            artifact_digests = _cohort_digests(cohort)
            # ``load_python_cohort`` has already checked the source archive,
            # cohort manifest, and every wheelhouse member byte. Validate the
            # archive against the same lock digest once more at this handoff.
            # Runtime selection happens only after the target interpreter's
            # identity is observed below; a 3.13 wheel can never be presented
            # to a 3.14 installer by accident.
            wheelhouse_bundle = load_runtime_wheelhouse(
                cohort.runtime_wheelhouse,
                expected_lock_sha256=lock_sha256,
            )
            artifact_digests["runtime-wheelhouse"] = cohort.sha256["runtime-wheelhouse"]
            artifact_sha256 = artifact_map_digest(artifact_digests)
            cohort_manifest_sha256 = sha256_path(cohort.manifest)
            source_digest = cohort.source_digest
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
            # Bind failures to the observed target minor before selecting the
            # manifest entry.  This keeps an advisory missing-wheel verdict
            # attributable even when selection itself raises.
            wheelhouse_runtime = _runtime_minor(runtime)
            dependency["wheelhouse_runtime"] = wheelhouse_runtime
            wheelhouse_platform = _wheelhouse_platform(runtime)
            if wheelhouse_bundle is None:  # pragma: no cover - guarded by binary cohort setup
                raise CompatibilityProbeError(
                    "binary mode did not load its sealed runtime wheelhouse",
                    category="cohort-invalid",
                )
            wheelhouse_runtime, selected_wheelhouse = _select_runtime_wheelhouse(
                wheelhouse_bundle.manifest,
                runtime,
            )
            dependency["wheelhouse_runtime"] = wheelhouse_runtime
            wheelhouse_dir = work_dir / f"runtime-wheelhouse-{wheelhouse_runtime}"
            extract_runtime_wheelhouse(
                wheelhouse_bundle.archive,
                wheelhouse_dir,
                python_version=wheelhouse_runtime,
            )
            wheelhouse_manifest = selected_wheelhouse
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
        _require_resolved_dependencies(dependency_status, dependency_detail)
        probe_commands, isolation = _installed_probe(venv, work_dir=work_dir)
        commands.extend(probe_commands)
        focused_tests, focused_commands, focused_failure = _focused_runtime_tests(venv, work_dir=work_dir)
        commands.extend(focused_commands)
        if focused_failure is not None:
            raise CompatibilityProbeError(focused_failure, category="focused-test-failed")
    except (CompatibilityProbeError, OSError, ValueError, SystemExit) as exc:
        failure = _failed_probe_evidence(exc, dependency)
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
        source_digest=source_digest,
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
        encoding=UTF_8,
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


def _failed_probe_evidence(
    exc: CompatibilityProbeError | OSError | ValueError | SystemExit, dependency: dict[str, str]
) -> dict[str, str]:
    """Preserve missing-wheel attribution before projecting a failed probe."""
    category = exc.category if isinstance(exc, CompatibilityProbeError) else "probe-failure"
    if category == PythonRuntimeDependencyStatus.MISSING_WHEEL.value:
        dependency["status"] = PythonRuntimeDependencyStatus.MISSING_WHEEL.value
        dependency["detail"] = str(exc)
    failure = {"category": category, "detail": str(exc)}
    return failure


def _require_resolved_dependencies(
    dependency_status: PythonRuntimeDependencyStatus, dependency_detail: str | None
) -> None:
    """Refuse installed behavior probes until their dependency closure is resolved."""
    if dependency_status is not PythonRuntimeDependencyStatus.RESOLVED:
        raise CompatibilityProbeError(
            dependency_detail or "dependency installation failed",
            category=dependency_status.value,
        )


if __name__ == "__main__":  # pragma: no cover - CLI dispatch
    raise SystemExit(main())
