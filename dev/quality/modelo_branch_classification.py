"""Classify every modelo-conditional branch outside the registry package.

The drift census derives WHERE behaviour is conditioned on a concrete ``Modelo``
member; this module forces exactly one adjudication per site on the axis that
matters: is the branch selecting a code path, or is it deciding a regulatory
outcome?

Routing a workflow by modelo is legitimate application logic -- a modelo has its
own CLI surface, its own repository projection, its own import shape. Deciding a
modelo's regulatory treatment in a Python branch is not: which base a category
feeds, which casilla receives a value, which reduction applies are facts the
registry declares. Nothing in the syntax separates them, which is exactly why
this file exists and why the derivation is kept apart from the judgement.

The derived set is the census's, not a second walk. Two censuses deriving the
same population from the same tree would drift apart, and the plan row is
explicit that the set already exists and only the adjudication is missing.

**How a claim is kept honest.** The sibling embed classifier makes a machinery
claim answerable by requiring it to dispose of every regulatory literal detected
in the same module. That mechanism does not transplant here, and the measurement
says so: of the branch sites in this derived set, almost none carries a
regulatory literal inside the guarded body, because a branch body mostly *calls*
things rather than *containing* values. A disposal rule built on it would report
clean because nothing could reach it -- the unproven-gate failure the quality
rules name -- and the few times it did fire it fired on false matches like
``ImportError`` containing the substring ``importe``.

So the honesty mechanism here is a **falsifiable citation**. An
``orchestration_routing`` claim must name, in ``selects``, a token that actually
appears inside the guarded branch at HEAD; the gate verifies it. An author who
cannot point at what the branch selects has not established that it selects
anything, and a rename that invalidates the citation reds the gate instead of
silently outliving it. A ``regulatory_treatment`` claim carries no citation
because it is not the claim being doubted -- it must instead name the plan row
or record that answers it.

What this cannot decide, stated rather than assumed away:

- **Whether a selected code path is itself regulatory.** A branch that picks a
  service whose body encodes a rate is orchestration by this instrument and
  regulatory by intent; only reading the selected code settles it.
- **Branches on a modelo value that never names the enum**, reached through a
  variable holding a modelo string. The census's detector keys on ``Modelo``
  members, so those are invisible to both instruments.
"""

from __future__ import annotations

import argparse
import ast
import json
import tomllib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from .regulatory_drift_census import REPO_ROOT, FindingKind, census

LEDGER_PATH: Final[Path] = Path(__file__).with_name("modelo_branch_classification.toml")

#: Branches inside the registry package are adjudicated by the modelo-specific
#: embed classifier, which derives the same sites from its own signals. Excluded
#: here so one site is never answered by two ledgers that can disagree.
REGISTRY_PACKAGE_PREFIX: Final[str] = "src/cadrumo/domain/calculations/registry/"

MODULE_SCOPE: Final[str] = "<module>"

#: Tokens that appear in every modelo test and therefore prove nothing when
#: cited. Excluded from the citable set so a citation must name something the
#: branch reaches, not the condition it branches on.
_VACUOUS_CITATIONS: Final[frozenset[str]] = frozenset({"Modelo", "value", "modelo", "id", "str", "getattr"})


class BranchClassificationError(RuntimeError):
    """Raised when the ledger cannot be reconciled with the derived branch set."""


class BranchClassification(StrEnum):
    """The closed adjudication vocabulary; every derived branch carries one."""

    #: The branch selects which code runs -- a surface, a projection, an import
    #: shape. Must cite the token it selects.
    ORCHESTRATION_ROUTING = "orchestration_routing"
    #: The branch decides a regulatory outcome the registry should declare.
    #: Must name the plan row or record that answers it.
    REGULATORY_TREATMENT = "regulatory_treatment"


