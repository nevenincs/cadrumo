"""Live-reloading documentation development server.

Wrap ``sphinx-autobuild`` to serve the rendered handbook and rebuild
incrementally whenever the narrative corpus (``docs/``) or the autodoc source
tree (``src/cadrumo/``) changes. The Sphinx application stays warm between
rebuilds, so edit-to-refresh is a fraction of a cold ``just docs`` build.

The server binds every interface (``0.0.0.0``) on the docs' OWNED canonical
port so a container, VM, or peer device on the LAN can reach the preview at a
stable, known address, and is **start-idempotent**: a second
``just docs-serve`` does not collide with the first. The port is strict — the
server never silently drifts to a neighbouring port. It probes the target
port and either

* **attaches** — a healthy aeat docs server is already answering there, so this
  invocation just points you at it (and opens the browser) and exits, rather
  than failing with ``EADDRINUSE``;
* **starts** — the port is free, so a fresh server is launched;
* **respawns** — a server *we* started is bound but no longer healthy ("dirty"),
  so it is terminated and a fresh one is launched in its place; or
* **evicts** — a foreign process squats the docs' canonical port, so it is
  terminated and the port reclaimed. The canonical port belongs to the docs
  server by declaration; anything else answering there is an invalid occupant.

Not being able to serve on the resolved port is an ERROR (exit 1), never a
silent fallback. An explicitly pinned ``--port`` that a foreign process holds
is refused with guidance (eviction applies only to the canonical port we own).

The first serve performs an initial build so the review is never a stale
snapshot; subsequent edits rebuild incrementally.

Surfaces that the build itself rewrites are excluded from the watch set so a
rebuild cannot trigger itself: ``docs/cli/`` is regenerated from the live
command tree at ``builder-inited`` (see ``docs/conf.py``) and ``docs/_build``
is the output tree. Editing a docstring under ``src/cadrumo/`` rebuilds the
affected autodoc page; adding or removing a *module* still requires
``python -m dev.docs.apidocs scaffold`` to refresh the committed ``docs/api``
stub set (per the aeat-documentation rule), which this server does not
run. This is the interactive companion to :mod:`dev.docs.build`, which performs
the one-shot incremental and gate builds.
"""

from __future__ import annotations

import argparse
import contextlib
import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8

_UTF_8: Final[str] = UTF_8

# Bind every interface so containers / VMs / LAN peers can reach the preview.
_DEFAULT_HOST = "0.0.0.0"  # noqa: S104 - a LAN-reachable dev preview is the intent
# The docs server's OWNED canonical port. 8765/8766 belong to the resident
# vaultspec-rag stack (qdrant HTTP + the RAG service) and 8767/8770 to its
# dashboards on developer machines, so the docs claim a port clear of that
# cluster and clear of the crowded 8000. The port is strict: the server never
# scans away from it, and a foreign squatter on it is evicted.
_DEFAULT_PORT = 8788
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

    EVICT = "evict"
    """A foreign process squats the canonical port we own; terminate it and claim the port."""

    BLOCKED = "blocked"
    """A foreign process holds an explicitly pinned non-canonical port; refuse with guidance."""


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
    return REPO_ROOT


