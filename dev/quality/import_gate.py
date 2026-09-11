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
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8
from dev.exit_codes import FAILED, TOOL_BROKEN, TOOL_MISSING

from .import_checker import Authority, CheckResult, has_architectural_warning, read_authority

_DEFAULT_TIMEOUT_SECONDS: Final[float] = 300.0
_ROOT_ENV: Final[str] = "CADRUMO_IMPORT_GATE_ROOT"
_LINTER_ENV: Final[str] = "CADRUMO_IMPORT_GATE_LINT_IMPORTS"
_FORCE_CHECKER_EXCEPTION_ENV: Final[str] = "CADRUMO_IMPORT_GATE_FORCE_CHECKER_EXCEPTION"
_CHECKER_PATH: Final[Path] = Path(__file__).with_name("import_checker.py").resolve()


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

    environment = os.environ.copy()
    import_paths = [str(root.source_root) for root in authority.roots]
    existing = environment.get("PYTHONPATH")
    if existing:
        import_paths.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(import_paths))
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
        environment = os.environ.copy()
        import_paths = [str(_CHECKER_PATH.parents[2]), *(str(root.source_root) for root in authority.roots)]
        existing = environment.get("PYTHONPATH")
        if existing:
            import_paths.append(existing)
        environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(import_paths))
        command = (
            sys.executable,
            str(_CHECKER_PATH),
            "--root",
            str(authority.repository),
            "--config",
            str(authority.config_path),
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
    if completed.returncode == 0:
        return (
            ComponentResult(
                "subordinate-checker",
                0,
                output or "subordinate import checker completed without diagnostics",
            ),
            CheckResult((), 0),
        )
    if completed.returncode == FAILED:
        return ComponentResult("subordinate-checker", FAILED, output), CheckResult((), 0)
    return (
        ComponentResult(
            "subordinate-checker",
            TOOL_BROKEN,
            f"[TOOL_BROKEN] subordinate checker exited unexpectedly with {completed.returncode}\n{output}".rstrip(),
        ),
        CheckResult((), 0),
    )


def run_import_gate(
    repository: Path,
    config_path: Path | None = None,
    lint_executable: str | None = None,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> int:
    """Run the ordered authority, graph, and subordinate components."""
    read = read_authority(repository, config_path)
    if read.authority is None:
        _emit_failure(
            [ComponentResult("authority-preflight", TOOL_BROKEN, "\n".join(read.findings))],
        )
        return TOOL_BROKEN

    authority = read.authority
    components: list[ComponentResult] = []
    if read.findings:
        components.append(ComponentResult("authority-preflight", TOOL_BROKEN, "\n".join(read.findings)))

    linter = run_import_linter(authority, lint_executable, timeout)
    components.append(linter)
    subordinate, _ = run_subordinate(
        authority,
        force_exception=os.environ.get(_FORCE_CHECKER_EXCEPTION_ENV) == "1",
        timeout=timeout,
    )
    components.append(subordinate)

    failures = [component for component in components if component.returncode != 0]
    if failures:
        _emit_failure(components)
        return failures[0].returncode

    print("check-imports: passed")
    return 0


def _combined_output(stdout: str | None, stderr: str | None) -> str:
    """Combine native streams without changing their text or encoding."""
    return "\n".join(part for part in (stdout or "", stderr or "") if part).strip()


def _emit_failure(components: list[ComponentResult]) -> None:
    """Replay only failing component diagnostics, retaining native output."""
    print("check-imports: failed")
    for component in components:
        if component.returncode == 0 or not component.output:
            continue
        label = {
            "authority-preflight": "AUTHORITY_PREFLIGHT",
            "import-linter": "GRAPH_AUTHORITY",
            "subordinate-checker": "SUBORDINATE_CHECKER",
        }.get(component.name, component.name.upper().replace("-", "_"))
        print(f"[{label}] exit {component.returncode}")
        print(component.output.rstrip())


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
    "run_subordinate",
]
