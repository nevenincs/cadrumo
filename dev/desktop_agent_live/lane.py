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
import time
import traceback
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

import httpx
import psutil

from cadrumo.core.storage_environment import prepare_temporary_directory

from ..packaging.command_execution import run_command
from ..runtime_lifecycle.caller_owned_root import AcceptanceError, require
from .browser_scripts import CATALOG_SETTLED, ENDED, INVOKE, SHELL_GRANT_COPIER, SIGN_IN_OR_FAILURE, STATUS_UNTIL
from .containment import LaneJob
from .desktop_cleanup import Watch, desktop_exit_code, settle_desktop
from .desktop_processes import person_environment, person_storage_root, require_no_desktop
from .lane_diagnostics import ready_lanes, sign_in_failures
from .lane_errors import UnavailableError
from .lane_stage import TestHost, require_current, snapshot_report, stage_package, test_host
from .scans import (
    ScanResult,
    descendants,
    merge,
    process_table,
    scan_file,
    scan_tree,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

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


#: Run in each new shell document after the host's own script: it takes the
#: one-read token, keeps it for the lane, and re-arms the read for the shell.


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
    page.add_init_script(SHELL_GRANT_COPIER)
    page.reload(wait_until="domcontentloaded", timeout=max(deadline - time.monotonic(), 0) * 1000)
    page.wait_for_function(
        "() => Boolean(window.__CADRUMO_LANE_TOKEN__)",
        timeout=max(deadline - time.monotonic(), 0) * 1000,
    )
    return page


#: Calls one desktop command with the lane's copy of the shell token.

#: Resolves with the status a desktop command reports once the named condition
#: holds of it, and with the last one when the bound passes first. The host keeps one
#: subscriber for each status, the shell's own, so the lane asks again on each
#: rendered frame instead of subscribing.


#: Resolves with the provider catalog, or with the last refusal once it is not
#: busy or the bound passes. A service still building the catalog answers busy
#: and keeps the answer for the next read, so the lane asks again on each
#: rendered frame, as the agent column asks again.


def provider_catalog(page: Any, seconds: float) -> Any:
    """The agent's provider catalog once the service has built it, or a failure naming its refusal."""
    answer = page.evaluate(CATALOG_SETTLED, {"boundMs": seconds * 1000})
    if "refused" in answer:
        raise AcceptanceError(f"agent_provider_catalog: {json.dumps(answer['refused'])}")
    return answer.get("ok")


def invoke(page: Any, command: str, **args: Any) -> Any:
    """The result of one desktop command, or a failure naming its refusal."""
    answer = page.evaluate(INVOKE, {"command": command, "args": args})
    if "refused" in answer:
        raise AcceptanceError(f"{command}: {json.dumps(answer['refused'])}")
    return answer.get("ok")


def status_until(page: Any, command: str, until: str, seconds: float) -> tuple[bool, Any]:
    """Whether ``command``'s status came to satisfy the named condition within ``seconds``, and the last status read."""
    answer = page.evaluate(STATUS_UNTIL, {"command": command, "until": until, "boundMs": seconds * 1000})
    return bool(answer["held"]), answer["status"]


#: Resolves once the profile is signed in, or with the desktop's sign-in
#: attempts that failed after ``afterSequence``, or with nothing once the bound
#: passes. The desktop records each sign-in command it runs in its diagnostics;
#: they are read on every thirtieth rendered frame.


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
        answer = page.evaluate(SIGN_IN_OR_FAILURE, {"boundMs": remaining * 1000, "afterSequence": seen})
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
                INVOKE, {"command": "agent_conversation_delete", "args": {"conversationId": conversation}}
            )
            if "refused" not in answer:
                break
            refused = answer["refused"]
            partial = isinstance(refused, Mapping) and refused.get("code") == "agent_conversation_delete_incomplete"
            if not partial or attempt == _DELETE_ATTEMPTS - 1:
                raise AcceptanceError(f"the run's conversation {conversation} was not deleted: {json.dumps(refused)}")
    left = created & conversation_ids(page)
    require(not left, f"the run's conversations remain after deletion: {sorted(left)}")


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


