#!/usr/bin/env python
"""Locate SEMANTIC duplication: one concept implemented twice in different syntax.

The sibling :mod:`dev.audit.duplication` runner owns COPY-PASTE measurement through
jscpd, and its own docstring records why that is not enough here: jscpd matches token
sequences, so "a concept implemented twice in different syntax is invisible to it, and
that is exactly the duplication this project's rules treat as a blocker". Five ledger
projections once shared one casilla fold differing only in an accumulator loop versus a
comprehension, and jscpd reported none of them.

Embedding search does not close that gap either. It matches VOCABULARY, so two
implementations written by different authors -- different nouns, different helper
names, different comments -- score as unrelated however identical their behaviour.

So this runner does not look at surface at all. It fingerprints each module by the
MEANINGS it references, taking those meanings from places the code cannot paraphrase
away: closed enum members, scarce regulated literals, the callees a function invokes,
the field set a record declares, the first-party modules an implementation depends on.
Two modules with the same rare fingerprint are implementing the same rule, whatever
they call it.

**Every detector here is a CANDIDATE generator, never a verdict.** A shared fingerprint
is evidence that two sites mean the same thing; it is not proof, and the project's
substitutability rule applies before any of them may be collapsed: the proposed
canonical site's constraint shape must be a SUPERSET of the other's. Two sites that
partition the same enum for genuinely different rules are a legitimate finding to leave
standing, and a lower duplicate count bought by merging them is a regression.

Detection is deterministic AST work with no model in the path, so the output is
reproducible and the runner can later back a gate.

Usage::

    uv run --no-sync python -m dev.audit.semantic_duplication            # human report
    uv run --no-sync python -m dev.audit.semantic_duplication --json     # machine output
    uv run --no-sync python -m dev.audit.semantic_duplication --detector enum_subset
"""

from __future__ import annotations

import argparse
import ast
import collections
import json
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Scope is the shipped product tree, matching the sibling duplication runner: the
#: duplication that matters is duplicate AUTHORITY in shipped code. ``dev/`` is
#: scannable on demand by passing a different root, not by widening the default.
_PRODUCT_SOURCE_ROOT = _REPO_ROOT / "src" / "cadrumo"

#: Literals too common to carry meaning. Excluded by VALUE rather than by frequency
#: so the exclusion is auditable: a frequency cut-off would silently drop a genuinely
#: scarce regulated figure the moment a sixth site adopted it.
_TRIVIAL_LITERALS: frozenset[object] = frozenset({0, 1, 2, -1, "", " ", ".", ",", "/", "-", "_", "\n"})

#: A literal is scarce when it appears at no more than this many distinct modules.
#: Above it the value is vocabulary, not a rule.
_SCARCE_LITERAL_CEILING = 6

#: Fingerprints below this size match on coincidence rather than on behaviour.
_MIN_CALL_FINGERPRINT = 5
_MIN_FIELD_SET = 4
_MIN_IMPORT_SET = 5

#: Rare-import overlap at or above this Jaccard is a candidate.
_IMPORT_JACCARD_FLOOR = 0.65


@dataclass(frozen=True)
class Candidate:
    """One duplication candidate: a shared fingerprint and the sites carrying it."""

    detector: str
    fingerprint: str
    sites: tuple[str, ...]
    weight: int = 0

    def as_dict(self) -> dict[str, object]:
        """Return the candidate as a JSON-ready mapping."""
        return {
            "detector": self.detector,
            "fingerprint": self.fingerprint,
            "sites": list(self.sites),
            "site_count": len(self.sites),
            "weight": self.weight,
        }


@dataclass
class Module:
    """One parsed production module and the meanings it references."""

    path: Path
    relative: str
    tree: ast.AST
    enum_members: dict[str, set[str]] = field(default_factory=dict)
    literals: set[object] = field(default_factory=set)
    first_party_imports: set[str] = field(default_factory=set)


def _iter_source_files(root: Path) -> Iterator[Path]:
    """Yield every production module, excluding test packages."""
    for path in sorted(root.rglob("*.py")):
        if "tests" in path.parts or path.name == "conftest.py":
            continue
        yield path


def _closed_enum_names(modules: Sequence[Module]) -> frozenset[str]:
    """Return every closed value-set class declared anywhere in the tree.

    Discovered rather than listed. A hand-kept list of enums is itself the kind of
    restated inventory this runner exists to find, and it would go stale the first
    time a new closed axis landed.
    """
    names: set[str] = set()
    for module in modules:
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                base_name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
                if base_name in {"StrEnum", "IntEnum", "Enum"}:
                    names.add(node.name)
    return frozenset(names)


