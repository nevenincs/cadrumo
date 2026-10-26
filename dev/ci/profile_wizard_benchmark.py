"""Measure the real native wizard without retaining inputs or changing its authority.

Run with --output pointing at a new directory. Timings are inclusive and must
not be added across nested boundaries. Wall time is advisory on a shared host.
The existing journey exercises synthetic credentials and never contacts AEAT.
"""

from __future__ import annotations

import argparse
import cProfile
import functools
import inspect
import json
import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from dev._paths import REPO_ROOT
from dev.ci.modelo_runtime_benchmark import RuntimeBenchmarkRecorder, _patch_function_aliases, record_runtime_tree

_JOURNEY = "src/cadrumo_runtime/host/tests/frontend/tui/test_profile_wizard_native.py"
_CLI_JOURNEY = "src/cadrumo_runtime/host/tests/frontend/cli/test_censo_credentials_native.py"


def _observe(patch: pytest.MonkeyPatch, recorder: RuntimeBenchmarkRecorder, owner: Any, name: str, label: str) -> None:
    original = getattr(owner, name)
    if inspect.iscoroutinefunction(original):

        @functools.wraps(original)
        async def asynchronous(*args: Any, **kwargs: Any) -> Any:
            with recorder.measure(label, aggregate=True):
                return await original(*args, **kwargs)

        patch.setattr(owner, name, asynchronous)
    else:

        @functools.wraps(original)
        def synchronous(*args: Any, **kwargs: Any) -> Any:
            with recorder.measure(label, aggregate=True):
                return original(*args, **kwargs)

        patch.setattr(owner, name, synchronous)


def _observe_binding(patch: pytest.MonkeyPatch, recorder: RuntimeBenchmarkRecorder) -> None:
    from cadrumo.adapters.persistence.storage.custody.automation_profile import validate_automation_profile_binding

    @functools.wraps(validate_automation_profile_binding)
    def validate(*args: Any, **kwargs: Any) -> Any:
        with recorder.measure("custody.validate_binding", aggregate=True):
            return validate_automation_profile_binding(*args, **kwargs)

    _patch_function_aliases(patch, validate_automation_profile_binding, validate)


@contextmanager
def observe_worker(recorder: RuntimeBenchmarkRecorder) -> Generator[None]:
    """Count real durable writes and currentness reads inside the native worker."""
    from cadrumo.application.journal_repository import JournalRepositoryBase
    from cadrumo.application.user_profile import view_reader
    from cadrumo_runtime.adapters.worker_authorization_lease import WorkerAuthorizationLease
    from cadrumo_runtime.host.operation_host import ProfileWorkerOperationHost

    with pytest.MonkeyPatch.context() as patch:
        _observe_binding(patch, recorder)
        _observe(patch, recorder, os, "fsync", "storage.fsync")
        _observe(patch, recorder, JournalRepositoryBase, "_write_payload", "journal.write")
        _observe(patch, recorder, view_reader, "_build_overview_source", "profile.build_overview_source")
        _observe(patch, recorder, view_reader, "_paginate_source", "profile.paginate")
        _observe(patch, recorder, WorkerAuthorizationLease, "acquire", "authority.lease_acquire")
        _observe(patch, recorder, WorkerAuthorizationLease, "release", "authority.lease_release")
        _observe(patch, recorder, ProfileWorkerOperationHost, "_require_current_inventory", "worker.current_inventory")
        delivered = ProfileWorkerOperationHost.release_delivered_result

        @functools.wraps(delivered)
        def release(*args: Any, **kwargs: Any) -> Any:
            try:
                return delivered(*args, **kwargs)
            finally:
                recorder.flush()

        patch.setattr(ProfileWorkerOperationHost, "release_delivered_result", release)
        try:
            yield
        finally:
            recorder.flush()


