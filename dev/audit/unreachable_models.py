"""Typed reachability findings, outcomes and parsed-module records."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final


class UnreachableCodeOutcome(StrEnum):
    """The three honest states the scan can land in."""

    CLEAN = "clean"
    FINDINGS = "findings"
    ERROR = "error"


class ModuleReach(StrEnum):
    """How far the entrypoint walk got to a reported module.

    ``UNREACHABLE`` means no root reaches it at all. ``MODULE_EXEC_ONLY`` means
    only a ``python -m`` surface does, never a console script -- an installed
    user can run it, but no product command leads there, so it is a weaker
    kind of alive worth seeing separately. ``TYPE_ONLY`` means only an
    ``if TYPE_CHECKING:`` import names it, which does not execute.
    """

    UNREACHABLE = "unreachable"
    MODULE_EXEC_ONLY = "module-exec-only"
    TYPE_ONLY = "type-only"


class SymbolKind(StrEnum):
    """The definition families the symbol layer inspects."""

    FUNCTION = "function"
    CLASS = "class"
    CONSTANT = "constant"
    METHOD = "method"
    ATTRIBUTE = "attribute"
    ENUM_MEMBER = "enum-member"


class Confidence(StrEnum):
    """How much a finding can be trusted before a human or agent looks.

    ``EXACT`` findings are resolved through the import graph: an unreachable
    module, or a top-level symbol whose every way in was checked and found
    absent. Act on these first. ``NAME_MATCH`` findings are methods, reached
    by attribute access the scan cannot bind to a type, so a same-named live
    method elsewhere hides a real use. ``NAME_MATCH_DATA`` findings are class
    attributes and enum members, which additionally may be reached through
    serialisation, ORM mapping, or registry data; the shipped data corpus is
    consulted for them, but a computed name still escapes it.
    """

    EXACT = "exact"
    NAME_MATCH = "name-match"
    NAME_MATCH_DATA = "name-match-data"


_KIND_CONFIDENCE: Final[dict[SymbolKind, Confidence]] = {
    SymbolKind.FUNCTION: Confidence.EXACT,
    SymbolKind.CLASS: Confidence.EXACT,
    SymbolKind.CONSTANT: Confidence.EXACT,
    SymbolKind.METHOD: Confidence.NAME_MATCH,
    SymbolKind.ATTRIBUTE: Confidence.NAME_MATCH_DATA,
    SymbolKind.ENUM_MEMBER: Confidence.NAME_MATCH_DATA,
}


# Weakest-wins ordering, so a composite finding inherits its softest evidence.
_CONFIDENCE_ORDER: Final[dict[Confidence, int]] = {
    Confidence.EXACT: 0,
    Confidence.NAME_MATCH: 1,
    Confidence.NAME_MATCH_DATA: 2,
}


_CONFIDENCE_BY_ORDER: Final[dict[int, Confidence]] = {rank: tier for tier, rank in _CONFIDENCE_ORDER.items()}


_TOP_LEVEL_KINDS: Final[frozenset[SymbolKind]] = frozenset(
    {SymbolKind.FUNCTION, SymbolKind.CLASS, SymbolKind.CONSTANT},
)


_DATA_SHAPED_KINDS: Final[frozenset[SymbolKind]] = frozenset(
    {SymbolKind.ATTRIBUTE, SymbolKind.ENUM_MEMBER},
)


@dataclass(frozen=True)
class ModuleFinding:
    """A shipped module, or a whole package folder, the entrypoints never reach.

    ``spanned_modules`` is 1 for a single module and the member count for a
    package folder whose every module is unreachable and is reported once.

    ``importers`` names the shipped modules outside this finding's own span
    that still import it. It separates two shapes that are identical in the
    reach categories: a module nothing imports at all, and a module whose
    importers exist but are themselves unreached. The scan states the fact;
    what a consumer makes of it is the consumer's disposition.
    """

    path: str
    module: str
    reach: ModuleReach
    spanned_modules: int
    used_by: tuple[str, ...]
    importers: tuple[str, ...] = ()

    @property
    def is_package(self) -> bool:
        """Whether this finding stands for a whole folder."""
        return self.spanned_modules > 1 or self.path.endswith("/")

    @property
    def confidence(self) -> Confidence:
        """Module findings come from resolved imports and are exact."""
        return Confidence.EXACT

    @property
    def id(self) -> str:
        """Stable identifier an agent can track a finding by across runs."""
        return f"module:{self.module}"


@dataclass(frozen=True)
class SymbolFinding:
    """A definition inside a reachable module that shipped code never references."""

    path: str
    line: int
    kind: SymbolKind
    name: str
    qualname: str
    used_by: tuple[str, ...]
    module: str = ""

    @property
    def confidence(self) -> Confidence:
        """Name-matched, and weaker still for data-shaped kinds."""
        return _KIND_CONFIDENCE[self.kind]

    @property
    def id(self) -> str:
        """Stable identifier an agent can track a finding by across runs."""
        return f"symbol:{self.module}:{self.qualname}"


@dataclass(frozen=True)
class TestFinding:
    """A test module whose every shipped subject is itself a finding.

    ``subjects`` lists what it imports from the shipped tree, as module names
    or ``module:name`` pairs; every one of them is unreachable or unused, so
    the test exists only to keep dead code exercised. The finding is only as
    strong as its weakest subject: a test standing on an unreachable module is
    exact, one standing on a name-matched member inherits that weaker tier.
    """

    path: str
    module: str
    subjects: tuple[str, ...]
    confidence: Confidence = Confidence.EXACT

    @property
    def id(self) -> str:
        """Stable identifier an agent can track a finding by across runs."""
        return f"test:{self.module}"


@dataclass(frozen=True)
class UnreachableCodeResult:
    """The scan's typed outcome.

    Construct through :meth:`clean`, :meth:`from_findings`, or :meth:`error`
    so each outcome is bound to its evidence by construction.
    """

    outcome: UnreachableCodeOutcome
    roots: tuple[str, ...] = ()
    shipped_modules: int = 0
    reachable_modules: int = 0
    modules: tuple[ModuleFinding, ...] = ()
    symbols: tuple[SymbolFinding, ...] = ()
    tests: tuple[TestFinding, ...] = ()
    data_cleared: int = 0
    dev_cleared: int = 0
    reason: str = ""

    def __post_init__(self) -> None:
        """Refuse a count of reachable modules larger than the shipped total.

        ``reachable_modules`` is ``len(runtime_reach & audited_names)`` and
        ``shipped_modules`` is ``len(audited_names)``, so the first is a subset
        count of the second and cannot exceed it. Nothing enforced that: the
        record is a plain frozen dataclass, and its three constructors take both
        numbers as parameters, so a caller could hand over any pair. The headline
        renders them together -- "99/10 shipped modules reachable at runtime" --
        which is self-refuting on one line and misstates the coverage an operator
        reads. Equality is NOT asserted: an allowlisted or frozen module can be
        unreachable without producing a finding, so a clean scan may legitimately
        report fewer reachable modules than shipped.
        """
        if self.reachable_modules > self.shipped_modules:
            message = (
                f"reachable_modules is {self.reachable_modules}, above the {self.shipped_modules} shipped "
                "module(s) it is counted from; reachable modules are a subset of the audited total"
            )
            raise ValueError(message)

    @classmethod
    def clean(
        cls,
        *,
        roots: tuple[str, ...],
        shipped_modules: int,
        reachable_modules: int,
        data_cleared: int = 0,
        dev_cleared: int = 0,
    ) -> UnreachableCodeResult:
        """A complete scan with no findings in its reported population."""
        return cls(
            outcome=UnreachableCodeOutcome.CLEAN,
            roots=roots,
            shipped_modules=shipped_modules,
            reachable_modules=reachable_modules,
            data_cleared=data_cleared,
            dev_cleared=dev_cleared,
        )

    @classmethod
    def from_findings(
        cls,
        *,
        roots: tuple[str, ...],
        shipped_modules: int,
        reachable_modules: int,
        modules: tuple[ModuleFinding, ...],
        symbols: tuple[SymbolFinding, ...],
        tests: tuple[TestFinding, ...] = (),
        data_cleared: int = 0,
        dev_cleared: int = 0,
    ) -> UnreachableCodeResult:
        """A scan that found unreachable modules, unused symbols, or orphaned tests."""
        if not modules and not symbols:
            msg = "from_findings requires at least one module or symbol finding"
            raise ValueError(msg)
        return cls(
            outcome=UnreachableCodeOutcome.FINDINGS,
            roots=roots,
            shipped_modules=shipped_modules,
            reachable_modules=reachable_modules,
            modules=modules,
            symbols=symbols,
            tests=tests,
            data_cleared=data_cleared,
            dev_cleared=dev_cleared,
        )

    @classmethod
    def error(cls, reason: str) -> UnreachableCodeResult:
        """A scan that could not produce a trustworthy result; ``reason`` says why."""
        return cls(outcome=UnreachableCodeOutcome.ERROR, reason=reason)

    @property
    def is_green(self) -> bool:
        """Whether this result honestly earns a GREEN verdict."""
        return self.outcome is UnreachableCodeOutcome.CLEAN

    @property
    def exact_findings(self) -> tuple[_Finding, ...]:
        """Every finding resolved through the import graph, safe to act on first."""
        ordered: tuple[_Finding, ...] = self.modules + self.tests + self.symbols
        return tuple(finding for finding in ordered if finding.confidence is Confidence.EXACT)

    @property
    def unreachable_module_total(self) -> int:
        """Modules (not findings) the runtime walk never reaches, folders expanded."""
        return sum(f.spanned_modules for f in self.modules if f.reach is ModuleReach.UNREACHABLE)

    @property
    def module_exec_only_total(self) -> int:
        """Modules only a ``python -m`` surface reaches, never a console script."""
        return sum(f.spanned_modules for f in self.modules if f.reach is ModuleReach.MODULE_EXEC_ONLY)

    @property
    def type_only_module_total(self) -> int:
        """Modules reached only through ``TYPE_CHECKING`` imports."""
        return sum(f.spanned_modules for f in self.modules if f.reach is ModuleReach.TYPE_ONLY)

    def headline(self) -> str:
        """One-line human summary of the outcome."""
        if self.outcome is UnreachableCodeOutcome.ERROR:
            return f"unreachable-code signal unavailable this cycle: {self.reason}"
        coverage = f"{self.reachable_modules}/{self.shipped_modules} shipped modules reachable at runtime"
        if self.outcome is UnreachableCodeOutcome.CLEAN:
            return f"no reachability findings ({coverage})"
        return (
            f"{self.unreachable_module_total} unreachable module(s), "
            f"{self.module_exec_only_total} module-exec-only, "
            f"{self.type_only_module_total} type-only module(s), "
            f"{len(self.symbols)} unused-symbol candidate(s) in reachable modules, "
            f"{len(self.tests)} orphaned test module(s) ({coverage})"
        )


# ---------------------------------------------------------------------------
# Shipped-tree census
# ---------------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class ShippedModule:
    """One parsed module of the shipped tree, with the facts the walks need."""

    name: str
    path: Path
    is_package: bool
    tree: ast.Module


@dataclass(frozen=True)
class _Definition:
    name: str
    qualname: str
    line: int
    kind: SymbolKind
    owner: str = ""
    #: The string literal the member assigns, when it assigns one. A registry
    #: declaration addresses a StrEnum member by this VALUE, never by the
    #: member name, so the data consult cannot see the binding without it.
    value: str = ""


# ---------------------------------------------------------------------------
# Outside corpus: labels only
# ---------------------------------------------------------------------------


@dataclass
class _OutsideUse:
    names: dict[str, set[str]] = field(default_factory=dict)
    modules: dict[str, set[str]] = field(default_factory=dict)
    resolved: dict[tuple[str, str], set[str]] = field(default_factory=dict)
    """Corpus labels keyed by the ``(defining module, symbol)`` pair they reach.

    ``names`` is a bare-token index: :func:`_references` harvests attribute
    names, keyword-argument names and identifiers spelled inside strings, none
    of which say which module defined the name. That looseness is harmless
    while a label only ANNOTATES a finding, and unacceptable once a label
    CLEARS one -- a coincidental ``verbose=`` kwarg in a dev script would
    silence a genuinely orphaned ``verbose`` constant. This index is built with
    :func:`resolved_symbol_uses` instead, so a clear requires the one thing that
    proves a real cross-module reach: a ``from M import N`` or an attribute read
    on a binding that names ``M``.
    """
    unreadable: list[str] = field(default_factory=list)
    """Files skipped during the reference walk, and therefore never consulted.

    A skipped file's references are not seen, so every symbol only IT used
    looks unreferenced and is reported as dead. The skip is deliberate - this
    tree is edited while the audit runs and a file can vanish mid-scan - but a
    silent skip means the findings were computed over an incomplete corpus with
    nothing saying so.
    """

    def labels_for_name(self, name: str) -> tuple[str, ...]:
        return tuple(sorted(self.names.get(name, ())))

    def labels_for_module(self, name: str) -> tuple[str, ...]:
        return tuple(sorted(self.modules.get(name, ())))

    def resolved_labels(self, module: str, name: str) -> tuple[str, ...]:
        """Labels of corpora that reach ``name`` as a resolved import or attribute."""
        return tuple(sorted(self.resolved.get((module, name), ())))


type _Finding = ModuleFinding | SymbolFinding | TestFinding
