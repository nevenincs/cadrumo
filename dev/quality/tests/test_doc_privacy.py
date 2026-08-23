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
  PRIVACY.md and license-chain tests; they are intentionally
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

import re
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

# Cross-project infrastructure identifiers. A DIFFERENT class from the operator
# tokens above: not personally identifying, but belonging to the account or to a
# sibling product rather than to this repository. This repository is public and
# carries its own concerns only, so a leak here is a disclosure question and not
# a tidiness one.
#
# On why this is split between shapes and fragment tokens, which is the honest
# part: shape detection works only where a shape is distinctive. A cloud role
# identifier is unmistakable. A DNS zone or cloud account id is thirty-two hex
# characters, which is indistinguishable from an index job id, a document
# internal id, or a library digest -- measured at eighty-two legitimate
# occurrences in this tree, so banning that shape would produce noise that gets
# silenced rather than corrected. Known values are therefore banned by fragment
# token, exactly as the operator tokens are, and the shape rules cover only what
# a shape can honestly identify.
#
# What this cannot catch, stated rather than implied: an identifier belonging to
# a sibling product whose value nobody recorded here. The detector narrows the
# window; only the discipline of naming account dependencies abstractly closes
# it.
_BANNED_CROSS_PROJECT_LITERALS: tuple[str, ...] = (
    _token("7c9544cd48f5393b", "d9c0ced07c587eb3"),  # account DNS zone id
    _token("5147c4292ed2ddca", "fdcbd4f0828e7436"),  # account CDN/DNS account id
    _token("neve-nincs", "-docs"),  # operator's private planning vault repository
    _token("adaline.ns.", "cloudflare.com"),  # account nameserver
    _token("todd.ns.", "cloudflare.com"),  # account nameserver
)

# ERE patterns for cross-project shapes that ARE distinctive enough to match on
# form. Kept deliberately narrow for the reason above.
_BANNED_CROSS_PROJECT_PATTERNS: tuple[str, ...] = (
    # Cloud role identifiers: an account number is embedded in the ARN itself.
    r"arn:aws:iam::[0-9]{12}:",
)

# Exact (relative-path, token) exemptions for genuine functional survivors, each
# with a stated reason. Empty today: the scrub left no functional survivor that
# still carries a banned token. A future functional survivor (e.g. a runner name
# that GitHub's registry requires verbatim) is recorded here, never by weakening
# the token list.
_ALLOWLIST: dict[tuple[str, str], str] = {}

#: Untracked binaries and build outputs are read as text, so a size ceiling
#: keeps an accidental large artifact from stalling the gate.
_MAX_SCANNED_BYTES: int = 2_000_000


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


def _untracked_files(root: Path) -> list[str]:
    """Return untracked, non-ignored paths -- the half ``git grep`` cannot see.

    ``git grep`` reads the tracked tree, so a file that has never been added is
    invisible to it. That is not a theoretical gap: this repo's own records
    once carried an account DNS zone id while untracked, and the gate was
    green for the whole time it did. It can only ever have caught that leak
    after the commit introducing it, by which point removing it is a history
    rewrite rather than an edit.
    """
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],  # noqa: S607 - git from PATH like every dev gate
        cwd=root,
        capture_output=True,
        text=True,
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git ls-files failed: {result.stderr}")
    return [line for line in result.stdout.splitlines() if line]


def _scan_untracked(root: Path, needles: tuple[str, ...], patterns: tuple[str, ...]) -> list[str]:
    """Return ``path:line`` hits for banned shapes in untracked files."""
    offenders: list[str] = []
    compiled = [re.compile(pattern) for pattern in patterns]
    for relative in _untracked_files(root):
        path = root / relative
        try:
            if path.stat().st_size > _MAX_SCANNED_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for needle in needles:
                if needle in line:
                    offenders.append(f"[{needle!r}] {relative}:{number}")
            for pattern in compiled:
                if pattern.search(line):
                    offenders.append(f"[/{pattern.pattern}/] {relative}:{number}")
    return offenders


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


