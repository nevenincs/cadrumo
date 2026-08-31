"""Census of hex-64 shape declarations made anywhere other than the canonical home.

WHY THIS EXISTS. ``core/hex.py`` states the mandate in the primitive's own
docstring -- every hex-64 concept is "declared as its OWN semantic alias
assigned FROM this one primitive, never by re-declaring the
``StringConstraints(...)`` call". A gate for it already existed
(``core/tests/test_hex64_identity.py``) and could not enforce it: its
``_ALIASES`` set is HAND-LISTED, it never walks the tree, and its own comment
asks authors to "add its alias here too". An enrolment gate over a hand-listed
set is blind to non-enrolment -- it passes under every mutation to a site that
never enrolled. So a mandate, a gate and a docstring all pointed the right way
while dozens of bypasses accumulated beside them.

This scanner is the missing half: it finds the sites the enrolment gate cannot
see, by walking the tree instead of reading a list.

TWO CLASSES, and they are not the same severity.

``REDECLARED_PATTERN`` -- the hex-64 regex written out again somewhere else.
The shape matches the canonical one today, so there is no behavioural gap; the
exposure is drift, because a future change to the canonical shape (a different
digest width, admitting uppercase) reaches every alias and none of these.

``UNPATTERNED_LENGTH`` -- a field constrained to exactly 64 characters with NO
pattern at all. This is a VALIDATION GAP, not drift: 64 ``Z``s or 64
exclamation marks satisfy it, so a malformed digest reaches a persisted record
and the mismatch surfaces only when something later recomputes the hash.

WHAT IT DOES NOT DO. It does not adjudicate promotability. A site is reported
because it declares the shape locally, not because it should necessarily be
retyped: a genuinely different concept may share the digits and diverge in its
constraint. Those are named in :data:`ALLOWLIST` with a reason each, and the
gate proves every entry still answers a live occurrence so a stale exemption
cannot outlive the code it excused.

Usage::

    python -m dev.identity.hex64_redeclaration_census HEAD
    python -m dev.identity.hex64_redeclaration_census HEAD --json
    python -m dev.identity.hex64_redeclaration_census HEAD --kind unpatterned_length
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Final

from ..quality.cli_action_census import production_sources

#: The canonical home. A declaration here is the definition, not a bypass.
CANONICAL_HOME: Final[str] = "src/cadrumo/core/hex.py"

#: The exact hex-64 character-class shapes this codebase writes, in every
#: ordering and casing seen. Ordering matters to nobody but a regex: a sweep
#: matching only ``[0-9a-f]`` silently misses ``[a-f0-9]``, which is how two
#: real sites stayed invisible to the first census of this concept.
_HEX_64_SHAPE: Final[re.Pattern[str]] = re.compile(
    r"\[(?:0-9a-f|a-f0-9|0-9a-fA-F|a-fA-F0-9|A-Fa-f0-9)\]\{64\}",
)

#: Constraint keywords that pin a value to exactly 64 characters.
_EXACT_64 = ("min_length", "max_length")

#: Calls whose keywords constrain a string field.
_CONSTRAINT_CALLS: Final[frozenset[str]] = frozenset({"Field", "StringConstraints"})


class DeclarationKind(StrEnum):
    """How a site declares the hex-64 shape outside the canonical home.

    Attributes:
        REDECLARED_PATTERN: The hex-64 regex written out again. Drift risk;
            the shape agrees with the canonical one today.
        UNPATTERNED_LENGTH: Exactly-64 length with no pattern, so any 64
            characters pass. A validation gap on whatever the field persists.
    """

    REDECLARED_PATTERN = "redeclared_pattern"
    UNPATTERNED_LENGTH = "unpatterned_length"


@dataclass(frozen=True, slots=True)
class Exemption:
    """One site excused from the gate, with the reason it is excused.

    Keyed by ``(path, symbol)`` rather than by line, because a line number is
    invalidated by every edit above it and an exemption that moves silently is
    an exemption nobody re-reads.

    Attributes:
        path: Repository-relative module path.
        symbol: Enclosing dotted symbol -- class, function, or the module-level
            constant's own name.
        reason: Why this site is NOT promotable. Required: an exemption whose
            reason is not stated is indistinguishable from an oversight.
    """

    path: str
    symbol: str
    reason: str

    def key(self) -> tuple[str, str]:
        """The identity this exemption matches occurrences on."""
        return (self.path, self.symbol)


#: Sites that declare the shape locally and MUST NOT be retyped to the
#: canonical primitive. Each survives the substitutability pre-filter check in
#: the opposite direction: the canonical type is NARROWER than what the site
#: legitimately accepts, so promoting it would refuse a value the site exists
#: to handle.
ALLOWLIST: Final[tuple[Exemption, ...]] = (
    Exemption(
        path="src/cadrumo/application/modelo/selectors.py",
        symbol="_WorkUnitLookupId",
        reason=(
            "A CLI lookup accepts an abbreviated 12-character prefix as well as the full "
            "64, and lowercases its input. Hex64Str admits only the full 64 and does not "
            "lowercase, so it is strictly NARROWER: promoting this would refuse every "
            "abbreviated lookup the surface exists to serve."
        ),
    ),
    Exemption(
        path="src/cadrumo/application/modelo/export.py",
        symbol="_Sha256Ref",
        reason=(
            "A 'sha256:'-prefixed reference, 71 characters including the prefix. A "
            "different shape carrying a different concept -- the algorithm label is part "
            "of the value -- so it is not the bare digest Hex64Str describes."
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class Declaration:
    """One hex-64 shape declaration made outside the canonical home.

    Attributes:
        path: Repository-relative module path at the pinned revision.
        line: Line the declaration appears on.
        symbol: Enclosing dotted symbol used for exemption matching.
        field: Field or constant name, where the site names one.
        kind: Which class of declaration this is.
        excerpt: The declaration rendered back to source, for the report.
    """

    path: str
    line: int
    symbol: str
    field: str
    kind: DeclarationKind
    excerpt: str

    def key(self) -> tuple[str, str]:
        """The identity an :class:`Exemption` matches on."""
        return (self.path, self.symbol)

    def rendered(self) -> str:
        """A single deterministic line for a report or a failure message."""
        return f"{self.path}:{self.line} {self.symbol}.{self.field} [{self.kind.value}] {self.excerpt}"


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    """The value of one keyword argument, or ``None`` when absent."""
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _is_exactly_64(call: ast.Call) -> bool:
    """Whether ``call`` pins a string to exactly 64 characters."""
    for bound in _EXACT_64:
        value = _keyword(call, bound)
        if not isinstance(value, ast.Constant) or value.value != 64:
            return False
    return True


def _declares_hex_pattern(call: ast.Call) -> bool:
    """Whether ``call`` carries a pattern naming the hex-64 shape.

    A pattern given as a NAME (``pattern=HEX_PATTERN_64``) counts as declared:
    the site is consuming a shared constant rather than writing the shape out,
    which is the behaviour this gate wants. Only a literal is a redeclaration.
    """
    pattern = _keyword(call, "pattern")
    if pattern is None:
        return False
    if isinstance(pattern, ast.Constant) and isinstance(pattern.value, str):
        return bool(_HEX_64_SHAPE.search(pattern.value))
    return True


def _call_name(call: ast.Call) -> str:
    """The bare callee name of ``call``, or the empty string."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


