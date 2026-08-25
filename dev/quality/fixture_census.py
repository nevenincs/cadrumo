"""Fail-closed AST census of every pytest fixture in the maintained tree.

The fixture-canonicalization campaign must start from the source population,
not a hand-maintained list of familiar ``conftest.py`` files.  This module
walks root ``conftest.py`` plus ``src``, ``dev``, and ``packaging`` and reports
every statically recognisable pytest fixture.  ``src/cadrumo/_data`` is bundled
registry data rather than Python test-harness source and is deliberately out
of scope.

The census is intentionally descriptive.  A matching normalized body digest
is candidate evidence for a later review, never a conclusion that two fixture
owners are substitutable: scope, autouse, dependencies, decorator parameters,
and topology-visible consumer candidates remain in the record.

Raw source-text counts are deliberately not treated as fixture counts.  In the
current tree, the ``@pytest.fixture`` text pattern also appears in the teaching
docstring at ``src/cadrumo/tests/settings_scope.py:59``; it is not a decorator
AST node and cannot register a fixture.  The AST census therefore excludes
that specimen while retaining actual nested decorator nodes.

Unlike a best-effort grep, included Python that cannot be read or parsed makes
the census fail.  A partial fixture universe looks authoritative while hiding
the exact source that needs review.

A fixture can also be produced indirectly: a factory function returns an
``@pytest.fixture``-decorated closure, and a module binds that closure to a
name through a plain call assignment (``_runtime_profile =
some_factory(...)``).  The assignment carries no decorator, so the walk above
cannot see it, and such a fixture would otherwise be absent from the census
entirely.  ``FactoryFixtureCandidate`` records the bindings whose callee
resolves to an in-tree factory.

Bindings whose callee cannot be followed are counted rather than recorded.
Most module-level call assignments construct ordinary values, so listing them
as fixture candidates would name a large population after a property almost
none of it has.  The count is still reported, because it is this walk's honest
bound: a factory reached through an unresolvable callee sits inside it.

Usage::

    python -m dev.quality.fixture_census
    python -m dev.quality.fixture_census --json
    python -m dev.quality.fixture_census --root Y:/code/aeat-worktrees/main
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Final

from cadrumo.core import DirectoryEntryKind, scan_directory

from .._paths import REPO_ROOT, UTF_8

_UTF_8: Final[str] = UTF_8
_SOURCE_ROOTS: Final[tuple[str, ...]] = ("src", "dev", "packaging")
_ROOT_CONFTEXT: Final[str] = "conftest.py"
_EXCLUDED_PREFIX: Final[Path] = Path("src/cadrumo/_data")
_DEFAULT_SCOPE: Final[str] = "function"


class FixtureCensusError(RuntimeError):
    """Raised when the census cannot establish its complete source universe."""


@dataclass(frozen=True, slots=True)
class FixtureParameter:
    """One Python parameter whose shape constrains a fixture's lifecycle."""

    name: str
    kind: str
    annotation: str | None
    default: str | None


@dataclass(frozen=True, slots=True)
class FixtureDecorator:
    """The fixture decorator and every semantically relevant keyword shape."""

    callee: str
    form: str
    expression: str
    scope: str
    scope_expression: str | None
    autouse: bool
    autouse_expression: str | None
    name_expression: str | None
    params_expression: str | None
    keyword_arguments: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class FixtureConsumer:
    """A topology-visible direct consumer candidate for one fixture name.

    This is deliberately a *candidate*, not a claim of pytest's final fixture
    resolution.  Nested ``conftest.py`` files can shadow the same name; the
    record preserves every source-level claimant for later adjudication rather
    than quietly choosing one.
    """

    path: str
    line: int
    qualname: str
    kind: str
    via: str


@dataclass(frozen=True, slots=True)
class FixtureImport:
    """One module-level binding that exposes a provider in file or conftest scope."""

    path: str
    line: int
    provider_module: str
    provider_name: str
    bound_name: str


@dataclass(frozen=True, slots=True)
class DynamicFixtureRequest:
    """A ``request.getfixturevalue`` consumer whose name needs later review."""

    path: str
    line: int
    qualname: str
    expression: str


@dataclass(frozen=True, slots=True)
class FactoryFixtureCandidate:
    """A module-level ``name = call(...)`` binding proven to come from a fixture factory.

    A factory returning an ``@pytest.fixture``-decorated closure produces a
    real, working fixture through exactly this shape, and the decorator-only
    walk that fills ``FixtureCensus.fixtures`` cannot see it: the assignment
    carries no decorator of its own. Such a binding is therefore a fixture the
    census would otherwise omit entirely.

    Membership requires a resolved factory, so every member genuinely is one.
    Assignments whose callee cannot be followed are counted, not recorded --
    see ``FixtureCensus.unresolved_call_assignment_count`` for why.
    """

    path: str
    line: int
    column: int
    bound_name: str
    callee_expression: str
    resolved_factory: str


@dataclass(frozen=True, slots=True)
class FixtureRecord:
    """The complete static identity and constraints of one fixture definition."""

    path: str
    line: int
    column: int
    qualname: str
    function_name: str
    effective_name: str
    owner_kind: str
    decorator: FixtureDecorator
    parameters: tuple[FixtureParameter, ...]
    dependencies: tuple[str, ...]
    body_ast_format: str
    normalized_body: str
    normalized_body_sha256: str
    imported_bindings: tuple[FixtureImport, ...]
    consumers: tuple[FixtureConsumer, ...]
    autouse_reach: tuple[FixtureConsumer, ...]
    #: Derived from the body by the census, which always sets it explicitly. The
    #: default exists for records built directly in tests, where a fixture that
    #: was never classified is by definition not a scaffold.
    body_performs_no_work: bool = False
    #: Digest of what the body's imported names actually RESOLVE to. An AST dump
    #: records the local name, so two bodies calling different functions that
    #: happen to share a name dump identically; this is what separates them.
    body_symbol_origins_sha256: str = ""


