"""Build, validate, provision, and exercise one cohort-bound Cadrumo MCPB."""

from __future__ import annotations

import argparse
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
if not __package__:
    __package__ = "dev.packaging"

from ._command import CommandResult, run_command  # noqa: E402
from ._hashing import sha256_path  # noqa: E402
from .cohort_manifest import load_release_cohort  # noqa: E402
from .constraint_effect import assert_installed_matches_constraints  # noqa: E402
from .installed_mcp_oracle import run_installed_mcp_oracle  # noqa: E402
from .python_cohort import load_python_cohort  # noqa: E402
from .runtime_wheelhouse import load_runtime_wheelhouse  # noqa: E402

_UTF_8: Final[str] = "utf-8"
MCPB_CLI_VERSION: Final[str] = "2.1.2"


def _run(argv: list[str], *, cwd: Path, env: dict[str, str], log: Path, timeout: float) -> CommandResult:
    completed = run_command(argv, cwd=cwd, environment=env, timeout_seconds=timeout)
    log.write_text(
        f"argv={json.dumps(argv)}\n"
        f"cwd={cwd}\n"
        f"exit_code={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}\n",
        encoding=_UTF_8,
        newline="\n",
    )
    if completed.returncode != 0:
        raise SystemExit(f"command failed ({completed.returncode}): {argv!r}; retained log: {log}")
    return completed


def run_concurrent_launches(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    logs: Path,
    timeout: float,
    count: int = 4,
    label: str = "concurrent",
) -> None:
    """Launch the real server ``count`` times, waiting for each to exit.

    Every server reads ``DEVNULL`` stdin, hits EOF, and exits cleanly, so a launch
    both provisions (on the bundle's first touch, through the bootstrap) and
    returns. ``label`` distinguishes the retained per-launch logs.
    """
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
            failures.append(f"{label} launch {index} timed out")
        log = logs / f"{label}-launch-{index}.log"
        log.write_text(
            f"argv={json.dumps(argv)}\n"
            f"cwd={cwd}\n"
            f"exit_code={process.returncode}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}\n",
            encoding=_UTF_8,
            newline="\n",
        )
        if process.returncode != 0:
            failures.append(f"{label} launch {index} exited {process.returncode}; retained log: {log}")
    if failures:
        raise SystemExit("; ".join(failures))


def _npx_argv(npx: Path) -> list[str]:
    r"""Return a directly executable NPX argv on POSIX and Windows.

    A Windows ``npx.cmd`` is a shim whose real interpreter layout depends on
    the install kind: a native Node install (and setup-node's tool cache)
    keeps ``node.exe`` and npm's ``npx-cli.js`` beside the shim, while an
    npm-global-prefix directory (``npm prefix --global``, e.g.
    ``%APPDATA%\\npm``) holds ONLY shims — its ``node.exe`` lives with the
    Node installation and ``npx-cli.js`` with that installation's bundled npm
    (or under ``npm root --global`` when npm itself was installed globally).
    Probe the beside layout first, then fall back to the PATH-resolved node's
    installation, then to the npm global root, refusing with every probed
    path named.
    """
    if npx.suffix.casefold() not in {".cmd", ".bat", ".ps1"}:
        return [str(npx)]
    probed: list[Path] = []
    nodes: list[Path] = []
    for candidate in (npx.parent / "node.exe", *(Path(which) for which in (shutil.which("node"),) if which)):
        if candidate in nodes:
            continue
        if candidate.is_file():
            nodes.append(candidate)
        else:
            probed.append(candidate)
    for node in nodes:
        cli = node.parent / "node_modules" / "npm" / "bin" / "npx-cli.js"
        if cli.is_file():
            return [str(node), str(cli)]
        probed.append(cli)
    npm = shutil.which("npm")
    if nodes and npm is not None:
        completed = run_command([npm, "root", "--global"], cwd=_REPO_ROOT, timeout_seconds=60)
        global_root = completed.stdout.strip()
        if completed.returncode == 0 and global_root:
            cli = Path(global_root) / "npm" / "bin" / "npx-cli.js"
            if cli.is_file():
                return [str(nodes[0]), str(cli)]
            probed.append(cli)
    raise SystemExit(
        f"could not resolve a node interpreter with npm's npx-cli.js for the shim {npx}; probed: "
        + ", ".join(str(path) for path in probed),
    )


