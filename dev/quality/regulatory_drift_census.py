"""Repo-wide census of regulatory data resident in Python instead of the registry.

The authority-flow rule says AEAT schema, constants, thresholds and
registry-shaped data live in the registry authoring tree or the central config,
never inlined at a call site. This census quantifies over the SOURCE to find
where that is not true -- over every production module under ``src/cadrumo``
and ``dev``, not over a list of known offenders. The direction is the whole
point: a census that iterates a known-offender list cannot see an offender
nobody listed, and being unlisted is exactly what is being asked about.

Seven detectors, each answering a different question, and each chosen because a
real instance of it exists in this tree:

``filing_year_literal``
    A bare integer in the filing-year span appearing in code. Name-independent,
    so it catches ``ejercicio=2022`` and ``ge=2000, le=2099`` that no naming
    convention would surface.
``regulatory_named_constant``
    A name carrying AEAT tax vocabulary bound to a number or a collection of
    numbers. The vocabulary is Spanish-stemmed because the domain is, per the
    naming rule.
``decimal_literal``
    A ``Decimal`` literal that is not a scale or rounding quantum. Rates,
    coefficients and thresholds are written this way throughout.
``year_set``
    A collection of two or more filing-year integers -- the shape the coverage
    decision replaces with a declared supported-filing-years catalogue.
``modelo_keyed_mapping_entry``
    One entry of a mapping literal keyed by a :class:`Modelo` member. Per-entry
    rather than per-mapping, because the unit that migrates is one modelo's row.
``modelo_conditional_branch``
    A comparison or match on a concrete ``Modelo`` member: behaviour conditioned
    per modelo in Python rather than declared as registry data.
``design_prose_grammar``
    A regular expression that parses Spanish AEAT design prose to derive a
    filing wire fact -- field widths, a ``Constante`` value, a trailing
    ``Nota N`` reference. The interpretation of official text encoded as a
    Python pattern is regulatory semantics living outside the registry, and the
    export-tree generator is the named instance.
``dev_resident_regulatory_data``
    Filing wire facts checked into ``dev`` as data files rather than into the
    registry authoring tree.

**Findings are keyed by ``(path, enclosing symbol, kind, detail)`` and never by
line number**, so a finding survives the edit above it and an adjudication
cannot be silently detached by a reformat. Repeated occurrences of one finding
inside one symbol collapse into that finding's ``occurrences`` count, which is
reported but is not part of its identity.

What this cannot decide, stated rather than assumed away:

- **Whether a number is regulatory.** ``4`` in ``_FOUR_YEAR_WINDOW`` is the LIVA
  compensation window and ``4`` in ``_MAX_ANCESTOR_DEPTH`` is a search bound.
  Nothing in the syntax separates them. The census reports both and the
  adjudication ledger beside it records which is which, with a reason.
- **Values reached indirectly.** A regulatory number computed from two others,
  read from an environment variable, or assembled by string formatting.
- **Non-Python carriers** other than the two ``dev`` directories named
  explicitly. The registry authoring tree is TOML by design and is sanctioned.

The sanctioned channels are excluded structurally, not by allowlist:
``core/external_constants.py`` is the curated leaf home the authority-flow rule
grants, and the registry authoring tree is data. Everything else that looks
regulatory is reported and must be adjudicated.
"""

from __future__ import annotations

import argparse
import ast
import json
import tomllib
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory

from .._paths import REPO_ROOT

SOURCE_ROOT: Final[Path] = REPO_ROOT / "src" / "cadrumo"
DEV_ROOT: Final[Path] = REPO_ROOT / "dev"
DISPOSITIONS_PATH: Final[Path] = Path(__file__).with_name("regulatory_drift_dispositions.toml")

#: The curated leaf channel the authority-flow rule grants for a true regulatory
#: leaf constant. Excluded structurally: a value here is already centralised, and
#: reporting it would make the census argue against its own sanctioned answer.
SANCTIONED_PYTHON_HOMES: Final[tuple[Path, ...]] = (SOURCE_ROOT / "core" / "external_constants.py",)

