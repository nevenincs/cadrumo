"""Repo-wide privacy lint: committed text must carry no operator-identifying data.

The operator directive is that every committed document is free of *actual*
identifying data — machine host names, OS login user names, home-directory
paths, and private/tailnet network identifiers. This gate is the standing guard
that keeps the tree clean after the one-off scrub: it fails the moment a banned
token reappears in any tracked file.

Scope and judgement:

- It bans leaked *machine/login/network* tokens, not deliberate published
  attribution. The project's public copyright holder / privacy responsible
  party ("Neve Nincs") and the published ``hello@neve.md`` contact address on
  the neve.md domain are legally load-bearing attribution carried in NOTICE,
  PRIVACY.md, the frontend, and license-chain tests; they are intentionally
  public and are NOT banned here. The retired personal identity that predated
  it is now a privacy leak if it resurfaces in a shipped doc and is banned
  below.
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


def _token(*fragments: str) -> str:
    """Join ``fragments`` into one banned token.

    Every token is split across fragments at its call site and rejoined here at
    runtime, so no banned literal appears whole in this source. That is what
    lets the scan cover this gate too: a self-exclusion would blind it to its
    own regressions, and an inline literal would make it fail on itself.
    """
    return "".join(fragments)


# Fixed-string banned tokens. Each is leaked machine / login / path metadata, or
# a retired public identity that must not resurface in a shipped document.
_BANNED_LITERALS: tuple[str, ...] = (
    _token("gw-", "workstation"),  # operator Windows/WSL build-host name
    _token("macbook", "-neo"),  # operator macOS build-host name
    _token("gw-", "macbook"),  # operator macOS build-host name (variant)
    _token("gergelys", "-macbook"),  # operator macOS build-host name (variant)
    _token("wger", "gely"),  # operator VCS / account login handle
    _token("C:\\Users", "\\hello"),  # operator Windows home path (backslash form)
    _token("C:/Users", "/hello"),  # operator Windows home path (forward-slash form)
    _token("/home", "/hello"),  # operator Linux home path
    _token("/Users", "/gergely"),  # operator macOS home path
)

# Retired public identity, banned in SHIPPED surfaces only. Superseded by
# "Neve Nincs" / hello@neve.md; the old personal name and contact address are a
# privacy leak if they reappear in any published/shipped document. They are
# scanned with .vault/ and .vaultspec/ excluded, because those trees are
# removable development scaffolding whose historical records legitimately retain
# the prior attribution — the exclusion applies ONLY to this retired-identity
# set, never to the machine/login/path tokens above (which stay tree-wide).
_BANNED_IN_SHIPPED_SURFACES: tuple[str, ...] = (
    _token("Gergely", " Wootsch"),  # retired public personal name
    _token("hello@gergely", "-wootsch.com"),  # retired public contact email
)

# Pathspec excluding the removable dev-scaffolding trees for the shipped-only set.
_SCAFFOLDING_EXCLUSIONS: tuple[str, ...] = (":!.vault", ":!.vaultspec")

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


def _probe_repo(root: Path) -> None:
    """Materialise a real git repo carrying one instance of each banned shape.

    Every planted token is assembled through :func:`_token` for the same reason
    the ban list is: a literal here would be a real leak in a tracked file and
    the tree-wide scan would flag this module. The out-of-range addresses are
    written whole because they are not banned and must not match.
    """
    leak = "\n".join(
        (
            f"host {_token('probe-host.tailnet-0000', '.ts', '.net')} answered",
            f"peer {_token('100.', '101.102.103')} answered",
            f"low edge {_token('100.', '64.0.1')} high edge {_token('100.', '127.255.254')}",
            "outside 100.63.0.1 and outside 100.128.0.1",
            f"contact {_BANNED_LITERALS[0]}",
        ),
    )
    (root / "leak.txt").write_text(leak + "\n", encoding="utf-8")
    for argv in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=p@example.invalid", "-c", "user.name=probe", "commit", "-qm", "probe"],
    ):
        subprocess.run(argv, cwd=root, check=True, capture_output=True)  # noqa: S603 - fixed git argv in a temp repo


def test_the_banned_token_sets_are_not_empty() -> None:
    """An emptied ban list disarms the scan while leaving it green."""
    assert len(_BANNED_LITERALS) >= 5
    assert _BANNED_IN_SHIPPED_SURFACES
    assert _BANNED_PATTERNS


def test_the_scan_finds_every_banned_shape_in_a_repository_that_carries_them(tmp_path: Path) -> None:
    """Positive control: the real scan, run against a repo that really leaks.

    The tree-wide assertion below reports zero offenders, which is the same
    result it would report if the patterns had stopped matching or ``git grep``
    had stopped reading anything. Nothing distinguishes a scrubbed tree from a
    blind scan without exercising the scan against a corpus known to contain
    each shape, through the gate's own ``_git_grep``.
    """
    _probe_repo(tmp_path)

    literal_hits = _git_grep(tmp_path, ["-F", "-e", _BANNED_LITERALS[0]])
    assert literal_hits, f"the fixed-string scan no longer finds {_BANNED_LITERALS[0]!r}"

    for pattern in _BANNED_PATTERNS:
        assert _git_grep(tmp_path, ["-E", "-e", pattern]), f"the ERE scan no longer matches {pattern!r}"


def test_the_network_range_pattern_stops_at_its_boundaries(tmp_path: Path) -> None:
    """Negative control: the CGNAT pattern covers 100.64-100.127 and no more.

    A pattern widened to every ``100.x`` address would flag ordinary public
    addresses and get silenced rather than corrected, so both edges are pinned.
    """
    _probe_repo(tmp_path)
    cgnat = next(pattern for pattern in _BANNED_PATTERNS if "12[0-7]" in pattern)
    matched = "\n".join(_git_grep(tmp_path, ["-E", "-e", cgnat]))

    for inside in (_token("100.", "64.0.1"), _token("100.", "127.255.254"), _token("100.", "101.102.103")):
        assert inside in matched, f"{inside} is inside the CGNAT range and must match"
    for outside in ("100.63.0.1", "100.128.0.1"):
        assert outside not in matched, f"{outside} is outside the CGNAT range and must not match"


def test_no_operator_identifying_tokens_in_tracked_files() -> None:
    """No tracked file may carry a leaked host / login / path / network token."""
    root = _repo_root()
    offenders: list[str] = []

    for token in _BANNED_LITERALS:
        for hit in _git_grep(root, ["-F", "-e", token]):
            if not _is_allowlisted(hit, token):
                offenders.append(f"[{token!r}] {hit}")

    # Retired-identity tokens are banned only in shipped surfaces; historical
    # .vault/.vaultspec records legitimately retain the prior attribution.
    for token in _BANNED_IN_SHIPPED_SURFACES:
        for hit in _git_grep(root, ["-F", "-e", token, "--", ".", *_SCAFFOLDING_EXCLUSIONS]):
            if not _is_allowlisted(hit, token):
                offenders.append(f"[{token!r}] {hit}")

    for pattern in _BANNED_PATTERNS:
        for hit in _git_grep(root, ["-E", "-e", pattern]):
            if not _is_allowlisted(hit, pattern):
                offenders.append(f"[/{pattern}/] {hit}")

    assert not offenders, (
        "Operator-identifying tokens found in committed text. Scrub them "
        "(host/login/path/network data must not ship) or, for a genuine "
        "functional survivor, record it in _ALLOWLIST with a reason:\n" + "\n".join(sorted(offenders))
    )
