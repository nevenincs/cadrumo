"""Bounded shutdown of verified product processes before native package replacement."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from contextlib import suppress
from pathlib import Path

import psutil

from .build_log import BuildLog
from .layout import application_images, load_layout


def running(process: psutil.Process) -> bool:
    """Check the retained identity's execution, not a Windows PID's lifetime."""
    if not process.is_running():
        return False
    if sys.platform != "win32":
        return True
    import pywintypes
    import win32api
    import win32con
    import win32event

    from cadrumo_client.transport.windows_native_io import native_windows_call, owned_windows_handle

    try:
        handle = owned_windows_handle(
            native_windows_call(
                win32api,
                "OpenProcess",
                win32con.SYNCHRONIZE | win32con.PROCESS_QUERY_LIMITED_INFORMATION,
                False,
                process.pid,
            )
        )
    except pywintypes.error as error:
        if error.winerror == 87 or not process.is_running():
            return False
        raise
    try:
        if not process.is_running():
            return False
        # An exited process can remain enumerable while another owner holds
        # its handle. Its signalled kernel object is the exit evidence.
        state = win32event.WaitForSingleObject(int(handle), 0)
        if state not in {win32con.WAIT_TIMEOUT, win32con.WAIT_OBJECT_0}:
            raise RuntimeError(f"Cannot observe process exit for pid={process.pid}: wait={state}")
        return state == win32con.WAIT_TIMEOUT
    finally:
        handle.Close()


def wait_for_exit(processes: list[psutil.Process], timeout: float) -> list[psutil.Process]:
    """Wait within one deadline, including Windows processes with retained handles."""
    if sys.platform != "win32":
        _, pending = psutil.wait_procs(processes, timeout=timeout)
        return [process for process in processes if process in pending]
    deadline = time.monotonic() + timeout
    alive: list[psutil.Process] = [process for process in processes if running(process)]
    while alive and (remaining := deadline - time.monotonic()) > 0:
        time.sleep(min(0.05, remaining))
        alive = [process for process in alive if running(process)]
    return alive


def product_process(executable: Path, build: Path, application_id: str, names: set[str]) -> bool:
    """Require an owned build image or an installation identifying this product."""
    image = executable.resolve()
    if image.is_relative_to(build / "stage"):
        return True
    if image.name.casefold() not in names:
        return False
    if image.is_relative_to(build / "cargo") or image.is_relative_to(build / "bin"):
        return True
    for parent in image.parents:
        for relative in ("data/installation.json", "data/package-manifest.json"):
            try:
                document = json.loads((parent / relative).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(document, dict):
                continue
            identity = document.get("installation_identity", document.get("build", document))
            if isinstance(identity, dict) and identity.get("application_id") == application_id:
                return True
    return False


def graceful(processes: list[psutil.Process]) -> None:
    """Ask the product windows to close, or send SIGTERM on POSIX."""
    if sys.platform == "win32":
        import pywintypes
        import win32con
        import win32gui
        import win32process

        retained = {process.pid: process for process in processes}

        def close(window: int, _: object) -> None:
            process = retained.get(win32process.GetWindowThreadProcessId(window)[1])
            if process is not None and process.is_running():
                with suppress(pywintypes.error):
                    win32gui.PostMessage(window, win32con.WM_CLOSE, 0, 0)

        win32gui.EnumWindows(close, None)
    else:
        for process in processes:
            with suppress(psutil.NoSuchProcess):
                process.send_signal(signal.SIGTERM)


def terminate(process: psutil.Process) -> None:
    """Pin the Windows process handle before rechecking creation identity."""
    if sys.platform != "win32":
        process.kill()
        return
    import pywintypes
    import win32api
    import win32con
    import win32event
    import win32process

    from cadrumo_client.transport.windows_native_io import native_windows_call, owned_windows_handle

    try:
        handle = owned_windows_handle(
            native_windows_call(
                win32api,
                "OpenProcess",
                win32con.PROCESS_TERMINATE | win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE,
                False,
                process.pid,
            )
        )
    except (OSError, pywintypes.error):
        if not process.is_running():
            return
        raise
    try:
        if process.is_running() and win32event.WaitForSingleObject(int(handle), 0) == win32con.WAIT_TIMEOUT:
            try:
                win32process.TerminateProcess(int(handle), 1)
            except pywintypes.error:
                if win32event.WaitForSingleObject(int(handle), 0) != win32con.WAIT_OBJECT_0:
                    raise
    finally:
        handle.Close()


def stop_service(build: Path, application_id: str, names: set[str]) -> None:
    """Fence the verified machine broker before it can respawn user managers."""
    if sys.platform != "win32":
        return
    import pywintypes
    import win32service

    identity_path = build / "generated/identity.json"
    service_name = (
        json.loads(identity_path.read_text(encoding="utf-8"))["manager_id"]
        if identity_path.is_file()
        else f"{application_id}.manager"
    )
    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
    try:
        try:
            service = win32service.OpenService(
                scm,
                service_name,
                win32service.SERVICE_QUERY_CONFIG | win32service.SERVICE_QUERY_STATUS,
            )
        except pywintypes.error as error:
            if error.winerror == 1060:  # No service was installed.
                return
            raise RuntimeError("Cannot inspect or stop the installed Cadrumo service") from error
        try:
            command = win32service.QueryServiceConfig(service)[3]
            # The installer owns this exact quoted command, never a shell expression.
            if not command.startswith('"') or '"' not in command[1:]:
                raise RuntimeError("Installed Cadrumo service image could not be verified")
            image, arguments = command[1:].split('"', 1)
            if arguments.strip() != "--service" or not product_process(Path(image), build, application_id, names):
                raise RuntimeError("Installed Cadrumo service image could not be verified")
            state = win32service.QueryServiceStatus(service)[1]
            if state not in {win32service.SERVICE_STOPPED, win32service.SERVICE_STOP_PENDING}:
                stop_handle = win32service.OpenService(scm, service_name, win32service.SERVICE_STOP)
                try:
                    win32service.ControlService(stop_handle, win32service.SERVICE_CONTROL_STOP)
                except pywintypes.error as error:
                    if error.winerror != 1062:  # An exit raced the stop request.
                        raise RuntimeError("Cannot stop the installed Cadrumo service") from error
                finally:
                    win32service.CloseServiceHandle(stop_handle)
        finally:
            win32service.CloseServiceHandle(service)
    finally:
        win32service.CloseServiceHandle(scm)


def quiesce(build: Path, target: str, *, graceful_timeout: float = 10, terminate_timeout: float = 10) -> None:
    """Retain process creation identities and refuse surviving or respawned owners."""
    started = time.monotonic()
    log = BuildLog("native-process-quiesce")
    build = build.resolve(strict=True)
    layout = load_layout(target)
    identity = json.loads((build / "generated/contract.json").read_text(encoding="utf-8"))["installation_identity"]
    images = application_images(layout)
    names = {image.file.casefold() for image in images}
    names.add(Path(layout["paths"]["executable"]).name.casefold())
    if development := layout["files"].get("development_executable"):
        names.add(Path(development).name.casefold())
    supervisors = {image.file.casefold() for image in images if image.startup or image.desktop}
    manager_pids: set[int] = set()
    names.update(
        f"{name}{layout['entrypoint_suffix']}".casefold()
        for name in (*layout["entrypoints"], *layout.get("bundled_images", {}))
    )
    excluded = {os.getpid(), *(process.pid for process in psutil.Process().parents())}

    service_started = time.monotonic()
    stop_service(build, identity["application_id"], names)
    log.status(f"service stop request took {time.monotonic() - service_started:.3f} s")

    def discover() -> list[psutil.Process]:
        found: dict[int, psutil.Process] = {}
        for process in psutil.process_iter(["name"], ad_value=""):
            try:
                if process.pid in excluded or not product_process(
                    Path(process.exe()), build, identity["application_id"], names
                ):
                    continue
                # Cache creation time before any shutdown request. psutil checks
                # this identity again before signals, killing and descendant reads.
                process.create_time()
                if not running(process):
                    continue
                found[process.pid] = process
                if str(process.info["name"]).casefold() in supervisors:
                    manager_pids.add(process.pid)
                for child in process.children(recursive=True):
                    if child.pid not in excluded and running(child):
                        child.create_time()
                        found[child.pid] = child
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied as error:
                if str(process.info["name"]).casefold() in names:
                    raise RuntimeError("Cannot verify or stop a running Cadrumo process") from error
        return list(found.values())

    discovery_started = time.monotonic()
    processes = discover()
    log.status(f"process discovery took {time.monotonic() - discovery_started:.3f} s; {len(processes)} owners running")
    if not processes:
        return
    for process in processes:
        log.status(f"shutdown owner pid={process.pid} created={process.create_time():.6f}")
    log.status(
        f"{len(processes)} Cadrumo processes run from this build; requesting graceful exit within "
        f"{graceful_timeout:g} s"
    )
    graceful_started = time.monotonic()
    graceful(processes)
    alive = wait_for_exit(processes, graceful_timeout)
    log.status(f"graceful shutdown took {time.monotonic() - graceful_started:.3f} s; {len(alive)} owners still running")
    # Include workers launched while the manager was settling its graceful stop.
    alive = list({process.pid: process for process in (*alive, *discover())}.values())
    alive.sort(key=lambda process: process.pid not in manager_pids)
    if alive:
        log.warning(f"terminating {len(alive)} processes that did not exit gracefully")
    forced_started = time.monotonic()
    deadline = forced_started + terminate_timeout
    remaining = {process.pid: process for process in alive if running(process)}
    attempted: set[tuple[int, float]] = set()
    while remaining:
        for process in sorted(remaining.values(), key=lambda process: process.pid not in manager_pids):
            with suppress(psutil.NoSuchProcess):
                attempted.add((process.pid, process.create_time()))
                terminate(process)
        surviving = wait_for_exit(list(remaining.values()), max(0, deadline - time.monotonic()))
        remaining = {process.pid: process for process in (*surviving, *discover()) if running(process)}
        if time.monotonic() >= deadline:
            break
    log.status(f"forced shutdown took {time.monotonic() - forced_started:.3f} s; {len(remaining)} owners still running")
    if remaining:
        identities = ", ".join(
            f"pid={process.pid} created={process.create_time():.6f}" for process in remaining.values()
        )
        raise RuntimeError(
            f"Cadrumo processes remain alive after forced termination ({identities}); package replacement refused"
        )
    log.status(
        f"quiescent after {time.monotonic() - started:.3f} s; force attempted for {len(attempted)} process identities"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--target", required=True)
    arguments = parser.parse_args()
    quiesce(arguments.build, arguments.target)
