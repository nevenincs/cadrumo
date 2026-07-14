"""Static hygiene for executable-looking shell examples in documentation."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCS_ROOT = _REPO_ROOT / "docs"
_SHELL_FENCE_RE = re.compile(r"```(?:bash|sh|pwsh)\n(?P<body>.*?)\n```", re.DOTALL)
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

    version_re = re.compile(r"cadrumo-(\d+\.\d+\.\d+)-py3|cadrumo\[[\w,]+\]==(\d+\.\d+\.\d+)|release is `(\d+\.\d+\.\d+)`")
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
