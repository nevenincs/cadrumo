"""Runtime-owned console bootstrap composition for fresh-process product tests."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from cadrumo.tests.audited_process import run_audited_process
from cadrumo.tests.cli_fixture_ports import FreshCliResult
from cadrumo.tests.subprocess_cli import as_text_completed_process, subprocess_cli_env

_CONSOLE_SOURCE = """
import json, os, sys
program_name = os.environ.get("CADRUMO_TEST_PROGRAM_NAME")
if program_name is not None:
    sys.argv[0] = program_name
from cadrumo_runtime.host.frontend.cli.bootstrap import main
try:
    main()
finally:
    report = os.environ.get("CADRUMO_TEST_IMPORT_REPORT")
    if report is not None:
        watched = json.loads(os.environ["CADRUMO_TEST_WATCHED_MODULES"])
        with open(report, "w", encoding="utf-8") as stream:
            json.dump(sorted(name for name in watched if name in sys.modules), stream)
"""


def run_fresh_cli(
    args: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    env_strip_prefixes: Sequence[str] = ("AEAT_", "PYTEST_"),
    extra_env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    program_name: str | None = None,
    watched_modules: Sequence[str] = (),
    import_report: Path | None = None,
    site_dir: Path | None = None,
) -> FreshCliResult:
    """Execute the real console bootstrap and validate its optional import report."""
    if env is not None and extra_env is not None:
        raise ValueError("exact env and extra_env cannot be combined")
    child_env = dict(env) if env is not None else subprocess_cli_env(strip_prefixes=env_strip_prefixes, extra=extra_env)
    if watched_modules and import_report is None:
        raise ValueError("watched modules require an import report path")
    # These controls are private to this invocation, even with an exact env.
    child_env.pop("CADRUMO_TEST_PROGRAM_NAME", None)
    if program_name is not None:
        child_env["CADRUMO_TEST_PROGRAM_NAME"] = program_name
    child_env.pop("CADRUMO_TEST_IMPORT_REPORT", None)
    child_env.pop("CADRUMO_TEST_WATCHED_MODULES", None)
    if import_report is not None:
        if import_report.exists():
            raise ValueError("the import report must not already exist")
        child_env["CADRUMO_TEST_IMPORT_REPORT"] = str(import_report)
        child_env["CADRUMO_TEST_WATCHED_MODULES"] = json.dumps(tuple(watched_modules))
    if site_dir is not None:
        child_env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(site_dir), child_env.get("PYTHONPATH"))))
    completed = as_text_completed_process(
        run_audited_process(
            [sys.executable, "-c", _CONSOLE_SOURCE, *args],
            env=child_env,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=None,
            check=False,
        )
    )
    loaded: tuple[str, ...] = ()
    if import_report is not None:
        observed: object = json.loads(import_report.read_text(encoding="utf-8"))
        if not isinstance(observed, list) or not all(isinstance(name, str) for name in observed):
            raise TypeError("the import report must contain a list of module names")
        loaded = tuple(str(name) for name in observed)
        if loaded != tuple(sorted(set(loaded))) or not set(loaded).issubset(watched_modules):
            raise ValueError("the import report contains unexpected module names or ordering")
    return FreshCliResult(completed, loaded)
