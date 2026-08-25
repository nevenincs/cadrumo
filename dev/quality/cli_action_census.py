"""AST-backed candidate census for the CLI action-envelope campaign.

The census measures the source before an adjudication table declares what is
canonical.  It deliberately reports the initial, mechanical candidate
universe rather than presenting a small hand-curated list as the blast radius.
Each record has a semantic key made of the repository path, its enclosing
symbol, the data-flow role, the field alias, and the observed action identity.
Locations are retained as locators, not as identity: moving a statement within
the same symbol must not make an old disposition stale.

This first pass covers production Python under ``src/cadrumo``.  Later passes
extend its vocabulary and join its candidates to dispositions and the live
operator surface; those concerns are intentionally not hidden in this scanner.

Usage::

    python -m dev.quality.cli_action_census HEAD
    python -m dev.quality.cli_action_census HEAD --json
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, cast, override

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.errors import declared_error_codes

from .._paths import REPO_ROOT, UTF_8

SOURCE_ROOT: Final[str] = "src/cadrumo"
_UTF_8: Final[str] = UTF_8

# This is the mechanically grounded starting vocabulary, not the claimed
# fixed point.  ``recovery_hint`` was discovered by the pre-plan semantic pass
# and therefore belongs in the seed rather than waiting to be rediscovered.
INITIAL_ACTION_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "fix_command",
        "next_action",
        "next_command",
        "recovery_hint",
        "remediation",
        "suggestion",
    },
)
COMMAND_PREFIX: Final[str] = "aeat "
COMMAND_LITERAL_ALIAS: Final[str] = "<command-literal>"
MODULE_SYMBOL: Final[str] = "<module>"
_FIXED_POINT_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset({".json", ".py", ".yaml", ".yml"})
_RENDERER_SINKS: Final[frozenset[str]] = frozenset(
    {"emit_envelope", "emit_json_success", "echo", "print", "tr"},
)
FIXED_POINT_STATE_VERSION: Final[int] = 1
FIXED_POINT_PRODUCTION_SCOPE: Final[str] = "production-src-cadrumo-v1"
AUTHORED_ERROR_MESSAGE_SCOPE: Final[str] = "production-src-cadrumo-v1"
"""The whole production tree whose registered-error messages are joined."""

_CADRUMO_ERROR_QUALNAME: Final[str] = "cadrumo.core.errors.CadrumoError"
_MESSAGE_KEYWORDS: Final[frozenset[str]] = frozenset({"message", "translated_message"})

type CandidateKey = tuple[str, str, str, str, str]


class DiscoveryKind(StrEnum):
    """Closed kinds of evidence found by one fixed-point census pass."""

    ACTION_ALIAS = "action_alias"
    COMMAND_FORM = "command_form"
    HELPER = "helper"
    LOCALE_FAMILY = "locale_family"
    MODEL = "model"
    REFUSAL_SITE = "refusal_site"
    RENDERER = "renderer"


class DiscoveryTriggerKind(StrEnum):
    """The evidence relationship that permitted a discovery."""

    CANDIDATE = "candidate"
    SEED = "seed"


@dataclass(frozen=True, slots=True)
class DiscoveryTrigger:
    """Local causal evidence for a discovery, never a global alias lookup."""

    kind: DiscoveryTriggerKind
    token: str
    path: str
    enclosing_symbol: str
    line: int
    column: int
    candidate_key: CandidateKey | None = None


@dataclass(frozen=True, slots=True)
class DiscoveryRecord:
    """One evidence-preserving semantic cluster observed in source."""

    kind: DiscoveryKind
    token: str
    path: str
    enclosing_symbol: str
    line: int
    column: int
    trigger: DiscoveryTrigger

    @property
    def key(self) -> tuple[object, ...]:
        """Return a deterministic identity including the causal relationship."""
        return (
            self.kind.value,
            self.token,
            self.path,
            self.enclosing_symbol,
            self.trigger.kind.value,
            self.trigger.token,
            self.trigger.path,
            self.trigger.enclosing_symbol,
            self.trigger.candidate_key or (),
        )


@dataclass(frozen=True, slots=True)
class UnknownCluster:
    """An externally reported cluster that cannot be auto-admitted safely."""

    kind: str
    token: str
    path: str
    enclosing_symbol: str
    line: int
    column: int
    trigger: DiscoveryTrigger

    @property
    def key(self) -> tuple[object, ...]:
        """Return a deterministic identity for an unclosed external finding."""
        return (
            self.kind,
            self.token,
            self.path,
            self.enclosing_symbol,
            self.trigger.kind.value,
            self.trigger.token,
            self.trigger.path,
            self.trigger.enclosing_symbol,
            self.trigger.candidate_key or (),
        )


@dataclass(frozen=True, slots=True)
class FixedPointState:
    """Versioned, serializable admissions used by one source-scope closure."""

    version: int
    revision: str
    scope: str
    admitted_aliases: tuple[str, ...]
    admitted_cluster_keys: tuple[tuple[object, ...], ...] = ()


@dataclass(frozen=True, slots=True)
class FixedPointPass:
    """The deterministic result of one semantic-plus-mechanical pass."""

    state: FixedPointState
    candidates: tuple[CandidateRecord, ...]
    discoveries: tuple[DiscoveryRecord, ...]
    unknown_clusters: tuple[UnknownCluster, ...]

    @property
    def newly_observed(self) -> tuple[DiscoveryRecord, ...]:
        """Return evidence not explicitly admitted into the prior state."""
        admitted = set(self.state.admitted_cluster_keys)
        return tuple(record for record in self.discoveries if record.key not in admitted)


class FixedPointNotClosedError(RuntimeError):
    """Raised when a proposed closing pass finds unadmitted evidence."""


@dataclass(frozen=True, slots=True)
class RegisteredErrorCode:
    """One live registry declaration used as an authored-message join owner."""

    error_qualname: str
    code: str


@dataclass(frozen=True, slots=True)
class AuthoredErrorMessageSite:
    """One source call that supplies a registered error's direct message text.

    The location is a diagnostic locator only.  ``fingerprint`` excludes it so
    an intentional disposition stays current through a formatting-only move.
    ``owner_qualnames`` is deliberately a set-shaped tuple: its cardinality is
    the mechanical join result that the disposition layer must partition.
    """

    path: str
    enclosing_symbol: str
    callee: str
    message_expression: str
    normalized_call_sha256: str
    ordinal: int
    line: int
    column: int
    owner_qualnames: tuple[str, ...]

    @property
    def fingerprint(self) -> str:
        """Return the stable physical identity used by exclusion rows."""
        return "|".join(
            (
                self.path,
                self.enclosing_symbol,
                self.callee,
                self.message_expression,
                self.normalized_call_sha256,
                str(self.ordinal),
            ),
        )


@dataclass(frozen=True, slots=True)
class AuthoredErrorMessageJoin:
    """The complete mechanical join of live codes to direct message sites."""

    registered_codes: tuple[RegisteredErrorCode, ...]
    sites: tuple[AuthoredErrorMessageSite, ...]

    @property
    def clean_codes(self) -> tuple[RegisteredErrorCode, ...]:
        """Return declared codes with no authored-message site in this tree."""
        joined = {owner for site in self.sites for owner in site.owner_qualnames}
        return tuple(code for code in self.registered_codes if code.error_qualname not in joined)

    @property
    def unresolved_sites(self) -> tuple[AuthoredErrorMessageSite, ...]:
        """Return known error-message calls without a registered-code owner."""
        return tuple(site for site in self.sites if not site.owner_qualnames)

    @property
    def multiply_owned_sites(self) -> tuple[AuthoredErrorMessageSite, ...]:
        """Return calls whose static path resolves to more than one code."""
        return tuple(site for site in self.sites if len(site.owner_qualnames) > 1)

    @property
    def singly_owned_sites(self) -> tuple[AuthoredErrorMessageSite, ...]:
        """Return calls that resolve to exactly one registered-code owner."""
        return tuple(site for site in self.sites if len(site.owner_qualnames) == 1)


class AuthoredErrorMessageCensusError(ValueError):
    """Raised when the live source tree cannot be scanned as one whole input."""


class CurrentTreeCensusError(ValueError):
    """Raised when the current production tree cannot be scanned as one whole input."""


@dataclass(frozen=True, slots=True)
class CandidateRecord:
    """One mechanically observed action-guidance candidate.

    ``key`` is the stable identity consumed by later adjudication work.  The
    line and column locate the current source only; they do not participate in
    identity because a formatting-only move is not a new candidate.
    """

    path: str
    enclosing_symbol: str
    role: str
    alias: str
    action_identity: str
    line: int
    column: int

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        """Return the disposition-safe, source-location-independent key."""
        return (self.path, self.enclosing_symbol, self.role, self.alias, self.action_identity)


def repository_sources(revision: str) -> tuple[tuple[str, str], ...]:
    """Read census-relevant repository text from one pinned revision.

    ``git archive`` is a single, revision-consistent object read.  Calling
    ``git show`` for every source file made a normal census operationally
    unbounded on this repository despite each individual lookup being cheap.
    """
    completed = subprocess.run(  # noqa: S603 - fixed executable and arguments
        ["git", "archive", "--format=tar", revision, SOURCE_ROOT],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    sources: list[tuple[str, str]] = []
    with tarfile.open(fileobj=io.BytesIO(completed.stdout), mode="r:") as archive:
        for member in archive:
            path = member.name
            if not member.isfile() or Path(path).suffix not in _FIXED_POINT_SOURCE_SUFFIXES:
                continue
            source_file = archive.extractfile(member)
            if source_file is None:
                continue
            try:
                sources.append((path, source_file.read().decode(_UTF_8)))
            except UnicodeDecodeError:
                continue
    return tuple(sorted(sources))


def production_sources(revision: str) -> tuple[tuple[str, str], ...]:
    """Return the original S01 production-Python source universe unchanged."""
    return tuple(
        (path, source)
        for path, source in repository_sources(revision)
        if path.endswith(".py") and "/tests/" not in path and not Path(path).name.startswith("test_")
    )


def _current_tree_sources(
    *,
    root: Path,
    suffixes: frozenset[str],
) -> tuple[tuple[str, str], ...]:
    """Read one complete production source scope from the current worktree.

    This is intentionally distinct from :func:`repository_sources`: a pinned
    revision remains the reproducible campaign baseline, while S46 needs a
    fail-closed mechanical reading of concurrent work before it can claim that
    no action site or direct alias has appeared.
    """
    source_root = root / SOURCE_ROOT
    if not source_root.is_dir():
        raise CurrentTreeCensusError(f"current-tree census source root is absent: {source_root}")

    sources: list[tuple[str, str]] = []
    for source_path in scan_directory(
        source_root,
        pattern="*",
        recursive=True,
        prune_directories=("__pycache__",),
    ):
        if source_path.suffix not in suffixes:
            continue
        relative = source_path.relative_to(root)
        if "tests" in relative.parts or source_path.name.startswith("test_"):
            continue
        path = relative.as_posix()
        try:
            source = source_path.read_text(encoding=_UTF_8)
        except OSError as error:
            raise CurrentTreeCensusError(
                f"current-tree census cannot read {path}: {type(error).__name__}",
            ) from error
        except UnicodeDecodeError as error:
            raise CurrentTreeCensusError(
                f"current-tree census cannot decode {path}: {type(error).__name__}",
            ) from error
        if source_path.suffix == ".py":
            try:
                ast.parse(source, filename=path)
            except SyntaxError as error:
                raise CurrentTreeCensusError(
                    f"current-tree census cannot parse {path}: {type(error).__name__}",
                ) from error
        sources.append((path, source))
    if not sources:
        raise CurrentTreeCensusError(f"current-tree census found no production sources: {source_root}")
    return tuple(sorted(sources))


def current_production_sources(*, root: Path = REPO_ROOT) -> tuple[tuple[str, str], ...]:
    """Return the complete non-test production Python tree at its live filesystem state."""
    return _current_tree_sources(root=root, suffixes=frozenset({".py"}))


def fixed_point_production_sources(revision: str) -> tuple[tuple[str, str], ...]:
    """Return the production-only source scope used by S02.

    S01's denominator is Python under ``src/cadrumo``.  S02 keeps exactly that
    candidate universe while admitting production catalogue YAML solely as a
    separately typed discovery source.  Tests are intentionally unavailable
    through this function; unit tests exercise ``fixed_point_pass_from_sources``
    with an explicit source snapshot instead.
    """
    return tuple(
        (path, source)
        for path, source in repository_sources(revision)
        if "/tests/" not in path
        and not Path(path).name.startswith("test_")
        and Path(path).suffix in _FIXED_POINT_SOURCE_SUFFIXES
    )


def _identity(node: ast.expr | None, *, missing: str = "<declaration>") -> str:
    """Return a deterministic action identity without evaluating source code."""
    if node is None:
        return missing
    if isinstance(node, ast.Constant):
        if node.value is None:
            return "<none>"
        if isinstance(node.value, str):
            return node.value or "<empty>"
        return repr(node.value)
    return ast.unparse(node)


def _target_aliases(target: ast.expr, aliases: frozenset[str]) -> tuple[str, ...]:
    """Return admitted action aliases written by an assignment target."""
    if isinstance(target, ast.Name) and target.id in aliases:
        return (target.id,)
    if isinstance(target, ast.Attribute) and target.attr in aliases:
        return (target.attr,)
    if isinstance(target, (ast.Tuple, ast.List)):
        return tuple(alias for child in target.elts for alias in _target_aliases(child, aliases))
    return ()


class _CandidateVisitor(ast.NodeVisitor):
    """Collect role-labelled candidates while carrying the enclosing symbol."""

    def __init__(self, path: str, aliases: frozenset[str]) -> None:
        self._path = path
        self._aliases = aliases
        self._symbols: list[str] = []
        self.records: list[CandidateRecord] = []

    @property
    def _symbol(self) -> str:
        return ".".join(self._symbols) if self._symbols else MODULE_SYMBOL

    def _add(self, node: ast.stmt | ast.expr, *, role: str, alias: str, action_identity: str) -> None:
        self.records.append(
            CandidateRecord(
                path=self._path,
                enclosing_symbol=self._symbol,
                role=role,
                alias=alias,
                action_identity=action_identity,
                line=node.lineno,
                column=node.col_offset,
            ),
        )

    @override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._symbols.append(node.name)
        self.generic_visit(node)
        self._symbols.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._symbols.append(node.name)
        self.generic_visit(node)
        self._symbols.pop()

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    @override
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        for alias in _target_aliases(node.target, self._aliases):
            self._add(node, role="definition", alias=alias, action_identity=_identity(node.value))
        self.generic_visit(node)

    @override
    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            for alias in _target_aliases(target, self._aliases):
                self._add(node, role="assignment", alias=alias, action_identity=_identity(node.value))
        self.generic_visit(node)

    @override
    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        for alias in _target_aliases(node.target, self._aliases):
            self._add(node, role="assignment", alias=alias, action_identity=_identity(node.value))
        self.generic_visit(node)

    @override
    def visit_Call(self, node: ast.Call) -> None:
        for keyword in node.keywords:
            if keyword.arg in self._aliases:
                self._add(node, role="producer", alias=keyword.arg, action_identity=_identity(keyword.value))
        self.generic_visit(node)

    @override
    def visit_Dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values, strict=True):
            if isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value in self._aliases:
                self._add(key, role="producer", alias=key.value, action_identity=_identity(value))
        self.generic_visit(node)

    @override
    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load) and node.attr in self._aliases:
            self._add(node, role="transformer", alias=node.attr, action_identity=ast.unparse(node))
        self.generic_visit(node)

    @override
    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and node.value.startswith(COMMAND_PREFIX):
            self._add(
                node,
                role="command_literal",
                alias=COMMAND_LITERAL_ALIAS,
                action_identity=node.value,
            )


def _census_sources(
    sources: Iterable[tuple[str, str]],
    aliases: frozenset[str],
) -> tuple[CandidateRecord, ...]:
    """Return unique candidates from already-pinned Python sources."""
    records: dict[CandidateKey, CandidateRecord] = {}
    for path, source in sources:
        if not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError:
            continue
        visitor = _CandidateVisitor(path, aliases)
        visitor.visit(tree)
        for record in visitor.records:
            previous = records.get(record.key)
            if previous is None or (record.line, record.column) < (previous.line, previous.column):
                records[record.key] = record
    return tuple(sorted(records.values(), key=lambda record: (*record.key, record.line, record.column)))


def census(revision: str) -> tuple[CandidateRecord, ...]:
    """Return the S01 candidate ledger from ``revision``.

    The revision is deliberately required.  Scanning a moving worktree while
    peers are committing can combine source from different trees and fabricate
    a blast-radius number that has never existed at one revision.
    """
    return _census_sources(production_sources(revision), INITIAL_ACTION_ALIASES)


def current_census(*, root: Path = REPO_ROOT) -> tuple[CandidateRecord, ...]:
    """Return the mechanically complete action-candidate census for the current tree."""
    return _census_sources(current_production_sources(root=root), INITIAL_ACTION_ALIASES)


def action_alias_discoveries_from_sources(
    sources: Iterable[SourceEntry],
    *,
    aliases: frozenset[str],
) -> tuple[DiscoveryRecord, ...]:
    """Find only direct, newly named fields to which an admitted action flows.

    This intentionally keeps a distinct result from the broader fixed-point
    report: S46 needs a cheap fail-closed alias check over current Python, not
    catalogue/YAML discovery or a second claim about source authority.
    """
    source_snapshot = tuple(sources)
    candidates = _census_sources(source_snapshot, aliases)
    discoveries: list[DiscoveryRecord] = []
    for path, source in source_snapshot:
        if not path.endswith(".py"):
            continue
        tree = ast.parse(source, filename=path)
        visitor = _DiscoveryVisitor(path, aliases, candidates)
        visitor.visit(tree)
        discoveries.extend(record for record in visitor.records if record.kind is DiscoveryKind.ACTION_ALIAS)
    return _stable_records(discoveries)


def current_action_alias_discoveries(
    *,
    aliases: frozenset[str],
    root: Path = REPO_ROOT,
) -> tuple[DiscoveryRecord, ...]:
    """Find direct action-field aliases across the complete current production tree."""
    return action_alias_discoveries_from_sources(current_production_sources(root=root), aliases=aliases)


type SourceEntry = tuple[str, str]
type ClusterKey = tuple[object, ...]


@dataclass(frozen=True, slots=True)
class FixedPointSources:
    """The explicit production-only inputs to one S02 observation pass."""

    production_python: tuple[SourceEntry, ...]
    yaml_catalogues: tuple[SourceEntry, ...]

    @classmethod
    def from_entries(cls, entries: Iterable[SourceEntry]) -> FixedPointSources:
        """Partition explicit source text without widening the production scope."""
        python: list[SourceEntry] = []
        catalogues: list[SourceEntry] = []
        for path, source in entries:
            if not _is_fixed_point_production_path(path):
                message = f"fixed-point source outside production scope: {path}"
                raise ValueError(message)
            suffix = Path(path).suffix
            if suffix == ".py":
                python.append((path, source))
            elif suffix in {".yaml", ".yml"}:
                catalogues.append((path, source))
        return cls(tuple(sorted(python)), tuple(sorted(catalogues)))


@dataclass(frozen=True, slots=True)
class _SourceReference:
    """One direct lexical flow from an admitted action token to a use site."""

    alias: str
    node: ast.expr


def _is_fixed_point_production_path(path: str) -> bool:
    return path.startswith(f"{SOURCE_ROOT}/") and "/tests/" not in path and not Path(path).name.startswith("test_")


def fixed_point_sources(revision: str) -> FixedPointSources:
    """Read the complete, production-only S02 source scope at one revision."""
    return FixedPointSources.from_entries(fixed_point_production_sources(revision))


def current_fixed_point_sources(*, root: Path = REPO_ROOT) -> FixedPointSources:
    """Read the complete fixed-point scope from the live production tree.

    The returned snapshot is intentionally ephemeral: callers use it to prove
    that the checked-in ledger covers the tree they are about to change, not to
    replace a revision-pinned campaign record.
    """
    return FixedPointSources.from_entries(
        _current_tree_sources(root=root, suffixes=_FIXED_POINT_SOURCE_SUFFIXES),
    )


def initial_fixed_point_state(revision: str) -> FixedPointState:
    """Return the only automatically admitted inputs: the S01 seed aliases."""
    return FixedPointState(
        version=FIXED_POINT_STATE_VERSION,
        revision=revision,
        scope=FIXED_POINT_PRODUCTION_SCOPE,
        admitted_aliases=tuple(sorted(INITIAL_ACTION_ALIASES)),
    )


def _command_form(value: str) -> str:
    """Return the stable two-token command-family form of one CLI literal."""
    return " ".join(value.split(maxsplit=2)[:2])


def _stable_records(records: Iterable[DiscoveryRecord]) -> tuple[DiscoveryRecord, ...]:
    unique = {record.key: record for record in records}
    return tuple(sorted(unique.values(), key=lambda record: record.key))


def _stable_unknown(records: Iterable[UnknownCluster]) -> tuple[UnknownCluster, ...]:
    unique = {record.key: record for record in records}
    return tuple(sorted(unique.values(), key=lambda record: record.key))


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _assignment_target_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _direct_nodes(nodes: Iterable[ast.AST]) -> Iterable[ast.AST]:
    """Yield a scope's nodes while deliberately excluding nested lexical scopes."""
    stack = list(reversed(tuple(nodes)))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield node
        stack.extend(reversed(tuple(ast.iter_child_nodes(node))))


