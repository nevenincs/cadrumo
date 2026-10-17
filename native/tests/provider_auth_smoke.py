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

from cadrumo_agent_service.host.auth_attempt import AuthAttempt
from cadrumo_agent_service.host.launch_environment import (
    EXTERNAL_BIN_DIRECTORIES_VARIABLE,
    HOSTED_ROOT_VARIABLE,
    system_environment,
)


def verify(package: Path, provider_bin: Path | None) -> None:
    """Use package imports and its admitted helper; optionally initiate real login then cancel."""
    package = package.resolve(strict=True)
    if not Path(sys.executable).resolve().is_relative_to(package):
        raise AssertionError("package_interpreter_required")
    import cadrumo_agent_service.host.auth_attempt as owner

    if not Path(owner.__file__).resolve().is_relative_to(package):
        raise AssertionError("package_imports_required")
    manifest = json.loads((package / "data/package-manifest.json").read_text(encoding="utf-8"))
    image = package / manifest["layout"]["paths"]["native"] / "cadrumo-agent.exe"
    routes = [("browser", "cancel"), ("device", "revoke")]
    if provider_bin is not None:
        routes.append(("browser", "unobserved"))
    for method, ending in routes:
        with tempfile.TemporaryDirectory(prefix="cadrumo-auth-probe-") as directory:
            environment = system_environment(os.environ)
            environment[HOSTED_ROOT_VARIABLE] = directory
            if provider_bin is not None:
                environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE] = str(provider_bin.resolve(strict=True))
            live = Event()
            live.set()
            attempt = AuthAttempt(
                provider="codex",
                lane="codex_cli",
                executable=image,
                arguments=(
                    "-m",
                    "cadrumo_agent.cli.main",
                    "auth",
                    "connect",
                    "--provider",
                    "codex",
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
                        if provider_bin is None:
                            if event != "failed" or answer.get("reason") != "provider_unavailable":
                                raise AssertionError("missing_provider_not_reported")
                        elif not saw_action or event != "cancelled":
                            raise AssertionError("real_login_not_cancelled")
                        break
                    time.sleep(0.1)
                else:
                    raise AssertionError("auth_probe_deadline")
            finally:
                attempt.close()
            sys.stdout.write(f"{method}/{ending}: {','.join(sorted(events))}; cleanup confirmed\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--provider-bin", type=Path)
    options = parser.parse_args()
    verify(options.package, options.provider_bin)
