"""Find closed string vocabularies declared at a registry schema model field.

A closed vocabulary belongs in one named enum the schema imports. This scan is the
authority for which fields still spell one out inline, and it is the measurement the
canonicalization gate asserts on.

Why it resolves rather than matches
-----------------------------------

Three earlier counting methods each measured a SPELLING and each was superseded
within a day. The first read the token written at the field. The second added alias
chains, which raised the count by forty-two. The third added annotations nested in
generics, which raised it again. Every one of those moves is available to a future
author as an evasion: a union survives a spelling-based gate by being renamed into an
alias, or pushed one level inward as a mapping key.

So the predicate here is structural. A field is in scope when its annotation, after
every alias is resolved and the whole subtree is walked, admits a closed set of two
or more strings. Where the union is written does not matter.

What it deliberately does not count
-----------------------------------

* **One-member unions.** These split semantically, not syntactically. A field
  asserting an assurance a reader relies on is a defect; a field restating its own
  model's identity or pinning scope is correct, and no property of the annotation
  separates them. The campaign misjudged this population twice before recording it as
  undecidable, so it is adjudicated per field and never counted toward a zero.
* **Non-string unions.** A pinned integer, boolean or version cannot become a member
  of a string enum.
* **Genuinely open text.** Legal prose, party names and text quoted from an official
  design are strings without a closed set, and no annotation marks them.

Its own blind spot
------------------

The scan reads annotations, so a vocabulary enforced somewhere other than a type --
a validator comparing against a tuple of literals, a membership test against a
module constant -- is invisible to it, exactly as an AST census cannot see a semantic
mirror. Finding those is a `vaultspec-rag` search by meaning, which is how this
campaign found an aliasing normaliser and two byte-identical enums that no name
search reached. The zero this scan can report is a zero for declared annotations, and
the module says so rather than letting a green result overstate itself.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT

SCHEMA_ROOT: Final[Path] = REPO_ROOT / "src" / "cadrumo" / "domain" / "calculations" / "registry"


@dataclass(frozen=True)
class VocabularyField:
    """One model field whose annotation admits a closed set of strings."""

    path: str
    lineno: int
    model: str
    field: str
    members: tuple[str, ...]
    reached_through_alias: bool
    nested_in_generic: bool

    @property
    def location(self) -> str:
        return f"{self.path}:{self.lineno}"


def _literal_subscript(node: ast.AST) -> ast.Subscript | None:
    if not isinstance(node, ast.Subscript):
        return None
    base = node.value
    name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
    return node if name == "Literal" else None


def _members(node: ast.Subscript) -> tuple[object, ...]:
    elts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
    return tuple(e.value for e in elts if isinstance(e, ast.Constant))


def _module_trees() -> Iterator[tuple[Path, ast.AST]]:
    for path in sorted(SCHEMA_ROOT.rglob("*.py")):
        if "tests" in path.parts or "__pycache__" in path.parts:
            continue
        try:
            yield path, ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue


def _alias_table(trees: list[tuple[Path, ast.AST]]) -> dict[str, ast.Subscript]:
    """Map every alias name in the package to the ``Literal`` it resolves to."""
    aliases: dict[str, ast.Subscript] = {}
    for _, tree in trees:
        for node in ast.walk(tree):
            target = value = None
            if isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
                target, value = node.name.id, node.value
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                target, value = node.targets[0].id, node.value
            if target is None or value is None:
                continue
            literal = _literal_subscript(value)
            if literal is not None:
                aliases[target] = literal
    return aliases


def _resolve(annotation: ast.AST, aliases: dict[str, ast.Subscript]) -> tuple[ast.Subscript, bool, bool] | None:
    """Return the closed union an annotation admits, however it is written."""
    direct = _literal_subscript(annotation)
    if direct is not None:
        return direct, False, False
    if isinstance(annotation, ast.Name) and annotation.id in aliases:
        return aliases[annotation.id], True, False
    for child in ast.walk(annotation):
        if child is annotation:
            continue
        nested = _literal_subscript(child)
        if nested is not None:
            return nested, False, True
        if isinstance(child, ast.Name) and child.id in aliases:
            return aliases[child.id], True, True
    return None


def scan() -> tuple[VocabularyField, ...]:
    """Return every model field whose annotation admits a closed string set."""
    trees = list(_module_trees())
    aliases = _alias_table(trees)
    found: list[VocabularyField] = []

    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for stmt in node.body:
                if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                    continue
                resolved = _resolve(stmt.annotation, aliases)
                if resolved is None:
                    continue
                literal, via_alias, nested = resolved
                members = _members(literal)
                if len(members) < 2 or not all(isinstance(m, str) for m in members):
                    continue
                found.append(
                    VocabularyField(
                        path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                        lineno=stmt.lineno,
                        model=node.name,
                        field=stmt.target.id,
                        members=tuple(str(m) for m in members),
                        reached_through_alias=via_alias,
                        nested_in_generic=nested,
                    ),
                )
    return tuple(found)


def main() -> int:
    """Print the inline closed vocabularies still declared at a schema field."""
    rows = scan()
    print(f"{len(rows)} model fields declare a closed string vocabulary inline\n")
    by_members: dict[tuple[str, ...], list[VocabularyField]] = {}
    for row in rows:
        by_members.setdefault(tuple(sorted(row.members)), []).append(row)

    print(f"{len(by_members)} distinct vocabularies; those at more than one field first:\n")
    for members, sites in sorted(by_members.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        marker = "" if len(sites) > 1 else " (single site)"
        print(f"  {len(sites)}x{marker}  [{', '.join(members)}]")
        for site in sites:
            how = " via alias" if site.reached_through_alias else ""
            how += " nested" if site.nested_in_generic else ""
            print(f"        {site.location}  {site.model}.{site.field}{how}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
