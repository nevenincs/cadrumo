"""The one ``gh`` release-asset boundary the release flows share.

The draft-release evidence transport is retired: the repository is public,
Actions artifacts are available again, and an artifact cannot be attached to a
run that did not produce it, so the layered release-to-run and manifest checks
collapse into the Actions-API identity assertion that was always the anchor.
The sealing, manifest-verification and garbage-collection surfaces that existed
to make draft releases trustworthy therefore have no callers and are gone.

What survives is the transport itself, and it survives because one consumer
still genuinely needs it: the operator's locally-minted evidence release has no
backing run, so it stays a release download rather than an artifact download.
The release-candidate, seal and soak flows all reach GitHub through that same
boundary, and they live here, which is why this module does too.

Retrying is deliberately confined to the transport. :func:`list_releases` calls
the subprocess helper directly rather than through the retry wrapper, so a
listing that informs a trust decision can never be papered over by a retry;
:func:`download_release_assets` is a pure fetch and is retried.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from enum import StrEnum
from pathlib import Path
from typing import Final

_RUN_NUMBER_PATTERN: Final[str] = r"^[1-9][0-9]*$"

_GH_TIMEOUT_SECONDS: Final[int] = 600
_DOWNLOAD_ATTEMPTS: Final[int] = 3
_DOWNLOAD_RETRY_SECONDS: Final[float] = 5.0


class EvidenceLane(StrEnum):
    """Closed set of producing workflows whose evidence a release flow reads."""

    SMOKE = "smoke"
    SCOOP = "scoop"
    HOMEBREW = "homebrew"
    CLAUDE = "claude"


class ReleaseAssetTransportError(ValueError):
    """A transport invariant failed; the message names the mismatch."""


def evidence_tag(lane: EvidenceLane, run_id: str) -> str:
    """Return the evidence tag for one producing run (``evidence-<lane>-<run_id>``)."""
    if re.fullmatch(_RUN_NUMBER_PATTERN, run_id) is None:
        raise ReleaseAssetTransportError(f"run id must be one positive workflow run id, got {run_id!r}")
    return f"evidence-{lane.value}-{run_id}"


def _run_gh(gh: str, arguments: list[str], *, timeout_seconds: int = _GH_TIMEOUT_SECONDS) -> str:
    """Run one real ``gh`` subprocess and return stdout, raising on failure.

    ``timeout_seconds`` is injectable so the retry helper's timeout path can be
    exercised against a real slow subprocess rather than a simulated one; every
    production caller takes the default.
    """
    completed = subprocess.run(
        [gh, *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        raise ReleaseAssetTransportError(
            f"gh {' '.join(arguments)} failed (rc={completed.returncode}): {completed.stderr.strip()[:500]}",
        )
    return completed.stdout


def resolve_gh(explicit: str | None) -> str:
    """Resolve the ``gh`` executable, honouring an explicit path for tests."""
    if explicit is not None:
        return explicit
    resolved = shutil.which("gh")
    if resolved is None:
        raise ReleaseAssetTransportError("gh is not on PATH; pass --gh with an explicit executable")
    return resolved


def _is_deterministic_gh_failure(message: str) -> bool:
    """Return whether a ``gh`` failure will fail identically however often it is retried.

    Authorization and not-found failures are decisions the API has already made:
    retrying one only delays the report and burns the backoff budget. Anything
    unrecognised stays retryable, so an unenumerated transient keeps today's
    behaviour rather than becoming a new hard failure.
    """
    haystack = message.lower()
    return any(
        marker in haystack
        for marker in (
            "http 401",
            "http 403",
            "http 404",
            "bad credentials",
            "requires authentication",
            "gh auth login",
            "not logged into",
        )
    )


def run_gh_with_retry(gh: str, arguments: list[str], *, timeout_seconds: int = _GH_TIMEOUT_SECONDS) -> str:
    """Run ``gh`` with a short bounded retry for transient API failures.

    Retries the TRANSPORT only. A timeout is the most retryable failure there
    is, so :class:`subprocess.TimeoutExpired` is converted and retried here
    rather than escaping uncaught. A deterministic authorization or not-found
    failure is raised on the first attempt: it cannot succeed on the third, and
    delaying it behind two backoffs only obscures the diagnosis.

    Retrying is never a substitute for surfacing: every exhausted failure raises
    carrying the last error verbatim. Trust decisions deliberately do NOT come
    through here -- :func:`list_releases` calls :func:`_run_gh` directly, so no
    retry can paper over a state that must never be trusted.
    """
    last_error: ReleaseAssetTransportError | None = None
    for attempt in range(1, _DOWNLOAD_ATTEMPTS + 1):
        try:
            return _run_gh(gh, arguments, timeout_seconds=timeout_seconds)
        except subprocess.TimeoutExpired as timeout:
            last_error = ReleaseAssetTransportError(
                f"gh {' '.join(arguments)} timed out after {timeout_seconds}s: {timeout}",
            )
        except ReleaseAssetTransportError as error:
            if _is_deterministic_gh_failure(str(error)):
                raise
            last_error = error
        if attempt < _DOWNLOAD_ATTEMPTS:
            time.sleep(_DOWNLOAD_RETRY_SECONDS * attempt)
    raise ReleaseAssetTransportError(f"gh failed after {_DOWNLOAD_ATTEMPTS} attempts: {last_error}")


def download_release_assets(gh: str, *, repository: str, tag: str, patterns: list[str], directory: Path) -> None:
    """Download the tag's assets (all, or per pattern) into ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    base = ["release", "download", tag, "--repo", repository, "--dir", str(directory), "--clobber"]
    if patterns:
        for pattern in patterns:
            run_gh_with_retry(gh, [*base, "--pattern", pattern])
    else:
        run_gh_with_retry(gh, base)


def list_releases(gh: str, repository: str) -> list[dict[str, object]]:
    """Return every release record (drafts included), paginated past 100.

    Pagination matters: softprops/action-gh-release#602 documents duplicate
    draft creation precisely because a lookup stopped at the first page.
    """
    raw = _run_gh(
        gh,
        [
            "api",
            f"repos/{repository}/releases?per_page=100",
            "--paginate",
            "--jq",
            ".[] | {tag_name, draft, created_at}",
        ],
    )
    return [json.loads(line) for line in raw.splitlines() if line.strip()]
