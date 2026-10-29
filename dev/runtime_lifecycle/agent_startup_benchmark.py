"""Measure real packaged agent startup on disposable profiles, without model or AEAT calls.

Each sample creates and signs in one synthetic profile, then starts the service
twice: absent agent stores, followed by current stores on the same live runtime.
Before service launch it measures the first saved-language observation and a
cached observation through the held profile connection.
The driver uses the package's CLI and authenticated service admission. It does
not measure desktop rendering, OS cold-cache startup, or provider turn latency.
"""

from __future__ import annotations

import argparse
import json
import secrets
import statistics
import tempfile
import time
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import httpx
import psutil

from cadrumo_agent_service.installed_client import SERVICE_ID
from cadrumo_runtime.application.development_root import mark_development_root
from dev.temporary_output import prepare_temp_root

from .agent_service_session import (
    _close_holder,
    _logout_profile,
    _require_runtime_stopped,
    _validate_agent_event,
    _validate_service_lease,
    _validate_service_ready,
)
from .caller_owned_root import Programs, caller_owned_runtime, consumer_environment, require
from .packaged_service_process import PackagedServiceProcess
from .proof_support import create_profile, identify_profile, login_profile, package_identity, started_processes
from .windows_holder import WindowsRuntimeSessionHolder

_PHASE_MESSAGES = (
    "agent service ready ",
    "agent store step=",
    "agent start timing ",
    "agent gateway timing ",
    "Gateway process up ",
    "Gateway startup timing ",
    "Hosted temporary setup ",
    "Worker process up ",
    "Worker startup timing ",
    "worker operation composition ",
)


def _wait_for_builds() -> None:
    """Wait for observed build activity before a sample; never stop another task."""
    deadline = time.monotonic() + 600.0
    announced = False
    while any(
        str(process.info["name"]).casefold() in {"msbuild.exe", "rustc.exe", "cargo.exe", "wix.exe"}
        for process in psutil.process_iter(["name"])
    ):
        if not announced:
            print(json.dumps({"waiting": "background builds must finish before timing"}), flush=True)
            announced = True
        require(time.monotonic() < deadline, "background builds did not finish within the benchmark wait bound")
        time.sleep(1.0)


def _health_facts(health: dict[str, Any]) -> dict[str, Any]:
    """Require a live worker in either documented gateway health projection."""
    if "gateway_readiness" in health:
        require(health["gateway_readiness"] == "ready", "gateway health probe was not ready")
        require(health.get("worker_state") == "ready", "worker health probe was not ready")
        return {
            "gateway_health": health["gateway_readiness"],
            "worker_health": health["worker_state"],
            "run_admission": health.get("run_admission"),
        }
    require(health.get("service") == "gateway" and health.get("ready") is True, "gateway probe was not ready")
    require(health.get("status") == "ok", "gateway dependency probes were not healthy")
    require(health.get("worker_status") == "up", "gateway worker probe was not up")
    return {"gateway_health": "ready", "worker_health": "up", "run_admission": "not measured"}


