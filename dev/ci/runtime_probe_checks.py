"""Verify installed package origins, commands, and focused target-runtime behavior."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from dev.packaging.command_execution import run_command
from dev.packaging.lane_verification_core import (
    venv_bin_dir,
    venv_cadrumo_path,
    venv_python_path,
)

from .runtime_probe_contracts import CommandEvidence, CompatibilityProbeError, FocusedTestEvidence, FocusedTestStatus
from .runtime_probe_environment import _isolated_environment


def _installed_site_root(venv: Path) -> Path:
    """Installed site root."""
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
        install_root = (venv / "Lib" / "site-packages") if os.name == "nt" else (venv / "lib")
    return install_root


def _installed_probe(venv: Path, *, work_dir: Path) -> tuple[list[CommandEvidence], dict[str, bool]]:
    """Prove package origins and CLI execution from the target venv outside checkout."""
    python = venv_python_path(venv)
    install_root = _installed_site_root(venv)
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
    """Run the installed MCP command under the selected interpreter.

    The check runs from the target venv with the checkout absent from both
    ``sys.path`` and ``PATH``.  Invoking the installed console script exercises
    the package import and MCP entrypoint without duplicating application code in
    an inline Python program.
    """
    environment = _isolated_environment(work_dir, venv_bin_dir(venv))
    tests = (
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