def _direct_reference(
    node: ast.AST | None,
    aliases: frozenset[str],
    bindings: Mapping[str, _SourceReference],
) -> _SourceReference | None:
    """Resolve only an explicit local data-flow edge; never a global alias match."""
    if isinstance(node, ast.Name):
        if node.id in bindings:
            return bindings[node.id]
        if node.id in aliases:
            return _SourceReference(node.id, node)
        return None
    if isinstance(node, ast.Attribute) and node.attr in aliases:
        return _SourceReference(node.attr, node)
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
        and node.slice.value in aliases
    ):
        return _SourceReference(node.slice.value, node)
    if isinstance(node, ast.Call):
        references = [
            reference
            for value in (*node.args, *(keyword.value for keyword in node.keywords))
            if (reference := _direct_reference(value, aliases, bindings)) is not None
        ]
        return references[0] if len(references) == 1 else None
    if isinstance(node, ast.FormattedValue):
        return _direct_reference(node.value, aliases, bindings)
    if isinstance(node, ast.JoinedStr):
        references = [
            reference for value in node.values if (reference := _direct_reference(value, aliases, bindings)) is not None
        ]
        return references[0] if len(references) == 1 else None
    return None


class _DiscoveryVisitor(ast.NodeVisitor):
    """Collect typed discoveries from direct lexical action-dataflow edges only."""

    def __init__(
        self,
        path: str,
        aliases: frozenset[str],
        candidates: tuple[CandidateRecord, ...],
    ) -> None:
        self._path = path
        self._aliases = aliases
        self._symbols: list[str] = []
        self.records: list[DiscoveryRecord] = []
        self._candidates_by_line_alias: dict[tuple[int, str], CandidateRecord] = {}
        for candidate in candidates:
            if candidate.path != path:
                continue
            key = (candidate.line, candidate.alias)
            prior = self._candidates_by_line_alias.get(key)
            if prior is None or (candidate.column, candidate.key) < (prior.column, prior.key):
                self._candidates_by_line_alias[key] = candidate

    @property
    def _symbol(self) -> str:
        return ".".join(self._symbols) if self._symbols else MODULE_SYMBOL

    def _trigger(self, reference: _SourceReference) -> DiscoveryTrigger:
        candidate = self._candidates_by_line_alias.get((reference.node.lineno, reference.alias))
        return DiscoveryTrigger(
            kind=DiscoveryTriggerKind.CANDIDATE if candidate is not None else DiscoveryTriggerKind.SEED,
            token=reference.alias,
            path=self._path,
            enclosing_symbol=self._symbol,
            line=reference.node.lineno,
            column=reference.node.col_offset,
            candidate_key=candidate.key if candidate is not None else None,
        )

    def _add(
        self,
        kind: DiscoveryKind,
        token: str,
        node: ast.stmt | ast.expr,
        reference: _SourceReference,
    ) -> None:
        self.records.append(
            DiscoveryRecord(
                kind=kind,
                token=token,
                path=self._path,
                enclosing_symbol=self._symbol,
                line=node.lineno,
                column=node.col_offset,
                trigger=self._trigger(reference),
            ),
        )

    def _observe_assignment(
        self,
        target: ast.expr,
        value: ast.AST | None,
        node: ast.stmt | ast.expr,
        bindings: dict[str, _SourceReference],
    ) -> None:
        reference = _direct_reference(value, self._aliases, bindings)
        target_name = _assignment_target_name(target)
        if reference is None or target_name is None:
            return
        if target_name not in self._aliases and target_name != reference.alias:
            self._add(DiscoveryKind.ACTION_ALIAS, target_name, node, reference)
        if isinstance(target, ast.Name):
            bindings[target.id] = reference

    def _observe_scope(
        self,
        body: Iterable[ast.stmt],
        *,
        parameter_names: Iterable[str] = (),
    ) -> None:
        bindings = {
            name: _SourceReference(name, ast.Name(id=name, ctx=ast.Load(), lineno=0, col_offset=0))
            for name in parameter_names
            if name in self._aliases
        }
        for node in _direct_nodes(body):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    self._observe_assignment(target, node.value, node, bindings)
            elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
                self._observe_assignment(node.target, node.value, node, bindings)
            elif isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values, strict=True):
                    reference = _direct_reference(value, self._aliases, bindings)
                    if (
                        reference is not None
                        and isinstance(key, ast.Constant)
                        and isinstance(key.value, str)
                        and key.value not in self._aliases
                    ):
                        self._add(DiscoveryKind.ACTION_ALIAS, key.value, key, reference)
            elif isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)):
                value = node.value
                reference = _direct_reference(value, self._aliases, bindings)
                if reference is not None:
                    self._add(DiscoveryKind.HELPER, self._symbol, node, reference)
            elif isinstance(node, ast.Call):
                if _call_name(node) in _RENDERER_SINKS:
                    references = [
                        reference
                        for value in (*node.args, *(keyword.value for keyword in node.keywords))
                        if (reference := _direct_reference(value, self._aliases, bindings)) is not None
                    ]
                    for reference in references:
                        self._add(DiscoveryKind.RENDERER, self._symbol, node, reference)
            elif isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                references = [
                    reference
                    for value in (*node.exc.args, *(keyword.value for keyword in node.exc.keywords))
                    if (reference := _direct_reference(value, self._aliases, bindings)) is not None
                ]
                for reference in references:
                    self._add(DiscoveryKind.REFUSAL_SITE, ast.unparse(node.exc.func), node, reference)
            elif (
                isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith(COMMAND_PREFIX)
            ):
                self._add(
                    DiscoveryKind.COMMAND_FORM,
                    _command_form(node.value),
                    node,
                    _SourceReference(COMMAND_LITERAL_ALIAS, node),
                )

    @override
    def visit_Module(self, node: ast.Module) -> None:
        self._observe_scope(node.body)
        for child in node.body:
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(child)

    @override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._symbols.append(node.name)
        for child in node.body:
            if not isinstance(child, (ast.Assign, ast.AnnAssign)):
                continue
            targets = (child.target,) if isinstance(child, ast.AnnAssign) else child.targets
            for target in targets:
                for alias in _target_aliases(target, self._aliases):
                    self._add(
                        DiscoveryKind.MODEL,
                        self._symbol,
                        child,
                        _SourceReference(alias, target),
                    )
        self._observe_scope(node.body)
        for child in node.body:
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(child)
        self._symbols.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._symbols.append(node.name)
        parameters = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
        self._observe_scope(node.body, parameter_names=(argument.arg for argument in parameters))
        for child in node.body:
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(child)
        self._symbols.pop()

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)


