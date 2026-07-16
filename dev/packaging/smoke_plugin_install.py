"""Install the generated Claude plugin and perform real tax work through it.

The plugin integrates with an already installed ``cadrumo-mcp`` service. This
lane materialises a marketplace, installs and enables its plugin in an isolated
Claude configuration, verifies the installed three-distribution cohort, and
asks the real Claude client to complete the grounded Modelo 200 oracle entirely
through the plugin MCP tools.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Final

from cadrumo.agent import materialise_marketplace
from dev.packaging.installed_tax_oracle import isolated_product_environment

_UTF_8: Final[str] = "utf-8"
_PLUGIN_ID: Final[str] = "cadrumo@neve"
_DISTRIBUTIONS: Final[tuple[str, ...]] = (
    "cadrumo",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)
_JSON_FENCE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
_COHORT_PROBE = (
    "import json; from importlib.metadata import version; "
    f"names={_DISTRIBUTIONS!r}; "
    "print(json.dumps({name:version(name) for name in names},sort_keys=True))"
)
_TAX_PROMPT = """Use only the installed Cadrumo plugin MCP tools. Execute this real itinerary;
do not use Bash, files, or fabricate values.
1. Call execute with command_key config.profile.create and arguments:
{"profile_name":"installed-oracle","quiet":true,"accept_defaults":true,
"entity_type":"legal_entity","legal_entity_form":"sl","tax_id":"B66012345",
"legal_name":"Installed Oracle SL","activity":"software services",
"incn_prior_12_months":"500000","new_entity_first_two_profit_periods":false,
"iva_regime":"GENERAL","tax_residence_ccaa":"madrid"}.
2. Call cadrumo_whoami and require active_profile installed-oracle.
3. Call execute with command_key modelo.work.create and arguments:
{"modelo":"200","year":2024,"period":"0A","revision":"2024-y-siguientes",
"name":"Installed Modelo 200 oracle","actor":"installed-tax-oracle"}.
Extract the returned work_unit_id.
4. Calculate that work unit through the Cadrumo MCP surface with:
casilla=["00501=100000.00","DP200013:00417=0.00","DP200013:00418=0.00",
"01032=0.00","DP200014:00547=0.00","DP200014:01033=0.00",
"DP200014:01034=0.00"],
binding=["modelo-200-2024-profile-legal-entity-form=sl",
"modelo-200-2024-profile-new-entity-flag=0",
"modelo-200-2024-profile-incn-prior-12-months=500000",
"modelo-200-2024-profile-tributacion-estado-porcentaje=100",
"modelo-200-2024-bin-pendiente-ejercicios-anteriores=0",
"modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores=0",
"modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores=0"],
relation=["modelo-200-2024-rel-202-pagos-fraccionados=0",
"modelo-200-2024-rel-202-pagos-fraccionados-40-2=0"],
actor="installed-tax-oracle".
5. Read the calculation observations and find DP200014:00562. Require value
23000.00, formula_id modelo-200-cuota-integra, legal_refs containing
ley-27-2014:art-29, and source_refs containing
aeat-modelo-200-manual-2024.
Return one compact JSON object in a ```json fence containing connected,
active_profile, work_unit_id, target_casilla, target_value, formula_id,
legal_ref_present, source_ref_present, and mcp_tools_called. If any call fails,
return the real failure instead of claiming success."""


def _python_for_mcp(executable: Path) -> Path:
    candidate = executable.parent / ("python.exe" if sys.platform == "win32" else "python")
    if not candidate.is_file():
        raise SystemExit(f"cannot locate the installed cohort Python beside {executable}")
    return candidate.resolve()


def _run(
    argv: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    log_path: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(  # noqa: S603 - executable paths are explicit operator inputs
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
    record = {
        "argv": argv,
        "cwd": str(cwd),
        "duration_seconds": round(time.monotonic() - started, 3),
        "log": str(log_path),
        "returncode": completed.returncode,
        "stderr": completed.stderr,
        "stdout": completed.stdout,
    }
    if completed.returncode != 0:
        raise SystemExit(f"command failed with exit {completed.returncode}: {argv!r}; see {log_path}")
    return record


def _parse_oracle(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("is_error") is not False or result.get("subtype") != "success":
        raise SystemExit(f"Claude did not complete successfully: {result!r}")
    response = result.get("result")
    if not isinstance(response, str):
        raise SystemExit("Claude result did not contain textual output")
    match = _JSON_FENCE.search(response)
    if match is None:
        raise SystemExit("Claude result did not contain the required JSON fence")
    oracle = json.loads(match.group(1))
    required = {
        "connected": True,
        "active_profile": "installed-oracle",
        "target_casilla": "DP200014:00562",
        "target_value": "23000.00",
        "formula_id": "modelo-200-cuota-integra",
        "legal_ref_present": True,
        "source_ref_present": True,
    }
    for key, expected in required.items():
        if oracle.get(key) != expected:
            raise SystemExit(f"Claude oracle mismatch for {key}: {oracle.get(key)!r} != {expected!r}")
    work_unit_id = oracle.get("work_unit_id")
    tools = oracle.get("mcp_tools_called")
    if not isinstance(work_unit_id, str) or not work_unit_id:
        raise SystemExit("Claude oracle omitted the real work_unit_id")
    if not isinstance(tools, list) or not tools or not all(isinstance(item, str) for item in tools):
        raise SystemExit("Claude oracle omitted the MCP tool-call evidence")
    return oracle


def _copy_credentials(credentials: Path | None, config_dir: Path) -> Path | None:
    if credentials is None:
        return None
    if not credentials.is_file():
        raise SystemExit(f"Claude credentials file does not exist: {credentials}")
    destination = config_dir / ".credentials.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(credentials, destination)
    return destination


def main(argv: list[str] | None = None) -> int:
    """Run the isolated installed-plugin tax oracle and retain its evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude", type=Path, required=True)
    parser.add_argument("--mcp", type=Path, required=True)
    parser.add_argument("--credentials", type=Path)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--max-budget-usd", default="1.5")
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    args = parser.parse_args(argv)

    claude = args.claude.resolve(strict=True)
    mcp = args.mcp.resolve(strict=True)
    evidence_root = args.evidence_dir.resolve()
    run_root = evidence_root / f"run-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    marketplace = run_root / "marketplace"
    workspace = run_root / "workspace"
    config_dir = run_root / "claude-config"
    logs = run_root / "logs"
    workspace.mkdir(parents=True)
    config_dir.mkdir(parents=True)

    environment = isolated_product_environment(run_root / "storage")
    environment["CLAUDE_CONFIG_DIR"] = str(config_dir)
    environment["PATH"] = os.pathsep.join((str(mcp.parent), environment.get("PATH", "")))
    copied_credentials = _copy_credentials(args.credentials.resolve() if args.credentials else None, config_dir)
    if copied_credentials is None and not (
        environment.get("ANTHROPIC_API_KEY") or environment.get("ANTHROPIC_AUTH_TOKEN")
    ):
        raise SystemExit("provide --credentials or set ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN")

    commands: list[dict[str, Any]] = []
    try:
        cohort_record = _run(
            [str(_python_for_mcp(mcp)), "-c", _COHORT_PROBE],
            cwd=workspace,
            environment=environment,
            log_path=logs / "installed-cohort.log",
            timeout_seconds=60.0,
        )
        commands.append(cohort_record)
        installed_cohort = json.loads(cohort_record["stdout"])
        versions = set(installed_cohort.values())
        if set(installed_cohort) != set(_DISTRIBUTIONS) or len(versions) != 1:
            raise SystemExit(f"installed MCP cohort is incomplete or mixed: {installed_cohort!r}")
        (version,) = versions
        manifest = materialise_marketplace(marketplace, version=version)

        for name, command, timeout in (
            ("marketplace-add", [str(claude), "plugin", "marketplace", "add", str(marketplace)], 60.0),
            ("plugin-install", [str(claude), "plugin", "install", _PLUGIN_ID, "--scope", "user"], 120.0),
            ("plugin-enable", [str(claude), "plugin", "enable", _PLUGIN_ID], 60.0),
        ):
            commands.append(
                _run(
                    command,
                    cwd=workspace,
                    environment=environment,
                    log_path=logs / f"{name}.log",
                    timeout_seconds=timeout,
                ),
            )
        plugin_list_record = _run(
            [str(claude), "plugin", "list", "--json"],
            cwd=workspace,
            environment=environment,
            log_path=logs / "plugin-list.log",
            timeout_seconds=60.0,
        )
        commands.append(plugin_list_record)
        installed_plugins = json.loads(plugin_list_record["stdout"])
        plugin = next((item for item in installed_plugins if item.get("id") == _PLUGIN_ID), None)
        if plugin is None or plugin.get("enabled") is not True or plugin.get("version") != version:
            raise SystemExit(f"installed plugin identity mismatch: {plugin!r}")
        server = plugin.get("mcpServers", {}).get("cadrumo", {})
        expected_env = {
            "CADRUMO_MCP_REQUIRED_VERSION": version,
            "CADRUMO_MCP_PERSONA": "${user_config.persona}",
            "CADRUMO_MCP_SURFACE": "${user_config.surface}",
        }
        if server.get("command") != "cadrumo-mcp" or server.get("args") != [] or server.get("env") != expected_env:
            raise SystemExit(f"installed plugin MCP declaration is not the global service integration: {server!r}")

        debug_log = logs / "claude-debug.log"
        claude_record = _run(
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
                args.model,
                "--max-budget-usd",
                args.max_budget_usd,
                "--debug-file",
                str(debug_log),
                _TAX_PROMPT,
            ],
            cwd=workspace,
            environment=environment,
            log_path=logs / "claude-tax-oracle.log",
            timeout_seconds=args.timeout_seconds,
        )
        commands.append(claude_record)
        claude_result = json.loads(claude_record["stdout"])
        oracle = _parse_oracle(claude_result)
        debug_text = debug_log.read_text(encoding=_UTF_8)
        if 'MCP server "plugin:cadrumo:cadrumo": Successfully connected' not in debug_text:
            raise SystemExit("Claude debug log does not prove the plugin MCP server connected")
        if "tool=mcp__plugin_cadrumo_cadrumo__execute" not in debug_text:
            raise SystemExit("Claude debug log does not prove real Cadrumo MCP execution")

        evidence_path = run_root / "plugin-evidence.json"
        evidence_path.write_text(
            json.dumps(
                {
                    "artifact": {
                        "marketplace": str(marketplace),
                        "marketplace_name": manifest.marketplace_name,
                        "plugin_id": _PLUGIN_ID,
                        "plugin_version": manifest.plugin.version,
                    },
                    "claude_result": claude_result,
                    "client": {"claude_executable": str(claude), "model": args.model},
                    "commands": commands,
                    "debug_log": str(debug_log),
                    "installed_cohort": installed_cohort,
                    "installed_mcp_executable": str(mcp),
                    "oracle": oracle,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding=_UTF_8,
        )
        print(evidence_path)
        return 0
    finally:
        if copied_credentials is not None:
            copied_credentials.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
