"""Reacquire the published GitHub release cohort and verify every digest.

This post-publication check downloads every asset attached to the ``v<version>``
GitHub release via ``gh release download``, then proves the promoted release
cohort is served completely and byte-for-byte: every one of the twelve declared
cohort artifacts must be present with its exact manifest size and SHA-256. It is
digest-only — no installed behaviour is repeated here (that is the channel-
specific rows) — and refuses instructively when the tag or an asset is absent
(implements post-release-distribution plan row P03.S15).
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from .._paths import UTF_8
from ._acquire_common import (
    AcquisitionError,
    require_command_succeeded,
    verify_release_download,
)
from ._command import run_command
from .cohort_manifest import load_release_cohort

_UTF_8: Final[str] = UTF_8
_DEFAULT_REPO: Final[str] = "nevenincs/cadrumo"


def _resolve_gh(override: Path | None) -> Path:
    """Resolve the ``gh`` executable from an override or PATH, refusing on absence."""
    if override is not None:
        return override.expanduser().resolve(strict=True)
    found = shutil.which("gh")
    if found is None:
        raise AcquisitionError(
            "gh (GitHub CLI) not found on PATH; install it or pass --gh to verify the published release",
        )
    return Path(found).resolve(strict=True)


def run_github_release_acquisition(
    *,
    cohort_dir: Path,
    evidence_dir: Path,
    repo: str,
    gh_executable: Path | None,
    timeout_seconds: float,
) -> Path:
    """Download the release cohort for ``v<version>`` and verify every asset.

    Args:
        cohort_dir: The promoted release cohort directory (twelve artifacts).
        evidence_dir: The directory retaining per-run evidence.
        repo: The ``owner/name`` GitHub repository slug hosting the release.
        gh_executable: An explicit ``gh`` path, or ``None`` to resolve from PATH.
        timeout_seconds: Timeout for the ``gh release download`` invocation.

    Returns:
        The path to the retained JSON evidence document.

    Raises:
        AcquisitionError: If the tag is unpublished or any asset drifts.
    """
    cohort = load_release_cohort(cohort_dir)
    gh = _resolve_gh(gh_executable)
    version = cohort.manifest.version
    tag = f"v{version}"
    endpoint = f"{repo}@{tag}"
    evidence_root = evidence_dir.resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    run_root = evidence_root / f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    run_root.mkdir()
    logs = run_root / "logs"
    logs.mkdir()
    download_dir = run_root / "assets"
    download_dir.mkdir()

    completed = run_command(
        [
            str(gh),
            "release",
            "download",
            tag,
            "--repo",
            repo,
            "--dir",
            str(download_dir),
            "--pattern",
            "*",
            "--skip-existing",
        ],
        cwd=run_root,
        timeout_seconds=timeout_seconds,
        errors="replace",
    )
    (logs / "gh-release-download.log").write_text(
        f"exit_code={completed.returncode}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}\n",
        encoding=_UTF_8,
        newline="\n",
    )
    require_command_succeeded(
        returncode=completed.returncode,
        stderr=completed.stderr,
        mechanism="gh release download",
        endpoint=endpoint,
        version=version,
        next_step=f"publish the {tag} GitHub release with every cohort asset and rerun",
    )

    verified = verify_release_download(
        cohort,
        download_dir,
        mechanism="gh release download",
        endpoint=endpoint,
    )

    evidence = {
        "schema": "cadrumo.packaging.acquire-github-release.v1",
        "status": "passed",
        "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "repo": repo,
        "tag": tag,
        "cohort_id": cohort.manifest.cohort_id,
        "version": version,
        "verified_assets": {name: str(path) for name, path in verified.items()},
    }
    evidence_path = run_root / "acquire-github-release-evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    return evidence_path


def _parser() -> argparse.ArgumentParser:
    """Return the argument parser for the GitHub release reacquisition check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-dir", required=True, type=Path, help="Promoted release cohort directory.")
    parser.add_argument("--evidence-dir", required=True, type=Path, help="Directory retaining per-run evidence.")
    parser.add_argument("--repo", default=_DEFAULT_REPO, help="owner/name GitHub repository slug.")
    parser.add_argument("--gh", type=Path, default=None, help="Explicit gh executable (defaults to PATH).")
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the GitHub release reacquisition verification from the command line."""
    args = _parser().parse_args(argv)
    evidence = run_github_release_acquisition(
        cohort_dir=args.cohort_dir,
        evidence_dir=args.evidence_dir,
        repo=args.repo,
        gh_executable=args.gh,
        timeout_seconds=args.timeout_seconds,
    )
    print(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
