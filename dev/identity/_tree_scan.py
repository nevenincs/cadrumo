"""Scan the repository working tree for checksum-valid Spanish tax identifiers.

WHY THIS EXISTS. A security review found a live operator identity sitting in an
environment file in the working tree, and the project had no identity or secret
scanner at all -- there is still none in the pre-commit config. The file that
carried it was gitignored, which is not protection: an ignored file is one
``git add -f`` away from history, and the exposure that motivated this reached
the tree exactly that way. So the sweep covers TRACKED, UNTRACKED AND IGNORED
files alike. A scanner that honoured ``.gitignore`` would have been blind to the
very file it was built for.

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

WHY THE GATE IS TIERED BY TRACKING STATE. Only TRACKED content blocks. Tracked
content ships, reaches every clone and cannot be taken back out of history, so a
checksum-valid identity there is the leak. Untracked and ignored content is
reported in a separate, non-blocking operator tier, because a hit there is
routinely the system working rather than a leak: the Cl@ve Movil settings MUST
carry the operator's own DNI or NIE in order to authenticate against AEAT, and
keeping that file gitignored is the correct handling for it.

The tier is decided by tracking state and NEVER by path. A path exclusion for the
environment file would re-create the exact blindness described above. Under the
tier the ignored sweep keeps its full value, and gains its real one: enumerating
ignored files is what proves the operator's own identity has not ALSO landed in
tracked content. That cross-check is the property this canary is finally for, and
it does not exist without the ignored pass.

WHAT THIS DOES NOT COVER, stated rather than implied. Source and prose are
reported, never gated. Binary payloads -- spreadsheets, archives, images -- are
not scanned at all, because a pattern means nothing before extraction. Among
ignored files, machine-generated trees and transient scratch or runtime-state
directories are not enumerated: their contents differ per machine and per hour,
so reading them would give each developer a different verdict, and the price is
that an identity dropped into a scratch directory is invisible here. The operator
tier is reported and never enforced, so nothing stops an untracked identity file
existing -- only its promotion into tracked content is gated. Of the identity
classes, the tax-identity shapes are gated and the bank-account shape is not;
extending the gate to IBAN is an open item. Each of these is a narrowing of the
standing goal, which is that no real identity reaches this repository by any
route.
"""

from __future__ import annotations

import shutil
import subprocess
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from .._paths import UTF_8
from ..sanitizer import ResidualKind, checksum_valid_spans

_UTF_8: Final[str] = UTF_8

#: Suffixes carrying DATA rather than prose. These are the blocking scope: a
#: taxpayer identity in one of these is a payload, and this project has no
#: legitimate reason to ship one.
#:
#: ``.env`` here is the SUFFIXED spelling only, as in ``production.env``. The
#: bare dotfile is not reachable by suffix at all and is matched by name below.
DATA_SUFFIXES: frozenset[str] = frozenset(
    {".json", ".csv", ".toml", ".yml", ".yaml", ".xml", ".txt", ".sql", ".ini", ".cfg", ".env"}
)

#: The environment-file family, matched by NAME because it has no suffix to
#: match on: ``Path(".env").suffix`` is the empty string, since a leading-dot
#: filename is all stem. A suffix set alone therefore selected ``production.env``
#: and missed every ``.env``, ``.env.local`` and ``.env.example`` in the tree --
#: which is the exact shape of the file the motivating exposure arrived in, so
#: the one file class this canary was built for was the one class it could not
#: see.
ENVIRONMENT_FILE_STEM: Final[str] = ".env"

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
    "/_data/manual_corpus_text/manuals/": (
        "extracted text of the bundled AEAT Manual practico publications, whose worked examples "
        "carry fictitious identities the project reproduces verbatim and must not alter"
    ),
    "/docs/_sequences/": (
        "recorded CLI transcripts generated against the documentation demo profile, regenerated "
        "from the demo rather than hand-authored"
    ),
}


