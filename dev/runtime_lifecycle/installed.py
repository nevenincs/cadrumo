"""Native-guarded immediate installed acceptance, reusable without pytest."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Literal, cast, override
from uuid import UUID, uuid4

from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_login_native import WindowsTokenIdentity
from cadrumo.adapters.local_runtime.windows_native_io import owned_windows_handle
from cadrumo.adapters.local_runtime.windows_process import WindowsOwnedProcess
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.storage_environment import PROCESS_ENVIRONMENT, STORAGE_ROOT, StoragePlatform
from dev.packaging.command_execution import run_command

from .harness import Connection, LifecycleHarness


def _interactive_identity(token: int, owner: str) -> WindowsTokenIdentity:
    """Read and reobserve one actual retained token and its own LSA logon."""
    from cadrumo.adapters.local_runtime.windows_login_native import read_windows_logon, read_windows_token_identity

    identity = read_windows_token_identity(token)
    logon = read_windows_logon(identity.authentication_id)
    if (
        identity.owner != owner
        or logon.owner != owner
        or identity.session_id != logon.session
        or logon.kind not in (2, 10, 11, 12)
        or read_windows_token_identity(token) != identity
        or read_windows_logon(identity.authentication_id) != logon
    ):
        raise ValueError("Installed acceptance requires the actual interactive account token and LSA logon")
    return identity


def require_interactive_token(process: int, owner: str) -> WindowsTokenIdentity:
    """Validate actual retained-token LSA identity without desktop-context substitution."""
    import win32api
    import win32security

    token = win32security.OpenProcessToken(process, win32security.TOKEN_QUERY)
    try:
        return _interactive_identity(int(token), owner)
    finally:
        win32api.CloseHandle(token)


def require_linked_interactive_token(process: int, owner: str) -> WindowsTokenIdentity:
    """Observe the kernel-linked UAC counterpart without using it to authenticate."""
    import win32api
    import win32security

    token = win32security.OpenProcessToken(process, win32security.TOKEN_QUERY)
    linked = None
    try:
        original = _interactive_identity(int(token), owner)
        elevated = bool(win32security.GetTokenInformation(token, win32security.TokenElevation))
        linked = win32security.GetTokenInformation(token, win32security.TokenLinkedToken)
        counterpart = _interactive_identity(int(linked), owner)
        if (
            counterpart.session_id != original.session_id
            or bool(win32security.GetTokenInformation(linked, win32security.TokenElevation)) == elevated
            or _interactive_identity(int(token), owner) != original
            or _interactive_identity(int(linked), owner) != counterpart
        ):
            raise ValueError("GUI phase lacks the genuine same-user/session opposite-elevation UAC linked token")
        return counterpart
    finally:
        if linked is not None:
            win32api.CloseHandle(linked)
        win32api.CloseHandle(token)


def require_credential_facility() -> None:
    """Probe an intentionally nonexistent target; never read or create real credentials."""
    import pywintypes
    import win32cred

    try:
        win32cred.CredRead("CadrumoInstalledAcceptanceMissing/" + str(uuid4()), win32cred.CRED_TYPE_GENERIC)
    except pywintypes.error as error:
        if error.winerror == 1168:
            return
        raise ValueError(
            f"Installed acceptance credential facility unavailable: native_code={error.winerror}"
        ) from None
    raise ValueError("Installed acceptance credential probe unexpectedly exists")


def _canonical_guest_root() -> Path:
    """Verify the actual token's canonical destination, not the pin's unknowable origin."""
    from win32com.shell import shell, shellcon

    from cadrumo.core.storage_environment import normalize_storage_path

    if os.environ.get(STORAGE_ROOT.development_variable):
        raise ValueError("Installed acceptance refuses storage overrides")
    base = normalize_storage_path(Path(shell.SHGetKnownFolderPath(shellcon.FOLDERID_LocalAppData, 0, None)))
    ambient_base = os.environ.get("LOCALAPPDATA")
    if ambient_base and normalize_storage_path(Path(ambient_base)) != base:
        raise ValueError("Installed acceptance refuses a noncanonical native storage base")
    pin = os.environ.get(STORAGE_ROOT.variable)
    channel = STORAGE_ROOT.stable_channel
    if pin:
        if normalize_storage_path(Path(pin)) not in (
            base / STORAGE_ROOT.channel_directory(STORAGE_ROOT.stable_channel),
            base / STORAGE_ROOT.channel_directory("preview"),
        ):
            raise ValueError("Installed acceptance refuses storage overrides")
        build = vars(sys).get("cadrumo_build")
        bootstrap = sys.modules.get("_cadrumo_bootstrap")
        if not isinstance(build, dict) or build.get("development") != 0 or bootstrap is None:
            raise ValueError("Installed acceptance canonical storage pin requires the shipping native interpreter")
        # Its native build identity and startup inventory must still match the package.
        bootstrap.verify()
        package = (Path(sys.executable).parent / bootstrap.LAYOUT["package_root_from_executable"]).resolve(strict=True)
        manifest = json.loads(
            bootstrap._inside(package, bootstrap.LAYOUT["files"]["package_manifest"]).read_text(encoding="utf-8")
        )
        channel = manifest["build"]["channel"]
        if channel not in (STORAGE_ROOT.stable_channel, "preview"):
            raise ValueError("Installed acceptance requires a supported verified package channel")
    root = normalize_storage_path(base / STORAGE_ROOT.channel_directory(channel))
    if pin and normalize_storage_path(Path(pin)) != root:
        raise ValueError("Installed acceptance refuses storage overrides")
    return root


def _require_fresh_root(root: Path) -> None:
    """Permit only the native bootstrap's empty declared temporary directory."""
    from cadrumo.core.storage_environment import normalize_storage_path
    from cadrumo.core.storage_taxonomy import StorageCategory
    from cadrumo.core.storage_taxonomy_locations import storage_location

    temporary = root / storage_location(StorageCategory.TEMPORARY_FILES).relative_path()
    if root.exists():
        for entry in root.iterdir():
            if (
                entry != temporary
                or not entry.is_dir()
                or normalize_storage_path(entry) != temporary
                or any(entry.iterdir())
            ):
                raise ValueError("Installed acceptance requires fresh canonical storage on the disposable guest")