@dataclass(frozen=True, slots=True)
class AliasedBehaviour:
    """One fixture body reached through more than one effective name.

    This is the duplication a name-keyed comparison cannot express. Grouping
    fixtures by name asks "is this name declared twice"; a behaviour copied
    under a fresh name each time answers no every time, while a search for any
    one of those names returns a single site and reads as unique. Keying on the
    body inverts the question, and the answer is the set of names below.

    Aliasing is reported, never refused. Two sites may share a body and still
    differ in scope, autouse, or the module values they close over, so this is
    the population a reviewer must adjudicate -- not a verdict that they are
    interchangeable.

    Fixtures whose body carries no behaviour are excluded -- see
    :func:`_performs_no_work` for the two shapes and why each aliases by
    construction rather than by copying. They are counted separately instead of
    being dropped, because a reader comparing this figure across runs needs to
    see what the detector declined to consider.
    """

    body_sha256: str
    effective_names: tuple[str, ...]
    sites: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FixtureCensus:
    """A reproducible fixture population and the source files it measured."""

    root: str
    sources: tuple[str, ...]
    fixtures: tuple[FixtureRecord, ...]
    dynamic_fixture_requests: tuple[DynamicFixtureRequest, ...]
    factory_fixture_candidates: tuple[FactoryFixtureCandidate, ...]
    #: Module-level call assignments whose callee this walk could not follow.
    #:
    #: Overwhelmingly ordinary construction -- ``re.compile``, ``Decimal``,
    #: ``frozenset`` -- which is why these are counted rather than listed as
    #: fixture candidates: naming thousands of constants after a property
    #: almost none of them have would report something false. The number is
    #: still stated, because it is this walk's honest bound. A fixture factory
    #: reached through a callee the resolver cannot follow is inside it.
    unresolved_call_assignment_count: int

    @property
    def fixture_count(self) -> int:
        """Return the number of fixture definitions in the complete census."""
        return len(self.fixtures)

    @property
    def aliased_behaviours(self) -> tuple[AliasedBehaviour, ...]:
        """Return every fixture body reached through more than one name."""
        by_body: dict[tuple[str, str], list[FixtureRecord]] = {}
        for record in self.fixtures:
            if record.body_performs_no_work:
                continue
            # Keyed on the body AND on what its imported names resolve to: an
            # AST dump records the local name, so two bodies calling different
            # functions that share a name are otherwise indistinguishable.
            key = (record.normalized_body_sha256, record.body_symbol_origins_sha256)
            by_body.setdefault(key, []).append(record)
        return tuple(
            AliasedBehaviour(
                body_sha256=body,
                effective_names=tuple(sorted({record.effective_name for record in group})),
                sites=tuple(sorted(f"{record.path}:{record.line}" for record in group)),
            )
            for (body, _origins), group in sorted(by_body.items())
            if len({record.effective_name for record in group}) > 1
        )

    @property
    def aliased_behaviour_count(self) -> int:
        """Return how many distinct behaviours are reached through several names."""
        return len(self.aliased_behaviours)

    @property
    def behaviourless_fixtures(self) -> tuple[FixtureRecord, ...]:
        """Return every fixture excluded from aliasing for carrying no behaviour.

        Surfaced rather than silently discarded: these are a real population
        with a real shape, and a reader comparing the aliasing count across two
        runs needs to see what the detector chose not to consider.

        A NAMING inconsistency inside this population is still worth acting on --
        one role reached under two names is a real finding. It is simply not the
        finding the aliasing detector makes, which is that one BEHAVIOUR was
        copied. Read these as a vocabulary question, not a duplication one.
        """
        return tuple(
            sorted(
                (record for record in self.fixtures if record.body_performs_no_work),
                key=lambda record: (record.path, record.line),
            ),
        )

    @property
    def factory_fixture_candidate_count(self) -> int:
        """Return how many module-level bindings resolve to a fixture factory."""
        return len(self.factory_fixture_candidates)


@dataclass(frozen=True, slots=True)
class _FunctionFact:
    """One function-like source declaration used to link fixture consumers."""

    path: str
    line: int
    qualname: str
    owner_kind: str
    parameters: tuple[str, ...]
    usefixtures: tuple[str, ...]
    getfixturevalue: tuple[str, ...]
    is_fixture: bool
    is_test: bool


@dataclass(frozen=True, slots=True)
class _ConsumerReference:
    """One explicit fixture request indexed by its requested name and route."""

    function: _FunctionFact
    via: str


@dataclass(frozen=True, slots=True)
class _FunctionIndex:
    """Indexed function facts used by provider, import, and autouse joins."""

    explicit_by_name: dict[str, tuple[_ConsumerReference, ...]]
    tests_by_path: dict[str, tuple[_FunctionFact, ...]]
    tests_by_directory: dict[str, tuple[_FunctionFact, ...]]


@dataclass(frozen=True, slots=True)
class _FixtureDraft:
    """A fixture before consumer candidates have been joined to it."""

    record: FixtureRecord
    module: str
    is_conftest: bool
    conftest_directory: Path | None


@dataclass(frozen=True, slots=True)
class _ImportFact:
    """One static module import considered for fixture-provider linking."""

    path: str
    line: int
    provider_module: str
    provider_name: str
    bound_name: str


@dataclass(frozen=True, slots=True)
class _FactoryCandidateDraft:
    """A module-level call-assignment before its callee is joined to a factory."""

    path: str
    line: int
    column: int
    module: str
    bound_name: str
    callee_expression: str
    callee_name: str | None


@dataclass(frozen=True, slots=True)
class _FixtureFactoryFact:
    """One module-level function recognized as returning a nested fixture."""

    path: str
    line: int
    module: str
    function_name: str


def _relative_path(path: Path, root: Path) -> str:
    """Return a stable repository-relative POSIX path."""
    return path.relative_to(root).as_posix()


def _module_name(path: Path, root: Path) -> str:
    """Return the import-module spelling for an included source path."""
    relative = path.relative_to(root)
    parts = list(relative.with_suffix("").parts)
    if parts[0] == "src":
        parts = parts[1:]
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _import_base(module: str, path: Path) -> str:
    """Return the package against which a relative import in ``path`` resolves."""
    return module if path.name == "__init__.py" else module.rpartition(".")[0]


def _resolve_import_module(module: str, path: Path, node: ast.ImportFrom) -> str | None:
    """Resolve an ``ImportFrom`` module without importing user code."""
    if node.level == 0:
        return node.module
    parts = _import_base(module, path).split(".") if _import_base(module, path) else []
    if node.level > 1:
        parts = parts[: len(parts) - (node.level - 1)]
    target = ".".join(parts)
    if node.module:
        return f"{target}.{node.module}" if target else node.module
    return target or None


