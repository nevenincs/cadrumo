"""Run the shared agent specs against the packaged desktop, on the person's own signed-in profile.

The lane drives a built package the way a person does, through the desktop
window's WebView2 DevTools endpoint, against the profile the installed desktop
uses, with the provider settings the person stored in Settings. It holds no
provider key and no password, and never creates, signs in or signs out a
profile:

1. refuses to run while a Cadrumo desktop is open: the person's own is never
   stopped, and only a test-build desktop whose lane is gone is;
2. starts the remote-debugging desktop test host, as the desktop image of a
   mirror of its configuration's staged package, in a kill-on-close Job, on
   the per-user installed storage root the canonical environment definition
   names, with the workspace window's DevTools port in
   ``CADRUMO_DEV_DESKTOP_DEVTOOLS_PORT``, and requires the DevTools endpoint to
   listen on loopback only; its attach button takes the run's synthetic files
   from ``CADRUMO_DEV_DESKTOP_LIVE_ATTACH_DIR`` in place of its native dialog, a
   seam only the test host has;
3. waits for the profile's sign-in: the desktop resumes a stored one, and
   otherwise the person signs in in the window while the lane waits;
4. waits for the agent service and reads the agent's own provider catalog,
   requiring a lane that reports ready;
5. records the agent's conversations, runs the live Playwright project, which
   attaches to the window, and deletes every conversation the run created,
   with the documents stored for it, and nothing else;
6. closes the window and requires every process the run started to have ended;
7. scans the started processes' command lines, the run's files, the logs and
   agent files written during the run, and the Playwright traces and
   screenshots for every provider key prefix.

Exit 0 means every step held and every spec passed. Exit 1 names what failed.
Exit 3 means a prerequisite is absent: the test host, the package, an
interactive desktop, a closed desktop, a profile, the person's sign-in, or a
provider lane the agent reports ready. ``--attach-only`` runs only the
attachment check and always ends incomplete. ``--ledger-privacy`` runs the
Ledger page's privacy check in place of the agent specs, needs no provider
lane, and is refused while its Playwright project would trace, screenshot or
film the window. ``--served`` loads the shell from the development server
(``just dev``) for iterating on it; the host, launcher and agent stay real.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import traceback
from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import httpx
import psutil

from cadrumo.core.storage_environment import prepare_temporary_directory

from ..packaging.command_execution import run_command
from ..runtime_lifecycle.caller_owned_root import AcceptanceError, require
from .containment import LaneJob
from .freshness import StageVerdict, stage_verdict
from .package import stage_lane_package
from .scans import (
    ProcessRecord,
    ScanResult,
    descendants,
    merge,
    process_table,
    scan_command_lines,
    scan_file,
    scan_tree,
    survivors,
)

_REPOSITORY: Final = Path(__file__).resolve().parents[2]
_FRONTEND: Final = _REPOSITORY / "native" / "desktop" / "frontend"
_BUILD: Final = _REPOSITORY / "build" / "windows-x64"
_STAGE: Final = _BUILD / "stage"
_TESTING: Final = _BUILD / "desktop" / "testing"
_PACKAGED_ENTRY: Final = "http://tauri.localhost/index.html"
_DEVTOOLS_SECONDS: Final = 120.0
_RUNTIME_SECONDS: Final = 120.0
_SIGN_IN_SECONDS: Final = 15 * 60.0
"""How long the person has to sign in in the window, a person's time and not the machine's."""
_CLOSE_SECONDS: Final = 60.0
_WATCH_SECONDS: Final = 1.0
_DELETE_ATTEMPTS: Final = 3
_DESKTOP_UNAVAILABLE: Final = 69
"""The desktop host's exit when the logon has no interactive desktop for its window."""
_DEVTOOLS_PORT_VARIABLE: Final = "CADRUMO_DEV_DESKTOP_DEVTOOLS_PORT"
"""Where the packaged test host's workspace window, and only it, serves DevTools."""
_ATTACH_VARIABLE: Final = "CADRUMO_DEV_DESKTOP_LIVE_ATTACH_DIR"
"""Where the packaged test host's attach button takes its files from, in place of its dialog."""
_AMBIENT_EXCLUDED: Final = ("CADRUMO_", "PYTHON", "VIRTUAL_ENV", "UV_", "WEBVIEW2_")
"""Settings of this checkout's own environment that the packaged desktop must not inherit."""
_LIVE_CONFIGURATION: Final = _FRONTEND / "tests" / "live" / "playwright.config.ts"
AGENT_PROJECT: Final = "live"
"""The live project of the shared agent specs."""
PRIVACY_PROJECT: Final = "ledger-privacy"
"""The live project that looks for the person's ledger values where the window must not keep them."""
RECORDINGS: Final = ("trace", "screenshot", "video")
"""The Playwright settings that record the window's content, each of which the privacy project keeps off."""
_DEBUG_VARIABLES: Final = ("DEBUG", "PWDEBUG")
"""Playwright's debug logging, which prints protocol traffic and with it the page's values."""

LANE_ATTACHMENTS: Final[Mapping[str, bytes]] = {
    # Stored, and read by the agent: the word is what its reply must name.
    "lane-notes.txt": b"Lane check. The word in this file is GIRASOL.\n",
    "lane-ledger.csv": b"date,concept,amount\n2026-01-15,lane check,12.50\n",
    # An empty ZIP archive: a format the storage refuses.
    "lane-archive.zip": b"PK\x05\x06" + bytes(18),
    # A name the host refuses before sending anything.
    ".lane-hidden.txt": b"hidden\n",
    # Text under a PDF's name: the storage refuses what does not match.
    "lane-mismatch.pdf": b"This is plain text, not a PDF.\n",
}
"""The synthetic files the attach button picks. Nothing in them is anyone's."""


class UnavailableError(Exception):
    """A prerequisite of the lane is absent; the run cannot say pass or fail."""


