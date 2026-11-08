r"""Run the packaged desktop on a disposable storage root outside every Git project, signed in to a seeded profile.

The agent service refuses a provider home inside a Git project, so a storage
root inside the checkout fails every agent run. This tool keeps the root in
the account's own temporary folder and drives the built package as the live
lane does:

1. refuses to run while a Cadrumo desktop is open, then stages the lane
   package from the recorded remote-debugging host;
2. creates ``%LOCALAPPDATA%\Temp\cadrumo-e2e-<random>``, refuses it when it or
   any ancestor holds ``.git``, and marks it as a development root;
3. starts the package's ``cadrumo-runtime --configured-root`` on it, creates a
   synthetic profile through the package's ``aeat`` with a fresh random
   password on standard input only, signs it in with a stored sign-in, states
   synthetic taxpayer facts, imports :data:`LEDGER_SEED` through
   ``app ledger import`` and requires ``app ledger list`` to show at least
   :data:`MINIMUM_SEEDED_ROWS` movements, then stops that runtime;
4. launches the desktop on the root in a kill-on-close Job, with the window's
   DevTools port set, requires the endpoint to listen on loopback only and the
   desktop to resume the stored sign-in, writes ``state.json`` into the run's
   results directory and holds until ``stop`` appears there, a stop signal
   arrives, or the window is closed;
5. closes the window, signs the profile out through a fresh caller-owned
   runtime so no sign-in key stays in the account's credential store, copies
   the root's logs into the results directory, removes every results file
   that holds the password, and removes the root without following any link,
   naming every path it could not remove.

The managed local AI keeps its models below the root
(``models/ollama``): the desktop derives that folder from the storage root
and sets the server's ``OLLAMA_MODELS`` itself, so no setting moves it, and
each run starts with an empty model folder.

The results directory lies below the enrolled native build's
``desktop/testing``. ``--warm`` launches the desktop once and closes it before
the measured launch, so the reported DevTools time is a warm start. Exit 0
means every step held, 1 names what failed, 3 means a prerequisite is absent.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import signal
import stat
import sys
import threading
import time
import traceback
from collections.abc import Callable, Mapping
from contextlib import ExitStack, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any, Final

import httpx

from cadrumo_runtime.application.development_root import mark_development_root

from ..runtime_lifecycle.caller_owned_root import (
    AcceptanceError,
    Programs,
    caller_owned_runtime,
    consumer_environment,
    error_code,
    require,
    run_cli,
)
from ..runtime_lifecycle.proof_support import Profile, create_profile, identify_profile, login_profile, state_taxpayer
from ..temporary_output import prepare_temp_root
from .containment import LaneJob
from .desktop_cleanup import Watch, desktop_exit_code, settle_desktop
from .desktop_processes import person_environment, require_no_desktop
from .lane import attached, devtools_endpoint, free_port, lane_desktop, status_until
from .lane_errors import UnavailableError
from .lane_stage import TESTING, TestHost, require_current, snapshot_report, stage_package, test_host

ROOT_PREFIX: Final = "cadrumo-e2e-"
"""The name every disposable root starts with; removal refuses any other."""
_ROOT_NAME: Final = re.compile(r"cadrumo-e2e-[0-9a-f]{32}")
LEDGER_SEED: Final = Path(__file__).resolve().parent / "fixtures" / "ledger-seed.csv"
"""Five synthetic bank movements in the documentation fixture's CSV shape."""
MINIMUM_SEEDED_ROWS: Final = 3
"""The ledger-privacy check needs at least three shown amounts beyond the listed descriptions."""
RESULTS: Final = TESTING / "disposable-root"
"""Where each run's state, stop file and copied logs go, below the enrolled native build."""
_PROFILE: Final = "desktop-e2e"
_SUCCESS: Final = frozenset({"success", "warning"})
_RUNTIME_STOPPED: Final = 64
_DEVTOOLS_SECONDS: Final = 180.0
_SIGN_IN_SECONDS: Final = 120.0
_POLL_SECONDS: Final = 0.1
_HOLD_SECONDS: Final = 0.5
_LOG_LEVEL_VARIABLE: Final = "CADRUMO_LOG_LEVEL"

CliRunner = Callable[..., tuple[int, dict[str, Any]]]
"""Runs one JSON ``aeat`` command: its arguments, and a secret for standard input only."""