def _module_symbol_origins(tree: ast.Module, path: Path, root: Path) -> dict[str, str]:
    """Map each imported name in a module to the module that provides it.

    Two fixture bodies can dump to identical AST while calling entirely
    different functions, because the dump records the local NAME and not what
    that name resolves to. Two censuses in this tree do exactly that: one body
    calls a CLI-action census and another a tax-id respelling census, both
    spelled ``census("HEAD")`` and both imported from different modules. Without
    origins they group as one behaviour, which is a false positive that costs a
    reviewer a real investigation.
    """
    module = _module_name(path, root)
    origins: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            provider = _resolve_import_module(module, path, node)
            if provider is None:
                continue
            for alias in node.names:
                origins[alias.asname or alias.name] = f"{provider}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                origins[alias.asname or alias.name] = alias.name
    return origins


def _body_symbol_origins(body: list[ast.stmt], origins: dict[str, str]) -> tuple[tuple[str, str], ...]:
    """Return the resolved origin of every imported name this body references."""
    referenced = {node.id for statement in body for node in ast.walk(statement) if isinstance(node, ast.Name)}
    return tuple(sorted((name, origins[name]) for name in referenced if name in origins))


def iter_source_files(repo_root: Path = REPO_ROOT) -> tuple[Path, ...]:
    """Return the exact sorted source universe, refusing missing required roots."""
    root = repo_root.resolve()
    root_conftest = root / _ROOT_CONFTEXT
    if not root_conftest.is_file():
        raise FixtureCensusError(f"fixture census requires {_ROOT_CONFTEXT!r} at {root}")

    files = [root_conftest]
    for relative_root in _SOURCE_ROOTS:
        source_root = root / relative_root
        if not source_root.is_dir():
            raise FixtureCensusError(f"fixture census requires source root {relative_root!r} at {root}")
        files.extend(
            scan_directory(
                source_root,
                pattern="*.py",
                recursive=True,
                select=DirectoryEntryKind.FILES,
                prune_directories=("__pycache__",),
            )
        )

    included = [path for path in files if not _relative_path(path, root).startswith(f"{_EXCLUDED_PREFIX.as_posix()}/")]
    return tuple(sorted(set(included), key=lambda path: _relative_path(path, root)))


def _read_trees(paths: Iterable[Path], root: Path) -> dict[Path, ast.Module]:
    """Read and parse every included path, reporting all failures together."""
    trees: dict[Path, ast.Module] = {}
    failures: list[str] = []
    for path in paths:
        relative = _relative_path(path, root)
        try:
            source = path.read_text(encoding=_UTF_8)
        except OSError as exc:
            failures.append(f"unreadable included Python {relative}: {exc}")
            continue
        try:
            trees[path] = ast.parse(source, filename=relative)
        except SyntaxError as exc:
            failures.append(
                f"unparseable included Python {relative}:{exc.lineno}:{exc.offset}: {exc.msg}",
            )
    if failures:
        raise FixtureCensusError("fixture census refused incomplete input:\n" + "\n".join(sorted(failures)))
    return trees


def _dotted_name(node: ast.AST) -> str | None:
    """Return an attribute/name chain, or ``None`` for a dynamic expression."""
    match node:
        case ast.Name(id=name):
            return name
        case ast.Attribute(value=value, attr=attribute):
            prefix = _dotted_name(value)
            return f"{prefix}.{attribute}" if prefix else None
        case _:
            return None


def _expression(node: ast.AST | None) -> str | None:
    """Serialize an AST expression without source positions for stable comparison."""
    return ast.unparse(node) if node is not None else None


def _pytest_bindings(tree: ast.Module) -> tuple[frozenset[str], frozenset[str]]:
    """Return local pytest modules and direct fixture-decorator aliases.

    The fixture surface has two common static forms: ``pytest.fixture`` after
    importing the module, and a direct import such as ``from pytest import
    fixture as fx``.  Capturing aliases avoids both missing valid fixtures and
    treating an unrelated function named ``fixture`` as pytest infrastructure.
    """
    modules: set[str] = set()
    decorators: set[str] = set()
    for node in ast.walk(tree):
        match node:
            case ast.Import(names=names):
                for alias in names:
                    if alias.name in {"pytest", "pytest_asyncio"}:
                        modules.add(alias.asname or alias.name)
            case ast.ImportFrom(module=module, names=names) if module in {"pytest", "pytest_asyncio"}:
                for alias in names:
                    if alias.name == "fixture":
                        decorators.add(alias.asname or alias.name)
    return frozenset(modules), frozenset(decorators)


def _fixture_callee(
    decorator: ast.expr,
    *,
    pytest_modules: frozenset[str],
    fixture_aliases: frozenset[str],
) -> tuple[str, str, ast.Call | None] | None:
    """Recognize one supported pytest fixture decorator without importing it."""
    callee = decorator.func if isinstance(decorator, ast.Call) else decorator
    dotted = _dotted_name(callee)
    if dotted is None:
        return None
    form = "call" if isinstance(decorator, ast.Call) else "bare"
    call = decorator if isinstance(decorator, ast.Call) else None
    if dotted in fixture_aliases:
        return ("pytest.fixture", form, call)
    head, _, tail = dotted.partition(".")
    if head in pytest_modules and tail == "fixture":
        canonical = "pytest.fixture" if head != "pytest_asyncio" else "pytest_asyncio.fixture"
        return (canonical, form, call)
    return None


def _keyword_map(call: ast.Call | None) -> dict[str, ast.expr]:
    """Return explicit named decorator keywords, rejecting dynamic ``**kwargs``."""
    if call is None:
        return {}
    keywords: dict[str, ast.expr] = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            raise FixtureCensusError(
                f"fixture decorator at line {call.lineno} uses dynamic **kwargs; static constraints are incomplete",
            )
        keywords[keyword.arg] = keyword.value
    return keywords


