"""Install the cohort-bound Claude plugin and prove its real MCP behavior.

The marketplace plugin is the acquisition surface: it carries the exact tested
three-wheel cohort and launches that cohort through ``uvx``. This smoke installs
the generated marketplace through Claude Code, reads the installed declaration,
then drives the declaration directly through the public MCP protocol. Tax truth
comes from raw initialize/list/call results checked by the shared installed MCP
oracle, never from model narration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any, Final

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cadrumo.agent import materialise_marketplace  # noqa: E402
from dev.packaging.installed_mcp_oracle import run_installed_mcp_oracle  # noqa: E402
from dev.packaging.python_cohort import PythonCohort, load_python_cohort  # noqa: E402

_UTF_8: Final[str] = "utf-8"
_PLUGIN_ID: Final[str] = "cadrumo@neve"
_COHORT_MANIFEST: Final[str] = "plugin-python-cohort.json"
_CLAUDE_PLUGIN_ROOT: Final[str] = "${CLAUDE_PLUGIN_ROOT}"
_CLIENT_TOOL_NAME: Final[str] = "mcp__plugin_cadrumo_cadrumo__cadrumo_harness_load"
_CLIENT_PROMPT: Final[str] = (
    "Call the Cadrumo cadrumo_harness_load MCP tool exactly once. "
    "Do not use Bash or any other tool. Then say only connected."
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(
    argv: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    log_path: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(  # noqa: S603 - every executable is an explicit operator input
        argv,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="replace",
        check=False,
        timeout=timeout_seconds,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        f"argv={json.dumps(argv)}\nreturncode={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        encoding=_UTF_8,
    )
    result = {
        "argv": argv,
        "duration_seconds": round(time.monotonic() - started, 3),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode != 0:
        raise SystemExit(f"command failed with exit {completed.returncode}: {argv!r}; see {log_path}")
    return result


def _installed_plugin(claude: Path, *, environment: dict[str, str], cwd: Path, log: Path) -> dict[str, Any]:
    record = _run(
        [str(claude), "plugin", "list", "--json"],
        cwd=cwd,
        environment=environment,
        log_path=log,
        timeout_seconds=60.0,
    )
    document = json.loads(record["stdout"])
    if not isinstance(document, list):
        raise SystemExit("Claude plugin list did not return a JSON array")
    plugin = next((item for item in document if isinstance(item, dict) and item.get("id") == _PLUGIN_ID), None)
    if not isinstance(plugin, dict):
        raise SystemExit(f"Claude did not report installed plugin {_PLUGIN_ID!r}")
    return plugin


def _verify_installed_cohort(plugin_root: Path, cohort: PythonCohort) -> dict[str, Any]:
    retained_path = plugin_root / "artifacts" / "python" / _COHORT_MANIFEST
    retained = json.loads(retained_path.read_text(encoding=_UTF_8))
    expected_sha256 = {
        "cadrumo": cohort.sha256["cadrumo"],
        "cadrumo-data-manuals": cohort.sha256["cadrumo-data-manuals"],
        "cadrumo-data-official": cohort.sha256["cadrumo-data-official"],
    }
    if retained.get("source_commit") != cohort.source_commit:
        raise SystemExit("installed plugin cohort source commit drifted")
    if retained.get("version") != cohort.version:
        raise SystemExit("installed plugin cohort version drifted")
    if retained.get("sha256") != expected_sha256:
        raise SystemExit("installed plugin cohort digest declaration drifted")
    artifacts = retained.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(expected_sha256):
        raise SystemExit("installed plugin cohort artifact declaration is incomplete")
    observed: dict[str, str] = {}
    for distribution, filename in artifacts.items():
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise SystemExit(f"installed plugin artifact path is invalid: {filename!r}")
        observed[distribution] = _sha256(retained_path.parent / filename)
    if observed != expected_sha256:
        raise SystemExit("installed plugin cohort bytes do not match the tested cohort")
    return retained


def _resolve_server(plugin: dict[str, Any]) -> tuple[Path, tuple[str, ...], dict[str, str], Path]:
    install_path = plugin.get("installPath")
    servers = plugin.get("mcpServers")
    if not isinstance(install_path, str) or not install_path:
        raise SystemExit("Claude plugin list omitted the installed plugin path")
    if not isinstance(servers, dict) or not isinstance(servers.get("cadrumo"), dict):
        raise SystemExit("Claude plugin list omitted the installed Cadrumo MCP declaration")
    plugin_root = Path(install_path).resolve(strict=True)
    server = servers["cadrumo"]
    command = server.get("command")
    args = server.get("args")
    declared_environment = server.get("env")
    if command != "uvx" or not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise SystemExit(f"installed plugin MCP launcher is not the pinned uvx contract: {server!r}")
    if not isinstance(declared_environment, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in declared_environment.items()
    ):
        raise SystemExit("installed plugin MCP environment declaration is invalid")
    uvx = shutil.which(command)
    if uvx is None:
        raise SystemExit("uvx is required to execute the installed plugin cohort")
    resolved_args = tuple(item.replace(_CLAUDE_PLUGIN_ROOT, str(plugin_root)) for item in args)
    if _CLAUDE_PLUGIN_ROOT in " ".join(resolved_args):
        raise SystemExit("installed plugin root interpolation was not fully resolved")
    environment = {
        key: ("" if value == "${user_config.persona}" else "core" if value == "${user_config.surface}" else value)
        for key, value in declared_environment.items()
    }
    return Path(uvx).resolve(strict=True), resolved_args, environment, plugin_root


# The credential-document fields that carry actual secrets. Keying on these
# (rather than every long string value) keeps an account email or UUID from
# tripping a spurious "credential leaked" refusal that would delete the very
# log needed to triage a smoke failure.
_CREDENTIAL_SECRET_FIELDS: Final[frozenset[str]] = frozenset({"accessToken", "refreshToken"})


def _credential_secret_values(credential_path: Path, *, environment: dict[str, str]) -> tuple[str, ...]:
    """The secret values whose appearance in a retained log refuses the run.

    Collects the known token fields from the copied credential document (every
    string value >= 16 chars as a fallback when no known field matches, so an
    unrecognised credential shape stays covered), plus any API key or auth
    token the environment supplies, plus a URL-encoded variant of each - the
    one cheap re-encoding a protocol log plausibly applies.
    """
    secrets: list[str] = []
    try:
        document = json.loads(credential_path.read_text(encoding=_UTF_8))
    except (OSError, json.JSONDecodeError):
        document = None
    field_hits: list[str] = []
    long_strings: list[str] = []
    pending: list[Any] = [document] if document is not None else []
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if key in _CREDENTIAL_SECRET_FIELDS and isinstance(value, str) and value:
                    field_hits.append(value)
                else:
                    pending.append(value)
        elif isinstance(node, list):
            pending.extend(node)
        elif isinstance(node, str) and len(node) >= 16:
            long_strings.append(node)
    secrets.extend(field_hits if field_hits else long_strings)
    secrets.extend(
        value for value in (environment.get("ANTHROPIC_API_KEY"), environment.get("ANTHROPIC_AUTH_TOKEN")) if value
    )
    return tuple(dict.fromkeys(secret for value in secrets for secret in (value, urllib.parse.quote(value, safe=""))))


def _assert_no_credential_leak(logs: Path, *, secrets: tuple[str, ...]) -> None:
    """Refuse to retain session evidence that carries a credential secret.

    The retained evidence tree uploads as a CI artifact; the Claude debug and
    session logs land inside it. Scanning them for the credential secret
    values (verbatim and URL-encoded) fails closed BEFORE the run returns.
    This covers the dominant leak shape - a token echoed intact or
    URL-encoded into a diagnostic line - and REDUCES rather than eliminates
    the risk: an exotic re-encoding (base64-of-header, compressed output, or
    a substring broken by a replaced undecodable byte) would pass the scan.
    Note the SystemExit here supersedes any in-flight exception from the
    protected block; when a leak and a functional failure co-occur, the leak
    refusal is deliberately the surviving signal.
    """
    if not secrets:
        return
    for log_path in sorted(logs.rglob("*")):
        if not log_path.is_file():
            continue
        text = log_path.read_text(encoding=_UTF_8, errors="replace")
        if any(secret in text for secret in secrets):
            log_path.unlink()
            raise SystemExit(
                f"credential secret leaked into session log {log_path.name}; "
                "the leaking log was deleted and the evidence run is refused",
            )


def _run_optional_claude_session(
    claude: Path,
    *,
    environment: dict[str, str],
    cwd: Path,
    logs: Path,
    model: str,
    max_budget_usd: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    debug_log = logs / "claude-debug.log"
    record = _run(
        [
            str(claude),
            "-p",
            "--output-format",
            "json",
            "--setting-sources",
            "user",
            "--permission-mode",
            "bypassPermissions",
            "--dangerously-skip-permissions",
            "--model",
            model,
            "--max-budget-usd",
            max_budget_usd,
            "--debug-file",
            str(debug_log),
            _CLIENT_PROMPT,
        ],
        cwd=cwd,
        environment=environment,
        log_path=logs / "claude-client-session.log",
        timeout_seconds=timeout_seconds,
    )
    debug_text = debug_log.read_text(encoding=_UTF_8)
    connected = 'MCP server "plugin:cadrumo:cadrumo": Successfully connected' in debug_text
    tool_called = f"tool={_CLIENT_TOOL_NAME}" in debug_text
    if not connected or not tool_called:
        raise SystemExit("Claude client session did not prove plugin MCP connection and harness tool use")
    return {
        "connected": connected,
        "duration_seconds": record["duration_seconds"],
        "model": model,
        "status": "passed",
        "tool_called": _CLIENT_TOOL_NAME,
    }


def main(argv: list[str] | None = None) -> int:
    """Run installed-plugin acquisition and protocol evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude", type=Path, required=True, help="Absolute Claude Code executable.")
    parser.add_argument("--cohort-dir", type=Path, required=True, help="Canonical tested Python cohort.")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--run-claude-session", action="store_true")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--max-budget-usd", default="0.5")
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    args = parser.parse_args(argv)

    claude = args.claude.resolve(strict=True)
    if sys.platform == "win32" and claude.suffix.lower() == ".ps1":
        # An npm-installed Claude Code resolves to the PowerShell shim first
        # (`Get-Command claude` -> claude.ps1), which CreateProcess cannot
        # execute (WinError 193). npm always writes the sibling .cmd shim,
        # which CreateProcess runs natively - swap to it.
        command_shim = claude.with_suffix(".cmd")
        if not command_shim.is_file():
            raise SystemExit(
                f"claude resolves to a PowerShell shim ({claude}) and no sibling "
                ".cmd shim exists; pass the executable directly via --claude",
            )
        claude = command_shim
    cohort = load_python_cohort(args.cohort_dir)
    evidence_root = args.evidence_dir.resolve()
    run_root = evidence_root / f"run-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    marketplace = run_root / "marketplace"
    workspace = run_root / "workspace"
    # The isolated Claude config lives OUTSIDE the retained evidence tree: a
    # subscription credential copied into it must never reach evidence bytes
    # that later upload as CI artifacts or publish with a release.
    config_dir = Path(tempfile.mkdtemp(prefix="cadrumo-plugin-smoke-claude-config-"))
    logs = run_root / "logs"
    workspace.mkdir(parents=True)

    environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    default_config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
    environment["CLAUDE_CONFIG_DIR"] = str(config_dir)
    subscription_credential = default_config_dir / ".credentials.json"
    if subscription_credential.is_file():
        shutil.copy2(subscription_credential, config_dir / ".credentials.json")
    has_claude_credential = bool(
        environment.get("ANTHROPIC_API_KEY")
        or environment.get("ANTHROPIC_AUTH_TOKEN")
        or subscription_credential.is_file(),
    )
    if args.run_claude_session and not has_claude_credential:
        raise SystemExit(
            "--run-claude-session requires ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, "
            "or a subscription-authenticated Claude Code login "
            f"({subscription_credential})",
        )

    credential_secrets = _credential_secret_values(config_dir / ".credentials.json", environment=environment)
    try:
        return _prove_installed_plugin(
            args,
            claude=claude,
            cohort=cohort,
            run_root=run_root,
            marketplace=marketplace,
            workspace=workspace,
            logs=logs,
            environment=environment,
            has_claude_credential=has_claude_credential,
        )
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)
        # Every exit path - success, refusal, or crash - scans the retained
        # session logs for the credential secrets before the evidence survives.
        if logs.is_dir():
            _assert_no_credential_leak(logs, secrets=credential_secrets)