class _Hex64Visitor(ast.NodeVisitor):
    """Collect hex-64 shape declarations from one module's AST."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._stack: list[str] = []
        self._binding: list[str] = []
        self.declarations: list[Declaration] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_Constant(self, node: ast.Constant) -> None:
        # Class 1 catches the shape wherever it is written: a module constant, a
        # Field(pattern=...), a re.compile argument, or a value inside a typed
        # kwargs dict. Matching the STRING rather than the surrounding call is
        # what makes it carrier-independent -- four distinct carriers of this
        # drift ship in this tree today.
        if isinstance(node.value, str) and _HEX_64_SHAPE.search(node.value):
            self.declarations.append(
                Declaration(
                    path=self._path,
                    line=node.lineno,
                    # A pattern occurrence is found deep inside an expression and
                    # has no name of its own, so it borrows the binding it is
                    # being assigned to. Without this it reported an EMPTY
                    # symbol, and an exemption keyed by (path, symbol) could
                    # never match one -- an allowlist entry that excuses nothing
                    # while reading as a considered carve-out.
                    symbol=self._symbol() or self._bound_name(),
                    field=self._bound_name(),
                    kind=DeclarationKind.REDECLARED_PATTERN,
                    excerpt=node.value,
                )
            )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        name = node.target.id if isinstance(node.target, ast.Name) else ""
        if name:
            self._consider_constraint(node.value, name, node.lineno)
        self._visit_bound(node, name)

    def visit_Assign(self, node: ast.Assign) -> None:
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        for name in names:
            self._consider_constraint(node.value, name, node.lineno)
        self._visit_bound(node, names[0] if names else "")

    def visit_TypeAlias(self, node: ast.TypeAlias) -> None:
        # PEP 695 ``type X = Annotated[...]``. A distinct node from Assign, and
        # a real carrier in this tree -- the sha256-prefixed export ref is one.
        name = node.name.id if isinstance(node.name, ast.Name) else ""
        self._consider_constraint(node.value, name, node.lineno)
        self._visit_bound(node, name)

    def _visit_bound(self, node: ast.AST, name: str) -> None:
        """Visit ``node``'s children with ``name`` as the active binding."""
        self._binding.append(name)
        self.generic_visit(node)
        self._binding.pop()

    def _bound_name(self) -> str:
        """The innermost binding currently being assigned, or the empty string."""
        return self._binding[-1] if self._binding else ""

    def _consider_constraint(self, value: ast.expr | None, name: str, line: int) -> None:
        for call in self._constraint_calls(value):
            if not _is_exactly_64(call) or _declares_hex_pattern(call):
                continue
            self.declarations.append(
                Declaration(
                    path=self._path,
                    line=line,
                    symbol=self._symbol() or name,
                    field=name,
                    kind=DeclarationKind.UNPATTERNED_LENGTH,
                    excerpt=ast.unparse(call),
                )
            )

    def _constraint_calls(self, value: ast.expr | None) -> tuple[ast.Call, ...]:
        """Every constraint call reachable from a field's declared value.

        Walks the whole subtree rather than reading ``value`` directly, because
        the constraint is routinely nested inside ``Annotated[...]`` rather than
        assigned bare.
        """
        if value is None:
            return ()
        return tuple(
            node for node in ast.walk(value) if isinstance(node, ast.Call) and _call_name(node) in _CONSTRAINT_CALLS
        )

    def _symbol(self) -> str:
        return ".".join(self._stack)


