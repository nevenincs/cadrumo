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
    uv run --no-sync python -m dev.audit.semantic_duplication --full     # every candidate, uncapped
    uv run --no-sync python -m dev.audit.semantic_duplication --json     # machine output
    uv run --no-sync python -m dev.audit.semantic_duplication --detector enum_subset
"""

from __future__ import annotations

import argparse
import ast
import collections
import io
import itertools
import json
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from dev.first_party_source import SOURCE_PACKAGES, is_production_source

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Scope is every package under ``src/``, matching the sibling duplication runner:
#: the duplication that matters is duplicate AUTHORITY in shipped code, and one
#: corpus across the packages lets a rule restated in another package collide.
#: ``dev/`` is scannable on demand by passing different roots, not by widening the
#: default.
_SOURCE_ROOTS = tuple(_REPO_ROOT / package for package in SOURCE_PACKAGES)

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

_ENUM_BASES = frozenset({"StrEnum", "IntEnum", "Enum"})

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
    tree: ast.Module
    enum_partitions: set[tuple[str, tuple[str, ...]]] = field(default_factory=set)
    literal_scopes: list[frozenset[object]] = field(default_factory=list)
    first_party_imports: set[str] = field(default_factory=set)
    imported_names: set[str] = field(default_factory=set)
    closed_enum_names: frozenset[str] = frozenset()


def _iter_source_files(root: Path) -> Iterator[Path]:
    """Yield every production module under ``root``."""
    for path in sorted(root.rglob("*.py")):
        if not is_production_source(path, root=root):
            continue
        yield path


def _closed_enums(modules: Sequence[Module]) -> dict[str, frozenset[str]]:
    """Return every closed value-set class declared in the tree, with its declared members.

    Discovered rather than listed. A hand-kept list of enums is itself the kind of
    restated inventory this runner exists to find, and it would go stale the first
    time a new closed axis landed.
    """
    enums: dict[str, set[str]] = {}
    for module in modules:
        for node in ast.walk(module.tree):
            if isinstance(node, ast.ClassDef) and any(_base_name(base) in _ENUM_BASES for base in node.bases):
                enums.setdefault(node.name, set()).update(_declared_members(node))
    return {name: frozenset(members) for name, members in enums.items()}


def _base_name(base: ast.expr) -> str:
    """Return the last segment of a class base expression."""
    return _trailing_name(base) or ""


def _trailing_name(node: ast.expr) -> str | None:
    """Return the last segment of a name or attribute expression."""
    if isinstance(node, ast.Name):
        return node.id
    return node.attr if isinstance(node, ast.Attribute) else None


def _declared_members(node: ast.ClassDef) -> Iterator[str]:
    """Yield the upper-case names an enum class body assigns."""
    for statement in node.body:
        targets = statement.targets if isinstance(statement, ast.Assign) else ()
        for target in targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                yield target.id


def load_modules(roots: Sequence[Path]) -> list[Module]:
    """Parse every production module under ``roots`` once; every detector reads these.

    A module is named relative to its root's parent, so each site carries its
    package (``cadrumo/...``, ``cadrumo_runtime/...``) and two packages' modules
    can never share a name. Each root must yield a module: a root that yields
    none is refused, so a lost package cannot shrink the corpus unnoticed.

    A module that does not parse is REFUSED rather than dropped. This list is
    the corpus for every detector in this file, so a silently skipped module
    hides its duplicates from all of them at once - and nothing downstream
    reports a corpus size, so a short corpus and a clean one look identical.

    Measured against the src/ packages: 3544 source files, none unparsable, so
    refusing costs nothing today and says so immediately if that changes.
    """
    modules: list[Module] = []
    for root in roots:
        loaded = [_load_module(path, root) for path in _iter_source_files(root)]
        if not loaded:
            raise SystemExit(f"no production modules found under {root}; every detector would report clean")
        modules.extend(loaded)
    return modules


def _load_module(path: Path, root: Path) -> Module:
    """Read and parse one module, refusing rather than dropping one that cannot be analysed."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as error:
        # A module the walk listed and the read could not reach shortens the
        # corpus exactly as an unparsable one does, and a raw traceback names
        # neither the loss nor its size. Refused for its own reason, so a
        # caller matching on one cause cannot be satisfied by the other.
        raise SystemExit(
            f"{path} could not be read, so the duplication corpus would be short "
            f"by exactly the module nobody can analyse: {error}"
        ) from error
    try:
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError) as error:
        raise SystemExit(
            f"{path} could not be parsed, so the duplication corpus would be short "
            f"by exactly the module nobody can analyse: {error}"
        ) from error
    return Module(path=path, relative=path.relative_to(root.parent).as_posix(), tree=tree)