@dataclass(frozen=True, slots=True)
class TestHost:
    """The recorded remote-debugging desktop host, the shell it loads and the configuration it was built in."""

    executable: Path
    entry: str
    configuration: str
    record: Path

    @property
    def package(self) -> Path:
        """The staged package of the host's own configuration, which the run's package mirrors."""
        return _STAGE / self.configuration / "app"

    @property
    def lane_package(self) -> Path:
        """Where the run's package mirrors :attr:`package` with this host as its desktop image."""
        return _TESTING / "agent-live-package" / self.configuration / "app"


@dataclass(frozen=True, slots=True)
class Desktop:
    """One Cadrumo desktop process running for this account."""

    pid: int
    executable: Path | None
    test_build: bool
    orphaned: bool


@dataclass(slots=True)
class Watch:
    """Every process the run started, recorded as it appears, and the key findings on their command lines."""

    roots: list[int]
    members: Callable[[], tuple[int, ...]] = tuple
    started: set[ProcessRecord] = field(default_factory=set)
    command_lines: list[ScanResult] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None

    def observe(self) -> None:
        """Record the run's processes now and scan the command lines of the new ones."""
        members = self.members()
        table = process_table()
        current = descendants(table, self.roots) | {table[pid] for pid in members if pid in table}
        new = current - self.started
        if new:
            self.command_lines.append(scan_command_lines(new))
            self.started |= new

    def start(self) -> None:
        """Observe in the background until :meth:`stop`."""

        def loop() -> None:
            while not self._stop.wait(_WATCH_SECONDS):
                with suppress(Exception):
                    self.observe()

        self._thread = threading.Thread(target=loop, name="desktop-agent-live-watch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop observing, after one last observation."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=30)
        self.observe()


def person_storage_root() -> Path:
    """The per-user storage root the installed desktop uses, as the canonical environment definition names it."""
    from cadrumo.core.storage_environment import host_installed_default_root

    try:
        root = host_installed_default_root(os.environ)
    except (OSError, ValueError) as refused:
        raise UnavailableError(f"this account has no installed storage root: {refused}") from refused
    if not root.is_dir():
        raise UnavailableError(f"no Cadrumo profile is stored at {root}; create one in the desktop first")
    return root


def person_environment(root: Path, package: Path) -> dict[str, str]:
    """The ambient environment without this checkout's settings, on the person's root and the run's package.

    No secret store is pinned: the desktop reads the sign-in it resumes from
    the account's own credential store, as the installed desktop does.
    """
    environment = {name: value for name, value in os.environ.items() if not name.upper().startswith(_AMBIENT_EXCLUDED)}
    environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(root)
    environment["CADRUMO_DESKTOP_PACKAGE_ROOT"] = str(package)
    return environment


def _under(path: Path, directory: Path) -> bool:
    return os.path.normcase(str(path)).startswith(os.path.normcase(str(directory)) + os.sep)


def classify_desktops(processes: Iterable[Mapping[str, Any]], testing: Path) -> list[Desktop]:
    """The desktop processes among ``processes``, each with whether it is a test build and its lane is gone.

    A ``cadrumo.exe`` that runs a ``--role`` is one of the package's own
    commands, not a desktop. A process whose image cannot be read is taken for
    the person's own.
    """
    found: list[Desktop] = []
    for process in processes:
        if str(process.get("name") or "").lower() != "cadrumo.exe":
            continue
        if "--role" in (process.get("cmdline") or ()):
            continue
        image = process.get("exe")
        executable = Path(image) if image else None
        test_build = executable is not None and _under(executable, testing)
        found.append(Desktop(int(process["pid"]), executable, test_build, not process.get("parent_alive", True)))
    return found


def _desktop_processes() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for process in psutil.process_iter(["pid", "name", "exe", "cmdline", "ppid", "create_time"]):
        info = dict(process.info)
        try:
            parent = psutil.Process(int(info["ppid"])) if info.get("ppid") else None
            info["parent_alive"] = parent is not None and parent.create_time() <= float(info["create_time"] or 0)
        except psutil.Error:
            info["parent_alive"] = False
        rows.append(info)
    return rows


def require_no_desktop() -> None:
    """Refuse while the person's desktop runs, and stop a test-build desktop whose lane is gone.

    The desktop is one instance per account, so the run's own would only hand
    its window to the one already open.
    """
    for desktop in classify_desktops(_desktop_processes(), _TESTING):
        if not desktop.test_build:
            raise UnavailableError(
                f"the Cadrumo desktop is open (process {desktop.pid}); close it, then run the lane again"
            )
        if not desktop.orphaned:
            raise UnavailableError(
                f"another run's test desktop is open (process {desktop.pid}, {desktop.executable}); let it end first"
            )
        with suppress(psutil.NoSuchProcess):
            process = psutil.Process(desktop.pid)
            tree = [*process.children(recursive=True), process]
            for member in tree:
                with suppress(psutil.NoSuchProcess):
                    member.kill()
            _gone, alive = psutil.wait_procs(tree, timeout=_CLOSE_SECONDS)
            if alive:
                raise UnavailableError(f"a leftover test desktop (process {desktop.pid}) did not end")
            print(json.dumps({"step": "leftover_test_desktop_stopped", "pid": desktop.pid}), flush=True)


#: Run in each new shell document after the host's own script: it takes the
#: one-read token, keeps it for the lane, and re-arms the read for the shell.
_SHELL_GRANT_COPIER: Final = """(() => {
    const shell = window.__CADRUMO_SHELL__;
    if (!shell) return;
    const token = shell.token;
    if (!token) return;
    Object.defineProperty(shell, "token", {configurable: true, get() { delete shell.token; return token; }});
    Object.defineProperty(window, "__CADRUMO_LANE_TOKEN__", {configurable: true, value: token});
})()"""


