"""Live-reloading documentation development server.

Wrap ``sphinx-autobuild`` to serve the rendered handbook and rebuild
incrementally whenever the narrative corpus (``docs/``) or the autodoc source
tree (``src/aeat/``) changes. The Sphinx application stays warm between
rebuilds, so edit-to-refresh is a fraction of a cold ``just docs`` build.

The server binds every interface (``0.0.0.0``) on a non-default port so a
container, VM, or peer device on the LAN can reach the preview, and is
**start-idempotent**: a second ``just docs-serve`` does not collide with the
first. It probes the target port and either

* **attaches** — a healthy aeat docs server is already answering there, so this
  invocation just points you at it (and opens the browser) and exits, rather
  than failing with ``EADDRINUSE``;
* **starts** — the port is free (the previous server died: "dead"), so a fresh
  server is launched; or
* **respawns** — a server *we* started is bound but no longer healthy ("dirty"),
  so it is terminated and a fresh one is launched in its place.

A port occupied by a process we did not start is never killed: in auto mode the
next free port is used, and when an explicit ``--port`` is pinned the server
refuses with an instructive message.

Surfaces that the build itself rewrites are excluded from the watch set so a
rebuild cannot trigger itself: ``docs/cli/`` is regenerated from the live
command tree at ``builder-inited`` (see ``docs/conf.py``) and ``docs/_build``
is the output tree. Editing a docstring under ``src/aeat/`` rebuilds the
affected autodoc page; adding or removing a *module* still requires
``python -m dev.docs.apidocs scaffold`` to refresh the committed ``docs/api``
stub set (per the aeat-docs-scaffolding-cli rule), which this server does not
run. This is the interactive companion to :mod:`dev.docs.build`, which performs
the one-shot incremental and gate builds.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

_UTF_8: Final[str] = "utf-8"

# Bind every interface so containers / VMs / LAN peers can reach the preview,
# and default to a non-default port to avoid colliding with the crowded 8000.
_DEFAULT_HOST = "0.0.0.0"  # noqa: S104 - a LAN-reachable dev preview is the intent
_DEFAULT_PORT = 8765
# In auto mode (no explicit --port) scan this many ports upward from the default
# past any occupied-by-a-stranger ports before giving up.
_PORT_SCAN_LIMIT = 20
# Interfaces that cannot be the *target* of an HTTP probe: a wildcard bind is
# reached over a concrete loopback address.
_WILDCARD_PROBE_HOST = {"0.0.0.0": "127.0.0.1", "::": "::1", "": "127.0.0.1"}  # noqa: S104 - probe mapping, not a bind
_PROBE_TIMEOUT_SECONDS = 1.5
_PROBE_READ_BYTES = 8192
# Ceiling for waiting on a terminated stale server to release its port.
_PORT_RELEASE_TIMEOUT_SECONDS = 5.0


class PortStatus(StrEnum):
    """Classification of what, if anything, holds a target port."""

    FREE = "free"
    """Nothing is listening — the port is available to bind."""

    SERVING = "serving"
    """A healthy aeat docs server is answering — attach to it."""

    DIRTY = "dirty"
    """Something is bound but is not a healthy aeat docs server."""


class ServeAction(StrEnum):
    """The action :func:`resolve_target` decided for the resolved port."""

    ATTACH = "attach"
    """Point the operator at the already-running server; do not spawn."""

    START = "start"
    """Bind and launch a fresh server on a free port."""

    RESPAWN = "respawn"
    """Terminate our own dirty server, then launch a fresh one."""

    BLOCKED = "blocked"
    """A foreign process holds the pinned port; refuse with guidance."""


@dataclass(frozen=True)
class ServeState:
    """The recorded identity of a running docs server this tool started."""

    pid: int
    host: str
    port: int


@dataclass(frozen=True)
class Resolution:
    """The resolved port plus the action to take on it."""

    action: ServeAction
    port: int


def _repo_root() -> Path:
    """Return the repository root for this module."""
    return Path(__file__).resolve().parents[2]


def _ignore_patterns() -> list[str]:
    """Return fnmatch globs for changed paths that must not trigger a rebuild.

    ``sphinx-autobuild`` matches each pattern against the native (OS-separator)
    absolute path of a changed file, and ``*`` spans separators, so a single
    ``*<sep>dir<sep>*`` glob excludes a directory subtree recursively. The
    ``docs/cli`` exclusion is load-bearing: that tree is rewritten on every
    build, so watching it would loop the server on its own output. The pattern
    is anchored to ``docs/cli`` specifically so changes under the unrelated
    ``src/aeat/entrypoints/cli`` source still rebuild the CLI reference.

    Returns:
        The ignore globs, in declaration order.
    """
    sep = os.sep
    return [
        f"*{sep}_build{sep}*",
        f"*{sep}docs{sep}cli{sep}*",
        f"*{sep}__pycache__{sep}*",
        "*.pyc",
        f"*{sep}.git{sep}*",
        f"*{sep}tests{sep}*",
        f"*{sep}_data{sep}*",
    ]


def serve_command(repo_root: Path, *, host: str, port: int, open_browser: bool) -> list[str]:
    """Build the ``sphinx-autobuild`` argument vector for the dev server.

    Args:
        repo_root: Repository root containing ``docs/`` and ``src/aeat/``.
        host: Interface the server binds (``0.0.0.0`` serves every interface).
        port: TCP port the server listens on.
        open_browser: Whether to open a browser tab once the first build lands.

    Returns:
        The full command vector, runnable with the current interpreter.
    """
    docs_root = repo_root / "docs"
    out_dir = docs_root / "_build" / "html"
    command = [
        sys.executable,
        "-m",
        "sphinx_autobuild",
        str(docs_root),
        str(out_dir),
        "-b",
        "html",
        "-j",
        "auto",
        # Bind and serve the existing docs/_build/html immediately instead of
        # blocking the port until a full cold autodoc build finishes; the first
        # rebuild fires on the first detected change.
        "--no-initial",
        "--watch",
        str(repo_root / "src" / "aeat"),
        "--host",
        host,
        "--port",
        str(port),
    ]
    if open_browser:
        command.append("--open-browser")
    for pattern in _ignore_patterns():
        command.extend(["--ignore", pattern])
    return command


# ── Running-server awareness ──────────────────────────────────────────────────


def _state_path(repo_root: Path) -> Path:
    """Return the path of the running-server state file (gitignored ``var/``)."""
    return repo_root / "var" / "docs-serve" / "state.json"


def read_state(path: Path) -> ServeState | None:
    """Read the recorded running-server state, tolerating a missing/corrupt file.

    Args:
        path: The state-file path from :func:`_state_path`.

    Returns:
        The parsed :class:`ServeState`, or ``None`` when the file is absent or
        malformed (a stale hand-truncated file must never crash a start).
    """
    try:
        raw = path.read_text(encoding=_UTF_8)
    except OSError:
        return None
    try:
        payload = json.loads(raw)
        return ServeState(pid=int(payload["pid"]), host=str(payload["host"]), port=int(payload["port"]))
    except (ValueError, KeyError, TypeError):
        return None


def write_state(path: Path, state: ServeState) -> None:
    """Persist the running-server identity so a later start can find it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"pid": state.pid, "host": state.host, "port": state.port}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding=_UTF_8)