def _locale_family(path: str) -> str | None:
    prefix = "src/cadrumo/locales/"
    return "src/cadrumo/locales" if path.startswith(prefix) else None


def _yaml_value_scalars(node: Node) -> Iterable[ScalarNode]:
    """Yield scalar *values* only, excluding YAML comments and mapping keys."""
    if isinstance(node, ScalarNode):
        yield node
    elif isinstance(node, SequenceNode):
        for child in node.value:
            yield from _yaml_value_scalars(child)
    elif isinstance(node, MappingNode):
        for _key, value in node.value:
            yield from _yaml_value_scalars(value)


def _locale_discoveries(sources: Iterable[SourceEntry]) -> tuple[DiscoveryRecord, ...]:
    records: list[DiscoveryRecord] = []
    for path, source in sources:
        family = _locale_family(path)
        if family is None:
            continue
        try:
            document = cast(Node | None, yaml.compose(source))  # type: ignore[reportUnknownMemberType]
        except yaml.YAMLError:
            continue
        if document is None:
            continue
        for scalar in _yaml_value_scalars(document):
            if scalar.tag != "tag:yaml.org,2002:str" or not scalar.value.startswith(COMMAND_PREFIX):
                continue
            mark = scalar.start_mark
            records.append(
                DiscoveryRecord(
                    kind=DiscoveryKind.LOCALE_FAMILY,
                    token=family,
                    path=path,
                    enclosing_symbol=MODULE_SYMBOL,
                    line=mark.line + 1,
                    column=mark.column,
                    trigger=DiscoveryTrigger(
                        kind=DiscoveryTriggerKind.SEED,
                        token=COMMAND_PREFIX,
                        path=path,
                        enclosing_symbol=MODULE_SYMBOL,
                        line=mark.line + 1,
                        column=mark.column,
                    ),
                ),
            )
    return _stable_records(records)