@dataclass(frozen=True, slots=True, order=True)
class BranchSite:
    """One modelo-conditional branch, identified without a line number."""

    path: str
    enclosing_symbol: str
    modelo_codes: str

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the ledger key for this site.

        Returns:
            Path, enclosing symbol and the comma-joined modelo codes.
        """
        return (self.path, self.enclosing_symbol, self.modelo_codes)

    def render(self) -> str:
        """Return one deterministic diagnostic identity.

        Returns:
            A single-line rendering.
        """
        return f"{self.path}::{self.enclosing_symbol} [{self.modelo_codes}]"


@dataclass(frozen=True, slots=True)
class BranchGroup:
    """A reasoning shared by many branches, authored once and referenced by id.

    The per-site ``selects`` citation is never shared: it is the part of the
    claim that has to be specific, and a shared citation would be a shared
    assertion about different code.
    """

    identifier: str
    classification: BranchClassification
    justification: str
    row: str = ""
    reference: str = ""


@dataclass(frozen=True, slots=True)
class BranchEntry:
    """One adjudicated branch read from the ledger."""

    key: tuple[str, str, str]
    classification: BranchClassification
    justification: str
    selects: str = ""
    row: str = ""
    reference: str = ""
    group: str = ""


def _load_groups(document: Mapping[str, object]) -> Mapping[str, BranchGroup]:
    rows = document.get("group", [])
    if not isinstance(rows, list):
        raise BranchClassificationError("the ledger's [[group]] section must be an array of tables")
    groups: dict[str, BranchGroup] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise BranchClassificationError(f"malformed group {row!r}")
        try:
            identifier = str(row["id"])
            classification = BranchClassification(str(row["classification"]))
            justification = str(row["justification"]).strip()
        except (KeyError, ValueError) as error:
            raise BranchClassificationError(f"malformed group {row!r}: {error}") from error
        if identifier in groups:
            raise BranchClassificationError(f"group {identifier!r} is declared twice")
        groups[identifier] = BranchGroup(
            identifier,
            classification,
            justification,
            str(row.get("row", "")).strip(),
            str(row.get("reference", "")).strip(),
        )
    return groups


def derived_branch_sites() -> tuple[BranchSite, ...]:
    """Return every modelo-conditional branch the census finds outside the registry package.

    Returns:
        The derived set, sorted, deduplicated by key.
    """
    sites = {
        BranchSite(finding.path, finding.enclosing_symbol, finding.detail)
        for finding in census()
        if finding.kind is FindingKind.MODELO_CONDITIONAL_BRANCH
        and not finding.path.startswith(REGISTRY_PACKAGE_PREFIX)
    }
    return tuple(sorted(sites))


def _enclosing_symbols(tree: ast.Module) -> dict[int, str]:
    symbols: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            for child in ast.walk(node):
                symbols[id(child)] = node.name
    return symbols


def _modelo_members(node: ast.AST) -> set[str]:
    found: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name) and child.value.id == "Modelo":
            found.add(child.attr)
    return found


def _guarded_regions(tree: ast.Module) -> Iterator[tuple[str, ast.AST]]:
    """Yield the enclosing symbol and the guarded subtree for every modelo branch.

    An ``if`` or ``match`` case yields its own node, so the region is the guarded
    block. Any other shape -- a ternary, a comprehension filter, a boolean
    expression, an assertion -- yields the nearest enclosing statement, because
    that is the smallest subtree that certainly contains whatever the branch
    controls. Falling back rather than skipping is what keeps every census
    finding citable.
    """
    symbols = _enclosing_symbols(tree)
    statement_of: dict[int, ast.stmt] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt):
            for child in ast.walk(node):
                statement_of.setdefault(id(child), node)
    for node in ast.walk(tree):
        guarded_block = (isinstance(node, ast.If) and _modelo_members(node.test)) or (
            isinstance(node, ast.match_case) and _modelo_members(node.pattern)
        )
        if guarded_block:
            yield symbols.get(id(node), MODULE_SCOPE), node
        elif isinstance(node, ast.Compare) and _modelo_members(node):
            statement = statement_of.get(id(node))
            if statement is not None and not isinstance(statement, ast.If):
                yield symbols.get(id(node), MODULE_SCOPE), statement


def citable_tokens(path: str) -> Mapping[str, frozenset[str]]:
    """Return, per enclosing symbol, every token appearing inside a guarded branch.

    Args:
        path: A repository-relative POSIX path.

    Returns:
        Enclosing symbol to the set of names, attributes, call targets and string
        constants a citation may point at.
    """
    source = (REPO_ROOT / path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    tokens: dict[str, set[str]] = {}
    for symbol, region in _guarded_regions(tree):
        bucket = tokens.setdefault(symbol, set())
        # The guarded symbol's own name is citable. Most branches in this set are
        # scope guards on a function named for one modelo, and what such a branch
        # selects IS that scope; citing the function makes the claim falsifiable,
        # because renaming it to something modelo-neutral breaks the citation and
        # forces the claim to be made again.
        bucket.add(symbol)
        for child in ast.walk(region):
            if isinstance(child, ast.Name):
                bucket.add(child.id)
            elif isinstance(child, ast.Attribute):
                bucket.add(child.attr)
            elif isinstance(child, ast.Constant) and isinstance(child.value, str):
                bucket.add(child.value)
    return {symbol: frozenset(names) - _VACUOUS_CITATIONS for symbol, names in tokens.items()}


def load_ledger(path: Path = LEDGER_PATH) -> tuple[BranchEntry, ...]:
    """Read the checked-in adjudication ledger.

    Args:
        path: The ledger file.

    Returns:
        One entry per adjudicated branch.

    Raises:
        BranchClassificationError: If the ledger is missing or malformed, an
            entry carries no justification, an orchestration claim cites
            nothing, a regulatory-treatment claim names neither a plan row nor a
            reference, or a key is adjudicated twice.
    """
    if not path.is_file():
        raise BranchClassificationError(f"branch ledger not found at {path}")
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    groups = _load_groups(document)
    rows = document.get("branch", [])
    if not isinstance(rows, list):
        raise BranchClassificationError("the ledger's [[branch]] section must be an array of tables")
    entries: list[BranchEntry] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise BranchClassificationError(f"malformed ledger row {row!r}")
        try:
            key = (str(row["path"]), str(row["enclosing_symbol"]), str(row["modelo_codes"]))
        except KeyError as error:
            raise BranchClassificationError(f"malformed ledger row {row!r}: {error}") from error
        selects = str(row.get("selects", "")).strip()
        group_id = str(row.get("group", "")).strip()
        if group_id:
            group = groups.get(group_id)
            if group is None:
                raise BranchClassificationError(f"{key} names unknown group {group_id!r}")
            classification, justification = group.classification, group.justification
            plan_row, reference = group.row, group.reference
        else:
            try:
                classification = BranchClassification(str(row["classification"]))
            except (KeyError, ValueError) as error:
                raise BranchClassificationError(f"malformed ledger row {key}: {error}") from error
            justification = str(row.get("justification", "")).strip()
            plan_row = str(row.get("row", "")).strip()
            reference = str(row.get("reference", "")).strip()
        if not justification:
            raise BranchClassificationError(f"{key} carries no justification")
        if classification is BranchClassification.ORCHESTRATION_ROUTING and not selects:
            raise BranchClassificationError(
                f"{key} claims orchestration routing but cites nothing it selects; "
                "an author who cannot point at what the branch selects has not shown that it selects anything"
            )
        if classification is BranchClassification.REGULATORY_TREATMENT and not (plan_row or reference):
            raise BranchClassificationError(f"{key} claims regulatory treatment but names no plan row or reference")
        if classification is BranchClassification.REGULATORY_TREATMENT and selects:
            raise BranchClassificationError(f"{key} is not an orchestration claim and must not cite a selection")
        if key in seen:
            raise BranchClassificationError(f"{key} is adjudicated twice")
        seen.add(key)
        entries.append(BranchEntry(key, classification, justification, selects, plan_row, reference, group_id))
    referenced = {entry.group for entry in entries if entry.group}
    orphaned = sorted(set(groups) - referenced)
    if orphaned:
        raise BranchClassificationError(f"groups {orphaned} are declared but referenced by no branch")
    return tuple(entries)


@dataclass(frozen=True)
class BranchReport:
    """One reconciliation of the derived branch set against the ledger."""

    sites: tuple[BranchSite, ...]
    unclassified: tuple[BranchSite, ...]
    stale: tuple[tuple[str, str, str], ...]
    broken_citations: tuple[str, ...]

    @property
    def clean(self) -> bool:
        """Whether every branch is adjudicated and every citation still holds.

        Returns:
            ``True`` when all three residues are empty.
        """
        return not (self.unclassified or self.stale or self.broken_citations)


def reconcile(ledger: Path = LEDGER_PATH) -> BranchReport:
    """Derive the branch set and reconcile it against the ledger.

    Args:
        ledger: The adjudication ledger.

    Returns:
        The derived sites, the unadjudicated residue, ledger rows matching no
        live branch, and orchestration citations that no longer appear inside
        their guarded branch.
    """
    sites = derived_branch_sites()
    entries = load_ledger(ledger)
    by_key = {entry.key: entry for entry in entries}
    live = {site.key for site in sites}
    broken: list[str] = []
    token_cache: dict[str, Mapping[str, frozenset[str]]] = {}
    for site in sites:
        entry = by_key.get(site.key)
        if entry is None or entry.classification is not BranchClassification.ORCHESTRATION_ROUTING:
            continue
        if site.path not in token_cache:
            token_cache[site.path] = citable_tokens(site.path)
        available = token_cache[site.path].get(site.enclosing_symbol, frozenset())
        if entry.selects not in available:
            broken.append(f"{site.render()} cites {entry.selects!r}, which no longer appears inside the branch")
    return BranchReport(
        sites=sites,
        unclassified=tuple(site for site in sites if site.key not in by_key),
        stale=tuple(sorted(key for key in by_key if key not in live)),
        broken_citations=tuple(sorted(broken)),
    )


def render_ledger(sites: Sequence[BranchSite]) -> str:
    """Render an unadjudicated ledger scaffold for the derived sites.

    Every row is emitted without a classification, because a generator that
    guessed one would assert a judgement nobody made.

    Returns:
        TOML text.
    """
    lines = ["[meta]", "schema_version = 1", ""]
    for site in sites:
        lines.extend(
            [
                "[[branch]]",
                f'path = "{site.path}"',
                f'enclosing_symbol = "{site.enclosing_symbol}"',
                f'modelo_codes = "{site.modelo_codes}"',
                'classification = ""',
                'justification = ""',
                "",
            ]
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Reconcile the derived branch set against the ledger and report.

    Args:
        argv: Command-line arguments; ``sys.argv`` when omitted.

    Returns:
        ``0`` when every branch is adjudicated and every citation holds.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument("--skeleton", action="store_true", help="emit an unadjudicated ledger scaffold")
    parser.add_argument("--tokens", metavar="PATH", help="print the citable tokens per symbol for one file")
    arguments = parser.parse_args(argv)

    if arguments.tokens:
        for symbol, names in sorted(citable_tokens(arguments.tokens).items()):
            print(f"{symbol}: {', '.join(sorted(names))}")
        return 0
    if arguments.skeleton:
        print(render_ledger(derived_branch_sites()))
        return 0

    report = reconcile()
    if arguments.json:
        print(
            json.dumps(
                {
                    "sites": [list(site.key) for site in report.sites],
                    "unclassified": [list(site.key) for site in report.unclassified],
                    "stale": [list(key) for key in report.stale],
                    "broken_citations": list(report.broken_citations),
                },
                indent=2,
            )
        )
        return 0 if report.clean else 1

    print(f"derived branches      : {len(report.sites)}")
    print(f"unclassified          : {len(report.unclassified)}")
    print(f"stale ledger rows     : {len(report.stale)}")
    print(f"broken citations      : {len(report.broken_citations)}")
    for site in report.unclassified:
        print(f"  UNCLASSIFIED: {site.render()}")
    for key in report.stale:
        print(f"  STALE LEDGER ROW: {key[0]}::{key[1]} [{key[2]}]")
    for entry in report.broken_citations:
        print(f"  BROKEN CITATION: {entry}")
    return 0 if report.clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