def shell_page(browser: Any, entry: str, deadline: float) -> Any:
    """The desktop's shell page, reloaded so the lane holds its shell token.

    The host gives the token to the shell document once, and the shell reads
    it as it starts, so the lane reloads the page with a script that keeps a
    copy before the shell reads it, then waits for that copy. It waits on the
    page on the shell's origin to appear first, since the workspace window
    opens after the loading window.
    """
    from urllib.parse import urlsplit

    origin = urlsplit(entry)[:2]
    contexts = browser.contexts
    require(len(contexts) == 1, "the live desktop must expose one browser context")
    context = contexts[0]
    while True:
        pages = [page for page in context.pages if urlsplit(page.url)[:2] == origin]
        if pages:
            break
        remaining = deadline - time.monotonic()
        require(remaining > 0, "the desktop's shell page did not open")
        context.wait_for_event("page", timeout=remaining * 1000)
    require(len(pages) == 1, "the live desktop must expose one shell page")
    page = pages[0]
    page.add_init_script(_SHELL_GRANT_COPIER)
    page.reload(wait_until="domcontentloaded", timeout=max(deadline - time.monotonic(), 0) * 1000)
    page.wait_for_function(
        "() => Boolean(window.__CADRUMO_LANE_TOKEN__)",
        timeout=max(deadline - time.monotonic(), 0) * 1000,
    )
    return page


#: Calls one desktop command with the lane's copy of the shell token.
_INVOKE: Final = """async ({command, args}) => {
    const token = window.__CADRUMO_LANE_TOKEN__;
    if (!token) throw new Error('desktop token unavailable');
    try {
        return {ok: await window.__TAURI_INTERNALS__.invoke(command, {...args, token})};
    } catch (error) {
        return {refused: error};
    }
}"""

#: Resolves with the status a desktop command reports once the named condition
#: holds of it, and with the last one when the bound passes first. The host keeps one
#: subscriber for each status, the shell's own, so the lane asks again on each
#: rendered frame instead of subscribing.
_STATUS_UNTIL: Final = """async ({command, until, boundMs}) => {
    const token = window.__CADRUMO_LANE_TOKEN__;
    if (!token) throw new Error('desktop token unavailable');
    const conditions = {
        sign_in_observed: (status) => Boolean(status && status.runtimeAvailable && status.state !== 'unknown'),
        signed_in: (status) => Boolean(status && status.state === 'present'),
        agent_ready: (status) => Boolean(status && status.state === 'ready'),
    };
    const holds = conditions[until];
    if (!holds) throw new Error(`unknown condition ${until}`);
    const bound = Date.now() + boundMs;
    let status = null;
    for (;;) {
        try { status = await window.__TAURI_INTERNALS__.invoke(command, {token}); }
        catch (error) { status = {unreadable: error}; }
        if (holds(status)) return {held: true, status};
        if (Date.now() >= bound) return {held: false, status};
        await new Promise((frame) => requestAnimationFrame(frame));
    }
}"""


#: Resolves with the provider catalog, or with the last refusal once it is not
#: busy or the bound passes. A service still building the catalog answers busy
#: and keeps the answer for the next read, so the lane asks again on each
#: rendered frame, as the agent column asks again.
_CATALOG_SETTLED: Final = """async ({boundMs}) => {
    const token = window.__CADRUMO_LANE_TOKEN__;
    if (!token) throw new Error('desktop token unavailable');
    const bound = Date.now() + boundMs;
    for (;;) {
        try {
            return {ok: await window.__TAURI_INTERNALS__.invoke('agent_provider_catalog', {token})};
        } catch (error) {
            const busy = error && error.code === 'agent_service_busy';
            if (!busy || Date.now() >= bound) return {refused: error};
        }
        await new Promise((next) => requestAnimationFrame(next));
    }
}"""


def provider_catalog(page: Any, seconds: float) -> Any:
    """The agent's provider catalog once the service has built it, or a failure naming its refusal."""
    answer = page.evaluate(_CATALOG_SETTLED, {"boundMs": seconds * 1000})
    if "refused" in answer:
        raise AcceptanceError(f"agent_provider_catalog: {json.dumps(answer['refused'])}")
    return answer.get("ok")


def invoke(page: Any, command: str, **args: Any) -> Any:
    """The result of one desktop command, or a failure naming its refusal."""
    answer = page.evaluate(_INVOKE, {"command": command, "args": args})
    if "refused" in answer:
        raise AcceptanceError(f"{command}: {json.dumps(answer['refused'])}")
    return answer.get("ok")


def status_until(page: Any, command: str, until: str, seconds: float) -> tuple[bool, Any]:
    """Whether ``command``'s status came to satisfy the named condition within ``seconds``, and the last status read."""
    answer = page.evaluate(_STATUS_UNTIL, {"command": command, "until": until, "boundMs": seconds * 1000})
    return bool(answer["held"]), answer["status"]


#: Resolves once the profile is signed in, or with the desktop's sign-in
#: attempts that failed after ``afterSequence``, or with nothing once the bound
#: passes. The desktop records each sign-in command it runs in its diagnostics;
#: they are read on every thirtieth rendered frame.
_SIGN_IN_OR_FAILURE: Final = """async ({boundMs, afterSequence}) => {
    const token = window.__CADRUMO_LANE_TOKEN__;
    if (!token) throw new Error('desktop token unavailable');
    const invoke = (command, args) => window.__TAURI_INTERNALS__.invoke(command, {...args, token});
    const bound = Date.now() + boundMs;
    let status = null;
    for (let frame = 0; ; frame++) {
        try { status = await invoke('sign_in_status', {}); } catch (error) { status = {unreadable: error}; }
        if (status && status.state === 'present') return {status, events: []};
        if (frame % 30 === 0) {
            let snapshot = null;
            try { snapshot = await invoke('diagnostics_snapshot', {after: 0}); } catch (error) { snapshot = null; }
            const events = ((snapshot && snapshot.events) || []).filter((event) => event.sequence > afterSequence);
            if (sign_in_failed(events)) return {status, events};
        }
        if (Date.now() >= bound) return {status, events: []};
        await new Promise((next) => requestAnimationFrame(next));
    }
    function sign_in_failed(events) {
        return events.some((event) => event.kind === 'helper_result' && event.failure
            && event.helperResult && event.helperResult.command === 'config.login');
    }
}"""


def sign_in_failures(events: Iterable[Mapping[str, Any]]) -> list[tuple[int, str]]:
    """Each failed sign-in the desktop's diagnostics record, by sequence, as ``code`` or ``code (reason)``."""
    failures: list[tuple[int, str]] = []
    for event in events:
        result = event.get("helperResult")
        failure = event.get("failure")
        if event.get("kind") != "helper_result" or not isinstance(result, Mapping) or not isinstance(failure, Mapping):
            continue
        if result.get("command") != "config.login":
            continue
        code = str(failure.get("code") or "unknown")
        reason = result.get("reason") or result.get("code") or failure.get("reason")
        failures.append((int(event.get("sequence") or 0), f"{code} ({reason})" if reason else code))
    return sorted(failures)