def _validate_fixed_point_state(state: FixedPointState, revision: str | None = None) -> None:
    if state.version != FIXED_POINT_STATE_VERSION:
        message = f"unsupported fixed-point state version {state.version!r}"
        raise ValueError(message)
    if state.scope != FIXED_POINT_PRODUCTION_SCOPE:
        message = f"unsupported fixed-point state scope {state.scope!r}"
        raise ValueError(message)
    if revision is not None and state.revision != revision:
        message = f"fixed-point state revision {state.revision!r} does not match pass revision {revision!r}"
        raise ValueError(message)
    if tuple(sorted(set(state.admitted_aliases))) != state.admitted_aliases:
        raise ValueError("fixed-point state aliases must be sorted and unique")
    if not INITIAL_ACTION_ALIASES.issubset(state.admitted_aliases):
        raise ValueError("fixed-point state omits one or more S01 seed aliases")


def _json_cluster_value(value: object) -> object:
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        return [_json_cluster_value(item) for item in items]
    if isinstance(value, str):
        return value
    raise ValueError("fixed-point cluster keys may contain only strings and tuples")


def _cluster_key_from_json(value: object) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise ValueError("fixed-point cluster key must be a JSON array")
    values = cast(list[object], value)
    parsed: list[object] = []
    for item in values:
        if isinstance(item, str):
            parsed.append(item)
        elif isinstance(item, list):
            parsed.append(_cluster_key_from_json(cast(object, item)))
        else:
            raise ValueError("fixed-point cluster key values must be strings or arrays")
    return tuple(parsed)