def _load_modules(root: Path) -> list[Module]:
    """Parse every production module once; every detector reads these.

    A module that does not parse is REFUSED rather than dropped. This list is
    the corpus for every detector in this file, so a silently skipped module
    hides its duplicates from all of them at once - and nothing downstream
    reports a corpus size, so a short corpus and a clean one look identical.

    Measured against the shipped tree: 2103 source files, none unparsable, so
    refusing costs nothing today and says so immediately if that changes.
    """
    modules: list[Module] = []
    for path in _iter_source_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as error:
            raise SystemExit(
                f"{path} could not be parsed, so the duplication corpus would be short "
                f"by exactly the module nobody can analyse: {error}"
            ) from error
        modules.append(Module(path=path, relative=path.relative_to(root).as_posix(), tree=tree))
    if not modules:
        raise SystemExit(f"no production modules found under {root}; every detector would report clean")
    return modules


def _populate(modules: Sequence[Module], enum_names: frozenset[str]) -> None:
    """Fill each module's referenced-meaning sets in a single AST pass."""
    for module in modules:
        for node in ast.walk(module.tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in enum_names
                and node.attr.isupper()
            ):
                module.enum_members.setdefault(node.value.id, set()).add(node.attr)
            elif isinstance(node, ast.Constant) and isinstance(node.value, int | float | str):
                if node.value not in _TRIVIAL_LITERALS and not isinstance(node.value, bool):
                    module.literals.add(node.value)
            elif isinstance(node, ast.ImportFrom) and node.module:
                module.first_party_imports.add(f"{'.' * (node.level or 0)}{node.module}")


def detect_enum_subset(modules: Sequence[Module]) -> list[Candidate]:
    """Modules naming the SAME multi-member subset of one closed enum.

    The subset a module references is a fingerprint of the partition it implements.
    Two modules naming an identical unusual subset are drawing the same line through
    the same closed axis, which is a rule stated twice.

    Whole-enum references are excluded: a module that names every member is usually
    exhaustively dispatching, not partitioning.
    """
    by_subset: dict[tuple[str, tuple[str, ...]], list[str]] = collections.defaultdict(list)
    enum_sizes: dict[str, int] = collections.defaultdict(int)
    for module in modules:
        for enum_name, members in module.enum_members.items():
            enum_sizes[enum_name] = max(enum_sizes[enum_name], len(members))
    for module in modules:
        for enum_name, members in module.enum_members.items():
            if len(members) < 2 or len(members) == enum_sizes[enum_name]:
                continue
            by_subset[(enum_name, tuple(sorted(members)))].append(module.relative)
    return [
        Candidate(
            detector="enum_subset",
            fingerprint=f"{enum_name}{{{', '.join(subset)}}}",
            sites=tuple(sorted(sites)),
            weight=len(subset) * len(sites),
        )
        for (enum_name, subset), sites in by_subset.items()
        if len(sites) > 1
    ]


def detect_scarce_literal(modules: Sequence[Module]) -> list[Candidate]:
    """Modules sharing two or more SCARCE literals.

    In a regulated domain a rule is a number. Two modules that both mention the same
    scarce rate, threshold or code are very often two implementations of the provision
    that fixes it -- and unlike a name, a regulated figure cannot be paraphrased.

    Two shared literals rather than one: a single shared figure is frequently a genuine
    cross-reference, while a pair is a shared rule.
    """
    sites_by_literal: dict[object, set[str]] = collections.defaultdict(set)
    for module in modules:
        for literal in module.literals:
            sites_by_literal[literal].add(module.relative)
    scarce = {
        literal: sites for literal, sites in sites_by_literal.items() if 1 < len(sites) <= _SCARCE_LITERAL_CEILING
    }
    shared: dict[tuple[str, str], set[object]] = collections.defaultdict(set)
    for literal, sites in scarce.items():
        for left in sorted(sites):
            for right in sorted(sites):
                if left < right:
                    shared[(left, right)].add(literal)
    return [
        Candidate(
            detector="scarce_literal",
            fingerprint=" + ".join(repr(literal) for literal in sorted(literals, key=repr)[:6]),
            sites=(left, right),
            weight=len(literals),
        )
        for (left, right), literals in shared.items()
        if len(literals) >= 2
    ]


