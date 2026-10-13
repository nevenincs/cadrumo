"""Bounded shutdown of verified product processes before native package replacement."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from contextlib import suppress
from pathlib import Path

import psutil

from .build_log import BuildLog
from .layout import application_images, load_layout


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
    import win32process

    from cadrumo.adapters.local_runtime.windows_native_io import native_windows_call, owned_windows_handle

    try:
        handle = owned_windows_handle(
            native_windows_call(
                win32api,
                "OpenProcess",
                win32con.PROCESS_TERMINATE | win32con.PROCESS_QUERY_LIMITED_INFORMATION,
                False,
                process.pid,
            )
        )
    except (OSError, pywintypes.error):
        if not process.is_running():
            return
        raise
    try:
        if process.is_running():
            win32process.TerminateProcess(int(handle), 1)
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
    build = build.resolve(strict=True)
    layout = load_layout(target)
    identity = json.loads((build / "generated/contract.json").read_text(encoding="utf-8"))["installation_identity"]
    images = application_images(layout)
    names = {image.file.casefold() for image in images}
    names.add(Path(layout["paths"]["executable"]).name.casefold())
    if development := layout["files"].get("development_executable"):
        names.add(Path(development).name.casefold())
    supervisors = {image.file.casefold() for image in images if image.startup}
    manager_pids: set[int] = set()
    names.update(f"{name}{layout['entrypoint_suffix']}".casefold() for name in layout["entrypoints"])
    excluded = {os.getpid(), *(process.pid for process in psutil.Process().parents())}

    stop_service(build, identity["application_id"], names)

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
                found[process.pid] = process
                if str(process.info["name"]).casefold() in supervisors:
                    manager_pids.add(process.pid)
                for child in process.children(recursive=True):
                    if child.pid not in excluded:
                        found[child.pid] = child
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied as error:
                if str(process.info["name"]).casefold() in names:
                    raise RuntimeError("Cannot verify or stop a running Cadrumo process") from error
        return list(found.values())

    processes = discover()
    if not processes:
        return
    log = BuildLog("native-process-quiesce")
    log.status(
        f"{len(processes)} Cadrumo processes run from this build; requesting graceful exit within "
        f"{graceful_timeout:g} s"
    )
    graceful(processes)
    _, alive = psutil.wait_procs(processes, timeout=graceful_timeout)
    # Include workers launched while the manager was settling its graceful stop.
    alive = list({process.pid: process for process in (*alive, *discover())}.values())
    alive.sort(key=lambda process: process.pid not in manager_pids)
    if alive:
        log.warning(f"terminating {len(alive)} processes that did not exit gracefully")
    for process in alive:
        with suppress(psutil.NoSuchProcess):
            terminate(process)
    _, surviving = psutil.wait_procs(alive, timeout=terminate_timeout)
    if surviving or discover():
        raise RuntimeError("Cadrumo processes remain alive after forced termination; package replacement refused")
    log.status(f"stopped {len(processes)} processes, {len(alive)} of them forcibly")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--target", required=True)
    arguments = parser.parse_args()
    quiesce(arguments.build, arguments.target)