def _cluster_sort_key(key: ClusterKey) -> str:
    return json.dumps(_json_cluster_value(key), separators=(",", ":"))


def dump_fixed_point_state(state: FixedPointState) -> dict[str, object]:
    """Return the sole canonical JSON-v1 representation of admitted state."""
    _validate_fixed_point_state(state)
    cluster_keys = tuple(sorted(set(state.admitted_cluster_keys), key=_cluster_sort_key))
    if cluster_keys != state.admitted_cluster_keys:
        raise ValueError("fixed-point state cluster keys must be sorted and unique")
    return {
        "version": state.version,
        "revision": state.revision,
        "scope": state.scope,
        "admitted_aliases": list(state.admitted_aliases),
        "admitted_cluster_keys": [_json_cluster_value(key) for key in state.admitted_cluster_keys],
    }


def load_fixed_point_state(payload: Mapping[str, object]) -> FixedPointState:
    """Load only a complete canonical v1 state; partial state is not evidence."""
    expected = {"version", "revision", "scope", "admitted_aliases", "admitted_cluster_keys"}
    if set(payload) != expected:
        message = f"fixed-point state keys must be exactly {sorted(expected)!r}"
        raise ValueError(message)
    version = payload["version"]
    revision = payload["revision"]
    scope = payload["scope"]
    aliases = payload["admitted_aliases"]
    keys = payload["admitted_cluster_keys"]
    if type(version) is not int or not isinstance(revision, str) or not isinstance(scope, str):
        raise ValueError("fixed-point state version, revision, and scope have invalid types")
    if not isinstance(aliases, list):
        raise ValueError("fixed-point state aliases must be a non-empty string array")
    alias_values = cast(list[object], aliases)
    if not all(isinstance(alias, str) and alias for alias in alias_values):
        raise ValueError("fixed-point state aliases must be a non-empty string array")
    if not isinstance(keys, list):
        raise ValueError("fixed-point state cluster keys must be an array")
    key_values = cast(list[object], keys)
    state = FixedPointState(
        version=version,
        revision=revision,
        scope=scope,
        admitted_aliases=tuple(cast(str, alias) for alias in alias_values),
        admitted_cluster_keys=tuple(_cluster_key_from_json(key) for key in key_values),
    )
    dumped = dump_fixed_point_state(state)
    if dumped != dict(payload):
        raise ValueError("fixed-point state is not canonical JSON-v1")
    return state