def wait_for_person(page: Any) -> Mapping[str, Any]:
    """Wait the person's time for their sign-in, saying each failed attempt as the desktop records it.

    The person may try again after a failure, so the wait goes on; when it
    ends without a sign-in, the refusal names the last failure seen, not a
    silence that never happened.
    """
    deadline = time.monotonic() + _SIGN_IN_SECONDS
    seen = 0
    failed: list[str] = []
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if failed:
                raise UnavailableError(f"sign-in failed: {failed[-1]} ({len(failed)} attempts failed)")
            raise UnavailableError(f"nobody signed in within {_SIGN_IN_SECONDS / 60:.0f} minutes")
        answer = page.evaluate(_SIGN_IN_OR_FAILURE, {"boundMs": remaining * 1000, "afterSequence": seen})
        status = answer.get("status") or {}
        if status.get("state") == "present":
            return status
        for sequence, failure in sign_in_failures(answer.get("events") or ()):
            seen = max(seen, sequence)
            failed.append(failure)
            print(
                json.dumps({"step": "sign_in_failed", "failure": failure, "prompt": "Sign in again in the window."}),
                flush=True,
            )


def wait_for_sign_in(page: Any) -> str:
    """Wait for the person's sign-in, prompting them once when the desktop has none to resume; return the profile."""
    settled, status = status_until(page, "sign_in_status", "sign_in_observed", _RUNTIME_SECONDS)
    if not settled:
        raise AcceptanceError(f"the desktop's runtime did not report the sign-in: {json.dumps(status)}")
    if not status.get("active_profile") and status.get("state") != "present":
        raise UnavailableError("no profile is selected; create or select one in the Cadrumo desktop first")
    if status.get("state") != "present":
        print(
            json.dumps(
                {
                    "step": "waiting_for_sign_in",
                    "prompt": f"Sign in to {status.get('active_profile')} in the Cadrumo test window; the lane waits.",
                }
            ),
            flush=True,
        )
        status = wait_for_person(page)
    print(json.dumps({"step": "signed_in"}), flush=True)
    return str(status.get("active_profile"))


def lane_problems(lane: Mapping[str, Any]) -> list[str]:
    """What keeps a provider lane from serving a run, as the agent column judges it; empty when it is ready."""
    health = lane.get("health") or {}
    problems = [
        f"{facet} {health.get(facet)}"
        for facet in ("configured", "transport", "catalog")
        if health.get(facet) != "available"
    ]
    if health.get("authentication") not in ("authenticated", "not_applicable"):
        problems.append(f"authentication {health.get('authentication')}")
    if health.get("selectable") is not True:
        problems.append("not selectable" + (f" ({', '.join(health['reasons'])})" if health.get("reasons") else ""))
    if lane.get("executable") is not True:
        problems.append("not executable")
    if lane.get("model_source") != "declared" and not (lane.get("catalog") or {}).get("models"):
        problems.append("no models")
    return problems


def ready_lanes(catalog: Mapping[str, Any]) -> tuple[list[str], dict[str, list[str]]]:
    """The ready lanes in the order the agent column offers them, and what each other lane lacks.

    The column groups lanes by provider in the order they were served, the
    API before the command-line app, and starts on the first ready one.
    """
    served = [lane for lane in catalog.get("providers") or () if isinstance(lane, Mapping)]
    providers = list(dict.fromkeys(str(lane.get("provider_id")) for lane in served))
    ordered = sorted(
        served,
        key=lambda lane: (providers.index(str(lane.get("provider_id"))), lane.get("transport") == "cli"),
    )
    ready: list[str] = []
    missing: dict[str, list[str]] = {}
    for lane in ordered:
        name = f"{lane.get('provider_id')}/{lane.get('transport')}"
        problems = lane_problems(lane)
        if problems:
            missing[name] = problems
        else:
            ready.append(name)
    return ready, missing


def require_ready_lane(page: Any) -> str:
    """Wait for the agent service, then require a provider lane its catalog reports ready; return it."""
    ready, status = status_until(page, "agent_status", "agent_ready", _RUNTIME_SECONDS)
    if not ready:
        raise UnavailableError(f"the agent service is not ready: {json.dumps(status)}")
    catalog = provider_catalog(page, _RUNTIME_SECONDS)
    if not isinstance(catalog, Mapping):
        raise AcceptanceError(f"the agent's provider catalog is unreadable: {json.dumps(catalog)}")
    lanes, missing = ready_lanes(catalog)
    if not lanes:
        lacking = "; ".join(f"{name}: {', '.join(problems)}" for name, problems in missing.items()) or "none served"
        raise UnavailableError(
            f"no provider lane is ready ({lacking}); "
            "store a key in Settings > Providers, or sign in to a provider there"
        )
    print(json.dumps({"step": "provider_lane", "lane": lanes[0], "ready": lanes}), flush=True)
    return lanes[0]


def conversation_ids(page: Any) -> set[str]:
    """The ids of every conversation the agent column lists."""
    records = invoke(page, "agent_conversations")
    require(isinstance(records, list), f"the conversations are unreadable: {json.dumps(records)}")
    return {str(record["id"]) for record in records if isinstance(record, Mapping) and "id" in record}


def created_during(before: set[str], after: set[str]) -> set[str]:
    """The conversations the run created: listed after it and not before it."""
    return after - before


def delete_conversations(page: Any, created: set[str]) -> None:
    """Delete the run's conversations, with their documents, asking again while a deletion is partial."""
    for conversation in sorted(created):
        for attempt in range(_DELETE_ATTEMPTS):
            answer = page.evaluate(
                _INVOKE, {"command": "agent_conversation_delete", "args": {"conversationId": conversation}}
            )
            if "refused" not in answer:
                break
            refused = answer["refused"]
            partial = isinstance(refused, Mapping) and refused.get("code") == "agent_conversation_delete_incomplete"
            if not partial or attempt == _DELETE_ATTEMPTS - 1:
                raise AcceptanceError(f"the run's conversation {conversation} was not deleted: {json.dumps(refused)}")
    left = created & conversation_ids(page)
    require(not left, f"the run's conversations remain after deletion: {sorted(left)}")


