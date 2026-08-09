"""AST-backed candidate census for the CLI action-envelope campaign.

The census measures the source before an adjudication table declares what is
canonical.  It deliberately reports the initial, mechanical candidate
universe rather than presenting a small hand-curated list as the blast radius.
Each record has a semantic key made of the repository path, its enclosing
symbol, the data-flow role, the field alias, and the observed action identity.
Locations are retained as locators, not as identity: moving a statement within
the same symbol must not make an old disposition stale.

This first pass covers production Python under ``src/cadrumo``.  Later passes
extend its vocabulary and join its candidates to dispositions and the live
operator surface; those concerns are intentionally not hidden in this scanner.

Usage::

    python -m dev.cli_action_census HEAD
    python -m dev.cli_action_census HEAD --json
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import subprocess
import sys
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
SOURCE_ROOT: Final[str] = "src/cadrumo"
_UTF_8: Final[str] = "utf-8"

# This is the mechanically grounded starting vocabulary, not the claimed
# fixed point.  ``recovery_hint`` was discovered by the pre-plan semantic pass
# and therefore belongs in the seed rather than waiting to be rediscovered.
INITIAL_ACTION_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "default_suggestion",
        "fix_command",
        "next_action",
        "next_command",
        "recovery_hint",
        "remediation",
        "suggestion",
    },
)
COMMAND_PREFIX: Final[str] = "aeat "
COMMAND_LITERAL_ALIAS: Final[str] = "<command-literal>"
MODULE_SYMBOL: Final[str] = "<module>"


@dataclass(frozen=True, slots=True)
class CandidateRecord:
    """One mechanically observed action-guidance candidate.

    ``key`` is the stable identity consumed by later adjudication work.  The
    line and column locate the current source only; they do not participate in
    identity because a formatting-only move is not a new candidate.
    """

    path: str
    enclosing_symbol: str
    role: str
    alias: str
    action_identity: str
    line: int
    column: int

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        """Return the disposition-safe, source-location-independent key."""
        return (self.path, self.enclosing_symbol, self.role, self.alias, self.action_identity)


def production_sources(revision: str) -> tuple[tuple[str, str], ...]:
    """Read production Python from one pinned revision in one Git process.

    ``git archive`` is a single, revision-consistent object read.  Calling
    ``git show`` for every source file made a normal census operationally
    unbounded on this repository despite each individual lookup being cheap.
    """
    completed = subprocess.run(  # noqa: S603 - fixed executable and arguments
        ["git", "archive", "--format=tar", revision, SOURCE_ROOT],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    sources: list[tuple[str, str]] = []
    with tarfile.open(fileobj=io.BytesIO(completed.stdout), mode="r:") as archive:
        for member in archive:
            path = member.name
            if (
                not member.isfile()
                or not path.endswith(".py")
                or "/tests/" in path
                or Path(path).name.startswith("test_")
            ):
                continue
            source_file = archive.extractfile(member)
            if source_file is None:
                continue
            sources.append((path, source_file.read().decode(_UTF_8)))
    return tuple(sorted(sources))


def _identity(node: ast.expr | None, *, missing: str = "<declaration>") -> str:
    """Return a deterministic action identity without evaluating source code."""
    if node is None:
        return missing
    if isinstance(node, ast.Constant):
        if node.value is None:
            return "<none>"
        if isinstance(node.value, str):
            return node.value or "<empty>"
        return repr(node.value)
    return ast.unparse(node)


def _target_aliases(target: ast.expr) -> tuple[str, ...]:
    """Return initial action aliases written by an assignment target."""
    if isinstance(target, ast.Name) and target.id in INITIAL_ACTION_ALIASES:
        return (target.id,)
    if isinstance(target, ast.Attribute) and target.attr in INITIAL_ACTION_ALIASES:
        return (target.attr,)
    if isinstance(target, (ast.Tuple, ast.List)):
        return tuple(alias for child in target.elts for alias in _target_aliases(child))
    return ()


class _CandidateVisitor(ast.NodeVisitor):
    """Collect role-labelled candidates while carrying the enclosing symbol."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._symbols: list[str] = []
        self.records: list[CandidateRecord] = []

    @property
    def _symbol(self) -> str:
        return ".".join(self._symbols) if self._symbols else MODULE_SYMBOL

    def _add(self, node: ast.AST, *, role: str, alias: str, action_identity: str) -> None:
        self.records.append(
            CandidateRecord(
                path=self._path,
                enclosing_symbol=self._symbol,
                role=role,
                alias=alias,
                action_identity=action_identity,
                line=node.lineno,
                column=node.col_offset,
            ),
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._symbols.append(node.name)
        self.generic_visit(node)
        self._symbols.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._symbols.append(node.name)
        self.generic_visit(node)
        self._symbols.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        for alias in _target_aliases(node.target):
            self._add(node, role="definition", alias=alias, action_identity=_identity(node.value))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            for alias in _target_aliases(target):
                self._add(node, role="assignment", alias=alias, action_identity=_identity(node.value))
        self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        for alias in _target_aliases(node.target):
            self._add(node, role="assignment", alias=alias, action_identity=_identity(node.value))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        for keyword in node.keywords:
            if keyword.arg in INITIAL_ACTION_ALIASES:
                self._add(node, role="producer", alias=keyword.arg, action_identity=_identity(keyword.value))
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values, strict=True):
            if isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value in INITIAL_ACTION_ALIASES:
                self._add(key, role="producer", alias=key.value, action_identity=_identity(value))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load) and node.attr in INITIAL_ACTION_ALIASES:
            self._add(node, role="transformer", alias=node.attr, action_identity=ast.unparse(node))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and node.value.startswith(COMMAND_PREFIX):
            self._add(
                node,
                role="command_literal",
                alias=COMMAND_LITERAL_ALIAS,
                action_identity=node.value,
            )


def census(revision: str) -> tuple[CandidateRecord, ...]:
    """Return unique, deterministically ordered candidates from ``revision``.

    The revision is deliberately required.  Scanning a moving worktree while
    peers are committing can combine source from different trees and fabricate
    a blast-radius number that has never existed at one revision.
    """
    records: dict[tuple[str, str, str, str, str], CandidateRecord] = {}
    for path, source in production_sources(revision):
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError:
            # A revision that contains syntactically invalid Python cannot
            # supply AST evidence for that module; later closure work treats
            # this as a separately adjudicated source-health finding.
            continue
        visitor = _CandidateVisitor(path)
        visitor.visit(tree)
        for record in visitor.records:
            previous = records.get(record.key)
            if previous is None or (record.line, record.column) < (previous.line, previous.column):
                records[record.key] = record
    return tuple(sorted(records.values(), key=lambda record: (*record.key, record.line, record.column)))


def main(argv: list[str] | None = None) -> int:
    """Print the initial candidate ledger for one pinned revision."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("revision", help="Git revision to census; use an immutable commit when citing output")
    parser.add_argument("--json", action="store_true", help="emit candidate records as JSON")
    arguments = parser.parse_args(argv)
    records = census(arguments.revision)
    if arguments.json:
        print(
            json.dumps(
                {
                    "revision": arguments.revision,
                    "candidate_count": len(records),
                    "candidates": [asdict(record) | {"key": record.key} for record in records],
                },
                indent=2,
            ),
        )
        return 0
    print(f"revision {arguments.revision}")
    print(f"action-guidance candidates {len(records)}")
    for record in records:
        print(
            f"{record.path}:{record.line}:{record.column}  {record.role}  "
            f"{record.enclosing_symbol}  {record.alias}={record.action_identity!r}",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
