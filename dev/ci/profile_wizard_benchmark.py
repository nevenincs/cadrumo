"""Measure the real native wizard without retaining inputs or changing its authority.

Run with --output pointing at a new directory. Timings are inclusive and must
not be added across nested boundaries. Wall time is advisory on a shared host.
The existing journey exercises synthetic credentials and never contacts AEAT.
Parent observer imports precede the journey clock; worker startup includes
the child observer imports. Compare identical instrumentation across revisions.
Custody unlock includes lease acquisition, worker supervision and sentinel proof;
individual child phases are not measured.
"""

from __future__ import annotations

import argparse
import cProfile
import functools
import inspect
import json
import math
import os
import sys
import time
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from pathlib import Path
from types import ModuleType
from typing import Any, Literal, override

import pytest

from dev._paths import REPO_ROOT
from dev.ci.modelo_runtime_benchmark import (
    RuntimeBenchmarkRecorder,
    _patch_function_aliases,
    _Total,
    record_runtime_tree,
)

_JOURNEY = "src/cadrumo_runtime/host/tests/frontend/tui/test_profile_wizard_native.py"
_CLI_JOURNEY = "src/cadrumo/entrypoints/cli/tests/test_censo_credentials_native.py"
_PROFILE_JOURNEY = "src/cadrumo/entrypoints/cli/tests/test_profile_io_native.py"
_ACTIVE_BOUNDARIES: ContextVar[tuple[str, ...]] = ContextVar("profile_benchmark_boundaries", default=())


class ProfileBenchmarkRecorder(RuntimeBenchmarkRecorder):
    """Retain per-call timing distributions in memory, without per-call I/O."""

    def __init__(self, output: Path, *, role: Literal["parent", "worker"]) -> None:
        """Bind process-local distributions to the existing safe recorder."""
        super().__init__(output, role=role)
        self.samples: dict[str, list[tuple[float, float, float]]] = {}
        self.timeline: list[dict[str, object]] = []

    @override
    @contextmanager
    def measure(self, boundary: str, *, payload_bytes: int | None = None, aggregate: bool = False) -> Generator[None]:
        """Observe nested scopes while preserving return and exception behavior."""
        token = _ACTIVE_BOUNDARIES.set((*_ACTIVE_BOUNDARIES.get(), boundary))
        try:
            with super().measure(boundary, payload_bytes=payload_bytes, aggregate=aggregate):
                yield
        finally:
            _ACTIVE_BOUNDARIES.reset(token)

    @override
    def _finish(self, boundary: str, call: int, outcome: str, sample: _Total, *, aggregate: bool) -> None:
        with self.lock:
            self.samples.setdefault(boundary, []).append(
                (sample.wall_seconds, sample.cpu_seconds, sample.thread_cpu_seconds)
            )
            if boundary.startswith(
                ("cli.invocation.", "startup.", "admission.", "kdf.", "custody.unlock")
            ) or boundary in {
                "journal.write",
                "storage.fsync",
                "profile.fact_write",
                "profile.record_replace",
                "profile.record_write_transaction",
                "storage.sql_commit.profile",
            }:
                self.timeline.append(
                    {
                        "boundary": boundary,
                        "call": call,
                        "outcome": outcome,
                        "finished_monotonic_seconds": time.perf_counter(),
                        "wall_seconds": sample.wall_seconds,
                        "cpu_seconds": sample.cpu_seconds,
                        "thread_cpu_seconds": sample.thread_cpu_seconds,
                    }
                )
            super()._finish(boundary, call, outcome, sample, aggregate=aggregate)

    @override
    def flush(self) -> None:
        """Publish the latest cumulative totals and sample distributions."""
        with self.lock:
            super().flush()
            distributions = {}
            for boundary, samples in self.samples.items():
                metrics: dict[str, object] = {"calls": len(samples)}
                for column, metric in enumerate(("wall_seconds", "cpu_seconds", "thread_cpu_seconds")):
                    ordered = sorted(sample[column] for sample in samples)
                    values = {"total": sum(ordered), "min": ordered[0], "max": ordered[-1]}
                    if len(ordered) >= 20:
                        values.update(
                            p50=ordered[math.ceil(len(ordered) * 0.5) - 1],
                            p95=ordered[math.ceil(len(ordered) * 0.95) - 1],
                        )
                    metrics[metric] = values
                distributions[boundary] = metrics
            self._write({"event": "distributions", "semantics": "cumulative", "boundaries": distributions})
            self._write({"event": "timeline", "semantics": "cumulative", "measurements": self.timeline})


def _observe_alias(
    patch: pytest.MonkeyPatch, recorder: RuntimeBenchmarkRecorder, owner: Any, name: str, label: str
) -> None:
    original = getattr(owner, name)
    replacement = recorder.wrap(original, label)
    for module_name, module in tuple(sys.modules.items()):
        if module_name.startswith(("cadrumo.", "cadrumo_runtime.")):
            for attribute, value in tuple(vars(module).items()):
                if value is original:
                    patch.setattr(module, attribute, replacement)