def _populate(modules: Sequence[Module], enums: dict[str, frozenset[str]]) -> None:
    """Fill each module's referenced meanings from its syntax tree."""
    first_party_roots = {PurePosixPath(package).name for package in SOURCE_PACKAGES}
    first_party_roots.update(PurePosixPath(module.relative).parts[0] for module in modules)
    closed_enum_names = frozenset(enums)
    for module in modules:
        module.closed_enum_names = closed_enum_names
        module.literal_scopes = [_scope_literals(scope) for scope in _literal_scope_nodes(module.tree.body)]
        for node in ast.walk(module.tree):
            _populate_reference_node(node, module, closed_enum_names, first_party_roots)


def detect_enum_subset(modules: Sequence[Module]) -> list[Candidate]:
    """Modules drawing the SAME multi-member partition through one closed enum.

    A partition is members gathered in ONE expression: a collection, or an ``or``/``and``
    chain testing one subject. Members a module merely mentions in unrelated places
    state no line through the axis, so they are not a fingerprint of anything.

    Whole-enum references are excluded against the DECLARED members: a site naming every
    member is usually exhaustively dispatching, not partitioning.
    """
    enums = _closed_enums(modules)
    by_subset: dict[tuple[str, tuple[str, ...]], set[str]] = collections.defaultdict(set)
    for module in modules:
        for enum_name, subset in module.enum_partitions:
            if set(subset) != enums[enum_name]:
                by_subset[(enum_name, subset)].add(module.relative)
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


def _scarce_literals(modules: Sequence[Module]) -> set[object]:
    """Return the literals stated in more than one module but in few enough to be scarce."""
    sites_by_literal: dict[object, set[str]] = collections.defaultdict(set)
    for module in modules:
        for scope in module.literal_scopes:
            for literal in scope:
                sites_by_literal[literal].add(module.relative)
    return {literal for literal, sites in sites_by_literal.items() if 1 < len(sites) <= _SCARCE_LITERAL_CEILING}


def _sites_by_scarce_pair(modules: Sequence[Module], scarce: set[object]) -> dict[tuple[object, object], set[str]]:
    """Return, per pair of scarce literals met in one scope, the modules stating that pair."""
    sites_by_pair: dict[tuple[object, object], set[str]] = collections.defaultdict(set)
    for module in modules:
        for scope in module.literal_scopes:
            for pair in itertools.combinations(sorted(scope & scarce, key=repr), 2):
                sites_by_pair[pair].add(module.relative)
    return sites_by_pair


def _shared_literals_by_site_pair(
    sites_by_pair: dict[tuple[object, object], set[str]],
) -> dict[tuple[str, str], set[object]]:
    """Return, per pair of modules, the literals of every literal pair both state."""
    shared: dict[tuple[str, str], set[object]] = collections.defaultdict(set)
    for pair, sites in sites_by_pair.items():
        for site_pair in itertools.combinations(sorted(sites), 2):
            shared[site_pair].update(pair)
    return shared


def detect_scarce_literal(modules: Sequence[Module]) -> list[Candidate]:
    """Module pairs that each state the same two or more SCARCE literals TOGETHER.

    In a regulated domain a rule is a number. Two modules that both mention the same
    scarce rate, threshold or code are very often two implementations of the provision
    that fixes it -- and unlike a name, a regulated figure cannot be paraphrased.

    Two shared literals rather than one: a single shared figure is frequently a genuine
    cross-reference, while a pair is a shared rule. The pair must meet inside one
    function or top-level statement on both sides; two values hundreds of lines apart
    are not one rule, and counting them made every large module collide with every other.
    """
    scarce = _scarce_literals(modules)
    shared = _shared_literals_by_site_pair(_sites_by_scarce_pair(modules, scarce))
    return [
        Candidate(
            detector="scarce_literal",
            fingerprint=" + ".join(repr(literal) for literal in sorted(literals, key=repr)[:6]),
            sites=site_pair,
            weight=len(literals),
        )
        for site_pair, literals in shared.items()
    ]