def test_host(served: bool) -> TestHost:
    """Read the remote-debugging host record the host build wrote, refusing a changed image."""
    import hashlib

    variant = "served" if served else "packaged"
    record = _TESTING / variant / "host.json"
    build = (
        "node native/desktop/tests/packaged/host.mjs --served (with CADRUMO_CMAKE_BINARY_DIR, CADRUMO_BUILD_CONFIG "
        "and CADRUMO_NATIVE_CONTRACT set)"
        if served
        else "just build-native Release desktop-packaged-host"
    )
    if not record.is_file():
        raise UnavailableError(f"no remote-debugging desktop host is built; build it with: {build}")
    value = json.loads(record.read_text(encoding="utf-8"))
    executable = Path(value.get("executable", ""))
    if "webview2-remote-debugging" not in value.get("features", ()) or not executable.is_file():
        raise UnavailableError(f"the desktop host record is not a remote-debugging host; rebuild it with: {build}")
    if hashlib.sha256(executable.read_bytes()).hexdigest() != value.get("sha256"):
        raise UnavailableError(f"the desktop host changed after its build recorded it; rebuild it with: {build}")
    shell = value.get("shell")
    configuration = value.get("configuration")
    if configuration not in ("Debug", "Release"):
        raise UnavailableError(f"the desktop host record names no build configuration; rebuild it with: {build}")
    return TestHost(executable, f"{shell}index.html" if served and shell else _PACKAGED_ENTRY, configuration, record)


def require_current(host: TestHost) -> StageVerdict:
    """Refuse a stage or test host whose build records do not vouch for its bytes.

    Inputs edited since the stage was built do not refuse the run: the verdict
    names the build each component's bytes come from and what was edited since,
    for the run to report with its results.
    """
    configuration = host.configuration
    verdict = stage_verdict(_BUILD, configuration)
    if verdict.refusals:
        raise UnavailableError("; ".join(verdict.refusals))
    return verdict


def snapshot_report(verdict: StageVerdict) -> dict[str, object]:
    """What the run's results are for: each component's build, and the inputs edited since it."""
    edited = sorted({name for names in verdict.changed.values() for name in names})
    return {
        "snapshot": verdict.snapshot,
        "newer_edits": len(edited),
        "edited_since": edited,
        "summary": (
            "results are for snapshot "
            + ", ".join(f"{component} {build}" for component, build in verdict.snapshot.items())
            + (f"; {len(edited)} inputs changed since" if edited else "; no input changed since")
        ),
    }


def stage_package(host: TestHost, destination: Path) -> Path:
    """Mirror the host's staged package into ``destination`` with the host as its desktop; return its image."""
    from ..packaging.native.layout import load_layout

    target = json.loads((_BUILD / "generated" / "identity.json").read_text(encoding="utf-8"))["target"]
    try:
        image = stage_lane_package(load_layout(target), host.package, host.executable, destination)
    except (OSError, ValueError) as refused:
        raise UnavailableError(f"the lane package could not be staged from {host.package}: {refused}") from refused
    print(json.dumps({"step": "package_staged", "package": str(destination)}), flush=True)
    return image


def require_served_shell(entry: str) -> None:
    """Require the development server to answer and to be this checkout's own."""
    port = int(entry.split(":")[2].split("/")[0])
    owners = [
        connection.pid
        for connection in psutil.net_connections(kind="tcp")
        if connection.status == psutil.CONN_LISTEN and connection.laddr and connection.laddr.port == port
    ]
    if not owners:
        raise UnavailableError(f"nothing serves the shell on port {port}; start it with: just dev")
    for pid in owners:
        with suppress(psutil.Error):
            process = psutil.Process(pid)
            places = [Path(process.cwd()), *(Path(parent.cwd()) for parent in process.parents()[:2])]
            if any(place.resolve() in {_REPOSITORY, _FRONTEND} for place in places):
                return
    raise UnavailableError(f"port {port} is served by another checkout; stop it and run just dev here")


def write_lane_attachments(directory: Path) -> Path:
    """Write the files the attach button picks into a fresh ``directory``."""
    directory.mkdir(parents=True)
    for name, content in LANE_ATTACHMENTS.items():
        (directory / name).write_bytes(content)
    return directory


def written_directories(root: Path) -> tuple[Path, ...]:
    """Where the desktop, the runtime and the agent write logs and files; those written during a run are the run's."""
    return (root / "logs", root / "agent")


#: Prints the live configuration's top-level and per-project ``use`` as JSON.
_CONFIGURATION_READER: Final = """
const configuration = (await import(process.argv[1])).default;
const projects = (configuration.projects ?? []).map((project) => ({name: project.name, use: project.use ?? {}}));
process.stdout.write(JSON.stringify({use: configuration.use ?? {}, projects}));
"""


def live_configuration(results: Path) -> dict[str, Any]:
    """The live Playwright configuration as Node evaluates it: its ``use`` and each project's name and ``use``."""
    node = shutil.which("node")
    if node is None:
        raise UnavailableError("node is not on PATH")
    environment = {name: value for name, value in os.environ.items() if not name.upper().startswith(_AMBIENT_EXCLUDED)}
    environment["CADRUMO_DEV_DESKTOP_LIVE_RESULTS"] = str(results)
    outcome = run_command(
        [node, "--input-type=module", "-e", _CONFIGURATION_READER, _LIVE_CONFIGURATION.as_uri()],
        cwd=_FRONTEND,
        environment=environment,
        timeout_seconds=120,
    )
    require(outcome.returncode == 0, f"the live configuration did not load: {outcome.stderr.strip()[-2000:]}")
    return json.loads(outcome.stdout)