def read_fixed_point_state(path: Path) -> FixedPointState:
    """Read one reviewed state artifact without accepting malformed JSON."""
    try:
        payload = cast(object, json.loads(path.read_text(encoding=_UTF_8)))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read fixed-point state {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("fixed-point state document must be a JSON object")
    document = cast(dict[object, object], payload)
    if not all(isinstance(key, str) for key in document):
        raise ValueError("fixed-point state document must be a JSON object")
    return load_fixed_point_state(cast(Mapping[str, object], document))


def write_fixed_point_state(path: Path, state: FixedPointState) -> None:
    """Persist the canonical reviewed-state form for a later exact rescan."""
    path.write_text(f"{json.dumps(dump_fixed_point_state(state), indent=2)}\n", encoding=_UTF_8, newline="\n")


def fixed_point_pass_from_sources(
    state: FixedPointState,
    sources: FixedPointSources | Iterable[SourceEntry],
    *,
    semantic_observations: Iterable[DiscoveryRecord | UnknownCluster] = (),
) -> FixedPointPass:
    """Run one deterministic pass over an explicit production source snapshot."""
    _validate_fixed_point_state(state)
    source_set = sources if isinstance(sources, FixedPointSources) else FixedPointSources.from_entries(sources)
    candidates = _census_sources(source_set.production_python, frozenset(state.admitted_aliases))
    discoveries: list[DiscoveryRecord] = []
    for path, source in source_set.production_python:
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError:
            continue
        visitor = _DiscoveryVisitor(path, frozenset(state.admitted_aliases), candidates)
        visitor.visit(tree)
        discoveries.extend(visitor.records)
    discoveries.extend(_locale_discoveries(source_set.yaml_catalogues))
    unknown_clusters: list[UnknownCluster] = []
    for observation in semantic_observations:
        if isinstance(observation, DiscoveryRecord):
            discoveries.append(observation)
        else:
            unknown_clusters.append(observation)
    return FixedPointPass(
        state=state,
        candidates=candidates,
        discoveries=_stable_records(discoveries),
        unknown_clusters=_stable_unknown(unknown_clusters),
    )


def fixed_point_pass(
    revision: str,
    state: FixedPointState,
    *,
    semantic_observations: Iterable[DiscoveryRecord | UnknownCluster] = (),
) -> FixedPointPass:
    """Run one pass over the exact S01 production scope at ``revision``."""
    _validate_fixed_point_state(state, revision)
    return fixed_point_pass_from_sources(
        state,
        fixed_point_sources(revision),
        semantic_observations=semantic_observations,
    )


def current_fixed_point_pass(
    state: FixedPointState,
    *,
    root: Path = REPO_ROOT,
    semantic_observations: Iterable[DiscoveryRecord | UnknownCluster] = (),
) -> FixedPointPass:
    """Run one fail-closed fixed-point pass against the live production tree."""
    return fixed_point_pass_from_sources(
        state,
        current_fixed_point_sources(root=root),
        semantic_observations=semantic_observations,
    )


def admit_observed(
    state: FixedPointState,
    discoveries: Iterable[DiscoveryRecord],
) -> FixedPointState:
    """Acknowledge reviewed cluster keys without expanding the scan vocabulary."""
    _validate_fixed_point_state(state)
    observed = tuple(discoveries)
    cluster_keys = tuple(
        sorted(
            {*state.admitted_cluster_keys, *(record.key for record in observed)},
            key=_cluster_sort_key,
        ),
    )
    return FixedPointState(
        version=state.version,
        revision=state.revision,
        scope=state.scope,
        admitted_aliases=state.admitted_aliases,
        admitted_cluster_keys=cluster_keys,
    )


def admit_discoveries(
    state: FixedPointState,
    discoveries: Iterable[DiscoveryRecord],
) -> FixedPointState:
    """Compatibility name for the cluster-only ``admit_observed`` transition."""
    return admit_observed(state, discoveries)


def admit_aliases(
    state: FixedPointState,
    aliases: Iterable[str],
    discoveries: Iterable[DiscoveryRecord],
) -> FixedPointState:
    """Promote only explicitly named, locally evidenced action-alias tokens."""
    _validate_fixed_point_state(state)
    requested = tuple(aliases)
    if not requested or any(not alias for alias in requested):
        raise ValueError("at least one non-empty action alias is required for promotion")
    observed = tuple(discoveries)
    evidenced = {
        record.token
        for record in observed
        if record.kind is DiscoveryKind.ACTION_ALIAS
        and record.trigger.path == record.path
        and record.trigger.enclosing_symbol == record.enclosing_symbol
    }
    unsupported = tuple(sorted(set(requested).difference(evidenced)))
    if unsupported:
        message = f"cannot admit unobserved action alias tokens: {', '.join(unsupported)}"
        raise ValueError(message)
    return FixedPointState(
        version=state.version,
        revision=state.revision,
        scope=state.scope,
        admitted_aliases=tuple(sorted((*state.admitted_aliases, *requested))),
        admitted_cluster_keys=state.admitted_cluster_keys,
    )


def admit_alias(
    state: FixedPointState,
    alias: str,
    discoveries: Iterable[DiscoveryRecord],
) -> FixedPointState:
    """Promote one evidenced action alias; convenience for reviewed state tools."""
    return admit_aliases(state, (alias,), discoveries)


def close_fixed_point(result: FixedPointPass) -> FixedPointPass:
    """Accept a closure only when a full rescan finds no reopened evidence."""
    new_keys = result.newly_observed
    if not new_keys and not result.unknown_clusters:
        return result
    lines = ["fixed-point closure refused: complete pass found unclosed semantic clusters"]
    lines.extend(
        f"{record.kind.value}:{record.token} at {record.path}:{record.line} "
        f"via {record.trigger.kind.value}:{record.trigger.token}"
        for record in new_keys
    )
    lines.extend(
        f"unknown:{record.kind}:{record.token} at {record.path}:{record.line} "
        f"via {record.trigger.kind.value}:{record.trigger.token}"
        for record in result.unknown_clusters
    )
    raise FixedPointNotClosedError("\n".join(lines))


@dataclass(frozen=True, slots=True)
class _ErrorReference:
    """A lexical name binding that may resolve to error classes or modules."""

    error_qualnames: frozenset[str] = frozenset()
    modules: frozenset[str] = frozenset()

    def merged(self, other: _ErrorReference) -> _ErrorReference:
        return _ErrorReference(
            error_qualnames=self.error_qualnames | other.error_qualnames,
            modules=self.modules | other.modules,
        )


_EMPTY_ERROR_REFERENCE: Final[_ErrorReference] = _ErrorReference()


def registered_error_codes() -> tuple[RegisteredErrorCode, ...]:
    """Return the live canonical registry declarations without restating them.

    The core registry remains the only owner of error codes.  This quality
    census consumes its declared projection solely to make the source join
    mechanical and complete.
    """
    return tuple(
        sorted(
            (
                RegisteredErrorCode(error_qualname=qualname, code=error.code)
                for qualname, error in declared_error_codes()
            ),
            key=lambda record: (record.error_qualname, record.code),
        ),
    )


def _authored_message_module_name(path: Path, *, root: Path) -> tuple[str, bool]:
    """Return the Python module name and package status for one production file."""
    relative = path.relative_to(root / "src").with_suffix("")
    is_package = relative.name == "__init__"
    parts = relative.parts[:-1] if is_package else relative.parts
    return ".".join(parts), is_package


def _authored_message_import_module(
    *,
    module: str,
    is_package: bool,
    level: int,
    imported: str | None,
) -> str:
    """Resolve an import statement's lexical module without importing source."""
    if not level:
        return imported or ""
    package = module if is_package else module.rpartition(".")[0]
    parts = package.split(".") if package else []
    if level:
        parts = parts[: len(parts) - level + 1]
    if imported:
        parts.extend(imported.split("."))
    return ".".join(part for part in parts if part)


def _authored_message_literal_reexport_module(
    *,
    module: str,
    is_package: bool,
    target: str,
) -> str:
    """Resolve a literal lazy-facade module target without importing it."""
    level = len(target) - len(target.lstrip("."))
    return _authored_message_import_module(
        module=module,
        is_package=is_package,
        level=level,
        imported=target[level:] or None,
    )


def _authored_message_sources(root: Path) -> tuple[tuple[str, str, str, bool], ...]:
    """Read every production Python module or fail rather than shrink the join."""
    source_root = root / SOURCE_ROOT
    if not source_root.is_dir():
        raise AuthoredErrorMessageCensusError(f"authored-message census source root is absent: {source_root}")
    sources: list[tuple[str, str, str, bool]] = []
    for source_path in scan_directory(
        source_root,
        pattern="*.py",
        recursive=True,
        prune_directories=("__pycache__",),
    ):
        if "tests" in source_path.relative_to(source_root).parts or source_path.name.startswith("test_"):
            continue
        path = source_path.relative_to(root).as_posix()
        try:
            source = source_path.read_text(encoding=_UTF_8)
        except OSError as error:
            raise AuthoredErrorMessageCensusError(
                f"authored-message census cannot read {path}: {type(error).__name__}",
            ) from error
        except UnicodeDecodeError as error:
            raise AuthoredErrorMessageCensusError(
                f"authored-message census cannot decode {path}: {type(error).__name__}",
            ) from error
        try:
            ast.parse(source, filename=path)
        except SyntaxError as error:
            raise AuthoredErrorMessageCensusError(
                f"authored-message census cannot parse {path}: {type(error).__name__}",
            ) from error
        module, is_package = _authored_message_module_name(source_path, root=root)
        sources.append((path, source, module, is_package))
    if not sources:
        raise AuthoredErrorMessageCensusError(f"authored-message census found no production modules: {source_root}")
    return tuple(sorted(sources))


class _SourceFacadeReexportResolver:
    """Resolve named ``cadrumo`` facade exports from source, never imports.

    Public packages routinely re-export a registered error from a private
    module.  Consumers of that public package must still join to the private
    registry owner.  This intentionally recognizes only source-level named
    imports (and their re-export chains); a recursive branch carries its
    ancestry so a malformed cycle cannot cause a recursive scan or be
    mistaken for a real owner.
    """

    def __init__(
        self,
        *,
        modules: Mapping[str, tuple[ast.Module, bool]],
        registered_qualnames: frozenset[str],
    ) -> None:
        self._modules = modules
        self._known_qualnames = registered_qualnames | {_CADRUMO_ERROR_QUALNAME}
        self._known_names = frozenset(qualname.rpartition(".")[2] for qualname in self._known_qualnames)
        self._cache: dict[tuple[str, str], _ErrorReference] = {}

    def is_source_module(self, module: str) -> bool:
        """Return whether ``module`` has a scanned production source file."""
        return module in self._modules

    def is_possible_registered_name(self, name: str) -> bool:
        """Return whether a name could bind a live registered error class."""
        return name in self._known_names

    def resolve(self, module: str, name: str) -> _ErrorReference:
        """Resolve one possible facade export through a cycle-safe AST walk."""
        return self._resolve(module, name, ancestry=frozenset())

    def _resolve(
        self,
        module: str,
        name: str,
        *,
        ancestry: frozenset[tuple[str, str]],
    ) -> _ErrorReference:
        key = (module, name)
        if key in self._cache:
            return self._cache[key]
        if key in ancestry:
            return _EMPTY_ERROR_REFERENCE

        direct_qualname = f"{module}.{name}"
        if direct_qualname in self._known_qualnames:
            reference = _ErrorReference(error_qualnames=frozenset({direct_qualname}))
            self._cache[key] = reference
            return reference

        source_module = self._modules.get(module)
        if source_module is None:
            return _EMPTY_ERROR_REFERENCE
        tree, is_package = source_module
        reference = _EMPTY_ERROR_REFERENCE
        next_ancestry = ancestry | {key}
        for statement in tree.body:
            if not isinstance(statement, ast.ImportFrom):
                continue
            source = _authored_message_import_module(
                module=module,
                is_package=is_package,
                level=statement.level,
                imported=statement.module,
            )
            for imported in statement.names:
                exported_name = imported.asname or imported.name
                if imported.name != "*" and exported_name != name:
                    continue
                imported_name = name if imported.name == "*" else imported.name
                reference = reference.merged(
                    self._resolve(source, imported_name, ancestry=next_ancestry),
                )
        lazy_target = self._lazy_export_target(tree, name)
        if lazy_target is not None:
            source = _authored_message_literal_reexport_module(
                module=module,
                is_package=is_package,
                target=lazy_target,
            )
            reference = reference.merged(self._resolve(source, name, ancestry=next_ancestry))
        self._cache[key] = reference
        return reference

    @staticmethod
    def _lazy_export_target(tree: ast.Module, name: str) -> str | None:
        """Return a source-literal ``_LAZY_EXPORTS`` target for one public name."""
        for statement in tree.body:
            value: ast.expr | None = None
            if (
                isinstance(statement, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "_LAZY_EXPORTS" for target in statement.targets)
            ) or (
                isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and statement.target.id == "_LAZY_EXPORTS"
            ):
                value = statement.value
            if not isinstance(value, ast.Dict):
                continue
            resolved_target: str | None = None
            for key, target in zip(value.keys, value.values, strict=True):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == name
                    and isinstance(target, ast.Constant)
                    and isinstance(target.value, str)
                ):
                    resolved_target = target.value
                elif key is None:
                    resolved_target = (
                        _SourceFacadeReexportResolver._dict_fromkeys_target(target, name) or resolved_target
                    )
            return resolved_target
        return None

    @staticmethod
    def _dict_fromkeys_target(node: ast.AST, name: str) -> str | None:
        """Resolve one literal ``dict.fromkeys((names), module)`` table entry."""
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Attribute)
            or node.func.attr != "fromkeys"
            or not isinstance(node.func.value, ast.Name)
            or node.func.value.id != "dict"
            or len(node.args) != 2
        ):
            return None
        names, target = node.args
        if not isinstance(names, (ast.Tuple, ast.List)) or not (
            isinstance(target, ast.Constant) and isinstance(target.value, str)
        ):
            return None
        if any(isinstance(item, ast.Constant) and item.value == name for item in names.elts):
            return target.value
        return None


