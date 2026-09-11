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

Implementation note: the scan reads every file the repository enumerates
(:func:`dev.source_tree.repository_files`, which already returns the same
union a VCS would honour -- committed content plus new files nobody has
ignored) rather than asking twice for a "tracked" half and an "untracked"
half. That split used to matter only because it was answered by two different
commands with two different blind spots; this repo's own records once carried
an account DNS zone id while untracked, and the tracked-only half of the old
scan was green for the whole time it did.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.source_tree import repository_files

from ..unread_inputs import report_unread

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


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

# Scaffolding trees excluded from the shipped-only set.
_SCAFFOLDING_PREFIXES: tuple[str, ...] = (".vault/", ".vaultspec/")

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

#: A large untracked binary or build output is read as text, so a size ceiling
#: keeps an accidental large artifact from stalling the gate.
_MAX_SCANNED_BYTES: int = 2_000_000


@dataclass(frozen=True, slots=True)
class _ScannedFile:
    """One file's full decoded text, kept whole so a fast substring probe can
    reject the common case before the cost of splitting it into lines."""

    relative: str
    text: str


def _read_corpus(root: Path, files: tuple[str, ...]) -> tuple[tuple[_ScannedFile, ...], list[str]]:
    """Read every file in ``files`` once. Returns the corpus and any unread paths.

    Both skips below leave a file unscanned, and an unscanned file is
    indistinguishable from a clean one in a gate about leaked private data, so
    every skip is collected and reported by the caller rather than swallowed.
    """
    corpus: list[_ScannedFile] = []
    unread: list[str] = []
    for relative in files:
        path = root / relative
        try:
            if path.stat().st_size > _MAX_SCANNED_BYTES:
                unread.append(f"{relative} (larger than {_MAX_SCANNED_BYTES} bytes)")
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as refusal:
            unread.append(f"{relative} ({refusal})")
            continue
        corpus.append(_ScannedFile(relative, text))
    return tuple(corpus), unread


def _find_literal(corpus: tuple[_ScannedFile, ...], literal: str) -> list[str]:
    """Return ``path:line:content`` hits for one fixed-string needle."""
    hits: list[str] = []
    for scanned in corpus:
        if literal not in scanned.text:
            continue
        for number, line in enumerate(scanned.text.splitlines(), start=1):
            if literal in line:
                hits.append(f"{scanned.relative}:{number}:{line}")
    return hits


def _find_pattern(corpus: tuple[_ScannedFile, ...], pattern: str) -> list[str]:
    """Return ``path:line:content`` hits for one ERE pattern."""
    compiled = re.compile(pattern)
    hits: list[str] = []
    for scanned in corpus:
        if not compiled.search(scanned.text):
            continue
        for number, line in enumerate(scanned.text.splitlines(), start=1):
            if compiled.search(line):
                hits.append(f"{scanned.relative}:{number}:{line}")
    return hits


def _is_allowlisted(hit: str, token: str) -> bool:
    path = hit.split(":", 1)[0]
    return (path, token) in _ALLOWLIST