#: Filing years a taxpayer could plausibly file for. Deliberately wide: a value
#: outside it is not a year, and a narrow window would miss a historical
#: transitional cut-off, which is exactly the drift worth finding.
FILING_YEAR_SPAN: Final[range] = range(1960, 2101)

#: Decimal values that are scale, identity or a rounding quantum rather than a
#: regulatory quantity. Compared as text, because ``Decimal("0.10")`` and
#: ``Decimal("0.1")`` are different literals with the same value and only the
#: written form tells you which one an author meant.
SCALE_DECIMALS: Final[frozenset[str]] = frozenset(
    {"0", "-0", "1", "-1", "2", "100", "0.0", "0.00", "0.000", "0.0000", "1.0", "0.01", "0.001", "0.0001", "0.00001"}
)

#: AEAT tax vocabulary, Spanish-stemmed per the domain naming rule. A name
#: carrying one of these and bound to a number is a candidate regulatory
#: constant. Matched case-insensitively against the identifier.
REGULATORY_NAME_STEMS: Final[tuple[str, ...]] = (
    "ejercicio",
    "filing_year",
    "deduccion",
    "reduccion",
    "retencion",
    "recargo",
    "cuota",
    "prorrata",
    "devengo",
    "exencion",
    "amortizacion",
    "minimo_",
    "modulo",
    "epigrafe",
    "casilla",
    "tramo",
    "escala",
    "coeficiente",
    "porcentaje",
    "umbral",
    "importe",
    "_eur",
    "_pct",
    "irpf",
    "iva",
    "renta",
    "articulo",
    "art_",
    "_dt",
    "dt12",
    "ley_",
    "aeat_",
    "declaracion",
    "tributar",
    "fiscal",
)

#: Spanish AEAT design-prose vocabulary. A regular expression whose pattern
#: carries one of these is parsing official design text to derive a wire fact.
DESIGN_PROSE_VOCABULARY: Final[tuple[str, ...]] = (
    "entero",
    "decimale",
    "constante",
    "nota",
    "ejercicio",
    "casilla",
    "importe",
    "declaracion",
    "periodo",
)

#: Directories under ``dev`` holding filing wire facts as checked-in data. Named
#: by the plan row this census executes; enumerated rather than described so a
#: new file inside one is a new finding without an edit here.
DEV_REGULATORY_DATA_DIRS: Final[tuple[Path, ...]] = (
    DEV_ROOT / "registry" / "mappings",
    DEV_ROOT / "registry" / "render_profiles",
)

MODULE_SCOPE: Final[str] = "<module>"


class DriftCensusError(RuntimeError):
    """Raised when the census or its adjudication ledger cannot be reconciled."""


class FindingKind(StrEnum):
    """The seven drift classes this census detects."""

    FILING_YEAR_LITERAL = "filing_year_literal"
    REGULATORY_NAMED_CONSTANT = "regulatory_named_constant"
    DECIMAL_LITERAL = "decimal_literal"
    YEAR_SET = "year_set"
    MODELO_KEYED_MAPPING_ENTRY = "modelo_keyed_mapping_entry"
    MODELO_CONDITIONAL_BRANCH = "modelo_conditional_branch"
    DESIGN_PROSE_GRAMMAR = "design_prose_grammar"
    DEV_RESIDENT_REGULATORY_DATA = "dev_resident_regulatory_data"


class Disposition(StrEnum):
    """What was decided about a finding. Every finding carries exactly one."""

    #: Regulatory data with a plan row that moves it. ``row`` names the row.
    ENROLLED = "enrolled"
    #: Regulatory data deliberately not moved now. ``reference`` names the record.
    DEFERRED = "deferred"
    #: Not regulatory data. ``reason`` says why -- this is the allowlist, and it
    #: is where the judgement moves, so a bare entry is refused.
    NOT_REGULATORY = "not_regulatory"


@dataclass(frozen=True, order=True)
class Finding:
    """One drift candidate, identified without reference to a line number."""

    path: str
    enclosing_symbol: str
    kind: FindingKind
    detail: str
    occurrences: int = 1

    @property
    def key(self) -> tuple[str, str, str, str]:
        """Stable identity: path, enclosing symbol, kind, detail.

        Returns:
            The tuple an adjudication row is keyed by. ``occurrences`` is
            excluded deliberately -- a second occurrence of the same thing in
            the same function is not a new decision.
        """
        return (self.path, self.enclosing_symbol, str(self.kind), self.detail)


