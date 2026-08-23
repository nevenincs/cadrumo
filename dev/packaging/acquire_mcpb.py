"""Reacquire the published Cadrumo MCPB and repeat the MCP tax-work oracle.

This post-publication check downloads the published ``.mcpb`` bundle (from an
explicit URL or the ``v<version>`` GitHub release asset), proves its bytes match
the promoted release cohort's declared MCPB digest, then exercises the exact
bundle launch contract through the shared installed MCP oracle: it extracts the
bundle, provisions the client-side runtime on first launch, and repeats the
grounded MCP tax-work call. The oracle and the launch-ceremony helpers are
imported from :mod:`dev.packaging.smoke_mcpb` and
:mod:`dev.packaging.installed_mcp_oracle`, never copied. It refuses instructively
when the bundle is not yet published (implements post-release-distribution plan
rows P03.S19 and P03.S20).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.request
import zipfile
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import version as _package_version
from pathlib import Path
from typing import Final

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if not __package__:
    __package__ = "dev.packaging"

from cadrumo.core import scan_directory  # noqa: E402

from ._acquire_common import (  # noqa: E402
    AcquisitionError,
    capture_owned_server_launch,
    refuse_unavailable,
    require_command_succeeded,
    verify_artifact_digest,
)
from ._command import run_command  # noqa: E402
from ._hashing import sha256_path  # noqa: E402
from .cohort_manifest import LoadedReleaseCohort, load_release_cohort  # noqa: E402
from .distribution_evidence_emit import SDK_CLIENT_NAME, emit_client_evidence  # noqa: E402
from .evidence import (  # noqa: E402
    AcquisitionIdentity,
    ClientIdentity,
    CommandTranscript,
    DestinationIdentity,
)
from .installed_mcp_oracle import (  # noqa: E402
    InstalledMcpEvidence,
    isolated_mcp_environment,
    run_installed_mcp_oracle,
)
from .python_cohort import load_python_cohort  # noqa: E402
from .smoke_mcpb import resolve_mcpb_value, run_concurrent_launches  # noqa: E402

_UTF_8: Final[str] = "utf-8"
_DEFAULT_REPO: Final[str] = "nevenincs/cadrumo"
_DEFAULT_DISTRIBUTION_EVIDENCE_DIR: Final[Path] = Path("var/distribution-install-readiness")
_EXPECTED_TARGET_VALUE: Final[str] = "23000.00"


def expected_mcpb_digest(cohort: LoadedReleaseCohort) -> tuple[str, str]:
    """Return the promoted release cohort's declared MCPB digest and version.

    Args:
        cohort: The loaded release cohort authority.

    Returns:
        A ``(sha256, version)`` tuple for the ``mcpb`` cohort artifact.

    Raises:
        AcquisitionError: If the cohort declares no ``mcpb`` artifact.
    """
    record = next((item for item in cohort.manifest.artifacts if item.name == "mcpb"), None)
    if record is None:
        raise AcquisitionError("release cohort declares no mcpb artifact to verify")
    return record.sha256, cohort.manifest.version


def _download_bundle(
    *,
    mcpb_url: str | None,
    repo: str,
    version: str,
    dist: Path,
    logs: Path,
    gh_executable: Path | None,
    timeout_seconds: float,
) -> Path:
    """Download the published ``.mcpb`` bundle, refusing instructively on absence."""
    dist.mkdir(parents=True, exist_ok=True)
    bundle = dist / f"cadrumo-{version}.mcpb"
    tag = f"v{version}"
    if mcpb_url is not None:
        try:
            with urllib.request.urlopen(mcpb_url, timeout=timeout_seconds) as response:  # noqa: S310 - operator URL
                bundle.write_bytes(response.read())
        except OSError as exc:
            refuse_unavailable(
                mechanism="mcpb download",
                endpoint=mcpb_url,
                version=version,
                reason=f"the bundle URL could not be fetched: {exc}",
                next_step=f"publish cadrumo-{version}.mcpb at {mcpb_url} and rerun",
            )
        return bundle
    resolved_gh = gh_executable.expanduser().resolve(strict=True) if gh_executable is not None else shutil.which("gh")
    if resolved_gh is None:
        raise AcquisitionError("gh not found on PATH; pass --mcpb-url or --gh to fetch the published bundle")
    gh = Path(resolved_gh)
    completed = run_command(
        [
            str(gh),
            "release",
            "download",
            tag,
            "--repo",
            repo,
            "--dir",
            str(dist),
            "--pattern",
            "*.mcpb",
            "--skip-existing",
        ],
        cwd=dist,
        timeout_seconds=timeout_seconds,
        errors="replace",
    )
    (logs / "gh-mcpb-download.log").write_text(
        f"exit_code={completed.returncode}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}\n",
        encoding=_UTF_8,
        newline="\n",
    )
    require_command_succeeded(
        returncode=completed.returncode,
        stderr=completed.stderr,
        mechanism="gh release download",
        endpoint=f"{repo}@{tag}",
        version=version,
        next_step=f"attach cadrumo-{version}.mcpb to the {tag} GitHub release and rerun",
    )
    bundles = scan_directory(dist, pattern="*.mcpb")
    if len(bundles) != 1:
        raise AcquisitionError(f"expected one published .mcpb asset for {tag}; got {[b.name for b in bundles]!r}")
    return bundles[0]


def _exercise_bundle(
    *,
    bundle: Path,
    python_cohort_dir: Path,
    run_root: Path,
    uv: Path,
    logs: Path,
    timeout_seconds: float,
) -> tuple[InstalledMcpEvidence, CommandTranscript]:
    """Extract, provision, and run the MCP oracle against the downloaded bundle.

    Reuses the launch-ceremony helpers and the installed MCP oracle from the
    packaging smoke rather than re-deriving them, so acquisition exercises the
    exact published launch contract.
    """
    cohort = load_python_cohort(python_cohort_dir)
    extracted = run_root / "extracted"
    extracted.mkdir()
    with zipfile.ZipFile(bundle) as archive:
        for distribution, source in {
            cohort.root_wheel.name: cohort.root_wheel,
            cohort.harness_wheel.name: cohort.harness_wheel,
            cohort.manuals_wheel.name: cohort.manuals_wheel,
            cohort.official_wheel.name: cohort.official_wheel,
        }.items():
            member = f"artifacts/{distribution}"
            if archive.read(member) != source.read_bytes():
                raise AcquisitionError(f"published MCPB carries different cohort bytes for {member}")
        archive.extractall(extracted)
    manifest = json.loads((extracted / "manifest.json").read_text(encoding=_UTF_8))
    server = manifest["server"]["mcp_config"]
    if server.get("command") != "uv":
        raise AcquisitionError(f"published MCPB launch command drifted: {server.get('command')!r}")
    storage_root = run_root / "storage"
    user_config = {"persona": "", "storage_root": str(storage_root), "surface": "full"}
    server_args = tuple(
        resolve_mcpb_value(value, extension_dir=extracted, user_config=user_config) for value in server["args"]
    )
    resolved_environment = {
        key: resolve_mcpb_value(value, extension_dir=extracted, user_config=user_config)
        for key, value in server["env"].items()
    }
    first_launch_env = isolated_mcp_environment(storage_root)
    first_launch_env.update(resolved_environment)
    run_concurrent_launches(
        [str(uv), *server_args],
        cwd=run_root,
        env=first_launch_env,
        logs=logs,
        timeout=timeout_seconds,
        count=1,
        label="first",
    )
    evidence = run_installed_mcp_oracle(
        uv,
        server_args=server_args,
        environment_overrides=resolved_environment,
        storage_root=storage_root,
        work_dir=run_root / "external-work",
        cohort_source_commit=cohort.source_commit,
        cohort_manifest_sha256=sha256_path(cohort.manifest),
        cohort_root_wheel_sha256=cohort.sha256["cadrumo"],
        cohort_harness_wheel_sha256=cohort.sha256["cadrumo-harness"],
        timeout_seconds=timeout_seconds,
    )
    if evidence.target_value != _EXPECTED_TARGET_VALUE:
        raise AcquisitionError(f"published MCPB oracle target value drifted: {evidence.target_value!r}")
    # Capture a genuinely-owned bounded launch of the exact bundle server contract
    # AFTER the oracle completes (so the bounded initialize-then-shutdown cannot
    # pollute the oracle's storage): the real subprocess transcript becomes the
    # sole command of the option-A pure-client record.
    launch_env = isolated_mcp_environment(storage_root)
    launch_env.update(resolved_environment)
    launch_transcript = capture_owned_server_launch(
        server=uv,
        server_args=server_args,
        env=launch_env,
        cwd=run_root,
        timeout_seconds=timeout_seconds,
    )
    return evidence, launch_transcript


def run_mcpb_acquisition(
    *,
    cohort_dir: Path,
    evidence_dir: Path,
    mcpb_url: str | None,
    repo: str,
    uv_executable: Path | None,
    gh_executable: Path | None,
    timeout_seconds: float,
    row_id: str | None = None,
    distribution_evidence_dir: Path | None = None,
) -> Path:
    """Download the published MCPB, verify its digest, and repeat the MCP oracle.

    Args:
        cohort_dir: The promoted RELEASE cohort directory (carries the mcpb
            digest; the Python cohort is read from its ``python`` subdirectory).
        evidence_dir: The directory retaining per-run evidence.
        mcpb_url: An explicit published bundle URL, or ``None`` to use ``gh``.
        repo: The ``owner/name`` slug for the ``gh`` release-asset fallback.
        uv_executable: An explicit ``uv`` path, or ``None`` to resolve from PATH.
        gh_executable: An explicit ``gh`` path, or ``None`` to resolve from PATH.
        timeout_seconds: Timeout for downloads, launches, and the MCP oracle.
        row_id: The client row this run proves (required to emit the flat
            client-row record, e.g. ``claude-desktop-mcpb``).
        distribution_evidence_dir: Where the flat record lands; defaults to
            ``var/distribution-install-readiness`` (the directory both gates scan).

    Returns:
        The path to the retained JSON evidence document.

    Raises:
        AcquisitionError: If the bundle is unpublished or its bytes drift.
    """
    cohort = load_release_cohort(cohort_dir)
    expected_sha256, version = expected_mcpb_digest(cohort)
    uv = (uv_executable or Path(shutil.which("uv") or "uv")).expanduser().resolve(strict=True)
    evidence_root = evidence_dir.resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    run_root = evidence_root / f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    run_root.mkdir()
    logs = run_root / "logs"
    logs.mkdir()

    bundle = _download_bundle(
        mcpb_url=mcpb_url,
        repo=repo,
        version=version,
        dist=run_root / "dist",
        logs=logs,
        gh_executable=gh_executable,
        timeout_seconds=timeout_seconds,
    )
    endpoint = mcpb_url if mcpb_url is not None else f"{repo}@v{version}"
    verify_artifact_digest(
        mechanism="mcpb download",
        endpoint=endpoint,
        name="mcpb",
        path=bundle,
        expected_sha256=expected_sha256,
    )
    mcp_evidence, launch_transcript = _exercise_bundle(
        bundle=bundle,
        python_cohort_dir=cohort_dir / "python",
        run_root=run_root,
        uv=uv,
        logs=logs,
        timeout_seconds=timeout_seconds,
    )

    evidence = {
        "schema": "cadrumo.packaging.acquire-mcpb.v1",
        "status": "passed",
        "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "endpoint": endpoint,
        "cohort_id": cohort.manifest.cohort_id,
        "version": version,
        "bundle": str(bundle),
        "verified_mcpb_sha256": expected_sha256,
        "mcp_oracle": asdict(mcp_evidence),
    }
    evidence_path = run_root / "acquire-mcpb-evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )

    if row_id is not None:
        emit_client_evidence(
            directory=(distribution_evidence_dir or _DEFAULT_DISTRIBUTION_EVIDENCE_DIR),
            row_id=row_id,
            cohort=cohort,
            mcp_evidence=mcp_evidence,
            launch_transcript=launch_transcript,
            client=ClientIdentity(
                name=SDK_CLIENT_NAME,
                version=_package_version("mcp"),
                executable=str(uv),
            ),
            acquisition=AcquisitionIdentity(mechanism="mcpb", source=endpoint),
            destination=DestinationIdentity(kind="mcpb-bundle", locator=str(bundle), version=cohort.manifest.version),
        )

    return evidence_path


def _parser() -> argparse.ArgumentParser:
    """Return the argument parser for the MCPB reacquisition check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cohort-dir",
        required=True,
        type=Path,
        help="Promoted release cohort directory (mcpb digest; python cohort in its python/ subdir).",
    )
    parser.add_argument("--evidence-dir", required=True, type=Path, help="Directory retaining per-run evidence.")
    parser.add_argument("--mcpb-url", default=None, help="Explicit published .mcpb URL (else gh release asset).")
    parser.add_argument("--repo", default=_DEFAULT_REPO, help="owner/name slug for the gh release-asset fallback.")
    parser.add_argument("--uv", type=Path, default=None, help="Explicit uv executable (defaults to PATH).")
    parser.add_argument("--gh", type=Path, default=None, help="Explicit gh executable (defaults to PATH).")
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument(
        "--row-id",
        default=None,
        help="Distribution row this run proves (required to emit the flat client record).",
    )
    parser.add_argument(
        "--distribution-evidence-dir",
        type=Path,
        default=None,
        help="Where the flat record lands (defaults to var/distribution-install-readiness).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the MCPB reacquisition verification from the command line."""
    args = _parser().parse_args(argv)
    evidence = run_mcpb_acquisition(
        cohort_dir=args.cohort_dir,
        evidence_dir=args.evidence_dir,
        mcpb_url=args.mcpb_url,
        repo=args.repo,
        uv_executable=args.uv,
        gh_executable=args.gh,
        timeout_seconds=args.timeout_seconds,
        row_id=args.row_id,
        distribution_evidence_dir=args.distribution_evidence_dir,
    )
    print(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