#: Path fragments NEVER ENUMERATED in the ignored sweep, each with its reason.
#:
#: These are categorically different from :data:`EXCLUDED_PATH_FRAGMENTS`. An
#: excluded path is read, counted and reported as suppressed; a path here is
#: never opened at all, so nothing about it is measured. That is only defensible
#: for trees this repository does not AUTHOR, and every entry must name such a
#: tree.
#:
#: They apply to the ignored sweep alone. The tracked and untracked sweeps stay
#: unfiltered, so nothing that was in scope before this pass existed can fall
#: out of scope because of it.
UNENUMERATED_PATH_FRAGMENTS: dict[str, str] = {
    "/.git/": "git's own object, index and log store, written by git rather than authored here",
    "/__pycache__/": "compiled Python bytecode, regenerated from the sources beside it",
    "/node_modules/": "installed third-party JavaScript packages, authored by their publishers",
    "/site-packages/": "installed third-party Python distributions, authored by their publishers",
    "/_build/": "generated documentation build output, rebuilt from the sources beside it",
    "/dist/": "packaged build output, rebuilt from the sources beside it",
    "/.state/": "local application state recorded while exercising a harness against a demo profile",
    "/.vault/data/": "generated search and dependency-graph indexes for the development harness",
}

#: Top-level directory-name PREFIXES never enumerated in the ignored sweep.
#:
#: A prefix rather than a fragment because these trees are named by convention
#: and not by a fixed string: scratch directories arrive as ``tmp``,
#: ``tmp-<probe>`` and ``tmp_<probe>`` from whoever created them, so an
#: exhaustive fragment list would be stale the day after it was written.
#:
#: Scratch and local runtime state are excluded for a reason worth stating
#: plainly: their contents vary per machine and per hour, so a gate that read
#: them would return a different verdict for every developer, which is not a
#: gate. The cost is real and is stated rather than glossed: an identity dropped
#: into a scratch or runtime-state directory is NOT covered by this canary.
UNENUMERATED_ROOT_PREFIXES: dict[str, str] = {
    "tmp": "operator and agent scratch trees, transient working directories rather than repository content",
    ".tmp": "the dot-prefixed spelling of the same scratch convention",
    "scratch": "explicitly named scratch working directory",
    "var": "local application runtime state written while exercising the CLI",
    "cadrumo-storage": "an encrypted local bucket store the application writes at whatever root it is run from",
    ".venv": "an installed virtual environment; third-party distributions this repository does not author",
    ".playwright": "browser session dumps written by the Playwright harness",
    "pagefind": "a generated documentation search index, rebuilt by the docs build",
    "htmlcov": "generated coverage report output, rebuilt by the coverage tool from a run",
}

#: Top-level directory-name SUFFIXES never enumerated in the ignored sweep.
#:
#: One entry, and it is a convention rather than a list on purpose: build tools
#: name their caches ``<tool>_cache`` and the set grows whenever a tool is
#: added, so enumerating them by name guarantees the next one is missed.
UNENUMERATED_ROOT_SUFFIXES: dict[str, str] = {
    "_cache": "a build- or lint-tool cache, keyed by content hash and rebuilt on demand",
}


class FileTracking(StrEnum):
    """How git regards a file, which is what decides an occurrence's tier.

    Attributes:
        TRACKED: In the index. Its content ships, reaches every clone and lives
            in history, so an identity here is the leak shape and BLOCKS.
        UNTRACKED: Present in the working tree and not ignored. Operator tier.
        IGNORED: Present and ignored by ``.gitignore``. Operator tier, and the
            expected home of a credential file that must hold the operator's own
            identity in order to authenticate.
    """

    TRACKED = "tracked"
    UNTRACKED = "untracked"
    IGNORED = "ignored"


#: The tracking states whose occurrences FAIL the gate.
#:
#: Tracked content only, and the distinction is the whole point of the tier. A
#: checksum-valid identity in tracked content ships to everyone who clones and
#: cannot be taken back out of history: that is the leak. The same value in an
#: ignored credential file is the system working -- the Cl@ve Movil settings MUST
#: carry the operator's own DNI or NIE to authenticate against AEAT, and gitignore
#: is the correct handling for them.
#:
#: The tier is by tracking state and NEVER by path, because a path exclusion for
#: the environment file is exactly the blindness this canary was rebuilt to
#: remove. The ignored sweep keeps its full value under the tier: it is what
#: proves the operator's own identity has not ALSO landed in tracked content, and
#: that cross-check only exists because ignored files are enumerated.
BLOCKING_TRACKING: frozenset[FileTracking] = frozenset({FileTracking.TRACKED})


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
    tracking: FileTracking

    def rendered(self) -> str:
        """A value-free, deterministic description safe to put in a failure message."""
        return f"{self.path}:{self.line}:{self.column} [{self.kind.value}] ({self.tracking.value})"