def require_installation_guest(
    vm_id: UUID,
    account_sid: str,
    scope: Literal["user", "machine"],
    *,
    guest_kind: Literal["hyperv", "qemu"] = "hyperv",
    fresh: bool = True,
    interactive: bool = True,
    caller_elevation: Literal[False] | None = None,
) -> Path:
    """Bind destructive acceptance to the explicitly selected native Hyper-V guest and account."""
    if caller_elevation is not None and (
        caller_elevation is not False or scope != "machine" or fresh or not interactive
    ):
        raise ValueError("Least-privilege GUI observation requires a held machine installation and interactive caller")
    if sys.platform != "win32":
        raise ValueError("Installed acceptance requires the selected disposable Windows guest")
    import winreg

    import win32api
    import win32security

    from cadrumo.adapters.local_runtime.windows_native_io import current_windows_owner_sid

    if scope not in {"user", "machine"} or not account_sid.startswith("S-1-5-21-"):
        raise ValueError("Installed acceptance requires an explicit scope and dedicated account SID")
    root = _canonical_guest_root()
    # Importing the COM client creates its declared generated cache. Observe
    # pristine storage before this guard's own native-hardware discovery does so.
    if fresh:
        _require_fresh_root(root)
    import win32com.client

    wmi = win32com.client.GetObject("winmgmts:")
    systems = tuple(wmi.ExecQuery("SELECT Manufacturer,Model FROM Win32_ComputerSystem"))
    if len(systems) != 1:
        raise ValueError("Installed acceptance requires a unique native guest hardware identity")
    hardware = (systems[0].Manufacturer, systems[0].Model)
    if guest_kind == "hyperv":
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Virtual Machine\Guest\Parameters") as key:
            native_vm, kind = winreg.QueryValueEx(key, "VirtualMachineId")
        if kind != winreg.REG_SZ or UUID(native_vm.strip("{}")) != vm_id:
            raise ValueError("Installed acceptance guest identity differs from the selected Hyper-V VM")
        if hardware != ("Microsoft Corporation", "Virtual Machine"):
            raise ValueError("Installed acceptance requires native Hyper-V guest evidence")
    elif guest_kind == "qemu":
        products = tuple(wmi.ExecQuery("SELECT UUID FROM Win32_ComputerSystemProduct"))
        if len(products) != 1 or UUID(products[0].UUID) != vm_id:
            raise ValueError("Installed acceptance hardware UUID differs from the selected QEMU guest")
        if hardware != ("QEMU", "CadrumoRuntimeGuest"):
            raise ValueError("Installed acceptance requires the pinned native QEMU guest template")
    else:
        raise ValueError("Installed acceptance requires a supported, explicitly selected guest kind")
    if current_windows_owner_sid() != account_sid:
        raise ValueError("Installed acceptance account differs from the selected dedicated guest account")
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_QUERY)
    try:
        elevated = bool(win32security.GetTokenInformation(token, win32security.TokenElevation))
    finally:
        token.Close()
    if elevated != ((scope == "machine") if caller_elevation is None else caller_elevation):
        raise ValueError("Installed acceptance token elevation differs from its installation scope")
    if interactive:
        require_interactive_token(int(win32api.GetCurrentProcess()), account_sid)
        require_credential_facility()
    return root


