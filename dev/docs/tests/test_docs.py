"""Static hygiene for executable-looking shell examples in documentation."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = Path(__file__).resolve().parents[3]
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
    "Note that",
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


def _marker_pattern(marker: str) -> re.Pattern[str]:
    """Compile a case-insensitive word-boundary pattern for one LLM-tell marker."""
    pattern = r"\b" + re.escape(marker)
    if marker[-1].isalnum():
        pattern += r"\b"
    return re.compile(pattern, re.IGNORECASE)


_LLM_MARKER_RES = tuple((marker, _marker_pattern(marker)) for marker in _LLM_MARKERS)


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
    re.compile(r"\bgit\s+clean\s+-[^\n]*f\b"),
)


def _markdown_docs() -> tuple[Path, ...]:
    """Return checked-in markdown documentation pages."""
    return tuple(sorted(path for path in _DOCS_ROOT.rglob("*.md") if "_build" not in path.parts))


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