def _performs_no_work(body: list[ast.stmt]) -> bool:
    """Return whether a fixture body carries no behaviour to share.

    Two shapes qualify, and both alias by CONSTRUCTION rather than by copying:

    A body that only ``raise``s is a required-override scaffold -- a default that
    exists to force the consuming module to supply its own. Every such scaffold
    in the tree normalises identically no matter what concept it scaffolds.

    A body that only hands back a module global -- ``return _BUCKET_ID`` -- is a
    value binding. It is the same AST in every module while the constant behind
    it differs in each, so reporting eleven per-module overrides as one
    duplicated behaviour inverts the truth: they are eleven DIFFERENT values
    wearing one trivial shape.

    The distinction is deliberately drawn at NAME versus LITERAL, not at
    "performs no call". ``return "fixed"`` is self-contained and identical
    wherever it appears, so three fixtures sharing it genuinely are one
    behaviour copied and MUST still be reported. Only the bare-name form defers
    its value to a per-module global and is therefore uninformative.

    Grouping either excluded kind reports absence of behaviour as duplication,
    and a detector that fires on non-duplicates is one reviewers learn to skip.
    """
    if not body:
        return False
    if all(isinstance(statement, ast.Raise) for statement in body):
        return True
    if len(body) != 1:
        return False
    only = body[0]
    return isinstance(only, ast.Return) and isinstance(only.value, ast.Name)


def _is_deferred_to_call_site(value: ast.expr, deferred_names: frozenset[str]) -> bool:
    """Return whether this value is an enclosing factory's parameter.

    Such a value is not unknowable, only not-yet-known: it is supplied where the
    factory is called, and that binding is censused in its own right. Treating it
    as dynamic refuses a correct factory; treating any non-literal as deferred
    would hide genuinely unmeasurable expressions, so only a bare parameter name
    qualifies.
    """
    return bool(deferred_names) and isinstance(value, ast.Name) and value.id in deferred_names


def _literal_string(
    value: ast.expr | None,
    *,
    field: str,
    line: int,
    where: str,
    deferred_names: frozenset[str] = frozenset(),
) -> str | None:
    """Return a static string or fail rather than inventing an effective value.

    ``where`` is the module being judged. Without it the refusal names a line
    number and nothing else, and a line number alone does not locate anything
    in a tree of 5,773 scanned files -- established by trying: six separate
    probes failed to name the offending module, including a subtree bisect that
    reported nothing because the census refuses a root with no ``conftest.py``
    and the filter swallowed that refusal. A gate that cannot say WHERE cannot
    be acted on.
    """
    if value is None:
        return None
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if _is_deferred_to_call_site(value, deferred_names):
        return None
    message = f"{where}:{line}: fixture {field} is dynamic; static census cannot state its effective value"
    raise FixtureCensusError(message)


def _literal_bool(
    value: ast.expr | None,
    *,
    field: str,
    line: int,
    default: bool,
    where: str,
    deferred_names: frozenset[str] = frozenset(),
) -> bool:
    """Return a static boolean or fail rather than silently applying a default.

    ``where`` names the module, for the reason :func:`_literal_string` states.
    """
    if value is None:
        return default
    if isinstance(value, ast.Constant) and isinstance(value.value, bool):
        return value.value
    if _is_deferred_to_call_site(value, deferred_names):
        return default
    message = f"{where}:{line}: fixture {field} is dynamic; static census cannot state its effective value"
    raise FixtureCensusError(message)


def _parameters(arguments: ast.arguments) -> tuple[FixtureParameter, ...]:
    """Capture positional, vararg, and keyword-only parameter constraints."""
    positional = (*arguments.posonlyargs, *arguments.args)
    defaults = (None,) * (len(positional) - len(arguments.defaults)) + tuple(arguments.defaults)
    rows: list[FixtureParameter] = []
    for index, (argument, default) in enumerate(zip(positional, defaults, strict=True)):
        kind = "positional_only" if index < len(arguments.posonlyargs) else "positional"
        rows.append(FixtureParameter(argument.arg, kind, _expression(argument.annotation), _expression(default)))
    if arguments.vararg is not None:
        rows.append(FixtureParameter(arguments.vararg.arg, "vararg", _expression(arguments.vararg.annotation), None))
    rows.extend(
        FixtureParameter(argument.arg, "keyword_only", _expression(argument.annotation), _expression(default))
        for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True)
    )
    if arguments.kwarg is not None:
        rows.append(FixtureParameter(arguments.kwarg.arg, "kwarg", _expression(arguments.kwarg.annotation), None))
    return tuple(rows)


def _executable_body(body: list[ast.stmt]) -> list[ast.stmt]:
    """Return function statements without a leading non-executable docstring."""
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def _usefixtures(decorators: Iterable[ast.expr]) -> tuple[str, ...]:
    """Return static fixture names declared through ``pytest.mark.usefixtures``."""
    names: list[str] = []
    for decorator in decorators:
        if not isinstance(decorator, ast.Call):
            continue
        dotted = _dotted_name(decorator.func)
        if dotted is None or not dotted.endswith(".mark.usefixtures"):
            continue
        for argument in decorator.args:
            if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
                raise FixtureCensusError(
                    f"pytest.mark.usefixtures at line {decorator.lineno} has a dynamic fixture name",
                )
            names.append(argument.value)
    return tuple(dict.fromkeys(names))


def _fixture_requests(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    path: str,
    qualname: str,
) -> tuple[tuple[str, ...], tuple[DynamicFixtureRequest, ...]]:
    """Return static and dynamic ``request.getfixturevalue`` evidence.

    A static string can join a provider directly.  Dynamic request names remain
    first-class census output rather than being quietly discarded or guessed;
    their producer must be read before an ownership manifest can claim closure.
    """
    static_names: list[str] = []
    dynamic: list[DynamicFixtureRequest] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if not (
            isinstance(child.func, ast.Attribute)
            and child.func.attr == "getfixturevalue"
            and isinstance(child.func.value, ast.Name)
            and child.func.value.id == "request"
        ):
            continue
        if not child.args:
            raise FixtureCensusError(f"request.getfixturevalue at {path}:{child.lineno} has no fixture-name argument")
        fixture_name = child.args[0]
        if isinstance(fixture_name, ast.Constant) and isinstance(fixture_name.value, str):
            static_names.append(fixture_name.value)
            continue
        dynamic.append(
            DynamicFixtureRequest(
                path=path,
                line=child.lineno,
                qualname=qualname,
                expression=_expression(fixture_name) or "<expression>",
            ),
        )
    return tuple(dict.fromkeys(static_names)), tuple(dynamic)