class InstalledLifecycleHarness(LifecycleHarness):
    """Exercise one admitted installation on the explicitly guarded disposable guest."""

    def __init__(self, plan: Path, runner: Path, root: Path) -> None:
        """Bind the authentic maintenance plan and canonical fresh guest storage."""
        from defusedxml import ElementTree

        self.plan, self.runner = plan, runner
        self.intent = json.loads(plan.read_text(encoding="utf-8"))
        self.prefix = Path(self.intent["prefix"])
        package = self.prefix / self.intent["contract"]["layout"]["installation"]["versions"] / self.intent["version"]
        super().__init__(package / "cadrumo-manager.exe", package, root)
        source = plan.parent / "wix" / f"{self.intent['scope']}-registration.wxs"
        node = ElementTree.parse(source).find(
            ".//{http://wixtoolset.org/schemas/v4/wxs}Property[@Id='CadrumoRegistration']"
        )
        if node is None:
            raise ValueError("Installed acceptance requires the immutable native registration description")
        self.registration = json.loads(node.attrib["Value"])
        machine_node = ElementTree.parse(plan.parent / "wix/machine-registration.wxs").find(
            ".//{http://wixtoolset.org/schemas/v4/wxs}Property[@Id='CadrumoRegistration']"
        )
        if machine_node is None:
            raise ValueError("Installed acceptance requires the machine registration preflight description")
        self.machine_services = json.loads(machine_node.attrib["Value"])["services"]
        self._preflight_admitted = False
        self._installation_attempted = False
        self._removed = False
        self._held = False
        self.manager_handle: Any = None

    def native_environment(self) -> dict[str, str]:
        """Native owners derive storage and authority themselves; frontend pins stay ambient."""
        excluded = {
            name.upper()
            for name in (*STORAGE_ROOT.precedence, *PROCESS_ENVIRONMENT.inherited_names(StoragePlatform.WINDOWS))
        }
        return {key: value for key, value in os.environ.items() if key.upper() not in excluded}

    def maintenance(self, command: str) -> dict[str, Any]:
        """Use the actual authenticated native transaction, preserving typed failure evidence."""
        try:
            result = run_command(
                [str(self.runner), command, "--plan", str(self.plan)],
                cwd=self.plan.parent,
                environment=self.native_environment(),
                timeout_seconds=900,
            )
        except subprocess.TimeoutExpired as error:
            self.retain_native_timeout(error, command)
            raise
        document = json.loads(result.stdout)
        allowed = {"published", "already_published_verified"} if command == "install" else {"unregistered"}
        if (
            result.returncode
            or document.get("schema") != 1
            or document.get("outcome") not in allowed
            or document.get("service_restore")
        ):
            failure = _precommit_receipt(document, result.returncode)
            failure["phases"] = _native_phase_facts(result.stderr)
            failure["command"] = command if command in {"install", "unregister"} else "unexpected"
            cause = document.get("cause")
            causes = {
                "native_removal_failed",
                "native_removal_refused",
                "native_owner_unavailable",
                "version_in_use_or_unknown",
                "version_installation_failed",
                "version_inventory_failed",
                "registration_entrypoint_invalid",
                "shared_registration_in_use_or_unknown",
                "registration_installation_failed",
            }
            if cause not in causes:
                cause = None
            failure["cause"] = cause
            if document.get("code") in causes | {
                "invalid_plan",
                "artifact_or_owner_refused",
                "installer_authority_unavailable",
                "existing_registration_not_verified",
                "installation_destination_inventory_refused",
                "installation_destination_too_long",
                "native_preparation_refused",
                "native_owner_protocol_not_admitted",
                "native_transaction_unavailable",
                "native_commit_failed",
                "native_publication_incomplete",
                "native_maintenance_busy",
                "native_removal_admission_refused",
                "native_removal_busy_or_unavailable",
                "native_removal_owner_differs",
                "native_removal_owner_unknown",
                "native_removal_owner_unavailable",
                "native_removal_publication_incomplete",
                "native_removal_publication_invalid",
                "native_removal_recovery_fenced",
                "native_removal_recovery_refused",
                "native_recovery_commit_failed",
                "native_service_removal_unconfirmed",
            }:
                failure["code"] = document["code"]
            if document.get("outcome") in {
                "published",
                "already_published_verified",
                "removed",
                "unregistered",
                "refused",
                "committed_publication_pending",
            }:
                failure["outcome"] = document["outcome"]
            error = RuntimeError(
                f"Native {command} failed: outcome={failure['outcome']}, code={failure['code']}, "
                f"cause={cause}, service_restore={failure['service_restore']}, "
                f"candidate_rejection={failure['candidate_rejection']}"
            )
            self.retain_native_failure(error, failure)
            raise error
        return document

    def retain_native_failure(self, error: BaseException, facts: dict[str, Any]) -> None:
        """Retain bounded facts without replacing the actual native failure."""
        evidence = self.plan.with_name(f"native-maintenance-failure-{uuid4().hex}.json")
        try:
            with evidence.open("x", encoding="utf-8") as stream:
                json.dump(facts, stream, sort_keys=True)
        except BaseException as retention:
            error.add_note(f"Native failure evidence retention failed: {type(retention).__name__}")

    def retain_native_timeout(self, error: subprocess.TimeoutExpired, command: str) -> None:
        """A timeout has phase evidence, never an invented native result."""
        facts = {
            "schema": 1,
            "command": command if command in {"install", "unregister"} else "unexpected",
            "observation": "timed_out",
            "native_result": None,
            "phases": _native_phase_facts(error.stderr),
        }
        self.retain_native_failure(error, facts)
        error.add_note(f"Native maintenance timeout phases: {json.dumps(facts['phases'], sort_keys=True)}")

    def cleanup_after_outer_exit(self) -> None:
        """Reconcile this preflight-admitted run through its authentic native transaction."""
        if not self._preflight_admitted:
            raise ValueError("Outer cleanup requires this run's verified absent-owner preflight")
        self._installation_attempted = True
        retained_runtime = None
        observation_failure = None
        try:
            self.start_manager(activate=False, absent_ok=True)
            retained_runtime = self.retain_cleanup_runtime()
            if self.manager_handle is not None and self.intent["scope"] == "user":
                self.observe_cleanup_popup()
        except Exception as error:
            observation_failure = error
        try:
            self.stop_manager()
        except BaseException as cleanup:
            if observation_failure is None:
                raise
            observation_failure.add_note(f"Installed acceptance cleanup failed: {type(cleanup).__name__}")
            raise observation_failure from None
        if observation_failure is not None:
            raise observation_failure
        if retained_runtime is not None:
            retained_runtime.wait(timeout=90)
        if self.manager_handle is None:
            self.start_manager(activate=False, absent_ok=True)
            if self.manager_handle is not None:
                self.process.wait(timeout=90)

    def observe_cleanup_popup(self) -> None:
        """Require the retained manager's native menu before authentic removal."""
        import win32event
        import win32gui
        import win32process

        retained, pid = self.manager_handle, self.process.pid
        self.start_manager()
        if self.process.pid != pid or win32event.WaitForSingleObject(int(retained), 0) != win32event.WAIT_TIMEOUT:
            raise AssertionError("Cleanup activation replaced the retained manager")
        deadline = time.monotonic() + 10
        menus: list[int] = []

        def observe(window: int, _context: object) -> None:
            if win32process.GetWindowThreadProcessId(window)[1] == pid and win32gui.GetClassName(window) == "#32768":
                menus.append(window)

        while True:
            menus.clear()
            win32gui.EnumWindows(observe, None)
            if win32event.WaitForSingleObject(int(retained), 0) != win32event.WAIT_TIMEOUT:
                raise AssertionError("Cleanup manager exited before its native menu was observed")
            if menus:
                self.metrics["cleanup_popup_observed"] = 1.0
                return
            if time.monotonic() >= deadline:
                raise TimeoutError("Retained manager did not reveal its native menu before cleanup")
            time.sleep(0.1)

    def retain_cleanup_runtime(self) -> WindowsOwnedProcess | None:
        """Retain an existing exact-image kernel IPC peer; never activate a process."""
        import win32api
        import win32con

        from cadrumo.adapters.local_runtime.windows_native_io import current_windows_owner_sid

        endpoint = WindowsRuntimeEndpoint(storage_root=self.root)
        self.resources.callback(endpoint.close)
        try:
            native = endpoint.connect(timeout=1, expected_image=self.runtime_image)
        except RuntimeRefusalError as error:
            if error.reason is RuntimeRefusalCode.ENDPOINT_NOT_READY:
                return None
            raise
        self.resources.callback(native.close)
        pid = native.peer.process_id
        if type(pid) is not int or pid <= 0:
            raise ValueError("Cleanup peer lacks a native process identity")
        handle = owned_windows_handle(
            win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE, False, pid)
        )
        self.resources.callback(handle.Close)
        native.verify_peer_process(int(handle))
        owner = current_windows_owner_sid()
        peer = require_interactive_token(int(handle), owner)
        caller = require_interactive_token(int(win32api.GetCurrentProcess()), owner)
        if peer.session_id != caller.session_id:
            raise ValueError("Cleanup runtime token differs from the admitted guest session")
        if self.intent["scope"] == "user" and peer.authentication_id != caller.authentication_id:
            raise ValueError("Cleanup runtime token differs from the admitted guest logon")
        return WindowsOwnedProcess(handle=int(handle), pid=pid)

    def preflight(self) -> None:
        """Observe absent owned installation/resources before authorizing timeout cleanup."""
        if self.prefix.exists() and any(self.prefix.iterdir()):
            raise ValueError("Installed acceptance refuses a preexisting installation prefix")
        self.verify_registration(absent=True)
        for service in self.machine_services:
            with self.service(service, absent=True):
                pass

        self._preflight_admitted = True

    @override
    def __enter__(self) -> InstalledLifecycleHarness:
        """Install only after preflight, retaining exact owner cleanup on failures."""
        self.preflight()
        self._installation_attempted = True
        try:
            self.maintenance("install")
            self.verify_registration()
            self.root.mkdir(exist_ok=True)
            self.endpoint = WindowsRuntimeEndpoint(storage_root=self.root)
            self.resources.callback(self.endpoint.close)
            self.started = time.monotonic()
            self.start_manager()
            return self
        except BaseException as error:
            try:
                self.stop_manager()
            except BaseException as cleanup:
                error.add_note(f"Installed acceptance cleanup failed: {type(cleanup).__name__}")
            try:
                self.resources.close()
            except BaseException as cleanup:
                error.add_note(f"Installed acceptance resource cleanup failed: {type(cleanup).__name__}")
            raise

    @override
    def __exit__(self, *exc: object) -> None:
        """Retain an existing acceptance failure when native cleanup also fails."""
        started = time.monotonic()
        error = exc[1] if len(exc) > 1 else None
        primary = error if isinstance(error, BaseException) else None
        try:
            self.stop_manager()
        except BaseException as cleanup:
            if primary is None:
                primary = cleanup
            else:
                primary.add_note(f"Installed acceptance cleanup failed: {type(cleanup).__name__}")
        try:
            self.resources.close()
        except BaseException as cleanup:
            if primary is None:
                primary = cleanup
            else:
                primary.add_note(f"Installed acceptance resource cleanup failed: {type(cleanup).__name__}")
        self.metrics["cleanup_seconds"] = time.monotonic() - started
        if primary is not None and primary is not error:
            raise primary

    def verify_registration(self, *, absent: bool = False) -> None:
        """Observe the real scoped registration resources and configured SCM owner."""
        if sys.platform != "win32":
            raise ValueError("Native registration verification requires Windows")
        import winreg

        import win32service

        hive = winreg.HKEY_CURRENT_USER if self.intent["scope"] == "user" else winreg.HKEY_LOCAL_MACHINE
        for entry in self.registration["registry"]:
            try:
                with winreg.OpenKey(hive, entry["key"], 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                    value, kind = winreg.QueryValueEx(key, entry["name"])
            except FileNotFoundError:
                if absent:
                    continue
                raise
            if absent:
                raise AssertionError("Unregistered native resource remains present")
            expected = entry["value"].replace("[INSTALL_ROOT]", str(self.prefix) + "\\")
            expected_kind = winreg.REG_DWORD if entry["type"] == "integer" else winreg.REG_SZ
            if value != (int(expected) if expected_kind == winreg.REG_DWORD else expected) or kind != expected_kind:
                raise AssertionError("Native registration differs from its immutable MSI description")
        for service in self.registration["services"]:
            with self.service(service, absent=absent) as handle:
                if not absent and win32service.QueryServiceStatus(handle)[1] != win32service.SERVICE_RUNNING:
                    raise AssertionError("Installed SCM broker is configured but not running")

    def service(self, expected: dict[str, Any], *, absent: bool = False, controls: bool = True) -> Any:
        """Retain a configured service handle before any acceptance control."""
        from contextlib import contextmanager

        import pywintypes
        import win32service

        @contextmanager
        def retained() -> Any:
            scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
            with ExitStack() as resources:
                resources.callback(win32service.CloseServiceHandle, scm)
                try:
                    access = win32service.SERVICE_QUERY_CONFIG | win32service.SERVICE_QUERY_STATUS
                    if not absent and controls:
                        access |= win32service.SERVICE_START | win32service.SERVICE_STOP
                    handle = win32service.OpenService(scm, expected["name"], access)
                except pywintypes.error as error:
                    if absent and error.winerror == 1060:
                        yield None
                        return
                    raise
                resources.callback(win32service.CloseServiceHandle, handle)
                if absent:
                    raise AssertionError("Unregistered SCM service remains present")
                config = win32service.QueryServiceConfig(handle)
                image = expected["binary"].replace("[INSTALL_ROOT]", str(self.prefix) + "\\")
                if (config[0], config[1], config[3], config[7]) != (
                    win32service.SERVICE_WIN32_OWN_PROCESS,
                    win32service.SERVICE_AUTO_START,
                    f'"{image}" {expected["arguments"]}',
                    expected["account"],
                ):
                    raise AssertionError("SCM configuration differs from its immutable native owner")
                yield handle

        return retained()

    def verify_stopped_service(self) -> None:
        """Observe the exact machine broker without requesting service control rights."""
        import win32service

        if self.intent["scope"] != "machine" or len(self.registration["services"]) != 1:
            raise ValueError("Stopped broker observation requires the installed machine owner")
        with self.service(self.registration["services"][0], controls=False) as handle:
            if win32service.QueryServiceStatus(handle)[1] != win32service.SERVICE_STOPPED:
                raise AssertionError("Least-privilege Cadrumo proof requires the actual broker stopped")

    def control_service(self, *, start: bool) -> None:
        """Control only the admitted machine broker, with bounded native status observation."""
        import win32service

        if self.intent["scope"] != "machine" or len(self.registration["services"]) != 1:
            raise ValueError("SCM controls require the installed machine broker")
        with self.service(self.registration["services"][0]) as handle:
            target = win32service.SERVICE_RUNNING if start else win32service.SERVICE_STOPPED
            if win32service.QueryServiceStatus(handle)[1] != target:
                if start:
                    win32service.StartService(handle, None)
                else:
                    win32service.ControlService(handle, win32service.SERVICE_CONTROL_STOP)
            deadline = time.monotonic() + 90
            while win32service.QueryServiceStatus(handle)[1] != target:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Admitted SCM broker did not complete its requested transition")
                time.sleep(0.1)
        if not start and self.process.wait(timeout=35) != 0:
            raise AssertionError("Service stop did not gracefully stop its user manager")

    @override
    def start_manager(self, *, activate: bool = True, absent_ok: bool = False) -> None:
        """Activate the user installation, or attach the genuine machine broker's worker."""
        import pywintypes
        import win32api
        import win32con
        import win32event
        import win32process

        from cadrumo.adapters.local_runtime.windows_native_io import current_windows_owner_sid, windows_image_path

        owner = current_windows_owner_sid()
        current = require_interactive_token(int(win32api.GetCurrentProcess()), owner)
        if activate and self.intent["scope"] == "user":
            # The scheduler's Job forbids breakaway; use the GUI's existing
            # Explorer dispatcher, then independently verify the actual worker.
            dispatcher = self.plan.parent.parent / "metadata/native/manager_dispatch.py"
            result = run_command(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    dispatcher.read_text(encoding="utf-8"),
                    str(self.prefix / self.manager.name),
                ],
                cwd=self.prefix,
                environment=self.native_environment(),
                timeout_seconds=60,
            )
            try:
                reply = json.loads(result.stdout) if len(result.stdout) <= 4096 else None
            except json.JSONDecodeError:
                reply = None
            if (
                result.returncode != 0
                or not isinstance(reply, dict)
                or set(reply) != {"dispatched", "os_code"}
                or reply["dispatched"] is not True
                or reply["os_code"] is not None
            ):
                raise RuntimeError("Installed manager Explorer dispatch failed")
        deadline = time.monotonic() + 90
        while True:
            for pid in win32process.EnumProcesses():
                try:
                    handle = owned_windows_handle(
                        win32api.OpenProcess(
                            win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE, False, pid
                        )
                    )
                except (OSError, pywintypes.error):
                    continue
                try:
                    if (
                        windows_image_path(handle) != self.manager.resolve()
                        or win32event.WaitForSingleObject(int(handle), 0) != win32event.WAIT_TIMEOUT
                    ):
                        continue
                    context = require_interactive_token(int(handle), owner)
                    if context.session_id != current.session_id:
                        continue
                    if self.intent["scope"] == "user" and context.authentication_id != current.authentication_id:
                        continue
                    if self.intent["scope"] == "machine" and not self.worker_of_broker(pid, int(handle)):
                        continue
                    self.manager_handle = handle
                    self.process = WindowsOwnedProcess(handle=int(handle), pid=pid)
                    self._manager_crashed = False
                    self.resources.callback(handle.Close)
                    return
                except (OSError, pywintypes.error, RuntimeRefusalError, ValueError):
                    continue
                finally:
                    if handle is not self.manager_handle:
                        handle.Close()
            if absent_ok:
                return
            if time.monotonic() >= deadline:
                raise TimeoutError("No kernel-verified installed same-logon manager appeared")
            time.sleep(0.1)

    def worker_of_broker(self, pid: int, worker_handle: int) -> bool:
        """Verify the worker parent is the exact live installed LocalSystem SCM broker."""
        import win32api
        import win32com.client
        import win32con
        import win32event
        import win32job
        import win32process
        import win32security
        import win32service

        from cadrumo.adapters.local_runtime.windows_native_io import current_windows_owner_sid, windows_image_path

        with self.service(self.registration["services"][0]) as service:
            status = cast(dict[str, int], win32service.QueryServiceStatusEx(service))
            if status["CurrentState"] != win32service.SERVICE_RUNNING:
                return False
            broker_pid = status["ProcessId"]
            broker = owned_windows_handle(
                win32api.OpenProcess(
                    win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE, False, broker_pid
                )
            )
            try:
                parent = win32com.client.GetObject("winmgmts:").Get('Win32_Process.Handle="' + str(pid) + '"')
                if windows_image_path(broker) != (self.prefix / self.manager.name).resolve():
                    return False
                if parent.ParentProcessId != broker_pid:
                    # A genuine cutover successor inherits the broker's SYSTEM-owned
                    # job; its immediate parent is the prior same-logon worker.
                    owner = current_windows_owner_sid()
                    observed = require_interactive_token(worker_handle, owner)
                    service_name = self.registration["services"][0]["name"]
                    name = f"Global\\{service_name}.service.{owner}.{observed.authentication_id:016x}.job"
                    job = owned_windows_handle(win32job.OpenJobObject(win32job.JOB_OBJECT_QUERY | 0x20000, False, name))
                    try:
                        descriptor = win32security.GetSecurityInfo(
                            int(job), win32security.SE_KERNEL_OBJECT, win32security.OWNER_SECURITY_INFORMATION
                        )
                        if win32security.ConvertSidToStringSid(
                            descriptor.GetSecurityDescriptorOwner()
                        ) != "S-1-5-18" or not win32job.IsProcessInJob(worker_handle, int(job)):
                            return False
                    finally:
                        job.Close()
                token = win32security.OpenProcessToken(int(broker), win32security.TOKEN_QUERY)
                try:
                    sid, _ = win32security.GetTokenInformation(token, win32security.TokenUser)
                    if win32security.ConvertSidToStringSid(sid) != "S-1-5-18":
                        return False
                finally:
                    win32api.CloseHandle(token)
                return bool(
                    win32event.WaitForSingleObject(int(broker), 0) == win32event.WAIT_TIMEOUT
                    and win32process.GetProcessTimes(int(broker))["CreationTime"]
                    <= win32process.GetProcessTimes(worker_handle)["CreationTime"]
                    and cast(dict[str, int], win32service.QueryServiceStatusEx(service))["ProcessId"] == broker_pid
                )
            finally:
                broker.Close()

    @override
    def owns_runtime(
        self,
        connection: Connection,
        handle: int,
        *,
        parent: WindowsOwnedProcess | None = None,
        parent_handle: int | None = None,
    ) -> bool:
        """Require the exact live installed manager parent, without claiming its service job."""
        import win32com.client
        import win32process

        process = win32com.client.GetObject("winmgmts:").Get(
            'Win32_Process.Handle="' + str(connection.native.peer.process_id) + '"'
        )
        parent = parent or self.process
        parent_handle = parent_handle if parent_handle is not None else int(self.manager_handle)
        if process.ParentProcessId != parent.pid:
            return False
        manager_birth = win32process.GetProcessTimes(parent_handle)["CreationTime"]
        runtime_birth = win32process.GetProcessTimes(handle)["CreationTime"]
        try:
            parent.wait(timeout=0)
        except RuntimeRefusalError as error:
            return bool(error.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED and manager_birth <= runtime_birth)
        return False

    def lose_manager(self) -> None:
        """Stop the genuine broker, or terminate only the retained actual user worker."""
        if self.intent["scope"] == "machine":
            self.control_service(start=False)
            return
        import win32api
        import win32con
        import win32process

        from cadrumo.adapters.local_runtime.windows_native_io import current_windows_owner_sid, windows_image_path

        handle = owned_windows_handle(
            win32api.OpenProcess(
                win32con.PROCESS_TERMINATE | win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE,
                False,
                self.process.pid,
            )
        )
        try:
            owner = current_windows_owner_sid()
            if (
                windows_image_path(handle) != self.manager.resolve()
                or require_interactive_token(int(handle), owner)
                != require_interactive_token(int(self.manager_handle), owner)
                or win32process.GetProcessTimes(int(handle))["CreationTime"]
                != win32process.GetProcessTimes(int(self.manager_handle))["CreationTime"]
            ):
                raise ValueError("Manager termination target differs from the retained installed worker")
            try:
                self.process.wait(timeout=0)
            except RuntimeRefusalError as error:
                if error.reason != RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    raise
            else:
                raise ValueError("Installed manager exited before exact fault injection")
            win32process.TerminateProcess(int(handle), 73)
            if self.process.wait(timeout=10) != 73:
                raise ValueError("Installed user manager termination was not confirmed")
            self._manager_crashed = True
        finally:
            handle.Close()

    @override
    def stop_manager(self) -> None:
        """Unregister through the exact native owner, then prove installed processes stopped."""
        if getattr(self, "_held", False) or not self._installation_attempted or self._removed:
            return
        self.maintenance("unregister")
        self._removed = True
        self.verify_registration(absent=True)
        expected_exit = 73 if getattr(self, "_manager_crashed", False) else 0
        if self.manager_handle is not None and self.process.wait(timeout=90) != expected_exit:
            raise AssertionError("Unregister did not stop the installed manager")