def _call_marks(call: ast.Call) -> list[str]:
    """Return the callee and keyword marks of one call expression."""
    marks: list[str] = []
    func = call.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    if name is not None and name:
        marks.append(f"call:{name}/{len(call.args)}")
    # A keyword is the callee's vocabulary, so a second author cannot rename it.
    marks.extend(f"kw:{keyword.arg}" for keyword in call.keywords if keyword.arg is not None)
    return marks


def _node_marks(inner: ast.AST) -> list[str]:
    """Return the behaviour marks one syntax node contributes to a call fingerprint."""
    if isinstance(inner, ast.Call):
        return _call_marks(inner)
    if isinstance(inner, ast.Constant) and _meaningful_literal(inner):
        return [f"lit:{inner.value!r}"]
    if isinstance(inner, ast.Compare):
        return [f"cmp:{type(op).__name__}" for op in inner.ops]
    return []


def _call_fingerprint(node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    """Return what a function DOES: the callees it invokes and the literals it uses.

    Deliberately blind to the function's own name, its parameter names, its local
    variable names and its comments -- every axis a second author would spell
    differently while implementing the same rule.
    """
    marks: set[str] = set()
    documentation = _documentation_constants(node)
    for inner in ast.walk(node):
        if id(inner) in documentation:
            continue
        marks.update(_node_marks(inner))
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


def _normalised_expression(node: ast.AST, closed_enum_names: frozenset[str]) -> str | None:
    """Return a naming-blind fingerprint of one expression, or ``None`` if trivial.

    Identifiers are erased and only STRUCTURE plus the closed-value members and
    literals survive, so two authors who spell the same derivation with different
    variable names produce the same fingerprint. A ternary choosing between two
    enum members on a comparison is the shape this exists to catch.

    Each member keeps its enum, so ``Effect.NONE`` does not collide with ``Stage.NONE``.
    A ternary keeps its order, so ``A if c else B`` does not collide with its inverse;
    anything else is sorted, because ``{A, B}`` and ``{B, A}`` are one set.
    """
    marks: list[str] = []
    for inner in ast.walk(node):
        _append_expression_mark(inner, marks, closed_enum_names)
    members = [mark for mark in marks if mark.startswith("member:")]
    if len(members) < 2:
        return None
    return " ".join(marks if "ternary" in marks else sorted(marks))


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
            shape = _normalised_expression(node, module.closed_enum_names)
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
            fields = _declared_field_names(node)
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
            _append_import_overlap(left, right, candidates)
    return candidates


def detect_package_overlap(modules: Sequence[Module]) -> list[Candidate]:
    """Package pairs whose behaviour fingerprints overlap heavily.

    The whole-module-lives-twice case. Rolled up from function fingerprints rather
    than from names, so two packages solving one problem under different vocabulary
    still collide.
    """
    by_package: dict[str, set[frozenset[str]]] = collections.defaultdict(set)
    for module in modules:
        _accumulate_package_fingerprints(module, by_package)
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


DETECTORS = {
    "enum_subset": detect_enum_subset,
    "scarce_literal": detect_scarce_literal,
    "call_fingerprint": detect_call_fingerprint,
    "duplicated_derivation": detect_duplicated_derivation,
    "field_set": detect_field_set,
    "import_overlap": detect_import_overlap,
    "package_overlap": detect_package_overlap,
}


def run(roots: Sequence[Path], detectors: Sequence[str]) -> list[Candidate]:
    """Run the named detectors over one corpus of ``roots`` and return candidates, heaviest first."""
    modules = load_modules(roots)
    _populate(modules, _closed_enums(modules))
    found: list[Candidate] = []
    for name in detectors:
        found.extend(DETECTORS[name](modules))
    return sorted(found, key=lambda candidate: (-candidate.weight, candidate.detector, candidate.sites))


def render(candidates: Sequence[Candidate], limit: int | None) -> str:
    """Render a human report, heaviest candidates first."""
    lines: list[str] = []
    by_detector: dict[str, list[Candidate]] = collections.defaultdict(list)
    for candidate in candidates:
        by_detector[candidate.detector].append(candidate)
    lines.append(f"{len(candidates)} candidate(s) across {len(by_detector)} detector(s)")
    lines.append("These are CANDIDATES, not verdicts: confirm each site before collapsing anything.\n")
    for detector, group in sorted(by_detector.items(), key=lambda kv: -len(kv[1])):
        shown = group if limit is None else group[:limit]
        scope = "showing all" if limit is None else f"showing up to {limit}, --full for all"
        lines.append(f"== {detector}: {len(group)} candidate(s), {scope}")
        for candidate in shown:
            lines.append(f"  [{candidate.weight}] {candidate.fingerprint}")
            for site in candidate.sites:
                lines.append(f"       {site}")
        lines.append("")
    return "\n".join(lines)


def emit(text: str) -> None:
    """Write the report as UTF-8; fingerprints carry literals a Windows console codec cannot encode."""
    stream = sys.stdout
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding="utf-8")
    stream.write(text)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the semantic-duplication scan."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        action="append",
        default=None,
        help="A source root to scan; repeat for several. Defaults to every package under src/.",
    )
    parser.add_argument("--detector", action="append", choices=sorted(DETECTORS), default=None)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--full", action="store_true", help="List every candidate per detector, uncapped.")
    parser.add_argument("--json", action="store_true", help="Emit every candidate as JSON (never capped).")
    args = parser.parse_args(argv)

    candidates = run(args.root or _SOURCE_ROOTS, args.detector or sorted(DETECTORS))
    if args.json:
        emit(json.dumps([candidate.as_dict() for candidate in candidates], indent=2) + "\n")
    else:
        emit(render(candidates, None if args.full else args.limit) + "\n")
    return 0


