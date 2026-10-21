"""Real process shutdown and exclusion checks for package replacement."""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from types import ModuleType, SimpleNamespace

import psutil
import pytest

from ...command_execution import run_command
from .. import process_quiescence
from ..process_quiescence import product_process, quiesce, running

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_shutdown_recognition_requires_named_image_inside_owned_build_tree(tmp_path: Path) -> None:
    build = tmp_path / "build"
    build.mkdir()
    names = {"cadrumo.exe", "python.exe"}
    assert not product_process(tmp_path / "unrelated/cadrumo.exe", build, names)
    assert not product_process(build / "_deps/builder/python.exe", build, names)
    assert product_process(build / "stage/Release/app/bin/python.exe", build, names)
    assert product_process(build / "cargo/debug/cadrumo.exe", build, names)
    assert product_process(build / "bin/cadrumo.exe", build, names)
    assert not product_process(build / "stage/Release/app/bin/unlisted.exe", build, names)

    # A copied package can carry the same product marker, but its image is not
    # owned by this build and must not be selected for shutdown.
    prefix = tmp_path / "verified-copy"
    (prefix / "data").mkdir(parents=True)
    (prefix / "data/package-manifest.json").write_text(
        json.dumps({"build": {"application_id": "test.product"}}), encoding="utf-8"
    )
    assert not product_process(prefix / "bin/cadrumo.exe", build, names)


def test_shutdown_recognition_rejects_symlink_escape_from_owned_stage(tmp_path: Path) -> None:
    build = tmp_path / "build"
    stage = build / "stage/Release/app/bin"
    stage.mkdir(parents=True)
    external = tmp_path / "external/cadrumo.exe"
    external.parent.mkdir()
    external.write_bytes(b"image")
    (external.parent / "data").mkdir()
    (external.parent / "data/installation.json").write_text(
        json.dumps({"application_id": "test.product"}), encoding="utf-8"
    )
    image = stage / "cadrumo.exe"
    try:
        image.symlink_to(external)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"file symlink creation is unavailable: {error}")
    assert not product_process(image, build, {"cadrumo.exe"})

    linked_build = tmp_path / "linked-build"
    linked_build.mkdir()
    try:
        (linked_build / "stage").symlink_to(external.parent, target_is_directory=True)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"directory symlink creation is unavailable: {error}")
    assert not product_process(linked_build / "stage/cadrumo.exe", linked_build, {"cadrumo.exe"})


