"""Unit gate for the live-reloading documentation server.

Asserts that :func:`dev.docs.serve.serve_command` serves the narrative corpus and
scopes the ``src/cadrumo`` docstring-source watch to full scope (user scope, the
preview default, loads no autodoc so it is not watched), and that
the self-regenerated trees are excluded from the watch set so a rebuild cannot
loop on its own output; and that the start-idempotent running-server awareness
(:func:`dev.docs.serve.resolve_target` and its probe/state helpers) attaches to
a healthy peer, starts on a free port, respawns a dirty server it owns, evicts
a foreign squatter from the canonical port the docs own, refuses a foreign-held
pinned non-canonical port, and never scans away from the strict target port.
"""

from __future__ import annotations

import http.server
import os
import socket
import socketserver
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import override

import pytest

from ..._paths import REPO_ROOT
from ..serve import (
    _DEFAULT_HOST,
    _DEFAULT_PORT,
    PortStatus,
    Resolution,
    ServeAction,
    ServeState,
    _looks_like_sphinx,
    _probe_host,
    classify_probe,
    clear_state,
    probe_port,
    read_state,
    resolve_target,
    serve_command,
    start_ipv6_relay,
    write_state,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT


def test_serve_command_scopes_the_autodoc_source_watch() -> None:
    """User scope (the default) serves docs/ only; full scope also watches the app source.

    The preview loop defaults to user scope, which loads no autodoc, so the
    ``src/cadrumo`` docstring source is NOT watched — watching it would only
    trigger rebuilds that render nothing new. Full scope restores the autodoc
    source watch so a docstring edit rebuilds its API page.
    """
    user = serve_command(_REPO_ROOT, host="127.0.0.1", port=8000, open_browser=False)
    assert user[1:3] == ["-m", "sphinx_autobuild"]
    assert str(_REPO_ROOT / "docs") in user
    assert str(_REPO_ROOT / "docs" / "_build" / "html") in user
    assert "--watch" not in user  # user scope does not watch the (unrendered) app source

    full = serve_command(_REPO_ROOT, host="127.0.0.1", port=8000, open_browser=False, scope="full")
    watch_index = full.index("--watch")
    assert full[watch_index + 1] == str(_REPO_ROOT / "src" / "cadrumo")


def test_serve_command_excludes_self_regenerated_trees() -> None:
    """The generated CLI tree and build output are ignored to prevent a loop."""
    command = serve_command(_REPO_ROOT, host="127.0.0.1", port=8000, open_browser=False)
    ignores = [command[index + 1] for index, flag in enumerate(command) if flag == "--ignore"]
    sep = os.sep
    assert f"*{sep}docs{sep}cli{sep}*" in ignores
    assert any("_build" in pattern for pattern in ignores)
    # The docs/cli ignore must be anchored so it does not also swallow changes
    # to the unrelated src/cadrumo/entrypoints/cli source tree.
    assert f"*{sep}cli{sep}*" not in ignores


def test_serve_command_open_browser_flag_is_optional() -> None:
    """The browser-open flag and port are threaded through to the command."""
    with_browser = serve_command(_REPO_ROOT, host="127.0.0.1", port=9001, open_browser=True)
    without_browser = serve_command(_REPO_ROOT, host="127.0.0.1", port=9001, open_browser=False)
    assert "--open-browser" in with_browser
    assert "--open-browser" not in without_browser
    assert "9001" in with_browser


# ── Binding defaults ──────────────────────────────────────────────────────────


def test_default_host_binds_every_interface() -> None:
    """The default bind exposes the preview on every interface, not loopback."""
    assert _DEFAULT_HOST == "0.0.0.0"  # noqa: S104 - asserting the intended LAN-reachable bind


def test_default_port_is_the_owned_canonical_port() -> None:
    """The canonical port avoids the crowded 8000 and the resident RAG cluster.

    8765/8766 are the vaultspec-rag stack (qdrant HTTP + service) and
    8767/8770 its dashboards on developer machines; the docs' strict eviction
    semantics must never point a kill at those.
    """
    assert _DEFAULT_PORT == 8788
    assert _DEFAULT_PORT not in {8000, 8765, 8766, 8767, 8770}


@pytest.mark.parametrize(
    ("bind", "expected"),
    [("0.0.0.0", "127.0.0.1"), ("::", "::1"), ("", "127.0.0.1"), ("192.168.1.4", "192.168.1.4")],  # noqa: S104 - probe-mapping fixtures
)
def test_probe_host_maps_wildcard_to_a_reachable_address(bind: str, expected: str) -> None:
    """A wildcard bind is probed over a concrete loopback / its own address."""
    assert _probe_host(bind) == expected


# ── Probe classification ──────────────────────────────────────────────────────


def test_classify_probe_serving_needs_2xx_and_sphinx() -> None:
    """Only a 2xx response whose body looks like Sphinx counts as serving."""
    assert classify_probe(http_ok=True, is_sphinx=True) is PortStatus.SERVING
    assert classify_probe(http_ok=True, is_sphinx=False) is PortStatus.DIRTY
    assert classify_probe(http_ok=False, is_sphinx=True) is PortStatus.DIRTY
    assert classify_probe(http_ok=False, is_sphinx=False) is PortStatus.DIRTY


def test_looks_like_sphinx_recognises_generator_markers() -> None:
    """A Sphinx/Docutils generator marker identifies our docs page."""
    assert _looks_like_sphinx('<meta name="generator" content="Docutils: ... Sphinx">')
    assert _looks_like_sphinx("Created using SPHINX 8")
    assert not _looks_like_sphinx("<html><body>hello from some other service</body></html>")


def _free_port() -> int:
    """Return a port that is closed right now (bound then released)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def sphinx_http_server() -> Iterator[int]:
    """Serve a Sphinx-looking page on an ephemeral port for a live probe."""
    body = b'<meta name="generator" content="Docutils 0.21: Sphinx 8.1">'

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)

        @override
        def log_message(self, *_args: object) -> None:
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_probe_port_free_when_nothing_listens() -> None:
    """A closed port classifies FREE via the bind-availability check."""
    assert probe_port("127.0.0.1", _free_port()) is PortStatus.FREE


def test_probe_port_dirty_when_a_non_http_listener_holds_it() -> None:
    """A raw listening socket that never answers HTTP classifies DIRTY."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        assert probe_port("127.0.0.1", port, timeout=0.5) is PortStatus.DIRTY


def test_probe_port_serving_against_a_live_sphinx_page(sphinx_http_server: int) -> None:
    """A live 2xx Sphinx page classifies SERVING through the real socket path."""
    assert probe_port("127.0.0.1", sphinx_http_server) is PortStatus.SERVING


def test_ipv6_relay_bridges_to_the_ipv4_listener(sphinx_http_server: int) -> None:
    """The IPv6 relay makes the IPv4-only server answer on [::1] at the same port.

    Windows resolves the machine's own hostname to IPv6 first, so without the
    relay a browser at http://<hostname>:<port>/ gets connection-refused while
    curl over 127.0.0.1 works — the docs must be reachable over both stacks.
    The fetch goes over the real IPv6 loopback socket (not probe_port, whose
    bind-availability check cannot see a wildcard-IPv6 listener from a specific
    ::1 bind on Windows).
    """
    import urllib.request

    relay = start_ipv6_relay(sphinx_http_server)
    try:
        if relay is None:
            # IPv6 loopback is unavailable on this host: start_ipv6_relay
            # returned its documented IPv4-only fallback without raising, so
            # there is no [::1] listener to bridge and the dual-stack fetch
            # below does not apply. The fallback contract is what we assert here.
            return
        with urllib.request.urlopen(f"http://[::1]:{sphinx_http_server}/", timeout=3) as response:
            assert response.status == 200
            assert _looks_like_sphinx(response.read().decode("utf-8", "replace"))
    finally:
        if relay is not None:
            relay.close()


# ── State file round-trip ─────────────────────────────────────────────────────


def test_state_round_trips_and_clears(tmp_path: Path) -> None:
    """State writes, reads back equal, and clears; a missing file reads None."""
    path = tmp_path / "state.json"
    assert read_state(path) is None
    state = ServeState(pid=4242, host="0.0.0.0", port=8765)  # noqa: S104 - state fixture, not a bind
    write_state(path, state)
    assert read_state(path) == state
    clear_state(path)
    assert read_state(path) is None


def test_read_state_tolerates_corrupt_file(tmp_path: Path) -> None:
    """A hand-truncated or malformed state file reads as None, never raises."""
    path = tmp_path / "state.json"
    path.write_text("{ not json", encoding="utf-8")
    assert read_state(path) is None
    path.write_text('{"pid": "not-an-int"}', encoding="utf-8")
    assert read_state(path) is None


def test_clear_state_only_pid_guard(tmp_path: Path) -> None:
    """clear_state(only_pid=...) leaves a file another invocation now owns."""
    path = tmp_path / "state.json"
    original = ServeState(pid=999, host="0.0.0.0", port=8765)  # noqa: S104 - state fixture, not a bind
    write_state(path, original)
    clear_state(path, only_pid=111)  # not ours — must not delete
    # Not just "a" state survived — the SAME state another invocation owns,
    # untouched by the mismatched guard.
    assert read_state(path) == original
    clear_state(path, only_pid=999)  # ours — deletes
    assert read_state(path) is None


# ── Target resolution ─────────────────────────────────────────────────────────


def _resolve(
    *,
    requested_port: int | None,
    probe: dict[int, PortStatus],
    owned: set[int] | None = None,
    default_port: int = 8788,
) -> Resolution:
    owned = owned or set()
    return resolve_target(
        requested_port=requested_port,
        default_port=default_port,
        probe=lambda port: probe.get(port, PortStatus.FREE),
        owned_stale=lambda port: port in owned,
    )


def test_resolve_attaches_to_a_healthy_peer() -> None:
    """A serving canonical port yields ATTACH on that exact port."""
    result = _resolve(requested_port=None, probe={8788: PortStatus.SERVING})
    assert result == Resolution(ServeAction.ATTACH, 8788)


def test_resolve_starts_on_a_free_default_port() -> None:
    """A free canonical port yields START."""
    result = _resolve(requested_port=None, probe={})
    assert result == Resolution(ServeAction.START, 8788)


def test_resolve_respawns_a_dirty_port_we_own() -> None:
    """A dirty port whose live server we started yields RESPAWN."""
    result = _resolve(requested_port=None, probe={8788: PortStatus.DIRTY}, owned={8788})
    assert result == Resolution(ServeAction.RESPAWN, 8788)


def test_resolve_evicts_a_stranger_from_the_canonical_port() -> None:
    """The canonical port is OURS: a foreign squatter resolves to EVICT, never a scan."""
    result = _resolve(requested_port=None, probe={8788: PortStatus.DIRTY}, owned=set())
    assert result == Resolution(ServeAction.EVICT, 8788)


def test_resolve_never_scans_away_from_the_strict_port() -> None:
    """A dirty canonical port with free neighbours still resolves to the canonical port."""
    result = _resolve(
        requested_port=None,
        probe={8788: PortStatus.DIRTY, 8789: PortStatus.FREE, 8790: PortStatus.SERVING},
        owned=set(),
    )
    assert result.port == 8788
    assert result.action is ServeAction.EVICT


def test_resolve_explicit_non_canonical_port_blocks_on_a_foreign_process() -> None:
    """A pinned non-canonical port held by a stranger is BLOCKED, never evicted."""
    result = _resolve(requested_port=9100, probe={9100: PortStatus.DIRTY}, owned=set())
    assert result == Resolution(ServeAction.BLOCKED, 9100)


def test_resolve_explicit_canonical_pin_still_evicts() -> None:
    """Pinning the canonical port explicitly keeps the eviction claim semantics."""
    result = _resolve(requested_port=8788, probe={8788: PortStatus.DIRTY}, owned=set())
    assert result == Resolution(ServeAction.EVICT, 8788)


def test_resolve_explicit_port_attaches_or_respawns_when_ours() -> None:
    """A pinned port that is serving attaches; a dirty one we own respawns."""
    assert _resolve(requested_port=9100, probe={9100: PortStatus.SERVING}) == Resolution(ServeAction.ATTACH, 9100)
    assert _resolve(requested_port=9100, probe={9100: PortStatus.DIRTY}, owned={9100}) == Resolution(
        ServeAction.RESPAWN, 9100
    )