def temporary_parent(environment: Mapping[str, str]) -> Path:
    r"""The account's own temporary folder, ``%LOCALAPPDATA%\Temp``, where disposable roots live."""
    local = environment.get("LOCALAPPDATA", "").strip()
    if not local:
        raise UnavailableError("LOCALAPPDATA is not set; the disposable root lives in %LOCALAPPDATA%\\Temp")
    return Path(local) / "Temp"


def is_link(path: Path) -> bool:
    """Whether ``path`` is a symbolic link, a junction or any other reparse point, without following it."""
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def enclosing_git_project(directory: Path) -> Path | None:
    """The nearest directory at or above ``directory`` holding a ``.git`` entry, or ``None``.

    ``directory`` need not exist. Where it exists its resolved form is searched
    first, so a link or junction into a project is caught where it lands, then
    its spelling.
    """
    candidates = [directory.resolve(strict=True)] if directory.exists() else []
    candidates.append(directory)
    for start in dict.fromkeys(candidates):
        for ancestor in (start, *start.parents):
            marker = ancestor / ".git"
            if marker.exists() or marker.is_symlink():
                return ancestor
    return None


def require_outside_git(directory: Path, owner: str) -> None:
    """Refuse ``directory`` when it lies inside a Git project; the agent service refuses such a root."""
    project = enclosing_git_project(directory)
    if project is not None:
        raise AcceptanceError(
            f"{owner} {directory} is inside the Git project {project}; the agent service refuses provider "
            "homes there, so the disposable root must lie outside every Git project"
        )


def create_root(parent: Path) -> Path:
    """Create a fresh, collision-resistant disposable root directly below ``parent``, outside every Git project."""
    require_outside_git(parent, "the disposable root's parent")
    resolved_parent = parent.resolve(strict=True)
    root = resolved_parent / f"{ROOT_PREFIX}{secrets.token_hex(16)}"
    root.mkdir()
    resolved = root.resolve(strict=True)
    require(resolved == root, f"the disposable root {root} resolves elsewhere: {resolved}")
    require_outside_git(resolved, "the disposable storage root")
    return resolved


def removable_root(candidate: Path, parent: Path) -> Path:
    """The root to remove, refusing anything but a real directory named like one directly below ``parent``."""
    if not _ROOT_NAME.fullmatch(candidate.name):
        raise AcceptanceError(f"refusing to remove {candidate}: not named like a disposable root")
    if is_link(candidate):
        raise AcceptanceError(f"refusing to remove {candidate}: it is a link")
    if not candidate.is_dir():
        raise AcceptanceError(f"refusing to remove {candidate}: not a directory")
    resolved = candidate.resolve(strict=True)
    if resolved.parent != parent.resolve() or resolved.name != candidate.name:
        raise AcceptanceError(f"refusing to remove {candidate}: not directly below {parent}")
    return resolved


def remove_root(candidate: Path, parent: Path) -> list[str]:
    """Remove a disposable root without following any link inside it; return each path left behind and why."""
    root = removable_root(candidate, parent)
    left: list[str] = []
    _remove_tree(root, left)
    return left


def _remove_tree(directory: Path, left: list[str]) -> None:
    before = len(left)
    try:
        entries = sorted(directory.iterdir())
    except OSError as error:
        left.append(f"{directory}: {error.strerror or error}")
        return
    for path in entries:
        try:
            if is_link(path):
                _remove_link(path)
            elif path.is_dir():
                _remove_tree(path, left)
            else:
                _remove_file(path)
        except OSError as error:
            left.append(f"{path}: {error.strerror or error}")
    if len(left) == before:
        try:
            directory.rmdir()
        except OSError as error:
            left.append(f"{directory}: {error.strerror or error}")


def _remove_link(path: Path) -> None:
    """Remove the link itself; a directory junction or link needs the directory call, which leaves its target."""
    try:
        path.unlink()
    except (IsADirectoryError, PermissionError):
        path.rmdir()


def _remove_file(path: Path) -> None:
    try:
        path.unlink()
    except PermissionError:
        # A read-only attribute refuses deletion on Windows; a file held open stays refused and is reported.
        path.chmod(stat.S_IWRITE | stat.S_IREAD)
        path.unlink()