def clear_state(path: Path, *, only_pid: int | None = None) -> None:
    """Remove the state file, optionally only when it still names ``only_pid``.

    Args:
        path: The state-file path.
        only_pid: When given, delete only if the recorded pid matches, so a
            server started by a *later* invocation is not orphaned by this one's
            teardown.
    """
    if only_pid is not None:
        current = read_state(path)
        if current is not None and current.pid != only_pid:
            return
    path.unlink(missing_ok=True)


def _pid_alive(pid: int) -> bool:
    """Return whether ``pid`` names a live, non-zombie process.

    Uses ``psutil`` for a cross-platform check; on Windows ``os.kill(pid, 0)``
    would *terminate* the process, so it must never be used for liveness.
    """
    try:
        import psutil
    except ImportError:  # pragma: no cover - psutil is a dev-group dependency
        return False
    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except psutil.Error:
        return False


def _terminate(pid: int, *, timeout: float = _PORT_RELEASE_TIMEOUT_SECONDS) -> None:
    """Terminate a process we started, escalating to kill, best-effort."""
    try:
        import psutil
    except ImportError:  # pragma: no cover - psutil is a dev-group dependency
        return
    try:
        proc = psutil.Process(pid)
    except psutil.Error:
        return
    try:
        proc.terminate()
        proc.wait(timeout=timeout)
    except psutil.TimeoutExpired:
        with contextlib.suppress(psutil.Error):
            proc.kill()
    except psutil.Error:
        pass