@dataclass(frozen=True, slots=True)
class CandidateFile:
    """One enumerated file, with the tracking state that decides its tier."""

    path: Path
    relative: str
    tracking: FileTracking


@dataclass(frozen=True, slots=True)
class TreeScan:
    """The result of one sweep, split into a blocking and an operator tier.

    ``files_scanned`` exists so a green verdict can prove the sweep actually
    looked at files. A scanner that enumerated nothing and reported nothing is
    indistinguishable from a clean tree, and that is the failure mode a canary
    can least afford.

    ``unreadable`` exists for the same reason one step further in. A file the
    scan enumerated but could not open contributes no findings, and counting it
    as scanned would let an unopened file raise the very number that is supposed
    to evidence the sweep. In a security scanner a silent skip IS the defect, so
    such a file is named here, excluded from ``files_scanned``, and asserted
    empty by the gate.
    """

    findings: tuple[TreeFinding, ...]
    operator_findings: tuple[TreeFinding, ...]
    files_scanned: int
    suppressed_by_fragment: dict[str, int]
    unreadable: tuple[str, ...]

    def render(self) -> str:
        """Every blocking finding, one per line, value-free."""
        return "\n".join(finding.rendered() for finding in self.findings)

    def render_operator(self) -> str:
        """Every operator-tier finding, one per line, value-free."""
        return "\n".join(finding.rendered() for finding in self.operator_findings)


def is_environment_file(name: str) -> bool:
    """Whether ``name`` belongs to the ``.env`` family, which has no suffix to match.

    Covers the bare ``.env`` and every variant spelling built on it --
    ``.env.local``, ``.env.production``, ``.env.example`` -- because the variant
    word occupies the suffix slot and so is never a file-kind suffix at all.
    """
    lowered = name.lower()
    return lowered == ENVIRONMENT_FILE_STEM or lowered.startswith(f"{ENVIRONMENT_FILE_STEM}.")


def in_scope(path: Path, suffixes: frozenset[str]) -> bool:
    """Whether ``path`` belongs to the file class ``suffixes`` selects.

    An environment file is data by nature, so it is selected whenever the data
    class is being selected and never when only the narrative class is.
    """
    if is_environment_file(path.name):
        return bool(suffixes & DATA_SUFFIXES)
    return path.suffix.lower() in suffixes


def unenumerated_reason(relative_path: str) -> str | None:
    """The stated reason the ignored sweep never opens ``relative_path``, or ``None``."""
    haystack = f"/{relative_path}"
    for fragment, reason in UNENUMERATED_PATH_FRAGMENTS.items():
        if fragment in haystack:
            return reason
    root = relative_path.split("/", 1)[0]
    for prefix, reason in UNENUMERATED_ROOT_PREFIXES.items():
        if root.startswith(prefix):
            return reason
    for suffix, reason in UNENUMERATED_ROOT_SUFFIXES.items():
        if root.endswith(suffix):
            return reason
    return None