@dataclass(frozen=True)
class Adjudication:
    """One reviewed decision about one file's findings of one kind.

    A decision names a concrete file, never a directory -- the sole exception
    being the two ``dev`` data directories, which are directories by nature. That
    is what makes the gate bite: a NEW file carrying regulatory data is
    unadjudicated the moment it is written, where a directory-scoped decision
    would have swallowed it silently.

    The reasoning is authored once in a :class:`DecisionGroup` and referenced by
    id, so a shared judgement reads as one judgement instead of two hundred
    copies of the same paragraph.
    """

    disposition: Disposition
    rationale: str
    path: str
    kind: str = ""
    enclosing_symbol: str = ""
    detail: str = ""
    row: str = ""
    reference: str = ""
    group: str = ""

    @property
    def specificity(self) -> tuple[int, int, int, int]:
        """How narrowly this decision is drawn, most specific first.

        Returns:
            A comparable tuple; the widest match loses to the narrowest.
        """
        return (len(self.path), int(bool(self.kind)), int(bool(self.enclosing_symbol)), len(self.detail))

    def matches(self, finding: Finding) -> bool:
        """Return whether this decision covers ``finding``.

        Returns:
            ``True`` when the path matches exactly, or as a directory prefix for
            the ``dev`` data directories, and every stated constraint holds.
        """
        if finding.path != self.path and not finding.path.startswith(self.path.rstrip("/") + "/"):
            return False
        if self.kind and str(finding.kind) != self.kind:
            return False
        if self.enclosing_symbol and finding.enclosing_symbol != self.enclosing_symbol:
            return False
        return not (self.detail and not finding.detail.startswith(self.detail))


@dataclass(frozen=True)
class DecisionGroup:
    """A reasoning shared by many decisions, authored once."""

    identifier: str
    disposition: Disposition
    rationale: str
    row: str = ""
    reference: str = ""


def is_test_path(path: Path) -> bool:
    """Return whether ``path`` belongs to the test surface.

    Returns:
        ``True`` for files inside a ``tests`` package, ``test_*`` modules and
        ``conftest`` modules.
    """
    return "tests" in path.parts or path.name.startswith("test_") or path.name == "conftest.py"


def repo_relative(path: Path) -> str:
    """Return ``path`` as a repository-relative POSIX string.

    Returns:
        The relative path, or the absolute POSIX form when outside the repo.
    """
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _iter_python_files(*, scope: str) -> Iterator[Path]:
    for root in (SOURCE_ROOT, DEV_ROOT):
        for path in scan_directory(root, pattern="*.py", recursive=True, prune_directories=("__pycache__",)):
            if is_test_path(path) is not (scope == "tests"):
                continue
            if path.resolve() in {home.resolve() for home in SANCTIONED_PYTHON_HOMES}:
                continue
            yield path


def _docstring_constants(tree: ast.Module) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _enclosing_symbols(tree: ast.Module) -> dict[int, str]:
    """Map each node to the nearest enclosing function or class name."""
    symbols: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            for child in ast.walk(node):
                symbols[id(child)] = node.name
    return symbols


def _assigned_names(tree: ast.Module) -> dict[int, str]:
    """Map each assigned value node to the name it is bound to."""
    names: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets: Sequence[ast.expr] = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        name = next((t.id for t in targets if isinstance(t, ast.Name)), None)
        if name is not None:
            names[id(value)] = name
    return names


def _has_regulatory_stem(name: str) -> bool:
    lowered = name.lower()
    return any(stem in lowered for stem in REGULATORY_NAME_STEMS)


def _numeric_constant(node: ast.expr) -> bool:
    """Return whether ``node`` carries a number, including one wrapped in ``Decimal``.

    The ``Decimal`` case is not a nicety. It is how this repository writes every
    regulatory quantity, and omitting it made the named-constant detector blind
    to the entire population it exists to find: the difficult-justification
    percentage is written ``Decimal("1")``, which the value-shape detector also
    skips as a scale literal, so the two exclusions coincided and the constant
    was reported by neither.
    """
    if isinstance(node, ast.Constant):
        return isinstance(node.value, int | float) and not isinstance(node.value, bool)
    return _decimal_literal_text(node) is not None if isinstance(node, ast.Call) else False


