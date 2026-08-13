"""Scan the repository working tree for checksum-valid Spanish tax identifiers.

WHY THIS EXISTS. The 2026-05-30 security audit recommended an identity-pattern
canary and none was built; there is no identity or secret scanner in the
pre-commit config at all. The exposure that motivated it reached the tree through
a file that was gitignored and committed anyway, so this scans TRACKED AND
UNTRACKED files both.

DETECTION IS NOT IMPLEMENTED HERE. The pattern, the checksum and the value-free
finding shape all come from the sanitiser's identity detection, reached through
:mod:`dev.sanitizer`, which already imports
:func:`cadrumo.core.identity.validate_identity` rather than restating the AEAT
control-letter algorithm. Re-deriving any of it would be a second authority for
one rule. This module contributes the SURFACE (a working tree rather than a
sanitised PDF) and the SCOPE decision, nothing else.

HANDLING RULE, ABSOLUTE AND INHERITED. A finding never carries the matched text.
It carries the path, the line, the column and the pattern class. Anything that
reads a finding -- an assertion message, a log line, a report -- is therefore
incapable of disclosing the value it found. A canary that hardcodes or echoes the
identifier it hunts would republish the exposure it exists to prevent.

WHY THERE IS NO VALUE ALLOWLIST. The sharpest possible discriminator would be
"fail on a checksum-valid identifier outside the declared synthetic set", because
the tree's identifiers are few and stable. That needs the set stored. Storing
values republishes them. Storing HASHES does not help: the eight-digit-plus-letter
space is about 2.3e9, trivially brute-forced from an unsalted digest, and no
secret salt exists in-repo -- so a hash baseline is disclosure wearing a checksum.
Worse, a value allowlist is precisely where a real leak would be silenced by
whoever hit the red gate. Scope is therefore decided BY PATH AND FILE KIND, each
exclusion carrying its reason.

WHY THE BLOCKING SCOPE IS DATA PAYLOADS ONLY, and what that deliberately gives
up. Measured over the whole tree, pattern-plus-checksum reports thousands of
occurrences, essentially all of them deliberate: synthetic fixture identities,
format examples in docstrings and operator help text, and demo values in
READMEs. Nothing in the repository distinguishes a deliberate example from a real
leak -- the convention is real but undeclared -- so a whole-tree gate would be
noise, and noise trains every reader to ignore it.

A payload is different. A ``.json``, ``.csv``, ``.toml`` or ``.yml`` file outside
the fixture corpus carries data, not prose, and this project has no legitimate
reason to ship a taxpayer identity as data. That is also the shape the motivating
exposure took: a captured artefact dropped into the tree, not a sentence someone
wrote. So the blocking scope is data payloads, where the tree is provably clean
today, and the narrative surfaces are reported by :func:`advisory_findings`
instead of gated. Extending the gate to source and prose needs a declared
synthetic-identity convention first; that is an open item, not a solved one.
"""

from __future__ import annotations

import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dev.sanitizer import ResidualKind, checksum_valid_spans

_UTF_8: Final[str] = "utf-8"

#: Suffixes carrying DATA rather than prose. These are the blocking scope: a
#: taxpayer identity in one of these is a payload, and this project has no
#: legitimate reason to ship one.
DATA_SUFFIXES: frozenset[str] = frozenset(
    {".json", ".csv", ".toml", ".yml", ".yaml", ".xml", ".txt", ".sql", ".ini", ".cfg", ".env"}
)

#: Suffixes carrying prose or source. Reported as advisory, never blocking: every
#: occurrence measured in these is a format example, a docstring specimen or a
#: demo command, and no declared convention separates those from a real leak.
NARRATIVE_SUFFIXES: frozenset[str] = frozenset({".py", ".md", ".rst", ".html", ".sh", ".ps1", ".j2"})

#: Binaries are a different problem with a different detector: the sanitiser owns
#: PDFs, and a spreadsheet or archive needs extraction before a pattern means
#: anything. Neither suffix set admits one.
SCANNED_SUFFIXES: frozenset[str] = DATA_SUFFIXES | NARRATIVE_SUFFIXES

#: Path fragments excluded from the BLOCKING scope, each with the reason it is
#: excluded. NEVER a value allowlist: an allowlist of identifiers is the one
#: artefact that would carry the identifier this canary exists to keep out of the
#: repository.
#:
#: Every entry must still be suppressing a real occurrence. An exclusion that
#: covers nothing is a claim about the tree that stopped being true, and it must
#: be deleted rather than left standing as a widening nobody re-reads.
EXCLUDED_PATH_FRAGMENTS: dict[str, str] = {
    "/tests/": (
        "the project uses structurally valid synthetic identities in fixtures as established "
        "practice; the convention is undeclared, which is what keeps this corpus ungateable"
    ),
    "/fixtures/": "fixture payloads carry synthetic identities by construction",
    "/src/cadrumo/locales/": (
        "operator help strings illustrate the NIF, NIE and CIF formats, so a format example is "
        "the content rather than a leak"
    ),
    "/src/cadrumo/_data/corpus/": (
        "byte-exact bundled BOE and AEAT text; a match there is the authority's own worked "
        "example and must not be edited"
    ),
    "/docs/_sequences/": (
        "recorded CLI transcripts generated against the documentation demo profile, regenerated "
        "from the demo rather than hand-authored"
    ),
}


@dataclass(frozen=True, slots=True)
class TreeFinding:
    """One checksum-valid identity occurrence, WITHOUT the value.

    Carries where and what class, never what. Sorting is by location so assertion
    output is deterministic across runs and platforms.
    """

    path: str
    line: int
    column: int
    kind: ResidualKind

    def rendered(self) -> str:
        """A value-free, deterministic description safe to put in a failure message."""
        return f"{self.path}:{self.line}:{self.column} [{self.kind.value}]"


