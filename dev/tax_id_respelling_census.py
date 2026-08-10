"""AST census of hand-respelled tax-identifier normalisation.

Two canonical forms exist and each answers exactly one question:

* :func:`core.identity.same_tax_identifier` -- "do these two name the same
  bearer", comparing on separator-stripped ``normalise_nif_iva``;
* :func:`core.identity.tax_id_identity_token` -- the trim-and-uppercase form
  used to KEY a stored object.

A site that writes ``value.strip().upper()`` by hand is a respelling of one of
them, and which one depends on what the result is USED for, not on how it is
spelled. So this census classifies by USE:

``comparison``
    the normalised value reaches a comparison operand. Belongs to
    ``same_tax_identifier``.
``keying``
    the normalised value reaches a subscript, an f-string key, a dict literal
    key, or a call argument named like a key. Belongs to
    ``tax_id_identity_token``.
``unclassified``
    normalised, but its use is neither -- reported rather than dropped,
    because a census that silently discards what it cannot classify reports a
    smaller number than the truth and reads identically to a clean tree.

**Why an AST pass and not a grep.** The floor that preceded this counted only
respellings whose normalisation and comparison sat on ONE line. A site that
binds the normalised value to a local first --

    left = raw_left.strip().upper()
    if left == stored:

-- is the same defect and is invisible to that pattern. Twice a commit
claimed to have closed "the last" of this class on a same-line count, and
twice the residue was exactly the sites that spanned an assignment. This
walker follows local bindings within a function, so binding to a name no
longer hides the site.

**Two blind spots, both proven against this tree rather than hypothesised.**

It cannot see a normalisation that crosses a function boundary: normalise in
one function, compare in another, and neither half looks like a respelling
here.

And it cannot see one whose expression text carries no tax-identifier word,
because the tax-id filter reads that text. The live witness is
``adapters/outbound/aeat/sede/_adapter_utils.py:644`` --
``sorted(str(key).strip().upper() for key in expected)`` -- which normalises
NIFs through a variable named ``key``. It is a genuine member of this class
and this census does not report it.

So the number this prints is a FLOOR with two named leaks, never a
denominator. A closing report must say what was measured and by what
instrument; "the last" is the claim that has already been wrong twice here.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Final

from dev.cli_action_census import production_sources

NORMALISING_METHODS: Final = ("strip", "upper", "casefold", "lower")
TAX_ID_HINTS: Final = (
    "nif",
    "cif",
    "nie",
    "dni",
    "tax_id",
    "taxid",
    "identifier",
    "identity",
    "perceptor",
    "declarante",
    "contribuyente",
    "titular",
)
#: Bases whose text matches a hint but which do not carry a tax identifier.
#:
#: A bare ``counterparty`` hint was the first version and it matched
#: ``invoice.counterparty_country`` -- a two-letter ISO country code, which
#: has its own normal form and no business reaching a tax-identifier
#: predicate. The hint is dropped rather than exempted per site: it was
#: matching the OWNER of the field, not the field.
NON_TAX_ID_SUFFIXES: Final = ("_country", "_name", "_state", "_code")
KEY_ARGUMENT_HINTS: Final = ("key", "token", "bucket", "subject")


@dataclass(frozen=True)
class Finding:
    """One hand-respelled normalisation, classified by what its result feeds."""

    path: str
    line: int
    name: str
    kind: str
    snippet: str


def _looks_like_a_tax_id(name: str) -> bool:
    lowered = name.lower()
    if any(lowered.rstrip("\"')] ").endswith(suffix) for suffix in NON_TAX_ID_SUFFIXES):
        return False
    return any(hint in lowered for hint in TAX_ID_HINTS)


def _is_normalising_chain(node: ast.AST) -> bool:
    """Return whether *node* is a ``.strip().upper()``-style chain."""
    seen = 0
    cursor = node
    while isinstance(cursor, ast.Call) and isinstance(cursor.func, ast.Attribute):
        if cursor.func.attr not in NORMALISING_METHODS:
            return False
        seen += 1
        cursor = cursor.func.value
    return seen >= 2


def _base_text(node: ast.AST) -> str | None:
    """Return the source text of the expression the chain normalises.

    Unparsed rather than reduced to a root identifier. An earlier version of
    this walked down to a bare :class:`ast.Name` or :class:`ast.Attribute` and
    returned ``None`` for anything else, which silently discarded the two most
    common shapes in this tree -- ``row["nif"].strip().upper()`` (a subscript
    base) and ``read_nif().strip().upper()`` (a call base). It resolved a base
    for 7 of 182 chains and reported the other 175 as unmatched, so the census
    read as a nearly-clean tree because the instrument could not see.
    """
    cursor = node
    while isinstance(cursor, ast.Call) and isinstance(cursor.func, ast.Attribute):
        cursor = cursor.func.value
    try:
        return ast.unparse(cursor)
    except (AttributeError, ValueError):
        return None


class _FunctionScan(ast.NodeVisitor):
    """Collect respellings in one function, following local bindings."""

    def __init__(self, path: str, source_lines: list[str]) -> None:
        self.path = path
        self.lines = source_lines
        self.normalised: dict[str, int] = {}
        self.consumed: set[str] = set()
        self.findings: list[Finding] = []

    def _snippet(self, line: int) -> str:
        return self.lines[line - 1].strip() if 0 < line <= len(self.lines) else ""

    def visit_Assign(self, node: ast.Assign) -> None:
        if _is_normalising_chain(node.value):
            root = _base_text(node.value)
            if root and _looks_like_a_tax_id(root):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.normalised[target.id] = node.lineno
        self.generic_visit(node)

    def _record(self, name: str, line: int, kind: str) -> None:
        self.findings.append(Finding(self.path, line, name, kind, self._snippet(line)))

    def _operand_is_respelled(self, node: ast.AST) -> str | None:
        if _is_normalising_chain(node):
            root = _base_text(node)
            return root if root and _looks_like_a_tax_id(root) else None
        if isinstance(node, ast.Name) and node.id in self.normalised:
            self.consumed.add(node.id)
            return node.id
        return None

    def visit_Compare(self, node: ast.Compare) -> None:
        for operand in (node.left, *node.comparators):
            name = self._operand_is_respelled(operand)
            if name:
                self._record(name, node.lineno, "comparison")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        name = self._operand_is_respelled(node.slice)
        if name:
            self._record(name, node.lineno, "keying")
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                name = self._operand_is_respelled(value.value)
                if name:
                    self._record(name, node.lineno, "keying")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        for keyword in node.keywords:
            if keyword.arg and any(hint in keyword.arg.lower() for hint in KEY_ARGUMENT_HINTS):
                name = self._operand_is_respelled(keyword.value)
                if name:
                    self._record(name, node.lineno, "keying")
        self.generic_visit(node)


def _scan_module(path: pathlib.Path, source: str) -> list[Finding]:
    tree = ast.parse(source)
    lines = source.splitlines()
    rel = str(path).replace("\\", "/")
    findings: list[Finding] = []
    seen_lines: set[tuple[int, str]] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Module):
            continue
        scan = _FunctionScan(rel, lines)
        for child in ast.iter_child_nodes(node):
            scan.visit(child)
        for finding in scan.findings:
            marker = (finding.line, finding.kind)
            if marker not in seen_lines:
                seen_lines.add(marker)
                findings.append(finding)

        # A respelling bound but never classified is still a respelling. A
        # binding whose value DOES reach a comparison or a key is already
        # reported there, so counting it again here would inflate the
        # denominator with the very sites the census just explained.
        for name, line in scan.normalised.items():
            if name not in scan.consumed and (line, "unclassified") not in seen_lines:
                seen_lines.add((line, "unclassified"))
                findings.append(
                    Finding(rel, line, name, "unclassified", scan._snippet(line)),
                )

    # Every remaining tax-id-shaped chain, wherever it sits.
    #
    # The visitors above only reach a chain that is ASSIGNED to a local, or
    # that appears as a comparison operand, a subscript, an f-string slot or a
    # key-named argument. A chain passed straight into a call --
    # ``member_tax_id=str(row["nif"]).strip().upper()`` -- matches none of
    # those and was counted nowhere, so the census reported only the subset it
    # happened to have a visitor for. That is the same blindness the grep
    # floor had, in a different place, and it understated the population by
    # more than the visitors found. This sweep is the denominator: it counts
    # every chain, and the visitors above only refine HOW each is classified.
    for node in ast.walk(tree):
        if not _is_normalising_chain(node):
            continue
        base = _base_text(node)
        if not base or not _looks_like_a_tax_id(base):
            continue
        line = getattr(node, "lineno", 0)
        if any(f.line == line for f in findings):
            continue
        if (line, "free_standing") in seen_lines:
            continue
        seen_lines.add((line, "free_standing"))
        snippet = lines[line - 1].strip() if 0 < line <= len(lines) else ""
        findings.append(Finding(rel, line, base, "free_standing", snippet))
    return findings


def census(revision: str) -> list[Finding]:
    """Return every hand-respelled tax-id normalisation at *revision*."""
    findings: list[Finding] = []
    for path, source in production_sources(revision):
        try:
            findings += _scan_module(pathlib.Path(path), source)
        except SyntaxError:
            continue
    return sorted(findings, key=lambda f: (f.kind, f.path, f.line))


def main(argv: list[str] | None = None) -> int:
    """Print the respelling census for one pinned revision."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision", help="Pinned git revision to scan, e.g. HEAD")
    parser.add_argument("--kind", choices=("comparison", "keying", "unclassified", "free_standing"))
    args = parser.parse_args(argv)

    findings = census(args.revision)
    if args.kind:
        findings = [f for f in findings if f.kind == args.kind]
    for finding in findings:
        print(f"{finding.path}:{finding.line} [{finding.kind}] {finding.name} -- {finding.snippet}")

    tally: defaultdict[str, int] = defaultdict(int)
    for finding in findings:
        tally[finding.kind] += 1
    print()
    for kind in ("comparison", "keying", "unclassified", "free_standing"):
        print(f"{kind}: {tally[kind]}")
    print(f"total: {len(findings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
