"""Proofs for the acquisition lane's guards, without downloading anything.

Each guard is shown to catch its defect against real files, real child
processes and real sockets: a volume too full, a root that outgrows its
budget, a write to real storage, a removal outside the lane's own directory,
and a proxy fault.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import stat
import sys
import threading
from pathlib import Path

import pytest

from ..acquisition_lane import (
    DISK_MARGIN_BYTES,
    GIB,
    ChildRun,
    CountingProxy,
    LaneRefusalError,
    LaneReport,
    ProxyMode,
    _browser_row,
    _cleanup_guard,
    credential_leaks,
    fingerprint,
    fingerprint_changes,
    free_space_refusal,
    isolated_environment,
    lane_parent,
    proxy_credential_forms,
    real_acquisition_destinations,
    remove_scratch,
    run_child,
    run_lane,
    runtime_log_changes,
    tree_bytes,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("platform", "override_cache", "installed_parts", "browser_parts"),
    [
        ("win32", False, ("local", "cadrumo"), ("local", "ms-playwright")),
        ("linux", False, ("home", ".local", "share", "cadrumo"), ("home", ".cache", "ms-playwright")),
        ("linux", True, ("home", ".local", "share", "cadrumo"), ("cache", "ms-playwright")),
        (
            "darwin",
            False,
            ("home", "Library", "Application Support", "cadrumo"),
            ("home", "Library", "Caches", "ms-playwright"),
        ),
    ],
)
def test_real_destination_watch_uses_canonical_installed_storage_and_external_browser_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    override_cache: bool,
    installed_parts: tuple[str, ...],
    browser_parts: tuple[str, ...],
) -> None:
    from cadrumo.core import config_state_root

    environment = {
        "LOCALAPPDATA": str(tmp_path / "local"),
        "HOME": str(tmp_path / "home"),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "unrelated-override"),
    }
    if override_cache:
        environment["XDG_CACHE_HOME"] = str(tmp_path / "cache")
    inputs = config_state_root.StateRootInputs(platform=platform, environ=environment, home=tmp_path / "home")
    monkeypatch.setattr(config_state_root, "live_state_root_inputs", lambda: inputs)

    destinations = real_acquisition_destinations(tmp_path / "repository")

    installed = tmp_path.joinpath(*installed_parts)
    assert destinations == (
        tmp_path / "repository" / "var" / "storage" / "components",
        tmp_path / "repository" / "var" / "storage" / "models",
        tmp_path / "repository" / "var" / "storage" / "development" / "components",
        tmp_path / "repository" / "var" / "storage" / "development" / "models",
        installed / "components",
        installed / "models",
        tmp_path.joinpath(*browser_parts),
    )
    assert all(not path.exists() for path in destinations), "enumerating watched destinations must create nothing"


def _plan_floor(download_bytes: int) -> int:
    """The plan's own rule, written out independently: the size plus a fifth, rounded up, plus 1 GiB."""
    return -(-download_bytes * 6 // 5) + GIB


def test_free_space_floor_is_the_plan_rule_plus_ten_gibibytes() -> None:
    """The run starts at exactly the floor and refuses one byte below it, or with no stated size."""
    download = 332_691_793
    floor = _plan_floor(download) + 10 * GIB
    assert DISK_MARGIN_BYTES == 10 * GIB
    assert free_space_refusal(free_bytes=floor, download_bytes=download) is None
    refusal = free_space_refusal(free_bytes=floor - 1, download_bytes=download)
    assert refusal is not None and str(floor) in refusal
    assert free_space_refusal(free_bytes=10**15, download_bytes=None) is not None


def test_isolated_environment_inherits_nothing_of_cadrumo_and_points_everything_into_the_root(tmp_path: Path) -> None:
    """Inherited Cadrumo, Playwright, model-program and proxy settings are dropped; every location is in the root."""
    base = {
        "PATH": "kept",
        "CADRUMO_LOCAL_STORAGE_ROOT": "C:/real/storage",
        "CADRUMO_PROXY_URL": "http://corporate:8080",
        "PLAYWRIGHT_BROWSERS_PATH": "C:/real/ms-playwright",
        "OLLAMA_MODELS": "C:/real/models",
        "https_proxy": "http://corporate:8080",
        "LOCALAPPDATA": "C:/Users/real/AppData/Local",
    }
    environment = isolated_environment(tmp_path, base, proxy_url="http://127.0.0.1:1")
    assert environment["PATH"] == "kept"
    assert "PLAYWRIGHT_BROWSERS_PATH" not in environment
    assert "OLLAMA_MODELS" not in environment
    assert "https_proxy" not in environment
    assert environment["CADRUMO_PROXY_URL"] == "http://127.0.0.1:1"
    located = {
        name: value
        for name, value in environment.items()
        if name.endswith(("_DIR", "_ROOT")) or name in {"LOCALAPPDATA", "APPDATA", "TEMP", "TMP", "TMPDIR"}
    }
    assert len(located) >= 12
    outside = [name for name, value in located.items() if not Path(value).is_relative_to(tmp_path)]
    assert outside == []


def test_fingerprint_names_an_added_a_removed_and_a_changed_file(tmp_path: Path) -> None:
    """Any write to a watched destination shows up in the before-and-after comparison."""
    watched = tmp_path / "components"
    (watched / "playwright").mkdir(parents=True)
    kept = watched / "playwright" / "kept.bin"
    changed = watched / "playwright" / "changed.bin"
    removed = watched / "playwright" / "removed.bin"
    for path in (kept, changed, removed):
        path.write_bytes(b"x")
    missing = tmp_path / "models"
    before = fingerprint([watched, missing])
    assert fingerprint_changes(before, fingerprint([watched, missing])) == []
    changed.write_bytes(b"xy")
    removed.unlink()
    (watched / "playwright" / "added.bin").write_bytes(b"z")
    missing.mkdir()
    changes = fingerprint_changes(before, fingerprint([watched, missing]))
    assert f"added {watched / 'playwright' / 'added.bin'}" in changes
    assert f"removed {removed}" in changes
    assert f"changed {changed}" in changes
    assert f"added {missing}" in changes


def test_removal_refuses_anything_but_a_root_directly_inside_the_lane_directory(tmp_path: Path) -> None:
    """The lane removes only its own roots, read-only files included, and confirms they are gone."""
    parent = tmp_path / "acquisition"
    scratch = parent / "run-1"
    (scratch / "storage" / "deep").mkdir(parents=True)
    locked = scratch / "storage" / "deep" / "read-only.bin"
    locked.write_bytes(b"x" * 1024)
    locked.chmod(stat.S_IREAD)
    with pytest.raises(LaneRefusalError):
        remove_scratch(parent, parent=parent)
    with pytest.raises(LaneRefusalError):
        remove_scratch(scratch / "storage", parent=parent)
    assert scratch.exists()
    assert remove_scratch(scratch, parent=parent) is True
    assert not scratch.exists()
    assert parent.exists()


def test_cleanup_guard_removes_the_root_when_the_run_is_interrupted(tmp_path: Path) -> None:
    """A Ctrl-C inside the run still removes the root, and the report says so."""
    parent = tmp_path / "acquisition"
    scratch = parent / "run-2"
    (scratch / "storage").mkdir(parents=True)
    (scratch / "storage" / "partial.zip").write_bytes(b"x" * 4096)
    report = LaneReport(scratch=str(scratch), items=["browser"])
    with pytest.raises(KeyboardInterrupt), _cleanup_guard(scratch, parent, report):
        raise KeyboardInterrupt
    assert report.scratch_removed is True
    assert not scratch.exists()


def test_lane_parent_is_the_build_tree_testing_path_and_refuses_an_unconfigured_tree(tmp_path: Path) -> None:
    """The root lives under the declared testing directory, never under an invented name."""
    with pytest.raises(LaneRefusalError):
        lane_parent(tmp_path)
    (tmp_path / "build-paths.json").write_text(json.dumps({"paths": {"testing": "testing"}}), encoding="utf-8")
    assert lane_parent(tmp_path) == tmp_path / "testing" / "acquisition"


_GROWER = """
import pathlib, sys, time
target = pathlib.Path(sys.argv[1]) / "growing.bin"
with target.open("wb") as handle:
    for _ in range(400):
        handle.write(b"x" * 262144)
        handle.flush()
        time.sleep(0.05)
"""

_REPORTER = """
import json, sys
print(json.dumps({"event": "step", "step": "download"}), flush=True)
print(json.dumps({"event": "result", "changed": False}), flush=True)
"""


def test_watchdog_stops_a_child_whose_root_outgrows_the_budget(tmp_path: Path) -> None:
    """A child writing past the budget is stopped mid-run, long before it would finish."""
    budget = 4 * 1024 * 1024
    run = run_child(
        [str(tmp_path)],
        environment=dict(os.environ),
        scratch=tmp_path,
        budget_bytes=budget,
        program=[sys.executable, "-c", _GROWER],
        timeout_s=60,
    )
    assert run.aborted is not None and "budget" in run.aborted
    assert run.exit_code != 0
    assert run.peak_scratch_bytes > budget
    # Unchecked, the child would write 100 MiB.
    assert tree_bytes(tmp_path) < 100 * 1024 * 1024


def test_child_events_and_result_are_read_from_its_output(tmp_path: Path) -> None:
    """The child's result line is its result; every other line is an event the parent can react to."""
    seen: list[dict[str, object]] = []
    run = run_child(
        [],
        environment=dict(os.environ),
        scratch=tmp_path,
        budget_bytes=GIB,
        program=[sys.executable, "-c", _REPORTER],
        on_event=seen.append,
    )
    assert run.aborted is None
    assert run.exit_code == 0
    assert run.result == {"event": "result", "changed": False}
    assert run.events == [{"event": "step", "step": "download"}]
    assert len(seen) == 2


def test_interrupt_trigger_stops_the_child_with_its_reason(tmp_path: Path) -> None:
    """The interruption scenario's trigger ends the child as soon as it names a reason."""
    run = run_child(
        [str(tmp_path)],
        environment=dict(os.environ),
        scratch=tmp_path,
        budget_bytes=GIB,
        program=[sys.executable, "-c", _GROWER],
        interrupt=lambda _run, _moved: "interrupted" if tree_bytes(tmp_path) > 1024 * 1024 else None,
        timeout_s=60,
    )
    assert run.aborted == "interrupted"
    assert run.exit_code != 0


def _upstream_server() -> tuple[socket.socket, threading.Thread]:
    server = socket.create_server(("127.0.0.1", 0))

    def serve() -> None:
        connection, _ = server.accept()
        with connection:
            connection.recv(1024)
            connection.sendall(b"y" * 100_000)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return server, thread


def _connect_through(proxy: CountingProxy, port: int, *, credentials: str | None = None) -> socket.socket:
    client = socket.create_connection(("127.0.0.1", proxy.port), timeout=5)
    authorization = ""
    if credentials is not None:
        authorization = f"Proxy-Authorization: Basic {base64.b64encode(credentials.encode()).decode()}\r\n"
    head = f"CONNECT 127.0.0.1:{port} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n{authorization}\r\n"
    client.sendall(head.encode())
    return client


def test_proxy_counts_the_bytes_it_tunnels() -> None:
    """Bytes the publisher sends are counted on the wire, so a run's download size is measured."""
    server, thread = _upstream_server()
    proxy = CountingProxy().start()
    try:
        with _connect_through(proxy, int(server.getsockname()[1])) as client:
            assert client.recv(1024).startswith(b"HTTP/1.1 200")
            client.sendall(b"hello")
            received = b""
            while chunk := client.recv(65536):
                received += chunk
        thread.join(5)
        assert len(received) == 100_000
        assert proxy.counters() == (100_000, 5)
        assert proxy.tunnels == 1
    finally:
        proxy.stop()
        server.close()


def test_proxy_in_reset_mode_aborts_new_tunnels() -> None:
    """A reset tunnel reaches the installer as a dropped connection, never as an answer."""
    proxy = CountingProxy(mode=ProxyMode.RESET).start()
    try:
        with _connect_through(proxy, 9) as client:
            try:
                answer = client.recv(1024)
            except ConnectionResetError:
                answer = b""
        assert answer == b""
        assert proxy.resets == 1
        assert proxy.counters() == (0, 0)
    finally:
        proxy.stop()


def test_opt_in_items_are_refused_before_anything_is_created() -> None:
    """Naming the local AI refuses the run without touching the disk."""
    with pytest.raises(LaneRefusalError):
        run_lane(["browser", "local_ai"])
    with pytest.raises(LaneRefusalError):
        run_lane(["local_ai"])
    with pytest.raises(LaneRefusalError):
        run_lane(["something_else"])


def test_a_running_browser_log_is_reported_apart_and_its_appearance_still_counts(tmp_path: Path) -> None:
    """Another session's browser appending to its log is noted, not mistaken for an acquisition."""
    build = tmp_path / "ms-playwright" / "chromium-1"
    build.mkdir(parents=True)
    log = build / "debug.log"
    log.write_text("started\n", encoding="utf-8")
    before = fingerprint([tmp_path / "ms-playwright"])
    log.write_text("started\nstill running\n", encoding="utf-8")
    after = fingerprint([tmp_path / "ms-playwright"])
    assert fingerprint_changes(before, after) == []
    assert runtime_log_changes(before, after) == [f"changed {log}"]
    (build / "INSTALLATION_COMPLETE").write_text("", encoding="utf-8")
    (tmp_path / "ms-playwright" / "chromium-2" / "debug.log").parent.mkdir()
    (tmp_path / "ms-playwright" / "chromium-2" / "debug.log").write_text("", encoding="utf-8")
    changes = fingerprint_changes(before, fingerprint([tmp_path / "ms-playwright"]))
    assert f"added {build / 'INSTALLATION_COMPLETE'}" in changes
    assert f"added {tmp_path / 'ms-playwright' / 'chromium-2' / 'debug.log'}" in changes


def test_a_proxy_with_credentials_tunnels_only_for_a_client_that_presents_them() -> None:
    """A tunnel the run counted is proof the client took the configured, credentialed route."""
    server, thread = _upstream_server()
    proxy = CountingProxy(credentials="lane:synthetic-word").start()
    try:
        port = int(server.getsockname()[1])
        with _connect_through(proxy, port) as anonymous:
            assert anonymous.recv(1024).startswith(b"HTTP/1.1 407")
        with _connect_through(proxy, port, credentials="lane:another-word") as wrong:
            assert wrong.recv(1024).startswith(b"HTTP/1.1 407")
        with _connect_through(proxy, port, credentials="lane:synthetic-word") as client:
            assert client.recv(1024).startswith(b"HTTP/1.1 200")
            client.sendall(b"hello")
            while client.recv(65536):
                pass
        thread.join(5)
        assert proxy.unauthenticated == 2
        assert proxy.tunnels == 1
    finally:
        proxy.stop()
        server.close()


def test_a_credential_written_anywhere_under_the_root_is_found(tmp_path: Path) -> None:
    """Every spelling of the proxy credentials is searched for, outside the skipped browser builds."""
    forms = proxy_credential_forms("lane:synthetic-word")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "clean.log").write_text("proxy http://127.0.0.1:1 used\n", encoding="utf-8")
    assert credential_leaks(tmp_path, forms) == []
    header = base64.b64encode(b"lane:synthetic-word").decode()
    (tmp_path / "logs" / "worker.log").write_text(f"Proxy-Authorization: Basic {header}\n", encoding="utf-8")
    (tmp_path / "builds").mkdir()
    (tmp_path / "builds" / "chrome.dll").write_bytes(b"synthetic-word")
    assert credential_leaks(tmp_path, forms, skip=(tmp_path / "builds",)) == [str(Path("logs") / "worker.log")]
    report = LaneReport(scratch=str(tmp_path), items=["browser"], secret_forms=forms)
    report.record("leaky", ChildRun(command="x", stdout=["http://lane:synthetic-word@127.0.0.1:1"]))
    assert report.credential_leaks == ["output of leaky"]


def test_the_browser_row_is_read_from_the_published_items() -> None:
    """The lane reads a provision command's rows where the CLI publishes them, and validates their shape."""
    envelope: dict[str, object] = {
        "result": {
            "mode": "quick",
            "complete": False,
            "hardware_limited": False,
            "items": [
                {"item_id": "local_ai", "state": "absent"},
                {"item_id": "browser", "state": "ready", "version": "1"},
            ],
        }
    }
    row = _browser_row(ChildRun(command="status", result=envelope))
    assert (row["item_id"], row["state"], row["version"]) == ("browser", "ready", "1")
    assert _browser_row(ChildRun(command="status", result={"result": {"rows": [{"item_id": "browser"}]}})) == {}