def _modelo_member(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "Modelo":
        return node.attr
    return None


def _decimal_literal_text(node: ast.Call) -> str | None:
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
    if name != "Decimal" or not node.args:
        return None
    argument = node.args[0]
    if not isinstance(argument, ast.Constant) or isinstance(argument.value, bool):
        return None
    if not isinstance(argument.value, str | int | float):
        return None
    return str(argument.value)


def _regex_pattern(node: ast.Call) -> str | None:
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != "compile":
        return None
    if not node.args or not isinstance(node.args[0], ast.Constant):
        return None
    value = node.args[0].value
    return value if isinstance(value, str) else None


def _year_members(node: ast.expr) -> tuple[int, ...]:
    if not isinstance(node, ast.Tuple | ast.List | ast.Set):
        return ()
    values = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, int)]
    if len(values) != len(node.elts) or len(values) < 2:
        return ()
    if any(v not in FILING_YEAR_SPAN for v in values):
        return ()
    return tuple(sorted(set(values)))


def _scan_module(path: Path) -> Iterator[Finding]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return
    relative = repo_relative(path)
    docstrings = _docstring_constants(tree)
    symbols = _enclosing_symbols(tree)
    assigned = _assigned_names(tree)

    def symbol_for(node: ast.AST) -> str:
        return symbols.get(id(node), MODULE_SCOPE)

    years: dict[str, set[int]] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
            and node.value in FILING_YEAR_SPAN
            and id(node) not in docstrings
            and not _is_binary_magnitude(node.value)
        ):
            years.setdefault(symbol_for(node), set()).add(node.value)

        if isinstance(node, ast.Call):
            decimal_text = _decimal_literal_text(node)
            if decimal_text is not None and decimal_text not in SCALE_DECIMALS:
                yield Finding(relative, symbol_for(node), FindingKind.DECIMAL_LITERAL, decimal_text)
            pattern = _regex_pattern(node)
            if pattern is not None:
                lowered = pattern.lower()
                if any(word in lowered for word in DESIGN_PROSE_VOCABULARY):
                    name = assigned.get(id(node), "<inline>")
                    yield Finding(relative, symbol_for(node), FindingKind.DESIGN_PROSE_GRAMMAR, name)

        if isinstance(node, ast.Assign | ast.AnnAssign):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            name = next((t.id for t in targets if isinstance(t, ast.Name)), None)
            if name is not None and value is not None and _has_regulatory_stem(name):
                collection = isinstance(value, ast.Tuple | ast.List | ast.Set | ast.Dict)
                if _numeric_constant(value) or (collection and _contains_number(value)):
                    yield Finding(relative, symbol_for(node), FindingKind.REGULATORY_NAMED_CONSTANT, name)

        members = _year_members(node) if isinstance(node, ast.Tuple | ast.List | ast.Set) else ()
        if members:
            label = assigned.get(id(node), "<literal>")
            detail = f"{label}={','.join(str(m) for m in members)}"
            yield Finding(relative, symbol_for(node), FindingKind.YEAR_SET, detail)

        if isinstance(node, ast.Dict):
            for key in node.keys:
                member = _modelo_member(key)
                if member is not None:
                    label = assigned.get(id(node), "<literal>")
                    yield Finding(
                        relative,
                        symbol_for(node),
                        FindingKind.MODELO_KEYED_MAPPING_ENTRY,
                        f"{label}[{member}]",
                    )

        if isinstance(node, ast.Compare):
            members_seen = sorted({m for m in (_modelo_member(c) for c in [node.left, *node.comparators]) if m})
            members_seen += sorted(_modelo_members_in(node))
            if members_seen:
                yield Finding(
                    relative,
                    symbol_for(node),
                    FindingKind.MODELO_CONDITIONAL_BRANCH,
                    ",".join(sorted(set(members_seen))),
                )

        if isinstance(node, ast.match_case):
            matched = sorted(_modelo_members_in(node.pattern))
            if matched:
                yield Finding(
                    relative,
                    symbol_for(node),
                    FindingKind.MODELO_CONDITIONAL_BRANCH,
                    ",".join(matched),
                )

    for symbol, values in years.items():
        yield Finding(
            relative,
            symbol,
            FindingKind.FILING_YEAR_LITERAL,
            ",".join(str(v) for v in sorted(values)),
            occurrences=len(values),
        )


