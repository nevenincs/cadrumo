"""Automated real-client capture for the Claude Desktop distribution rows.

Supersedes the manual in-app capture previously accepted for the
``claude-desktop-mcpb`` / ``claude-desktop-plugin`` rows: this is a
reproducible harness that provisions a clean isolated Claude Desktop profile
(seeded only with the operator's session auth), launches the real app as the
debug-enabled primary instance, drives it over CDP to make a real cadrumo MCP
tool call, verifies that call from Desktop's own MCP server telemetry, and mints
the sanctioned real-client evidence row.

Claude Desktop is a Windows MSIX / Store FullTrust Electron app, so this command
MUST run from a NON-ELEVATED INTERACTIVE session (an elevated Session-0 caller
cannot activate a Store app), and it must be the only Claude Desktop instance
launching (single-instance forwarding drops the debug-port flag otherwise). Both
constraints are checked and refused instructively. See
:mod:`dev.packaging.desktop_capture` for the primitives and the empirical model.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Final

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if not __package__:
    __package__ = "dev.packaging"

from cadrumo.core.directory_scan import iter_directory   # noqa: E402

from . import desktop_capture as dc  # noqa: E402
from ._acquire_common import capture_owned_server_launch  # noqa: E402
from .cohort_manifest import load_release_cohort  # noqa: E402
from .distribution_evidence_emit import emit_client_evidence  # noqa: E402
from .evidence import AcquisitionIdentity, ClientIdentity, DestinationIdentity  # noqa: E402
from .installed_mcp_oracle import isolated_mcp_environment, run_installed_mcp_oracle  # noqa: E402

_UTF_8: Final[str] = "utf-8"
_MCP_LOG_GLOB: Final[str] = "logs/mcp-server-*adrumo*.log"
# A deterministic single-tool prompt (the smoke_plugin_install shape): the model
# only needs to prove the real client reaches the cohort server, so it calls one
# read-only cadrumo tool once. The rigorous 23000.00 tax proof rides in the
# separately-owned protocol oracle, not this reply.
_CANONICAL_PROMPT: Final[str] = (
    "Call the Cadrumo MCP tool cadrumo_whoami exactly once. "
    "Do not use any other tool. Then reply with only the word connected."
)


def _resolve_extension_launch(extension_dir: Path) -> tuple[Path, tuple[str, ...], dict[str, str]]:
    """Resolve the installed MCPB's uv launch command, args, and environment.

    Reads the extension ``manifest.json`` server block and substitutes the two
    sanctioned MCPB placeholders (``${__dirname}`` and ``${user_config.*}``)
    exactly as Claude Desktop does, pointing user config at test-isolated values.
    """
    manifest = json.loads((extension_dir / "manifest.json").read_text(encoding=_UTF_8))
    config = manifest["server"]["mcp_config"]
    command = config["command"]
    resolved_command = shutil.which(command)
    if resolved_command is None:
        raise dc.DesktopCaptureError(f"MCPB launcher {command!r} is not on PATH")
    user_config = {"persona": "", "surface": "core", "storage_root": ""}

    def _sub(value: str) -> str:
        value = value.replace("${__dirname}", str(extension_dir))
        for name, configured in user_config.items():
            value = value.replace(f"${{user_config.{name}}}", configured)
        return value

    args = tuple(_sub(str(item)) for item in config["args"])
    environment = {key: _sub(str(value)) for key, value in config.get("env", {}).items()}
    environment.pop("CADRUMO_LOCAL_STORAGE_ROOT", None)  # the oracle supplies an isolated storage root
    return Path(resolved_command).resolve(strict=True), args, environment


def _perform_attempt(
    *,
    cdp_endpoint: str,
    isolated_profile: Path,
    baseline_calls: int,
) -> Callable[[int], dc.AttemptLog]:
    """Build the one-attempt callable: send the prompt, confirm a new real tool call."""

    def _perform(index: int) -> dc.AttemptLog:
        reply = dc.drive_tax_prompt(cdp_endpoint, _CANONICAL_PROMPT)
        time.sleep(3.0)  # let Desktop flush the MCP server telemetry line
        observation = _read_mcp_log(isolated_profile)
        # The gate is a NEW SUCCESSFUL call: really served (genuine transport)
        # AND its result carried no error marker — a dispatched-but-errored tool
        # call must never mint a passing capture.
        new_success = len(observation.successful_calls) > baseline_calls
        return dc.AttemptLog(
            attempt=index,
            ok=observation.connected and new_success,
            detail=(
                f"connected={observation.connected} calls={len(observation.calls)} "
                f"successful={len(observation.successful_calls)} (baseline {baseline_calls})"
            ),
            reply_excerpt=reply[:2000],
        )

    return _perform


def _read_mcp_log(profile: Path) -> dc.McpLogObservation:
    """Parse the cadrumo MCP server console log from an isolated Desktop profile."""
    matches = sorted(profile.glob(_MCP_LOG_GLOB))
    if not matches:
        return dc.McpLogObservation(connected=False, calls=())
    text = "\n".join(path.read_text(encoding=_UTF_8, errors="replace") for path in matches)
    return dc.parse_mcp_server_log(text)


def main(argv: list[str] | None = None) -> int:
    """Provision, launch, drive, verify, and emit one Desktop real-client row."""
    args = _parser().parse_args(argv)
    run_root = args.evidence_dir.resolve() / f"run-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    logs = run_root / "logs"
    logs.mkdir(parents=True)
    profile = run_root / "isolated-user-data"
    cohort = load_release_cohort(args.release_cohort_dir)

    package = dc.discover_desktop_package(state_dir=args.source_profile.resolve())
    extension_dir = (args.source_profile / "Claude Extensions" / args.extension_id).resolve(strict=True)
    settings_path = args.source_profile / "Claude Extensions Settings" / f"{args.extension_id}.json"
    uv, server_args, server_env = _resolve_extension_launch(extension_dir)

    # 1. Owned protocol oracle: the exact installed cohort server computes the
    #    grounded target — the rigorous tax proof, independent of the in-app model.
    protocol_oracle = run_installed_mcp_oracle(
        uv,
        server_args=server_args,
        environment_overrides=server_env,
        storage_root=run_root / "oracle-storage",
        work_dir=run_root / "oracle-work",
        cohort_source_commit=cohort.manifest.source.commit,
        cohort_manifest_sha256=next(
            item.sha256 for item in cohort.manifest.artifacts if item.name == "python-cohort-manifest"
        ),
        cohort_root_wheel_sha256=next(
            item.sha256 for item in cohort.manifest.artifacts if item.name == "cadrumo-wheel"
        ),
        cohort_harness_wheel_sha256=next(
            item.sha256 for item in cohort.manifest.artifacts if item.name == "cadrumo-harness-wheel"
        ),
        timeout_seconds=args.timeout_seconds,
    )
    (run_root / "protocol-oracle.json").write_text(
        json.dumps(protocol_oracle.to_jsonable(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )

    # 2. Clean isolated profile: session auth seeded, one extension provisioned.
    #    The extension user-config is REWRITTEN with an isolated per-run platform
    #    root — the Desktop-launched server must never write the operator's real
    #    storage (and a default-root launch would hit the retired-aeat-state
    #    refusal on a host carrying retired state).
    seeded = dc.seed_auth_state(args.source_profile.resolve(), profile)
    source_settings = json.loads(settings_path.read_text(encoding=_UTF_8))
    isolated_settings = {
        "isEnabled": True,
        "userConfig": {
            **source_settings.get("userConfig", {}),
            "storage_root": str(run_root / "desktop-storage"),
        },
    }
    dc.seed_extension(profile, extension_dir, settings_json=json.dumps(isolated_settings, indent=2))
    seed_secrets = dc.collect_seed_secrets(profile / "config.json")

    if not args.run_real_capture:
        print(json.dumps({"prepared": True, "profile": str(profile), "seeded": seeded}, indent=2))
        return 0

    # 3. Exclusivity: the harness must be the debug-enabled PRIMARY instance.
    running = dc.running_desktop_pids(package.executable)
    if running:
        if not args.allow_close_running:
            raise dc.DesktopCaptureError(
                f"Claude Desktop is already running (pids {list(running)}); the harness must own the primary "
                "instance. Re-run with --allow-close-running to close it first, or run on a machine with no "
                "interactive Desktop session.",
            )
        _close_desktop(running)

    # 4. Launch as primary (MSIX activation; requires non-elevated interactive session).
    pre_launch_entries = {entry.name for entry in iter_directory(profile)}
    dc.activate_desktop(package.aumid, remote_debugging_port=args.remote_debugging_port, user_data_dir=profile)
    version_doc = dc.wait_for_cdp(args.remote_debugging_port, timeout_seconds=args.launch_timeout_seconds)
    endpoint = version_doc.get("webSocketDebuggerUrl") or f"http://127.0.0.1:{args.remote_debugging_port}"

    # ABORT-BEFORE-DRIVE guard: if the app ignored --user-data-dir it is running
    # against the operator's real %APPDATA%\Claude — stop before any prompt or
    # write lands there. A honored isolated dir gains Chromium runtime entries
    # (DevToolsActivePort, caches, Preferences) beyond what was seeded.
    post_launch_entries = {entry.name for entry in iter_directory(profile)}
    if post_launch_entries == pre_launch_entries:
        _close_desktop(dc.running_desktop_pids(package.executable))
        raise dc.DesktopCaptureError(
            "Claude Desktop ignored --user-data-dir (the isolated profile gained no runtime state after "
            "launch); aborted before driving so nothing touches the real profile. The harness needs the "
            "APPDATA-redirection launch variant on this Desktop version.",
        )

    # 5. Drive + verify with bounded, fail-closed retries.
    baseline = len(_read_mcp_log(profile).successful_calls)
    capture = dc.capture_with_retries(
        _perform_attempt(cdp_endpoint=endpoint, isolated_profile=profile, baseline_calls=baseline),
        attempts=args.attempts,
    )
    _retain_attempts(logs, capture)
    if profile.joinpath("logs").is_dir():
        shutil.copytree(profile / "logs", logs / "desktop-mcp-logs", dirs_exist_ok=True)

    # 6. Fail-closed leak scan of every retained artifact before it can be trusted.
    dc.scan_for_secret_leak(logs, seed_secrets)

    if not capture.ok:
        raise dc.DesktopCaptureError(
            f"no attempt proved a real cadrumo tool call in {args.attempts} tries; diagnostics retained under {logs}",
        )

    # 7. Emit the sanctioned real-client row.
    launch_transcript = capture_owned_server_launch(
        server=uv,
        server_args=server_args,
        env={**isolated_mcp_environment(run_root / "launch-storage"), **server_env},
        cwd=run_root,
        timeout_seconds=args.timeout_seconds,
    )
    real_client_session = {
        "client": "claude-desktop",
        "client_version": package.version,
        "connected": True,
        "status": "passed",
        "tool_called": "cadrumo_whoami",
        "transport_observed": True,
        "attempts": [vars(attempt) for attempt in capture.attempts],
        "capture_mechanism": "automated-cdp-harness",
    }
    path = emit_client_evidence(
        directory=args.distribution_evidence_dir,
        row_id=args.row_id,
        cohort=cohort,
        mcp_evidence=protocol_oracle,
        launch_transcript=launch_transcript,
        client=ClientIdentity(
            name="claude-desktop",
            version=package.version,
            executable=str(package.executable),
        ),
        acquisition=AcquisitionIdentity(mechanism="real-claude-client", source=args.acquisition_source),
        destination=DestinationIdentity(
            kind=args.destination_kind,
            locator=args.destination_locator,
            version=cohort.manifest.version,
        ),
        real_client_session=real_client_session,
    )
    print(path)
    return 0


def _close_desktop(pids: tuple[int, ...]) -> None:
    """Close the running Claude Desktop gracefully so the harness can be primary.

    First requests a normal close (``taskkill`` without ``/F`` posts WM_CLOSE, so
    in-flight app state persists through the app's own shutdown path), waits for
    the process tree to exit, and only force-terminates whatever remains after
    the grace budget.
    """
    import shutil as _sh
    import subprocess

    taskkill = _sh.which("taskkill.exe") or r"C:\Windows\System32\taskkill.exe"

    for pid in pids:
        subprocess.run(  # noqa: S603 - graceful close request for an enumerated Desktop pid
            [taskkill, "/PID", str(pid)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    deadline = time.monotonic() + 30.0
    remaining: tuple[int, ...] = pids
    while remaining and time.monotonic() < deadline:
        time.sleep(2.0)
        alive = set(dc.running_desktop_pids(Path()))
        remaining = tuple(pid for pid in pids if pid in alive)
    for pid in remaining:  # last resort only, after the grace budget
        subprocess.run(  # noqa: S603 - forced close of a pid that ignored WM_CLOSE
            [taskkill, "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    time.sleep(3.0)


def _retain_attempts(logs: Path, capture: dc.CaptureResult) -> None:
    """Write every attempt's diagnostics to the retained evidence tree."""
    (logs / "attempts.json").write_text(
        json.dumps({"ok": capture.ok, "attempts": [vars(a) for a in capture.attempts]}, indent=2),
        encoding=_UTF_8,
        newline="\n",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--row-id", required=True, help="claude-desktop-mcpb or claude-desktop-plugin.")
    parser.add_argument("--release-cohort-dir", required=True, type=Path, help="Full release-cohort directory.")
    parser.add_argument("--evidence-dir", required=True, type=Path, help="Where per-run artifacts land.")
    parser.add_argument(
        "--source-profile",
        type=Path,
        default=Path.home() / "AppData" / "Roaming" / "Claude",
        help="Blessed Desktop profile to seed session auth + the extension from.",
    )
    parser.add_argument(
        "--extension-id",
        default="local.mcpb.cadrumo-project-neve.md.cadrumo",
        help="Installed cadrumo MCPB extension directory name.",
    )
    parser.add_argument("--acquisition-source", required=True, help="Where the client acquired the artifact.")
    parser.add_argument("--destination-kind", default="claude-desktop-extension")
    parser.add_argument("--destination-locator", required=True, help="Install destination locator.")
    parser.add_argument("--remote-debugging-port", type=int, default=9223)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--launch-timeout-seconds", type=float, default=90.0)
    parser.add_argument(
        "--run-real-capture",
        action="store_true",
        help="Launch and drive the real app; without it, only prepare the isolated profile + oracle.",
    )
    parser.add_argument(
        "--allow-close-running",
        action="store_true",
        help="Close an already-running Desktop instance so the harness can own the primary.",
    )
    parser.add_argument(
        "--distribution-evidence-dir",
        type=Path,
        default=Path("var/distribution-install-readiness"),
        help="Where the flat evidence record lands.",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
