"""Isolated-root acquisition lane: the components role sets an item up end to end in a throwaway root.

The lane drives the native ``components`` role of a built Cadrumo binary,
through the same client every Python surface uses, inside one throwaway root
under the configured build tree's ``testing`` directory. The role's storage
root, the user profile directories and the temporary directory all point into
that root, so nothing reaches the real profile, the installation storage or
``var/storage``; a before-and-after fingerprint of the real acquisition
destinations proves it. Python only drives and reads: every plan, download,
check and state is the role's.

Scenarios, in order, against one root:

* a quick status and a plan, whose download size is named;
* a setup approved for exactly the planned digest, forcibly interrupted part
  way by ending the role's process tree;
* a status that reads the interruption, with Resume;
* the resumed setup under the same approval, which the role must run without a
  second review;
* the full check;
* a second setup, which must have nothing to do and move nothing;
* the removal, then a status that reads the item absent.

The root is removed in a ``finally`` and at exit, on success, failure and
Ctrl-C alike, with the removal verified. Disk use is bounded: the run refuses
to start unless the volume has the plan's own required free space plus a
10 GiB margin, and the setup is ended once the root grows past the item's
byte budget.

The download is opt-in: without ``--accept-size`` the lane stops after naming
the planned size, having downloaded nothing. Usage::

    .venv/Scripts/python.exe -m dev.smoke.acquisition_lane run --items browser --accept-size

The built binary is named by ``CADRUMO_DEVELOPMENT_ROLE_IMAGE``. Not a pytest
module: a run downloads hundreds of megabytes. Its guards are proved without
any download by ``dev/smoke/tests/test_acquisition_lane.py``. A vanilla-machine
run stays a separate obligation until a disposable host exists.
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import shutil
import signal
import sys
import threading
import time
import uuid
from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Final

from cadrumo.adapters.outbound.components.client import (
    ComponentsLaunch,
    ComponentsLauncher,
    ComponentsRequest,
    launch_components_role,
    run_components_role,
)
from cadrumo.adapters.outbound.components.protocol import (
    ComponentsApprove,
    ComponentsCommand,
    ComponentsDecline,
    ComponentsEvent,
    ComponentsOutcome,
    ComponentsProgressLine,
    ComponentsResultLine,
    ComponentsReviewLine,
)
from cadrumo.application.dependency_contracts import (
    DependencyItemKind,
    DependencyRecoveryAction,
    DependencyState,
    DependencyStatusRow,
)
from cadrumo.core.storage_environment import DEVELOPMENT_ROLE_IMAGE_VARIABLE, ChildEnvironmentProfile, child_environment
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

GIB: Final = 1024**3
MIB: Final = 1024**2
DISK_MARGIN_BYTES: Final = 10 * GIB
"""Free space kept on the volume beyond what the plan itself requires."""

ITEM_BYTE_BUDGETS: Final[Mapping[DependencyItemKind, int]] = {
    DependencyItemKind.BROWSER: 2 * GIB,
}
"""Largest size the scratch root may reach while each item is set up; the setup is ended past it.

The browser is the only item the role sets up for a Python caller: only the
desktop sets up the local AI, so the lane has no budget for it.
"""

INTERRUPT_AFTER_BYTES: Final = 5 * MIB
"""How far the first setup gets before the lane ends the role's process tree."""

_BUDGET_SAMPLE_BYTES: Final = 32 * MIB
_REMOVAL_ATTEMPTS: Final = 10
_REMOVAL_PAUSE_S: Final = 0.5
_STATUS_TIMEOUT_S: Final = 120.0
_REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[2]
_BUILD_DIRECTORY: Final = _REPOSITORY_ROOT / "build" / "windows-x64"
_LANE_DIRECTORY: Final = "acquisition"
_STRIPPED_PREFIXES: Final = ("CADRUMO_", "PLAYWRIGHT_", "OLLAMA_", "WEBVIEW2_")
_STRIPPED_PROXY_NAMES: Final = frozenset({"http_proxy", "https_proxy", "all_proxy", "no_proxy"})