def run_installed_acceptance(
    plan: Path, runner: Path, vm_id: UUID, account_sid: str, *, guest_kind: Literal["hyperv", "qemu"] = "hyperv"
) -> dict[str, Any]:
    """Execute the single immediate scenario after native guest/account admission."""
    from cadrumo.core.storage_environment import STORAGE_ROOT

    intent = json.loads(plan.read_text(encoding="utf-8"))
    root = require_installation_guest(vm_id, account_sid, intent["scope"], guest_kind=guest_kind)
    instance = InstalledLifecycleHarness(plan.resolve(strict=True), runner.resolve(strict=True), root)
    os.environ[STORAGE_ROOT.variable] = str(root)
    os.environ[STORAGE_ROOT.development_variable] = str(root)
    os.environ["CADRUMO_AUTHORITY_ROOT"] = str(instance.package / "data/authority")
    with instance:
        probe = instance.connect(uuid4())
        probe.client.close()
        from .client_probes import exercise_installed_manager

        exercise_installed_manager(instance)
    return {
        "schema": 1,
        "scope": intent["scope"],
        "vm_id": str(vm_id),
        "guest_kind": guest_kind,
        "immediate": "passed",
        "full_installation_acceptance": "incomplete",
        "pending": ["machine_boot", "user_login", "scope_coexistence", "upgrade_cutover_rollback"],
    }