def _milestones(root: Path, since: float, *, timeout: float = 60.0) -> dict[str, Any]:
    """Read only this synthetic run's bounded startup facts, never profile values."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        records = _startup_records(root, since)
        warmed = [stamp for stamp, line in records if "Worker model warm-up done" in line]
        available = [stamp for stamp, line in records if "Worker available" in line]
        if warmed and available:
            phases = _startup_phases(records)
            return {"worker_available_at": min(available), "worker_warmed_at": min(warmed), "phases": phases}
        time.sleep(0.05)
    raise RuntimeError("packaged worker did not publish availability and completed warm-up within 60 seconds")


def _startup_records(root: Path, since: float) -> list[tuple[float, str]]:
    """Read timestamped startup messages from this synthetic run."""
    records: list[tuple[float, str]] = []
    for path in (root / "logs" / "cadrumo.log",):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                stamp = datetime.fromisoformat(line.split(maxsplit=1)[0]).timestamp()
            except (ValueError, IndexError):
                continue
            if stamp >= since:
                records.append((stamp, line))
    return records


def _startup_phases(records: list[tuple[float, str]]) -> list[str]:
    """Retain only fixed timing messages without private diagnostic context."""
    phases: list[str] = []
    for _, line in records:
        for prefix in _PHASE_MESSAGES:
            if prefix in line:
                phases.append(prefix + line.split(prefix, 1)[1].split(" | ", 1)[0])
                break
    return phases


def measure(package: Path, scratch: Path) -> dict[str, Any]:
    """Measure fresh and repeat service starts; always close the trees we own."""
    root, secret_store = scratch / "storage", scratch / "secrets"
    root.mkdir(parents=True)
    secret_store.mkdir()
    environment = consumer_environment(root, secret_store)
    environment["CADRUMO_LOG_STDERR_LEVEL"] = "WARNING"
    # Startup requires no model credentials. Do not admit ambient credentials
    # even when the caller's development environment contains them.
    for key in tuple(environment):
        if key.endswith(("_API_KEY", "_AUTH_TOKEN")):
            environment.pop(key)
    mark_development_root(root)
    programs = Programs.of(package)
    measurements: dict[str, Any] = {}
    with ExitStack() as cleanup:
        phase = time.monotonic()
        runtime = cleanup.enter_context(caller_owned_runtime(programs, environment, scratch / "runtime-stderr.log"))
        cleanup.callback(_require_runtime_stopped, runtime)
        require(runtime.ready().get("kind") == "runtime_ready", "runtime readiness refused")
        measurements["runtime_ready_seconds"] = time.monotonic() - phase
        phase = time.monotonic()
        profile = create_profile(programs, environment, "startup-benchmark")
        persisted = login_profile(programs, environment, profile)
        if persisted:
            cleanup.callback(_logout_profile, programs, environment)
        profile = identify_profile(programs, environment, profile)
        if profile.profile_id is None:
            raise RuntimeError("synthetic profile identity unavailable")
        measurements["profile_create_and_login_seconds"] = time.monotonic() - phase
        phase = time.monotonic()
        holder = WindowsRuntimeSessionHolder(
            programs.runtime,
            profile_id=profile.profile_id,
            environment=environment,
            password=bytearray(profile.password, "utf-8"),
            frontend="cli",
        )
        cleanup.callback(_close_holder, holder)
        measurements["holder_start_seconds"] = time.monotonic() - phase
        for label in ("first", "cached"):
            phase = time.monotonic()
            language = holder.command("language_observe")
            require(language.get("kind") == "profile_language", "saved language observation refused")
            measurements[f"profile_language_{label}_seconds"] = time.monotonic() - phase
        starts = []
        for store_state in ("absent", "current"):
            bearer = bytearray(secrets.token_urlsafe(48), "ascii")
            gateway_bearer = bytearray(secrets.token_urlsafe(48), "ascii")
            wall_start, phase = time.time(), time.monotonic()
            try:
                with ExitStack() as service_cleanup:
                    service = PackagedServiceProcess(
                        package / "bin" / "cadrumo-agent-service.exe",
                        profile_id=profile.profile_id,
                        environment=environment,
                        directory=root,
                        bearer=bearer,
                        gateway_bearer=bytearray(gateway_bearer),
                    )
                    service_cleanup.callback(service.close)
                    ready = service.event()
                    _validate_service_ready(ready, holder, profile)
                    service_seconds = time.monotonic() - phase
                    admission = holder.command(
                        "service_admission", recipient_connection_id=ready["connection_id"], service_id=SERVICE_ID
                    )
                    _validate_service_lease(admission, holder, ready, profile)
                    admitted_seconds = time.monotonic() - phase
                    event = service.event()
                    _validate_agent_event(event)
                    require(event["event"] == "agent_ready", "packaged agent startup refused")
                    gateway_seconds = time.monotonic() - phase
                    milestones = _milestones(root, wall_start)
                    with httpx.Client(trust_env=False, timeout=10.0) as client:
                        response = client.get(
                            f"http://127.0.0.1:{event['gateway_port']}/health",
                            headers={"Authorization": "Bearer " + gateway_bearer.decode("ascii")},
                        )
                        response.raise_for_status()
                        health = response.json()
                    health_facts = _health_facts(health)
                    starts.append(
                        {
                            "store_state_before_start": store_state,
                            "service_ready_seconds": service_seconds,
                            "service_admitted_seconds": admitted_seconds,
                            "gateway_ready_seconds": gateway_seconds,
                            "worker_available_seconds": milestones["worker_available_at"] - wall_start,
                            "worker_warmed_seconds": milestones["worker_warmed_at"] - wall_start,
                            **health_facts,
                            "phases": milestones["phases"],
                        }
                    )
            finally:
                gateway_bearer[:] = bytes(len(gateway_bearer))
                bearer[:] = bytes(len(bearer))
        measurements["starts"] = starts
    require(not started_processes(), "benchmark left a child process running")
    measurements["cleanup"] = "all owned processes exited"
    return measurements


def main() -> None:
    """Record completed samples durably and reclaim this invocation's synthetic profiles.

    Resume reads completed observations; each remaining sample starts fresh.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--wait-for-builds", action="store_true", help="Wait for observed builds before each sample")
    parser.add_argument("--resume", action="store_true", help="Keep completed samples from the output report")
    arguments = parser.parse_args()
    require(1 <= arguments.samples <= 10, "samples must be between 1 and 10")
    packages = {name: getattr(arguments, name).resolve(strict=True) for name in ("baseline", "candidate")}
    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    identities = {name: package_identity(package) for name, package in packages.items()}
    scratch_parent = prepare_temp_root()
    with tempfile.TemporaryDirectory(prefix="agent-startup-", dir=scratch_parent) as temporary:
        scratch = Path(temporary)
        report: dict[str, Any]
        if arguments.resume:
            report = json.loads(output.read_text(encoding="utf-8"))
            require(report["packages"] == identities, "cannot resume with changed packages")
            previous_scratch = Path(report["scratch"]).resolve()
            require(
                previous_scratch.parent == scratch_parent,
                "benchmark scratch must remain in controlled temporary storage",
            )
            require(all(sample["sample"] <= arguments.samples for sample in report["samples"]), "cannot reduce samples")
        else:
            require(not output.exists(), "output already exists; use --resume or a new output path")
            report = {
                "scope": "Real Release packages; synthetic unconfigured profiles; no model, AEAT or desktop rendering",
                "cache_scope": "Fresh processes, warm OS caches; current-store starts keep the profile worker alive",
                "scratch": str(scratch),
                "packages": identities,
                "samples": [],
            }
        report["scratch"] = str(scratch)
        report["scratch_retained"] = False
        report.setdefault("load_policy_history", []).append(
            "wait for observed builds" if arguments.wait_for_builds else "measure under current load"
        )
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        _collect_samples(
            packages, report, scratch, output, arguments.samples, wait_for_builds=arguments.wait_for_builds
        )
        report["medians_seconds"], report["setup_medians_seconds"] = _sample_medians(packages, report["samples"])
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report["medians_seconds"], indent=2), flush=True)


