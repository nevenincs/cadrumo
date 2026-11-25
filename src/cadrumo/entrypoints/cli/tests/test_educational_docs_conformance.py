"""Single-source conformance gate for the educational documentation surface.

Per the ``docs-educational-surface`` contract, the Diataxis educational docs
(``docs/explanation``, ``docs/how-to``) and the
developer-facing architecture overview (``docs/architecture``) reference the live
CLI surface by stable verb; they never re-author flag help. This gate makes that
contract a tested invariant rather than an author-discipline hope: every
``aeat ...`` invocation cited in an educational doc must resolve to a real
command in the live CLI tree (the longest leading verb-prefix must accept
``--help``), so a doc that names a retired or renamed verb reds the gate.

The gate binds to CLI *verbs* (not module paths), so it survives module
relocations that churn the autodoc tree.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory
from ....tests.inventory import REPO_ROOT
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_EDU_DIRS = ("docs/explanation", "docs/how-to", "docs/architecture")

# A leading run of lowercase verb-ish tokens after `aeat` (subcommands use
# lowercase words and hyphens). Args (NAME, paths) and flags (-x/--x) end the run.
# Horizontal whitespace is deliberate: a directory command such as ``cd aeat``
# must not absorb the following line (for example ``uv sync``) as a CLI citation.
_AEAT_RE = re.compile(r"(?<![\w-])aeat[ \t]+((?:[a-z][a-z0-9-]*)(?:[ \t]+[a-z][a-z0-9-]*)*)")
# Commands are only authoritative inside code formatting (inline backticks or
# fenced blocks); a bare "aeat ..." in prose is not a cited invocation.
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


def _edu_docs() -> list[Path]:
    docs: list[Path] = []
    for d in _EDU_DIRS:
        docs.extend(scan_directory(REPO_ROOT / d, pattern="*.md", recursive=True))
    return docs


@cache
def _verb_resolves(path_tuple: tuple[str, ...]) -> bool:
    """True if `aeat <path...> --help` resolves to a real command."""
    result = invoke_cached_cli((*path_tuple, "--help"))
    return result.exit_code == 0


def _longest_resolving_prefix(tokens: tuple[str, ...]) -> tuple[str, ...] | None:
    for n in range(len(tokens), 0, -1):
        if _verb_resolves(tokens[:n]):
            return tokens[:n]
    return None


def _cited_commands(text: str) -> set[tuple[str, ...]]:
    spans = [m.group(1) for m in _INLINE_CODE_RE.finditer(text)]
    spans += [m.group(1) for m in _FENCE_RE.finditer(text)]
    cmds: set[tuple[str, ...]] = set()
    for span in spans:
        for m in _AEAT_RE.finditer(span):
            tokens = tuple(m.group(1).split())
            if tokens:
                cmds.add(tokens)
    return cmds


def test_educational_docs_exist() -> None:
    """The educational surface is present."""
    docs = _edu_docs()
    assert docs, "no educational docs found under docs/{explanation,how-to}/"


def test_cited_aeat_verbs_resolve() -> None:
    """Every `aeat ...` command cited in the doc resolves to a live CLI verb."""
    unresolved: list[str] = []
    for doc in _edu_docs():
        text = doc.read_text(encoding="utf-8")
        for tokens in sorted(_cited_commands(text)):
            if _longest_resolving_prefix(tokens) is None:
                unresolved.append(f"{doc.relative_to(REPO_ROOT)}: aeat {' '.join(tokens)}")
    assert not unresolved, "educational docs cite aeat commands whose leading verb does not resolve:\n" + "\n".join(
        unresolved,
    )


def test_command_scanner_does_not_cross_line_boundaries() -> None:
    """A directory name on one line cannot absorb commands from the next."""
    text = "```console\ncd aeat\nuv sync\n```"
    assert _cited_commands(text) == set()