class LaneRefusalError(RuntimeError):
    """The lane cannot run safely and started nothing."""


# --------------------------------------------------------------------------
# Disk, budget and isolation guards
# --------------------------------------------------------------------------


def free_space_refusal(*, free_bytes: int, required_bytes: int) -> str | None:
    """Return why the volume is too full for the run, or ``None`` when it may start.

    ``required_bytes`` is the plan's own free-space rule, which the role
    states; the lane keeps its margin on top.
    """
    needed = required_bytes + DISK_MARGIN_BYTES
    if free_bytes < needed:
        return f"the volume has {free_bytes} bytes free; the run needs {needed} ({required_bytes} for the plan)"
    return None


def tree_bytes(root: Path) -> int:
    """Return the bytes of every regular file under ``root``, without following links."""
    total = 0
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            entries = list(os.scandir(directory))
        except (FileNotFoundError, NotADirectoryError, PermissionError):
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    total += os.stat(entry.path, follow_symlinks=False).st_size
            except (FileNotFoundError, PermissionError):
                continue
    return total


def lane_parent(build_directory: Path = _BUILD_DIRECTORY) -> Path:
    """Return the directory the lane's roots live in: the build tree's declared ``testing`` path."""
    manifest = build_directory / "build-paths.json"
    if not manifest.is_file():
        raise LaneRefusalError(f"{manifest} is missing; configure the windows-x64 build before running the lane")
    paths = json.loads(manifest.read_text(encoding="utf-8")).get("paths", {})
    testing = paths.get("testing")
    if not isinstance(testing, str) or not testing:
        raise LaneRefusalError(f"{manifest} declares no testing directory")
    return build_directory / testing / _LANE_DIRECTORY


def role_environment(scratch: Path, base: Mapping[str, str]) -> dict[str, str]:
    """Return the role's environment: nothing inherited from Cadrumo, every location inside ``scratch``.

    The client's own environment builder pins the storage root and the
    temporary directory; the lane hands it an ambient set with every product,
    browser driver, model program and proxy variable removed and the user
    profile directories moved into the root.
    """
    home = scratch / "home"
    ambient = {
        name: value
        for name, value in base.items()
        if not name.upper().startswith(_STRIPPED_PREFIXES) and name.lower() not in _STRIPPED_PROXY_NAMES
    }
    ambient |= {
        "HOME": str(home),
        "USERPROFILE": str(home),
        "LOCALAPPDATA": str(home / "local"),
        "APPDATA": str(home / "roaming"),
        "XDG_CACHE_HOME": str(home / "cache"),
        "XDG_DATA_HOME": str(home / "data"),
    }
    return child_environment(ChildEnvironmentProfile.OPERATOR, scratch / "storage", received={}, base=ambient)


def prepare_scratch(scratch: Path) -> None:
    """Create the root, its storage root and every profile directory the role's environment names."""
    for directory in (
        scratch / "storage",
        scratch / "home" / "local",
        scratch / "home" / "roaming",
        scratch / "home" / "cache",
        scratch / "home" / "data",
    ):
        directory.mkdir(parents=True, exist_ok=True)


type Fingerprint = dict[str, tuple[int, int]]


def fingerprint(roots: Iterable[Path]) -> Fingerprint:
    """Return every file and directory under ``roots`` with its size and modification time."""
    found: Fingerprint = {}
    for root in roots:
        if not root.exists():
            found[f"{root}|absent"] = (0, 0)
            continue
        for path in [root, *root.rglob("*")]:
            with suppress(FileNotFoundError):
                stat = path.lstat()
                found[str(path)] = (0 if path.is_dir() else stat.st_size, stat.st_mtime_ns)
    return found


BROWSER_RUNTIME_LOG: Final = "debug.log"
"""The log a running Chromium appends to beside its own executable."""