def _meaningful_literal(node: ast.Constant) -> bool:
    """Use the existing scalar literal population, excluding trivial values and bool."""
    return (
        isinstance(node.value, int | float | str)
        and node.value not in _TRIVIAL_LITERALS
        and not isinstance(node.value, bool)
    )


def _declared_field_names(node: ast.ClassDef) -> tuple[str, ...]:
    """Fingerprint exactly the annotated bare-name fields in the class body."""
    fields = tuple(
        sorted(
            inner.target.id
            for inner in node.body
            if isinstance(inner, ast.AnnAssign) and isinstance(inner.target, ast.Name)
        ),
    )
    return fields


def _populate_reference_node(
    node: ast.AST, module: Module, closed_enum_names: frozenset[str], first_party_roots: set[str]
) -> None:
    """Record the enum partition or first-party import one node states."""
    if isinstance(node, ast.ImportFrom | ast.Import):
        _record_imports(node, module, first_party_roots)
        return
    for owner, members in _partition_members(node, closed_enum_names).items():
        if len(members) >= 2:
            module.enum_partitions.add((owner, tuple(sorted(members))))


def _partition_members(node: ast.AST, closed_enum_names: frozenset[str]) -> dict[str, set[str]]:
    """Return the members one collection or boolean chain gathers, by owning enum."""
    if isinstance(node, ast.Set | ast.List | ast.Tuple):
        operands: Sequence[ast.AST] = node.elts
    elif isinstance(node, ast.BoolOp):
        operands = [operand for value in node.values if isinstance(value, ast.Compare) for operand in value.comparators]
    else:
        return {}
    gathered: dict[str, set[str]] = {}
    for operand in operands:
        reference = _enum_reference(operand, closed_enum_names)
        if reference is not None:
            gathered.setdefault(reference[0], set()).add(reference[1])
    return gathered