def _sample_medians(
    packages: dict[str, Path], samples: list[dict[str, object]]
) -> tuple[dict[str, dict[str, dict[str, float]]], dict[str, dict[str, float]]]:
    """Summarize startup and setup timings for each package."""
    medians = {
        name: {
            state: {
                key: statistics.median(
                    cast(float, start[key])
                    for sample in samples
                    if sample["package"] == name
                    for start in cast(list[dict[str, object]], sample["starts"])
                    if start["store_state_before_start"] == state
                )
                for key in (
                    "service_ready_seconds",
                    "gateway_ready_seconds",
                    "worker_available_seconds",
                    "worker_warmed_seconds",
                )
            }
            for state in ("absent", "current")
        }
        for name in packages
    }
    return medians, _setup_medians(packages, samples)


def _setup_medians(packages: dict[str, Path], samples: list[dict[str, object]]) -> dict[str, dict[str, float]]:
    """Summarize the independent setup stages for each package."""
    return {
        name: {
            key: statistics.median(cast(float, sample[key]) for sample in samples if sample["package"] == name)
            for key in (
                "runtime_ready_seconds",
                "profile_create_and_login_seconds",
                "holder_start_seconds",
                "profile_language_first_seconds",
                "profile_language_cached_seconds",
            )
        }
        for name in packages
    }


def _collect_samples(
    packages: dict[str, Path],
    report: dict[str, object],
    scratch: Path,
    output: Path,
    count: int,
    *,
    wait_for_builds: bool,
) -> None:
    """Collect missing samples in alternating order, persisting each completed result."""
    samples = cast(list[dict[str, object]], report["samples"])
    identities = cast(dict[str, dict[str, object]], report["packages"])
    for index in range(count):
        order = ("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")
        for name in order:
            if any(sample["package"] == name and sample["sample"] == index + 1 for sample in samples):
                continue
            if wait_for_builds:
                _wait_for_builds()
            require(package_identity(packages[name]) == identities[name], "package changed before sample")
            print(json.dumps({"starting": name, "sample": index + 1}), flush=True)
            sample_root = scratch / f"{name}-{index + 1}"
            sample_root.mkdir()
            sample = measure(packages[name], sample_root)
            sample["scratch"] = str(sample_root)
            sample["scratch_retained"] = False
            require(package_identity(packages[name]) == identities[name], "package changed during sample")
            samples.append({"package": name, "sample": index + 1, **sample})
            output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            _print_completed(name, index + 1, sample)


def _print_completed(name: str, number: int, sample: dict[str, object]) -> None:
    """Print only timing fields and the pre-start store state."""
    print(
        json.dumps(
            {
                "completed": name,
                "sample": number,
                "starts": [
                    {k: v for k, v in start.items() if k.endswith("_seconds") or k == "store_state_before_start"}
                    for start in cast(list[dict[str, object]], sample["starts"])
                ],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