def fingerprint_changes(before: Fingerprint, after: Fingerprint) -> list[str]:
    """Name every path added, removed or changed between two fingerprints.

    A change to an existing browser's own runtime log is left out: any browser
    already running from that install appends to it, so it shows activity of
    another process rather than an acquisition. Its appearance or removal still
    counts.
    """
    changes = [f"added {path}" for path in sorted(after.keys() - before.keys())]
    changes += [f"removed {path}" for path in sorted(before.keys() - after.keys())]
    changes += [
        f"changed {path}"
        for path in sorted(before.keys() & after.keys())
        if before[path] != after[path] and Path(path).name != BROWSER_RUNTIME_LOG
    ]
    return changes


def real_acquisition_destinations(repository: Path = _REPOSITORY_ROOT) -> tuple[Path, ...]:
    """Return the real places a browser or model acquisition would write to on this computer."""
    from cadrumo.core.config_state_root import live_state_root_inputs
    from cadrumo.core.storage_environment import host_installed_default_root

    inputs = live_state_root_inputs()
    installed = host_installed_default_root(inputs.environ, sys_platform=inputs.platform)
    storage_roots = [repository / "var" / "storage", repository / "var" / "storage" / "development", installed]
    destinations = [root / part for root in storage_roots for part in ("components", "models")]
    if inputs.platform == "win32":
        browser_cache = installed.parent / "ms-playwright"
    elif inputs.platform == "darwin":
        browser_cache = inputs.home / "Library" / "Caches" / "ms-playwright"
    else:
        browser_cache = Path(inputs.environ.get("XDG_CACHE_HOME") or inputs.home / ".cache") / "ms-playwright"
    destinations.append(browser_cache)
    return tuple(destinations)


def remove_scratch(scratch: Path, *, parent: Path) -> bool:
    """Remove ``scratch``, which must sit directly inside ``parent``, and return whether it is gone."""
    resolved, owner = scratch.resolve(), parent.resolve()
    if resolved.parent != owner:
        raise LaneRefusalError(f"refusing to remove {resolved}: it is not a lane root inside {owner}")

    def clear_read_only(function: Callable[..., object], path: str, _error: BaseException) -> None:
        with suppress(OSError):
            os.chmod(path, 0o700)
            function(path)

    for _ in range(_REMOVAL_ATTEMPTS):
        if not resolved.exists():
            return True
        with suppress(OSError):
            shutil.rmtree(resolved, onexc=clear_read_only)
        if resolved.exists():
            # A file the ended role held open is released by the system shortly after.
            time.sleep(_REMOVAL_PAUSE_S)
    return not resolved.exists()


# --------------------------------------------------------------------------
# Driving the role
# --------------------------------------------------------------------------


@dataclass
class _EndableLaunch:
    """One started role the lane can end part way, as a crash or a closed computer would."""

    inner: ComponentsLaunch
    ended: bool = False

    @property
    def standard_input(self) -> IO[bytes]:
        """Where the client writes its answers."""
        return self.inner.standard_input

    @property
    def standard_output(self) -> IO[bytes]:
        """Where the role writes its lines."""
        return self.inner.standard_output

    def wait(self, timeout: float) -> int | None:
        """The role's exit status; one the lane ended exited without a result."""
        return 1 if self.ended else self.inner.wait(timeout)

    def end(self) -> None:
        """End the role and everything it started, once."""
        if not self.ended:
            self.ended = True
            self.inner.end()