def resolve_mcpb_value(
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
    release_cohort_dir: Path,
    evidence_dir: Path,
    uv_executable: Path,
    npx_executable: Path,
    timeout_seconds: float,
) -> Path:
    """Exercise the exact MCPB launch contract through a real MCP tax oracle."""
    release = load_release_cohort(release_cohort_dir)
    cohort = load_python_cohort(release.artifact("python-cohort-manifest").parent)
    uv = uv_executable.expanduser().resolve(strict=True)
    npx = npx_executable.expanduser().resolve(strict=True)
    evidence_root = evidence_dir.resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    run_root = evidence_root / f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    run_root.mkdir()
    logs = run_root / "logs"
    logs.mkdir()
    # The extraction dir DELIBERATELY contains a space: every real client
    # install lives under a spaced path ("...\\Claude Extensions\\..."), and
    # an unquoted-argv launch defect (os.execv word-splitting on Windows)
    # shipped invisibly because this smoke's paths were space-free.
    extracted = run_root / "extracted bundle"
    extracted.mkdir()
    environment = os.environ.copy()
    environment.pop("UV_PROJECT_ENVIRONMENT", None)
    poison = run_root / "poison-ambient-editable"
    (poison / "cadrumo_harness").mkdir(parents=True)
    (poison / "cadrumo_harness" / "__init__.py").write_text(
        "raise RuntimeError('ambient editable Cadrumo harness was imported')\n",
        encoding=_UTF_8,
    )
    environment["PYTHONPATH"] = str(poison)
    environment["UV_CACHE_DIR"] = str(run_root / "empty-uv-cache")
    environment["UV_OFFLINE"] = "1"
    environment["UV_NO_INDEX"] = "1"

    bundle = release.artifact("mcpb")
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise SystemExit("sealed MCPB contains duplicate archive members")
        expected_wheels = {
            cohort.root_wheel.name: cohort.root_wheel,
            cohort.harness_wheel.name: cohort.harness_wheel,
            cohort.manuals_wheel.name: cohort.manuals_wheel,
            cohort.official_wheel.name: cohort.official_wheel,
        }
        for filename, source in expected_wheels.items():
            member = f"artifacts/{filename}"
            if archive.read(member) != source.read_bytes():
                raise SystemExit(f"MCPB changed canonical cohort bytes for {member}")
        wheelhouse = load_runtime_wheelhouse(cohort.runtime_wheelhouse)
        with zipfile.ZipFile(cohort.runtime_wheelhouse) as source_wheelhouse:
            for filename in wheelhouse.manifest["wheels"]:
                expected = source_wheelhouse.read(f"wheels/{filename}")
                if archive.read(f"artifacts/wheelhouse/{filename}") != expected:
                    raise SystemExit(f"MCPB changed sealed runtime wheel bytes: {filename}")
        for name in names:
            member = Path(*name.split("/"))
            if member.is_absolute() or ".." in member.parts:
                raise SystemExit(f"sealed MCPB contains an unsafe member: {name!r}")
            if name.endswith("/"):
                continue
            target = extracted / member
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    _run(
        [
            *_npx_argv(npx),
            "-y",
            f"@anthropic-ai/mcpb@{MCPB_CLI_VERSION}",
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
    expected_args = ["run", "--no-project", "--directory", "${__dirname}", "src/server.py"]
    expected_sha256 = {
        "cadrumo": cohort.sha256["cadrumo"],
        "cadrumo-harness": cohort.sha256["cadrumo-harness"],
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
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": "",
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
        resolve_mcpb_value(
            value,
            extension_dir=extracted,
            user_config=user_config,
        )
        for value in server["args"]
    )
    resolved_environment = {
        key: resolve_mcpb_value(
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
    provision_marker = runtime_environment / ".cadrumo-cohort"
    launch_environment = {**environment, **resolved_environment}
    # No pre-sync: the FIRST launch of the manifest command must exercise the
    # bootstrap's own once-per-install provisioning, exactly as a real client's
    # first `uv run --no-project` does (Desktop extracts and immediately launches;
    # the first launch provisions). The launch reads DEVNULL stdin, so the server
    # provisions, starts, hits EOF, and exits.
    run_concurrent_launches(
        [str(uv), *server_args],
        cwd=run_root,
        env=launch_environment,
        logs=logs,
        timeout=timeout_seconds,
        count=1,
        label="first",
    )
    if not runtime_environment.is_dir():
        raise SystemExit(f"bootstrap first launch did not provision the bundle venv: {runtime_environment}")
    if not provision_marker.is_file():
        raise SystemExit(f"bootstrap first launch wrote no cohort marker: {provision_marker}")
    first_marker_mtime_ns = provision_marker.stat().st_mtime_ns
    # The SECOND launch must direct-exec the provisioned interpreter with NO
    # re-resolution: the bootstrap only rewrites the cohort marker when it
    # provisions, so an unchanged marker mtime proves the second launch skipped
    # provisioning entirely (the robustness research F4 remedy - no per-session
    # `uv run` project resolution after the first).
    run_concurrent_launches(
        [str(uv), *server_args],
        cwd=run_root,
        env=launch_environment,
        logs=logs,
        timeout=timeout_seconds,
        count=1,
        label="second",
    )
    if provision_marker.stat().st_mtime_ns != first_marker_mtime_ns:
        raise SystemExit("bootstrap second launch re-provisioned instead of direct-execing the venv")
    run_concurrent_launches(
        [str(uv), *server_args],
        cwd=run_root,
        env=launch_environment,
        logs=logs,
        timeout=timeout_seconds,
    )
    # The bundle pinned its runtime closure through the ``[tool.uv]
    # constraint-dependencies`` block; observe the provisioned interpreter's
    # actual installed set matches that pinned closure before the tax oracle can
    # mint evidence on it. The bundle ships the same constraints.txt for
    # transparency, so it is the constraint set of record here.
    bundle_python = runtime_environment / ("Scripts" if os.name == "nt" else "bin")
    bundle_python /= "python.exe" if os.name == "nt" else "python"
    assert_installed_matches_constraints(
        bundle_python,
        (extracted / "constraints.txt").read_text(encoding=_UTF_8).splitlines(),
    )
    work_dir = run_root / "external-work"
    evidence = run_installed_mcp_oracle(
        uv,
        server_args=server_args,
        environment_overrides=resolved_environment,
        storage_root=storage_root,
        work_dir=work_dir,
        cohort_source_commit=cohort.source_commit,
        cohort_manifest_sha256=sha256_path(cohort.manifest),
        cohort_root_wheel_sha256=cohort.sha256["cadrumo"],
        cohort_harness_wheel_sha256=cohort.sha256["cadrumo-harness"],
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
                "bundle_sha256": sha256_path(bundle),
                "bundle_size": bundle.stat().st_size,
                "cohort": {
                    "source_commit": cohort.source_commit,
                    "version": cohort.version,
                    "sha256": cohort.sha256,
                    "release_cohort_sha256": sha256_path(release.manifest_path),
                },
                "manifest": manifest,
                "resolved_launch": {
                    "args": server_args,
                    "env": resolved_environment,
                },
                "mcp_oracle": asdict(evidence),
                "official_validator": f"@anthropic-ai/mcpb@{MCPB_CLI_VERSION}",
                "proof": {
                    "archive_construction": "passed",
                    "first_launch_provisioning": "passed into bundle .venv",
                    "second_launch_direct_exec": "passed with no re-resolution",
                    "concurrent_server_launches": "passed",
                    "constraint_effect": "passed against the provisioned bundle interpreter",
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
        newline="\n",
    )
    return evidence_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-cohort-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--uv", type=Path, default=Path(shutil.which("uv") or "uv"))
    parser.add_argument("--npx", type=Path, default=Path(shutil.which("npx") or "npx"))
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    return parser


def main() -> int:
    """Run the real MCPB artifact smoke."""
    args = _parser().parse_args()
    evidence = run_mcpb_smoke(
        release_cohort_dir=args.release_cohort_dir,
        evidence_dir=args.evidence_dir,
        uv_executable=args.uv,
        npx_executable=args.npx,
        timeout_seconds=args.timeout_seconds,
    )
    print(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