def exact_msi_product_states(product: str, scope: str, account_sid: str) -> dict[int, int | None]:
    """Read exact native contexts; only ERROR_UNKNOWN_PRODUCT proves absence."""
    import ctypes
    from ctypes import wintypes

    if sys.platform != "win32":
        raise ValueError("Exact MSI observation requires Windows")
    if scope not in {"user", "machine"} or not account_sid.startswith("S-1-5-21-"):
        raise ValueError("MSI observation requires the admitted scope and account")
    code = "{" + str(UUID(product.strip("{}"))).upper() + "}"
    query = ctypes.WinDLL("msi.dll", winmode=0x00000800).MsiGetProductInfoExW
    query.argtypes = (
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    )
    query.restype = wintypes.UINT
    states: dict[int, int | None] = {}
    for context in (1, 2) if scope == "user" else (4,):
        buffer = ctypes.create_unicode_buffer(32)
        size = wintypes.DWORD(len(buffer))
        status = query(code, account_sid if scope == "user" else None, context, "State", buffer, ctypes.byref(size))
        if status == 1605:
            states[context] = None
        elif status == 0 and buffer.value in {str(value) for value in range(-7, 6)}:
            states[context] = int(buffer.value)
        else:
            raise ValueError(f"Exact MSI state observation refused: native_code={status}")
    return states