def devtools_endpoint(port: int, host: Any, deadline: float) -> str:
    """Wait for the window's DevTools endpoint, and require it to listen on loopback only."""
    endpoint = f"http://127.0.0.1:{port}"
    while True:
        with suppress(httpx.HTTPError):
            if httpx.get(f"{endpoint}/json/version", timeout=2).status_code == 200:
                break
        code = desktop_exit_code(host)
        _check_desktop_exit(code)
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


def _check_desktop_exit(code: int | None) -> None:
    """Report the desktop's precise early-exit reason before waiting again."""
    if code == _DESKTOP_UNAVAILABLE:
        raise UnavailableError("this logon has no interactive desktop for the window; run the lane from it")
    if code == 0:
        raise UnavailableError("another Cadrumo desktop took the window; close it, then run the lane again")
    if code is not None:
        raise AcceptanceError(f"the desktop exited with {code} before its DevTools endpoint answered")


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


def tell_person(endpoint: str, entry: str, why: str) -> None:
    """Show the person why the test run ended in the window, and wait for them to close it.

    The lane closes the window when it ends; without this the window would
    just vanish on a failure. The wait is the person's and is bounded, so an
    unattended run still ends.
    """
    print(json.dumps({"step": "telling_person", "reason": why}), flush=True)
    with attached(endpoint, entry) as page:
        page.evaluate(
            ENDED,
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
    host, snapshot = _prepare_host(results, served=served, ledger_privacy=ledger_privacy)
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
                language, before = _prepare_live_page(
                    page, attach_only=attach_only, ledger_privacy=ledger_privacy, unproven=unproven
                )
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
            _cleanup_conversations(endpoint, host.entry, before, failures)
            _notify_failed_run(endpoint, host.entry, failures, absent)
            failures.extend(settle_desktop(desktop, watch))
    _verify_run_results(watch, run_directory, root, started_at, snapshot, failures, absent)
    return unproven


def _prepare_live_page(
    page: Page, *, attach_only: bool, ledger_privacy: bool, unproven: list[str]
) -> tuple[str, set[str]]:
    """Observe sign-in, selected language and the pre-run conversation set."""
    wait_for_sign_in(page)
    language_result = cast(Mapping[str, object], invoke(page, "desktop_language_read") or {})
    language = str(language_result.get("language") or "en")
    if attach_only:
        unproven.append("agent specs: --attach-only ran only the attachment check")
    elif not ledger_privacy:
        require_ready_lane(page)
    return language, conversation_ids(page)


def _prepare_host(results: Path, *, served: bool, ledger_privacy: bool) -> tuple[TestHost, dict[str, object]]:
    """Verify recording policy and the selected host snapshot before launching."""
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
    return host, snapshot


def _notify_failed_run(endpoint: str | None, entry: str, failures: list[str], absent: UnavailableError | None) -> None:
    """Show the failure in the attached window when possible."""
    if endpoint is not None and (failures or absent is not None):
        why = "; ".join(failures) or str(absent)
        with suppress(Exception):
            tell_person(endpoint, entry, why)


def _cleanup_conversations(endpoint: str | None, entry: str, before: set[str] | None, failures: list[str]) -> None:
    """Remove only conversations created by this run, recording any cleanup failure."""
    if endpoint is not None and before is not None:
        try:
            with attached(endpoint, entry) as page:
                created = created_during(before, conversation_ids(page))
                delete_conversations(page, created)
            print(json.dumps({"step": "conversations_deleted", "count": len(created)}), flush=True)
        except Exception as error:  # A conversation left behind is the person's to see.
            failures.append(f"the run's conversations were not cleaned up: {error}")


def _verify_run_results(
    watch: Watch,
    run_directory: Path,
    root: Path,
    started_at: float,
    snapshot: Mapping[str, object],
    failures: list[str],
    absent: UnavailableError | None,
) -> None:
    """Scan retained evidence and report the snapshot's final outcome."""
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