@dataclass
class RoleDriver:
    """Starts the role of ``image`` with the lane's isolated environment, in the scratch root."""

    image: Path
    environment: Mapping[str, str]
    directory: Path
    start: ComponentsLauncher = launch_components_role
    launches: list[_EndableLaunch] = field(default_factory=list)

    def launcher(
        self, image: Path, arguments: Sequence[str], environment: Mapping[str, str], directory: Path
    ) -> ComponentsLaunch:
        """Start the role with the lane's own environment and directory, whatever the client derived."""
        del image, environment, directory
        launch = _EndableLaunch(self.start(self.image, arguments, self.environment, self.directory))
        self.launches.append(launch)
        return launch

    def run(
        self,
        request: ComponentsRequest,
        *,
        on_event: Callable[[ComponentsEvent], None] | None = None,
        review: Callable[[ComponentsReviewLine], ComponentsApprove | ComponentsDecline] | None = None,
        timeout: float | None = None,
    ) -> ComponentsResultLine:
        """Run one command of the role through the real client."""
        return run_components_role(
            request, on_event=on_event, review=review, timeout=timeout, image=self.image, launcher=self.launcher
        )

    def end_running(self) -> None:
        """End the role now running, and everything it started."""
        self.launches[-1].end()


@dataclass
class LaneReport:
    """What the lane did and found; ``failures`` names every contract the role did not keep."""

    items: list[str]
    scratch: str = ""
    planned_bytes: int | None = None
    plan_digest: str | None = None
    steps: list[dict[str, object]] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    refused: str | None = None
    downloaded: bool = False
    stopped_at_size: bool = False
    scratch_removed: bool | None = None
    real_storage_changes: list[str] = field(default_factory=list)

    def step(self, name: str, result: ComponentsResultLine | None, **facts: object) -> None:
        """Record one step and, when it settled, what the role answered."""
        entry: dict[str, object] = {"step": name, **facts}
        if result is not None:
            entry["outcome"] = result.outcome.value
            entry["rows"] = [row.model_dump(mode="json", exclude_none=True) for row in result.rows]
        self.steps.append(entry)

    def expect(self, holds: bool, failure: str) -> None:
        """Record ``failure`` unless the contract ``holds``."""
        if not holds:
            self.failures.append(failure)


def _rows(result: ComponentsResultLine, items: Sequence[DependencyItemKind]) -> dict[str, DependencyStatusRow]:
    wanted = {item.value for item in items}
    return {row.item_id: row.status_row() for row in result.rows if row.item_id in wanted}


@contextmanager
def _cleanup_guard(scratch: Path, parent: Path, report: LaneReport) -> Generator[None]:
    """Remove the scratch root however the run ends, including Ctrl-C and interpreter exit."""
    removed = threading.Event()

    def remove() -> None:
        if removed.is_set():
            return
        removed.set()
        report.scratch_removed = remove_scratch(scratch, parent=parent)

    def interrupted(signum: int, _frame: object) -> None:
        raise KeyboardInterrupt(f"signal {signum}")

    atexit.register(remove)
    previous = {
        number: signal.signal(number, interrupted)
        for number in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGBREAK", signal.SIGINT))
    }
    try:
        yield
    finally:
        remove()
        atexit.unregister(remove)
        for number, handler in previous.items():
            signal.signal(number, handler)


def _interrupted_setup(
    driver: RoleDriver, report: LaneReport, items: Sequence[DependencyItemKind], digest: str, scratch: Path
) -> None:
    """Set the items up under the approval of ``digest``, ending the role once the first bytes have moved."""
    moved = 0
    next_sample = _BUDGET_SAMPLE_BYTES
    budget = sum(ITEM_BYTE_BUDGETS[item] for item in items)
    reviewed: list[str] = []

    def approve(review: ComponentsReviewLine) -> ComponentsApprove | ComponentsDecline:
        reviewed.append(review.plan_digest)
        return ComponentsApprove(plan_digest=digest) if review.plan_digest == digest else ComponentsDecline()

    def observe(event: ComponentsEvent) -> None:
        nonlocal moved, next_sample
        if not isinstance(event, ComponentsProgressLine):
            return
        moved = max(moved, event.completed)
        if moved >= INTERRUPT_AFTER_BYTES:
            driver.end_running()
        if moved >= next_sample:
            next_sample += _BUDGET_SAMPLE_BYTES
            if tree_bytes(scratch) > budget:
                report.failures.append(f"the root grew past its budget of {budget} bytes")
                driver.end_running()

    try:
        result = driver.run(
            ComponentsRequest(ComponentsCommand.SETUP, items=tuple(items)), on_event=observe, review=approve
        )
    except RefusalError as ended:
        report.step("setup_interrupted", None, ended=ended.reason.value, moved_bytes=moved, reviewed=reviewed)
    else:
        report.step("setup_interrupted", result, moved_bytes=moved, reviewed=reviewed)
        report.failures.append(f"the first setup was not interrupted: it ended {result.outcome.value}")
    report.expect(reviewed == [digest], f"the first setup reviewed {reviewed}, not the planned digest {digest}")
    report.expect(moved > 0, "the first setup moved no bytes before it was ended")


