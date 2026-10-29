"""Compare Windows packaged CLI discovery and TUI screen startup without private data.

Each observation starts a fresh process on disposable storage. OS caches remain
warm. The TUI probe imports the installed session and opens the real installation
list, opens its first form, returns and closes. It does not measure authenticated
Home loading, desktop terminal rendering or any remote operation.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, cast

from .caller_owned_root import consumer_environment
from .proof_support import package_identity

_TUI_PROBE = """
import time
started = time.perf_counter()
import asyncio
import json
import sys
from pathlib import Path
from cadrumo_runtime.host.frontend.tui import installed_session
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.installation.destination import InstallationScreen
from textual.widgets import DataTable

report = {
    'imports_seconds': time.perf_counter() - started,
    'imported_modules': len(sys.modules),
    'profile_executors_loaded': 'cadrumo.application.user_profile.profile_operation_execution' in sys.modules,
    'calendar_execution_loaded': 'cadrumo.application.overview.calendar' in sys.modules,
}

async def exercise():
    screen = InstallationScreen()
    app = ScreenHostApp(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        table = screen.query_one('#installation-acts', DataTable)
        assert table.row_count == len(screen.offered_acts) > 0
        report['screen_ready_seconds'] = time.perf_counter() - started
        opened = time.perf_counter()
        await pilot.press('enter')
        from cadrumo.entrypoints.tui.installation.act_screen import InstallationActScreen
        assert isinstance(app.screen, InstallationActScreen)
        report['form_open_seconds'] = time.perf_counter() - opened
        await pilot.press('escape')
        assert app.screen is screen
        assert screen.query_one('#installation-acts', DataTable) is table
        await pilot.press('escape')
    report['navigation_completed'] = True

asyncio.run(exercise())
Path(sys.argv[1]).write_text(json.dumps(report), encoding='utf-8')
"""


def measure(package: Path, scratch: Path) -> dict[str, Any]:
    """Run discovery commands and real Textual navigation in independent processes."""
    environment = consumer_environment(scratch / "storage", scratch / "secrets")
    executable = package / "bin" / "aeat.exe"
    results: dict[str, Any] = {}
    for name, arguments in (
        ("version", ["--version"]),
        ("help", ["--help"]),
        ("app_help", ["app", "--help"]),
        ("config_help", ["config", "--help"]),
        ("tui", ["-c", _TUI_PROBE, str(scratch / "tui.json")]),
    ):
        program = package / "python.exe" if name == "tui" else executable
        started = time.perf_counter()
        completed = subprocess.run(  # noqa: S603 -- explicit packaged programs and fixed scenarios; no shell.
            [str(program), *arguments],
            env=environment,
            capture_output=True,
            timeout=90,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        elapsed = time.perf_counter() - started
        if completed.returncode != 0:
            raise RuntimeError(f"{name} exited {completed.returncode}: {completed.stderr.decode('utf-8', 'replace')}")
        if name != "tui" and not completed.stdout.strip():
            raise RuntimeError(f"{name} produced no operator output")
        results[name] = {"process_seconds": elapsed}
        if name == "tui":
            results[name].update(json.loads((scratch / "tui.json").read_text(encoding="utf-8")))
    return results


def main() -> None:
    """Alternate package order and retain observations alongside their identities."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=3)
    arguments = parser.parse_args()
    if arguments.samples < 1:
        parser.error("--samples must be positive")
    packages = {name: getattr(arguments, name).resolve(strict=True) for name in ("baseline", "candidate")}
    identities = {name: package_identity(package) for name, package in packages.items()}
    report: dict[str, Any] = {"identities": identities, "samples": [], "os_cache": "not cleared"}
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    for sample in range(arguments.samples):
        order = ("baseline", "candidate") if sample % 2 == 0 else ("candidate", "baseline")
        for name in order:
            with tempfile.TemporaryDirectory(prefix="frontend-startup-", dir=arguments.output.parent) as temporary:
                observation = measure(packages[name], Path(temporary).resolve())
            if package_identity(packages[name]) != identities[name]:
                raise RuntimeError(f"{name} changed during measurement")
            report["samples"].append({"package": name, "sample": sample + 1, "measurements": observation})
            arguments.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report["samples"][-1]), flush=True)
    report["process_medians_seconds"] = _process_medians(packages, report["samples"])
    for name, package in packages.items():
        if package_identity(package) != identities[name]:
            raise RuntimeError(f"{name} changed during measurement")
    arguments.output.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _process_medians(packages: dict[str, Path], samples: list[dict[str, object]]) -> dict[str, dict[str, float]]:
    """Summarize elapsed process times for each package and scenario."""
    first = cast(dict[str, dict[str, object]], samples[0]["measurements"])
    return {
        name: {
            scenario: statistics.median(
                cast(float, cast(dict[str, dict[str, object]], sample["measurements"])[scenario]["process_seconds"])
                for sample in samples
                if sample["package"] == name
            )
            for scenario in first
        }
        for name in packages
    }


if __name__ == "__main__":
    main()