def _probe_tree(root: Path) -> None:
    """Materialise a scratch tree carrying one instance of each banned shape.

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


@pytest.fixture(scope="module")
def repository_corpus() -> tuple[tuple[_ScannedFile, ...], list[str]]:
    """Read the live repository's enumerated text once, shared by both whole-tree gates.

    Both gates below read the same corpus; reading it twice would double the
    cost of a scan that already has to touch tens of thousands of files.
    """
    return _read_corpus(REPO_ROOT, repository_files(REPO_ROOT))


def test_the_banned_token_sets_are_not_empty() -> None:
    """An emptied ban list disarms the scan while leaving it green."""
    assert len(_BANNED_LITERALS) >= 5
    assert _BANNED_IN_SHIPPED_SURFACES
    assert _BANNED_PATTERNS


def test_the_scan_finds_every_banned_shape_in_a_tree_that_carries_them(tmp_path: Path) -> None:
    """Positive control: the real scan, run against a tree that really leaks.

    The tree-wide assertion below reports zero offenders, which is the same
    result it would report if the patterns had stopped matching or nothing had
    been read at all. Nothing distinguishes a scrubbed tree from a blind scan
    without exercising the scan against a corpus known to contain each shape.
    """
    _probe_tree(tmp_path)
    corpus, unread = _read_corpus(tmp_path, repository_files(tmp_path))
    assert not unread

    literal_hits = _find_literal(corpus, _BANNED_LITERALS[0])
    assert literal_hits, f"the scan no longer finds {_BANNED_LITERALS[0]!r}"

    for pattern in _BANNED_PATTERNS:
        assert _find_pattern(corpus, pattern), f"the scan no longer matches {pattern!r}"


def test_the_network_range_pattern_stops_at_its_boundaries(tmp_path: Path) -> None:
    """Negative control: the CGNAT pattern covers 100.64-100.127 and no more.

    A pattern widened to every ``100.x`` address would flag ordinary public
    addresses and get silenced rather than corrected, so both edges are pinned.
    """
    _probe_tree(tmp_path)
    corpus, _ = _read_corpus(tmp_path, repository_files(tmp_path))
    cgnat = next(pattern for pattern in _BANNED_PATTERNS if "12[0-7]" in pattern)
    matched = "\n".join(_find_pattern(corpus, cgnat))

    for inside in (_token("100.", "64.0.1"), _token("100.", "127.255.254"), _token("100.", "101.102.103")):
        assert inside in matched, f"{inside} is inside the CGNAT range and must match"
    for outside in ("100.63.0.1", "100.128.0.1"):
        assert outside not in matched, f"{outside} is outside the CGNAT range and must not match"


def test_a_gitignored_file_is_not_scanned(tmp_path: Path) -> None:
    """An ignored file cannot reach a commit, so it is not this gate's problem.

    Without this, a contributor's local scratch file would fail a gate about
    what gets SHIPPED.
    """
    (tmp_path / "notes.md").write_text(f"zone {_BANNED_CROSS_PROJECT_LITERALS[0]}\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("secret.md\n", encoding="utf-8")
    (tmp_path / "secret.md").write_text(f"zone {_BANNED_CROSS_PROJECT_LITERALS[0]}\n", encoding="utf-8")

    corpus, _ = _read_corpus(tmp_path, repository_files(tmp_path))
    hits = _find_literal(corpus, _BANNED_CROSS_PROJECT_LITERALS[0])

    assert any("notes.md" in hit for hit in hits), "an in-scope leak must be found"
    assert not any("secret.md" in hit for hit in hits), "an ignored file cannot reach a commit"


def test_the_scan_matches_cross_project_shape_patterns(tmp_path: Path) -> None:
    """The distinctive-shape half of the cross-project ban.

    Assembled from fragments like every other banned value: a literal here
    would be a real hit in a tracked file and this gate would flag itself.
    """
    planted = _token("arn:aws", ":iam::123456789012:role/example")
    (tmp_path / "role.tf").write_text(f'role = "{planted}"\n', encoding="utf-8")

    corpus, _ = _read_corpus(tmp_path, repository_files(tmp_path))
    hits = _find_pattern(corpus, _BANNED_CROSS_PROJECT_PATTERNS[0])

    assert any("role.tf" in hit for hit in hits)


def test_no_operator_identifying_tokens_in_the_repository(
    repository_corpus: tuple[tuple[_ScannedFile, ...], list[str]],
) -> None:
    """No file in the tree may carry a leaked host / login / path / network token."""
    corpus, unread = repository_corpus
    shipped_corpus = tuple(scanned for scanned in corpus if not scanned.relative.startswith(_SCAFFOLDING_PREFIXES))
    assert len(corpus) > 20000 and len(shipped_corpus) > 20000, (
        f"the scan reached {len(corpus)} files and {len(shipped_corpus)} shipped-surface files; the "
        "corpus collapsed, so an empty offender list would mean nothing was searched rather than "
        "nothing is wrong"
    )

    offenders: list[str] = []

    for token in _BANNED_LITERALS:
        for hit in _find_literal(corpus, token):
            if not _is_allowlisted(hit, token):
                offenders.append(f"[{token!r}] {hit}")

    # Retired-identity tokens are banned only in shipped surfaces; historical
    # .vault/.vaultspec records legitimately retain the prior attribution.
    for token in _BANNED_IN_SHIPPED_SURFACES:
        for hit in _find_literal(shipped_corpus, token):
            if not _is_allowlisted(hit, token):
                offenders.append(f"[{token!r}] {hit}")

    for pattern in _BANNED_PATTERNS:
        for hit in _find_pattern(corpus, pattern):
            if not _is_allowlisted(hit, pattern):
                offenders.append(f"[/{pattern}/] {hit}")

    report_unread("privacy scan", "a banned shape inside one would not appear below", unread)
    assert not offenders, (
        "Operator-identifying tokens found in committed text. Scrub them "
        "(host/login/path/network data must not ship) or, for a genuine "
        "functional survivor, record it in _ALLOWLIST with a reason:\n" + "\n".join(sorted(offenders))
    )


def test_the_cross_project_token_sets_are_not_empty() -> None:
    """An emptied set disarms this half while leaving the gate green."""
    assert len(_BANNED_CROSS_PROJECT_LITERALS) >= 3
    assert _BANNED_CROSS_PROJECT_PATTERNS


def test_no_cross_project_identifier_in_the_repository(
    repository_corpus: tuple[tuple[_ScannedFile, ...], list[str]],
) -> None:
    """This repository is public and carries its own concerns only.

    Account-level and sibling-product identifiers belong in the operator's
    private notes, not here, so a leak is a disclosure question rather than a
    tidiness one.
    """
    corpus, unread = repository_corpus
    assert len(corpus) > 20000, (
        f"the scan reached {len(corpus)} files; the corpus collapsed, so an empty offender "
        "list would mean nothing was searched rather than nothing is wrong"
    )

    offenders: list[str] = []

    for token in _BANNED_CROSS_PROJECT_LITERALS:
        offenders.extend(f"[{token!r}] {hit}" for hit in _find_literal(corpus, token))
    for pattern in _BANNED_CROSS_PROJECT_PATTERNS:
        offenders.extend(f"[/{pattern}/] {hit}" for hit in _find_pattern(corpus, pattern))

    report_unread("cross-project identifier scan", "a banned identifier inside one would not appear below", unread)
    assert not offenders, (
        "Cross-project infrastructure identifiers found in committed text. Name the "
        "account dependency abstractly and keep the value in private notes:\n" + "\n".join(sorted(offenders))
    )