def recording_problems(configuration: Mapping[str, Any], project: str) -> list[str]:
    """What would let ``project`` record the window: each recording setting it does not turn off.

    A project's ``use`` overrides the configuration's, so a setting the
    project leaves out falls back to the top level, and only an explicit
    ``"off"`` counts as off.
    """
    found = [entry for entry in configuration.get("projects") or () if entry.get("name") == project]
    if len(found) != 1:
        return [f"the live configuration declares {len(found)} projects named {project}"]
    use = {**(configuration.get("use") or {}), **(found[0].get("use") or {})}
    return [f"{name} is {json.dumps(use.get(name))}" for name in RECORDINGS if use.get(name) != "off"]


def playwright_arguments(arguments: Sequence[str], *, attach_only: bool, ledger_privacy: bool) -> list[str]:
    """The Playwright arguments of a run: the one project it runs, the caller's arguments, and its files."""
    if ledger_privacy:
        return ["--project", PRIVACY_PROJECT, *arguments]
    if attach_only:
        return ["--project", AGENT_PROJECT, *arguments, "tests/live/attach.live.ts"]
    return ["--project", AGENT_PROJECT, *arguments]


@dataclass(frozen=True, slots=True)
class PrivacyScope:
    """What the privacy check scans: the run's directory, and what was written below ``written`` since the start."""

    run_directory: Path
    written: tuple[Path, ...]
    started_at: float


def playwright_environment(
    entry: str, endpoint: str, results: Path, language: str, privacy: PrivacyScope | None = None
) -> dict[str, str]:
    """The live project's environment: the ambient one without this checkout's settings, and the run's coordinates.

    The privacy check also gets what it scans, keeps Playwright from writing
    the page's accessibility snapshot beside a failure, and runs without
    Playwright's debug logging.
    """
    environment = {name: value for name, value in os.environ.items() if not name.upper().startswith(_AMBIENT_EXCLUDED)}
    environment |= {
        "CADRUMO_CMAKE_BINARY_DIR": str(_BUILD),
        "CADRUMO_DEV_DESKTOP_LIVE_ENDPOINT": endpoint,
        "CADRUMO_DEV_DESKTOP_LIVE_ENTRY": entry,
        "CADRUMO_DEV_DESKTOP_LIVE_RESULTS": str(results),
        # The window speaks the profile's language, so the specs read its words.
        "CADRUMO_DEV_DESKTOP_LIVE_LANGUAGE": language,
    }
    if privacy is not None:
        for name in [name for name in environment if name.upper() in _DEBUG_VARIABLES]:
            del environment[name]
        environment |= {
            "CADRUMO_DEV_DESKTOP_LIVE_RUN_DIRECTORY": str(privacy.run_directory),
            "CADRUMO_DEV_DESKTOP_LIVE_WRITTEN": json.dumps([str(directory) for directory in privacy.written]),
            "CADRUMO_DEV_DESKTOP_LIVE_STARTED_AT": repr(privacy.started_at),
            "PLAYWRIGHT_NO_COPY_PROMPT": "1",
        }
    return environment


def free_port() -> int:
    """A loopback TCP port that was free a moment ago."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _exit_code(process: Any) -> int | None:
    """The desktop's exit code, or ``None`` while it runs."""
    from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

    try:
        return int(process.wait(timeout=0))
    except RefusalError as error:
        if error.reason is RefusalCode.TIMEOUT:
            return None
        raise


def devtools_endpoint(port: int, host: Any, deadline: float) -> str:
    """Wait for the window's DevTools endpoint, and require it to listen on loopback only."""
    endpoint = f"http://127.0.0.1:{port}"
    while True:
        with suppress(httpx.HTTPError):
            if httpx.get(f"{endpoint}/json/version", timeout=2).status_code == 200:
                break
        code = _exit_code(host)
        if code == _DESKTOP_UNAVAILABLE:
            raise UnavailableError("this logon has no interactive desktop for the window; run the lane from it")
        if code == 0:
            raise UnavailableError("another Cadrumo desktop took the window; close it, then run the lane again")
        if code is not None:
            raise AcceptanceError(f"the desktop exited with {code} before its DevTools endpoint answered")
        if time.monotonic() > deadline:
            raise UnavailableError(
                "the desktop opened no DevTools endpoint; the window needs an interactive desktop session"
            )
        time.sleep(0.5)
    listening = {
        connection.laddr.ip
        for connection in psutil.net_connections(kind="tcp")
        if connection.status == psutil.CONN_LISTEN and connection.laddr and connection.laddr.port == port
    }
    require(bool(listening) and listening <= {"127.0.0.1", "::1"}, f"DevTools listens beyond loopback: {listening}")
    return endpoint


def close_windows(pid: int) -> int:
    """Ask every application window of ``pid`` to close, as the title bar's close does; return how many.

    Tool windows are not the person's to close: the window toolkit's own event
    target is one, and closing it would end the event loop that exits the desktop.
    """
    import win32con
    import win32gui
    import win32process

    windows: list[int] = []

    def collect(handle: int, _extra: object) -> bool:
        if (
            win32process.GetWindowThreadProcessId(handle)[1] == pid
            and win32gui.IsWindowVisible(handle)
            and not win32gui.GetWindowLong(handle, win32con.GWL_EXSTYLE) & win32con.WS_EX_TOOLWINDOW
            and not win32gui.GetWindow(handle, win32con.GW_OWNER)
        ):
            windows.append(handle)
        return True

    win32gui.EnumWindows(collect, None)
    for handle in windows:
        win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)
    return len(windows)


def playwright(environment: Mapping[str, str], arguments: list[str]) -> int:
    """Run the live project as a child of this lane and return its exit status."""
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if npx is None:
        raise UnavailableError("npx is not on PATH")
    return run_command(
        [npx, "playwright", "test", "-c", "tests/live/playwright.config.ts", *arguments],
        cwd=_FRONTEND,
        environment=dict(environment),
        inherit_output=True,
    ).returncode


