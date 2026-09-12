"""The sole contributor-facing import-quality gate implementation.

The driver has one fixed order:

1. read and preflight the closed classification declared by Import Linter;
2. run Import Linter's complete native graph/contracts;
3. run the subordinate syntax/canonical/dynamic source checker.

Import Linter remains the only dependency-direction authority.  The
subordinate component is deliberately invoked here rather than exposed as a
second contributor verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8
from dev.exit_codes import FAILED, TOOL_BROKEN, TOOL_MISSING

from .import_checker import (
    Authority,
    CheckResult,
    Finding,
    ImportOccurrence,
    has_architectural_warning,
    read_authority,
)
from .import_health import build_import_health, render_import_health, unavailable_import_health

_DEFAULT_TIMEOUT_SECONDS: Final[float] = 300.0
_ROOT_ENV: Final[str] = "CADRUMO_IMPORT_GATE_ROOT"
_LINTER_ENV: Final[str] = "CADRUMO_IMPORT_GATE_LINT_IMPORTS"
_CHECKER_ENV: Final[str] = "CADRUMO_IMPORT_GATE_CHECKER"
_FORCE_CHECKER_EXCEPTION_ENV: Final[str] = "CADRUMO_IMPORT_GATE_FORCE_CHECKER_EXCEPTION"
_CHECKER_PATH: Final[Path] = Path(__file__).with_name("import_checker.py").resolve()
_LOAD_PROBE_MODULE: Final[str] = "dev.quality.import_load_probe"


@dataclass(frozen=True)
class ComponentResult:
    """Outcome of one ordered import-gate component."""

    name: str
    returncode: int
    output: str = ""


def run_import_linter(
    authority: Authority,
    executable: str | None = None,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> ComponentResult:
    """Run Import Linter's complete native graph/contracts once."""
    requested = executable or "lint-imports"
    resolved = shutil.which(requested)
    if resolved is None:
        return ComponentResult(
            "import-linter",
            TOOL_MISSING,
            f"[TOOL_MISSING] Import Linter executable {requested!r} is unavailable",
        )
    if timeout <= 0:
        return ComponentResult(
            "import-linter",
            TOOL_BROKEN,
            f"[TOOL_BROKEN] Import Linter timed out after {timeout:g}s",
        )

    environment = os.environ.copy()
    import_paths = [str(root.source_root) for root in authority.roots]
    existing = environment.get("PYTHONPATH")
    if existing:
        import_paths.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(import_paths))
    environment["PYTHONIOENCODING"] = UTF_8
    command = (
        resolved,
        "--config",
        str(authority.config_path),
        "--no-cache",
        "--no-logo",
    )
    try:
        completed = subprocess.run(  # noqa: S603 - resolved executable, fixed argv, no shell
            command,
            cwd=authority.repository,
            env=environment,
            capture_output=True,
            text=True,
            encoding=UTF_8,
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError:
        return ComponentResult(
            "import-linter",
            TOOL_MISSING,
            f"[TOOL_MISSING] Import Linter executable {requested!r} disappeared before execution",
        )
    except subprocess.TimeoutExpired as exc:
        return ComponentResult(
            "import-linter",
            TOOL_BROKEN,
            f"[TOOL_BROKEN] Import Linter timed out after {timeout:g}s: {exc}",
        )
    except OSError as exc:
        return ComponentResult("import-linter", TOOL_BROKEN, f"[TOOL_BROKEN] Import Linter could not run: {exc}")
    except Exception as exc:  # broad: a graph component exception must fail closed
        return ComponentResult("import-linter", TOOL_BROKEN, f"[TOOL_BROKEN] Import Linter aborted: {exc}")

    output = _combined_output(completed.stdout, completed.stderr)
    if completed.returncode == 0:
        returncode = FAILED if has_architectural_warning(output) else 0
    elif completed.returncode == FAILED:
        returncode = FAILED
    else:
        returncode = TOOL_BROKEN
    return ComponentResult("import-linter", returncode, output)


def run_subordinate(
    authority: Authority,
    force_exception: bool = False,
    *,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> tuple[ComponentResult, CheckResult]:
    """Run the subordinate checker as the final ordered component."""
    try:
        if force_exception:
            raise RuntimeError("forced subordinate checker exception")
        if timeout <= 0:
            return (
                ComponentResult(
                    "subordinate-checker",
                    TOOL_BROKEN,
                    f"[TOOL_BROKEN] subordinate checker timed out after {timeout:g}s",
                ),
                CheckResult((), 0),
            )
        requested = os.environ.get(_CHECKER_ENV) or sys.executable
        resolved = shutil.which(requested)
        if resolved is None:
            return (
                ComponentResult(
                    "subordinate-checker",
                    TOOL_MISSING,
                    f"[TOOL_MISSING] subordinate checker executable {requested!r} is unavailable",
                ),
                CheckResult((), 0),
            )
        environment = os.environ.copy()
        import_paths = [str(_CHECKER_PATH.parents[2]), *(str(root.source_root) for root in authority.roots)]
        existing = environment.get("PYTHONPATH")
        if existing:
            import_paths.append(existing)
        environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(import_paths))
        environment["PYTHONIOENCODING"] = UTF_8
        with tempfile.TemporaryDirectory(prefix="cadrumo-import-checker-") as temporary:
            report_path = Path(temporary) / "checker.json"
            command = (
                resolved,
                str(_CHECKER_PATH),
                "--internal",
                "--root",
                str(authority.repository),
                "--config",
                str(authority.config_path),
                "--report",
                str(report_path),
            )
            completed = subprocess.run(  # noqa: S603 - fixed interpreter and argv, no shell
                command,
                cwd=authority.repository,
                env=environment,
                capture_output=True,
                text=True,
                encoding=UTF_8,
                errors="replace",
                check=False,
                timeout=timeout,
            )
            checker_result = _read_checker_report(report_path, authority)
    except Exception as exc:  # broad: component boundary must fail closed
        if isinstance(exc, subprocess.TimeoutExpired):
            message = f"[TOOL_BROKEN] subordinate checker timed out after {timeout:g}s: {exc}"
        elif isinstance(exc, FileNotFoundError):
            message = f"[TOOL_MISSING] subordinate checker interpreter is unavailable: {exc}"
            return ComponentResult("subordinate-checker", TOOL_MISSING, message), CheckResult((), 0)
        elif force_exception:
            message = f"[INTERNAL_CHECKER] subordinate checker aborted: {exc}"
        else:
            message = f"[TOOL_BROKEN] subordinate checker could not run: {exc}"
        return ComponentResult(
            "subordinate-checker",
            TOOL_BROKEN,
            message,
        ), CheckResult((), 0)
    output = _combined_output(completed.stdout, completed.stderr)
    if any(finding.fatal for finding in checker_result.findings):
        return (
            ComponentResult(
                "subordinate-checker",
                TOOL_BROKEN,
                output or checker_result.render(authority.repository),
            ),
            checker_result,
        )
    if completed.returncode == 0:
        return (
            ComponentResult(
                "subordinate-checker",
                0,
                output or "subordinate import checker completed without diagnostics",
            ),
            checker_result,
        )
    if completed.returncode == FAILED:
        return ComponentResult("subordinate-checker", FAILED, output), checker_result
    return (
        ComponentResult(
            "subordinate-checker",
            TOOL_BROKEN,
            f"[TOOL_BROKEN] subordinate checker exited unexpectedly with {completed.returncode}\n{output}".rstrip(),
        ),
        checker_result,
    )


def run_loadability(
    authority: Authority,
    *,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> tuple[ComponentResult, dict[str, object]]:
    """Import every governed non-test module in an isolated process."""
    unavailable: dict[str, object] = {
        "attempted": 0,
        "failed": 0,
        "failures": [],
        "loaded": 0,
        "operational_error": "loadability evidence is unavailable",
        "root_cause_count": 0,
        "root_causes": [],
        "scope": "unavailable",
        "target_digest": None,
    }
    if timeout <= 0:
        unavailable["operational_error"] = f"loadability probe timed out after {timeout:g}s"
        return ComponentResult("loadability", TOOL_BROKEN, f"[TOOL_BROKEN] {unavailable['operational_error']}"), unavailable

    environment = os.environ.copy()
    import_paths = [str(authority.repository), *(str(root.source_root) for root in authority.roots)]
    existing = environment.get("PYTHONPATH")
    if existing:
        import_paths.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(import_paths))
    environment["PYTHONIOENCODING"] = UTF_8

    artifact_directory = os.environ.get("CADRUMO_DEV_ARTIFACTS_DIR")
    try:
        with tempfile.TemporaryDirectory(prefix="cadrumo-import-loadability-") as temporary:
            if artifact_directory:
                report_path = Path(artifact_directory).resolve() / "import-loadability.json"
                report_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                report_path = Path(temporary) / "import-loadability.json"
            command = (
                sys.executable,
                "-m",
                _LOAD_PROBE_MODULE,
                "--root",
                str(authority.repository),
                "--config",
                str(authority.config_path),
                "--report",
                str(report_path),
            )
            completed = subprocess.run(  # noqa: S603 - fixed interpreter and argv, no shell
                command,
                cwd=authority.repository,
                env=environment,
                capture_output=True,
                text=True,
                encoding=UTF_8,
                errors="replace",
                check=False,
                timeout=timeout,
            )
            payload = json.loads(report_path.read_text(encoding=UTF_8))
            if payload.get("schema_version") != 1:
                raise ValueError("unsupported loadability report schema")
            if artifact_directory:
                payload["artifact"] = str(report_path)
    except subprocess.TimeoutExpired as exc:
        unavailable["operational_error"] = f"loadability probe timed out after {timeout:g}s: {exc}"
        return ComponentResult("loadability", TOOL_BROKEN, f"[TOOL_BROKEN] {unavailable['operational_error']}"), unavailable
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        unavailable["operational_error"] = f"loadability evidence is unusable: {exc}"
        return ComponentResult("loadability", TOOL_BROKEN, f"[TOOL_BROKEN] {unavailable['operational_error']}"), unavailable

    output = _combined_output(completed.stdout, completed.stderr)
    if completed.returncode == 0:
        return ComponentResult("loadability", 0, output), payload
    if completed.returncode == FAILED:
        return ComponentResult("loadability", FAILED, output), payload
    payload["operational_error"] = f"loadability probe exited unexpectedly with {completed.returncode}"
    return ComponentResult("loadability", TOOL_BROKEN, output or str(payload["operational_error"])), payload


def _read_checker_report(path: Path, authority: Authority) -> CheckResult:
    """Load the complete child evidence or fail closed when it is unusable."""
    try:
        payload = json.loads(path.read_text(encoding=UTF_8))
        if payload.get("schema_version") != 2:
            raise ValueError("unsupported checker report schema")
        findings = tuple(
            Finding(
                category=str(item["category"]),
                message=str(item["message"]),
                path=(authority.repository / str(item["path"])).resolve() if item.get("path") else None,
                lineno=int(item["line"]) if item.get("line") is not None else None,
                fatal=bool(item.get("fatal", False)),
                advisory=bool(item.get("advisory", False)),
            )
            for item in payload.get("findings", ())
        )
        occurrences = tuple(
            ImportOccurrence(
                fingerprint=str(item["fingerprint"]),
                source_module=str(item["source_module"]),
                target_module=str(item["target_module"]),
                imported_symbols=tuple(str(symbol) for symbol in item.get("imported_symbols", ())),
                import_form=str(item["import_form"]),
                lexical_scope=str(item["lexical_scope"]),
                contract=str(item["contract"]),
                path=(authority.repository / str(item["location"]["path"])).resolve(),
                lineno=int(item["location"]["line"]),
            )
            for item in payload.get("occurrences", ())
        )
        files_scanned = int(payload["files_scanned"])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return CheckResult(
            (Finding("INTERNAL_CHECKER", f"checker evidence report is unusable: {exc}", fatal=True),),
            0,
        )
    return CheckResult(findings, files_scanned, occurrences)


def run_import_gate(
    repository: Path,
    config_path: Path | None = None,
    lint_executable: str | None = None,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> int:
    """Run the ordered authority, graph, and subordinate components."""
    try:
        read = read_authority(repository, config_path)
    except Exception as exc:  # broad: authority preflight must fail closed
        message = f"[AUTHORITY_PREFLIGHT] authority preflight aborted: {exc}"
        _emit_failure(
            [
                ComponentResult(
                    "authority-preflight",
                    TOOL_BROKEN,
                    message,
                )
            ]
        )
        _emit_health_payload(unavailable_import_health(message))
        return TOOL_BROKEN
    if read.authority is None:
        message = "\n".join(read.findings)
        _emit_failure(
            [ComponentResult("authority-preflight", TOOL_BROKEN, message)],
        )
        _emit_health_payload(unavailable_import_health(message))
        return TOOL_BROKEN

    authority = read.authority
    components: list[ComponentResult] = []
    if read.findings:
        components.append(ComponentResult("authority-preflight", TOOL_BROKEN, "\n".join(read.findings)))

    source_snapshot_before = _source_snapshot(authority)
    linter_started = time.perf_counter()
    linter = run_import_linter(authority, lint_executable, timeout)
    linter_seconds = time.perf_counter() - linter_started
    components.append(linter)
    checker_started = time.perf_counter()
    subordinate, subordinate_result = run_subordinate(
        authority,
        force_exception=os.environ.get(_FORCE_CHECKER_EXCEPTION_ENV) == "1",
        timeout=timeout,
    )
    checker_seconds = time.perf_counter() - checker_started
    components.append(subordinate)
    load_started = time.perf_counter()
    load_component, loadability = run_loadability(authority, timeout=timeout)
    load_seconds = time.perf_counter() - load_started
    components.append(load_component)
    source_snapshot_after = _source_snapshot(authority)

    health, exit_status = build_import_health(
        authority=authority,
        authority_findings=read.findings,
        linter_returncode=linter.returncode,
        linter_output=linter.output,
        checker=subordinate_result,
        loadability=loadability,
        load_returncode=load_component.returncode,
        source_snapshot_before=source_snapshot_before,
        source_snapshot_after=source_snapshot_after,
        component_durations={
            "import_linter": linter_seconds,
            "loadability": load_seconds,
            "subordinate_checker": checker_seconds,
        },
    )
    _emit_component_evidence(components)
    _emit_health_payload(health)
    return exit_status


def _combined_output(stdout: str | None, stderr: str | None) -> str:
    """Combine native streams without changing their text or encoding."""
    return "\n".join(part for part in (stdout or "", stderr or "") if part).strip()


def _source_snapshot(authority: Authority) -> str:
    """Fingerprint the governed inputs so concurrent mutation fails closed."""
    digest = hashlib.sha256()
    paths: set[Path] = {authority.config_path}
    for root in authority.roots:
        paths.update(root.path.rglob("*.py"))
    ratchet = authority.repository / "dev" / "quality" / "metadata" / "import_boundary_ratchet.json"
    if ratchet.is_file():
        paths.add(ratchet)
    for path in sorted(paths, key=lambda item: item.as_posix()):
        try:
            stat = path.stat()
            relative = path.relative_to(authority.repository).as_posix()
        except (OSError, ValueError) as exc:
            digest.update(f"unavailable:{path}:{exc}".encode(UTF_8))
            continue
        digest.update(f"{relative}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode(UTF_8))
    return digest.hexdigest()


def _emit_failure(components: list[ComponentResult]) -> None:
    """Replay only failing component diagnostics, retaining native output."""
    print("check-import-boundaries: failed")
    for component in components:
        if component.returncode == 0 or not component.output:
            continue
        label = {
            "authority-preflight": "AUTHORITY_PREFLIGHT",
            "import-linter": "GRAPH_AUTHORITY",
            "loadability": "LOADABILITY",
            "subordinate-checker": "SUBORDINATE_CHECKER",
        }.get(component.name, component.name.upper().replace("-", "_"))
        print(f"[{label}] exit {component.returncode}")
        print(component.output.rstrip())


def _emit_component_evidence(components: list[ComponentResult]) -> None:
    """Replay complete component evidence; the outer runner keeps it in the log."""
    for component in components:
        if not component.output:
            continue
        label = {
            "authority-preflight": "AUTHORITY_PREFLIGHT",
            "import-linter": "GRAPH_AUTHORITY",
            "loadability": "LOADABILITY",
            "subordinate-checker": "SUBORDINATE_CHECKER",
        }.get(component.name, component.name.upper().replace("-", "_"))
        print(f"[{label}] exit {component.returncode}")
        print(component.output.rstrip())


def _emit_health_payload(payload: dict[str, object]) -> None:
    """Emit the stable human and machine contracts together."""
    print(render_import_health(payload))
    print(json.dumps({"event": "import_health", **payload}, sort_keys=True, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    """Run the one import-quality verdict."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None, help="repository/source root for isolated proofs")
    parser.add_argument("--config", type=Path, default=None, help="Import Linter configuration path")
    parser.add_argument(
        "--lint-imports",
        dest="lint_executable",
        default=None,
        help="internal executable override used by failure-path tests",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=_DEFAULT_TIMEOUT_SECONDS,
        help="Import Linter timeout in seconds",
    )
    args = parser.parse_args(argv)
    env_root = os.environ.get(_ROOT_ENV)
    repository = args.root or (Path(env_root) if env_root else REPO_ROOT)
    lint_executable = args.lint_executable or os.environ.get(_LINTER_ENV)
    return run_import_gate(repository, args.config, lint_executable, args.timeout)


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "ComponentResult",
    "main",
    "run_import_gate",
    "run_import_linter",
    "run_loadability",
    "run_subordinate",
]