def _authored_message_call_hash(node: ast.Call) -> str:
    """Return a location-free source identity for one complete constructor call."""
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode(_UTF_8)).hexdigest()


def _authored_message_argument(node: ast.Call) -> ast.expr | None:
    """Return the direct message argument supplied by a registered error call."""
    if node.args:
        return node.args[0]
    return next((keyword.value for keyword in node.keywords if keyword.arg in _MESSAGE_KEYWORDS), None)


class _AuthoredMessageVisitor(ast.NodeVisitor):
    """Resolve direct error constructors in one module without executing it."""

    def __init__(
        self,
        *,
        path: str,
        module: str,
        is_package: bool,
        registered_qualnames: frozenset[str],
        facade_reexports: _SourceFacadeReexportResolver,
    ) -> None:
        self.path = path
        self.module = module
        self.is_package = is_package
        self._known_qualnames = registered_qualnames | {_CADRUMO_ERROR_QUALNAME}
        self._facade_reexports = facade_reexports
        self._scopes: list[dict[str, _ErrorReference]] = [{}]
        self._symbols: list[str] = []
        self._classes: list[_ErrorReference] = []
        self.records: list[AuthoredErrorMessageSite] = []

    @property
    def _symbol(self) -> str:
        return ".".join(self._symbols) if self._symbols else MODULE_SYMBOL

    @property
    def _scope(self) -> dict[str, _ErrorReference]:
        return self._scopes[-1]

    def _lookup(self, name: str) -> _ErrorReference:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return _EMPTY_ERROR_REFERENCE

    def _resolve(self, node: ast.AST) -> _ErrorReference:
        if isinstance(node, ast.Name):
            return self._lookup(node.id)
        if isinstance(node, ast.Attribute):
            base = self._resolve(node.value)
            direct_errors = frozenset(
                candidate for module in base.modules if (candidate := f"{module}.{node.attr}") in self._known_qualnames
            )
            reexported = tuple(self._facade_reexports.resolve(module, node.attr) for module in base.modules)
            errors = direct_errors | frozenset(owner for reference in reexported for owner in reference.error_qualnames)
            if (
                not errors
                and self._facade_reexports.is_possible_registered_name(node.attr)
                and any(self._facade_reexports.is_source_module(module) for module in base.modules)
            ):
                raise AuthoredErrorMessageCensusError(
                    "authored-message census cannot resolve possible registered-error "
                    f"facade attribute {ast.unparse(node)} in {self.path}",
                )
            return _ErrorReference(
                error_qualnames=errors,
                modules=(
                    frozenset(f"{module}.{node.attr}" for module in base.modules)
                    | frozenset(module for reference in reexported for module in reference.modules)
                ),
            )
        return _EMPTY_ERROR_REFERENCE

    def _bind_target(self, target: ast.expr, reference: _ErrorReference) -> None:
        if isinstance(target, ast.Name):
            self._scope[target.id] = reference
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self._bind_target(element, _EMPTY_ERROR_REFERENCE)

    def _record(self, node: ast.Call, owners: frozenset[str]) -> None:
        message = _authored_message_argument(node)
        if message is None:
            return
        self.records.append(
            AuthoredErrorMessageSite(
                path=self.path,
                enclosing_symbol=self._symbol,
                callee=ast.unparse(node.func),
                message_expression=ast.unparse(message),
                normalized_call_sha256=_authored_message_call_hash(node),
                ordinal=0,
                line=node.lineno,
                column=node.col_offset,
                owner_qualnames=tuple(sorted(owners - {_CADRUMO_ERROR_QUALNAME})),
            ),
        )

    def _super_owner(self, node: ast.Call) -> frozenset[str] | None:
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "__init__" or not self._classes:
            return None
        receiver = node.func.value
        direct_super = (
            isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Name) and receiver.func.id == "super"
        )
        cast_super = (
            isinstance(receiver, ast.Call)
            and isinstance(receiver.func, ast.Name)
            and receiver.func.id == "cast"
            and len(receiver.args) == 2
            and isinstance(receiver.args[1], ast.Call)
            and isinstance(receiver.args[1].func, ast.Name)
            and receiver.args[1].func.id == "super"
        )
        if direct_super or cast_super:
            owners = self._classes[-1].error_qualnames
            return owners or None
        return None

    @override
    def visit_Import(self, node: ast.Import) -> None:
        for imported in node.names:
            name = imported.asname or imported.name.split(".")[0]
            module = imported.name if imported.asname else imported.name.split(".")[0]
            self._scope[name] = _ErrorReference(modules=frozenset({module}))

    @override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        source = _authored_message_import_module(
            module=self.module,
            is_package=self.is_package,
            level=node.level,
            imported=node.module,
        )
        for imported in node.names:
            if imported.name == "*":
                for qualname in self._known_qualnames:
                    if qualname.rpartition(".")[0] == source:
                        self._scope[qualname.rpartition(".")[2]] = _ErrorReference(
                            error_qualnames=frozenset({qualname}),
                        )
                continue
            name = imported.asname or imported.name
            candidate = f"{source}.{imported.name}"
            reexported = self._facade_reexports.resolve(source, imported.name)
            errors = (
                frozenset({candidate}) if candidate in self._known_qualnames else frozenset()
            ) | reexported.error_qualnames
            if (
                not errors
                and self._facade_reexports.is_possible_registered_name(imported.name)
                and self._facade_reexports.is_source_module(source)
            ):
                raise AuthoredErrorMessageCensusError(
                    "authored-message census cannot resolve possible registered-error "
                    f"facade import {source}.{imported.name} in {self.path}",
                )
            self._scope[name] = _ErrorReference(
                error_qualnames=errors,
                modules=frozenset({candidate}) | reexported.modules,
            )

    @override
    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        reference = self._resolve(node.value)
        for target in node.targets:
            self._bind_target(target, reference)

    @override
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)
            self._bind_target(node.target, self._resolve(node.value))

    @override
    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self._bind_target(node.target, self._resolve(node.value))

    @override
    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        before = self._scope.copy()
        for statement in node.body:
            self.visit(statement)
        body = self._scope.copy()
        self._scopes[-1] = before.copy()
        for statement in node.orelse:
            self.visit(statement)
        otherwise = self._scope.copy()
        merged: dict[str, _ErrorReference] = {}
        for name in set(before) | set(body) | set(otherwise):
            baseline = before.get(name, _EMPTY_ERROR_REFERENCE)
            left = body.get(name, baseline)
            right = otherwise.get(name, baseline)
            merged[name] = left.merged(right)
        self._scopes[-1] = merged

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._scope[node.name] = _EMPTY_ERROR_REFERENCE
        for decorator in node.decorator_list:
            self.visit(decorator)
        self._symbols.append(node.name)
        parameters = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
        scope = {parameter.arg: _EMPTY_ERROR_REFERENCE for parameter in parameters}
        if node.args.vararg is not None:
            scope[node.args.vararg.arg] = _EMPTY_ERROR_REFERENCE
        if node.args.kwarg is not None:
            scope[node.args.kwarg.arg] = _EMPTY_ERROR_REFERENCE
        self._scopes.append(scope)
        for statement in node.body:
            self.visit(statement)
        self._scopes.pop()
        self._symbols.pop()

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    @override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualname = f"{self.module}.{node.name}"
        reference = _ErrorReference(
            error_qualnames=frozenset({qualname}) if qualname in self._known_qualnames else frozenset(),
        )
        self._scope[node.name] = reference
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        self._symbols.append(node.name)
        self._classes.append(reference)
        self._scopes.append({})
        for statement in node.body:
            self.visit(statement)
        self._scopes.pop()
        self._classes.pop()
        self._symbols.pop()

    @override
    def visit_Call(self, node: ast.Call) -> None:
        super_owner = self._super_owner(node)
        if super_owner is not None:
            self._record(node, super_owner)
        else:
            resolved = self._resolve(node.func)
            if resolved.error_qualnames:
                self._record(node, resolved.error_qualnames)
        self.generic_visit(node)