def ledger_import_arguments(csv: Path) -> tuple[str, ...]:
    """The ``aeat`` arguments that import ``csv`` through the registered ledger import operation."""
    return ("--profile-secrets-stdin", "app", "ledger", "import", "--file", str(csv), "--provider", "csv")


def ledger_list_arguments() -> tuple[str, ...]:
    """The ``aeat`` arguments that list the ledger."""
    return ("--profile-secrets-stdin", "app", "ledger", "list")


def seeded_rows(envelope: Mapping[str, Any]) -> int:
    """How many movements a ``app ledger list`` envelope says the ledger holds."""
    result = envelope.get("result")
    if not isinstance(result, Mapping):
        return 0
    total = result.get("total")
    if isinstance(total, int) and not isinstance(total, bool):
        return total
    rows = result.get("rows")
    return len(rows) if isinstance(rows, list) else 0


def require_seeded(envelope: Mapping[str, Any]) -> int:
    """The ledger's movement count, refusing fewer than :data:`MINIMUM_SEEDED_ROWS`."""
    count = seeded_rows(envelope)
    require(
        count >= MINIMUM_SEEDED_ROWS,
        f"the ledger holds {count} movements after the seed; the ledger-privacy check needs {MINIMUM_SEEDED_ROWS}",
    )
    return count


def seed_ledger(run: CliRunner, csv: Path, password: str) -> int:
    """Import ``csv`` and list the ledger through ``run``, the password on standard input only; return the count."""
    secret = {"profile_passphrase": password}
    code, envelope = run(*ledger_import_arguments(csv), secret=secret)
    require(
        code == 0 and envelope.get("status") in _SUCCESS,
        f"app ledger import: exit {code}, code {error_code(envelope)}",
    )
    code, envelope = run(*ledger_list_arguments(), secret=secret)
    require(code == 0, f"app ledger list: exit {code}, code {error_code(envelope)}")
    return require_seeded(envelope)


def contains_secret(data: bytes, secret: str) -> bool:
    """Whether ``data`` holds ``secret`` as UTF-8 or UTF-16 text."""
    return any(form in data for form in (secret.encode("utf-8"), secret.encode("utf-16-le")))


def remove_secret_bearing(directory: Path, secret: str) -> list[str]:
    """Remove every file below ``directory`` that holds ``secret``, following no link; name each one."""
    found: list[str] = []
    if not directory.is_dir() or is_link(directory):
        return found
    for place, subdirectories, files in os.walk(directory, followlinks=False):
        subdirectories[:] = [name for name in subdirectories if not is_link(Path(place, name))]
        for name in files:
            path = Path(place, name)
            if is_link(path):
                continue
            try:
                held = contains_secret(path.read_bytes(), secret)
            except OSError as error:
                found.append(f"{path.relative_to(directory)} could not be read for the password check: {error}")
                continue
            if held:
                path.unlink()
                found.append(f"the profile password appeared in {path.relative_to(directory)}, which was removed")
    return found


def _plain_files(directory: Path) -> list[Path]:
    if is_link(directory) or not directory.is_dir():
        return []
    return [path for path in sorted(directory.iterdir()) if not is_link(path) and path.is_file()]


def _plain_directories(directory: Path) -> list[Path]:
    if is_link(directory) or not directory.is_dir():
        return []
    return [path for path in sorted(directory.iterdir()) if not is_link(path) and path.is_dir()]


def _desktop_log(name: str) -> bool:
    return name == "cadrumo-native.jsonl" or (
        (name == "cadrumo.log" or name.startswith("cadrumo.log.")) and not name.endswith(".lock")
    )


def log_files(root: Path) -> list[tuple[Path, str]]:
    """The root's desktop, runtime and agent logs, each with where it goes in the results; no link is followed."""
    found = [(path, f"logs/{path.name}") for path in _plain_files(root / "logs") if _desktop_log(path.name)]
    for home in _plain_directories(root / "agent"):
        runtime = home / "home" / "runtime"
        if is_link(home / "home"):
            continue
        found.extend(
            (path, f"agent/{home.name}/{path.name}") for path in _plain_files(runtime) if path.suffix == ".log"
        )
    return found


def copy_logs(root: Path, destination: Path) -> list[str]:
    """Copy the root's logs below ``destination``; return what could not be copied."""
    failures: list[str] = []
    for source, relative in log_files(root):
        target = destination / relative
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        except OSError as error:
            failures.append(f"log {relative} was not copied: {error.strerror or error}")
    return failures