class _ModuleVisitor(ast.NodeVisitor):
    """Collect fixture drafts and runnable pytest function facts from one module."""

    def __init__(self, path: Path, root: Path, tree: ast.Module) -> None:
        self.path = path
        self.root = root
        self.pytest_modules, self.fixture_aliases = _pytest_bindings(tree)
        self.symbol_origins = _module_symbol_origins(tree, path, root)
        self.fixtures: list[_FixtureDraft] = []
        self.functions: list[_FunctionFact] = []
        self.dynamic_fixture_requests: list[DynamicFixtureRequest] = []
        self._qualname: list[str] = []
        self._class_depth = 0
        #: Fixtures nested inside a function are FACTORY TEMPLATES, not fixtures.
        #: pytest discovers module-level and class-level definitions; what a
        #: factory returns is discovered only where the caller binds it, and the
        #: census already resolves those bindings as factory-bound candidates.
        #: Reading the template as a definition asks a question it cannot answer
        #: -- its ``name`` and ``autouse`` are the factory's parameters, literal
        #: only at the call site -- and the fail-closed refusal then reports a
        #: correctly-written factory as an unmeasurable fixture.
        self._function_depth = 0
        #: Parameter names of the enclosing function, if any. Only these may be
        #: read as deferred-to-call-site; any other non-literal stays a refusal.
        self._enclosing_parameters: tuple[str, ...] = ()
        #: ``usefixtures`` names marked on the enclosing class chain, which every
        #: function inside inherits.
        self._class_usefixtures: tuple[str, ...] = ()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._qualname.append(node.name)
        self._class_depth += 1
        # A class-level ``usefixtures`` applies to every test the class holds, so
        # it is a real request from each of them. Reading only function
        # decorators made those requests invisible and let a fixture reached
        # ONLY that way report zero consumers -- which reads as dead code and is
        # the opposite of the truth. Nested classes inherit the outer mark, so
        # the stack accumulates rather than replaces.
        inherited = self._class_usefixtures
        self._class_usefixtures = (*inherited, *_usefixtures(node.decorator_list))
        self.generic_visit(node)
        self._class_usefixtures = inherited
        self._class_depth -= 1
        self._qualname.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        relative = _relative_path(self.path, self.root)
        qualname = ".".join((*self._qualname, node.name))
        fixture_decorator = next(
            (
                (decorator, found)
                for decorator in node.decorator_list
                if (
                    found := _fixture_callee(
                        decorator,
                        pytest_modules=self.pytest_modules,
                        fixture_aliases=self.fixture_aliases,
                    )
                )
                is not None
            ),
            None,
        )
        parameters = _parameters(node.args)
        declared_dependencies = tuple(parameter.name for parameter in parameters)
        usefixtures = tuple(
            dict.fromkeys((*self._class_usefixtures, *_usefixtures(node.decorator_list))),
        )
        requested_fixtures, dynamic_requests = _fixture_requests(node, path=relative, qualname=qualname)
        self.dynamic_fixture_requests.extend(dynamic_requests)
        is_fixture = fixture_decorator is not None
        owner_kind = "conftest" if self.path.name == _ROOT_CONFTEXT else ("class" if self._class_depth else "module")
        self.functions.append(
            _FunctionFact(
                path=relative,
                line=node.lineno,
                qualname=qualname,
                owner_kind=owner_kind,
                parameters=declared_dependencies,
                usefixtures=usefixtures,
                getfixturevalue=requested_fixtures,
                is_fixture=is_fixture,
                is_test=node.name.startswith("test"),
            ),
        )
        if fixture_decorator is not None:
            decorator_node, (callee, form, call) = fixture_decorator
            keywords = _keyword_map(call)
            # A fixture nested inside a function is a FACTORY TEMPLATE: pytest
            # discovers what the factory returns where the caller binds it, not
            # here, so `name` and `autouse` are legitimately the factory's own
            # parameters and are literal only at the call site. Refusing them
            # reports a correctly-written factory as unmeasurable. The template
            # keeps its own function name, the expression is preserved so the
            # dynamism stays visible, and the binding is resolved separately as
            # a factory-bound candidate.
            deferred = frozenset(self._enclosing_parameters) if self._function_depth else frozenset()
            judged = _relative_path(self.path, self.root)
            explicit_name = _literal_string(
                keywords.get("name"), field="name", line=node.lineno, where=judged, deferred_names=deferred
            )
            scope = (
                _literal_string(keywords.get("scope"), field="scope", line=node.lineno, where=judged) or _DEFAULT_SCOPE
            )
            autouse = _literal_bool(
                keywords.get("autouse"),
                field="autouse",
                line=node.lineno,
                default=False,
                where=judged,
                deferred_names=deferred,
            )
            decorator = FixtureDecorator(
                callee=callee,
                form=form,
                expression=_expression(decorator_node) or callee,
                scope=scope,
                scope_expression=_expression(keywords.get("scope")),
                autouse=autouse,
                autouse_expression=_expression(keywords.get("autouse")),
                name_expression=_expression(keywords.get("name")),
                params_expression=_expression(keywords.get("params")),
                keyword_arguments=tuple(
                    sorted((name, _expression(value) or "") for name, value in keywords.items()),
                ),
            )
            executable_body = _executable_body(node.body)
            normalized_body = ast.dump(
                ast.Module(body=executable_body, type_ignores=[]),
                annotate_fields=True,
                include_attributes=False,
            )
            body_performs_no_work = _performs_no_work(executable_body)
            symbol_origins = _body_symbol_origins(executable_body, self.symbol_origins)
            body_symbol_origins_sha256 = hashlib.sha256(
                json.dumps(symbol_origins, sort_keys=True).encode(_UTF_8),
            ).hexdigest()
            record = FixtureRecord(
                path=relative,
                line=node.lineno,
                column=node.col_offset,
                qualname=qualname,
                function_name=node.name,
                effective_name=explicit_name or node.name,
                owner_kind=owner_kind,
                decorator=decorator,
                parameters=parameters,
                dependencies=tuple(dict.fromkeys((*declared_dependencies, *usefixtures))),
                body_ast_format="python-ast-dump-v1",
                normalized_body=normalized_body,
                normalized_body_sha256=hashlib.sha256(normalized_body.encode(_UTF_8)).hexdigest(),
                imported_bindings=(),
                consumers=(),
                autouse_reach=(),
                body_performs_no_work=body_performs_no_work,
                body_symbol_origins_sha256=body_symbol_origins_sha256,
            )
            self.fixtures.append(
                _FixtureDraft(
                    record=record,
                    module=_module_name(self.path, self.root),
                    is_conftest=self.path.name == _ROOT_CONFTEXT,
                    conftest_directory=Path(relative).parent if self.path.name == _ROOT_CONFTEXT else None,
                ),
            )
        self._qualname.append(node.name)
        self._function_depth += 1
        outer_parameters = self._enclosing_parameters
        self._enclosing_parameters = tuple(parameter.name for parameter in parameters)
        self.generic_visit(node)
        self._enclosing_parameters = outer_parameters
        self._function_depth -= 1
        self._qualname.pop()