def _observe_profile_boundaries(patch: pytest.MonkeyPatch, recorder: RuntimeBenchmarkRecorder) -> None:
    """Observe real custody, record and SQLite commit owners in either process."""
    from sqlalchemy.orm import Session

    from cadrumo.adapters.persistence.storage.custody import kdf_supervision
    from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
    from cadrumo.application.user_profile.capsule_record import ProfileRecordStore
    from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
    from cadrumo_runtime.host.profile_login import ProfileWorkerHumanLogin

    for owner, name, label in (
        (ProfileWorkerHumanLogin, "authenticate", "admission.worker_password"),
        (ProfileWorkerHumanLogin, "bind", "admission.worker_bind"),
        (ProfileRecordRepository, "load", "profile.record_read"),
        (ProfileRecordRepository, "apply_fact_changes", "profile.fact_write"),
        (ProfileRecordStore, "replace", "profile.record_replace"),
        (ProfileRecordStore, "_write_with_event", "profile.record_write_transaction"),
        (SecureObjectRepository, "apply_batch", "storage.secure_batch"),
    ):
        _observe(patch, recorder, owner, name, label)
    _observe_alias(patch, recorder, kdf_supervision, "unlock_profile_custody", "custody.unlock")
    _observe_alias(
        patch, recorder, kdf_supervision, "unlock_profile_custody_password_material", "custody.unlock_password_material"
    )
    lease = kdf_supervision.profile_kdf_lease

    @functools.wraps(lease)
    @contextmanager
    def measured_lease(*args: Any, **kwargs: Any) -> Generator[None]:
        with ExitStack() as scope:
            with recorder.measure("kdf.lease_acquire", aggregate=True):
                scope.enter_context(lease(*args, **kwargs))
            yield

    _patch_function_aliases(patch, lease, measured_lease)
    commit = Session.commit

    @functools.wraps(commit)
    def commit_transaction(*args: Any, **kwargs: Any) -> Any:
        phase = "profile" if "profile.record_write_transaction" in _ACTIVE_BOUNDARIES.get() else "other"
        with recorder.measure("storage.sql_commit." + phase, aggregate=True):
            return commit(*args, **kwargs)

    patch.setattr(Session, "commit", commit_transaction)


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
        _observe_profile_boundaries(patch, recorder)
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
    from cadrumo_runtime.host.profile_connections import RuntimeProfileConnections
    from cadrumo_runtime.host.profile_host import RuntimeProfileHost

    script = output / "instrumented_worker.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
        "from pathlib import Path\n"
        "from dev.ci.profile_wizard_benchmark import observe_worker, ProfileBenchmarkRecorder\n"
        "from cadrumo_runtime.host.worker import run\n"
        f"recorder = ProfileBenchmarkRecorder(Path({str(output)!r}), role='worker')\n"
        "with observe_worker(recorder):\n"
        "    raise SystemExit(run())\n",
        encoding="utf-8",
    )
    with pytest.MonkeyPatch.context() as patch:
        _observe_profile_boundaries(patch, recorder)
        if sys.platform == "win32":
            from cadrumo_client.transport.windows import WindowsEndpoint
            from cadrumo_client.transport.windows_process import WindowsProcessScope

            _observe(patch, recorder, WindowsEndpoint, "connect", "startup.native_connect")
            _observe(patch, recorder, WindowsProcessScope, "launch", "startup.native_process_launch")
        _observe_binding(patch, recorder)
        construct = ProfileWorkerProcess.__init__

        @functools.wraps(construct)
        def worker(*args: Any, **kwargs: Any) -> Any:
            kwargs["worker_script"] = script
            with recorder.measure("startup.worker", aggregate=True):
                return construct(*args, **kwargs)

        patch.setattr(ProfileWorkerProcess, "__init__", worker)
        for owner, name, label in (
            (RuntimeProfileConnections, "_login", "admission.runtime_login"),
            (RuntimeProfileConnections, "_prepare", "admission.prepare"),
            (RuntimeProfileConnections, "_host", "admission.host"),
            (RuntimeProfileConnections, "prepare_registry", "startup.prepare_registry"),
            (RuntimeProfileConnections, "_admit_human_login", "admission.runtime_human"),
            (RuntimeProfileConnections, "_finish_login", "admission.finish"),
            (RuntimeProfileConnections, "_status", "admission.status"),
            (RuntimeProfileConnections, "_sign_out_other_profiles", "admission.sign_out_others"),
            (ProfileWorkerProcess, "_accept_startup_channel", "startup.accept_worker_channel"),
            (ProfileWorkerProcess, "_open_worker_channels", "startup.open_worker_channels"),
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
        recorder = ProfileBenchmarkRecorder(output, role="parent")
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
        distributions = [record for record in records if record["event"] == "distributions"]
        timeline = [record for record in records if record["event"] == "timeline"]
        processes.append(
            {
                "source": str(path.relative_to(output)),
                "totals": aggregates[-1]["boundaries"] if aggregates else {},
                "distributions": distributions[-1]["boundaries"] if distributions else {},
                "timeline": timeline[-1]["measurements"] if timeline else [],
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
                    "Parent observer imports precede clocks; worker startup includes child observer imports.",
                    "Custody unlock includes lease, worker supervision and sentinel proof; "
                    "child phases are not measured.",
                    "KDF lease acquisition includes thread and file acquisition; parent CPU excludes KDF child CPU.",
                    "SQLite commit includes configured durability; os.fsync excludes SQLite's native flushes.",
                    "Distributions are cumulative per process; p50/p95 use nearest rank only with at least 20 calls.",
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
    parser.add_argument("--surface", choices=("tui", "cli", "cli-profile"), default="tui")
    parser.add_argument("--case", help="Optional pytest name filter for a comparable isolated journey")
    options = parser.parse_args()
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = pytest.main(
        [
            str(REPO_ROOT / {"tui": _JOURNEY, "cli": _CLI_JOURNEY, "cli-profile": _PROFILE_JOURNEY}[options.surface]),
            "-q",
            "-n",
            "0",
            "-m",
            "integration and windows_only",
            "--maxfail=1",
            *(["-k", options.case] if options.case else []),
        ],
        plugins=[_BenchmarkPlugin(output)],
    )
    summarize(output, int(result))
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
