"""Derive every parser of official regulatory prose and force one enrolment each.

AEAT publishes its record designs, instructions and legal text as PROSE. Turning
that prose into wire facts needs a grammar, and a grammar over regulatory text is
sanctioned rather than suspect: ``no-legacy-compatibility`` keeps resilience for
"AEAT portal variations, BOE corpus formats, PDF producer quirks" precisely
because that variability is the outside world's, not ours.

The objection this module answers is not that the grammars exist. It is that
they were UNDECLARED: a reader could not tell which modules are entitled to read
official prose, so a new one could appear anywhere and look like every other
regex. An undeclared parser of regulatory text is indistinguishable from a
regulatory embed hiding in a pattern.

So the channel is declared here. Each parser is enrolled with the corpus it
reads and why it must read it, the SET is derived mechanically, and an
unenrolled parser refuses. Enrolment is not approval of a value: a grammar may
read prose, but a regulatory VALUE it derives still lands in the registry
authoring tree under ``aeat-calculation-grounding``.

Derivation flags any module compiling a regular expression whose pattern carries
AEAT design or legal vocabulary. The detector is deliberately broad: a false
positive costs one enrolment row saying "matches on the word X, reads no prose",
which is cheap and visible, whereas a narrow detector silently misses the module
this gate exists to surface.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.toml import read_toml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCANNED_ROOTS = ("src/cadrumo", "dev")
LEDGER_PATH = Path(__file__).with_name("regulatory_prose_parser_channel.toml")

#: Vocabulary that marks a pattern as reading AEAT design or legal prose.
PROSE_VOCABULARY: tuple[str, ...] = (
    "enteros",
    "decimales",
    "posic",
    "naturaleza",
    "nota",
    "alfanum",
    "numerico",
    "numérico",
    "casilla",
    "ejercicio",
    "declarante",
)


class ProseChannelLedgerError(RuntimeError):
    """The derived parser set and the enrolment ledger disagree."""


@dataclass(frozen=True, slots=True, order=True)
class ProseParserModule:
    """One module compiling at least one regulatory-prose pattern."""

    module: str
    pattern_count: int


@dataclass(frozen=True, slots=True)
class ProseParserEnrolment:
    """One authored enrolment row."""

    module: str
    corpus: str
    reason: str


def _iter_scanned_modules() -> Iterator[Path]:
    for root in SCANNED_ROOTS:
        for path in sorted((REPO_ROOT / root).rglob("*.py")):
            parts = path.parts
            if "tests" in parts or "__pycache__" in parts:
                continue
            if ".baseline-source-snapshot" in path.as_posix():
                continue
            yield path


def _prose_pattern_count(tree: ast.Module) -> int:
    """Return how many compiled patterns in ``tree`` carry prose vocabulary."""
    count = 0
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "compile"):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                lowered = child.value.casefold()
                if any(token in lowered for token in PROSE_VOCABULARY):
                    count += 1
                    break
    return count


def derive_prose_parsers() -> tuple[ProseParserModule, ...]:
    """Derive every module that compiles a regulatory-prose pattern."""
    found: list[ProseParserModule] = []
    for path in _iter_scanned_modules():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        count = _prose_pattern_count(tree)
        if count:
            found.append(
                ProseParserModule(module=path.relative_to(REPO_ROOT).as_posix(), pattern_count=count),
            )
    return tuple(sorted(found))


def load_ledger(path: Path | None = None) -> dict[str, ProseParserEnrolment]:
    """Load the authored enrolment ledger.

    Raises:
        ProseChannelLedgerError: When a row omits its module, corpus or reason.
    """
    target = path if path is not None else LEDGER_PATH
    if not target.exists():
        return {}
    raw = read_toml(target, error_factory=ProseChannelLedgerError)
    rows: dict[str, ProseParserEnrolment] = {}
    for entry in raw.get("parser", []):
        module = entry.get("module")
        corpus = entry.get("corpus", "")
        reason = entry.get("reason", "")
        if not module:
            message = f"{target}: every parser row needs a module"
            raise ProseChannelLedgerError(message)
        if not corpus.strip() or not reason.strip():
            message = f"{target}: {module!r} must name the corpus it reads and why it must read it"
            raise ProseChannelLedgerError(message)
        rows[module] = ProseParserEnrolment(module=module, corpus=corpus, reason=reason)
    return rows


def reconcile(
    parsers: tuple[ProseParserModule, ...] | None = None,
    ledger: dict[str, ProseParserEnrolment] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(unenrolled, stale)`` against the enrolment ledger."""
    derived = parsers if parsers is not None else derive_prose_parsers()
    rows = ledger if ledger is not None else load_ledger()
    modules = {parser.module for parser in derived}
    return tuple(sorted(modules - set(rows))), tuple(sorted(set(rows) - modules))


__all__ = [
    "LEDGER_PATH",
    "PROSE_VOCABULARY",
    "ProseChannelLedgerError",
    "ProseParserEnrolment",
    "ProseParserModule",
    "derive_prose_parsers",
    "load_ledger",
    "reconcile",
]