def census_sources(sources: tuple[tuple[str, str], ...]) -> tuple[Declaration, ...]:
    """Every out-of-home hex-64 declaration across already-pinned sources.

    Split from :func:`census` so contract tests can drive an explicit source
    snapshot rather than a revision, keeping them independent of whatever
    happens to be committed when they run.
    """
    found: list[Declaration] = []
    for path, source in sources:
        if path.replace("\\", "/") == CANONICAL_HOME:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            # A module that does not parse at the pinned revision contributes
            # neither a declaration nor a silent skip: it cannot carry one, and
            # counting it either way would misstate the denominator.
            continue
        visitor = _Hex64Visitor(path.replace("\\", "/"))
        visitor.visit(tree)
        found.extend(visitor.declarations)
    return tuple(sorted(found, key=lambda item: (item.path, item.line, item.field)))


def census(revision: str) -> tuple[Declaration, ...]:
    """Return the out-of-home hex-64 declaration ledger from ``revision``.

    The revision is required rather than defaulted, for the reason the sibling
    censuses under ``dev/`` state: this repository is written to by many agents
    at once, so a census over a moving worktree cannot be reproduced, and a
    number nobody can re-derive is not a gate.
    """
    return census_sources(production_sources(revision))


def unexempted(declarations: tuple[Declaration, ...]) -> tuple[Declaration, ...]:
    """Declarations not answered by a named :data:`ALLOWLIST` entry."""
    excused = {entry.key() for entry in ALLOWLIST}
    return tuple(item for item in declarations if item.key() not in excused)


def stale_exemptions(declarations: tuple[Declaration, ...]) -> tuple[Exemption, ...]:
    """Allowlist entries that no longer answer any live occurrence.

    A stale exemption is worse than a missing one: it reads as a considered
    judgement about code that has since moved or been fixed, and it silently
    widens to whatever later occupies its key.
    """
    live = {item.key() for item in declarations}
    return tuple(entry for entry in ALLOWLIST if entry.key() not in live)


def _summarise(declarations: tuple[Declaration, ...]) -> dict[str, int]:
    """Counts a report or a failure message needs, computed once."""
    open_sites = unexempted(declarations)
    return {
        "declarations": len(declarations),
        "redeclared_pattern": sum(1 for i in declarations if i.kind is DeclarationKind.REDECLARED_PATTERN),
        "unpatterned_length": sum(1 for i in declarations if i.kind is DeclarationKind.UNPATTERNED_LENGTH),
        "exempted": len(declarations) - len(open_sites),
        "open": len(open_sites),
        "stale_exemptions": len(stale_exemptions(declarations)),
    }


def main(argv: list[str] | None = None) -> int:
    """Print the census for one pinned revision, as text or JSON."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("revision", help="Pinned git revision to scan, e.g. HEAD or a sha")
    parser.add_argument("--json", action="store_true", help="Emit records and summary as JSON")
    parser.add_argument(
        "--kind",
        choices=tuple(kind.value for kind in DeclarationKind),
        help="Restrict output to one declaration class",
    )
    args = parser.parse_args(argv)

    declarations = census(args.revision)
    summary = _summarise(declarations)
    shown = tuple(i for i in declarations if i.kind.value == args.kind) if args.kind else declarations

    if args.json:
        print(json.dumps({"summary": summary, "records": [asdict(i) for i in shown]}, indent=2, sort_keys=True))
        return 0

    for item in shown:
        print(item.rendered())
    print()
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