def _module_path(relative: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return a module's dotted parts and the parts of the package holding it."""
    parts = PurePosixPath(relative).with_suffix("").parts
    if parts[-1] == "__init__":
        return parts[:-1], parts[:-1]
    return parts, parts[:-1]


def _record_imports(node: ast.ImportFrom | ast.Import, module: Module, first_party_roots: set[str]) -> None:
    """Record first-party imports under absolute names, so equal text means one module.

    ``.contracts`` in two packages is two modules, and ``typing`` is nobody's collaborator.
    """
    if isinstance(node, ast.Import):
        targets = [alias.name for alias in node.names]
        names = targets
    else:
        target = _absolute_import_target(node, module)
        if target is None:
            return
        names = [f"{target}.{alias.name}" for alias in node.names]
        targets = names if node.module is None else [target]
    first_party = [target for target in targets if target.split(".")[0] in first_party_roots]
    module.first_party_imports.update(first_party)
    module.imported_names.update(name for name in names if name.split(".")[0] in first_party_roots)


def _absolute_import_target(node: ast.ImportFrom, module: Module) -> str | None:
    """Resolve a ``from`` import to its absolute module; ``None`` if it escapes the corpus."""
    if not node.level:
        return node.module
    _, package = _module_path(module.relative)
    ascent = node.level - 1
    if ascent >= len(package):
        return None
    base = package[: len(package) - ascent]
    return ".".join((*base, *((node.module,) if node.module is not None else ())))


def _documentation_constants(node: ast.AST) -> set[int]:
    """Return the string constants that are statements, which document and do nothing."""
    return {
        id(inner.value)
        for inner in ast.walk(node)
        if isinstance(inner, ast.Expr) and isinstance(inner.value, ast.Constant) and isinstance(inner.value.value, str)
    }


def _literal_scope_nodes(body: Sequence[ast.stmt]) -> Iterator[ast.stmt]:
    """Yield the units a rule can live in: each function and each other statement, through classes."""
    for statement in body:
        if isinstance(statement, ast.ClassDef):
            yield from _literal_scope_nodes(statement.body)
        else:
            yield statement


def _scope_literals(scope: ast.stmt) -> frozenset[object]:
    """Return the meaningful literals one scope states, without its documentation."""
    documentation = _documentation_constants(scope)
    return frozenset(
        inner.value
        for inner in ast.walk(scope)
        if isinstance(inner, ast.Constant) and id(inner) not in documentation and _meaningful_literal(inner)
    )


def _append_import_overlap(left: Module, right: Module, candidates: list[Candidate]) -> None:
    """Append import overlap."""
    union = left.first_party_imports | right.first_party_imports
    if not union:
        return
    overlap = len(left.first_party_imports & right.first_party_imports) / len(union)
    if overlap < _IMPORT_JACCARD_FLOOR:
        return
    if _imports_module(left, right) or _imports_module(right, left):
        return
    candidates.append(
        Candidate(
            detector="import_overlap",
            fingerprint=f"jaccard={overlap:.2f}",
            sites=(left.relative, right.relative),
            weight=int(overlap * 100),
        ),
    )


def _imports_module(importer: Module, imported: Module) -> bool:
    """Tell whether one module imports the other, comparing whole module names."""
    name = ".".join(_module_path(imported.relative)[0])
    return name in importer.first_party_imports or name in importer.imported_names


def _accumulate_package_fingerprints(module: Module, by_package: dict[str, set[frozenset[str]]]) -> None:
    """Accumulate package fingerprints."""
    package = PurePosixPath(module.relative).parent.as_posix()
    for node in ast.walk(module.tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            fingerprint = _call_fingerprint(node)
            if len(fingerprint) >= _MIN_CALL_FINGERPRINT:
                by_package[package].add(fingerprint)


def _append_expression_mark(inner: ast.AST, marks: list[str], closed_enum_names: frozenset[str]) -> None:
    """Append expression mark."""
    reference = _enum_reference(inner, closed_enum_names)
    if reference is not None:
        marks.append(f"member:{reference[0]}.{reference[1]}")
    elif isinstance(inner, ast.Constant) and _meaningful_literal(inner):
        marks.append(f"lit:{inner.value!r}")
    elif isinstance(inner, ast.Compare):
        marks.extend(f"cmp:{type(op).__name__}" for op in inner.ops)
    elif isinstance(inner, ast.IfExp):
        marks.append("ternary")
    elif isinstance(inner, ast.BoolOp):
        marks.append(f"bool:{type(inner.op).__name__}")
    elif isinstance(inner, ast.UnaryOp) and isinstance(inner.op, ast.Not):
        marks.append("not")


def _enum_reference(node: ast.AST, enum_names: frozenset[str]) -> tuple[str, str] | None:
    """Return ``(enum, member)`` for ``Enum.MEMBER``, also when the enum is reached through a module."""
    if not isinstance(node, ast.Attribute) or not node.attr.isupper():
        return None
    owner = _trailing_name(node.value)
    return (owner, node.attr) if owner is not None and owner in enum_names else None


if __name__ == "__main__":
    raise SystemExit(main())