def _is_binary_magnitude(value: int) -> bool:
    """Return whether ``value`` is an exact power of two, and so a size rather than a year.

    ``2048`` is the only member of the filing-year span that is one, and it
    appears in this tree as a byte budget. Excluded structurally rather than by
    allowlist, because no AEAT filing year will ever be a power of two.
    """
    return value > 0 and value & (value - 1) == 0


def _modelo_members_in(node: ast.AST) -> set[str]:
    found: set[str] = set()
    for child in ast.walk(node):
        member = _modelo_member(child) if isinstance(child, ast.expr) else None
        if member is not None:
            found.add(member)
    return found


def _contains_number(node: ast.expr) -> bool:
    return any(_numeric_constant(child) for child in ast.walk(node) if isinstance(child, ast.expr))


def _dev_data_findings() -> Iterator[Finding]:
    """Yield one finding per modelo-and-epoch directory of dev-resident filing data.

    Grouped at the epoch rather than the file, because the epoch is the unit
    that is added: one new AEAT design epoch creates one directory and many
    files inside it, and a per-file census would report the same single decision
    over a hundred times.
    """
    for directory in DEV_REGULATORY_DATA_DIRS:
        if not directory.is_dir():
            continue
        groups: dict[str, int] = {}
        for path in scan_directory(directory, recursive=True, select=DirectoryEntryKind.FILES):
            relative = path.relative_to(directory).parts
            group = "/".join(relative[:2]) if len(relative) > 2 else "/".join(relative[:-1]) or "."
            groups[group] = groups.get(group, 0) + 1
        for group, count in sorted(groups.items()):
            yield Finding(
                repo_relative(directory),
                MODULE_SCOPE,
                FindingKind.DEV_RESIDENT_REGULATORY_DATA,
                group,
                occurrences=count,
            )


def census(*, scope: str = "production") -> tuple[Finding, ...]:
    """Walk the tree and return every drift candidate, deduplicated and sorted.

    Args:
        scope: ``production`` for non-test modules, ``tests`` for the test
            surface. The test surface is a different question -- a test's
            expected value legitimately comes from external authority -- so it
            is measured separately rather than mixed in.

    Returns:
        Findings in a stable order, with repeated occurrences of one finding
        inside one symbol collapsed into its ``occurrences`` count.
    """
    collapsed: dict[tuple[str, str, str, str], Finding] = {}
    sources: Iterable[Finding] = (finding for path in _iter_python_files(scope=scope) for finding in _scan_module(path))
    if scope == "production":
        sources = list(sources) + list(_dev_data_findings())
    for finding in sources:
        existing = collapsed.get(finding.key)
        if existing is None:
            collapsed[finding.key] = finding
        else:
            collapsed[finding.key] = Finding(
                existing.path,
                existing.enclosing_symbol,
                existing.kind,
                existing.detail,
                existing.occurrences + finding.occurrences,
            )
    return tuple(sorted(collapsed.values()))