def _ignore_patterns() -> list[str]:
    """Return fnmatch globs for changed paths that must not trigger a rebuild.

    ``sphinx-autobuild`` matches each pattern against the native (OS-separator)
    absolute path of a changed file, and ``*`` spans separators, so a single
    ``*<sep>dir<sep>*`` glob excludes a directory subtree recursively. The
    ``docs/cli`` exclusion is load-bearing: that tree is rewritten on every
    build, so watching it would loop the server on its own output. The pattern
    is anchored to ``docs/cli`` specifically so changes under the unrelated
    ``src/cadrumo/entrypoints/cli`` source still rebuild the CLI reference.

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


def serve_command(repo_root: Path, *, host: str, port: int, open_browser: bool, scope: str = "user") -> list[str]:
    """Build the ``sphinx-autobuild`` argument vector for the dev server.

    Args:
        repo_root: Repository root containing ``docs/`` and ``src/cadrumo/``.
        host: Interface the server binds (``0.0.0.0`` serves every interface).
        port: TCP port the server listens on.
        open_browser: Whether to open a browser tab once the first build lands.
        scope: Documentation surface (``user`` | ``full``). The preview loop's
            audience is user-docs authors, so ``user`` is the default: the API
            autodoc tree is excluded and the app is never imported for rendering,
            so the first build is minutes not an hour. Under ``user`` scope the
            ``src/cadrumo`` autodoc source is NOT watched — there is no autodoc to
            rebuild, and a user-docs author edits ``docs/``, not the app. ``full``
            restores the API tree and the source watch.

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
        # No --no-initial: the first serve builds the current tree before the
        # browser opens, so a review can never start on a stale snapshot of
        # docs/_build/html left by an earlier session.
    ]
    if scope != "user":
        # Full scope watches the autodoc source so a docstring edit rebuilds its
        # API page; user scope loads no autodoc, so watching src/cadrumo would
        # only trigger rebuilds that render nothing new.
        command.extend(["--watch", str(repo_root / "src" / "cadrumo")])
    command.extend(["--host", host, "--port", str(port)])
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
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding=_UTF_8, newline="\n")


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


def _validated_probe_target(host: str, port: int) -> tuple[str, int, str]:
    url_host = f"[{host}]" if ":" in host else host
    parsed = urllib.parse.urlsplit(f"http://{url_host}:{port}/")
    if (
        parsed.scheme != "http"
        or parsed.hostname != host
        or parsed.port != port
        or parsed.path != "/"
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("docs probe target is not a plain HTTP host and port")
    return parsed.hostname, parsed.port, parsed.path


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
    try:
        validated_host, validated_port, target = _validated_probe_target(http_host, port)
        connection = http.client.HTTPConnection(validated_host, validated_port, timeout=timeout)
        try:
            connection.request("GET", target)
            response = connection.getresponse()
            status = response.status
            body = response.read(_PROBE_READ_BYTES).decode("utf-8", "replace")
        finally:
            connection.close()
    except (http.client.HTTPException, TimeoutError, OSError, ValueError):
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
    probe: Callable[[int], PortStatus],
    owned_stale: Callable[[int], bool],
) -> Resolution:
    """Decide what to do with the single strict target port.

    Pure orchestration over injected ``probe`` and ``owned_stale`` callables so
    the attach / start / respawn / evict / blocked decision is unit testable
    without sockets or processes. There is exactly one candidate port — the
    explicit pin or the canonical default — and the server never scans away
    from it.

    Args:
        requested_port: An explicitly pinned port, or ``None`` for the
            canonical default.
        default_port: The docs server's owned canonical port.
        probe: Maps a port to its :class:`PortStatus`.
        owned_stale: Whether a dirty port is a live server we started.

    Returns:
        The resolved :class:`Resolution`. A dirty canonical port held by a
        stranger resolves to :attr:`ServeAction.EVICT` (the port is ours to
        claim); a dirty *pinned* non-canonical port resolves to
        :attr:`ServeAction.BLOCKED` (we do not kill strangers on ports we do
        not own).
    """
    port = requested_port if requested_port is not None else default_port
    status = probe(port)
    if status is PortStatus.SERVING:
        return Resolution(ServeAction.ATTACH, port)
    if status is PortStatus.FREE:
        return Resolution(ServeAction.START, port)
    # DIRTY from here on.
    if owned_stale(port):
        return Resolution(ServeAction.RESPAWN, port)
    if port == default_port:
        return Resolution(ServeAction.EVICT, port)
    return Resolution(ServeAction.BLOCKED, port)


