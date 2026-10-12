"""Real process shutdown and exclusion checks for package replacement."""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psutil
import pytest

from ...command_execution import run_command
from ..process_quiescence import product_process, quiesce

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_shutdown_recognition_requires_owned_path_or_product_identity(tmp_path: Path) -> None:
    build = tmp_path / "build"
    build.mkdir()
    names = {"cadrumo.exe"}
    assert not product_process(tmp_path / "unrelated/cadrumo.exe", build, "test.product", names)
    assert not product_process(build / "_deps/builder/python.exe", build, "test.product", names)
    assert product_process(build / "stage/Release/app/bin/python.exe", build, "test.product", names)
    prefix = tmp_path / "installed"
    (prefix / "data").mkdir(parents=True)
    marker = prefix / "data/installation.json"
    marker.write_text(json.dumps({"application_id": "other.product"}), encoding="utf-8")
    assert not product_process(prefix / "cadrumo.exe", build, "test.product", names)
    marker.write_text(json.dumps({"application_id": "test.product"}), encoding="utf-8")
    assert product_process(prefix / "cadrumo.exe", build, "test.product", names)


def test_shutdown_times_out_then_terminates_real_product_and_preserves_unrelated_process(tmp_path: Path) -> None:
    build = tmp_path / "build"
    package = build / "stage/Release/app"
    package.mkdir(parents=True)
    (build / "generated").mkdir()
    (build / "generated/contract.json").write_text(
        json.dumps({"installation_identity": {"application_id": "test.product"}}), encoding="utf-8"
    )
    # Use a real independent interpreter image, not a process-list double.
    base = Path(sys.base_prefix) / ("python.exe" if sys.platform == "win32" else "bin/python")
    interpreter = package / base.name
    shutil.copy2(base, interpreter)
    if sys.platform == "win32":
        for library in Path(sys.base_prefix).glob("python*.dll"):
            shutil.copy2(library, package / library.name)
    environment = dict(os.environ, PYTHONHOME=sys.base_prefix)
    code = (
        "import pathlib,sys,time,subprocess; p=pathlib.Path(sys.argv[1]); "
        "child=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(15)']) "
        "if sys.argv[2]=='child' else None; "
        "p.write_text(str(child.pid) if child else 'ready'); "
        "exec('while not p.with_suffix(\".stop\").exists():\\n time.sleep(0.01)')"
    )
    unrelated_ready, product_ready = tmp_path / "unrelated.ready", tmp_path / "product.ready"
    with ThreadPoolExecutor(max_workers=2) as executor:
        unrelated = executor.submit(
            run_command, [sys.executable, "-c", code, str(unrelated_ready), "none"], cwd=tmp_path, timeout_seconds=15
        )
        product = executor.submit(
            run_command,
            [str(interpreter), "-c", code, str(product_ready), "child"],
            cwd=tmp_path,
            environment=environment,
            timeout_seconds=15,
        )
        try:
            deadline = time.monotonic() + 5
            while not (unrelated_ready.is_file() and product_ready.is_file()):
                assert time.monotonic() < deadline, "real process failed to become ready"
                time.sleep(0.01)
            started = time.monotonic()
            quiesce(build, "windows-x86-64", graceful_timeout=0.2, terminate_timeout=5)
            assert product.result(timeout=5).returncode != 0
            assert not psutil.pid_exists(int(product_ready.read_text()))
            assert not unrelated.done()
            if sys.platform == "win32":
                assert time.monotonic() - started >= 0.2
        finally:
            unrelated_ready.with_suffix(".stop").touch()
            product_ready.with_suffix(".stop").touch()
        assert unrelated.result(timeout=5).returncode == 0


def test_shutdown_accepts_real_graceful_window_exit(tmp_path: Path) -> None:
    build = tmp_path / "build"
    package = build / "stage/Release/app"
    package.mkdir(parents=True)
    (build / "generated").mkdir()
    (build / "generated/contract.json").write_text(
        json.dumps({"installation_identity": {"application_id": "test.product"}}), encoding="utf-8"
    )
    base = Path(sys.base_prefix) / ("python.exe" if sys.platform == "win32" else "bin/python")
    interpreter = package / base.name
    shutil.copy2(base, interpreter)
    for library in Path(sys.base_prefix).glob("python*.dll"):
        shutil.copy2(library, package / library.name)
    ready = tmp_path / "graceful.ready"
    code = """
import pathlib, sys
ready = pathlib.Path(sys.argv[1])
if sys.platform == 'win32':
    import win32gui, win32con
    def close(window, message, wparam, lparam):
        if message == win32con.WM_CLOSE:
            win32gui.DestroyWindow(window)
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(window, message, wparam, lparam)
    cls = win32gui.WNDCLASS()
    cls.lpszClassName = 'CadrumoBuildShutdownTest'
    cls.lpfnWndProc = close
    atom = win32gui.RegisterClass(cls)
    win32gui.CreateWindow(atom, '', 0, 0, 0, 0, 0, 0, 0, cls.hInstance, None)
    ready.touch()
    win32gui.PumpMessages()
else:
    import signal, time
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    ready.touch()
    time.sleep(15)
"""
    environment = dict(os.environ, PYTHONHOME=sys.base_prefix, PYTHONPATH=os.pathsep.join(sys.path))
    with ThreadPoolExecutor(max_workers=1) as executor:
        product = executor.submit(
            run_command,
            [str(interpreter), "-c", code, str(ready)],
            cwd=tmp_path,
            environment=environment,
            timeout_seconds=15,
        )
        deadline = time.monotonic() + 5
        while not ready.exists():
            if product.done():
                result = product.result()
                pytest.fail(result.stderr)
            assert time.monotonic() < deadline, "graceful process did not become ready"
            time.sleep(0.01)
        quiesce(build, "windows-x86-64", graceful_timeout=3, terminate_timeout=3)
        assert product.result(timeout=5).returncode == 0
