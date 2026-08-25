"""Seal a release candidate from a concluded packaging campaign, then stop.

This is the orchestrator's terminal stage. It reads the sealed cohort's own
manifest to learn the version, cohort id, and source commit -- never re-deriving
them from the working tree, which after a bump is the same tree but is not the
authority -- records the acquisition run ids the chain produced, computes the
soak deadline from the release checklist, and publishes the candidate onto its
own draft release.

Then the run ends. The soak is crossed by ``release-soak-promoter.yml``, because
no run spans 48-72 hours and a job that waited would hold one of four shared
self-hosted runners for days.

See Also:
    :func:`dev.release.release_candidate.seal_candidate`
        The record this stage mints.
"""

from __future__ import annotations

import argparse
import json
import os
import tarfile
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from .._paths import REPO_ROOT, UTF_8
from ..docs.download_matrix import claimed_channels, load_descriptor
from ._asset_transport import (
    EvidenceLane,
    download_release_assets,
    evidence_tag,
    resolve_gh,
)
from .release_candidate import (
    ReleaseCandidateError,
    load_soak_window,
    publish_candidate,
    seal_candidate,
)

_UTF_8 = UTF_8
_COHORT_ARCHIVE = "cadrumo-release-cohort.tar.gz"
_COHORT_MANIFEST = "release-cohort.json"


def _cohort_identity(directory: Path) -> tuple[str, str, str]:
    """Return (cohort_id, version, source_commit) from the sealed cohort manifest.

    Read from the COHORT, not the checkout. After a bump the working tree
    carries the same version, so re-deriving would usually agree -- and would
    silently disagree in exactly the case that matters, when the campaign built
    something other than what this run believes it built.
    """
    manifest_path = directory / _COHORT_MANIFEST
    if not manifest_path.is_file():
        raise ReleaseCandidateError(f"sealed cohort carries no {_COHORT_MANIFEST}; refusing to guess its identity")
    payload = json.loads(manifest_path.read_text(encoding=_UTF_8))
    try:
        return str(payload["cohort_id"]), str(payload["version"]), str(payload["source"]["commit"])
    except (KeyError, TypeError) as error:
        raise ReleaseCandidateError(f"sealed cohort manifest is missing {error}") from error


def main(argv: Sequence[str] | None = None) -> int:
    """Seal the candidate for a concluded campaign and end the orchestration."""
    parser = argparse.ArgumentParser(description="Seal a release candidate and stop.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--packaging-run-id", required=True)
    parser.add_argument("--dry-run", default="false")
    parser.add_argument("--gh", default=None)
    args = parser.parse_args(argv)

    dry_run = str(args.dry_run).strip().lower() == "true"

    repo_root = REPO_ROOT
    descriptor = load_descriptor()

    with tempfile.TemporaryDirectory() as scratch:
        workspace = Path(scratch)
        raw = workspace / "raw"
        cohort = workspace / "cohort"
        raw.mkdir(parents=True, exist_ok=True)
        cohort.mkdir(parents=True, exist_ok=True)

        download_release_assets(
            resolve_gh(args.gh),
            repository=args.repository,
            tag=evidence_tag(EvidenceLane.SMOKE, args.packaging_run_id),
            patterns=[_COHORT_ARCHIVE],
            directory=raw,
        )
        with tarfile.open(raw / _COHORT_ARCHIVE) as archive:
            archive.extractall(cohort, filter="data")

        cohort_id, version, source_commit = _cohort_identity(cohort)
        candidate = seal_candidate(
            cohort_id=cohort_id,
            version=version,
            source_commit=source_commit,
            packaging_run_id=args.packaging_run_id,
            claimed_channels=tuple(sorted(channel.id for channel in claimed_channels(descriptor))),
            dry_run=dry_run,
            window=load_soak_window(repo_root),
            opened_at=datetime.now(UTC),
            scoop_run_id=os.environ.get("SCOOP_RUN_ID", ""),
            homebrew_run_id=os.environ.get("HOMEBREW_RUN_ID", ""),
        )
        tag = publish_candidate(
            candidate,
            repository=args.repository,
            staging_directory=workspace / "stage",
            gh_executable=args.gh,
        )

    print(f"sealed {candidate.version} as {tag}; soak closes {candidate.soak_deadline.isoformat()}")
    print("orchestration complete: the soak promoter resumes this release when its window closes")
    return 0


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
