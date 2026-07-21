"""Repo-wide privacy lint: committed text must carry no operator-identifying data.

The operator directive is that every committed document is free of *actual*
identifying data — machine host names, OS login user names, home-directory
paths, and private/tailnet network identifiers. This gate is the standing guard
that keeps the tree clean after the one-off scrub: it fails the moment a banned
token reappears in any tracked file.

Scope and judgement:

- It bans leaked *machine/login/network* tokens, not deliberate published
  attribution. The project's public copyright holder / privacy responsible
  party ("Gergely Wootsch") and the published contact address on the neve.md
  domain are legally load-bearing attribution carried in NOTICE, PRIVACY.md,
  the frontend, and license-chain tests; they are intentionally public and are
  NOT banned here.
- Runner *labels* (``[self-hosted, Linux, X64]``) are GitHub configuration, not
  machine names, and are untouched.

The banned tokens are assembled from fragments at runtime so this file itself
contains none of them verbatim — the scan therefore covers this gate too,
without a self-exclusion.

Implementation note: the scan shells out to ``git grep`` (fixed-string and ERE
modes, ``-I`` to skip binary blobs) over the tracked working tree, which is far
faster than reading every tracked file in Python.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _repo_root() -> Path:
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],  # noqa: S607 - git resolved from PATH like every dev gate
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return Path(top)


# Fixed-string banned tokens, assembled from fragments so the literal never
# appears in this source file. Each is leaked machine / login / path metadata.
_BANNED_LITERALS: tuple[str, ...] = (
    "gw-" "workstation",          # operator Windows/WSL build-host name
    "macbook-" "neo",             # operator macOS build-host name
    "gw-" "macbook",              # operator macOS build-host name (variant)
    "gergelys-" "macbook",        # operator macOS build-host name (variant)
    "wger" "gely",                # operator VCS / account login handle
    "C:\\Users\\" "hello",        # operator Windows home path (backslash form)
    "C:/Users/" "hello",          # operator Windows home path (forward-slash form)
    "/home/" "hello",             # operator Linux home path
    "/Users/" "gergely",          # operator macOS home path
)

# ERE banned patterns for network identifiers.
_BANNED_PATTERNS: tuple[str, ...] = (
    # Tailscale MagicDNS tailnet domains.
    r"\.ts\.net\b",
    # CGNAT / tailnet address range (100.64/10 through 100.127).
    r"\b100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.[0-9]{1,3}\.[0-9]{1,3}\b",
)

# Exact (relative-path, token) exemptions for genuine functional survivors, each
# with a stated reason. Empty today: the scrub left no functional survivor that
# still carries a banned token. A future functional survivor (e.g. a runner name
# that GitHub's registry requires verbatim) is recorded here, never by weakening
# the token list.
_ALLOWLIST: dict[tuple[str, str], str] = {}


def _git_grep(root: Path, args: list[str]) -> list[str]:
    """Return ``path:line:content`` hits, or [] when git grep finds nothing."""
    result = subprocess.run(  # noqa: S603 - fixed git argv over the tracked tree
        ["git", "grep", "-n", "-I", *args],  # noqa: S607 - git resolved from PATH like every dev gate
        cwd=root,
        capture_output=True,
        text=True,
        errors="replace",
    )
    # git grep exits 1 with no output when there are no matches.
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git grep failed: {result.stderr}")
    return [line for line in result.stdout.splitlines() if line]


def _is_allowlisted(hit: str, token: str) -> bool:
    path = hit.split(":", 1)[0]
    return (path, token) in _ALLOWLIST


def test_no_operator_identifying_tokens_in_tracked_files() -> None:
    """No tracked file may carry a leaked host / login / path / network token."""
    root = _repo_root()
    offenders: list[str] = []

    for token in _BANNED_LITERALS:
        for hit in _git_grep(root, ["-F", "-e", token]):
            if not _is_allowlisted(hit, token):
                offenders.append(f"[{token!r}] {hit}")

    for pattern in _BANNED_PATTERNS:
        for hit in _git_grep(root, ["-E", "-e", pattern]):
            if not _is_allowlisted(hit, pattern):
                offenders.append(f"[/{pattern}/] {hit}")

    assert not offenders, (
        "Operator-identifying tokens found in committed text. Scrub them "
        "(host/login/path/network data must not ship) or, for a genuine "
        "functional survivor, record it in _ALLOWLIST with a reason:\n"
        + "\n".join(sorted(offenders))
    )