def package_stats(root: Path) -> dict[str, tuple[int, int]]:
    """Each regular file below ``root`` by relative path, as (size, mtime_ns); empty when absent."""
    found: dict[str, tuple[int, int]] = {}
    if not root.is_dir():
        return found
    for directory, _names, files in os.walk(root):
        base = Path(directory)
        for name in files:
            status = (base / name).stat()
            found[(base / name).relative_to(root).as_posix()] = (status.st_size, status.st_mtime_ns)
    return found


def restaged(before: Mapping[str, tuple[int, int]], after: Mapping[str, tuple[int, int]]) -> dict[str, int]:
    """How many files staging wrote (new or changed) and their bytes, and how many it removed."""
    written = [member for member, facts in after.items() if before.get(member) != facts]
    return {
        "files_written": len(written),
        "bytes_written": sum(after[member][0] for member in written),
        "files_removed": len(before.keys() - after.keys()),
    }


def first_answer(
    probe: Callable[[], bool], clock: Callable[[], float], deadline: float, pause: Callable[[float], None]
) -> float:
    """The clock reading at the first successful probe; nothing after the answer is counted."""
    while clock() < deadline:
        if probe():
            return clock()
        pause(_POLL_SECONDS)
    raise UnavailableError("the desktop opened no DevTools endpoint; the window needs an interactive desktop session")


@dataclass(frozen=True, slots=True)
class Launched:
    """One desktop launch: seconds to its first DevTools answer, its endpoint, its process and its watch."""

    seconds: float
    endpoint: str
    process: Any
    watch: Watch


def launch(stack: ExitStack, image: Path, environment: Mapping[str, str], directory: Path) -> Launched:
    """Launch the desktop in a kill-on-close Job held by ``stack``; time it to its first DevTools answer."""
    port = free_port()
    endpoint = f"http://127.0.0.1:{port}"
    watch = Watch(roots=[os.getpid()])
    started = time.monotonic()
    scope, process = stack.enter_context(lane_desktop(image, environment, directory, port))
    watch.members = scope.active_process_ids
    watch.start()
    stack.callback(watch.stop)

    def probe() -> bool:
        with suppress(httpx.HTTPError):
            if httpx.get(f"{endpoint}/json/version", timeout=0.5).status_code == 200:
                return True
        code = desktop_exit_code(process)
        require(code is None, f"the desktop exited with {code} before its DevTools endpoint answered")
        return False

    answered = first_answer(probe, time.monotonic, started + _DEVTOOLS_SECONDS, time.sleep)
    # Answered already: this only requires the endpoint to listen on loopback alone.
    devtools_endpoint(port, process, time.monotonic() + _DEVTOOLS_SECONDS)
    return Launched(answered - started, endpoint, process, watch)


def require_resumed(endpoint: str, entry: str) -> None:
    """Require the desktop to resume the profile's stored sign-in; nobody can type the run's password."""
    with attached(endpoint, entry) as page:
        settled, status = status_until(page, "sign_in_status", "sign_in_observed", _SIGN_IN_SECONDS)
    state = status.get("state") if isinstance(status, Mapping) else None
    require(settled, "the desktop's runtime did not report the sign-in")
    require(state == "present", f"the desktop did not resume the stored sign-in: state {state}")


def hold(stop: Path, stopping: threading.Event, process: Any) -> str:
    """Wait until the stop file appears, a stop signal arrives or the desktop ends; say which."""
    while True:
        if stop.exists():
            return "stop_file"
        if stopping.is_set():
            return "signal"
        if desktop_exit_code(process) is not None:
            return "desktop_closed"
        stopping.wait(_HOLD_SECONDS)