@contextmanager
def lane_desktop(executable: Path, environment: Mapping[str, str], directory: Path, port: int) -> Generator[Any]:
    """Run the desktop in a kill-on-close Job for the block; the Job is reaped however the block ends."""
    from cadrumo_client.transport.windows_process import WindowsProcessScope

    scope = WindowsProcessScope()
    try:
        process = scope.launch(
            executable=executable,
            arguments=("--gui",),
            directory=directory,
            environment={**environment, _DEVTOOLS_PORT_VARIABLE: str(port)},
        )
        yield scope, process
    finally:
        scope.terminate(timeout=30)


@contextmanager
def attached(endpoint: str, entry: str) -> Generator[Any]:
    """The shell page, with the lane's copy of its token, for the block; the lane lets go of the window after."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        browser = driver.chromium.connect_over_cdp(endpoint)
        page = shell_page(browser, entry, time.monotonic() + _DEVTOOLS_SECONDS)
        try:
            yield page
        finally:
            with suppress(Exception):
                page.evaluate("() => { delete window.__CADRUMO_LANE_TOKEN__; }")


_ACKNOWLEDGE_SECONDS: Final = 5 * 60.0
"""How long the window waits for the person to read why the run ended, a person's time."""

#: Covers the window with why the test run ended, and a button that closes it.
_ENDED: Final = """({title, why, close}) => {
    const cover = document.createElement('div');
    cover.setAttribute('role', 'alertdialog');
    cover.setAttribute('aria-label', title);
    cover.style.cssText = 'position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;'
        + 'justify-content:center;background:rgba(0,0,0,.55);font:14px system-ui,sans-serif';
    const card = document.createElement('div');
    card.style.cssText = 'max-width:42rem;background:#fff;color:#111;padding:1.5rem;border-radius:.75rem';
    const heading = document.createElement('h2');
    heading.textContent = title;
    const text = document.createElement('p');
    text.style.whiteSpace = 'pre-wrap';
    text.textContent = why;
    const button = document.createElement('button');
    button.textContent = close;
    button.addEventListener('click', () => { window.__CADRUMO_LANE_ACKNOWLEDGED__ = true; });
    card.append(heading, text, button);
    cover.append(card);
    document.body.append(cover);
    button.focus();
}"""


def tell_person(endpoint: str, entry: str, why: str) -> None:
    """Show the person why the test run ended in the window, and wait for them to close it.

    The lane closes the window when it ends; without this the window would
    just vanish on a failure. The wait is the person's and is bounded, so an
    unattended run still ends.
    """
    print(json.dumps({"step": "telling_person", "reason": why}), flush=True)
    with attached(endpoint, entry) as page:
        page.evaluate(
            _ENDED,
            {
                "title": "The Cadrumo test run ended without passing",
                "why": f"{why}\n\nThis test window closes when you press the button below.",
                "close": "Close the test window",
            },
        )
        with suppress(Exception):
            page.wait_for_function(
                "() => window.__CADRUMO_LANE_ACKNOWLEDGED__ === true", timeout=_ACKNOWLEDGE_SECONDS * 1000
            )


def scan_written_since(directories: Sequence[Path], since: float) -> ScanResult:
    """Scan every file below ``directories`` written at or after ``since``, following no link."""
    results: list[ScanResult] = []
    unreadable: list[str] = []

    def unlisted(error: OSError) -> None:
        unreadable.append(f"directory {error.filename}")

    for directory in directories:
        if not directory.is_dir():
            continue
        for place, _subdirectories, files in os.walk(directory, followlinks=False, onerror=unlisted):
            for name in files:
                path = Path(place, name)
                with suppress(OSError):
                    if path.is_symlink() or not path.is_file() or path.stat().st_mtime < since:
                        continue
                results.append(scan_file(path))
    return merge(*results, ScanResult((), tuple(unreadable)))


def run(
    run_directory: Path, *, served: bool, attach_only: bool, arguments: list[str], ledger_privacy: bool = False
) -> list[str]:
    """Run the lane in ``run_directory``; return what it could not prove."""
    if sys.platform != "win32":
        raise UnavailableError("the lane drives the Windows desktop")
    unproven: list[str] = []
    results = run_directory / "playwright"
    if ledger_privacy:
        recording = recording_problems(live_configuration(results), PRIVACY_PROJECT)
        if recording:
            raise AcceptanceError(f"the {PRIVACY_PROJECT} project would record the window: {'; '.join(recording)}")
    host = test_host(served)
    if served:
        require_served_shell(host.entry)
    if not (host.package / "cadrumo.exe").is_file():
        raise UnavailableError(
            f"no {host.configuration} package is staged at {host.package}; "
            f"stage it with: just build-native {host.configuration} bundle"
        )
    snapshot = snapshot_report(require_current(host))
    print(json.dumps({"step": "stage_snapshot", **snapshot}), flush=True)
    require_no_desktop()
    root = person_storage_root()
    package = host.lane_package
    desktop_image = stage_package(host, package)
    results.mkdir(parents=True)
    attachments = write_lane_attachments(run_directory / "attach")
    environment = person_environment(root, package)
    print(json.dumps({"step": "storage_root", "root": str(root)}), flush=True)

    started_before = descendants(process_table(), [os.getpid()])
    require(not started_before, f"processes already run under the lane: {sorted(p.pid for p in started_before)}")
    watch = Watch(roots=[os.getpid()])
    port = free_port()
    absent: UnavailableError | None = None
    failures: list[str] = []
    started_at = time.time()
    # Only the desktop is told where the attach button's files are.
    desktop_environment = {**environment, _ATTACH_VARIABLE: str(attachments)}
    with lane_desktop(desktop_image, desktop_environment, run_directory, port) as (scope, desktop):
        watch.members = scope.active_process_ids
        watch.start()
        endpoint: str | None = None
        before: set[str] | None = None
        try:
            endpoint = devtools_endpoint(port, desktop, time.monotonic() + _DEVTOOLS_SECONDS)
            print(json.dumps({"step": "desktop_attached", "endpoint": endpoint}), flush=True)
            with attached(endpoint, host.entry) as page:
                wait_for_sign_in(page)
                language = str((invoke(page, "desktop_language_read") or {}).get("language") or "en")
                if attach_only:
                    unproven.append("agent specs: --attach-only ran only the attachment check")
                elif not ledger_privacy:
                    require_ready_lane(page)
                before = conversation_ids(page)
            privacy = PrivacyScope(run_directory, written_directories(root), started_at) if ledger_privacy else None
            status = playwright(
                playwright_environment(host.entry, endpoint, results, language, privacy),
                playwright_arguments(arguments, attach_only=attach_only, ledger_privacy=ledger_privacy),
            )
            print(json.dumps({"step": "playwright", "exit_code": status}), flush=True)
            if status != 0:
                failures.append(f"the live project failed with exit {status}; report: {results / 'results.json'}")
        except UnavailableError as error:
            absent = error
        except AcceptanceError as error:
            failures.append(str(error))
        finally:
            if endpoint is not None and before is not None:
                try:
                    with attached(endpoint, host.entry) as page:
                        created = created_during(before, conversation_ids(page))
                        delete_conversations(page, created)
                    print(json.dumps({"step": "conversations_deleted", "count": len(created)}), flush=True)
                except Exception as error:  # A conversation left behind is the person's to see.
                    failures.append(f"the run's conversations were not cleaned up: {error}")
            if endpoint is not None and (failures or absent is not None):
                why = "; ".join(failures) or str(absent)
                with suppress(Exception):
                    tell_person(endpoint, host.entry, why)
            failures.extend(_settle(desktop, watch))
    scan = merge(
        *watch.command_lines,
        scan_tree([run_directory]),
        scan_written_since(written_directories(root), started_at),
    )
    failures.extend(f"provider key prefix in the {finding.location} ({finding.encoding})" for finding in scan.findings)
    failures.extend(f"not scanned, unreadable: {place}" for place in scan.unreadable)
    if scan.clean:
        print(json.dumps({"step": "key_scan_clean", "processes": len(watch.started)}), flush=True)
    # Whatever the outcome, it is the outcome for this snapshot.
    print(json.dumps({"step": "results_snapshot", "summary": snapshot["summary"]}), flush=True)
    if failures:
        if absent is not None:
            failures.insert(0, f"unavailable: {absent}")
        raise AcceptanceError("; ".join(failures))
    if absent is not None:
        raise absent
    return unproven


