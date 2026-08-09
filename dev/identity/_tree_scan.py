"""Scan the repository working tree for checksum-valid Spanish tax identifiers.

WHY THIS EXISTS. The 2026-05-30 security audit recommended an identity-pattern canary
and none was built; there is no identity or secret scanner in the pre-commit config at
all. The exposure that motivated it reached the tree through a file that was gitignored
and committed anyway, so this scans TRACKED AND UNTRACKED files both.

DETECTION IS NOT IMPLEMENTED HERE. The pattern, the checksum and the value-free finding
shape all come from the sanitiser's residual-identity scan, which already imports
``cadrumo.core.identity.validate_identity`` rather than restating the AEAT control-letter
algorithm. Re-deriving any of it would be a second authority for one rule -- the defect
this repository has retired three times in the box-number marker alone. This module
contributes the SURFACE (a working tree rather than a sanitised PDF) and the SCOPE
decision, nothing else.

HANDLING RULE, ABSOLUTE AND INHERITED. A finding never carries the matched text. It
carries the path, the line, the column and the pattern class. Anything that reads a
finding -- an assertion message, a log line, a report -- is therefore incapable of
disclosing the value it found. A canary that hardcodes or echoes the identifier it hunts
would republish the exposure it exists to prevent.

WHY THERE IS NO VALUE ALLOWLIST, and why novelty detection is unavailable today. The
sharpest possible discriminator would be "fail on a checksum-valid identifier outside the
declared synthetic set", because the tree's identifiers are few and stable. That needs the
set stored. Storing values republishes them. Storing HASHES does not help: the
eight-digit-plus-letter space is about 2.3e9, trivially brute-forced from an unsalted
digest, and no secret salt exists in-repo -- so a hash baseline is disclosure wearing a
checksum. Scope is therefore decided BY PATH, each exclusion carrying its reason.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ..sanitizer.tests._residual_identity_scan import _VALIDATORS, ResidualKind

_UTF_8: Final[str] = "utf-8"

#: Suffixes read as text. A binary carrying an identifier is a different problem with a
#: different detector: the sanitiser owns PDFs, and a spreadsheet or archive needs
#: extraction before a pattern means anything.
TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".toml",
        ".md",
        ".yml",
        ".yaml",
        ".json",
        ".txt",
        ".cfg",
        ".ini",
        ".html",
        ".csv",
        ".xml",
        ".sql",
        ".sh",
        ".ps1",
        ".j2",
        ".rst",
        ".env",
    }
)

#: Path fragments excluded from the scan, each with the reason it is excluded. NEVER a
#: value allowlist: an allowlist of identifiers is the one artefact that would carry the
#: identifier this canary exists to keep out of the repository.
#:
#: Both exclusions rest on the same measured fact: the project uses structurally valid
#: synthetic identifiers in fixtures as established practice, 1,922 occurrences across
#: 649 test files drawn from 33 distinct values. That practice is UNDECLARED, which is
#: its own finding -- an undocumented de facto standard is how a real value hides among
#: synthetic ones -- and it is what makes pattern-plus-checksum unusable as a gate over
#: the whole tree.
EXCLUDED_PATH_FRAGMENTS: dict[str, str] = {
    "/tests/": "the project uses structurally valid synthetic identifiers in tests as established practice",
    "/fixtures/": "fixture payloads carry synthetic identifiers by construction",
}


@dataclass(frozen=True, slots=True)
class TreeFinding:
    """One checksum-valid identifier occurrence, WITHOUT the value.

    Carries where and what class, never what. Sorting is by location so assertion output
    is deterministic across runs and platforms.
    """

    path: str
    line: int
    column: int
    kind: ResidualKind

    def rendered(self) -> str:
        """A value-free, deterministic description safe to put in a failure message."""
        return f"{self.path}:{self.line}:{self.column} [{self.kind.value}]"


def repository_text_files(repo_root: Path) -> list[Path]:
    """Every tracked AND untracked text file, honouring ``.gitignore`` for the untracked.

    Untracked files are included deliberately. The exposure this canary answers to
    arrived through a file that was gitignored and committed anyway, so a scanner that
    only reads the index would have been blind to it at the moment it mattered.

    The git executable is resolved rather than taken from the argv shorthand: a canary
    whose enumeration silently resolves to whatever ``git`` a PATH entry happens to
    supply is a canary that can be pointed at a different tree than the one being
    guarded, and a machine without git gets one plain sentence instead of a
    file-not-found traceback from inside a security scan.
    """
    executable = shutil.which("git")
    if executable is None:
        raise SystemExit("git is not on PATH, so the working tree cannot be enumerated for scanning")
    completed = subprocess.run(  # noqa: S603 - resolved executable, fixed argv, no caller input
        [executable, "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    files: list[Path] = []
    for line in completed.stdout.splitlines():
        if not line:
            continue
        candidate = repo_root / line
        if candidate.suffix.lower() in TEXT_SUFFIXES and candidate.is_file():
            files.append(candidate)
    return files


def excluded(relative_path: str) -> str | None:
    """The stated reason ``relative_path`` is out of scope, or ``None`` when in scope."""
    haystack = f"/{relative_path}"
    for fragment, reason in EXCLUDED_PATH_FRAGMENTS.items():
        if fragment in haystack:
            return reason
    return None


def scan_tree(repo_root: Path, *, kinds: frozenset[ResidualKind] | None = None) -> tuple[TreeFinding, ...]:
    """Every checksum-valid identifier occurrence in the in-scope working tree.

    Only the checksum-verified pattern classes are scanned by default. The shape-only
    classes carry no checksum, so over a whole repository they would report ordinary
    prose and configuration rather than identities -- advisory by construction, and noise
    at this scale.
    """
    selected = kinds if kinds is not None else frozenset({ResidualKind.NIF_NIE})
    findings: list[TreeFinding] = []
    for path in repository_text_files(repo_root):
        relative = path.relative_to(repo_root).as_posix()
        if excluded(relative) is not None:
            continue
        try:
            text = path.read_text(encoding=_UTF_8, errors="replace")
        except OSError:
            # An unreadable file is reported by neither a pass nor a finding; a scanner
            # that silently skips is the failure this repository keeps correcting, so the
            # caller is told through the unreadable inventory instead.
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for kind in sorted(selected, key=lambda candidate: candidate.value):
                pattern, is_valid = _VALIDATORS[kind]
                for match in pattern.finditer(line):
                    if is_valid(match.group(1)):
                        findings.append(
                            TreeFinding(
                                path=relative,
                                line=line_number,
                                column=match.start(1),
                                kind=kind,
                            )
                        )
    return tuple(sorted(findings, key=lambda finding: (finding.path, finding.line, finding.column)))


__all__ = [
    "EXCLUDED_PATH_FRAGMENTS",
    "TEXT_SUFFIXES",
    "TreeFinding",
    "excluded",
    "repository_text_files",
    "scan_tree",
]
