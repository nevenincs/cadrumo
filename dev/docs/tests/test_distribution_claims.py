"""Gate: documentation channel claims require passing distribution evidence.

Scans ``README.md`` and every user-facing Markdown page under ``docs/`` for
acquisition channel claims — pip/PyPI install commands, ``uvx``, Scoop
install/bucket references, Homebrew install/tap references, Claude plugin
marketplace URLs, and MCPB download references.  For every claim found the
gate requires a passing :class:`~dev.packaging.evidence.DistributionEvidence`
record in ``var/distribution-install-readiness/`` for each distribution row
the channel maps to in :data:`REQUIRED_DISTRIBUTION_ROWS`.

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

from dev.packaging.evidence import DistributionEvidence, EvidenceStatus
from dev.release.readiness import REQUIRED_DISTRIBUTION_ROWS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
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
    # Operator ruling 2026-07-20: v0.2.1 claims only the rows the self-hosted
    # fleet proves — the macOS and hosted-only linux-arm64 rows are descoped
    # and return in a later release when their runners exist.
    (
        "pip install cadrumo (PyPI)",
        re.compile(r"pip\s+install\s+cadrumo", re.IGNORECASE),
        ("python-linux-x86-64", "python-windows-x86-64"),
    ),
    (
        "uvx cadrumo (PyPI via uvx)",
        re.compile(r"uvx\s+cadrumo", re.IGNORECASE),
        ("python-linux-x86-64", "python-windows-x86-64"),
    ),
    (
        "scoop install cadrumo (Scoop)",
        re.compile(r"scoop\s+install\s+cadrumo", re.IGNORECASE),
        ("scoop-windows-x86-64",),
    ),
    (
        "brew install cadrumo (Homebrew)",
        re.compile(r"brew\s+install\s+(?:\S+/)?cadrumo\b", re.IGNORECASE),
        ("homebrew-linux-x86-64",),
    ),
    (
        "brew tap cadrumo (Homebrew tap)",
        re.compile(r"brew\s+tap\s+\S+/cadrumo\b", re.IGNORECASE),
        ("homebrew-linux-x86-64",),
    ),
    (
        "Claude plugin marketplace install",
        re.compile(r"marketplace\.anthropic\.com[^\s\"']*cadrumo", re.IGNORECASE),
        ("claude-code-plugin", "claude-cowork-plugin", "claude-desktop-plugin"),
    ),
    (
        "MCPB cadrumo package install",
        re.compile(r"cadrumo[^\s\"']*\.mcpb\b", re.IGNORECASE),
        ("claude-desktop-mcpb",),
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
        for path in sorted(_DOCS_ROOT.rglob("*.md")):
            if not _is_internal_path(path):
                sources.append(path)
    return tuple(sources)


def _scan_claims() -> list[tuple[Path, str]]:
    """Return ``(doc_path, claim_label)`` pairs for every acquisition claim found.

    Reads each doc file once and tests every pattern against the full text.
    A single file may contribute multiple distinct claims if it contains
    patterns for more than one channel.
    """
    found: list[tuple[Path, str]] = []
    for doc in _doc_files():
        try:
            text = doc.read_text(encoding="utf-8")
        except OSError:
            continue
        for label, pattern, _row_ids in _CLAIM_PATTERNS:
            if pattern.search(text):
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
    for path in sorted(_EVIDENCE_DIR.glob("*.json")):
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


def test_no_unevidenced_channel_claims() -> None:
    """Every acquisition channel claimed in docs must have passing distribution evidence.

    Scans ``README.md`` and docs Markdown pages for channel-identifying
    patterns (pip/PyPI install commands, uvx, scoop install/bucket, brew
    install/tap, Claude plugin marketplace, MCPB download).  For every claim
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


def test_claim_row_ids_are_in_required_distribution_rows() -> None:
    """All row IDs in the claim-pattern mapping are known REQUIRED_DISTRIBUTION_ROWS.

    Guards against a typo in the mapping table that would silently skip the
    evidence check for a real distribution row.  If a new row is added to
    :data:`~dev.release.readiness.REQUIRED_DISTRIBUTION_ROWS`, the mapping
    here must be updated when documentation for that channel lands.
    """
    known_rows: frozenset[str] = frozenset(REQUIRED_DISTRIBUTION_ROWS)
    invalid: list[str] = []
    for label, _pattern, row_ids in _CLAIM_PATTERNS:
        for row_id in row_ids:
            if row_id not in known_rows:
                invalid.append(f"  pattern '{label}': '{row_id}' is not in REQUIRED_DISTRIBUTION_ROWS")
    assert not invalid, (
        "Claim pattern mapping references row IDs that are not in "
        "REQUIRED_DISTRIBUTION_ROWS (typo or stale entry):\n"
        + "\n".join(invalid)
        + "\nUpdate REQUIRED_DISTRIBUTION_ROWS in dev/release/readiness.py "
        "or correct the mapping in this file."
    )
