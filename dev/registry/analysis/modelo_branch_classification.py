"""Derive every modelo-conditional branch outside the registry and force one classification.

The registry package owns per-modelo regulatory data by design. OUTSIDE it, a
branch that asks "which modelo is this?" is one of exactly two things, and the
difference matters:

``orchestration_routing``
    The branch selects a collaborator, a code path, a payload shape or a
    surface. It encodes no rule the law fixes; it routes. Moving it into the
    registry would put orchestration in a data tree.

``regulatory_treatment``
    The branch encodes a rule the law fixes for that modelo -- a rate, a
    threshold, an eligibility condition, an ejercicio boundary, an
    obligation. It is a registry embed wearing an ``if``, and it belongs in
    the authoring tree.

Left unadjudicated the two are indistinguishable by inspection, which is how a
regulatory rule survives outside the registry: it looks like routing. So the
SET is derived mechanically here and the classification is authored in the
ledger beside this file. What the ledger cannot do is stay silent.

Derivation keys on :class:`cadrumo.core.modelo.Modelo`, so adding a modelo to the enum
widens the detector with no edit here. A branch is any ``if``/``elif`` test or
``match`` subject/pattern that reads a concrete ``Modelo.M###`` member, in a
module under ``src/cadrumo`` that is neither inside the registry package (which
owns this data legitimately) nor a test.

Sites are keyed by ``(module, enclosing symbol, modelo codes)`` rather than by
line number: a line number goes stale on the next edit above it, and an
allowlist keyed on a stale locator silently stops matching the thing it
exempted.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from cadrumo.core.toml import read_toml

from ...quality.unread_inputs import report_unread

PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "src" / "cadrumo"
REGISTRY_PACKAGE_ROOT = PACKAGE_ROOT / "domain" / "calculations" / "registry"
LEDGER_PATH = Path(__file__).with_name("modelo_branch_classification.toml")


class BranchLedgerError(RuntimeError):
    """The derived branch set and the adjudication ledger disagree."""


class BranchClassification(StrEnum):
    """The adjudicated nature of one modelo-conditional branch."""

    ORCHESTRATION_ROUTING = "orchestration_routing"
    REGULATORY_TREATMENT = "regulatory_treatment"


@dataclass(frozen=True, slots=True, order=True)
class BranchSite:
    """One derived modelo-conditional branch, keyed stably."""

    module: str
    symbol: str
    modelo_codes: tuple[str, ...]

    @property
    def key(self) -> str:
        """Return the ledger key for this site."""
        return f"{self.module}::{self.symbol}::{','.join(self.modelo_codes)}"


@dataclass(frozen=True, slots=True)
class BranchAdjudication:
    """One authored ledger row."""

    key: str
    classification: BranchClassification
    justification: str


def modelo_codes() -> frozenset[str]:
    """Return every modelo code the core enum declares."""
    from cadrumo.core.modelo import Modelo

    return frozenset(member.value for member in Modelo)


def _enclosing_symbols(tree: ast.Module) -> dict[int, str]:
    """Map every line to the nearest enclosing def/class name."""
    spans: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            spans.append((node.lineno, node.end_lineno or node.lineno, node.name))
    spans.sort(key=lambda item: item[1] - item[0])
    mapping: dict[int, str] = {}
    for start, end, name in spans:
        for line in range(start, end + 1):
            mapping.setdefault(line, name)
    return mapping


def _referenced_modelo_members(node: ast.AST) -> set[str]:
    """Return every ``Modelo.M###`` attribute name read anywhere under ``node``."""
    found: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name) and child.value.id == "Modelo":
            found.add(child.attr)
    return found


def _iter_candidate_modules() -> Iterator[Path]:
    """Yield every production module outside the registry package."""
    registry = REGISTRY_PACKAGE_ROOT.resolve()
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        resolved = path.resolve()
        if resolved.is_relative_to(registry):
            continue
        if "tests" in path.parts or path.name == "conftest.py":
            continue
        yield path


def derive_branch_sites() -> tuple[BranchSite, ...]:
    """Derive every modelo-conditional branch outside the registry package.

    Returns:
        The derived sites, sorted and deduplicated on their stable key.
    """
    sites: set[BranchSite] = set()
    unread: list[str] = []
    for path in _iter_candidate_modules():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as error:
            unread.append(f"{path}: {type(error).__name__}: {error}")
            continue
        symbols = _enclosing_symbols(tree)
        module = path.relative_to(PACKAGE_ROOT.parent.parent).as_posix()
        for node in ast.walk(tree):
            members: set[str] = set()
            if isinstance(node, ast.If):
                members = _referenced_modelo_members(node.test)
            elif isinstance(node, ast.Match):
                members = _referenced_modelo_members(node.subject)
                for case in node.cases:
                    members |= _referenced_modelo_members(case.pattern)
            if not members:
                continue
            sites.add(
                BranchSite(
                    module=module,
                    symbol=symbols.get(node.lineno, "<module>"),
                    modelo_codes=tuple(sorted(members)),
                ),
            )
    report_unread(
        "modelo branch classification",
        "a branch on modelo identity inside one of them is absent from these sites",
        unread,
    )
    return tuple(sorted(sites))


def load_ledger(path: Path | None = None) -> dict[str, BranchAdjudication]:
    """Load the authored adjudication ledger.

    Raises:
        BranchLedgerError: When a row omits a field or names an unknown
            classification.
    """
    target = path if path is not None else LEDGER_PATH
    if not target.exists():
        return {}
    raw = read_toml(target, error_factory=BranchLedgerError)
    rows: dict[str, BranchAdjudication] = {}
    for entry in raw.get("branch", []):
        key = entry.get("key")
        classification = entry.get("classification")
        justification = entry.get("justification", "")
        if not key or not classification:
            message = f"{target}: every branch row needs a key and a classification"
            raise BranchLedgerError(message)
        if classification not in set(BranchClassification):
            message = f"{target}: {key!r} declares unknown classification {classification!r}"
            raise BranchLedgerError(message)
        if not justification.strip():
            message = f"{target}: {key!r} carries no justification; a silent adjudication proves nothing"
            raise BranchLedgerError(message)
        rows[key] = BranchAdjudication(
            key=key,
            classification=BranchClassification(classification),
            justification=justification,
        )
    return rows


def reconcile(
    sites: tuple[BranchSite, ...] | None = None,
    ledger: dict[str, BranchAdjudication] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Reconcile the derived branch set against the ledger.

    Returns:
        ``(unclassified, stale)`` -- derived keys the ledger does not name, and
        ledger keys the derivation no longer yields.
    """
    derived = sites if sites is not None else derive_branch_sites()
    rows = ledger if ledger is not None else load_ledger()
    derived_keys = {site.key for site in derived}
    unclassified = tuple(sorted(derived_keys - set(rows)))
    stale = tuple(sorted(set(rows) - derived_keys))
    return unclassified, stale


__all__ = [
    "LEDGER_PATH",
    "BranchAdjudication",
    "BranchClassification",
    "BranchLedgerError",
    "BranchSite",
    "derive_branch_sites",
    "load_ledger",
    "modelo_codes",
    "reconcile",
]
