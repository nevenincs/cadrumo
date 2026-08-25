"""Gate: documentation channel claims require passing distribution evidence.

Scans ``README.md`` and every user-facing Markdown page under ``docs/`` for
acquisition channel claims — pip/PyPI install commands, ``uvx``, Scoop
install/bucket references, and Homebrew install/tap references. For every
claim found the
gate requires a passing :class:`~dev.packaging.evidence.DistributionEvidence`
record in ``var/distribution-install-readiness/`` for each distribution row
the channel maps to in :data:`~dev.release.readiness.ALL_DISTRIBUTION_ROWS`.

This gate is anchored on the FULL row set rather than the claimed subset. The
readiness gate scales its required rows to the channels a release claims, so an
unclaimed channel no longer blocks a claimed one — but a documentation claim is
itself the act of claiming a channel, so it must always carry that channel's
proof. The two are complements: readiness asks "did the channels you claim
pass?", this gate asks "are you claiming a channel that did not?".

The gate passes cleanly when documentation makes no positive acquisition
claims — disclaimers such as "do not install from PyPI yet" do not match the
channel-specific command patterns.  It fails with an instructive per-claim
message as soon as a doc update advertises a channel ahead of its passing
evidence.

Files whose filename component starts with ``_`` (Sphinx-internal convention:
``_release_notes_template.md``, ``_build/``, ``_static/``, etc.) are excluded
from scanning because they are not user-facing acquisition surfaces.

Carries the ``unit`` and ``docs`` markers so ``just docs-check`` and the
documentation CI lane pick it up alongside the other docs gates.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

import pydantic
import pytest

from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT
from ...packaging.evidence import DistributionEvidence, EvidenceStatus
from ...release.readiness import ALL_DISTRIBUTION_ROWS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT: Final[Path] = REPO_ROOT
_EVIDENCE_DIR: Final[Path] = _REPO_ROOT / "var" / "distribution-install-readiness"
_README: Final[Path] = _REPO_ROOT / "README.md"
_DOCS_ROOT: Final[Path] = _REPO_ROOT / "docs"

# ---------------------------------------------------------------------------
# Channel claim patterns
#
# Each entry: (human_label, compiled_pattern, required_row_ids)
#
# Patterns match positive acquisition instructions — command blocks or prose
# telling a reader to install via that channel.  Disclaimers such as "do not
# install from PyPI yet" are not matched because they lack the channel-specific
# command verb+noun that each pattern requires.
# ---------------------------------------------------------------------------

_CLAIM_PATTERNS: Final[tuple[tuple[str, re.Pattern[str], tuple[str, ...]], ...]] = (
    (
        "pip install cadrumo (PyPI)",
        re.compile(r"pip\s+install\s+cadrumo", re.IGNORECASE),
        ("python-linux-x86-64", "python-macos-arm64", "python-windows-x86-64"),
    ),
    (
        "uvx cadrumo (PyPI via uvx)",
        re.compile(r"uvx\s+cadrumo", re.IGNORECASE),
        ("python-linux-x86-64", "python-macos-arm64", "python-windows-x86-64"),
    ),
    (
        "scoop install cadrumo (Scoop)",
        # The bucket is account-scoped, so the documented command addresses the
        # app within that bucket (`scoop install nevenincs/cadrumo`). The bucket
        # prefix is optional because Scoop also resolves a bare app name once the
        # bucket is added; both spellings are a positive acquisition claim.
        re.compile(r"scoop\s+install\s+(?:\S+/)?cadrumo\b", re.IGNORECASE),
        ("scoop-windows-x86-64",),
    ),
    (
        "brew install cadrumo (Homebrew)",
        re.compile(r"brew\s+install\s+(?:\S+/)?cadrumo\b", re.IGNORECASE),
        (
            "homebrew-linux-arm64",
            "homebrew-linux-x86-64",
            "homebrew-macos-arm64",
        ),
    ),
    (
        "brew tap cadrumo (Homebrew tap)",
        # The tap is account-scoped, so the slug carries the account rather than
        # the product and cannot be anchored on "cadrumo". It is anchored on the
        # account instead: an unrelated third-party tap mentioned in prose
        # (`brew tap homebrew/cask`) is not a claim about this product, and
        # requiring a slug keeps "the Homebrew tap opens at public launch" out —
        # "brew tap opens" has no owner/name token after it.
        re.compile(r"brew\s+tap\s+nevenincs/\S+", re.IGNORECASE),
        (
            "homebrew-linux-arm64",
            "homebrew-linux-x86-64",
            "homebrew-macos-arm64",
        ),
    ),
)

# Pre-built label → row_ids lookup derived from the pattern table above.
_CLAIM_TO_ROWS: Final[dict[str, tuple[str, ...]]] = {label: row_ids for label, _pattern, row_ids in _CLAIM_PATTERNS}


def _is_internal_path(path: Path) -> bool:
    """Return True for Sphinx-internal paths (any component starts with ``_``).

    Excludes ``_release_notes_template.md``, ``_build/``, ``_static/``, and
    similar Sphinx-internal files from the user-facing acquisition scan.
    """
    try:
        relative = path.relative_to(_REPO_ROOT)
    except ValueError:
        return False
    return any(part.startswith("_") for part in relative.parts)


def _doc_files() -> tuple[Path, ...]:
    """Return README.md plus every user-facing Markdown file under docs/.

    Excludes files whose filename or any parent directory component starts
    with ``_`` (Sphinx-internal convention).
    """
    sources: list[Path] = []
    if _README.is_file() and not _is_internal_path(_README):
        sources.append(_README)
    if _DOCS_ROOT.is_dir():
        for path in scan_directory(_DOCS_ROOT, pattern="*.md", recursive=True):
            if not _is_internal_path(path):
                sources.append(path)
    return tuple(sources)


# A claim is only a claim when the reader is being told to run the command. A
# line that negates it before the command ("do not install from PyPI yet") is a
# disclaimer, which the module contract says must not match. The negation must
# appear BEFORE the command on the same line: scanning the whole line would let
# an unrelated trailing caveat ("...; do not use sudo") silence a real claim,
# and silencing a real claim is the failure direction this gate exists to
# prevent.
_NEGATION: Final[re.Pattern[str]] = re.compile(
    r"\b(?:do\s+not|don't|dont|never|avoid|cannot|can't|no\s+need\s+to)\b",
    re.IGNORECASE,
)


def claim_labels_in_line(line: str) -> tuple[str, ...]:
    """Return the claim labels a single line positively asserts.

    Scanning is per line rather than per file because ``\\s+`` inside the
    patterns crosses newlines: against whole-file text a line ending in
    "Homebrew tap" followed by a line beginning with a path token matches as a
    tap command. A line is also skipped when the matched command is preceded on
    that line by a negation, so a disclaimer is not read as an instruction.
    """
    labels: list[str] = []
    for label, pattern, _row_ids in _CLAIM_PATTERNS:
        match = pattern.search(line)
        if match is None:
            continue
        if _NEGATION.search(line[: match.start()]):
            continue
        labels.append(label)
    return tuple(labels)


def _scan_claims() -> list[tuple[Path, str]]:
    """Return ``(doc_path, claim_label)`` pairs for every acquisition claim found.

    Reads each doc file once and tests every pattern against each line. A
    single file may contribute multiple distinct claims if it contains patterns
    for more than one channel.
    """
    found: list[tuple[Path, str]] = []
    for doc in _doc_files():
        try:
            text = doc.read_text(encoding="utf-8")
        except OSError:
            continue
        seen: set[str] = set()
        for line in text.splitlines():
            for label in claim_labels_in_line(line):
                if label not in seen:
                    seen.add(label)
                    found.append((doc, label))
    return found


def _passing_evidence_rows() -> frozenset[str]:
    """Return the set of row_ids that have at least one passing evidence record.

    Loads every ``*.json`` file under :data:`_EVIDENCE_DIR` as a
    :class:`~dev.packaging.evidence.DistributionEvidence` and collects
    row_ids whose ``result.status`` is
    :attr:`~dev.packaging.evidence.EvidenceStatus.PASSED`.

    Files that fail schema validation (including tampered ``evidence_id``
    hash) are skipped silently — only genuine, self-consistent evidence
    records count as passing.  An absent or empty evidence directory yields
    an empty set.
    """
    if not _EVIDENCE_DIR.is_dir():
        return frozenset()
    passed: set[str] = set()
    for path in scan_directory(_EVIDENCE_DIR, pattern="*.json"):
        try:
            record = DistributionEvidence.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, pydantic.ValidationError):
            continue
        if record.result.status is EvidenceStatus.PASSED:
            passed.add(record.row_id)
    return frozenset(passed)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Positive control
#
# The corpus scan below finds nothing while every channel is pre-launch, so on
# its own it would pass without ever evaluating a pattern — green because it is
# inert rather than because it is satisfied. These cases pin each pattern's
# behaviour directly, so the gate fails the moment the pattern set stops
# discriminating, independently of what the documentation currently contains.
#
# Each entry: (claim_label, strings that MUST match, strings that MUST NOT).
# ---------------------------------------------------------------------------
_PATTERN_CONTROL: Final[tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...]] = (
    (
        "pip install cadrumo (PyPI)",
        ("pip install cadrumo", "Run `pip install cadrumo` to get started."),
        ("do not pip install cadrumo yet", "Don't pip install cadrumo before launch."),
    ),
    (
        "uvx cadrumo (PyPI via uvx)",
        ("uvx cadrumo", "uvx cadrumo --help"),
        ("do not uvx cadrumo yet",),
    ),
    (
        "scoop install cadrumo (Scoop)",
        ("scoop install cadrumo", "scoop install nevenincs/cadrumo"),
        ("scoop install ripgrep", "do not scoop install cadrumo yet"),
    ),
    (
        "brew install cadrumo (Homebrew)",
        ("brew install cadrumo", "brew install nevenincs/tap/cadrumo"),
        ("brew install ripgrep", "do not brew install cadrumo yet"),
    ),
    (
        "brew tap cadrumo (Homebrew tap)",
        ("brew tap nevenincs/tap", "brew tap nevenincs/homebrew-tap"),
        (
            # The withheld-state prose this pattern must never read as a command.
            "The Homebrew tap opens at public launch.",
            "Release page artifact; Homebrew tap at public launch",
            # An unrelated third-party tap is not a claim about this product.
            "brew tap homebrew/cask",
            "brew tap oven-sh/bun",
            # A disclaimer is not an instruction.
            "do not brew tap nevenincs/tap yet",
        ),
    ),
)


@pytest.mark.parametrize("label, must_match, must_not_match", _PATTERN_CONTROL)
def test_each_claim_pattern_matches_its_command_and_rejects_its_lookalike(
    label: str,
    must_match: tuple[str, ...],
    must_not_match: tuple[str, ...],
) -> None:
    """Pin every pattern's behaviour in both directions against known strings.

    Without this the gate can only be as good as whatever the docs happen to
    contain, and today they contain no claims at all. A pattern that stopped
    matching its own install command, or started matching prose, would go
    unnoticed.
    """
    for text in must_match:
        assert label in claim_labels_in_line(text), f"pattern {label!r} no longer matches its own command: {text!r}"
    for text in must_not_match:
        assert label not in claim_labels_in_line(text), f"pattern {label!r} over-matches: {text!r}"


def test_every_pattern_is_covered_by_the_positive_control() -> None:
    """A new pattern must arrive with its own match/no-match cases.

    Otherwise the control silently stops covering the table it is meant to pin.
    """
    controlled = {label for label, _match, _reject in _PATTERN_CONTROL}
    declared = {label for label, _pattern, _rows in _CLAIM_PATTERNS}
    assert declared == controlled, (
        "every claim pattern needs positive-control cases; "
        f"uncontrolled={sorted(declared - controlled)} stale={sorted(controlled - declared)}"
    )


def test_a_line_break_does_not_manufacture_a_tap_claim() -> None:
    """Whole-file scanning turned a line break into a command; per-line scanning must not.

    ``\\s+`` matches a newline, so against full-file text a line *ending* in
    "Homebrew tap" followed by a line *beginning* with a path token read as a
    tap command. The document below is a real reproduction: the tap pattern
    matches it under ``search()`` over the whole file and does not match any of
    its lines individually. A document that failed to reproduce the bug would
    make this test prove nothing.
    """
    document = "Install via the Homebrew tap\nnevenincs/cadrumo release page has details.\n"
    tap_label = "brew tap cadrumo (Homebrew tap)"
    tap_pattern = next(pattern for label, pattern, _rows in _CLAIM_PATTERNS if label == tap_label)

    # The reproduction is real: whole-file scanning does match this text.
    assert tap_pattern.search(document) is not None, "document no longer reproduces the cross-newline match"

    # Per-line scanning, which is what the scanner now does, does not.
    labels = [label for line in document.splitlines() for label in claim_labels_in_line(line)]
    assert "brew tap cadrumo (Homebrew tap)" not in labels


def test_the_scanned_corpus_is_not_empty() -> None:
    """The corpus scan is only meaningful over real files.

    An empty file list would make the claim scan vacuously clean, which is the
    failure mode this module already had once.
    """
    docs = _doc_files()
    assert len(docs) > 0, "no user-facing documentation was scanned; the claim gate would pass vacuously"
    assert _README in docs, "README.md must be part of the scanned acquisition surface"


def test_no_unevidenced_channel_claims() -> None:
    """Every acquisition channel claimed in docs must have passing distribution evidence.

    Scans ``README.md`` and docs Markdown pages for channel-identifying
    patterns (pip/PyPI install commands, uvx, scoop install/bucket, and brew
    install/tap). For every claim
    found the test requires a passing
    :class:`~dev.packaging.evidence.DistributionEvidence` record in
    ``var/distribution-install-readiness/`` for each row the channel maps to.

    The test passes when no claims are found — the absence of evidence is
    not a failure unless documentation already advertises the channel.  When
    claims do appear, the failure message names the exact doc file, the claim
    matched, and every row whose evidence is missing.
    """
    claims = _scan_claims()
    if not claims:
        # No positive acquisition claims in docs — nothing to verify.
        return

    passing_rows = _passing_evidence_rows()

    failures: list[str] = []
    for doc_path, claim_label in claims:
        required_rows = _CLAIM_TO_ROWS[claim_label]
        missing_rows = sorted(set(required_rows) - passing_rows)
        if missing_rows:
            try:
                rel = doc_path.relative_to(_REPO_ROOT)
            except ValueError:
                rel = doc_path
            failures.append(f"  {rel}: '{claim_label}' — missing passing evidence for rows: {missing_rows}")

    assert not failures, (
        f"Documentation claims {len(failures)} channel(s) without passing "
        f"distribution evidence in {_EVIDENCE_DIR.relative_to(_REPO_ROOT)}:\n" + "\n".join(failures) + "\n\n"
        "To resolve: either remove the acquisition claim from the documentation "
        "until passing evidence exists in var/distribution-install-readiness/, "
        "or provide passing evidence records for every listed row before the "
        "documentation promotes the channel."
    )


def test_claim_row_ids_are_real_distribution_rows() -> None:
    """All row IDs in the claim-pattern mapping are rows some channel really owns.

    Guards against a typo in the mapping table that would silently skip the
    evidence check for a real distribution row.

    Anchored on :data:`~dev.release.readiness.ALL_DISTRIBUTION_ROWS`, not the
    claimed subset. This gate exists to stop documentation advertising a channel
    ahead of its proof, so it must keep teeth for exactly the channels the
    release does NOT claim — anchoring it on the claimed set would let a doc
    claim an unclaimed channel with no row at all, which is the failure it is
    built to prevent.
    """
    known_rows: frozenset[str] = frozenset(ALL_DISTRIBUTION_ROWS)
    invalid: list[str] = []
    for label, _pattern, row_ids in _CLAIM_PATTERNS:
        for row_id in row_ids:
            if row_id not in known_rows:
                invalid.append(f"  pattern '{label}': '{row_id}' is owned by no download channel")
    assert not invalid, (
        "Claim pattern mapping references row IDs that no channel owns "
        "(typo or stale entry):\n" + "\n".join(invalid) + "\nAdd the row to a channel's evidence_rows in "
        "docs/_data/download_channels.toml or correct the mapping in this file."
    )


def test_every_channel_evidence_row_is_reachable_by_a_claim_pattern() -> None:
    """Anti-vacuity: each row a channel declares is guarded by some claim pattern.

    Without this, adding a channel row to the descriptor and forgetting its claim
    pattern would leave that channel documentable with no evidence requirement —
    the gate would stay green while measuring nothing for that channel.
    """
    patterned: frozenset[str] = frozenset(row for _label, _pattern, rows in _CLAIM_PATTERNS for row in rows)
    unguarded = sorted(frozenset(ALL_DISTRIBUTION_ROWS) - patterned)
    assert not unguarded, (
        "these declared channel evidence rows are guarded by no documentation claim pattern, "
        f"so their channel could be advertised unproven: {unguarded}"
    )