def prepare_profile(programs: Programs, root: Path, results: Path, created: list[Profile]) -> None:
    """Create, sign in, describe and seed the run's synthetic profile through a caller-owned runtime."""
    environment = consumer_environment(root)
    with caller_owned_runtime(programs, environment, results / "runtime-setup.stderr.log") as runtime:
        require(runtime.ready().get("kind") == "runtime_ready", "the setup runtime did not announce readiness")
        # The password is a fresh random one that exists only here and on the CLI's standard input.
        profile = create_profile(programs, environment, _PROFILE)
        created.append(profile)
        persisted = login_profile(programs, environment, profile)
        print(json.dumps({"step": "profile_signed_in", "session_persisted": persisted}), flush=True)
        if not persisted:
            raise UnavailableError(
                "this logon's credential store refused the stored sign-in, so the desktop cannot resume it; "
                "run from an interactive desktop logon"
            )
        profile = identify_profile(programs, environment, profile)
        state_taxpayer(programs, environment, profile)
        rows = seed_ledger(partial(run_cli, programs, environment), LEDGER_SEED, profile.password)
        print(json.dumps({"step": "ledger_seeded", "rows": rows}), flush=True)
        stopped = runtime.stop()
    require(stopped == _RUNTIME_STOPPED, f"the setup runtime exited with {stopped}")


def sign_out(programs: Programs, root: Path, results: Path) -> list[str]:
    """Sign the profile out through a fresh caller-owned runtime; return what did not hold."""
    environment = consumer_environment(root)
    try:
        with caller_owned_runtime(programs, environment, results / "runtime-sign-out.stderr.log") as runtime:
            require(runtime.ready().get("kind") == "runtime_ready", "the sign-out runtime did not announce readiness")
            code, envelope = run_cli(programs, environment, "config", "logout")
            stopped = runtime.stop()
    except AcceptanceError as error:
        return [f"sign-out: {error}; the account's credential store may keep this root's sign-in key"]
    failures = []
    if code != 0:
        failures.append(
            f"sign-out refused: exit {code}, code {error_code(envelope)}; "
            "the account's credential store may keep this root's sign-in key"
        )
    else:
        print(json.dumps({"step": "signed_out"}), flush=True)
    if stopped != _RUNTIME_STOPPED:
        failures.append(f"the sign-out runtime exited with {stopped}")
    return failures


@dataclass(frozen=True, slots=True)
class Options:
    """What a run was asked for."""

    warm: bool
    log_level: str | None


def run_desktop(
    host: TestHost, image: Path, root: Path, results: Path, options: Options, report: Mapping[str, Any]
) -> list[str]:
    """Launch, optionally after a warm-up launch, hold the desktop until told to stop, and close it."""
    environment = person_environment(root, host.lane_package)
    if options.log_level is not None:
        environment[_LOG_LEVEL_VARIABLE] = options.log_level
    failures: list[str] = []
    warmup: float | None = None
    if options.warm:
        with ExitStack() as stack:
            launched = launch(stack, image, environment, results)
            warmup = launched.seconds
            failures.extend(settle_desktop(launched.process, launched.watch))
        require_no_desktop()
    kind = "warm" if options.warm else ("cold" if report["staging"]["files_written"] else "unchanged-package")
    with ExitStack() as stack:
        wall = time.time()
        launched = launch(stack, image, environment, results)
        try:
            require_resumed(launched.endpoint, host.entry)
            measured = {
                "devtools_seconds": launched.seconds,
                "endpoint": launched.endpoint,
                "launch": kind,
                "warmup_devtools_seconds": warmup,
                "staging": report["staging"],
            }
            state = {
                **measured,
                "entry": host.entry,
                "launched_wall": wall,
                "pid": getattr(launched.process, "pid", None),
                "snapshot": report["snapshot"],
                "storage_root": str(root),
            }
            _hold_desktop(launched, results, state)
        finally:
            failures.extend(settle_desktop(launched.process, launched.watch))
    return failures


def _hold_desktop(launched: Launched, results: Path, state: Mapping[str, Any]) -> None:
    """Publish the run's state for the tools that attach, and hold the desktop until told to stop."""
    stop = results / "stop"
    published = results / "state.json"
    published.write_text(json.dumps({**state, "results": str(results), "stop_file": str(stop)}), encoding="utf-8")
    try:
        print(
            json.dumps({"step": "desktop_ready", **state, "state": str(published), "stop_file": str(stop)}), flush=True
        )
        reason = hold(stop, _stop_signals(), launched.process)
        print(json.dumps({"step": "stopping", "reason": reason}), flush=True)
    finally:
        published.unlink(missing_ok=True)


