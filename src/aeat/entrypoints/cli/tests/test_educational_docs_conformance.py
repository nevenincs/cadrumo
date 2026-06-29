"""Single-source conformance gate for the educational documentation surface.

Per the ``docs-educational-surface`` contract, the Diataxis educational docs
(``docs/tutorials``, ``docs/explanation``, ``docs/how-to``) and the
developer-facing architecture overview (``docs/architecture``) reference the live
CLI surface by stable verb and link to sibling docs; they never re-author flag
help. This gate makes that contract a tested invariant rather than an
author-discipline hope:

- every ``aeat ...`` invocation cited in an educational doc must resolve to a
  real command in the live CLI tree (the longest leading verb-prefix must accept
  ``--help``), so a doc that names a retired or renamed verb reds the gate; and
- every relative markdown link must resolve to a file that exists.

The gate binds to CLI *verbs* (not module paths), so it survives the module
relocation campaign that churns the autodoc tree.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from ....core.paths import PROJECT_ROOT
from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_EDU_DIRS = ("docs/tutorials", "docs/explanation", "docs/how-to", "docs/architecture")

# A leading run of lowercase verb-ish tokens after `aeat` (subcommands use
# lowercase words and hyphens). Args (NAME, paths) and flags (-x/--x) end the run.
# The lookbehind keeps `aeat` from matching the tail of a hyphenated doc page
# name (e.g. `file-at-aeat` in a toctree), which would otherwise greedily absorb
# the following lines as a bogus command.
_AEAT_RE = re.compile(r"(?<![\w-])aeat\s+((?:[a-z][a-z0-9-]*)(?:\s+[a-z][a-z0-9-]*)*)")
_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
# Commands are only authoritative inside code formatting (inline backticks or
# fenced blocks); a bare "aeat ..." in prose is not a cited invocation.
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


def _edu_docs() -> list[Path]:
    docs: list[Path] = []
    for d in _EDU_DIRS:
        docs.extend(sorted((PROJECT_ROOT / d).rglob("*.md")))
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
    assert docs, "no educational docs found under docs/{tutorials,explanation,how-to}/"


@pytest.mark.parametrize("doc", _edu_docs(), ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
def test_cited_aeat_verbs_resolve(doc: Path) -> None:
    """Every `aeat ...` command cited in the doc resolves to a live CLI verb."""
    text = doc.read_text(encoding="utf-8")
    unresolved: list[str] = []
    for tokens in sorted(_cited_commands(text)):
        if _longest_resolving_prefix(tokens) is None:
            unresolved.append("aeat " + " ".join(tokens))
    assert not unresolved, (
        f"{doc.relative_to(PROJECT_ROOT)} cites aeat commands whose leading verb "
        f"does not resolve in the live CLI: {unresolved}"
    )


@pytest.mark.parametrize("doc", _edu_docs(), ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
def test_relative_links_resolve(doc: Path) -> None:
    """Every relative markdown link in the doc resolves to an existing file."""
    text = doc.read_text(encoding="utf-8")
    broken: list[str] = []
    for m in _LINK_RE.finditer(text):
        target = m.group(1).strip()
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        path_part, _, anchor = target.partition("#")
        if not path_part:
            # pure-anchor link: a real in-page anchor (#section) is fine; an
            # empty target ("" or "#") is a dead placeholder myst rejects.
            if not anchor:
                broken.append(target or "(empty)")
            continue
        resolved = (doc.parent / path_part).resolve()
        # Must resolve to a FILE (a documented page), not a bare directory:
        # myst cannot cross-reference a directory link such as ``../cli/``.
        if not resolved.is_file():
            broken.append(target)
    assert not broken, f"{doc.relative_to(PROJECT_ROOT)} has unresolved relative links: {broken}"
