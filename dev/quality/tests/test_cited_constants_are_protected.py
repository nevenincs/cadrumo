"""Gate: a constant citing a binding provision is used, or adjudicated by name.

A constant carrying its legal provision in the comment above it is captured
research, not a value: the citation is the work, and the calculation-grounding
rule requires that provenance survive. A cited constant nothing reads is also
the more interesting finding, because a declared threshold no calculation
applies is an unenforced rule rather than an unused value.

Either way it must not sit in the backlog as an anonymous deletion candidate.
An adjudication in ``dev/audit/reachability_classification.toml`` naming it is
what separates "kept deliberately" from "not yet looked at", and a sweep once
recorded that only two such constants existed when the live tree had nine --
seven cited thresholds were standing unprotected on that stale count.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE_ROOT: Final[Path] = REPO_ROOT / "src" / "cadrumo"
_LEDGER: Final[Path] = REPO_ROOT / "dev" / "audit" / "reachability_classification.toml"

#: A binding provision as this domain spells one: an article, a law, a royal
#: decree, a BOE identifier, or one of the statute abbreviations in use.
_CITATION: Final[re.Pattern[str]] = re.compile(
    r"\b(art\.|Ley\s+\d|RD\s+\d|RDL\s+\d|BOE-A-|LIRPF|LIVA|LIS\b|RIRPF|RIVA|Real\s+Decreto)",
    re.IGNORECASE,
)


def _comment_block_above(lines: list[str], lineno: int) -> str:
    """Return the contiguous comment lines immediately above ``lineno``."""
    block: list[str] = []
    index = lineno - 2
    while index >= 0 and lines[index].lstrip().startswith("#"):
        block.append(lines[index])
        index -= 1
    return "\n".join(block)


def _cited_constants() -> dict[str, str]:
    """Return every module-level constant whose comment cites a provision."""
    found: dict[str, str] = {}
    for path in sorted(_PACKAGE_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        for node in tree.body:
            target = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
            elif isinstance(node, ast.AnnAssign):
                target = node.target
            if not isinstance(target, ast.Name) or not target.id.isupper():
                continue
            if _CITATION.search(_comment_block_above(lines, node.lineno)):
                found[target.id] = path.relative_to(REPO_ROOT).as_posix()
    return found


def _shipped_sources() -> list[str]:
    """Return the text of every shipped non-test module, read once.

    Reading the tree per NAME made the gate quadratic and pushed it past five
    minutes; the corpus is read once and every name counted against it.
    """
    texts: list[str] = []
    for path in _PACKAGE_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        try:
            texts.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return texts


def _production_uses(name: str, corpus: list[str]) -> int:
    """Count whole-word occurrences of ``name`` across ``corpus``."""
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
    return sum(len(pattern.findall(text)) for text in corpus)


def _adjudicated_names() -> set[str]:
    """Return every symbol named by a classification cluster."""
    data = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    names: set[str] = set()
    for cluster in data.get("symbol_cluster", ()):
        names.update(cluster.get("symbols", ()))
    return names


def test_the_scan_finds_cited_constants() -> None:
    """A scan finding none would make the assertion below vacuous."""
    assert len(_cited_constants()) > 20


def test_every_unused_cited_constant_is_adjudicated_by_name() -> None:
    """The direction the gate exists for: provenance standing unprotected."""
    adjudicated = _adjudicated_names()
    corpus = _shipped_sources()
    unprotected = sorted(
        f"{name} ({path})"
        for name, path in _cited_constants().items()
        if _production_uses(name, corpus) <= 1 and name not in adjudicated
    )
    assert not unprotected, (
        "these constants cite a binding provision and nothing reads them, so each is "
        "either an unenforced rule or captured research; name it in "
        "dev/audit/reachability_classification.toml rather than leaving it an "
        f"anonymous deletion candidate: {unprotected}"
    )


def test_the_citation_reader_accepts_a_real_provision() -> None:
    """Detector teeth: the comment shapes this domain actually uses."""
    for citation in (
        "#: Art. 81 LIRPF (Ley 35/2006, BOE-A-2006-20764) monthly accrual.",
        "#: rate fixed by RD 439/2007 (RIRPF) art. 14.2.a",
        "#: Binding provision: Art. 96.2.a) LIRPF (Ley 35/2006).",
    ):
        assert _CITATION.search(citation), citation


def test_the_citation_reader_ignores_ordinary_prose() -> None:
    """The guard: a looser reader would sweep unrelated constants into the ledger."""
    for prose in (
        "#: Default port of the resident service.",
        "#: The corpus subtree whose coverage the pipeline depends on.",
        "#: Every locale key this module references.",
    ):
        assert not _CITATION.search(prose), prose