def _stop_signals() -> threading.Event:
    """An event the console's interrupt, break and terminate signals set, so the hold ends through teardown."""
    stopping = threading.Event()

    def stop(_number: int, _frame: object) -> None:
        stopping.set()

    for name in ("SIGINT", "SIGBREAK", "SIGTERM"):
        number = getattr(signal, name, None)
        if number is not None:
            signal.signal(number, stop)
    return stopping


def run(results: Path, options: Options) -> list[str]:
    """Stage, prepare the disposable root, hold the desktop and tear everything down; return what failed."""
    if sys.platform != "win32":
        raise UnavailableError("the disposable desktop run drives the Windows desktop")
    require_no_desktop()
    host = test_host(served=False)
    if not (host.package / "cadrumo.exe").is_file():
        raise UnavailableError(
            f"no {host.configuration} package is staged at {host.package}; "
            f"stage it with: just build-native {host.configuration} bundle"
        )
    snapshot = snapshot_report(require_current(host))
    print(json.dumps({"step": "stage_snapshot", **snapshot}), flush=True)
    before = package_stats(host.lane_package)
    image = stage_package(host, host.lane_package)
    report = {"staging": restaged(before, package_stats(host.lane_package)), "snapshot": snapshot["snapshot"]}
    programs = Programs.of(host.lane_package)
    parent = temporary_parent(os.environ)
    root = create_root(parent)
    print(json.dumps({"step": "storage_root", "root": str(root), "results": str(results)}), flush=True)
    failures: list[str] = []
    absent: UnavailableError | None = None
    created: list[Profile] = []
    try:
        mark_development_root(root)
        try:
            prepare_profile(programs, root, results, created)
            failures.extend(run_desktop(host, image, root, results, options, report))
        finally:
            if created:
                failures.extend(sign_out(programs, root, results))
    except UnavailableError as error:
        absent = error
    except AcceptanceError as error:
        failures.append(str(error))
    finally:
        failures.extend(_teardown(root, parent, results, created))
    if absent is not None:
        if not failures:
            raise absent
        failures.insert(0, f"unavailable: {absent}")
    return failures


def _teardown(root: Path, parent: Path, results: Path, created: list[Profile]) -> list[str]:
    """Copy the logs, drop every results file holding the password, and remove the root."""
    failures = copy_logs(root, results / "logs")
    for profile in created:
        failures.extend(remove_secret_bearing(results, profile.password))
    try:
        left = remove_root(root, parent)
    except AcceptanceError as error:
        return [*failures, str(error)]
    if left:
        failures.append(f"the disposable root was not removed; still present: {'; '.join(left)}")
    else:
        print(json.dumps({"step": "root_removed", "root": str(root)}), flush=True)
    return failures


def run_disposable(argv: list[str] | None) -> int:
    """Run once; exit 0 on pass, 1 on a failure, 3 when a prerequisite is absent."""
    parser = argparse.ArgumentParser(prog="desktop-disposable-root", description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--warm", action="store_true", help="Launch and close the desktop once before measuring.")
    parser.add_argument("--log-level", help=f"Set {_LOG_LEVEL_VARIABLE} for the desktop, such as DEBUG.")
    options = parser.parse_args(argv)
    results = prepare_temp_root(override=RESULTS / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}")
    try:
        failures = run(results, Options(warm=options.warm, log_level=options.log_level))
    except UnavailableError as absent:
        print(json.dumps({"step": "unavailable", "reason": str(absent), "results": str(results)}), flush=True)
        return 3
    except AcceptanceError as failure:
        print(json.dumps({"step": "failed", "reason": str(failure), "results": str(results)}), flush=True)
        return 1
    if failures:
        print(json.dumps({"step": "failed", "reason": "; ".join(failures), "results": str(results)}), flush=True)
        return 1
    print(json.dumps({"step": "passed", "results": str(results)}), flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run in a kill-on-close Job; a process that outlives the run fails it and ends with it."""
    job = LaneJob() if sys.platform == "win32" else None
    if job is None:
        return run_disposable(argv)
    try:
        code = run_disposable(argv)
    except BaseException:  # The Job ends this process, so nothing else would report an escaped error.
        traceback.print_exc()
        code = 1
    left = job.others()
    if left:
        print(json.dumps({"step": "failed", "reason": f"processes outlived the run: {sorted(left)}"}), flush=True)
        code = 1
    job.end(code)


if __name__ == "__main__":
    raise SystemExit(main())