def _probe_host(host: str) -> str:
    """Map a wildcard bind interface to a concrete address for probing."""
    return _WILDCARD_PROBE_HOST.get(host, host)


def _looks_like_sphinx(body: str) -> bool:
    """Return whether an HTTP body looks like a Sphinx-generated docs page."""
    lowered = body.lower()
    return "sphinx" in lowered or "docutils" in lowered


def classify_probe(*, http_ok: bool, is_sphinx: bool) -> PortStatus:
    """Classify a port that accepted a connection and returned an HTTP response.

    Pure decision function (no I/O) so the SERVING-vs-DIRTY boundary is unit
    testable. A connection that never reached this point (refused) is
    :attr:`PortStatus.FREE`, decided in :func:`probe_port`.

    Args:
        http_ok: Whether the response carried a 2xx status.
        is_sphinx: Whether the body looked like our Sphinx docs.

    Returns:
        :attr:`PortStatus.SERVING` only when both hold, else
        :attr:`PortStatus.DIRTY`.
    """
    if http_ok and is_sphinx:
        return PortStatus.SERVING
    return PortStatus.DIRTY


def _port_bindable(bind_host: str, port: int) -> bool:
    """Return whether ``bind_host:port`` can be bound (nothing is listening).

    Binding is a more reliable availability probe than connecting: on Windows a
    closed loopback port surfaces a *connect timeout* rather than a refusal, so
    a connect-based check cannot tell "free" from "occupied but slow".

    The probe MUST bind the *same* host the server will bind — the wildcard
    ``0.0.0.0`` when that is the target — not a loopback substitute. ``uvicorn``
    (under ``sphinx-autobuild``) binds the wildcard with ``SO_REUSEADDR``, and
    on Windows a specific ``127.0.0.1`` bind can then coexist with it, so a
    loopback probe would falsely read FREE. A plain wildcard bind here (no
    ``SO_REUSEADDR`` — which on Windows would let us steal an in-use port) fails
    with ``EADDRINUSE`` against the running server, correctly reading occupied.
    """
    family = socket.AF_INET6 if ":" in bind_host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((bind_host, port))
            return True
        except OSError:
            return False


def probe_port(bind_host: str, port: int, *, timeout: float = _PROBE_TIMEOUT_SECONDS) -> PortStatus:
    """Probe the port the server would bind as ``bind_host`` and classify it.

    A bindable port is :attr:`PortStatus.FREE`; a 2xx Sphinx page (fetched over
    the concrete loopback address for a wildcard bind) is
    :attr:`PortStatus.SERVING`; anything else bound (non-2xx, non-Sphinx body,
    or a bound-but-unresponsive socket) is :attr:`PortStatus.DIRTY`.
    """
    if _port_bindable(bind_host, port):
        return PortStatus.FREE
    http_host = _probe_host(bind_host)
    url = f"http://{http_host}:{port}/"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - fixed localhost scheme
            status = getattr(response, "status", None) or response.getcode()
            body = response.read(_PROBE_READ_BYTES).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        # A real HTTP error status means something is serving — just not our
        # docs (or an autobuild page mid-build); read the body to be sure.
        body = ""
        with contextlib.suppress(OSError):
            body = exc.read(_PROBE_READ_BYTES).decode("utf-8", "replace")
        return classify_probe(http_ok=False, is_sphinx=_looks_like_sphinx(body))
    except (urllib.error.URLError, TimeoutError, OSError):
        # Bound (bind failed above) but not usable as HTTP — dirty.
        return PortStatus.DIRTY
    return classify_probe(http_ok=200 <= status < 300, is_sphinx=_looks_like_sphinx(body))


