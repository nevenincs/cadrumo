"""Derive regulatory-literal embeds in modelo-specific registry modules.

The registry package mixes generic compiler machinery with modules scoped to a
single AEAT modelo. This module derives that module set mechanically and emits
every embedded rate, ejercicio, and operator-facing prose literal. The expected
set is empty: findings must move to their owning registry or locale authority.

Derivation uses three independent signals, all keyed on
:class:`cadrumo.core.modelo.Modelo` so that adding a modelo to the enum widens the
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

"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT, UTF_8
from ...quality.unread_inputs import report_unread

SOURCE_ROOT: Final[Path] = REPO_ROOT / "src" / "cadrumo"
REGISTRY_PACKAGE_ROOT: Final[Path] = SOURCE_ROOT / "domain" / "calculations" / "registry"
__all__ = [
    "REGISTRY_PACKAGE_ROOT",
    "REPO_ROOT",
    "SOURCE_ROOT",
    "DerivationSignal",
    "EmbedEvidence",
    "EvidenceKind",
    "ModeloModuleRecord",
    "census",
    "modelo_codes",
]

_UTF_8: Final[str] = UTF_8
_MODULE_SCOPE: Final[str] = "<module>"

#: A four-digit integer in this span reads as an AEAT ejercicio / filing year
#: rather than as an arithmetic constant.  The span is deliberately wider than
#: the corpus so a forward-dated regulatory year is still evidence.
_FILING_YEAR_SPAN: Final[range] = range(1960, 2101)

#: Constant-name suffixes that mark a string literal as operator-facing prose,
#: whose home is the locale catalogues rather than a Python module.
_PROSE_NAME_SUFFIXES: Final[tuple[str, ...]] = (
    "_ARTICLE",
    "_REASON",
    "_RULES",
    "_SECTION",
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


def modelo_codes() -> frozenset[str]:
    """Return every AEAT modelo code the core enum declares."""
    if str(SOURCE_ROOT.parent) not in sys.path:
        sys.path.insert(0, str(SOURCE_ROOT.parent))
    from cadrumo.core.modelo import Modelo

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
        for index, item in enumerate(body):
            if not isinstance(item, ast.Expr) or not isinstance(item.value, ast.Constant):
                continue
            if index == 0 or isinstance(body[index - 1], (ast.Assign, ast.AnnAssign)):
                marked.add(id(item.value))
    return marked


def _parents(tree: ast.Module) -> dict[int, ast.AST]:
    """Return the immediate parent of every node in ``tree``."""
    return {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}


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
    return (
        symbol.upper().endswith(_PROSE_NAME_SUFFIXES)
        and len(value) >= _PROSE_MIN_LENGTH
        and any(character in _SPANISH_ORTHOGRAPHY for character in value)
    )


def _semantic_name(node: ast.AST, names: dict[int, str], parents: dict[int, ast.AST]) -> str:
    """Return the assignment or keyword role that gives a literal meaning."""
    assigned = names.get(id(node), "")
    if assigned:
        return assigned
    parent = parents.get(id(node))
    return parent.arg if isinstance(parent, ast.keyword) and parent.arg is not None else ""


def _is_non_policy_decimal(call: ast.Call, argument: ast.Constant, parents: dict[int, ast.AST]) -> bool:
    """Recognise algebraic identities and percentage-unit conversions structurally."""
    token = str(argument.value).strip()
    try:
        numeric = float(token)
    except ValueError:
        return False
    if numeric in {0.0, 1.0}:
        return True
    ancestor = parents.get(id(call))
    while ancestor is not None and not isinstance(ancestor, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        ancestor = parents.get(id(ancestor))
    if isinstance(ancestor, ast.ClassDef):
        return True
    parent = parents.get(id(call))
    if numeric == 100.0 and (
        isinstance(parent, ast.Compare) or (isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Div))
    ):
        return True
    return numeric in {365.0, 366.0} and isinstance(parent, ast.Compare)


def _excerpt(value: str, limit: int = 72) -> str:
    flattened = " ".join(value.split())
    return flattened if len(flattened) <= limit else f"{flattened[: limit - 1]}…"


def _collect_evidence(tree: ast.Module, relative: str) -> tuple[EmbedEvidence, ...]:
    docstrings = _docstring_nodes(tree)
    scopes = _enclosing_symbols(tree)
    names = _assigned_name(tree)
    parents = _parents(tree)
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
            if (
                isinstance(argument, ast.Constant)
                and isinstance(argument.value, (str, int))
                and not _is_non_policy_decimal(node, argument, parents)
            ):
                record(node, EvidenceKind.DECIMAL_LITERAL, f"Decimal({argument.value!r})")
            continue
        if not isinstance(node, ast.Constant) or id(node) in docstrings:
            continue
        if isinstance(node.value, bool):
            continue
        symbol = _semantic_name(node, names, parents)
        if (
            isinstance(node.value, int)
            and node.value in _FILING_YEAR_SPAN
            and scopes.get(id(node), _MODULE_SCOPE) == _MODULE_SCOPE
        ):
            record(node, EvidenceKind.FILING_YEAR_LITERAL, str(node.value))
        elif isinstance(node.value, str) and _is_prose(node.value, symbol):
            record(node, EvidenceKind.REGULATORY_PROSE_LITERAL, _excerpt(node.value))
    return tuple(sorted(found))


def census(package_root: Path = REGISTRY_PACKAGE_ROOT) -> tuple[ModeloModuleRecord, ...]:
    """Derive every modelo-specific module under ``package_root``, with evidence."""
    codes = modelo_codes()
    records: list[ModeloModuleRecord] = []
    unread: list[str] = []
    for path in _iter_package_modules(package_root):
        try:
            tree = ast.parse(path.read_text(encoding=_UTF_8))
        except FileNotFoundError:
            # The tree is walked live and peers create and remove scratch modules
            # under it; a file that vanishes between listing and reading carries
            # no evidence for this census to derive.
            continue
        except (SyntaxError, UnicodeDecodeError) as error:
            # The same race, one step earlier: a peer mid-write leaves a module
            # that exists but does not parse. Parsing sat outside the guard, so
            # that far likelier case killed the whole census instead of costing
            # one file's evidence.
            unread.append(f"{path}: {type(error).__name__}: {error}")
            continue
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
    report_unread(
        "modelo embed census",
        "a modelo-specific module hiding regulatory-literal evidence is absent from this census",
        unread,
    )
    return tuple(records)


def _repo_relative(path: Path) -> str:
    """Return the repo-relative posix path, or the absolute one when outside it."""
    if path.is_relative_to(REPO_ROOT):
        return path.relative_to(REPO_ROOT).as_posix()
    return path.as_posix()


def main(argv: Sequence[str] | None = None) -> int:
    """Print every current embed and exit non-zero until the set is empty."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--package-root", type=Path, default=REGISTRY_PACKAGE_ROOT)
    parser.add_argument("--json", action="store_true", help="emit the derived census as JSON")
    args = parser.parse_args(argv)

    records = census(args.package_root)
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

    evidence = tuple(item for record in records for item in record.evidence)
    for item in evidence:
        sys.stdout.write(f"{item.render()}\n")
    sys.stdout.write(f"{len(evidence)} modelo-specific regulatory embed(s); expected zero\n")
    return 1 if evidence else 0


if __name__ == "__main__":
    raise SystemExit(main())