def authored_error_message_join(
    *,
    root: Path = REPO_ROOT,
    codes: Iterable[RegisteredErrorCode] | None = None,
) -> AuthoredErrorMessageJoin:
    """Mechanically join every production message constructor to live registry code(s).

    The scan covers every non-test Python module below ``src/cadrumo`` and
    fails closed on unreadable, undecodable, or unparsable input.  It neither
    imports producers nor infers a code from error prose: every owner comes
    from the existing registry declaration and direct AST name resolution.
    """
    registered = tuple(codes) if codes is not None else registered_error_codes()
    by_qualname: dict[str, RegisteredErrorCode] = {}
    for record in registered:
        if record.error_qualname in by_qualname:
            raise AuthoredErrorMessageCensusError(
                f"authored-message census has duplicate registered qualname: {record.error_qualname}",
            )
        by_qualname[record.error_qualname] = record

    module_sources = _authored_message_sources(root)
    module_trees: dict[str, tuple[ast.Module, bool]] = {}
    parsed_sources: list[tuple[str, ast.Module, str, bool]] = []
    for path, source, module, is_package in module_sources:
        if module in module_trees:
            raise AuthoredErrorMessageCensusError(
                f"authored-message census found duplicate production module: {module}",
            )
        tree = ast.parse(source, filename=path)
        module_trees[module] = (tree, is_package)
        parsed_sources.append((path, tree, module, is_package))

    facade_reexports = _SourceFacadeReexportResolver(
        modules=module_trees,
        registered_qualnames=frozenset(by_qualname),
    )
    raw_sites: list[AuthoredErrorMessageSite] = []
    for path, tree, module, is_package in parsed_sources:
        visitor = _AuthoredMessageVisitor(
            path=path,
            module=module,
            is_package=is_package,
            registered_qualnames=frozenset(by_qualname),
            facade_reexports=facade_reexports,
        )
        visitor.visit(tree)
        raw_sites.extend(visitor.records)

    grouped: dict[tuple[str, str, str, str, str], list[AuthoredErrorMessageSite]] = {}
    for site in raw_sites:
        group = (
            site.path,
            site.enclosing_symbol,
            site.callee,
            site.message_expression,
            site.normalized_call_sha256,
        )
        grouped.setdefault(group, []).append(site)
    numbered: list[AuthoredErrorMessageSite] = []
    for group in grouped.values():
        for ordinal, site in enumerate(sorted(group, key=lambda item: (item.line, item.column)), start=1):
            numbered.append(
                AuthoredErrorMessageSite(
                    path=site.path,
                    enclosing_symbol=site.enclosing_symbol,
                    callee=site.callee,
                    message_expression=site.message_expression,
                    normalized_call_sha256=site.normalized_call_sha256,
                    ordinal=ordinal,
                    line=site.line,
                    column=site.column,
                    owner_qualnames=site.owner_qualnames,
                ),
            )
    return AuthoredErrorMessageJoin(
        registered_codes=tuple(sorted(registered, key=lambda record: (record.error_qualname, record.code))),
        sites=tuple(sorted(numbered, key=lambda site: (site.fingerprint, site.line, site.column))),
    )


def main(argv: list[str] | None = None) -> int:
    """Print the S01 ledger or an explicit fixed-point diagnostic snapshot."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("revision", help="Git revision to census; use an immutable commit when citing output")
    parser.add_argument("--json", action="store_true", help="emit candidate records as JSON")
    parser.add_argument(
        "--fixed-point",
        action="store_true",
        help="run the complete fixed-point observation pass from the seed state",
    )
    parser.add_argument(
        "--close-fixed-point",
        action="store_true",
        help="fail unless the complete fixed-point pass has no unadmitted discoveries",
    )
    parser.add_argument(
        "--state",
        type=Path,
        help="load a reviewed fixed-point JSON-v1 state before observing",
    )
    parser.add_argument(
        "--write-state",
        type=Path,
        help="write the resulting reviewed fixed-point JSON-v1 state",
    )
    parser.add_argument(
        "--admit-observed",
        action="store_true",
        help="explicitly admit this pass's cluster keys, then rescan once",
    )
    parser.add_argument(
        "--admit-alias",
        action="append",
        default=[],
        metavar="TOKEN",
        help="promote one locally evidenced action alias into the next scan vocabulary; repeatable",
    )
    arguments = parser.parse_args(argv)
    if arguments.close_fixed_point and not arguments.fixed_point:
        parser.error("--close-fixed-point requires --fixed-point")
    if (
        arguments.state or arguments.write_state or arguments.admit_observed or arguments.admit_alias
    ) and not arguments.fixed_point:
        parser.error("--state, --write-state, --admit-observed, and --admit-alias require --fixed-point")
    if arguments.fixed_point:
        state = (
            read_fixed_point_state(arguments.state)
            if arguments.state
            else initial_fixed_point_state(arguments.revision)
        )
        result = fixed_point_pass(arguments.revision, state)
        if arguments.admit_observed:
            state = admit_observed(state, result.newly_observed)
        if arguments.admit_alias:
            state = admit_aliases(state, arguments.admit_alias, result.discoveries)
        if arguments.admit_observed or arguments.admit_alias:
            result = fixed_point_pass(arguments.revision, state)
        if arguments.close_fixed_point:
            close_fixed_point(result)
        if arguments.write_state:
            write_fixed_point_state(arguments.write_state, result.state)
        snapshot = {
            "revision": arguments.revision,
            "state": dump_fixed_point_state(result.state),
            "candidate_count": len(result.candidates),
            "discovery_count": len(result.discoveries),
            "newly_observed": [asdict(record) | {"key": record.key} for record in result.newly_observed],
            "unknown_clusters": [asdict(record) | {"key": record.key} for record in result.unknown_clusters],
        }
        if arguments.json:
            print(json.dumps(snapshot, indent=2))
            return 0
        print(f"revision {arguments.revision}")
        print(f"action-guidance candidates {snapshot['candidate_count']}")
        print(f"fixed-point discoveries {snapshot['discovery_count']}")
        print(f"unadmitted discoveries {len(result.newly_observed)}")
        print(f"unknown clusters {len(result.unknown_clusters)}")
        return 0
    records = census(arguments.revision)
    if arguments.json:
        print(
            json.dumps(
                {
                    "revision": arguments.revision,
                    "candidate_count": len(records),
                    "candidates": [asdict(record) | {"key": record.key} for record in records],
                },
                indent=2,
            ),
        )
        return 0
    print(f"revision {arguments.revision}")
    print(f"action-guidance candidates {len(records)}")
    for record in records:
        print(
            f"{record.path}:{record.line}:{record.column}  {record.role}  "
            f"{record.enclosing_symbol}  {record.alias}={record.action_identity!r}",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