def _native_phase_facts(stderr: bytes | str | None) -> list[dict[str, Any]]:
    """Project bounded native bookends, never arbitrary stderr or coordinates."""
    if stderr is None:
        return []
    data = stderr.encode("utf-8") if isinstance(stderr, str) else stderr
    facts: list[dict[str, Any]] = []
    for line in data[-65536:].decode("utf-8", errors="replace").splitlines():
        try:
            fact = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if (
            not isinstance(fact, dict)
            or type(fact.get("schema")) is not int
            or fact.get("schema") != 1
            or fact.get("event") != "native_maintenance_phase"
        ):
            continue
        phase, transition, elapsed = fact.get("phase"), fact.get("transition"), fact.get("elapsedMs")
        if (
            isinstance(phase, str)
            and phase
            in {
                "version_install",
                "candidate_verification",
                "registration_install",
                "commit",
                "publication_admission",
                "product_verification",
                "registration_verification",
                "publication_hash",
            }
            and isinstance(transition, str)
            and transition in {"enter", "completed", "failed"}
            and type(elapsed) is int
            and 0 <= elapsed <= 2**64 - 1
        ):
            facts.append({"phase": phase, "transition": transition, "elapsedMs": elapsed})
    return facts[-32:]


def _precommit_receipt(document: dict[str, Any], returncode: int) -> dict[str, Any]:
    """Retain finite native failure fields, never arbitrary native output."""
    rejection = document.get("candidate_rejection")
    candidate = None
    if isinstance(rejection, dict):
        stage, kind = rejection.get("stage"), rejection.get("kind")
        if (
            isinstance(stage, str)
            and stage in {"release", "root", "manifest", "version_identity", "inventory", "manager"}
            and isinstance(kind, str)
            and kind
            in {
                "missing",
                "incompatible",
                "needs_user",
                "io_not_found",
                "io_permission_denied",
                "io_other",
                "json",
                "archive",
                "invalid",
                "integrity",
                "busy",
                "cancelled",
                "limit_exceeded",
                "download",
                "timed_out",
                "probe_failed",
            }
        ):
            candidate = {"stage": stage, "kind": kind}
            member = rejection.get("member_sha256")
            if (
                isinstance(member, str)
                and len(member) == 64
                and all(character in "0123456789abcdefABCDEF" for character in member)
            ):
                candidate["member_sha256"] = member
            elif "member_sha256" in rejection:
                candidate = None
    return {
        "schema": document.get("schema") if document.get("schema") == 1 else None,
        "returncode": returncode,
        "outcome": document.get("outcome")
        if document.get("outcome") in {"native_rolled_back", "native_unsettled", "rolled_back_publication_pending"}
        else "unexpected",
        "code": document.get("code")
        if document.get("code")
        in {"version_inventory_failed", "rollback_publication_fenced", "native_rollback_unsettled"}
        else "unexpected",
        "cause": "version_inventory_failed" if document.get("cause") == "version_inventory_failed" else None,
        "service_restore": "failed" if document.get("service_restore") else None,
        "candidate_rejection": candidate,
    }


