"""Derive the modelo-specific registry module set and force one classification each.

The registry package mixes generic compiler machinery with modules that are
scoped to a single AEAT modelo, and some of those carry regulatory data --
rates, coefficients, thresholds, ejercicio sets, operator-facing prose -- as
Python literals rather than as registry authoring-tree data.  This module
derives the modelo-specific set MECHANICALLY so the inventory stays correct as
modules are added or renamed, gathers the regulatory-literal evidence that
makes a classification arguable, and reconciles both against the checked-in
adjudication ledger beside this file.

Derivation uses three independent signals, all keyed on
:class:`cadrumo.core.Modelo` so that adding a modelo to the enum widens the
detector with no edit here:

``module_name``
    A modelo code appears as a token in the module's file name
    (``_m347_threshold.py``, ``_applicability_modelo202.py``).
``modelo_reference``
    The module body reads a concrete ``Modelo.M###`` member.
``defined_symbol``
    A module-level function, class, or constant the module DEFINES carries a
    modelo code token (``evaluate_m210_resolve_base_imponible``).

The third signal is what makes the derivation stronger than a file-name glob:
``_formula_runtime_irnr.py`` names no modelo and reads no ``Modelo`` member,
yet every evaluator it defines is Modelo 210 scoped.

Classification is exactly one of :class:`Classification` per derived module and
is never inferred: it is adjudicated in the ledger with a written
justification.  What the ledger cannot do is stay silent.  Reconciliation
refuses an unclassified derived module, a ledger row for a module the
derivation no longer yields, a machinery claim that leaves detected
regulatory-literal evidence undispositioned, and a dead claim for a module
something still imports.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tomllib
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Final

from cadrumo.core import scan_directory
from dev._paths import REPO_ROOT, UTF_8

SOURCE_ROOT: Final[Path] = REPO_ROOT / "src" / "cadrumo"
REGISTRY_PACKAGE_ROOT: Final[Path] = SOURCE_ROOT / "domain" / "calculations" / "registry"
LEDGER_PATH: Final[Path] = Path(__file__).with_suffix(".toml")

__all__ = [
    "LEDGER_PATH",
    "REGISTRY_PACKAGE_ROOT",
    "REPO_ROOT",
    "SOURCE_ROOT",
    "Classification",
    "ClassificationEntry",
    "ClassificationLedgerError",
    "DerivationSignal",
    "EmbedEvidence",
    "EvidenceKind",
    "ModeloModuleRecord",
    "TreeOwnership",
    "census",
    "importer_index",
    "importers_of",
    "load_ledger",
    "modelo_codes",
    "reconcile",
    "render_ledger",
]

_UTF_8: Final[str] = UTF_8
_SCHEMA_VERSION: Final[int] = 1
_MODULE_SCOPE: Final[str] = "<module>"

#: Modelo codes whose authoring trees another campaign owns; an embed destined
#: for one of them is queued rather than migrated by this campaign.
CAMPAIGN_OWNED_MODELO_CODES: Final[frozenset[str]] = frozenset({"303", "390"})

#: A four-digit integer in this span reads as an AEAT ejercicio / filing year
#: rather than as an arithmetic constant.  The span is deliberately wider than
#: the corpus so a forward-dated regulatory year is still evidence.
_FILING_YEAR_SPAN: Final[range] = range(1960, 2101)

#: Constant-name suffixes that mark a string literal as operator-facing prose,
#: whose home is the locale catalogues rather than a Python module.
_PROSE_NAME_SUFFIXES: Final[tuple[str, ...]] = (
    "_REASON",
    "_MESSAGE",
    "_LABEL",
    "_TITLE",
    "_HELP",
    "_DESCRIPTION",
    "_NOTE",
)

#: Spanish orthography a bare identifier or code token never carries; its
#: presence in a long literal marks the literal as authored prose.
_SPANISH_ORTHOGRAPHY: Final[frozenset[str]] = frozenset("áéíóúüñÁÉÍÓÚÜÑ¿¡")
_PROSE_MIN_LENGTH: Final[int] = 24

_MODELO_TOKEN: Final[re.Pattern[str]] = re.compile(r"(?<![0-9])(?:m|modelo)?([0-9]{3})(?![0-9])", re.IGNORECASE)


class ClassificationLedgerError(RuntimeError):
    """Raised when the adjudication ledger is malformed."""


class DerivationSignal(StrEnum):
    """Why a module is in the derived modelo-specific set."""

    MODULE_NAME = "module_name"
    MODELO_REFERENCE = "modelo_reference"
    DEFINED_SYMBOL = "defined_symbol"


class EvidenceKind(StrEnum):
    """Mechanically detected shapes that read as regulatory data in Python."""

    DECIMAL_LITERAL = "decimal_literal"
    FILING_YEAR_LITERAL = "filing_year_literal"
    REGULATORY_PROSE_LITERAL = "regulatory_prose_literal"


class Classification(StrEnum):
    """The closed adjudication vocabulary; every derived module carries one."""

    REGULATORY_DATA_EMBED = "regulatory_data_embed"
    MACHINERY = "machinery"
    DEAD = "dead"


class TreeOwnership(StrEnum):
    """Who owns the authoring tree an embed migrates into."""

    UNOWNED = "unowned"
    CAMPAIGN_OWNED = "campaign_owned"
    MIXED = "mixed"


@dataclass(frozen=True, slots=True, order=True)
class EmbedEvidence:
    """One detected regulatory-literal occurrence inside a derived module."""

    path: str
    enclosing_symbol: str
    kind: EvidenceKind
    symbol: str
    excerpt: str

    @property
    def key(self) -> tuple[str, str, str, str]:
        """Return the line-independent disposition key for this occurrence."""
        return (self.path, self.enclosing_symbol, str(self.kind), self.symbol)

    def render(self) -> str:
        """Return one deterministic diagnostic identity."""
        return f"{self.path}::{self.enclosing_symbol} [{self.kind} {self.symbol}] {self.excerpt}"


@dataclass(frozen=True, slots=True)
class ModeloModuleRecord:
    """One mechanically derived modelo-specific module."""

    path: str
    modelo_codes: tuple[str, ...]
    signals: tuple[DerivationSignal, ...]
    evidence: tuple[EmbedEvidence, ...]

    @property
    def evidence_keys(self) -> frozenset[tuple[str, str, str, str]]:
        """Return the disposition keys every machinery claim must answer."""
        return frozenset(item.key for item in self.evidence)


@dataclass(frozen=True, slots=True)
class ClassificationEntry:
    """One adjudicated classification read from the ledger."""

    path: str
    classification: Classification
    justification: str
    destination: str = ""
    tree_ownership: TreeOwnership | None = None
    evidence_dispositions: tuple[tuple[tuple[str, str, str, str], str], ...] = ()

    @property
    def disposition_map(self) -> Mapping[tuple[str, str, str, str], str]:
        """Return the evidence dispositions keyed by evidence identity."""
        return dict(self.evidence_dispositions)


def modelo_codes() -> frozenset[str]:
    """Return every AEAT modelo code the core enum declares."""
    if str(SOURCE_ROOT.parent) not in sys.path:
        sys.path.insert(0, str(SOURCE_ROOT.parent))
    from cadrumo.core import Modelo

    return frozenset(member.value for member in Modelo)


def _tokens(text: str, codes: frozenset[str]) -> set[str]:
    return {match.group(1) for match in _MODELO_TOKEN.finditer(text) if match.group(1) in codes}


def _iter_package_modules(package_root: Path) -> Iterator[Path]:
    for path in scan_directory(package_root, pattern="*.py", recursive=True, prune_directories=("__pycache__",)):
        if "tests" in path.relative_to(package_root).parts:
            continue
        yield path


def _defined_names(tree: ast.Module) -> Iterator[str]:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    yield target.id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            yield node.target.id


def _modelo_member_codes(tree: ast.Module, codes: frozenset[str]) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if not isinstance(node.value, ast.Name) or node.value.id != "Modelo":
            continue
        attribute = node.attr
        if attribute.startswith("M") and attribute[1:] in codes:
            found.add(attribute[1:])
    return found


def _docstring_nodes(tree: ast.Module) -> set[int]:
    marked: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", [])
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            marked.add(id(body[0].value))
    return marked


def _enclosing_symbols(tree: ast.Module) -> dict[int, str]:
    owner: dict[int, str] = {}

    def walk(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                inner = child.name if scope == _MODULE_SCOPE else f"{scope}.{child.name}"
                owner[id(child)] = inner
                walk(child, inner)
            else:
                owner[id(child)] = scope
                walk(child, scope)

    owner[id(tree)] = _MODULE_SCOPE
    walk(tree, _MODULE_SCOPE)
    return owner


def _assigned_name(tree: ast.Module) -> dict[int, str]:
    named: dict[int, str] = {}
    for node in ast.walk(tree):
        targets: Sequence[ast.expr] = ()
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = (node.target,)
        else:
            continue
        names = [target.id for target in targets if isinstance(target, ast.Name)]
        if not names:
            continue
        for descendant in ast.walk(node):
            named.setdefault(id(descendant), names[0])
    return named


def _is_prose(value: str, symbol: str) -> bool:
    if symbol.upper().endswith(_PROSE_NAME_SUFFIXES):
        return True
    return len(value) >= _PROSE_MIN_LENGTH and any(character in _SPANISH_ORTHOGRAPHY for character in value)


def _excerpt(value: str, limit: int = 72) -> str:
    flattened = " ".join(value.split())
    return flattened if len(flattened) <= limit else f"{flattened[: limit - 1]}…"


def _collect_evidence(tree: ast.Module, relative: str) -> tuple[EmbedEvidence, ...]:
    docstrings = _docstring_nodes(tree)
    scopes = _enclosing_symbols(tree)
    names = _assigned_name(tree)
    found: set[EmbedEvidence] = set()

    def record(node: ast.AST, kind: EvidenceKind, excerpt: str) -> None:
        found.add(
            EmbedEvidence(
                path=relative,
                enclosing_symbol=scopes.get(id(node), _MODULE_SCOPE),
                kind=kind,
                symbol=names.get(id(node), ""),
                excerpt=excerpt,
            )
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Decimal":
            argument = node.args[0] if node.args else None
            if isinstance(argument, ast.Constant) and isinstance(argument.value, (str, int)):
                record(node, EvidenceKind.DECIMAL_LITERAL, f"Decimal({argument.value!r})")
            continue
        if not isinstance(node, ast.Constant) or id(node) in docstrings:
            continue
        if isinstance(node.value, bool):
            continue
        if isinstance(node.value, int) and node.value in _FILING_YEAR_SPAN:
            record(node, EvidenceKind.FILING_YEAR_LITERAL, str(node.value))
        elif isinstance(node.value, str) and _is_prose(node.value, names.get(id(node), "")):
            record(node, EvidenceKind.REGULATORY_PROSE_LITERAL, _excerpt(node.value))
    return tuple(sorted(found))


def census(package_root: Path = REGISTRY_PACKAGE_ROOT) -> tuple[ModeloModuleRecord, ...]:
    """Derive every modelo-specific module under ``package_root``, with evidence."""
    codes = modelo_codes()
    records: list[ModeloModuleRecord] = []
    for path in _iter_package_modules(package_root):
        tree = ast.parse(path.read_text(encoding=_UTF_8))
        by_signal: dict[DerivationSignal, set[str]] = {
            DerivationSignal.MODULE_NAME: _tokens(path.stem, codes),
            DerivationSignal.MODELO_REFERENCE: _modelo_member_codes(tree, codes),
            DerivationSignal.DEFINED_SYMBOL: {code for name in _defined_names(tree) for code in _tokens(name, codes)},
        }
        signals = tuple(signal for signal in DerivationSignal if by_signal[signal])
        if not signals:
            continue
        relative = _repo_relative(path)
        records.append(
            ModeloModuleRecord(
                path=relative,
                modelo_codes=tuple(sorted(set().union(*by_signal.values()))),
                signals=signals,
                evidence=_collect_evidence(tree, relative),
            )
        )
    return tuple(records)


@cache
def importer_index(source_root: Path = SOURCE_ROOT) -> Mapping[str, tuple[str, ...]]:
    """Return, per module stem, every module under ``source_root`` that imports it."""
    index: dict[str, list[str]] = {}
    for path in scan_directory(source_root, pattern="*.py", recursive=True, prune_directories=("__pycache__",)):
        try:
            body = path.read_text(encoding=_UTF_8)
        except FileNotFoundError:
            # The tree is walked live and peers create and remove scratch modules
            # under it; a file that vanishes between listing and reading imports
            # nothing.
            continue
        relative = _repo_relative(path)
        for stem in _imported_stems(ast.parse(body)):
            index.setdefault(stem, []).append(relative)
    return {stem: tuple(paths) for stem, paths in index.items()}


def _repo_relative(path: Path) -> str:
    """Return the repo-relative posix path, or the absolute one when outside it."""
    if path.is_relative_to(REPO_ROOT):
        return path.relative_to(REPO_ROOT).as_posix()
    return path.as_posix()


def importers_of(relative_path: str, source_root: Path = SOURCE_ROOT) -> tuple[str, ...]:
    """Return every module under ``source_root`` whose import graph names this module."""
    stem = Path(relative_path).stem
    return tuple(path for path in importer_index(source_root).get(stem, ()) if path != relative_path)


def _imported_stems(tree: ast.Module) -> set[str]:
    stems: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module is not None:
                stems.add(node.module.split(".")[-1])
            stems.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            stems.update(alias.name.split(".")[-1] for alias in node.names)
    return stems


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ClassificationLedgerError(message)


def _entry_from_row(row: Mapping[str, object]) -> ClassificationEntry:
    path = row.get("path")
    _require(isinstance(path, str) and bool(path), f"ledger row without a path: {row!r}")
    assert isinstance(path, str)
    raw_classification = row.get("classification")
    _require(
        isinstance(raw_classification, str) and raw_classification in set(Classification),
        f"{path}: classification must be one of {sorted(Classification)}",
    )
    assert isinstance(raw_classification, str)
    justification = row.get("justification", "")
    _require(isinstance(justification, str), f"{path}: justification must be a string")
    assert isinstance(justification, str)
    ownership_value = row.get("tree_ownership")
    ownership: TreeOwnership | None = None
    if ownership_value is not None:
        _require(
            isinstance(ownership_value, str) and ownership_value in set(TreeOwnership),
            f"{path}: tree_ownership must be one of {sorted(TreeOwnership)}",
        )
        assert isinstance(ownership_value, str)
        ownership = TreeOwnership(ownership_value)
    destination = row.get("destination", "")
    _require(isinstance(destination, str), f"{path}: destination must be a string")
    assert isinstance(destination, str)
    dispositions: list[tuple[tuple[str, str, str, str], str]] = []
    for raw in row.get("evidence_disposition", ()) or ():
        _require(isinstance(raw, Mapping), f"{path}: evidence_disposition rows must be tables")
        assert isinstance(raw, Mapping)
        symbol = raw.get("symbol", "")
        enclosing = raw.get("enclosing_symbol")
        kind = raw.get("kind")
        reason = raw.get("reason", "")
        _require(
            isinstance(enclosing, str) and isinstance(kind, str) and isinstance(symbol, str),
            f"{path}: evidence_disposition needs enclosing_symbol, kind and symbol",
        )
        assert isinstance(enclosing, str) and isinstance(kind, str) and isinstance(symbol, str)
        _require(isinstance(reason, str) and bool(reason.strip()), f"{path}: evidence_disposition needs a reason")
        assert isinstance(reason, str)
        dispositions.append(((path, enclosing, kind, symbol), reason))
    return ClassificationEntry(
        path=path,
        classification=Classification(raw_classification),
        justification=justification,
        destination=destination,
        tree_ownership=ownership,
        evidence_dispositions=tuple(dispositions),
    )


def load_ledger(ledger_path: Path = LEDGER_PATH) -> tuple[ClassificationEntry, ...]:
    """Read and structurally validate the checked-in adjudication ledger."""
    payload = tomllib.loads(ledger_path.read_text(encoding=_UTF_8))
    meta = payload.get("meta", {})
    _require(isinstance(meta, Mapping), "ledger [meta] must be a table")
    assert isinstance(meta, Mapping)
    _require(
        meta.get("schema_version") == _SCHEMA_VERSION,
        f"ledger schema_version must be {_SCHEMA_VERSION}",
    )
    rows = payload.get("classification", ())
    _require(isinstance(rows, list), "ledger [[classification]] must be an array of tables")
    assert isinstance(rows, list)
    entries = tuple(_entry_from_row(row) for row in rows)
    seen: set[str] = set()
    for entry in entries:
        _require(entry.path not in seen, f"{entry.path}: classified more than once")
        seen.add(entry.path)
    return entries


def reconcile(
    records: Sequence[ModeloModuleRecord],
    entries: Sequence[ClassificationEntry],
    *,
    source_root: Path = SOURCE_ROOT,
) -> tuple[str, ...]:
    """Return every reconciliation failure between the derived set and the ledger."""
    failures: list[str] = []
    by_path = {entry.path: entry for entry in entries}
    derived = {record.path: record for record in records}

    for path in sorted(derived):
        if path not in by_path:
            record = derived[path]
            signals = ", ".join(str(signal) for signal in record.signals)
            failures.append(
                f"{path}: modelo-specific (modelos {', '.join(record.modelo_codes)}; signals {signals}) "
                "but carries no classification"
            )
    for path in sorted(by_path):
        if path not in derived:
            failures.append(f"{path}: classified but no longer derived as modelo-specific")

    for path in sorted(set(by_path) & set(derived)):
        failures.extend(_reconcile_one(derived[path], by_path[path], source_root=source_root))
    return tuple(failures)


def _reconcile_one(
    record: ModeloModuleRecord,
    entry: ClassificationEntry,
    *,
    source_root: Path,
) -> Iterable[str]:
    path = record.path
    if not entry.justification.strip():
        yield f"{path}: classification {entry.classification} carries no justification"

    if entry.classification is Classification.REGULATORY_DATA_EMBED:
        if not entry.destination.strip():
            yield f"{path}: a regulatory data embed must name its destination"
        yield from _ownership_failures(record, entry)
    elif entry.destination.strip() or entry.tree_ownership is not None:
        yield f"{path}: only a regulatory data embed declares a destination or tree_ownership"

    if entry.classification is Classification.MACHINERY:
        dispositions = entry.disposition_map
        for evidence in record.evidence:
            if evidence.key not in dispositions:
                yield (
                    f"{path}: machinery claim leaves regulatory-literal evidence undispositioned -- {evidence.render()}"
                )
        for key in sorted(set(dispositions) - record.evidence_keys):
            yield f"{path}: evidence_disposition {key[1]}/{key[2]}/{key[3]} matches no detected evidence"
    elif entry.evidence_dispositions:
        yield f"{path}: only a machinery classification carries evidence_disposition rows"

    if entry.classification is Classification.DEAD:
        importers = importers_of(path, source_root=source_root)
        if importers:
            yield f"{path}: classified dead but imported by {', '.join(importers)}"


def _ownership_failures(record: ModeloModuleRecord, entry: ClassificationEntry) -> Iterable[str]:
    """Refuse an embed whose queue declaration contradicts its derived modelo set."""
    path = record.path
    owned = set(record.modelo_codes) & CAMPAIGN_OWNED_MODELO_CODES
    unowned = set(record.modelo_codes) - CAMPAIGN_OWNED_MODELO_CODES
    codes = ", ".join(record.modelo_codes)
    match entry.tree_ownership:
        case None:
            yield f"{path}: a regulatory data embed must declare tree_ownership"
        case TreeOwnership.CAMPAIGN_OWNED if not owned:
            yield f"{path}: queued as campaign_owned but its modelos ({codes}) are not campaign-owned"
        case TreeOwnership.UNOWNED if owned:
            yield f"{path}: declared unowned but its modelos ({codes}) reach a campaign-owned tree"
        case TreeOwnership.MIXED if not (owned and unowned):
            yield f"{path}: declared mixed but its modelos ({codes}) fall in one ownership only"
        case _:
            return


def render_ledger(records: Sequence[ModeloModuleRecord]) -> str:
    """Return a ledger scaffold carrying every derived module and its evidence."""
    lines = [
        "# Adjudication ledger for the derived modelo-specific registry module set.",
        "# The set is derived mechanically; only the classification and its prose are authored.",
        "",
        "[meta]",
        f"schema_version = {_SCHEMA_VERSION}",
        "",
    ]
    for record in records:
        lines.append("[[classification]]")
        lines.append(f'path = "{record.path}"')
        lines.append(f"modelo_codes = {json.dumps(list(record.modelo_codes))}")
        lines.append(f"signals = {json.dumps([str(signal) for signal in record.signals])}")
        lines.append('classification = ""')
        lines.append('justification = ""')
        for evidence in record.evidence:
            lines.append("")
            lines.append("[[classification.evidence_disposition]]")
            lines.append(f'enclosing_symbol = "{evidence.enclosing_symbol}"')
            lines.append(f'kind = "{evidence.kind}"')
            lines.append(f'symbol = "{evidence.symbol}"')
            lines.append('reason = ""')
        lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the classifier over the registry package."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--package-root", type=Path, default=REGISTRY_PACKAGE_ROOT)
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    parser.add_argument("--json", action="store_true", help="emit the derived census as JSON")
    parser.add_argument("--scaffold", action="store_true", help="emit a ledger scaffold and exit")
    parser.add_argument("--check", action="store_true", help="reconcile and exit non-zero on any failure")
    args = parser.parse_args(argv)

    records = census(args.package_root)
    if args.scaffold:
        sys.stdout.write(render_ledger(records))
        return 0
    if args.json:
        payload = [
            {
                "path": record.path,
                "modelo_codes": list(record.modelo_codes),
                "signals": [str(signal) for signal in record.signals],
                "evidence": [
                    {
                        "enclosing_symbol": item.enclosing_symbol,
                        "kind": str(item.kind),
                        "symbol": item.symbol,
                        "excerpt": item.excerpt,
                    }
                    for item in record.evidence
                ],
            }
            for record in records
        ]
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
        sys.stdout.write("\n")
        return 0

    failures = reconcile(records, load_ledger(args.ledger))
    for failure in failures:
        sys.stdout.write(f"{failure}\n")
    sys.stdout.write(f"{len(records)} modelo-specific modules derived; {len(failures)} reconciliation failures\n")
    return 1 if (failures and args.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