@contextmanager
def observe_parent(recorder: RuntimeBenchmarkRecorder, output: Path, journey: ModuleType) -> Generator[None]:
    """Measure the existing journey and wrap real calls, preserving every result."""
    from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
    from cadrumo.entrypoints.tui.profile.overview import ProfileManagerScreen
    from cadrumo_client.transport.framing import VerifiedConnection
    from cadrumo_client.transport.frontend_client import FrontendClient
    from cadrumo_runtime.adapters.profile_worker import ProfileWorkerProcess
    from cadrumo_runtime.host.frontend.tui.profile.aeat_auth_client import AeatAuthClient
    from cadrumo_runtime.host.frontend.tui.profile.manager_client import ProfileManagerClientComposition
    from cadrumo_runtime.host.profile_host import RuntimeProfileHost

    script = output / "instrumented_worker.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
        "from pathlib import Path\n"
        "from dev.ci.profile_wizard_benchmark import observe_worker, RuntimeBenchmarkRecorder\n"
        "from cadrumo_runtime.host.worker import run\n"
        f"recorder = RuntimeBenchmarkRecorder(Path({str(output)!r}), role='worker')\n"
        "with observe_worker(recorder):\n"
        "    raise SystemExit(run())\n",
        encoding="utf-8",
    )
    with pytest.MonkeyPatch.context() as patch:
        _observe_binding(patch, recorder)
        construct = ProfileWorkerProcess.__init__

        @functools.wraps(construct)
        def worker(*args: Any, **kwargs: Any) -> Any:
            kwargs["worker_script"] = script
            with recorder.measure("startup.worker", aggregate=True):
                return construct(*args, **kwargs)

        patch.setattr(ProfileWorkerProcess, "__init__", worker)
        for owner, name, label in (
            (FrontendClient, "login_password", "startup.login"),
            (FrontendClient, "operation", "ipc.operation"),
            (FrontendClient, "contract", "ipc.contract"),
            (FrontendClient, "read_profile_view", "profile.collect_view"),
            (FrontendClient, "_collect_profile_view_page", "profile.view_page"),
            (RuntimeProfileHost, "facts", "authority.facts"),
            (AutomationControlStore, "enrollment_state", "custody.enrollment_state"),
            (AutomationControlStore, "profile_lock_state", "custody.profile_lock_state"),
            (ProfileManagerClientComposition, "_overview", "profile.overview"),
            (ProfileManagerClientComposition, "_field", "profile.save_field"),
            (ProfileManagerClientComposition, "_auth_field", "profile.save_auth_field"),
            (AeatAuthClient, "snapshot", "auth.snapshot"),
            (AeatAuthClient, "read_readiness", "auth.read_readiness"),
            (AeatAuthClient, "save", "auth.save"),
            (ProfileManagerScreen, "_redraw", "ui.redraw"),
            (ProfileManagerScreen, "apply_overview", "ui.apply_overview"),
        ):
            _observe(patch, recorder, owner, name, label)
        if hasattr(journey, "_walk"):
            _observe(patch, recorder, journey, "register_profile_through_installed_tui", "startup.registration")
            _observe(patch, recorder, journey, "_walk", "wizard.walk")
        if hasattr(journey, "_invoke"):
            invoke = journey._invoke
            invocation = 0

            @functools.wraps(invoke)
            def cli_invocation(*args: Any, **kwargs: Any) -> Any:
                nonlocal invocation
                invocation += 1
                with recorder.measure(f"cli.invocation.{invocation}"):
                    return invoke(*args, **kwargs)

            patch.setattr(journey, "_invoke", cli_invocation)
        exchange = VerifiedConnection.operation

        @functools.wraps(exchange)
        def operation(self: Any, request: Any, *args: Any, **kwargs: Any) -> Any:
            with recorder.measure("ipc." + type(request).__name__, aggregate=True):
                return exchange(self, request, *args, **kwargs)

        patch.setattr(VerifiedConnection, "operation", operation)
        scope = RuntimeProfileHost.scope
        profiled = False

        @functools.wraps(scope)
        def measured_scope(*args: Any, **kwargs: Any) -> Any:
            nonlocal profiled
            profile = None if profiled else cProfile.Profile(timer=time.thread_time)
            profiled = True
            with recorder.measure("authority.scope", aggregate=True):
                if profile is not None:
                    profile.enable()
                try:
                    result = scope(*args, **kwargs)
                finally:
                    if profile is not None:
                        profile.disable()
                        recorder.retain_profile(profile)
            if profile is not None:
                recorder._write(
                    {
                        "event": "scope_size",
                        "operations": len(result.operations),
                        "disclosures": len(result.disclosures),
                    }
                )
            return result

        patch.setattr(RuntimeProfileHost, "scope", measured_scope)
        if hasattr(journey, "_until"):
            until = journey._until
            started = time.perf_counter()
            previous = started

            @functools.wraps(until)
            async def milestone(*args: Any, **kwargs: Any) -> Any:
                nonlocal previous
                result = await until(*args, **kwargs)
                now = time.perf_counter()
                recorder._write(
                    {
                        "event": "milestone",
                        "stage": args[2],
                        "elapsed_seconds": now - started,
                        "step_seconds": now - previous,
                    }
                )
                previous = now
                recorder.flush()
                return result

            patch.setattr(journey, "_until", milestone)
        try:
            yield
        finally:
            recorder.flush()


class _BenchmarkPlugin:
    def __init__(self, output: Path) -> None:
        self.output = output
        self.case = 0

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item: pytest.Function) -> Generator[None]:
        self.case += 1
        output = self.output if self.case == 1 else self.output / f"case-{self.case}"
        if self.case > 1:
            output.mkdir()
        recorder = RuntimeBenchmarkRecorder(output, role="parent")
        recorder._write({"event": "case", "name": item.name})
        with (
            observe_parent(recorder, output, item.module),
            record_runtime_tree(recorder),
            recorder.measure("wizard.total"),
        ):
            yield


def summarize(output: Path, exit_code: int) -> None:
    """Retain final cumulative counters once per process, without double counting snapshots."""
    processes = []
    for path in sorted(output.rglob("*.jsonl")):
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        aggregates = [record for record in records if record["event"] == "aggregate"]
        processes.append(
            {
                "source": str(path.relative_to(output)),
                "totals": aggregates[-1]["boundaries"] if aggregates else {},
                "milestones": [record for record in records if record["event"] == "milestone"],
                "measurements": [
                    record for record in records if record["event"] in {"case", "scope_size", "process_tree", "finish"}
                ],
            }
        )
    (output / "summary.json").write_text(
        json.dumps(
            {
                "pytest_exit_code": exit_code,
                "notes": [
                    "Wall timings are advisory on this shared host; nested inclusive totals must not be added.",
                    "Synthetic profiles, real native IPC and encrypted persistence; no AEAT network request.",
                    "Instrumented source-runtime journey; not a packaged desktop or live-network latency benchmark.",
                ],
                "processes": processes,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """Run one real journey and retain safe, process-separated measurements."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--surface", choices=("tui", "cli"), default="tui")
    options = parser.parse_args()
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = pytest.main(
        [
            str(REPO_ROOT / (_JOURNEY if options.surface == "tui" else _CLI_JOURNEY)),
            "-q",
            "-n",
            "0",
            "-m",
            "integration and windows_only",
            "--maxfail=1",
        ],
        plugins=[_BenchmarkPlugin(output)],
    )
    summarize(output, int(result))
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