def _visible_to(fixture: _FixtureDraft, consumer: _FunctionFact) -> bool:
    """Return whether a consumer can see a fixture by static pytest topology."""
    provider = fixture.record
    if fixture.is_conftest:
        assert fixture.conftest_directory is not None
        return Path(consumer.path).is_relative_to(fixture.conftest_directory)
    if consumer.path != provider.path:
        return False
    if provider.owner_kind != "class":
        return True
    owner_prefix = provider.qualname.rsplit(".", 1)[0]
    return consumer.qualname.startswith(f"{owner_prefix}.")


def _import_facts(path: Path, root: Path, tree: ast.Module) -> tuple[_ImportFact, ...]:
    """Read module-level imported names without importing user code."""
    module = _module_name(path, root)
    relative = _relative_path(path, root)
    facts: list[_ImportFact] = []
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        provider_module = _resolve_import_module(module, path, node)
        if provider_module is None:
            continue
        for alias in node.names:
            facts.append(
                _ImportFact(
                    path=relative,
                    line=node.lineno,
                    provider_module=provider_module,
                    provider_name=alias.name,
                    bound_name=alias.asname or alias.name,
                ),
            )
    return tuple(facts)


def _module_level_factory_candidates(path: Path, root: Path, tree: ast.Module) -> tuple[_FactoryCandidateDraft, ...]:
    """Return every module-level ``name = call(...)`` assignment as a candidate.

    Pytest discovers fixtures by looking up names in a module's globals (or a
    class body), so only a top-level assignment can ever bind a name pytest
    would find.  A call assigned inside a function's local scope cannot become
    a fixture and is deliberately excluded rather than swelling the candidate
    population with unreachable local variables.
    """
    relative = _relative_path(path, root)
    module = _module_name(path, root)
    candidates: list[_FactoryCandidateDraft] = []
    for statement in tree.body:
        if not isinstance(statement, ast.Assign) or not isinstance(statement.value, ast.Call):
            continue
        callee_name = statement.value.func.id if isinstance(statement.value.func, ast.Name) else None
        for target in statement.targets:
            if not isinstance(target, ast.Name):
                continue
            candidates.append(
                _FactoryCandidateDraft(
                    path=relative,
                    line=statement.lineno,
                    column=statement.col_offset,
                    module=module,
                    bound_name=target.id,
                    callee_expression=_expression(statement.value.func) or "<expression>",
                    callee_name=callee_name,
                ),
            )
    return tuple(candidates)


def _fixture_factory_fact(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    path: str,
    module: str,
    pytest_modules: frozenset[str],
    fixture_aliases: frozenset[str],
) -> _FixtureFactoryFact | None:
    """Recognize the tree's known factory shape: define, then return, one nested fixture.

    Scoped to a straight-line body -- a nested ``@pytest.fixture`` closure and
    a bare ``return`` of its name, both as direct statements of the outer
    function.  A factory built with a different control-flow shape is not
    claimed here; its call sites stay unresolved candidates rather than a
    guessed match.
    """
    nested_fixture_names = {
        statement.name
        for statement in node.body
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(
            _fixture_callee(decorator, pytest_modules=pytest_modules, fixture_aliases=fixture_aliases) is not None
            for decorator in statement.decorator_list
        )
    }
    if not nested_fixture_names:
        return None
    returns_nested = any(
        isinstance(statement, ast.Return)
        and isinstance(statement.value, ast.Name)
        and statement.value.id in nested_fixture_names
        for statement in node.body
    )
    if not returns_nested:
        return None
    return _FixtureFactoryFact(path=path, line=node.lineno, module=module, function_name=node.name)


def _module_level_factory_functions(
    path: Path,
    root: Path,
    tree: ast.Module,
    *,
    pytest_modules: frozenset[str],
    fixture_aliases: frozenset[str],
) -> tuple[_FixtureFactoryFact, ...]:
    """Return every module-level function recognized as a fixture-returning factory."""
    relative = _relative_path(path, root)
    module = _module_name(path, root)
    facts: list[_FixtureFactoryFact] = []
    for statement in tree.body:
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        fact = _fixture_factory_fact(
            statement,
            path=relative,
            module=module,
            pytest_modules=pytest_modules,
            fixture_aliases=fixture_aliases,
        )
        if fact is not None:
            facts.append(fact)
    return tuple(facts)


def _resolve_factory_candidates(
    drafts: Iterable[_FactoryCandidateDraft],
    factories: Iterable[_FixtureFactoryFact],
    imports: Iterable[_ImportFact],
) -> tuple[tuple[FactoryFixtureCandidate, ...], int]:
    """Return the candidates provably tied to a factory, and how many were not.

    Only a resolved binding is returned as a candidate, so the population is
    what its name claims. The unresolved remainder is returned as a COUNT
    rather than as records: it is dominated by ordinary module-level
    construction (``re.compile``, ``Decimal``, ``frozenset``), and reporting
    thousands of those as fixture candidates would state something false about
    almost every member. The count is still reported, because it is the honest
    bound on this walk -- a factory reached through a callee this resolver
    cannot follow sits inside that number, unseen.
    """
    factories_by_site: dict[tuple[str, str], _FixtureFactoryFact] = {
        (fact.module, fact.function_name): fact for fact in factories
    }
    imports_by_file: dict[str, list[_ImportFact]] = {}
    for imported in imports:
        imports_by_file.setdefault(imported.path, []).append(imported)
    resolved: list[FactoryFixtureCandidate] = []
    unresolved = 0
    for draft in drafts:
        fact = factories_by_site.get((draft.module, draft.callee_name)) if draft.callee_name else None
        if fact is None and draft.callee_name is not None:
            for imported in imports_by_file.get(draft.path, []):
                if imported.bound_name != draft.callee_name:
                    continue
                fact = factories_by_site.get((imported.provider_module, imported.provider_name))
                if fact is not None:
                    break
        if fact is None:
            unresolved += 1
            continue
        resolved.append(
            FactoryFixtureCandidate(
                path=draft.path,
                line=draft.line,
                column=draft.column,
                bound_name=draft.bound_name,
                callee_expression=draft.callee_expression,
                resolved_factory=f"{fact.path}:{fact.line}:{fact.function_name}",
            ),
        )
    return (
        tuple(
            sorted(
                resolved,
                key=lambda candidate: (candidate.path, candidate.line, candidate.column, candidate.bound_name),
            ),
        ),
        unresolved,
    )


