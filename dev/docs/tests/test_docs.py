"""Static hygiene for executable-looking shell examples in documentation."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from cadrumo.core import scan_directory

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT
_DOCS_ROOT = _REPO_ROOT / "docs"
_SHELL_FENCE_RE = re.compile(r"```(?:bash|sh|pwsh)\n(?P<body>.*?)\n```", re.DOTALL)

# A fenced-code opening/closing line: an optionally-indented run of three or more
# backticks or tildes. The prose-hygiene gates strip whole fenced blocks (code,
# CLI output, cli-sequence directive bodies) before counting, so only
# reader-facing prose is measured.
_FENCE_LINE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def _strip_fenced_blocks(text: str) -> str:
    """Return the text with every fenced block replaced by a blank line.

    A line-based stripper (not a ``.*?`` regex): it tracks the open fence's
    character and length, so a fenced block is excluded in FULL regardless of its
    indentation, its fence character (``` ``` ``` or ``~~~``), or a longer fence
    run, and an unclosed fence drops to end of input rather than mis-pairing with
    a later fence. This is the same robust strip the CLI conformance gate applies
    to its inline-span scan; it replaces a greedy regex that mis-paired on odd
    fence structures.
    """
    out: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    for line in text.split("\n"):
        match = _FENCE_LINE_RE.match(line)
        run = match.group(1) if match else ""
        if fence_char is None:
            if match:
                fence_char = run[0]
                fence_len = len(run)
                out.append("")
            else:
                out.append(line)
            continue
        if match and run[0] == fence_char and len(run) >= fence_len and line.strip()[len(run) :].strip() == "":
            fence_char = None
            out.append("")
    return "\n".join(out)


# The em-dash (U+2014). Its per-page counts ratchet DOWN from a checked-in
# baseline; a page may only decrease, a page absent from the baseline starts at
# zero, and a page below its baseline passes (so a prose sweep never reds the
# tree mid-flight). Replace an em dash with a hyphen or a full stop.
_EM_DASH = "—"
_EM_DASH_BASELINE_PATH = Path(__file__).resolve().parent / "emdash_baseline.json"

# LLM-tell phrases banned outright from reader-facing prose (word-boundary,
# case-insensitive). Kept modest to avoid false positives.
_LLM_MARKERS = (
    "Additionally,",
    "It's worth noting",
    "Keep in mind",
    "Let's ",
    "we'll ",
    "seamless",
    "leverage",
    "streamline",
    "delve",
    "go ahead and",
)


#: LLM-tell phrases that are a tell only when they OPEN a sentence, because the
#: same words are ordinary English mid-sentence. "Note that" is the worked
#: example: banned as a sentence opener, but "it is an internal note that you
#: have already presented the file" is correct prose that a word-boundary match
#: flags anyway. Rewording good prose to satisfy a pattern that does not fit the
#: data is the wrong direction, so the pattern carries the sentence constraint.
_LLM_MARKERS_SENTENCE_INITIAL = ("Note that",)

#: Matches at the start of a line, or immediately after sentence-ending
#: punctuation. Each lookbehind is fixed-width, which Python's ``re`` requires.
_SENTENCE_START = r"(?:^|(?<=[.!?]\s)|(?<=[.!?]\s\s))"


def _marker_pattern(marker: str, *, sentence_initial: bool = False) -> re.Pattern[str]:
    """Compile a case-insensitive pattern for one LLM-tell marker.

    ``sentence_initial`` anchors the marker to a sentence opening. Without it a
    ban on a common English word sequence over-matches, and a gate that forces
    correct prose to be reworded teaches its reader to distrust it.
    """
    pattern = (_SENTENCE_START if sentence_initial else "") + r"\b" + re.escape(marker)
    if marker[-1].isalnum():
        pattern += r"\b"
    return re.compile(pattern, re.IGNORECASE | re.MULTILINE)


_LLM_MARKER_RES = tuple(
    [(marker, _marker_pattern(marker)) for marker in _LLM_MARKERS]
    + [(marker, _marker_pattern(marker, sentence_initial=True)) for marker in _LLM_MARKERS_SENTENCE_INITIAL]
)


def _prose(text: str) -> str:
    """Return the page text with fenced blocks removed, so only prose remains."""
    return _strip_fenced_blocks(text)


def _em_dash_counts() -> dict[str, int]:
    """Return the per-page em-dash count in prose, keyed by docs-relative path."""
    counts: dict[str, int] = {}
    for path in _markdown_docs():
        count = _prose(path.read_text(encoding="utf-8")).count(_EM_DASH)
        if count:
            counts[path.relative_to(_DOCS_ROOT).as_posix()] = count
    return counts


_DANGEROUS_COMMAND_PATTERNS = (
    re.compile(r"\brm\s+-rf\b"),
    re.compile(r"\bRemove-Item\b.*\s-(?:Recurse|r)\b", re.IGNORECASE),
    re.compile(r"\bgit\s+reset\s+--hard\b"),
    # The force flag may be bundled with other short flags (-fd, -fdx, -xdf) or
    # spelled long (--force), so the scan looks for a flag token CONTAINING `f`
    # rather than one ENDING in it. The earlier `-[^\n]*f\b` required a word
    # boundary immediately after the `f`, which `-fd` and `-fdx` do not provide,
    # so the two spellings the safety rule names most often went unmatched.
    re.compile(r"\bgit\s+clean\b[^\n]*?(?:\s-{1,2}[a-z]*f|\s--force)", re.IGNORECASE),
)

# The pre-correction `git clean` pattern, retained ONLY as the negative half of
# the control below: it must still fail the bundled-flag cases, which is what
# proves the correction changed real behaviour rather than being cosmetic.
_RETIRED_GIT_CLEAN_PATTERN = re.compile(r"\bgit\s+clean\s+-[^\n]*f\b")


def _markdown_docs() -> tuple[Path, ...]:
    """Return checked-in markdown documentation pages.

    Refuses an empty result rather than returning one. Three gates scan this
    corpus for violations and assert the offender list is empty; over an empty
    corpus each reports exactly what a clean corpus reports, so the proof of
    scan belongs here, once, rather than at each call site.
    """
    pages = tuple(
        path for path in scan_directory(_DOCS_ROOT, pattern="*.md", recursive=True) if "_build" not in path.parts
    )
    assert pages, f"no markdown documentation pages found under {_DOCS_ROOT}"
    return pages


def _shell_fence_commands(path: Path) -> list[tuple[int, str]]:
    """Return executable-looking command lines from shell fences in one page."""
    source = path.read_text(encoding="utf-8")
    commands: list[tuple[int, str]] = []
    for match in _SHELL_FENCE_RE.finditer(source):
        fence_start_line = source[: match.start()].count("\n") + 1
        for offset, raw_line in enumerate(match.group("body").splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("$ "):
                line = line[2:].strip()
            commands.append((fence_start_line + offset, line))
    return commands


def test_documentation_shell_examples_are_static_inventory() -> None:
    """Docs shell examples are inventoried but never executed at collection time."""
    command_sites = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}:{lineno}: {command}"
        for path in _markdown_docs()
        for lineno, command in _shell_fence_commands(path)
    ]

    assert command_sites, "expected at least one shell example in docs markdown"


def test_documentation_shell_examples_do_not_embed_destructive_commands() -> None:
    """Documentation shell fences must not publish destructive one-liners."""
    violations: list[str] = []
    for path in _markdown_docs():
        relative = path.relative_to(_REPO_ROOT).as_posix()
        for lineno, command in _shell_fence_commands(path):
            if any(pattern.search(command) for pattern in _DANGEROUS_COMMAND_PATTERNS):
                violations.append(f"{relative}:{lineno}: {command}")

    assert not violations, "destructive shell examples in docs:\n" + "\n".join(violations)


def test_dangerous_command_patterns_discriminate() -> None:
    """Positive control: each destructive-command pattern matches and rejects by measurement.

    The scan below reports zero hits over the whole corpus, so on its own it is
    green whether it is satisfied or simply blind. These cases pin each pattern
    against a command it MUST flag and a near-miss it MUST NOT, independently of
    what the documentation happens to contain.
    """
    must_match = (
        "rm -rf /tmp/build",
        "sudo rm -rf ~/cadrumo",
        "Remove-Item -Recurse -Force .venv",
        "Remove-Item -r .venv",
        "git reset --hard origin/main",
        "git clean -f",
        "git clean -fd",
        "git clean -fdx",
        "git clean -xdf",
        "git clean -d -f",
        "git clean --force",
    )
    must_not_match = (
        "rm build.log",
        "git reset --soft HEAD~1",
        "git clean --dry-run",
        "git clean -n",
        "git clean -d",
        "Remove-Item build.log",
    )
    for command in must_match:
        assert any(pattern.search(command) for pattern in _DANGEROUS_COMMAND_PATTERNS), (
            f"no destructive-command pattern flags {command!r}"
        )
    for command in must_not_match:
        assert not any(pattern.search(command) for pattern in _DANGEROUS_COMMAND_PATTERNS), (
            f"a destructive-command pattern over-matches the benign {command!r}"
        )


def test_the_retired_git_clean_pattern_really_missed_the_bundled_flags() -> None:
    """The correction is real: the previous pattern cannot see ``-fd`` or ``-fdx``.

    Without this the fix is unfalsifiable — a pattern edit that changed nothing
    would leave the control above passing exactly as before. The retired form is
    asserted to FAIL the same inputs the current form matches, so the two are
    proven to differ on the cases that matter.
    """
    for missed in ("git clean -fd", "git clean -fdx", "git clean --force"):
        assert not _RETIRED_GIT_CLEAN_PATTERN.search(missed), (
            f"the retired pattern matches {missed!r}; the correction would be cosmetic"
        )
        assert any(pattern.search(missed) for pattern in _DANGEROUS_COMMAND_PATTERNS), (
            f"the current pattern set still misses {missed!r}"
        )
    # Both forms agree on the spelling the retired pattern did handle, so the
    # correction widened coverage rather than trading one blind spot for another.
    assert _RETIRED_GIT_CLEAN_PATTERN.search("git clean -f")


def test_llm_marker_patterns_discriminate() -> None:
    """Positive control: every banned-phrase pattern matches its phrase and respects word boundaries.

    ``_marker_pattern`` builds each pattern by escaping the marker and appending
    a trailing boundary only when the marker ends alphanumerically. A marker that
    stopped matching its own phrase would silence one ban with no other signal.
    """
    for marker, pattern in _LLM_MARKER_RES:
        assert pattern.search(f"Some prose. {marker} then more."), (
            f"marker {marker!r} no longer matches its own phrase (pattern {pattern.pattern!r})"
        )
        assert not pattern.search(f"Some prose. X{marker}Y then more."), (
            f"marker {marker!r} matches inside a longer word (pattern {pattern.pattern!r})"
        )


def test_a_sentence_initial_marker_ignores_the_same_words_mid_sentence() -> None:
    """The ban catches the tell and leaves ordinary English alone.

    "Note that" opening a sentence is the LLM tell. The same two words as a noun
    plus a relative pronoun are correct prose, and two how-to pages carry exactly
    that: "it is an internal note that you have already presented the file". A
    word-boundary match flagged both, and the only ways out are rewording good
    prose or narrowing the pattern. Rewording to satisfy an instrument that does
    not fit the data is how a gate gets edited instead of read.
    """
    pattern = _marker_pattern("Note that", sentence_initial=True)

    assert pattern.search("Note that the deadline moves."), "a sentence-opening tell must still be caught"
    assert pattern.search("Run the export. Note that the file stays local."), (
        "a tell opening a later sentence must still be caught"
    )
    assert not pattern.search("it is an internal note that you have already presented the file"), (
        "the noun 'note' plus a relative pronoun is ordinary prose and must not be flagged"
    )
    assert not pattern.search("Keep a short note that records the reference."), (
        "a mid-sentence noun phrase must not be flagged"
    )


def test_every_sentence_initial_marker_is_anchored() -> None:
    """Anti-vacuity: the sentence-initial set is non-empty and really anchored.

    Without this the set could silently empty, or its patterns could lose the
    anchor, and the test above would still pass while the distinction it exists
    for had stopped being made.
    """
    assert _LLM_MARKERS_SENTENCE_INITIAL, "the sentence-initial marker set is empty; nothing is being anchored"
    for marker in _LLM_MARKERS_SENTENCE_INITIAL:
        pattern = _marker_pattern(marker, sentence_initial=True)
        assert not pattern.search(f"a preceding clause {marker.lower()} continues"), (
            f"marker {marker!r} is not anchored to a sentence opening"
        )


def test_the_scanned_markdown_corpus_is_not_empty() -> None:
    """Every scan in this module is vacuous over an empty page list."""
    docs = _markdown_docs()
    assert len(docs) > 20, f"expected the docs corpus, scanned only {len(docs)} markdown page(s)"


def test_documentation_install_snippets_cite_the_current_version() -> None:
    """Every versioned install reference in docs matches the shipped package version.

    The install pages cite the release wheel filename (``cadrumo-X.Y.Z-...whl``)
    and pinned uvx/pip specs (``cadrumo[agent]==X.Y.Z``). A hardcoded version
    rots silently on every release — the 0.2.0→0.2.1 bump left five stale
    install commands behind — so this gate pins every cited version to
    ``cadrumo.__version__``.
    """
    from cadrumo import __version__

    version_re = re.compile(
        r"cadrumo-(\d+\.\d+\.\d+)-py3|cadrumo\[[\w,]+\]==(\d+\.\d+\.\d+)|release is `(\d+\.\d+\.\d+)`"
    )
    violations: list[str] = []
    for path in _markdown_docs():
        relative = path.relative_to(_REPO_ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        for match in version_re.finditer(source):
            cited = next(group for group in match.groups() if group)
            if cited != __version__:
                lineno = source[: match.start()].count("\n") + 1
                violations.append(f"{relative}:{lineno}: cites {cited}, package is {__version__}")

    assert not violations, "stale install versions in docs:\n" + "\n".join(violations)


def test_em_dash_count_ratchets_down_in_docs_prose() -> None:
    """No docs page carries more em dashes (U+2014) in prose than its ratcheting baseline.

    Em dashes are an LLM tell the operator wants out of the corpus. The count
    ratchets DOWN from a committed per-page baseline: a page may never exceed its
    baseline, a page absent from the baseline may carry none, and a page below its
    baseline passes (so the prose sweep never reds the tree mid-flight). Code
    fences and CLI-output fences are exempt; only prose lines count. Converter and
    editorial agents tighten emdash_baseline.json down as they land; an empty
    baseline means the corpus is em-dash-free.
    """
    baseline: dict[str, int] = json.loads(_EM_DASH_BASELINE_PATH.read_text(encoding="utf-8"))
    current = _em_dash_counts()
    assert current, "no docs prose was counted; an empty corpus ratchets to zero without prose changing"
    problems: list[str] = []
    for page in sorted(current):
        count = current[page]
        allowed = baseline.get(page, 0)
        if count > allowed:
            problems.append(
                f"docs/{page}: {count} em dash(es) (U+2014) in prose, baseline allows {allowed}. "
                f"Replace a new em dash with a hyphen or a full stop, then tighten {_EM_DASH_BASELINE_PATH.name}"
            )
    assert not problems, "new em dashes in docs prose (they only ratchet down):\n  " + "\n  ".join(problems)


def test_prose_strip_excludes_fenced_blocks_robustly() -> None:
    """The line-based prose strip excludes a fenced block in full regardless of form.

    An em dash inside a code/CLI-output/directive fence must never be counted; the
    hardened strip handles indentation (a directive nested in a list item), the
    tilde fence character, and a longer fence run, and drops an unclosed fence to
    end of input instead of mis-pairing with a later fence — while a genuine em
    dash in prose is still measured.
    """
    indented_in_list = (
        "- A step — with an em dash in prose:\n"
        "\n"
        "  ```{cli-sequence} demo\n"
        "  @result aeat --format json config check — fenced em dash, must not count\n"
        "  ```\n"
    )
    prose = _prose(indented_in_list)
    assert prose.count(_EM_DASH) == 1  # only the prose em dash, not the fenced one

    tilde_and_unclosed = (
        "Prose with no dash here.\n\n"
        "~~~text\n"
        "fenced — dash ignored\n"
        "~~~\n\n"
        "```bash\n"
        "trailing unclosed fence — dash ignored to end of input\n"
    )
    assert _prose(tilde_and_unclosed).count(_EM_DASH) == 0


def test_no_llm_tell_markers_in_docs_prose() -> None:
    """Reader-facing docs prose carries none of the banned LLM-tell phrases (hard zero).

    Code fences and CLI-output fences are exempt; only prose lines are scanned.
    Unlike the em-dash count this is a hard zero, not a ratchet: the listed
    phrases must not appear at all.
    """
    hits: list[str] = []
    for path in _markdown_docs():
        prose = _prose(path.read_text(encoding="utf-8"))
        relative = path.relative_to(_DOCS_ROOT).as_posix()
        for marker, pattern in _LLM_MARKER_RES:
            for match in pattern.finditer(prose):
                lineno = prose[: match.start()].count("\n") + 1
                hits.append(f"docs/{relative}:{lineno}: banned LLM-tell phrase {marker!r}")
    assert not hits, (
        "LLM-tell phrases in docs prose (remove them; write plain imperative sentences):\n  " + "\n  ".join(hits)
    )