def _git_lines(repo_root: Path, arguments: list[str]) -> list[str]:
    """One ``git ls-files`` enumeration, as repository-relative POSIX paths.

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
        [executable, "ls-files", *arguments],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def repository_files(repo_root: Path, *, suffixes: frozenset[str]) -> list[CandidateFile]:
    """Every tracked, untracked AND ignored file of the class ``suffixes`` selects.

    Three enumerations, because the tier is decided by tracking state and one
    ``ls-files`` invocation cannot report which state a path came from.
    ``--exclude-standard`` applies ``.gitignore``, so the first two passes omit
    every ignored file; the third asks for exactly those. Reading only the
    unignored passes is how a canary comes to report a clean tree while an
    operator identity sits in an ignored file one ``git add -f`` from history.

    The ignored pass, and only the ignored pass, skips the trees named in
    :data:`UNENUMERATED_PATH_FRAGMENTS`, :data:`UNENUMERATED_ROOT_PREFIXES` and
    :data:`UNENUMERATED_ROOT_SUFFIXES` -- installed packages, build output, tool
    caches, scratch and local runtime state, each with its stated reason. Without
    them the sweep opens several hundred thousand machine-written files and
    returns a verdict that depends on which probe directories happen to exist
    today. The tracked and untracked passes are deliberately left unfiltered.

    A path is credited to the FIRST state that claims it, tracked first, so a
    file that somehow appears in two enumerations can only ever be classified
    more strictly rather than less.
    """
    tracking: dict[str, FileTracking] = {}
    for line in _git_lines(repo_root, ["--cached"]):
        tracking.setdefault(line, FileTracking.TRACKED)
    for line in _git_lines(repo_root, ["--others", "--exclude-standard"]):
        tracking.setdefault(line, FileTracking.UNTRACKED)
    for line in _git_lines(repo_root, ["--others", "--ignored", "--exclude-standard"]):
        if unenumerated_reason(line) is None:
            tracking.setdefault(line, FileTracking.IGNORED)

    files: list[CandidateFile] = []
    for line in sorted(tracking):
        path = repo_root / line
        if in_scope(path, suffixes) and path.is_file():
            files.append(CandidateFile(path=path, relative=line, tracking=tracking[line]))
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


def _read_text(path: Path) -> str | None:
    """The file's text, or ``None`` when it could not be opened.

    Decoding never fails -- undecodable bytes are replaced -- so ``None`` means
    the operating system refused the read: a permission denial, a lock, or a file
    that vanished between enumeration and open. The caller records it by name
    rather than treating it as an empty file.
    """
    try:
        return path.read_text(encoding=_UTF_8, errors="replace")
    except OSError:
        return None


def _file_findings(text: str, candidate: CandidateFile, kinds: frozenset[ResidualKind]) -> list[TreeFinding]:
    """Every checksum-valid occurrence in one file's text, value-free."""
    findings: list[TreeFinding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for kind, column, _match in checksum_valid_spans(line, kinds):
            findings.append(
                TreeFinding(
                    path=candidate.relative,
                    line=line_number,
                    column=column,
                    kind=kind,
                    tracking=candidate.tracking,
                )
            )
    return findings


def _ordered(findings: list[TreeFinding]) -> tuple[TreeFinding, ...]:
    return tuple(sorted(findings, key=lambda finding: (finding.path, finding.line, finding.column)))


#: The tax-identity classes, all of them checksum-verified. The shape-only
#: classes carry no arithmetic check, so over a whole repository they would
#: report ordinary prose and configuration rather than identities.
#:
#: All three tax shapes, not one. A natural person's document is digit-led or
#: led by an X/Y/Z or K/L/M prefix; a legal entity's is led by a company kind
#: letter; and either may be written in its ES-prefixed intra-community
#: spelling, which neither of the other two patterns can see past the prefix. A
#: gate carrying only the personal shape passes a company's tax identity, and a
#: company's identity in a shipped payload is the same leak.
#:
#: The bank-account class is checksum-verified too and is deliberately NOT here:
#: gating it is a scope decision this canary has not taken, and leaving it
#: unstated would be the false capability claim this constant already made once.
BLOCKING_KINDS: frozenset[ResidualKind] = frozenset({ResidualKind.NIF_NIE, ResidualKind.CIF, ResidualKind.NIF_IVA})


def scan_tree(
    repo_root: Path,
    *,
    kinds: frozenset[ResidualKind] | None = None,
    files: Sequence[CandidateFile] | None = None,
) -> TreeScan:
    """Every checksum-valid identity occurrence in the in-scope data payloads.

    Occurrences are split by the file's tracking state, never by its path.
    Tracked content fails the gate; untracked and ignored content is reported in
    the operator tier. Both tiers are read from the same sweep and neither can
    remove a file from the other: a tracked file is tracked whatever directory it
    sits in, so the tier cannot become a route out of the blocking set.

    The suppressed tally is returned alongside the findings so a caller can prove
    each exclusion is still doing work. It counts occurrences, never values.

    Args:
        repo_root: The working tree to scan.
        kinds: Restrict to these pattern classes, defaulting to
            :data:`BLOCKING_KINDS`.
        files: A pre-enumerated candidate list, narrowed here to the data class.
            Enumerating the tree costs three git walks, so a caller running both
            this and :func:`advisory_findings` passes one
            :func:`repository_files` result to both rather than paying for it
            twice.
    """
    selected = kinds if kinds is not None else BLOCKING_KINDS
    findings: list[TreeFinding] = []
    operator: list[TreeFinding] = []
    suppressed: Counter[str] = Counter()
    unreadable: list[str] = []
    scanned = 0
    for candidate in _candidates(repo_root, files, DATA_SUFFIXES):
        text = _read_text(candidate.path)
        if text is None:
            unreadable.append(candidate.relative)
            continue
        fragments = matching_fragments(candidate.relative)
        if fragments:
            hits = _file_findings(text, candidate, selected)
            for fragment in fragments:
                suppressed[fragment] += len(hits)
            continue
        scanned += 1
        tier = findings if candidate.tracking in BLOCKING_TRACKING else operator
        tier.extend(_file_findings(text, candidate, selected))
    return TreeScan(
        findings=_ordered(findings),
        operator_findings=_ordered(operator),
        files_scanned=scanned,
        suppressed_by_fragment=dict(suppressed),
        unreadable=tuple(sorted(unreadable)),
    )


def advisory_findings(
    repo_root: Path,
    *,
    kinds: frozenset[ResidualKind] | None = None,
    files: Sequence[CandidateFile] | None = None,
) -> tuple[TreeFinding, ...]:
    """Everything the blocking scope leaves out, reported rather than gated.

    Two populations: the narrative surfaces (source, markdown, prose), and the
    excluded data paths. Keeping them observable is what stops the narrowing from
    being silent -- a scope nobody can see the size of is a scope nobody can argue
    with.

    A file that cannot be opened is skipped here. This is a census rather than a
    gate, and the honest count of unopenable files is
    :attr:`TreeScan.unreadable`, which the gate asserts empty over the same disk.
    """
    selected = kinds if kinds is not None else BLOCKING_KINDS
    findings: list[TreeFinding] = []
    for candidate in _candidates(repo_root, files, SCANNED_SUFFIXES):
        in_narrative = candidate.path.suffix.lower() in NARRATIVE_SUFFIXES
        if not in_narrative and not matching_fragments(candidate.relative):
            continue
        text = _read_text(candidate.path)
        if text is None:
            continue
        findings.extend(_file_findings(text, candidate, selected))
    return _ordered(findings)


def _candidates(
    repo_root: Path,
    files: Sequence[CandidateFile] | None,
    suffixes: frozenset[str],
) -> list[CandidateFile]:
    """The candidate files of one class, enumerating only when none were supplied."""
    if files is None:
        return repository_files(repo_root, suffixes=suffixes)
    return [candidate for candidate in files if in_scope(candidate.path, suffixes)]


__all__ = [
    "BLOCKING_KINDS",
    "BLOCKING_TRACKING",
    "DATA_SUFFIXES",
    "ENVIRONMENT_FILE_STEM",
    "EXCLUDED_PATH_FRAGMENTS",
    "NARRATIVE_SUFFIXES",
    "SCANNED_SUFFIXES",
    "UNENUMERATED_PATH_FRAGMENTS",
    "UNENUMERATED_ROOT_PREFIXES",
    "UNENUMERATED_ROOT_SUFFIXES",
    "CandidateFile",
    "FileTracking",
    "TreeFinding",
    "TreeScan",
    "advisory_findings",
    "exclusion_reason",
    "in_scope",
    "is_environment_file",
    "matching_fragments",
    "repository_files",
    "scan_tree",
    "unenumerated_reason",
]