def test_external_service_image_is_left_running(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    build = tmp_path / "build"
    (build / "generated").mkdir(parents=True)
    (build / "generated/identity.json").write_text(json.dumps({"manager_id": "test.product.manager"}), encoding="utf-8")
    external = tmp_path / "installed/bin/cadrumo-manager.exe"
    external.parent.mkdir(parents=True)
    external.write_bytes(b"image")
    (tmp_path / "installed/data").mkdir()
    (tmp_path / "installed/data/package-manifest.json").write_text(
        json.dumps({"build": {"application_id": "test.product"}}), encoding="utf-8"
    )
    calls: list[str] = []
    command = f'"{external}" --service'

    class FakeServiceError(Exception):
        pass

    pywintypes = ModuleType("pywintypes")
    vars(pywintypes).update(error=FakeServiceError)
    win32service = ModuleType("win32service")
    vars(win32service).update(
        SC_MANAGER_CONNECT=1,
        SERVICE_QUERY_CONFIG=2,
        SERVICE_QUERY_STATUS=4,
        SERVICE_STOPPED=1,
        SERVICE_STOP_PENDING=2,
        SERVICE_STOP=8,
        SERVICE_CONTROL_STOP=1,
        SERVICE_RUNNING=4,
        OpenSCManager=lambda *_args: "scm",
        OpenService=lambda *_args: "service",
        QueryServiceConfig=lambda _service: (None, None, None, command),
        QueryServiceStatus=lambda _service: pytest.fail("external service must not be queried"),
        ControlService=lambda *_args: calls.append("stopped"),
        CloseServiceHandle=lambda handle: calls.append(f"closed:{handle}"),
    )
    monkeypatch.setattr(process_quiescence, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setitem(sys.modules, "pywintypes", pywintypes)
    monkeypatch.setitem(sys.modules, "win32service", win32service)

    process_quiescence.stop_service(build, "test.product", {"cadrumo-manager.exe"})

    assert calls == ["closed:service", "closed:scm"]


def test_shutdown_terminates_owned_tree_but_preserves_external_copy_and_unrelated_process(tmp_path: Path) -> None:
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
    external_package = tmp_path / "verified-copy"
    external_package.mkdir()
    external_interpreter = external_package / base.name
    shutil.copy2(base, external_interpreter)
    if sys.platform == "win32":
        for library in Path(sys.base_prefix).glob("python*.dll"):
            shutil.copy2(library, package / library.name)
            shutil.copy2(library, external_package / library.name)
    (external_package / "data").mkdir()
    (external_package / "data/package-manifest.json").write_text(
        json.dumps({"build": {"application_id": "test.product"}}), encoding="utf-8"
    )
    environment = dict(os.environ, PYTHONHOME=sys.base_prefix)
    code = (
        "import os,pathlib,sys,time,subprocess; p=pathlib.Path(sys.argv[1]); "
        "child=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']) "
        "if sys.argv[2]=='child' else None; "
        "p.write_text(str(child.pid) if child else str(os.getpid())); "
        "exec('while not p.with_suffix(\".stop\").exists():\\n time.sleep(0.01)')"
    )
    unrelated_ready = tmp_path / "unrelated.ready"
    product_ready = tmp_path / "product.ready"
    external_ready = tmp_path / "external.ready"
    with ThreadPoolExecutor(max_workers=3) as executor:
        unrelated = executor.submit(
            run_command, [sys.executable, "-c", code, str(unrelated_ready), "none"], cwd=tmp_path, timeout_seconds=30
        )
        product = executor.submit(
            run_command,
            [str(interpreter), "-c", code, str(product_ready), "child"],
            cwd=tmp_path,
            environment=environment,
            timeout_seconds=30,
        )
        external = executor.submit(
            run_command,
            [str(external_interpreter), "-c", code, str(external_ready), "none"],
            cwd=tmp_path,
            environment=environment,
            timeout_seconds=30,
        )
        try:
            deadline = time.monotonic() + 5
            while not (unrelated_ready.is_file() and product_ready.is_file() and external_ready.is_file()):
                assert time.monotonic() < deadline, "real process failed to become ready"
                time.sleep(0.01)
            child = psutil.Process(int(product_ready.read_text()))
            child.create_time()
            external_process = psutil.Process(int(external_ready.read_text()))
            external_process.create_time()
            with ExitStack() as retained:
                if sys.platform == "win32":
                    import win32api
                    import win32con
                    import win32event

                    from cadrumo_client.transport.windows_native_io import (
                        native_windows_call,
                        owned_windows_handle,
                    )

                    # Debuggers and supervisors may retain these handles after
                    # exit. Quiescence must wait for execution to end, not for
                    # every other owner to release the process object.
                    for pid in (child.pid, child.ppid()):
                        handle = owned_windows_handle(
                            native_windows_call(
                                win32api,
                                "OpenProcess",
                                win32con.SYNCHRONIZE | win32con.PROCESS_QUERY_LIMITED_INFORMATION,
                                False,
                                pid,
                            )
                        )
                        retained.callback(handle.Close)
                started = time.monotonic()
                quiesce(build, "windows-x86-64", graceful_timeout=0.2, terminate_timeout=5)
                assert product.result(timeout=5).returncode != 0
                assert not running(child)
                assert running(external_process)
                assert not external.done()
                if sys.platform == "win32":
                    assert win32event.WaitForSingleObject(int(handle), 0) == win32con.WAIT_OBJECT_0
            assert not unrelated.done()
            if sys.platform == "win32":
                assert time.monotonic() - started >= 0.2
        finally:
            unrelated_ready.with_suffix(".stop").touch()
            product_ready.with_suffix(".stop").touch()
            external_ready.with_suffix(".stop").touch()
        assert unrelated.result(timeout=5).returncode == 0
        assert external.result(timeout=5).returncode == 0


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
    import pywin32_bootstrap
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
