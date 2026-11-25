"""Exercise the shipped hidden login owner without completing a person's OAuth flow."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from threading import Event

from cadrumo.core.storage_environment import STORAGE_ROOT
from cadrumo_agent_service.adapters.agent_process import WindowsAgentInvocationRunner
from cadrumo_agent_service.host.auth_attempt import AuthAttempt
from cadrumo_agent_service.host.launch_environment import (
    AUTH_BROWSER_EXECUTABLE_VARIABLE,
    EXTERNAL_BIN_DIRECTORIES_VARIABLE,
    HOSTED_ROOT_VARIABLE,
    auth_browser_executable,
    system_environment,
)


def verify(package: Path, provider_bin: Path | None, *, installed: bool = False, provider: str | None = None) -> None:
    """Use package imports and its admitted helper; optionally initiate real login then cancel."""
    package = package.resolve(strict=True)
    if not Path(sys.executable).resolve().is_relative_to(package):
        raise AssertionError("package_interpreter_required")
    import cadrumo_agent_service.host.auth_attempt as owner

    manifest_bytes = (package / "data/package-manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    image = package / manifest["layout"]["paths"]["native"] / "cadrumo-agent.exe"
    packages = (package / manifest["layout"]["paths"]["packages"]).resolve()
    if not packages.is_relative_to(package) or owner.__file__ is None:
        raise AssertionError("package_imports_required")
    if not Path(owner.__file__).resolve().is_relative_to(packages):
        raise AssertionError("package_imports_required")
    agent = importlib.import_module("cadrumo_agent.cli.main")
    if agent.__file__ is None or not Path(agent.__file__).resolve().is_relative_to(packages):
        raise AssertionError("package_agent_import_required")
    distribution = importlib.metadata.distribution("cadrumo-agent")
    if (
        not manifest["agent"]["bundled"]
        or distribution.version != manifest["agent"]["version"]
        or Path(str(distribution.locate_file(""))).resolve() != packages
    ):
        raise AssertionError("package_agent_identity_mismatch")
    for executable in (image, Path(sys.executable).resolve()):
        if not executable.resolve().is_relative_to(package):
            raise AssertionError("package_executable_escaped")
        member = executable.relative_to(package).as_posix()
        if hashlib.sha256(executable.read_bytes()).hexdigest() != manifest["files"].get(member):
            raise AssertionError("package_executable_mismatch")
    package_member = packages.relative_to(package).as_posix()
    for prefix in (f"{package_member}/cadrumo_agent/", f"{package_member}/cadrumo_agent_service/"):
        members = [member for member in manifest["files"] if member.startswith(prefix)]
        if not members:
            raise AssertionError("package_import_inventory_missing")
        for member in members:
            path = package / member
            if not path.resolve().is_relative_to(packages):
                raise AssertionError("package_import_escaped")
            if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["files"][member]:
                raise AssertionError("package_import_checksum_mismatch")
    sys.stdout.write(f"package manifest sha256={hashlib.sha256(manifest_bytes).hexdigest()}\n")
    if provider == "antigravity" and not (installed or provider_bin is not None):
        raise ValueError("antigravity_probe_requires_installed_provider")

    for _ in range(2 if provider == "antigravity" else 1):
        with tempfile.TemporaryDirectory(prefix="cadrumo-auth-status-") as directory:
            environment = system_environment(os.environ)
            environment[HOSTED_ROOT_VARIABLE] = directory
            if provider_bin is not None:
                environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE] = str(provider_bin.resolve(strict=True))
            if provider == "antigravity":
                executable = Path(sys.executable)
                arguments = (
                    "-c",
                    "import sys; from pathlib import Path; "
                    "from cadrumo_agent.providers.login_status import probe_login; "
                    "print(probe_login('antigravity', Path(sys.argv[1])).value)",
                    directory,
                )
            else:
                executable = image
                arguments = ("-m", "cadrumo_agent.cli.main", "auth", "status", "--json")
            observed = WindowsAgentInvocationRunner().run(
                executable=executable,
                arguments=arguments,
                directory=Path(directory),
                environment=environment,
                timeout=15,
                output_limit=4096,
            )
            if observed.status != 0:
                raise AssertionError("packaged_provider_status_command_failed")
            if provider == "antigravity":
                if observed.standard_output.strip() != b"installed_signed_out":
                    raise AssertionError("fresh_antigravity_status_not_signed_out")
            else:
                status = json.loads(observed.standard_output)
                if status.get("schema_version") != 1 or not isinstance(status.get("providers"), dict):
                    raise AssertionError("packaged_provider_status_shape_invalid")
                if not {"codex", "claude"} <= status["providers"].keys():
                    raise AssertionError("packaged_provider_status_missing")
                if any(value == "installed_signed_in" for value in status["providers"].values()):
                    raise AssertionError("fresh_provider_home_inherited_sign_in")
            sys.stdout.write("profile-bound provider status command completed\n")

    real_login = installed or provider_bin is not None
    if provider == "antigravity":
        with tempfile.TemporaryDirectory(prefix="cadrumo-auth-catalog-") as directory:
            observed = WindowsAgentInvocationRunner().run(
                executable=image,
                arguments=("-m", "cadrumo_agent.cli.main", "auth", "providers", "--interface", "gui", "--json"),
                directory=Path(directory),
                environment=system_environment(os.environ),
                timeout=10,
                output_limit=4096,
            )
            if observed.status != 0:
                raise AssertionError("packaged_gui_catalog_command_failed")
            catalog = json.loads(observed.standard_output)
            methods = catalog.get("providers")
            if catalog.get("schema_version") != 3 or not isinstance(methods, dict):
                raise AssertionError("packaged_gui_catalog_shape_invalid")
            if methods.get("antigravity") != ["browser-code"] or methods.get("claude") != ["browser"]:
                raise AssertionError("packaged_gui_catalog_methods_invalid")
            if methods.get("codex") != ["browser", "device"]:
                raise AssertionError("packaged_gui_catalog_methods_invalid")
            method = methods[provider][0]
            sys.stdout.write("packaged GUI capability schema 3 confirmed\n")
        routes = [(provider, method, ending) for ending in ("cancel", "revoke", "unobserved", "submit")]
    else:
        routes = [("codex", "browser", "cancel"), ("codex", "device", "revoke")]
        if real_login:
            routes.append(("codex", "browser", "unobserved"))
        if installed:
            routes.extend(("claude", "browser", ending) for ending in ("cancel", "revoke", "unobserved"))
    for provider, method, ending in routes:
        with tempfile.TemporaryDirectory(prefix="cadrumo-auth-probe-") as directory:
            environment = system_environment(os.environ)
            environment[HOSTED_ROOT_VARIABLE] = directory
            if not real_login:
                # Keep this offline missing-installation test independent of
                # conventional user CLI folders on the package test machine.
                environment["USERPROFILE"] = directory
                environment["APPDATA"] = directory
                environment["HOME"] = directory
                environment[STORAGE_ROOT.variable] = directory
            browser = auth_browser_executable(Path(sys.executable))
            if browser is not None:
                environment[AUTH_BROWSER_EXECUTABLE_VARIABLE] = str(browser)
            if provider_bin is not None:
                environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE] = str(provider_bin.resolve(strict=True))
            live = Event()
            live.set()
            attempt = AuthAttempt(
                provider=provider,
                lane=f"{provider}_cli",
                executable=image,
                arguments=(
                    "-m",
                    "cadrumo_agent.cli.main",
                    "auth",
                    "connect",
                    "--provider",
                    provider,
                    "--method",
                    method,
                    "--timeout",
                    "300",
                ),
                directory=Path(directory),
                environment=environment,
                valid=live.is_set,
            )
            events: set[str] = set()
            deadline = time.monotonic() + 45
            saw_action = False
            try:
                while time.monotonic() < deadline:
                    answer = attempt.observe()
                    event = str(answer["event"])
                    events.add(event)
                    expected_action = "authorization_code_required" if provider == "antigravity" else "browser_action"
                    if event == expected_action and not saw_action:
                        if not isinstance(answer.get("url"), str):
                            raise AssertionError("browser_action_missing")
                        if provider == "antigravity" and "user_code" in answer:
                            raise AssertionError("authorization_code_confused_with_device_code")
                        saw_action = True
                        if ending == "cancel":
                            attempt.cancel()
                        elif ending == "revoke":
                            live.clear()
                        elif ending == "unobserved":
                            time.sleep(16)
                        else:
                            code = bytearray(b"cadrumo-smoke-invalid-code")
                            try:
                                submitted = attempt.submit_code(code)
                                if (
                                    submitted.get("event") != "started"
                                    or code.decode("ascii") in json.dumps(submitted)
                                    or "url" in submitted
                                ):
                                    raise AssertionError("submitted_code_or_url_retained")
                            finally:
                                code[:] = b"\x00" * len(code)
                            attempt.cancel()
                    if not attempt.active:
                        answer = attempt.observe()
                        event = str(answer["event"])
                        events.add(event)
                        if "url" in answer or "user_code" in answer:
                            raise AssertionError("terminal_browser_data_retained")
                        if ending == "submit" and "cadrumo-smoke-invalid-code" in json.dumps(answer):
                            raise AssertionError("terminal_code_retained")
                        if not real_login:
                            if event != "failed" or answer.get("reason") != "provider_unavailable":
                                raise AssertionError(
                                    f"missing_provider_not_reported event={event} reason={answer.get('reason', 'none')}"
                                )
                        elif not saw_action or not (
                            event == "cancelled"
                            or (ending == "submit" and event == "failed" and answer.get("reason") == "provider_error")
                        ):
                            reason = answer.get("reason", "none")
                            raise AssertionError(
                                f"real_login_not_cancelled provider={provider} event={event} reason={reason}"
                            )
                        if (
                            provider == "antigravity"
                            and ending == "unobserved"
                            and answer.get("reason") != ("host_disconnected")
                        ):
                            raise AssertionError("host_watchdog_not_reported")
                        break
                    time.sleep(0.1)
                else:
                    raise AssertionError("auth_probe_deadline")
            finally:
                attempt.close()
            sys.stdout.write(f"{provider}/{method}/{ending}: {','.join(sorted(events))}; cleanup confirmed\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--provider-bin", type=Path)
    parser.add_argument("--provider", choices=("antigravity",))
    parser.add_argument(
        "--installed",
        action="store_true",
        help="Use normal installed CLI discovery and initiate real logins, then cancel.",
    )
    options = parser.parse_args()
    verify(options.package, options.provider_bin, installed=options.installed, provider=options.provider)
