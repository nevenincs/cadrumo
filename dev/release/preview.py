"""Preview the next version release through a release-please dry run.

PREVIEW-ONLY AND MUTATES NOTHING. The bump is applied by merging the release
pull request, never by this recipe.

The two shell bodies this replaced disagreed on error propagation: the bash one
piped release-please into `tee` under `set -euo pipefail`, so the pipeline's
status was tee's rather than the tool's, while the PowerShell one captured
`$LASTEXITCODE` after `Tee-Object` and did propagate it. One of the two
reported success for a failed dry run.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from dev._paths import REPO_ROOT, UTF_8

#: Where the dry-run transcript is written for review.
LOG_PATH = REPO_ROOT / "var" / "release" / "release-please.log"

#: The pinned release-please major. An unpinned `npx release-please` resolves
#: whatever is newest, which changes the manifest format without warning.
RELEASE_PLEASE = "release-please@16"

REPO_URL = "nevenincs/cadrumo"
TARGET_BRANCH = "main"


def _require(tool: str, remedy: str) -> str | None:
    """Return an error message when ``tool`` is absent, otherwise ``None``.

    Args:
        tool: The executable to look for on ``PATH``.
        remedy: What the operator should do about its absence.

    Returns:
        The message to report, or ``None`` when the tool is present.
    """
    if shutil.which(tool) is None:
        return f"{tool} not on PATH - {remedy}"
    return None


def _github_token() -> tuple[str | None, str | None]:
    """Read a GitHub token from the authenticated `gh` CLI.

    Returns:
        A ``(token, error)`` pair; exactly one is not ``None``.
    """
    try:
        completed = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return None, f"gh could not be executed: {exc}"
    token = completed.stdout.strip()
    if completed.returncode != 0 or not token:
        return None, "gh auth token failed - run 'gh auth login' first."
    return token, None


def preview() -> int:
    """Run the release-please dry run and tee its output to the log.

    Returns:
        release-please's own exit code, or 1 when a prerequisite is missing.
        The tool's status propagates - a failed dry run is not a successful
        preview, which is what one of the two shell bodies used to report.
    """
    for tool, remedy in (
        ("node", "install Node.js to use release-please (npx)."),
        ("gh", "install the GitHub CLI and run 'gh auth login'."),
    ):
        problem = _require(tool, remedy)
        if problem is not None:
            print(problem, file=sys.stderr, flush=True)
            return 1

    token, error = _github_token()
    if token is None:
        print(error, file=sys.stderr, flush=True)
        return 1

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        "npx",
        "--yes",
        RELEASE_PLEASE,
        "release-pr",
        "--token",
        token,
        "--repo-url",
        REPO_URL,
        "--target-branch",
        TARGET_BRANCH,
        "--config-file",
        "release-please-config.json",
        "--manifest-file",
        ".release-please-manifest.json",
        "--dry-run",
        "--debug",
    ]
    print(
        f"> release-please release-pr --dry-run --debug (output -> {LOG_PATH})",
        flush=True,
    )

    # The token is in argv, so the transcript must not echo the command line.
    resolved = shutil.which("npx")
    if resolved is None:
        print("npx not found on PATH", file=sys.stderr, flush=True)
        return 1
    completed = subprocess.run(
        [resolved, *argv[1:]],
        capture_output=True,
        text=True,
        check=False,
    )
    transcript = completed.stdout + completed.stderr
    LOG_PATH.write_text(transcript, encoding=UTF_8)
    print(transcript, end="", flush=True)

    if completed.returncode != 0:
        print(
            f"release-please dry run failed (exit {completed.returncode}) - see {LOG_PATH}",
            file=sys.stderr,
            flush=True,
        )
        return completed.returncode

    print(
        f"dry-run complete - review {LOG_PATH}. Merging the release pull "
        "request applies the bump; this recipe is preview-only and mutates "
        "nothing.",
        flush=True,
    )
    return 0