def _imported_bindings(
    drafts: Iterable[_FixtureDraft],
    imports: Iterable[_ImportFact],
) -> dict[tuple[str, int, int], tuple[FixtureImport, ...]]:
    """Link source-level fixture providers to importing module aliases.

    A fixture imported into a test module is registered there under the bound
    alias.  This is not a second definition, so it remains linked to its
    originating record rather than being counted as a duplicate provider.
    """
    by_module: dict[str, list[_FixtureDraft]] = {}
    for draft in drafts:
        by_module.setdefault(draft.module, []).append(draft)
    bindings: dict[tuple[str, int, int], list[FixtureImport]] = {}
    for imported in imports:
        for draft in by_module.get(imported.provider_module, []):
            if draft.record.qualname != draft.record.function_name:
                # Not importable by its literal def name: a nested closure or
                # a class attribute is invisible to `from module import name`,
                # so a same-named module-level def is the only valid target.
                continue
            if imported.provider_name != "*" and draft.record.function_name != imported.provider_name:
                continue
            has_effective_name_override = draft.record.decorator.name_expression is not None
            bound_name = (
                draft.record.effective_name
                if has_effective_name_override
                else (draft.record.function_name if imported.provider_name == "*" else imported.bound_name)
            )
            identity = (draft.record.path, draft.record.line, draft.record.column)
            bindings.setdefault(identity, []).append(
                FixtureImport(
                    path=imported.path,
                    line=imported.line,
                    provider_module=imported.provider_module,
                    provider_name=draft.record.function_name,
                    bound_name=bound_name,
                ),
            )
    return {
        identity: tuple(sorted(set(rows), key=lambda row: (row.path, row.line, row.bound_name)))
        for identity, rows in bindings.items()
    }


def _function_index(functions: Iterable[_FunctionFact]) -> _FunctionIndex:
    """Index source-level requests and test topology once for the whole census."""
    explicit_by_name: dict[str, list[_ConsumerReference]] = {}
    tests_by_path: dict[str, list[_FunctionFact]] = {}
    tests_by_directory: dict[str, list[_FunctionFact]] = {}
    for function in functions:
        if function.is_fixture or function.is_test:
            for names, via in (
                (function.parameters, "parameter"),
                (function.usefixtures, "usefixtures"),
                (function.getfixturevalue, "getfixturevalue"),
            ):
                for name in names:
                    explicit_by_name.setdefault(name, []).append(_ConsumerReference(function, via))
        if not function.is_test:
            continue
        tests_by_path.setdefault(function.path, []).append(function)
        directory = Path(function.path).parent
        for ancestor in (directory, *directory.parents):
            tests_by_directory.setdefault(ancestor.as_posix(), []).append(function)
    return _FunctionIndex(
        explicit_by_name={name: tuple(rows) for name, rows in explicit_by_name.items()},
        tests_by_path={path: tuple(rows) for path, rows in tests_by_path.items()},
        tests_by_directory={path: tuple(rows) for path, rows in tests_by_directory.items()},
    )


def _consumer_record(reference: _ConsumerReference, *, via_prefix: str) -> FixtureConsumer:
    """Render one pre-indexed request as a public consumer record."""
    function = reference.function
    return FixtureConsumer(
        function.path,
        function.line,
        function.qualname,
        "fixture" if function.is_fixture else "test",
        f"{via_prefix}{reference.via}",
    )


def _consumer_rows(
    fixture: _FixtureDraft,
    index: _FunctionIndex,
    imported_bindings: Iterable[FixtureImport],
) -> tuple[FixtureConsumer, ...]:
    """Join explicit consumers from indexed requests without resolving shadows."""
    rows: list[FixtureConsumer] = []
    for reference in index.explicit_by_name.get(fixture.record.effective_name, ()):
        function = reference.function
        if _visible_to(fixture, function) and not (
            function.path == fixture.record.path and function.line == fixture.record.line
        ):
            rows.append(_consumer_record(reference, via_prefix=""))
    for binding in imported_bindings:
        for reference in index.explicit_by_name.get(binding.bound_name, ()):
            if _binding_visible_to(binding, reference.function):
                rows.append(_consumer_record(reference, via_prefix="imported-"))
    return tuple(sorted(set(rows), key=lambda row: (row.path, row.line, row.qualname, row.via)))


def _binding_visible_to(binding: FixtureImport, consumer: _FunctionFact) -> bool:
    """Return the pytest visibility of an imported fixture binding.

    A normal module import only registers its fixture binding for that module.
    An import into ``conftest.py`` registers the binding for every descendant
    test module, exactly like a fixture definition written in that conftest.
    Shadowing remains deliberately unresolved: any visible binding is retained
    as a consumer candidate rather than a claimed final provider.
    """
    binding_path = Path(binding.path)
    if binding_path.name == _ROOT_CONFTEXT:
        return Path(consumer.path).is_relative_to(binding_path.parent)
    return consumer.path == binding.path


def _fixture_tests(fixture: _FixtureDraft, index: _FunctionIndex) -> tuple[_FunctionFact, ...]:
    """Return test functions visible to a provider from its indexed topology."""
    if fixture.is_conftest:
        assert fixture.conftest_directory is not None
        return index.tests_by_directory.get(fixture.conftest_directory.as_posix(), ())
    return tuple(
        function for function in index.tests_by_path.get(fixture.record.path, ()) if _visible_to(fixture, function)
    )


def _binding_tests(binding: FixtureImport, index: _FunctionIndex) -> tuple[_FunctionFact, ...]:
    """Return test functions visible to an imported fixture binding."""
    binding_path = Path(binding.path)
    if binding_path.name == _ROOT_CONFTEXT:
        return index.tests_by_directory.get(binding_path.parent.as_posix(), ())
    return index.tests_by_path.get(binding.path, ())