def _owned_stale(state_path: Path, port: int) -> bool:
    """Return whether a *dirty* ``port`` is held by a live server we started.

    Only when the recorded state names this exact port and its pid is still
    alive do we own the process and may terminate it to respawn. A dead pid or a
    mismatched port means a stranger holds the port — never ours to kill.
    """
    state = read_state(state_path)
    return state is not None and state.port == port and _pid_alive(state.pid)


def resolve_target(
    *,
    requested_port: int | None,
    default_port: int,
    scan_limit: int,
    probe: Callable[[int], PortStatus],
    owned_stale: Callable[[int], bool],
) -> Resolution:
    """Decide which port to use and what to do with it.

    Pure orchestration over injected ``probe`` and ``owned_stale`` callables so
    the attach / start / respawn / blocked decision is unit testable without
    sockets or processes.

    Args:
        requested_port: An explicitly pinned port, or ``None`` for auto mode.
        default_port: The first candidate in auto mode.
        scan_limit: How many consecutive ports auto mode may try.
        probe: Maps a port to its :class:`PortStatus`.
        owned_stale: Whether a dirty port is a live server we started.

    Returns:
        The resolved :class:`Resolution`.
    """
    explicit = requested_port is not None
    candidates = [requested_port] if explicit else list(range(default_port, default_port + scan_limit))
    for port in candidates:
        assert port is not None
        status = probe(port)
        if status is PortStatus.SERVING:
            return Resolution(ServeAction.ATTACH, port)
        if status is PortStatus.FREE:
            return Resolution(ServeAction.START, port)
        # DIRTY from here on.
        if owned_stale(port):
            return Resolution(ServeAction.RESPAWN, port)
        if explicit:
            return Resolution(ServeAction.BLOCKED, port)
        # Auto mode: a stranger holds this port; try the next one.
    return Resolution(ServeAction.BLOCKED, candidates[0] if candidates else default_port)