def load_adjudications(path: Path = DISPOSITIONS_PATH) -> tuple[Adjudication, ...]:
    """Read the checked-in adjudication ledger and resolve its shared reasonings.

    Args:
        path: The ledger file.

    Returns:
        One record per adjudicated file-and-kind.

    Raises:
        DriftCensusError: If the ledger is missing or malformed, a decision
            states no rationale, an enrolled decision names no plan row, a
            deferred decision names no reference, an allowlist entry fails to
            name a file and an enclosing symbol, or a decision scopes a
            directory that is not one of the sanctioned data directories.
    """
    if not path.is_file():
        raise DriftCensusError(f"adjudication ledger not found at {path}")
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    groups = _load_groups(document)
    rows = document.get("decision", [])
    if not isinstance(rows, list):
        raise DriftCensusError("the ledger's [[decision]] section must be an array of tables")
    directory_scopes = frozenset(repo_relative(directory) for directory in DEV_REGULATORY_DATA_DIRS)
    adjudications: list[Adjudication] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        if not isinstance(row, Mapping) or "path" not in row:
            raise DriftCensusError(f"malformed ledger row {row!r}: no path")
        target = str(row["path"])
        kind = str(row.get("kind", "")).strip()
        symbol = str(row.get("enclosing_symbol", "")).strip()
        detail = str(row.get("detail", "")).strip()
        identity = (target, symbol, kind, detail)
        group_id = str(row.get("group", "")).strip()
        if group_id:
            group = groups.get(group_id)
            if group is None:
                raise DriftCensusError(f"ledger row {identity} names unknown group {group_id!r}")
            disposition, rationale = group.disposition, group.rationale
            plan_row, reference = group.row, group.reference
        else:
            try:
                disposition = Disposition(str(row["disposition"]))
            except (KeyError, ValueError) as error:
                raise DriftCensusError(f"malformed ledger row {identity}: {error}") from error
            rationale = str(row.get("rationale", "")).strip()
            plan_row = str(row.get("row", "")).strip()
            reference = str(row.get("reference", "")).strip()
        if not rationale:
            raise DriftCensusError(f"ledger row {identity} states no rationale; an entry without one is a mute button")
        if disposition is Disposition.ENROLLED and not plan_row:
            raise DriftCensusError(f"ledger row {identity} is enrolled but names no plan row")
        if disposition is Disposition.DEFERRED and not reference:
            raise DriftCensusError(f"ledger row {identity} is deferred but names no reference")
        if disposition is Disposition.NOT_REGULATORY and not (target.endswith(".py") and symbol):
            raise DriftCensusError(
                f"ledger row {identity} allowlists without naming a file and an enclosing symbol; "
                "the allowlist is keyed by path and enclosing function, never by directory"
            )
        if not target.endswith(".py") and target not in directory_scopes:
            raise DriftCensusError(
                f"ledger row {identity} scopes a directory. Only the sanctioned data directories "
                f"{sorted(directory_scopes)} may be adjudicated wholesale; every other decision names one file, "
                "so a new file carrying regulatory data is unadjudicated the moment it is written"
            )
        if identity in seen:
            raise DriftCensusError(f"ledger row {identity} is adjudicated twice")
        seen.add(identity)
        adjudications.append(
            Adjudication(disposition, rationale, target, kind, symbol, detail, plan_row, reference, group_id)
        )
    referenced = {entry.group for entry in adjudications if entry.group}
    orphaned = sorted(set(groups) - referenced)
    if orphaned:
        raise DriftCensusError(
            f"groups {orphaned} are declared but referenced by no decision; a reasoning nothing uses is stale"
        )
    return tuple(adjudications)


def _load_groups(document: Mapping[str, object]) -> Mapping[str, DecisionGroup]:
    rows = document.get("group", [])
    if not isinstance(rows, list):
        raise DriftCensusError("the ledger's [[group]] section must be an array of tables")
    groups: dict[str, DecisionGroup] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise DriftCensusError(f"malformed group {row!r}")
        try:
            identifier = str(row["id"])
            disposition = Disposition(str(row["disposition"]))
            rationale = str(row["rationale"]).strip()
        except (KeyError, ValueError) as error:
            raise DriftCensusError(f"malformed group {row!r}: {error}") from error
        if identifier in groups:
            raise DriftCensusError(f"group {identifier!r} is declared twice")
        groups[identifier] = DecisionGroup(
            identifier,
            disposition,
            rationale,
            str(row.get("row", "")).strip(),
            str(row.get("reference", "")).strip(),
        )
    return groups


@dataclass(frozen=True)
class CensusReport:
    """One census run reconciled against the ledger."""

    findings: tuple[Finding, ...]
    unadjudicated: tuple[Finding, ...]
    stale: tuple[str, ...]
    ambiguous: tuple[str, ...]

    @property
    def clean(self) -> bool:
        """Whether every finding is adjudicated exactly once and no row is stale.

        Returns:
            ``True`` when all three residues are empty.
        """
        return not (self.unadjudicated or self.stale or self.ambiguous)