@dataclass(frozen=True, slots=True)
class TreeScan:
    """The result of one blocking-scope sweep.

    ``files_scanned`` exists so a green verdict can prove the sweep actually
    looked at files. A scanner that enumerated nothing and reported nothing is
    indistinguishable from a clean tree, and that is the failure mode a canary
    can least afford.
    """

    findings: tuple[TreeFinding, ...]
    files_scanned: int
    suppressed_by_fragment: dict[str, int]

    def render(self) -> str:
        """Every finding, one per line, value-free."""
        return "\n".join(finding.rendered() for finding in self.findings)


def repository_files(repo_root: Path, *, suffixes: frozenset[str]) -> list[Path]:
    """Every tracked AND untracked file of ``suffixes``, honouring ``.gitignore``.

    Untracked files are included deliberately. The exposure this canary answers to
    arrived through a file that was gitignored and committed anyway, so a scanner
    that only reads the index would have been blind to it at the moment it
    mattered.

    The git executable is resolved rather than taken from the argv shorthand: a
    canary whose enumeration silently resolves to whatever ``git`` a PATH entry
    happens to supply is a canary that can be pointed at a different tree than the
    one being guarded, and a machine without git gets one plain sentence instead
    of a file-not-found traceback from inside a security scan.
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
        if candidate.suffix.lower() in suffixes and candidate.is_file():
            files.append(candidate)
    return files


def exclusion_reason(relative_path: str) -> str | None:
    """The stated reason ``relative_path`` is out of the blocking scope, or ``None``."""
    haystack = f"/{relative_path}"
    for fragment, reason in EXCLUDED_PATH_FRAGMENTS.items():
        if fragment in haystack:
            return reason
    return None


def matching_fragments(relative_path: str) -> tuple[str, ...]:
    """EVERY excluding fragment ``relative_path`` matches, not merely the first.

    Overlap is real -- a fixture directory usually sits under a test directory --
    and attributing an occurrence to whichever fragment happened to be declared
    first would make dictionary order decide which exclusion looks like it is
    doing work. Each fragment is credited with everything it covers, so the
    staleness question ("is this exclusion still suppressing anything?") is
    answered per fragment and independently.
    """
    haystack = f"/{relative_path}"
    return tuple(fragment for fragment in EXCLUDED_PATH_FRAGMENTS if fragment in haystack)


def _file_findings(path: Path, relative: str, kinds: frozenset[ResidualKind]) -> list[TreeFinding]:
    """Every checksum-valid occurrence in one file, value-free."""
    try:
        text = path.read_text(encoding=_UTF_8, errors="replace")
    except OSError:
        return []
    findings: list[TreeFinding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for kind, column, _candidate in checksum_valid_spans(line, kinds):
            findings.append(TreeFinding(path=relative, line=line_number, column=column, kind=kind))
    return findings


def _ordered(findings: list[TreeFinding]) -> tuple[TreeFinding, ...]:
    return tuple(sorted(findings, key=lambda finding: (finding.path, finding.line, finding.column)))


#: Only checksum-verified classes are scanned. The shape-only classes carry no
#: arithmetic check, so over a whole repository they would report ordinary prose
#: and configuration rather than identities.
BLOCKING_KINDS: frozenset[ResidualKind] = frozenset({ResidualKind.NIF_NIE})


def scan_tree(repo_root: Path, *, kinds: frozenset[ResidualKind] | None = None) -> TreeScan:
    """Every checksum-valid identity occurrence in the in-scope data payloads.

    The suppressed tally is returned alongside the findings so a caller can prove
    each exclusion is still doing work. It counts occurrences, never values.
    """
    selected = kinds if kinds is not None else BLOCKING_KINDS
    findings: list[TreeFinding] = []
    suppressed: Counter[str] = Counter()
    scanned = 0
    for path in repository_files(repo_root, suffixes=DATA_SUFFIXES):
        relative = path.relative_to(repo_root).as_posix()
        fragments = matching_fragments(relative)
        if fragments:
            hits = _file_findings(path, relative, selected)
            for fragment in fragments:
                suppressed[fragment] += len(hits)
            continue
        scanned += 1
        findings.extend(_file_findings(path, relative, selected))
    return TreeScan(
        findings=_ordered(findings),
        files_scanned=scanned,
        suppressed_by_fragment=dict(suppressed),
    )


def advisory_findings(repo_root: Path, *, kinds: frozenset[ResidualKind] | None = None) -> tuple[TreeFinding, ...]:
    """Everything the blocking scope leaves out, reported rather than gated.

    Two populations: the narrative surfaces (source, markdown, prose), and the
    excluded data paths. Keeping them observable is what stops the narrowing from
    being silent -- a scope nobody can see the size of is a scope nobody can argue
    with.
    """
    selected = kinds if kinds is not None else BLOCKING_KINDS
    findings: list[TreeFinding] = []
    for path in repository_files(repo_root, suffixes=SCANNED_SUFFIXES):
        relative = path.relative_to(repo_root).as_posix()
        in_narrative = path.suffix.lower() in NARRATIVE_SUFFIXES
        if not in_narrative and not matching_fragments(relative):
            continue
        findings.extend(_file_findings(path, relative, selected))
    return _ordered(findings)


__all__ = [
    "BLOCKING_KINDS",
    "DATA_SUFFIXES",
    "EXCLUDED_PATH_FRAGMENTS",
    "NARRATIVE_SUFFIXES",
    "SCANNED_SUFFIXES",
    "TreeFinding",
    "TreeScan",
    "advisory_findings",
    "exclusion_reason",
    "matching_fragments",
    "repository_files",
    "scan_tree",
]