def _call_fingerprint(node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    """Return what a function DOES: the callees it invokes and the literals it uses.

    Deliberately blind to the function's own name, its parameter names, its local
    variable names and its comments -- every axis a second author would spell
    differently while implementing the same rule.
    """
    marks: set[str] = set()
    for inner in ast.walk(node):
        if isinstance(inner, ast.Call):
            func = inner.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name:
                marks.add(f"call:{name}/{len(inner.args)}")
        elif isinstance(inner, ast.Constant) and isinstance(inner.value, int | float | str):
            if inner.value not in _TRIVIAL_LITERALS and not isinstance(inner.value, bool):
                marks.add(f"lit:{inner.value!r}")
        elif isinstance(inner, ast.Compare):
            marks.update(f"cmp:{type(op).__name__}" for op in inner.ops)
    return frozenset(marks)


def detect_call_fingerprint(modules: Sequence[Module]) -> list[Candidate]:
    """Functions in different modules whose behaviour fingerprint is identical.

    This is the detector aimed squarely at the case the jscpd runner records missing:
    an accumulator loop and a comprehension over the same fold produce the same callees
    and the same literals, and differ in every token.
    """
    by_fingerprint: dict[frozenset[str], list[str]] = collections.defaultdict(list)
    for module in modules:
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            fingerprint = _call_fingerprint(node)
            if len(fingerprint) < _MIN_CALL_FINGERPRINT:
                continue
            by_fingerprint[fingerprint].append(f"{module.relative}:{node.lineno} {node.name}")
    return [
        Candidate(
            detector="call_fingerprint",
            fingerprint=" ".join(sorted(fingerprint)[:8]),
            sites=tuple(sorted(sites)),
            weight=len(fingerprint) * len(sites),
        )
        for fingerprint, sites in by_fingerprint.items()
        if len({site.split(":")[0] for site in sites}) > 1
    ]


def _normalised_expression(node: ast.AST) -> str | None:
    """Return a naming-blind fingerprint of one expression, or ``None`` if trivial.

    Identifiers are erased and only STRUCTURE plus the closed-value members and
    literals survive, so two authors who spell the same derivation with different
    variable names produce the same fingerprint. A ternary choosing between two
    enum members on a comparison is the shape this exists to catch.
    """
    marks: list[str] = []
    for inner in ast.walk(node):
        if isinstance(inner, ast.Attribute) and inner.attr.isupper():
            marks.append(f"member:{inner.attr}")
        elif isinstance(inner, ast.Constant) and isinstance(inner.value, int | float | str):
            if inner.value not in _TRIVIAL_LITERALS and not isinstance(inner.value, bool):
                marks.append(f"lit:{inner.value!r}")
        elif isinstance(inner, ast.Compare):
            marks.extend(f"cmp:{type(op).__name__}" for op in inner.ops)
        elif isinstance(inner, ast.IfExp):
            marks.append("ternary")
        elif isinstance(inner, ast.BoolOp):
            marks.append(f"bool:{type(inner.op).__name__}")
    members = [mark for mark in marks if mark.startswith("member:")]
    if len(members) < 2:
        return None
    return " ".join(sorted(marks))


def detect_duplicated_derivation(modules: Sequence[Module]) -> list[Candidate]:
    """Identical DERIVATIONS over the same closed-value members, in different modules.

    The enum_subset detector only sees members gathered into a COLLECTION. A ternary
    that chooses between two members on a comparison states a rule just as firmly and
    is invisible to it -- the members never meet in a set. Three verbatim copies of one
    IVA flow-direction derivation were found by hand for exactly this reason, and the
    hand-find is what motivated this detector.

    Fingerprinting is naming-blind: variable names, parameter names and the enclosing
    function's own name are all erased, because those are precisely the axes a second
    author spells differently while writing the same rule.
    """
    by_shape: dict[str, list[str]] = collections.defaultdict(list)
    for module in modules:
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.IfExp | ast.Compare):
                continue
            shape = _normalised_expression(node)
            if shape is not None:
                by_shape[shape].append(f"{module.relative}:{node.lineno}")
    return [
        Candidate(
            detector="duplicated_derivation",
            fingerprint=shape,
            sites=tuple(sorted(sites)),
            weight=len(shape.split()) * len(sites),
        )
        for shape, sites in by_shape.items()
        if len({site.split(":")[0] for site in sites}) > 1
    ]


def detect_field_set(modules: Sequence[Module]) -> list[Candidate]:
    """Record types in different modules declaring an identical field set.

    A record shape is a claim about what a thing IS. The same field set under two class
    names is the same concept modelled twice, and the two copies drift independently --
    which at a persistence boundary means one of them silently drops a field.
    """
    by_fields: dict[tuple[str, ...], list[str]] = collections.defaultdict(list)
    for module in modules:
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.ClassDef):
                continue
            fields = tuple(
                sorted(
                    inner.target.id
                    for inner in node.body
                    if isinstance(inner, ast.AnnAssign) and isinstance(inner.target, ast.Name)
                ),
            )
            if len(fields) >= _MIN_FIELD_SET:
                by_fields[fields].append(f"{module.relative}:{node.lineno} {node.name}")
    return [
        Candidate(
            detector="field_set",
            fingerprint=", ".join(fields[:8]),
            sites=tuple(sorted(sites)),
            weight=len(fields) * len(sites),
        )
        for fields, sites in by_fields.items()
        if len({site.split(":")[0] for site in sites}) > 1
    ]