def _require_precommit_rollback(receipt: dict[str, Any]) -> None:
    if receipt != {
        "schema": 1,
        "returncode": 1,
        "outcome": "native_rolled_back",
        "code": "version_inventory_failed",
        "cause": None,
        "service_restore": None,
        "candidate_rejection": {"stage": "inventory", "kind": "incompatible"},
    }:
        raise ValueError("Precommit rollback did not settle the authentic candidate rejection")


def _require_rollback_publication(instance: InstalledLifecycleHarness, receipt: dict[str, Any]) -> None:
    """Fresh rollback must remove its entire reservation and all release anchors."""
    state = instance.prefix / instance.intent["contract"]["layout"]["installation"]["publication"] / "state.json"
    document = json.loads(state.read_text(encoding="utf-8"))
    receipt["publication"] = {
        "schema_valid": document.get("schema") == 2,
        "fields_present": {"versions", "manager_anchor", "desktop_anchor", "registration"}.issubset(document),
        "versions_empty": document.get("versions") == {},
        "anchors_absent": document.get("manager_anchor") is None and document.get("desktop_anchor") is None,
        "registration_absent": document.get("registration") is None,
    }
    if (
        document.get("schema") != 2
        or not {"versions", "manager_anchor", "desktop_anchor", "registration"}.issubset(document)
        or document.get("versions") != {}
        or document.get("manager_anchor") is not None
        or document.get("desktop_anchor") is not None
        or document.get("registration") is not None
    ):
        raise ValueError("Precommit rollback retained publication ownership or a Pending reservation")


