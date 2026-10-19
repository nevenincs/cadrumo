"""Exercise the shipped hidden login owner without completing a person's OAuth flow."""

from __future__ import annotations

import argparse
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


def verify(package: Path, provider_bin: Path | None, *, installed: bool = False) -> None:
    """Use package imports and its admitted helper; optionally initiate real login then cancel."""
    package = package.resolve(strict=True)
    if not Path(sys.executable).resolve().is_relative_to(package):
        raise AssertionError("package_interpreter_required")
    import cadrumo_agent_service.host.auth_attempt as owner

    if not Path(owner.__file__).resolve().is_relative_to(package):
        raise AssertionError("package_imports_required")
    manifest = json.loads((package / "data/package-manifest.json").read_text(encoding="utf-8"))
    image = package / manifest["layout"]["paths"]["native"] / "cadrumo-agent.exe"
    with tempfile.TemporaryDirectory(prefix="cadrumo-auth-status-") as directory:
        environment = system_environment(os.environ)
        environment[HOSTED_ROOT_VARIABLE] = directory
        observed = WindowsAgentInvocationRunner().run(
            executable=image,
            arguments=("-m", "cadrumo_agent.cli.main", "auth", "status", "--json"),
            directory=Path(directory),
            environment=environment,
            timeout=10,
            output_limit=4096,
        )
        if observed.status != 0:
            raise AssertionError("packaged_provider_status_command_failed")
        status = json.loads(observed.standard_output)
        if status.get("schema_version") != 1 or not isinstance(status.get("providers"), dict):
            raise AssertionError("packaged_provider_status_shape_invalid")
        if not {"codex", "claude"} <= status["providers"].keys():
            raise AssertionError("packaged_provider_status_missing")
        if any(value == "installed_signed_in" for value in status["providers"].values()):
            raise AssertionError("fresh_provider_home_inherited_sign_in")
        sys.stdout.write("profile-bound provider status command completed\n")
    real_login = installed or provider_bin is not None
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
                    if event == "browser_action" and not saw_action:
                        if not isinstance(answer.get("url"), str):
                            raise AssertionError("browser_action_missing")
                        saw_action = True
                        if ending == "cancel":
                            attempt.cancel()
                        elif ending == "revoke":
                            live.clear()
                        else:
                            time.sleep(16)
                    if not attempt.active:
                        answer = attempt.observe()
                        event = str(answer["event"])
                        events.add(event)
                        if "url" in answer or "user_code" in answer:
                            raise AssertionError("terminal_browser_data_retained")
                        if not real_login:
                            if event != "failed" or answer.get("reason") != "provider_unavailable":
                                raise AssertionError(
                                    f"missing_provider_not_reported event={event} reason={answer.get('reason', 'none')}"
                                )
                        elif not saw_action or event != "cancelled":
                            reason = answer.get("reason", "none")
                            raise AssertionError(
                                f"real_login_not_cancelled provider={provider} event={event} reason={reason}"
                            )
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
    parser.add_argument(
        "--installed",
        action="store_true",
        help="Use normal installed CLI discovery and initiate real logins, then cancel.",
    )
    options = parser.parse_args()
    verify(options.package, options.provider_bin, installed=options.installed)