def _wait_for_free(bind_host: str, port: int, *, timeout: float) -> bool:
    """Poll until ``port`` is released after a terminate, or the timeout lapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if probe_port(bind_host, port) is PortStatus.FREE:
            return True
        time.sleep(0.1)
    return probe_port(bind_host, port) is PortStatus.FREE


def _build_env(repo_root: Path) -> dict[str, str]:
    """Return the child environment forcing the full-site build path.

    sphinx-autobuild drives Sphinx through the ``build`` subcommand form
    (``python -m sphinx build ...``), whose extra leading token defeats the
    argv heuristic in ``docs/conf.py`` that distinguishes a full build from a
    targeted partial one. That heuristic otherwise skips the deferred
    pydantic-model rebuild and the CLI-reference generation, leaving autodoc to
    crash on a not-fully-defined model. The dev server always serves the whole
    site, so force both build-time steps on via the conf.py overrides.
    """
    return {
        **os.environ,
        "AEAT_DOCS_PROJECT_ROOT": str(repo_root),
        "AEAT_DOCS_FORCE_DEFERRED_MODELS": "1",
        "AEAT_DOCS_FORCE_CLI_REFERENCE": "1",
    }


def _launch(
    repo_root: Path,
    *,
    host: str,
    port: int,
    open_browser: bool,
) -> int:
    """Launch the server in the foreground, recording and clearing its state."""
    command = serve_command(repo_root, host=host, port=port, open_browser=open_browser)
    probe_host = _probe_host(host)
    state_path = _state_path(repo_root)
    print(f"Serving documentation on http://{probe_host}:{port}/ (Ctrl-C to stop).", flush=True)
    if host in _WILDCARD_PROBE_HOST:
        print(f"Bound to {host}:{port} — reachable from other hosts on the network.", flush=True)
    print("Watching docs/ and src/aeat/; rebuilding on change.", flush=True)
    process = subprocess.Popen(command, cwd=repo_root, env=_build_env(repo_root))
    write_state(state_path, ServeState(pid=process.pid, host=host, port=port))
    try:
        return process.wait()
    except KeyboardInterrupt:
        _terminate(process.pid)
        return 0
    finally:
        clear_state(state_path, only_pid=process.pid)


def _do_stop(state_path: Path) -> int:
    """Terminate the recorded running server, if any."""
    state = read_state(state_path)
    if state is None:
        print("No docs server is recorded as running.", flush=True)
        return 0
    if not _pid_alive(state.pid):
        print(f"Recorded docs server (pid {state.pid}) is not running; clearing stale state.", flush=True)
        clear_state(state_path)
        return 0
    print(f"Stopping docs server (pid {state.pid}) on {state.host}:{state.port}.", flush=True)
    _terminate(state.pid)
    clear_state(state_path, only_pid=state.pid)
    return 0


def _do_status(state_path: Path) -> int:
    """Print whether the recorded server is alive and healthy."""
    state = read_state(state_path)
    if state is None:
        print("No docs server is recorded as running.", flush=True)
        return 1
    alive = _pid_alive(state.pid)
    status = probe_port(state.host, state.port)
    print(
        f"Recorded docs server: pid {state.pid}, {state.host}:{state.port} "
        f"(process {'alive' if alive else 'dead'}, port {status.value}).",
        flush=True,
    )
    return 0 if (alive and status is PortStatus.SERVING) else 1


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the start-idempotent live-reloading docs server."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=_DEFAULT_HOST, help="Interface to bind (default: 0.0.0.0, every interface).")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=(
            f"Port to serve on. Omit to auto-pick from {_DEFAULT_PORT}; "
            "a pinned port a foreign process holds is refused."
        ),
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open a browser tab after the first build (or on attach).",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--stop", action="store_true", help="Terminate the recorded running docs server and exit.")
    group.add_argument("--status", action="store_true", help="Report the recorded running docs server and exit.")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    state_path = _state_path(repo_root)

    if args.stop:
        return _do_stop(state_path)
    if args.status:
        return _do_status(state_path)

    resolution = resolve_target(
        requested_port=args.port,
        default_port=_DEFAULT_PORT,
        scan_limit=_PORT_SCAN_LIMIT,
        probe=lambda port: probe_port(args.host, port),
        owned_stale=lambda port: _owned_stale(state_path, port),
    )
    port = resolution.port
    url = f"http://{_probe_host(args.host)}:{port}/"

    if resolution.action is ServeAction.ATTACH:
        print(f"A docs server is already serving at {url}; attaching instead of starting a second one.", flush=True)
        if args.open_browser:
            webbrowser.open(url)
        return 0

    if resolution.action is ServeAction.BLOCKED:
        print(
            f"Port {port} is held by another process that is not an aeat docs server; "
            "choose a different --port (or omit --port to auto-pick a free one).",
            file=sys.stderr,
            flush=True,
        )
        return 1

    if resolution.action is ServeAction.RESPAWN:
        stale = read_state(state_path)
        if stale is not None:
            print(
                f"Existing docs server on port {port} is unresponsive; respawning (terminating pid {stale.pid}).",
                flush=True,
            )
            _terminate(stale.pid)
            clear_state(state_path, only_pid=stale.pid)
        if not _wait_for_free(args.host, port, timeout=_PORT_RELEASE_TIMEOUT_SECONDS):
            print(
                f"Port {port} did not free after terminating the stale server; choose a different --port.",
                file=sys.stderr,
                flush=True,
            )
            return 1

    return _launch(repo_root, host=args.host, port=port, open_browser=args.open_browser)


if __name__ == "__main__":
    raise SystemExit(main())