def reconcile(*, scope: str = "production", ledger: Path = DISPOSITIONS_PATH) -> CensusReport:
    """Run the census and reconcile it against the checked-in ledger.

    Args:
        scope: The census scope.
        ledger: The adjudication ledger.

    Returns:
        The findings, the unadjudicated residue, and any ledger row that no
        longer matches a live finding.
    """
    findings = census(scope=scope)
    adjudications = load_adjudications(ledger)
    unadjudicated: list[Finding] = []
    ambiguous: list[str] = []
    used: set[int] = set()
    for finding in findings:
        matches = [entry for entry in adjudications if entry.matches(finding)]
        if not matches:
            unadjudicated.append(finding)
            continue
        best = max(entry.specificity for entry in matches)
        winners = [entry for entry in matches if entry.specificity == best]
        if len(winners) > 1:
            ambiguous.append(f"{finding.path}::{finding.enclosing_symbol} {finding.kind} {finding.detail}")
        used.update(id(entry) for entry in matches)
    stale = tuple(
        sorted(
            f"{entry.path}::{entry.enclosing_symbol or '*'} {entry.kind or '*'} {entry.detail or '*'}"
            for entry in adjudications
            if id(entry) not in used
        )
    )
    return CensusReport(findings=findings, unadjudicated=tuple(unadjudicated), stale=stale, ambiguous=tuple(ambiguous))


def render_ledger(findings: Sequence[Finding]) -> str:
    """Render a ledger skeleton for the given findings.

    Every row is emitted with an empty disposition, because a generator that
    guessed one would be asserting a judgement nobody made.

    Returns:
        TOML text.
    """
    lines = ["[meta]", "schema_version = 1", ""]
    for finding in findings:
        lines.extend(
            [
                "[[decision]]",
                f'path = "{finding.path}"',
                f'enclosing_symbol = "{finding.enclosing_symbol}"',
                f'kind = "{finding.kind}"',
                f'detail = "{finding.detail}"',
                'disposition = ""',
                'rationale = ""',
                "",
            ]
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the census and report.

    Args:
        argv: Command-line arguments; ``sys.argv`` when omitted.

    Returns:
        ``0`` when every finding is adjudicated and no ledger row is stale.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scope", choices=("production", "tests"), default="production")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument("--skeleton", action="store_true", help="emit an unadjudicated ledger skeleton")
    arguments = parser.parse_args(argv)

    if arguments.skeleton:
        print(render_ledger(census(scope=arguments.scope)))
        return 0

    report = reconcile(scope=arguments.scope)
    if arguments.json:
        print(
            json.dumps(
                {
                    "scope": arguments.scope,
                    "findings": [
                        {
                            "path": f.path,
                            "enclosing_symbol": f.enclosing_symbol,
                            "kind": str(f.kind),
                            "detail": f.detail,
                            "occurrences": f.occurrences,
                        }
                        for f in report.findings
                    ],
                    "unadjudicated": [list(f.key) for f in report.unadjudicated],
                    "stale": list(report.stale),
                    "ambiguous": list(report.ambiguous),
                },
                indent=2,
            )
        )
        return 0 if report.clean else 1

    by_kind: dict[str, int] = {}
    for finding in report.findings:
        by_kind[str(finding.kind)] = by_kind.get(str(finding.kind), 0) + 1
    print(f"scope                 : {arguments.scope}")
    print(f"findings              : {len(report.findings)}")
    for kind, count in sorted(by_kind.items()):
        print(f"  {kind:32s}: {count}")
    print(f"unadjudicated         : {len(report.unadjudicated)}")
    print(f"stale ledger rows     : {len(report.stale)}")
    print(f"ambiguous adjudications: {len(report.ambiguous)}")
    for finding in report.unadjudicated:
        print(f"  UNADJUDICATED: {finding.path}::{finding.enclosing_symbol} {finding.kind} {finding.detail}")
    for entry in report.stale:
        print(f"  STALE LEDGER ROW: {entry}")
    for entry in report.ambiguous:
        print(f"  AMBIGUOUS ADJUDICATION: {entry}")
    return 0 if report.clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