def _prove_installed_plugin(
    args: argparse.Namespace,
    *,
    claude: Path,
    cohort: PythonCohort,
    run_root: Path,
    marketplace: Path,
    workspace: Path,
    logs: Path,
    environment: dict[str, str],
    has_claude_credential: bool,
) -> int:
    """Install the marketplace plugin and retain protocol plus session evidence."""
    manifest = materialise_marketplace(marketplace, cohort=cohort)
    _run(
        [str(claude), "plugin", "marketplace", "add", str(marketplace)],
        cwd=workspace,
        environment=environment,
        log_path=logs / "marketplace-add.log",
        timeout_seconds=60.0,
    )
    _run(
        [str(claude), "plugin", "install", _PLUGIN_ID, "--scope", "user"],
        cwd=workspace,
        environment=environment,
        log_path=logs / "plugin-install.log",
        timeout_seconds=120.0,
    )
    _run(
        [str(claude), "plugin", "enable", _PLUGIN_ID],
        cwd=workspace,
        environment=environment,
        log_path=logs / "plugin-enable.log",
        timeout_seconds=60.0,
    )
    plugin = _installed_plugin(
        claude,
        environment=environment,
        cwd=workspace,
        log=logs / "plugin-list.log",
    )
    if plugin.get("enabled") is not True or plugin.get("version") != cohort.version:
        raise SystemExit(f"installed plugin identity mismatch: {plugin!r}")

    uvx, server_args, server_environment, plugin_root = _resolve_server(plugin)
    retained = _verify_installed_cohort(plugin_root, cohort)
    protocol = run_installed_mcp_oracle(
        uvx,
        server_args=server_args,
        environment_overrides=server_environment,
        storage_root=run_root / "storage",
        work_dir=run_root / "external-work",
        timeout_seconds=args.timeout_seconds,
    )
    client_session = (
        _run_optional_claude_session(
            claude,
            environment=environment,
            cwd=workspace,
            logs=logs,
            model=args.model,
            max_budget_usd=args.max_budget_usd,
            timeout_seconds=args.timeout_seconds,
        )
        if args.run_claude_session
        else {"status": "not_run_no_credential" if not has_claude_credential else "not_requested"}
    )

    evidence = {
        "artifact": {
            "marketplace_name": manifest.marketplace_name,
            "plugin_id": _PLUGIN_ID,
            "plugin_version": manifest.plugin.version,
        },
        "claude_client_session": client_session,
        "cohort": {
            "sha256": retained["sha256"],
            "source_commit": cohort.source_commit,
            "version": cohort.version,
        },
        "installed_plugin": {
            "enabled": True,
            "launcher": str(uvx),
            "server_args": list(server_args),
        },
        "protocol_oracle": protocol.to_jsonable(),
        "schema": "cadrumo.packaging.claude-plugin-evidence.v1",
    }
    evidence_path = run_root / "plugin-evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding=_UTF_8,
    )
    print(evidence_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