def _listeners_on(port: int) -> list[tuple[int, str]]:
    """Return ``(pid, name)`` for every process with a LISTEN socket on ``port``.

    Used only to evict a squatter from the docs' canonical port. Returns an
    empty list when psutil is unavailable or the listener cannot be identified
    (the caller then reports the port unclaimable instead of guessing).
    """
    try:
        import psutil
    except ImportError:  # pragma: no cover - psutil is a dev-group dependency
        return []
    found: dict[int, str] = {}
    with contextlib.suppress(psutil.Error, OSError):
        for conn in psutil.net_connections(kind="tcp"):
            if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port and conn.pid:
                name = ""
                with contextlib.suppress(psutil.Error):
                    name = psutil.Process(conn.pid).name()
                found[conn.pid] = name
    return sorted(found.items())


def _evict_port(bind_host: str, port: int, *, timeout: float = _PORT_RELEASE_TIMEOUT_SECONDS) -> bool:
    """Terminate whatever squats the docs' canonical ``port`` and wait for release.

    The canonical port is the docs server's by declaration; an occupant that is
    not a healthy aeat docs server is an invalid squatter and is evicted. Each
    evicted process is named on stdout so the operator sees exactly what was
    terminated.

    Returns:
        Whether the port was released within the timeout.
    """
    listeners = _listeners_on(port)
    if not listeners:
        print(f"Port {port} is bound but its holder could not be identified for eviction.", flush=True)
        return False
    for pid, name in listeners:
        label = f"{name} (pid {pid})" if name else f"pid {pid}"
        print(f"Evicting {label} from the docs' canonical port {port}.", flush=True)
        _terminate(pid, timeout=timeout)
    return _wait_for_free(bind_host, port, timeout=timeout)