def run_precommit_rollback(
    plan: Path,
    runner: Path,
    evidence: Path,
    vm_id: UUID,
    account_sid: str,
    *,
    guest_kind: Literal["hyperv", "qemu"] = "hyperv",
) -> dict[str, Any]:
    """Reject a test-derived ABI before commit, then prove real native rollback."""
    plan, runner = plan.resolve(strict=True), runner.resolve(strict=True)
    intent = json.loads(plan.read_text(encoding="utf-8"))
    root = require_installation_guest(vm_id, account_sid, intent["scope"], guest_kind=guest_kind)
    instance = InstalledLifecycleHarness(plan, runner, root)
    instance.preflight()
    for role in ("version_product", "registration_product"):
        if any(
            value is not None
            for value in exact_msi_product_states(intent[role]["product_code"], intent["scope"], account_sid).values()
        ):
            raise ValueError("Precommit rollback refuses a preexisting exact native product")
    abi = intent["contract"]["layout"]["abi"]
    if type(abi) is not int or not 0 <= abi <= 0xFFFFFFFF:
        raise ValueError("Precommit rollback requires the canonical u32 ABI")
    negative = json.loads(json.dumps(intent))
    negative["contract"]["layout"]["abi"] = abi ^ 1
    negative_plan = plan.with_name(f"precommit-rollback-{uuid4().hex}.json")
    evidence = evidence.resolve()
    if evidence.is_relative_to(instance.prefix.resolve()) or evidence.is_relative_to(root.resolve()):
        raise ValueError("Rollback evidence must remain outside the tested installation and native storage")
    evidence.parent.mkdir(parents=True, exist_ok=True)
    receipt: dict[str, Any] = {
        "schema": 1,
        "scope": intent["scope"],
        "vm_id": str(vm_id),
        "precommit_rollback": "failed",
        "full_installation_acceptance": "incomplete",
    }
    # Exclusive creation refuses foreign/prior evidence before any native mutation.
    with evidence.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, sort_keys=True)
    with negative_plan.open("x", encoding="utf-8") as stream:
        json.dump(negative, stream, sort_keys=True)
    try:
        try:
            result = run_command(
                [str(runner), "install", "--plan", str(negative_plan)],
                cwd=plan.parent,
                environment=instance.native_environment(),
                timeout_seconds=900,
            )
        except subprocess.TimeoutExpired as error:
            receipt["phases"] = _native_phase_facts(error.stderr)
            instance.retain_native_timeout(error, "install")
            raise
        receipt["native"] = _precommit_receipt(json.loads(result.stdout), result.returncode)
        receipt["phases"] = _native_phase_facts(result.stderr)
        # Retain the native result before any postcondition can reject settlement.
        evidence.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
        failure: BaseException | None = None
        receipt.update(
            products={"version_product": None, "registration_product": None},
            candidate_present=None,
            publication=None,
            registration_absent=None,
        )
        for observation in (
            "native",
            "version_product",
            "registration_product",
            "candidate",
            "publication",
            "registration",
        ):
            try:
                if observation == "native":
                    _require_precommit_rollback(receipt["native"])
                elif observation in ("version_product", "registration_product"):
                    states = exact_msi_product_states(intent[observation]["product_code"], intent["scope"], account_sid)
                    receipt["products"][observation] = states
                    if any(value is not None for value in states.values()):
                        raise ValueError("Precommit rollback retained an exact native MSI product")
                elif observation == "candidate":
                    receipt["candidate_present"] = instance.package.exists()
                    if receipt["candidate_present"]:
                        raise ValueError("Precommit rollback retained candidate version files")
                elif observation == "publication":
                    _require_rollback_publication(instance, receipt)
                else:
                    instance.verify_registration(absent=True)
                    receipt["registration_absent"] = True
            except Exception as error:
                receipt.setdefault("observation_errors", {})[observation] = type(error).__name__
                if failure is None:
                    failure = error
                else:
                    failure.add_note(f"Rollback {observation} check failed: {type(error).__name__}")
        if failure is not None:
            raise failure
        receipt["precommit_rollback"] = "passed"
        return receipt
    finally:
        existing_failure = sys.exception()
        primary_failure = existing_failure
        try:
            instance.resources.close()
        except BaseException as cleanup:
            receipt["precommit_rollback"] = "failed"
            if primary_failure is None:
                primary_failure = cleanup
            else:
                primary_failure.add_note(f"Rollback resource cleanup failed: {type(cleanup).__name__}")
        try:
            evidence.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
        except BaseException as retention:
            if primary_failure is None:
                primary_failure = retention
            else:
                primary_failure.add_note(f"Rollback evidence retention failed: {type(retention).__name__}")
        if primary_failure is not None and primary_failure is not existing_failure:
            raise primary_failure


def main() -> None:
    """Run with shipping CPython and transferred test-owner modules, without pytest."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--installed-vm-id", type=UUID, required=True)
    parser.add_argument("--installed-account-sid", required=True)
    parser.add_argument("--installed-guest-kind", choices=("hyperv", "qemu"), default="hyperv")
    parser.add_argument(
        "--phase",
        choices=(
            "immediate",
            "precommit-rollback",
            "hold",
            "boot",
            "login",
            "scope-conflict",
            "scope-verify",
            "gui-stop",
            "gui-user",
            "gui-restore",
            "upgrade-rollback",
            "machine-upgrade",
            "upgrade-verify",
            "cleanup",
        ),
        default="immediate",
    )
    parser.add_argument("--campaign-state", type=Path)
    parser.add_argument("--conflicting-plan", type=Path)
    parser.add_argument("--successor-plan", type=Path)
    parser.add_argument("--successor-runner", type=Path)
    args = parser.parse_args()
    if args.phase == "immediate":
        receipt = run_installed_acceptance(
            args.plan,
            args.runner,
            args.installed_vm_id,
            args.installed_account_sid,
            guest_kind=args.installed_guest_kind,
        )
    elif args.phase == "precommit-rollback":
        if args.campaign_state is None:
            parser.error("Precommit rollback requires a fresh --campaign-state evidence file")
        receipt = run_precommit_rollback(
            args.plan,
            args.runner,
            args.campaign_state,
            args.installed_vm_id,
            args.installed_account_sid,
            guest_kind=args.installed_guest_kind,
        )
    else:
        from .client_probes import installed_campaign

        if args.campaign_state is None:
            parser.error("Held installation phases require --campaign-state")
        receipt = installed_campaign(
            args.phase,
            args.campaign_state,
            args.plan,
            args.runner,
            args.installed_vm_id,
            args.installed_account_sid,
            guest_kind=args.installed_guest_kind,
            conflicting_plan=args.conflicting_plan,
            successor_plan=args.successor_plan,
            successor_runner=args.successor_runner,
        )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