def _scenarios(
    driver: RoleDriver,
    report: LaneReport,
    items: Sequence[DependencyItemKind],
    scratch: Path,
    *,
    accept_size: bool,
    free_space: Callable[[Path], int],
) -> None:
    status = driver.run(ComponentsRequest(ComponentsCommand.STATUS, items=tuple(items)), timeout=_STATUS_TIMEOUT_S)
    report.step("status", status)
    report.expect(status.outcome is ComponentsOutcome.OK, f"the first status ended {status.outcome.value}")
    plan = driver.run(ComponentsRequest(ComponentsCommand.PLAN, items=tuple(items)), timeout=_STATUS_TIMEOUT_S)
    report.step("plan", plan)
    if plan.plan is None or plan.plan_digest is None:
        report.refused = f"the role planned nothing to set up for {list(report.items)}: {plan.outcome.value}"
        return
    report.plan_digest = plan.plan_digest
    report.planned_bytes = plan.plan.known_download_bytes
    refusal = free_space_refusal(free_bytes=free_space(scratch), required_bytes=plan.plan.space.required_bytes)
    if refusal is not None:
        report.refused = refusal
        return
    if not accept_size:
        report.stopped_at_size = True
        return
    report.downloaded = True
    _interrupted_setup(driver, report, items, plan.plan_digest, scratch)

    interrupted = driver.run(ComponentsRequest(ComponentsCommand.STATUS, items=tuple(items)), timeout=_STATUS_TIMEOUT_S)
    report.step("status_after_interruption", interrupted)
    resumable = [
        row.item_id
        for row in _rows(interrupted, items).values()
        if row.failure_category is DependencyFailureCategory.INTERRUPTED
        and row.recovery is DependencyRecoveryAction.RESUME
    ]
    report.expect(bool(resumable), "no item reads as interrupted with Resume after the forced interruption")

    # A resume carries the approval already given; a review here breaks the client's protocol.
    resumed = driver.run(ComponentsRequest(ComponentsCommand.SETUP, items=tuple(items), approve=plan.plan_digest))
    report.step("setup_resumed", resumed)
    report.expect(resumed.outcome is ComponentsOutcome.COMPLETED, f"the resumed setup ended {resumed.outcome.value}")

    checked = driver.run(ComponentsRequest(ComponentsCommand.VERIFY, items=tuple(items)))
    report.step("full_check", checked)
    states = {row.item_id: row.state for row in _rows(checked, items).values()}
    report.expect(set(states.values()) == {DependencyState.READY}, f"the full check read {states}")

    asked: list[str] = []
    moved: list[int] = []

    def refuse(review: ComponentsReviewLine) -> ComponentsDecline:
        asked.append(review.plan_digest)
        return ComponentsDecline()

    def observe(event: ComponentsEvent) -> None:
        if isinstance(event, ComponentsProgressLine):
            moved.append(event.completed)

    again = driver.run(ComponentsRequest(ComponentsCommand.SETUP, items=tuple(items)), on_event=observe, review=refuse)
    report.step("setup_again", again, reviewed=asked, moved_bytes=sum(moved))
    report.expect(again.outcome is ComponentsOutcome.NOTHING_TO_DO, f"the second setup ended {again.outcome.value}")
    report.expect(not asked and not moved, "the second setup asked for approval or moved bytes")

    removed = driver.run(ComponentsRequest(ComponentsCommand.REMOVE, items=tuple(items)))
    report.step("remove", removed)
    after = driver.run(ComponentsRequest(ComponentsCommand.STATUS, items=tuple(items)), timeout=_STATUS_TIMEOUT_S)
    report.step("status_after_removal", after)
    left = {row.item_id: row.state for row in _rows(after, items).values() if row.state is not DependencyState.ABSENT}
    report.expect(not left, f"after the removal these items are still there: {left}")