def _wait_for_free(bind_host: str, port: int, *, timeout: float) -> bool:
    """Poll until ``port`` is released after a terminate, or the timeout lapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if probe_port(bind_host, port) is PortStatus.FREE:
            return True
        time.sleep(0.1)
    return probe_port(bind_host, port) is PortStatus.FREE


def _build_env(repo_root: Path, *, scope: str = "user") -> dict[str, str]:
    """Return the child environment forcing the full-site build path.

    sphinx-autobuild drives Sphinx through the ``build`` subcommand form
    (``python -m sphinx build ...``), whose extra leading token defeats the
    argv heuristic in ``docs/conf.py`` that distinguishes a full build from a
    targeted partial one. That heuristic otherwise skips the deferred
    pydantic-model rebuild and the CLI-reference generation, leaving autodoc to
    crash on a not-fully-defined model. The dev server always serves the whole
    site, so force both build-time steps on via the conf.py overrides.

    Ambient Cadrumo product and AEAT authority settings are stripped and the
    local-storage root is pinned to an isolated temp directory, mirroring the
    CLI-reference generator's subprocess environment: a developer workstation
    whose real storage root holds retired ``aeat``-named state otherwise trips
    the former-product refusal inside ``conf.py``'s settings construction and
    kills every rebuild.
    """
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith(("CADRUMO_", "AEAT_"))}
    environment.update(
        {
            "CADRUMO_DOCS_PROJECT_ROOT": str(repo_root),
            "CADRUMO_DOCS_FORCE_DEFERRED_MODELS": "1",
            "CADRUMO_DOCS_FORCE_CLI_REFERENCE": "1",
            "CADRUMO_OUTPUT_LANGUAGE": "en",
            "CADRUMO_DOCS_SCOPE": scope,
            "CADRUMO_LOCAL_STORAGE_ROOT": tempfile.mkdtemp(prefix="cadrumo-docs-serve-"),
        }
    )
    return environment


def _pipe(source: socket.socket, sink: socket.socket) -> None:
    """Copy bytes one way until EOF, then half-close the sink."""
    with contextlib.suppress(OSError):
        while chunk := source.recv(65536):
            sink.sendall(chunk)
    with contextlib.suppress(OSError):
        sink.shutdown(socket.SHUT_WR)


def _relay_connection(client: socket.socket, target_port: int) -> None:
    """Bridge one accepted IPv6 connection to the IPv4 server on ``target_port``."""
    try:
        upstream = socket.create_connection(("127.0.0.1", target_port), timeout=_PROBE_TIMEOUT_SECONDS)
    except OSError:
        with contextlib.suppress(OSError):
            client.close()
        return
    threading.Thread(target=_pipe, args=(client, upstream), daemon=True).start()
    threading.Thread(target=_pipe, args=(upstream, client), daemon=True).start()


def start_ipv6_relay(port: int) -> socket.socket | None:
    """Serve ``[::]:port`` by relaying byte streams to the IPv4 listener on ``port``.

    ``sphinx-autobuild``'s server binds IPv4 only, but Windows resolves the
    machine's own hostname to a link-local IPv6 address first, so a browser
    pointed at ``http://<hostname>:<port>/`` gets connection-refused while
    ``127.0.0.1`` works. An IPv6-only listener (``IPV6_V6ONLY`` on, so it
    coexists with the IPv4 bind on the same port) piping to loopback makes the
    single canonical port genuinely dual-stack. Returns the listening socket,
    or ``None`` when IPv6 is unavailable — the server then stays IPv4-only.
    """
    try:
        listener = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        listener.bind(("::", port))
        listener.listen(16)
    except OSError:
        return None

    def _accept_loop() -> None:
        while True:
            try:
                client, _addr = listener.accept()
            except OSError:
                return
            _relay_connection(client, port)

    threading.Thread(target=_accept_loop, daemon=True, name=f"docs-ipv6-relay-{port}").start()
    return listener


def _launch(
    repo_root: Path,
    *,
    host: str,
    port: int,
    open_browser: bool,
    scope: str = "user",
) -> int:
    """Launch the server in the foreground, recording and clearing its state."""
    command = serve_command(repo_root, host=host, port=port, open_browser=open_browser, scope=scope)
    probe_host = _probe_host(host)
    state_path = _state_path(repo_root)
    print(f"Serving {scope}-scope documentation on http://{probe_host}:{port}/ (Ctrl-C to stop).", flush=True)
    relay = start_ipv6_relay(port) if host in _WILDCARD_PROBE_HOST else None
    if host in _WILDCARD_PROBE_HOST:
        stacks = "IPv4+IPv6" if relay is not None else "IPv4"
        print(f"Bound to {host}:{port} ({stacks}) — reachable from other hosts on the network.", flush=True)
        print(f"Also reachable as http://{socket.gethostname().lower()}:{port}/ on the LAN.", flush=True)
    print("Watching docs/ and src/cadrumo/; rebuilding on change.", flush=True)
    process = subprocess.Popen(command, cwd=repo_root, env=_build_env(repo_root))
    write_state(state_path, ServeState(pid=process.pid, host=host, port=port))
    try:
        return process.wait()
    except KeyboardInterrupt:
        _terminate(process.pid)
        return 0
    finally:
        if relay is not None:
            with contextlib.suppress(OSError):
                relay.close()
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
            f"Port to serve on (default: the docs' canonical {_DEFAULT_PORT}, which is claimed strictly — "
            "an invalid occupant is evicted). A pinned non-canonical port a foreign process holds is refused."
        ),
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open a browser tab after the first build (or on attach).",
    )
    parser.add_argument(
        "--scope",
        choices=("user", "full"),
        default="user",
        help=(
            "Documentation surface to serve. 'user' (default) previews only the operator-facing docs, "
            "excluding the API autodoc tree so the first build is minutes instead of an hour; 'full' serves "
            "the whole handbook including the API reference and watches src/cadrumo for docstring edits."
        ),
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
            f"choose a different --port (or omit --port to claim the canonical {_DEFAULT_PORT}).",
            file=sys.stderr,
            flush=True,
        )
        return 1

    if resolution.action is ServeAction.EVICT and not _evict_port(args.host, port):
        print(
            f"ERROR: the docs' canonical port {port} could not be claimed — the squatter did not release it. "
            "Nothing else may hold this port; investigate the process bound to it.",
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

    return _launch(repo_root, host=args.host, port=port, open_browser=args.open_browser, scope=args.scope)


if __name__ == "__main__":
    raise SystemExit(main())