def _wait_for_exit(started: Iterable[ProcessRecord]) -> None:
    """Wait on the started processes that still run until they end or the close bound passes."""
    running: list[psutil.Process] = []
    for record in started:
        with suppress(psutil.Error):
            process = psutil.Process(record.pid)
            if process.ppid() == record.parent:
                running.append(process)
    psutil.wait_procs(running, timeout=_CLOSE_SECONDS)


def _settle(desktop: Any, watch: Watch) -> list[str]:
    """Close the window, and return what the run left behind."""
    failures: list[str] = []
    with suppress(Exception):
        watch.observe()
    if _exit_code(desktop) is None:
        close_windows(desktop.pid)
        with suppress(Exception):
            desktop.wait(timeout=_CLOSE_SECONDS)
    if _exit_code(desktop) is None:
        failures.append(f"the desktop did not close within {_CLOSE_SECONDS:.0f}s of its close request")
    watch.stop()
    _wait_for_exit(watch.started)
    left = survivors(watch.started, process_table())
    if left:
        failures.append("processes the run started survive it: " + ", ".join(f"{p.pid}:{p.name}" for p in left))
    else:
        print(json.dumps({"step": "no_surviving_processes", "started": len(watch.started)}), flush=True)
    return failures


def main(argv: list[str] | None = None) -> int:
    """Run the lane in its own kill-on-close Job; a process that outlives the run fails it."""
    job = LaneJob() if sys.platform == "win32" else None
    if job is None:
        return _main(argv)
    try:
        code = _main(argv)
    except BaseException:  # The Job ends the lane, so nothing else would report an escaped error.
        traceback.print_exc()
        code = 1
    left = job.others()
    if left:
        reason = f"processes outlived the run and end with the lane: {sorted(left)}"
        print(json.dumps({"step": "failed", "reason": reason}), flush=True)
        code = 1
    job.end(code)


def _main(argv: list[str] | None) -> int:
    """Run the lane; exit 0 on pass, 1 on a failure, 3 when a prerequisite is absent."""
    parser = argparse.ArgumentParser(prog="desktop-agent-live", description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--served", action="store_true", help="Load the shell from the development server.")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--attach-only", action="store_true", help="Run only the attachment check.")
    selection.add_argument(
        "--ledger-privacy",
        action="store_true",
        help="Run the Ledger page's privacy check on the person's own ledger in place of the agent specs.",
    )
    parser.add_argument("--keep", action="store_true", help="Keep the run directory after a pass.")
    parser.add_argument("playwright", nargs="*", help="Arguments after -- go to Playwright, such as -g PATTERN.")
    options = parser.parse_args(argv)
    run_directory = Path(
        tempfile.mkdtemp(
            prefix=f"desktop-agent-live-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-", dir=prepare_temporary_directory()
        )
    )
    base = run_directory.parent
    try:
        unproven = run(
            run_directory,
            served=options.served,
            attach_only=options.attach_only,
            arguments=options.playwright,
            ledger_privacy=options.ledger_privacy,
        )
    except UnavailableError as absent:
        # Nothing ran that a kept directory would explain, so only --keep keeps it.
        if not options.keep:
            _remove_run(run_directory, base)
        print(json.dumps({"step": "unavailable", "reason": str(absent)}), flush=True)
        return 3
    except AcceptanceError as failure:
        print(json.dumps({"step": "failed", "reason": str(failure), "kept": str(run_directory)}), flush=True)
        return 1
    if unproven:
        print(json.dumps({"step": "incomplete", "unproven": unproven, "kept": str(run_directory)}), flush=True)
        return 3
    if not options.keep:
        _remove_run(run_directory, base)
    print(json.dumps({"step": "passed"}), flush=True)
    return 0


def _remove_run(run_directory: Path, base: Path) -> None:
    """Remove a run directory this lane created, and nothing else."""
    resolved = run_directory.resolve()
    if resolved.parent != base.resolve() or not resolved.name.startswith("desktop-agent-live-"):
        raise AcceptanceError(f"refusing to remove {resolved}: not a lane run directory")
    shutil.rmtree(resolved)