def _volume_free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def run_lane(
    items: Sequence[str],
    *,
    accept_size: bool = False,
    image: Path | None = None,
    build_directory: Path = _BUILD_DIRECTORY,
    start: ComponentsLauncher = launch_components_role,
    free_space: Callable[[Path], int] | None = None,
    destinations: Sequence[Path] | None = None,
) -> LaneReport:
    """Run the isolated acquisition lane for ``items`` and return its report.

    ``start`` starts the role's process, the client's own contained launch by
    default. ``free_space`` measures the volume a root is on, and
    ``destinations`` are the real storage the run must leave unchanged; both
    default to this computer's own.
    """
    kinds = [DependencyItemKind(item) for item in items]
    held_back = [kind.value for kind in kinds if kind not in ITEM_BYTE_BUDGETS]
    if held_back:
        raise LaneRefusalError(f"the role sets up only the browser for this lane; the desktop sets up {held_back}")
    report = LaneReport(items=[kind.value for kind in kinds])
    named = image if image is not None else Path(os.environ.get(DEVELOPMENT_ROLE_IMAGE_VARIABLE, ""))
    if not named.is_absolute() or not named.is_file():
        raise LaneRefusalError(f"name a built Cadrumo binary in {DEVELOPMENT_ROLE_IMAGE_VARIABLE}")
    parent = lane_parent(build_directory)
    parent.mkdir(parents=True, exist_ok=True)
    scratch = parent / f"run-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    report.scratch = str(scratch)
    watched = tuple(real_acquisition_destinations() if destinations is None else destinations)
    before = fingerprint(watched)
    scratch.mkdir()
    with _cleanup_guard(scratch, parent, report):
        prepare_scratch(scratch)
        driver = RoleDriver(
            image=named, environment=role_environment(scratch, os.environ), directory=scratch, start=start
        )
        measure = free_space if free_space is not None else _volume_free_bytes
        _scenarios(driver, report, kinds, scratch, accept_size=accept_size, free_space=measure)
    report.real_storage_changes = fingerprint_changes(before, fingerprint(watched))
    report.expect(report.scratch_removed is True, f"the lane root {scratch} was not removed")
    report.expect(not report.real_storage_changes, "the run changed real storage")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """Run the lane and return the process exit code: 0 kept, 1 a contract broken, 2 refused."""
    parser = argparse.ArgumentParser(
        prog="python -m dev.smoke.acquisition_lane",
        description="Isolated-root acquisition lane: the components role sets an item up end to end.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run the isolated acquisition lane")
    run.add_argument(
        "--items",
        nargs="+",
        default=["browser"],
        choices=[kind.value for kind in ITEM_BYTE_BUDGETS],
        help="setup items",
    )
    run.add_argument("--accept-size", action="store_true", help="download what the plan names once its size is named")
    arguments = parser.parse_args(argv)
    try:
        report = run_lane(arguments.items, accept_size=arguments.accept_size)
    except LaneRefusalError as refusal:
        sys.stderr.write(f"acquisition-lane: refused: {refusal}\n")
        return 2
    sys.stdout.write(json.dumps(report.__dict__, indent=2, default=str) + "\n")
    if report.failures:
        return 1
    if report.refused is not None:
        sys.stderr.write(f"acquisition-lane: refused: {report.refused}\n")
        return 2
    if report.stopped_at_size:
        sys.stderr.write(f"acquisition-lane: the plan downloads {report.planned_bytes} bytes; add --accept-size\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