def _autouse_reach(
    fixture: _FixtureDraft,
    index: _FunctionIndex,
    imported_bindings: Iterable[FixtureImport],
) -> tuple[FixtureConsumer, ...]:
    """Report test functions a true autouse fixture can reach implicitly."""
    if not fixture.record.decorator.autouse:
        return ()
    rows = [
        FixtureConsumer(function.path, function.line, function.qualname, "test", "autouse")
        for function in _fixture_tests(fixture, index)
    ]
    for binding in imported_bindings:
        rows.extend(
            FixtureConsumer(function.path, function.line, function.qualname, "test", "imported-autouse")
            for function in _binding_tests(binding, index)
        )
    return tuple(sorted(set(rows), key=lambda row: (row.path, row.line, row.qualname, row.via)))


def census(repo_root: Path = REPO_ROOT) -> FixtureCensus:
    """Build the complete fixture census for one working-tree source snapshot."""
    root = repo_root.resolve()
    sources = iter_source_files(root)
    trees = _read_trees(sources, root)
    visitors = [_ModuleVisitor(path, root, trees[path]) for path in sources]
    for visitor in visitors:
        visitor.visit(trees[visitor.path])
    functions = tuple(function for visitor in visitors for function in visitor.functions)
    function_index = _function_index(functions)
    drafts = tuple(draft for visitor in visitors for draft in visitor.fixtures)
    imports = tuple(imported for path in sources for imported in _import_facts(path, root, trees[path]))
    bindings_by_fixture = _imported_bindings(drafts, imports)
    factory_candidate_drafts = tuple(
        candidate for path in sources for candidate in _module_level_factory_candidates(path, root, trees[path])
    )
    factory_functions = tuple(
        fact
        for visitor in visitors
        for fact in _module_level_factory_functions(
            visitor.path,
            root,
            trees[visitor.path],
            pytest_modules=visitor.pytest_modules,
            fixture_aliases=visitor.fixture_aliases,
        )
    )
    factory_fixture_candidates, unresolved_call_assignments = _resolve_factory_candidates(
        factory_candidate_drafts,
        factory_functions,
        imports,
    )
    fixtures = tuple(
        sorted(
            (
                replace(
                    draft.record,
                    imported_bindings=bindings_by_fixture.get(
                        (draft.record.path, draft.record.line, draft.record.column),
                        (),
                    ),
                    consumers=_consumer_rows(
                        draft,
                        function_index,
                        bindings_by_fixture.get((draft.record.path, draft.record.line, draft.record.column), ()),
                    ),
                    autouse_reach=_autouse_reach(
                        draft,
                        function_index,
                        bindings_by_fixture.get((draft.record.path, draft.record.line, draft.record.column), ()),
                    ),
                )
                for draft in drafts
            ),
            key=lambda record: (record.path, record.line, record.column, record.effective_name),
        ),
    )
    return FixtureCensus(
        root=str(root),
        sources=tuple(_relative_path(path, root) for path in sources),
        fixtures=fixtures,
        dynamic_fixture_requests=tuple(
            sorted(
                (request for visitor in visitors for request in visitor.dynamic_fixture_requests),
                key=lambda request: (request.path, request.line, request.qualname),
            ),
        ),
        factory_fixture_candidates=factory_fixture_candidates,
        unresolved_call_assignment_count=unresolved_call_assignments,
    )


def _json_payload(result: FixtureCensus) -> dict[str, object]:
    """Return a deterministic JSON-safe representation for the CLI and manifests."""
    return {
        "root": result.root,
        "source_count": len(result.sources),
        "sources": result.sources,
        "fixture_count": result.fixture_count,
        "fixtures": [asdict(record) for record in result.fixtures],
        "dynamic_fixture_requests": [asdict(request) for request in result.dynamic_fixture_requests],
        "factory_fixture_candidate_count": result.factory_fixture_candidate_count,
        "factory_fixture_candidates": [asdict(candidate) for candidate in result.factory_fixture_candidates],
        "unresolved_call_assignment_count": result.unresolved_call_assignment_count,
        "aliased_behaviour_count": result.aliased_behaviour_count,
        "aliased_behaviours": [asdict(behaviour) for behaviour in result.aliased_behaviours],
    }


def main(argv: list[str] | None = None) -> int:
    """Print the census or a machine-readable record population."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root to inventory")
    parser.add_argument("--json", action="store_true", help="emit the complete census as JSON")
    arguments = parser.parse_args(argv)
    try:
        result = census(arguments.root)
    except FixtureCensusError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if arguments.json:
        print(json.dumps(_json_payload(result), indent=2, sort_keys=True))
        return 0
    print(
        f"fixture census: {result.fixture_count} fixtures in {len(result.sources)} source files; "
        f"dynamic requests={len(result.dynamic_fixture_requests)}; "
        f"factory-bound fixtures={result.factory_fixture_candidate_count}; "
        f"aliased behaviours={result.aliased_behaviour_count} "
        f"(excluding {len(result.behaviourless_fixtures)} behaviourless fixtures, "
        f"which only raise or hand back a name and so share a body by construction)",
    )
    for behaviour in result.aliased_behaviours:
        print(
            f"  one body under {len(behaviour.effective_names)} names "
            f"({', '.join(behaviour.effective_names)}): {', '.join(behaviour.sites)}",
        )
    print(
        f"  {result.unresolved_call_assignment_count} module-level call assignments could not be resolved to a "
        "definition; a fixture factory reached through such a callee would not be recognised here.",
    )
    for record in result.fixtures:
        print(
            f"{record.path}:{record.line}:{record.column}  {record.effective_name}  "
            f"({record.decorator.callee}, {record.decorator.scope}, autouse={record.decorator.autouse})  "
            f"deps={','.join(record.dependencies) or '-'}  direct-consumers={len(record.consumers)}  "
            f"imports={len(record.imported_bindings)}  autouse-reach={len(record.autouse_reach)}  "
            f"body={record.normalized_body_sha256}",
        )
    for candidate in result.factory_fixture_candidates:
        print(
            f"{candidate.path}:{candidate.line}:{candidate.column}  "
            f"{candidate.bound_name} = {candidate.callee_expression}(...)  factory={candidate.resolved_factory}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
