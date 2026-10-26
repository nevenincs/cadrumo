"""Static hygiene for executable-looking shell examples in documentation."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT
_DOCS_ROOT = _REPO_ROOT / "docs"
_SHELL_FENCE_RE = re.compile(r"```(?:bash|sh|pwsh)\n(?P<body>.*?)\n```", re.DOTALL)

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


#: Floors for the documentation corpus checks. Live: 59 pages across
#: six areas (how-to 35, root 8, explanation 7, reference 7, api 1,
#: architecture 1). Both are needed: the total is dominated by how-to, so a
#: page floor alone would sit clear while a smaller subtree left the scan,
#: and an area floor alone would sit clear while how-to emptied.
_MINIMUM_MARKDOWN_PAGES = 40
_MINIMUM_MARKDOWN_AREAS = 5


def _markdown_docs() -> tuple[Path, ...]:
    """Return checked-in markdown documentation pages.

    Refuses an empty result rather than returning one. The retained gates scan
    this corpus for violations and assert the offender list is empty; over an empty
    corpus each reports exactly what a clean corpus reports, so the proof of
    scan belongs here, once, rather than at each call site.
    """
    pages = tuple(
        path for path in scan_directory(_DOCS_ROOT, pattern="*.md", recursive=True) if "_build" not in path.parts
    )
    assert pages, f"no markdown documentation pages found under {_DOCS_ROOT}"
    areas = {path.relative_to(_DOCS_ROOT).parts[0] for path in pages if len(path.relative_to(_DOCS_ROOT).parts) > 1}
    assert len(pages) >= _MINIMUM_MARKDOWN_PAGES, (
        f"only {len(pages)} markdown page(s) under {_DOCS_ROOT}; the gates that scan this "
        "corpus report an empty offender list over a narrowed one exactly as they do "
        "over a clean one"
    )
    assert len(areas) >= _MINIMUM_MARKDOWN_AREAS, (
        f"the corpus spans only {len(areas)} documentation area(s) ({sorted(areas)}); "
        "one subtree dropping out of the scan leaves the page total high enough to pass "
        "while nothing in it is read"
    )
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


def test_the_scanned_markdown_corpus_is_not_empty() -> None:
    """Every scan in this module is vacuous over an empty page list."""
    docs = _markdown_docs()
    assert len(docs) > 20, f"expected the docs corpus, scanned only {len(docs)} markdown page(s)"


#: The three shapes a docs page uses to cite a release version: the wheel
#: filename, a pinned extras spec, and the prose "release is `X.Y.Z`" line.
#: The extras alternative is deliberately generic (``[\w,]+``) rather than an
#: enumeration of the declared extras -- it exists to catch a stale VERSION in
#: any pinned spec, and an undeclared extra name is a different gate's question.
_CITED_VERSION_RE = re.compile(
    r"cadrumo-(\d+\.\d+\.\d+)-py3|cadrumo\[[\w,]+\]==(\d+\.\d+\.\d+)|release is `(\d+\.\d+\.\d+)`"
)


def _stale_version_citations(source: str, relative: str, version: str) -> list[str]:
    """Return one entry per version citation in ``source`` that is not ``version``."""
    stale: list[str] = []
    for match in _CITED_VERSION_RE.finditer(source):
        cited = next(group for group in match.groups() if group)
        if cited != version:
            lineno = source[: match.start()].count("\n") + 1
            stale.append(f"{relative}:{lineno}: cites {cited}, package is {version}")
    return stale


def test_documentation_install_snippets_cite_the_current_version() -> None:
    """No docs page cites a release version other than the shipped one.

    A hardcoded version rots silently on every release — the 0.2.0→0.2.1 bump
    left five stale install commands behind — so every cited version is pinned
    to ``cadrumo.__version__``.

    This is a standing guard, not a survey of live citations: the docs corpus
    carries NO pinned version today (the install pages moved to unpinned
    ``uvx cadrumo`` / wheel-less spellings), so the scan legitimately matches
    nothing and this gate would report a clean corpus and an empty one exactly
    alike. Its teeth therefore live in
    :func:`test_the_version_citation_scan_catches_a_stale_citation`, which runs
    the same scan over explicit input rather than over the corpus.
    """
    from cadrumo.core.package_version import PACKAGE_VERSION

    violations: list[str] = []
    for path in _markdown_docs():
        relative = path.relative_to(_REPO_ROOT).as_posix()
        violations.extend(_stale_version_citations(path.read_text(encoding="utf-8"), relative, PACKAGE_VERSION))

    assert not violations, "stale install versions in docs:\n" + "\n".join(violations)


def test_the_version_citation_scan_catches_a_stale_citation() -> None:
    """Detector teeth for the scan above, over explicit input.

    Each of the three citation shapes is presented once at a stale version and
    once at the current one. A stale citation must be reported and a current
    one must not, so a regex that stopped matching -- the way the corpus itself
    can no longer tell us -- fails here immediately.
    """
    from cadrumo.core.package_version import PACKAGE_VERSION

    stale_version = "0.0.1"
    assert stale_version != PACKAGE_VERSION, "pick a stale version the package does not carry"

    shapes = (
        "download `cadrumo-{v}-py3-none-any.whl`",
        "run `uvx cadrumo[llm]=={v}`",
        "the current release is `{v}`",
    )
    for shape in shapes:
        stale = _stale_version_citations(shape.format(v=stale_version), "probe.md", PACKAGE_VERSION)
        assert len(stale) == 1, f"the scan missed a stale citation in {shape.format(v=stale_version)!r}"
        assert stale_version in stale[0]

        current = _stale_version_citations(shape.format(v=PACKAGE_VERSION), "probe.md", PACKAGE_VERSION)
        assert not current, f"the scan flagged a current citation in {shape.format(v=PACKAGE_VERSION)!r}: {current}"