def test_the_cross_project_token_sets_are_not_empty() -> None:
    """An emptied set disarms this half while leaving the gate green."""
    assert len(_BANNED_CROSS_PROJECT_LITERALS) >= 3
    assert _BANNED_CROSS_PROJECT_PATTERNS


def test_no_cross_project_identifier_in_tracked_files() -> None:
    """This repository is public and carries its own concerns only.

    Account-level and sibling-product identifiers belong in the operator's
    private notes, not here, so a leak is a disclosure question rather than a
    tidiness one.
    """
    root = _repo_root()
    offenders: list[str] = []
    for token in _BANNED_CROSS_PROJECT_LITERALS:
        offenders.extend(f"[{token!r}] {hit}" for hit in _git_grep(root, ["-F", "-e", token]))
    for pattern in _BANNED_CROSS_PROJECT_PATTERNS:
        offenders.extend(f"[/{pattern}/] {hit}" for hit in _git_grep(root, ["-E", "-e", pattern]))
    assert not offenders, (
        "Cross-project infrastructure identifiers found in committed text. Name the "
        "account dependency abstractly and keep the value in private notes:\n" + "\n".join(sorted(offenders))
    )


def test_no_banned_shape_in_untracked_files() -> None:
    """The half a tracked-only scan cannot see, and the shape of the real breach.

    This repo's own records once carried an account DNS zone id while
    untracked, and the gate was green throughout. A tracked-only scan can
    only catch that after the commit that introduces it, when removal is a
    history rewrite.
    """
    root = _repo_root()
    offenders = _scan_untracked(
        root,
        _BANNED_LITERALS + _BANNED_CROSS_PROJECT_LITERALS,
        _BANNED_PATTERNS + _BANNED_CROSS_PROJECT_PATTERNS,
    )
    assert not offenders, (
        "Banned tokens found in untracked files. Scrub them BEFORE committing; "
        "after the commit, removal is a history rewrite:\n" + "\n".join(sorted(offenders))
    )


def test_the_untracked_scan_finds_a_planted_leak(tmp_path: Path) -> None:
    """Anti-tautology against an injectable root, not the real tree.

    Without this the untracked scan passes because it read nothing just as
    readily as because the tree is clean, and those look identical.
    """
    for argv in (["git", "init", "-q"], ["git", "config", "user.email", "p@example.invalid"]):
        subprocess.run(argv, cwd=tmp_path, check=True, capture_output=True)  # noqa: S603 - fixed git argv in a temp repo

    planted = tmp_path / "notes.md"
    planted.write_text(f"zone {_BANNED_CROSS_PROJECT_LITERALS[0]}\n", encoding="utf-8")
    hits = _scan_untracked(tmp_path, _BANNED_CROSS_PROJECT_LITERALS, ())
    assert any("notes.md" in hit for hit in hits), "an untracked leak must be found"

    # Ignored files are not scanned: they are not candidates for commit.
    (tmp_path / ".gitignore").write_text("secret.md\n", encoding="utf-8")
    (tmp_path / "secret.md").write_text(f"zone {_BANNED_CROSS_PROJECT_LITERALS[0]}\n", encoding="utf-8")
    ignored = _scan_untracked(tmp_path, _BANNED_CROSS_PROJECT_LITERALS, ())
    assert not any("secret.md" in hit for hit in ignored), "an ignored file cannot reach a commit"


def test_the_untracked_scan_matches_shape_patterns_too(tmp_path: Path) -> None:
    """Both halves of the ban - fixed tokens and shapes - reach untracked files."""
    subprocess.run(
        ["git", "init", "-q"],  # noqa: S607 - git resolved from PATH like every dev gate
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    # Assembled from fragments like every other banned value: a literal here
    # would be a real hit in a tracked file and this gate would flag itself,
    # which is exactly what it did on the first draft of this test.
    planted = _token("arn:aws", ":iam::123456789012:role/example")
    (tmp_path / "role.tf").write_text(f'role = "{planted}"\n', encoding="utf-8")
    hits = _scan_untracked(tmp_path, (), _BANNED_CROSS_PROJECT_PATTERNS)
    assert any("role.tf" in hit for hit in hits)