def detect_import_overlap(modules: Sequence[Module]) -> list[Candidate]:
    """Module pairs depending on nearly the same first-party set, with no edge between.

    Two implementations of one concept reach for the same collaborators. The
    no-edge condition is what separates a duplicate from a legitimate layering: a
    module that USES another is not a copy of it.
    """
    candidates: list[Candidate] = []
    considered = [module for module in modules if len(module.first_party_imports) >= _MIN_IMPORT_SET]
    for index, left in enumerate(considered):
        for right in considered[index + 1 :]:
            union = left.first_party_imports | right.first_party_imports
            if not union:
                continue
            overlap = len(left.first_party_imports & right.first_party_imports) / len(union)
            if overlap < _IMPORT_JACCARD_FLOOR:
                continue
            left_stem = Path(left.relative).stem
            right_stem = Path(right.relative).stem
            if any(right_stem in imported for imported in left.first_party_imports) or any(
                left_stem in imported for imported in right.first_party_imports
            ):
                continue
            candidates.append(
                Candidate(
                    detector="import_overlap",
                    fingerprint=f"jaccard={overlap:.2f}",
                    sites=(left.relative, right.relative),
                    weight=int(overlap * 100),
                ),
            )
    return candidates


def detect_package_overlap(modules: Sequence[Module]) -> list[Candidate]:
    """Package pairs whose behaviour fingerprints overlap heavily.

    The whole-module-lives-twice case. Rolled up from function fingerprints rather
    than from names, so two packages solving one problem under different vocabulary
    still collide.
    """
    by_package: dict[str, set[frozenset[str]]] = collections.defaultdict(set)
    for module in modules:
        package = str(Path(module.relative).parent)
        for node in ast.walk(module.tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                fingerprint = _call_fingerprint(node)
                if len(fingerprint) >= _MIN_CALL_FINGERPRINT:
                    by_package[package].add(fingerprint)
    packages = [(name, prints) for name, prints in by_package.items() if len(prints) >= 4]
    candidates: list[Candidate] = []
    for index, (left_name, left_prints) in enumerate(packages):
        for right_name, right_prints in packages[index + 1 :]:
            shared = left_prints & right_prints
            if not shared:
                continue
            overlap = len(shared) / min(len(left_prints), len(right_prints))
            if overlap < 0.25:
                continue
            candidates.append(
                Candidate(
                    detector="package_overlap",
                    fingerprint=f"{len(shared)} shared behaviours, overlap={overlap:.2f}",
                    sites=(left_name, right_name),
                    weight=int(overlap * 100) + len(shared),
                ),
            )
    return candidates


_DETECTORS = {
    "enum_subset": detect_enum_subset,
    "scarce_literal": detect_scarce_literal,
    "call_fingerprint": detect_call_fingerprint,
    "duplicated_derivation": detect_duplicated_derivation,
    "field_set": detect_field_set,
    "import_overlap": detect_import_overlap,
    "package_overlap": detect_package_overlap,
}


def run(root: Path, detectors: Sequence[str]) -> list[Candidate]:
    """Run the named detectors over ``root`` and return candidates, heaviest first."""
    modules = _load_modules(root)
    _populate(modules, _closed_enum_names(modules))
    found: list[Candidate] = []
    for name in detectors:
        found.extend(_DETECTORS[name](modules))
    return sorted(found, key=lambda candidate: (-candidate.weight, candidate.detector, candidate.sites))


def _render(candidates: Sequence[Candidate], limit: int) -> str:
    """Render a human report, heaviest candidates first."""
    lines: list[str] = []
    by_detector: dict[str, list[Candidate]] = collections.defaultdict(list)
    for candidate in candidates:
        by_detector[candidate.detector].append(candidate)
    lines.append(f"{len(candidates)} candidate(s) across {len(by_detector)} detector(s)")
    lines.append("These are CANDIDATES, not verdicts: confirm each site before collapsing anything.\n")
    for detector, group in sorted(by_detector.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"== {detector}: {len(group)} candidate(s), showing up to {limit}")
        for candidate in group[:limit]:
            lines.append(f"  [{candidate.weight}] {candidate.fingerprint}")
            for site in candidate.sites:
                lines.append(f"       {site}")
        lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the semantic-duplication scan."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_PRODUCT_SOURCE_ROOT)
    parser.add_argument("--detector", action="append", choices=sorted(_DETECTORS), default=None)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    candidates = run(args.root, args.detector or sorted(_DETECTORS))
    if args.json:
        json.dump([candidate.as_dict() for candidate in candidates], sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_render(candidates, args.limit) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
