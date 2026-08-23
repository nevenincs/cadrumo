"""Reacquire the public Claude marketplace plugin and repeat the MCP tax call.

This post-publication check adds the PUBLIC Claude plugin marketplace source,
installs the Cadrumo plugin through Claude Code, proves the plugin's retained
closed-world cohort matches the promoted cohort byte-for-byte, and repeats the
grounded MCP tax-work oracle against the plugin-declared ``uvx`` launch. It
refuses instructively when Claude Code is unavailable or the public marketplace
does not yet carry the plugin (implements post-release-distribution plan rows
P03.S18 and P03.S20). Acquisition differs from the local packaging smoke only in
its source: the marketplace is added from a published repository, never a
locally materialised directory.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from importlib.metadata import version as _package_version
from pathlib import Path
from typing import Final

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if not __package__:
    __package__ = "dev.packaging"

from ._acquire_common import (  # noqa: E402
    AcquisitionError,
    capture_owned_server_launch,
    require_command_succeeded,
)
from ._command import CommandResult, run_command  # noqa: E402
from ._hashing import sha256_path  # noqa: E402
from .cohort_manifest import load_release_cohort  # noqa: E402
from .distribution_evidence_emit import SDK_CLIENT_NAME, emit_client_evidence  # noqa: E402
from .evidence import (  # noqa: E402
    AcquisitionIdentity,
    ClientIdentity,
    DestinationIdentity,
)
from .installed_mcp_oracle import isolated_mcp_environment  # noqa: E402
from .python_cohort import load_python_cohort  # noqa: E402
from .smoke_plugin_install import (  # noqa: E402
    _PLUGIN_ID,
    _installed_plugin,
    _resolve_server,
    _verify_installed_cohort,
)

_UTF_8: Final[str] = "utf-8"
# The public Claude plugin marketplace repository (marketplace name "neve"),
# distinct from the product repo. Per packaging/marketplace/README.md, users add
# it with `/plugin marketplace add nevenincs/neve-marketplace`.
_DEFAULT_MARKETPLACE_SOURCE: Final[str] = "nevenincs/neve-marketplace"
_DEFAULT_DISTRIBUTION_EVIDENCE_DIR: Final[Path] = Path("var/distribution-install-readiness")


def _resolve_claude(override: Path | None) -> Path:
    """Resolve the Claude Code executable, refusing instructively when absent."""
    if override is not None:
        return override.expanduser().resolve(strict=True)
    import shutil

    found = shutil.which("claude")
    if found is None:
        raise AcquisitionError(
            "claude (Claude Code) not found on PATH; install it or pass --claude to reacquire the public plugin",
        )
    return Path(found).resolve(strict=True)


def _run(argv: list[str], *, cwd: Path, environment: dict[str, str], log: Path, timeout: float) -> CommandResult:
    """Run one Claude Code subprocess, retaining full output to a log file."""
    completed = run_command(
        argv,
        cwd=cwd,
        environment=environment,
        timeout_seconds=timeout,
        errors="replace",
    )
    log.write_text(
        f"argv={json.dumps(argv)}\nexit_code={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}\n",
        encoding=_UTF_8,
        newline="\n",
    )
    return completed


def run_claude_plugin_acquisition(
    *,
    cohort_dir: Path,
    evidence_dir: Path,
    marketplace_source: str,
    plugin_id: str,
    claude_executable: Path | None,
    timeout_seconds: float,
    release_cohort_dir: Path | None = None,
    row_id: str | None = None,
    distribution_evidence_dir: Path | None = None,
) -> Path:
    """Install the public plugin, verify its cohort, and repeat the MCP oracle.

    Args:
        cohort_dir: The promoted Python cohort directory (expected wheel digests).
        evidence_dir: The directory retaining per-run evidence.
        marketplace_source: The PUBLIC marketplace repository/URL to add.
        plugin_id: The plugin identifier to install (``name@marketplace``).
        claude_executable: An explicit ``claude`` path, or ``None`` for PATH.
        timeout_seconds: Timeout for Claude commands and the MCP oracle.
        release_cohort_dir: The full release-cohort directory to bind a sanctioned
            flat client-row record to. When omitted, only the per-run acquisition
            document is written.
        row_id: The client row this run proves (required to emit the flat record,
            e.g. ``claude-code-plugin``).
        distribution_evidence_dir: Where the flat record lands; defaults to
            ``var/distribution-install-readiness`` (the directory both gates scan).

    Returns:
        The path to the retained JSON evidence document.

    Raises:
        AcquisitionError: If Claude is absent, the public marketplace lacks the
            plugin, or the retained cohort drifts from the promoted cohort.
    """
    cohort = load_python_cohort(cohort_dir)
    claude = _resolve_claude(claude_executable)
    evidence_root = evidence_dir.resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    run_root = evidence_root / f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    run_root.mkdir()
    logs = run_root / "logs"
    logs.mkdir()
    workspace = run_root / "workspace"
    workspace.mkdir()

    environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    config_dir = Path(tempfile.mkdtemp(prefix="cadrumo-acquire-plugin-config-"))
    environment["CLAUDE_CONFIG_DIR"] = str(config_dir)

    add = _run(
        [str(claude), "plugin", "marketplace", "add", marketplace_source],
        cwd=workspace,
        environment=environment,
        log=logs / "marketplace-add.log",
        timeout=timeout_seconds,
    )
    require_command_succeeded(
        returncode=add.returncode,
        stderr=add.stderr,
        mechanism="claude plugin marketplace add",
        endpoint=marketplace_source,
        version=cohort.version,
        next_step=f"publish the Cadrumo plugin marketplace at {marketplace_source} and rerun",
    )
    install = _run(
        [str(claude), "plugin", "install", plugin_id, "--scope", "user"],
        cwd=workspace,
        environment=environment,
        log=logs / "plugin-install.log",
        timeout=timeout_seconds,
    )
    require_command_succeeded(
        returncode=install.returncode,
        stderr=install.stderr,
        mechanism="claude plugin install",
        endpoint=f"{marketplace_source}::{plugin_id}",
        version=cohort.version,
        next_step=f"publish {plugin_id}=={cohort.version} to {marketplace_source} and rerun",
    )
    _run(
        [str(claude), "plugin", "enable", plugin_id],
        cwd=workspace,
        environment=environment,
        log=logs / "plugin-enable.log",
        timeout=timeout_seconds,
    )

    plugin = _installed_plugin(claude, environment=environment, cwd=workspace, log=logs / "plugin-list.log")
    if plugin.get("enabled") is not True or plugin.get("version") != cohort.version:
        raise AcquisitionError(f"installed public plugin identity mismatch: {plugin!r}")
    uvx, server_args, server_environment, plugin_root = _resolve_server(plugin)
    retained = _verify_installed_cohort(plugin_root, cohort)

    # The plugin's acquisition surface is the MCP server launched via uvx, not a
    # standalone aeat CLI, so behaviour is proven by the MCP oracle alone; the
    # tax oracle needs a direct CLI executable the plugin does not expose.
    from .installed_mcp_oracle import run_installed_mcp_oracle

    mcp_evidence = run_installed_mcp_oracle(
        uvx,
        server_args=server_args,
        environment_overrides=server_environment,
        storage_root=run_root / "storage",
        work_dir=run_root / "external-work",
        cohort_source_commit=cohort.source_commit,
        cohort_manifest_sha256=sha256_path(cohort.manifest),
        cohort_root_wheel_sha256=cohort.sha256["cadrumo"],
        cohort_harness_wheel_sha256=cohort.sha256["cadrumo-harness"],
        timeout_seconds=timeout_seconds,
    )
    if mcp_evidence.target_value != "23000.00":
        raise AcquisitionError(f"public plugin MCP oracle target value drifted: {mcp_evidence.target_value!r}")

    # Owned bounded launch of the exact plugin server contract, captured after the
    # oracle (so it cannot pollute the oracle's storage) for the option-A record.
    launch_env = isolated_mcp_environment(run_root / "storage")
    launch_env.update(server_environment)
    launch_transcript = capture_owned_server_launch(
        server=uvx,
        server_args=server_args,
        env=launch_env,
        cwd=run_root,
        timeout_seconds=timeout_seconds,
    )

    if release_cohort_dir is not None and row_id is not None:
        release_cohort = load_release_cohort(release_cohort_dir)
        emit_client_evidence(
            directory=(distribution_evidence_dir or _DEFAULT_DISTRIBUTION_EVIDENCE_DIR),
            row_id=row_id,
            cohort=release_cohort,
            mcp_evidence=mcp_evidence,
            launch_transcript=launch_transcript,
            client=ClientIdentity(
                name=SDK_CLIENT_NAME,
                version=_package_version("mcp"),
                executable=str(uvx),
            ),
            acquisition=AcquisitionIdentity(mechanism="claude-plugin", source=f"{marketplace_source}::{plugin_id}"),
            destination=DestinationIdentity(
                kind="claude-plugin",
                locator=str(plugin_root),
                version=release_cohort.manifest.version,
            ),
        )

    evidence = {
        "schema": "cadrumo.packaging.acquire-claude-plugin.v1",
        "status": "passed",
        "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "marketplace_source": marketplace_source,
        "plugin_id": plugin_id,
        "harness_namespace_tools": [tool for tool in mcp_evidence.advertised_tools if tool.startswith("cadrumo")],
        "cohort": {
            "source_commit": cohort.source_commit,
            "version": cohort.version,
            "sha256": retained["sha256"],
        },
        "installed_plugin": {"enabled": True, "launcher": str(uvx), "server_args": list(server_args)},
        "protocol_oracle": mcp_evidence.to_jsonable(),
    }
    evidence_path = run_root / "acquire-claude-plugin-evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    return evidence_path


def _parser() -> argparse.ArgumentParser:
    """Return the argument parser for the Claude plugin reacquisition check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-dir", required=True, type=Path, help="Promoted Python cohort directory.")
    parser.add_argument("--evidence-dir", required=True, type=Path, help="Directory retaining per-run evidence.")
    parser.add_argument(
        "--marketplace-source",
        default=_DEFAULT_MARKETPLACE_SOURCE,
        help="Public Claude plugin marketplace repository or URL to add.",
    )
    parser.add_argument("--plugin-id", default=_PLUGIN_ID, help="Plugin identifier to install (name@marketplace).")
    parser.add_argument("--claude", type=Path, default=None, help="Explicit claude executable (defaults to PATH).")
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument(
        "--release-cohort-dir",
        type=Path,
        default=None,
        help="Full release-cohort directory to bind a sanctioned flat client record to.",
    )
    parser.add_argument(
        "--row-id",
        default=None,
        help="Client row this run proves (required to emit the flat record).",
    )
    parser.add_argument(
        "--distribution-evidence-dir",
        type=Path,
        default=None,
        help="Where the flat record lands (defaults to var/distribution-install-readiness).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Claude plugin reacquisition verification from the command line."""
    args = _parser().parse_args(argv)
    evidence = run_claude_plugin_acquisition(
        cohort_dir=args.cohort_dir,
        evidence_dir=args.evidence_dir,
        marketplace_source=args.marketplace_source,
        plugin_id=args.plugin_id,
        claude_executable=args.claude,
        timeout_seconds=args.timeout_seconds,
        release_cohort_dir=args.release_cohort_dir,
        row_id=args.row_id,
        distribution_evidence_dir=args.distribution_evidence_dir,
    )
    print(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
