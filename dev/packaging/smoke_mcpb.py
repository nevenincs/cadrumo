"""Build, validate, provision, and exercise one cohort-bound Cadrumo MCPB."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dev.packaging.installed_mcp_oracle import run_installed_mcp_oracle  # noqa: E402
from dev.packaging.python_cohort import load_python_cohort  # noqa: E402

_UTF_8: Final[str] = "utf-8"
_MCPB_CLI_VERSION: Final[str] = "2.1.2"
_BUILDER = _REPO_ROOT / "packaging" / "mcpb" / "build.py"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(argv: list[str], *, cwd: Path, env: dict[str, str], log: Path, timeout: float) -> None:
    completed = subprocess.run(  # noqa: S603 - fixed repository and installed tool commands
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="strict",
        check=False,
        timeout=timeout,
    )
    log.write_text(
        f"argv={json.dumps(argv)}\n"
        f"cwd={cwd}\n"
        f"exit_code={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}\n",
        encoding=_UTF_8,
    )
    if completed.returncode != 0:
        raise SystemExit(f"command failed ({completed.returncode}): {argv!r}; retained log: {log}")


def _run_concurrent_launches(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    logs: Path,
    timeout: float,
    count: int = 4,
) -> None:
    """Launch the real server concurrently after host-style provisioning."""
    processes = [
        subprocess.Popen(  # noqa: S603 - fixed installed tool and bundle-owned server
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=_UTF_8,
            errors="strict",
        )
        for _ in range(count)
    ]
    failures: list[str] = []
    for index, process in enumerate(processes, start=1):
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            failures.append(f"launch {index} timed out")
        log = logs / f"concurrent-launch-{index}.log"
        log.write_text(
            f"argv={json.dumps(argv)}\n"
            f"cwd={cwd}\n"
            f"exit_code={process.returncode}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}\n",
            encoding=_UTF_8,
        )
        if process.returncode != 0:
            failures.append(f"launch {index} exited {process.returncode}; retained log: {log}")
    if failures:
        raise SystemExit("; ".join(failures))


def _npx_argv(npx: Path) -> list[str]:
    """Return a directly executable NPX argv on POSIX and Windows."""
    if npx.suffix.casefold() not in {".cmd", ".bat", ".ps1"}:
        return [str(npx)]
    node = npx.parent / "node.exe"
    cli = npx.parent / "node_modules" / "npm" / "bin" / "npx-cli.js"
    if not node.is_file() or not cli.is_file():
        raise SystemExit(f"could not resolve node+npx-cli beside {npx}")
    return [str(node), str(cli)]


def _resolve_mcpb_value(
    value: str,
    *,
    extension_dir: Path,
    user_config: dict[str, str],
) -> str:
    """Resolve only placeholders sanctioned by the MCPB manifest contract."""
    resolved = value.replace("${__dirname}", str(extension_dir))
    for name, configured in user_config.items():
        resolved = resolved.replace(f"${{user_config.{name}}}", configured)
    if "${" in resolved:
        raise SystemExit(f"unresolved MCPB placeholder in launch value: {value!r}")
    return resolved


def run_mcpb_smoke(
    *,
    cohort_dir: Path,
    evidence_dir: Path,
    uv_executable: Path,
    npx_executable: Path,
    timeout_seconds: float,
) -> Path:
    """Exercise the exact MCPB launch contract through a real MCP tax oracle."""
    cohort = load_python_cohort(cohort_dir)
    uv = uv_executable.expanduser().resolve(strict=True)
    npx = npx_executable.expanduser().resolve(strict=True)
    evidence_root = evidence_dir.resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    run_root = evidence_root / f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    run_root.mkdir()
    logs = run_root / "logs"
    logs.mkdir()
    dist = run_root / "dist"
    extracted = run_root / "extracted"
    extracted.mkdir()
    environment = os.environ.copy()
    environment.pop("UV_PROJECT_ENVIRONMENT", None)

    _run(
        [
            sys.executable,
            str(_BUILDER),
            "--cohort-dir",
            str(cohort.directory),
            "--dist-dir",
            str(dist),
        ],
        cwd=_REPO_ROOT,
        env=environment,
        log=logs / "build.log",
        timeout=timeout_seconds,
    )
    bundle = dist / f"cadrumo-{cohort.version}.mcpb"
    if not bundle.is_file():
        raise SystemExit(f"MCPB builder produced no expected bundle: {bundle}")
    with zipfile.ZipFile(bundle) as archive:
        expected_wheels = {
            cohort.root_wheel.name: cohort.root_wheel,
            cohort.manuals_wheel.name: cohort.manuals_wheel,
            cohort.official_wheel.name: cohort.official_wheel,
        }
        for filename, source in expected_wheels.items():
            member = f"artifacts/{filename}"
            if archive.read(member) != source.read_bytes():
                raise SystemExit(f"MCPB changed canonical cohort bytes for {member}")
        archive.extractall(extracted)
    _run(
        [
            *_npx_argv(npx),
            "-y",
            f"@anthropic-ai/mcpb@{_MCPB_CLI_VERSION}",
            "validate",
            str(extracted),
        ],
        cwd=run_root,
        env=environment,
        log=logs / "official-validate.log",
        timeout=timeout_seconds,
    )
    manifest = json.loads((extracted / "manifest.json").read_text(encoding=_UTF_8))
    server = manifest["server"]["mcp_config"]
    expected_args = ["run", "--directory", "${__dirname}", "src/server.py"]
    expected_sha256 = {
        "cadrumo": cohort.sha256["cadrumo"],
        "cadrumo-data-manuals": cohort.sha256["cadrumo-data-manuals"],
        "cadrumo-data-official": cohort.sha256["cadrumo-data-official"],
    }
    if server != {
        "command": "uv",
        "args": expected_args,
        "env": {
            "CADRUMO_MCP_COHORT_SHA256": json.dumps(
                expected_sha256,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "CADRUMO_LOCAL_STORAGE_ROOT": "${user_config.storage_root}",
            "CADRUMO_MCP_REQUIRED_VERSION": cohort.version,
            "CADRUMO_MCP_PERSONA": "${user_config.persona}",
            "CADRUMO_MCP_SURFACE": "${user_config.surface}",
        },
    }:
        raise SystemExit(f"built MCPB launch contract drifted: {server!r}")
    storage_root = run_root / "storage"
    user_config = {
        "persona": "",
        "storage_root": str(storage_root),
        "surface": "full",
    }
    server_args = tuple(
        _resolve_mcpb_value(
            value,
            extension_dir=extracted,
            user_config=user_config,
        )
        for value in server["args"]
    )
    resolved_environment = {
        key: _resolve_mcpb_value(
            value,
            extension_dir=extracted,
            user_config=user_config,
        )
        for key, value in server["env"].items()
    }
    hostile_platform_root = run_root / "platform-data-with-retired-state"
    if sys.platform == "win32":
        former_product_root = hostile_platform_root / "aeat"
        canonical_product_root = hostile_platform_root / "cadrumo"
        resolved_environment["LOCALAPPDATA"] = str(hostile_platform_root)
    elif sys.platform == "darwin":
        hostile_home = run_root / "home-with-retired-state"
        former_product_root = hostile_home / "Library" / "Application Support" / "aeat"
        canonical_product_root = hostile_home / "Library" / "Application Support" / "cadrumo"
        resolved_environment["HOME"] = str(hostile_home)
    else:
        former_product_root = hostile_platform_root / "aeat"
        canonical_product_root = hostile_platform_root / "cadrumo"
        resolved_environment["XDG_DATA_HOME"] = str(hostile_platform_root)
    former_product_root.mkdir(parents=True)
    former_marker = former_product_root / "custody-marker.bin"
    former_marker_bytes = b"retired-aeat-state-must-remain-byte-identical"
    former_marker.write_bytes(former_marker_bytes)
    if "UV_PROJECT_ENVIRONMENT" in resolved_environment:
        raise SystemExit("MCPB must use the client-provisioned bundle environment")
    runtime_environment = extracted / ".venv"
    launch_environment = {**environment, **resolved_environment}
    _run(
        [str(uv), "sync", "--directory", str(extracted)],
        cwd=run_root,
        env=launch_environment,
        log=logs / "client-provision.log",
        timeout=timeout_seconds,
    )
    _run_concurrent_launches(
        [str(uv), *server_args],
        cwd=run_root,
        env=launch_environment,
        logs=logs,
        timeout=timeout_seconds,
    )
    work_dir = run_root / "external-work"
    evidence = run_installed_mcp_oracle(
        uv,
        server_args=server_args,
        environment_overrides=resolved_environment,
        storage_root=storage_root,
        work_dir=work_dir,
        timeout_seconds=timeout_seconds,
    )
    if not runtime_environment.is_dir():
        raise SystemExit(
            f"stamped MCPB runtime environment was not provisioned: {runtime_environment}",
        )
    if evidence.target_value != "23000.00":
        raise SystemExit(f"MCPB tax oracle returned unexpected evidence: {evidence.to_jsonable()!r}")
    if former_marker.read_bytes() != former_marker_bytes:
        raise SystemExit("MCPB launch mutated retired aeat state")
    if canonical_product_root.exists():
        raise SystemExit(
            "MCPB launch wrote through the implicit installed-product root instead "
            f"of the selected project-independent state root: {canonical_product_root}",
        )
    if extracted in storage_root.parents or storage_root in extracted.parents:
        raise SystemExit("MCPB state root must be independent from the unpacked extension")
    if work_dir in storage_root.parents or storage_root in work_dir.parents:
        raise SystemExit("MCPB state root must be independent from the client work directory")
    evidence_path = run_root / "mcpb-assembly-runtime-evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "bundle": str(bundle),
                "bundle_sha256": _sha256(bundle),
                "bundle_size": bundle.stat().st_size,
                "cohort": {
                    "source_commit": cohort.source_commit,
                    "version": cohort.version,
                    "sha256": cohort.sha256,
                },
                "manifest": manifest,
                "resolved_launch": {
                    "args": server_args,
                    "env": resolved_environment,
                },
                "mcp_oracle": asdict(evidence),
                "official_validator": f"@anthropic-ai/mcpb@{_MCPB_CLI_VERSION}",
                "proof": {
                    "archive_construction": "passed",
                    "client_style_provisioning": "passed into bundle .venv",
                    "concurrent_server_launches": "passed",
                    "bundle_runtime_oracle": "passed outside a desktop client",
                    "project_independent_state": str(storage_root),
                    "retired_default_state_refusal_isolated": str(former_product_root),
                    "client_installation": "not run",
                    "publisher_signature": "unsigned",
                    "support_claim": "none",
                },
                "uv_executable": str(uv),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding=_UTF_8,
    )
    return evidence_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--uv", type=Path, default=Path(shutil.which("uv") or "uv"))
    parser.add_argument("--npx", type=Path, default=Path(shutil.which("npx") or "npx"))
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    return parser


def main() -> int:
    """Run the real MCPB artifact smoke."""
    args = _parser().parse_args()
    evidence = run_mcpb_smoke(
        cohort_dir=args.cohort_dir,
        evidence_dir=args.evidence_dir,
        uv_executable=args.uv,
        npx_executable=args.npx,
        timeout_seconds=args.timeout_seconds,
    )
    print(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
