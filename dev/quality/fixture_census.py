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

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_UTF_8: Final[str] = "utf-8"
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


@dataclass(frozen=True, slots=True)
class FixtureCensus:
    """A reproducible fixture population and the source files it measured."""

    root: str
    sources: tuple[str, ...]
    fixtures: tuple[FixtureRecord, ...]
    dynamic_fixture_requests: tuple[DynamicFixtureRequest, ...]

    @property
    def fixture_count(self) -> int:
        """Return the number of fixture definitions in the complete census."""
        return len(self.fixtures)


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
        files.extend(path for path in source_root.rglob("*.py") if path.is_file())

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


def _literal_string(value: ast.expr | None, *, field: str, line: int) -> str | None:
    """Return a static string or fail rather than inventing an effective value."""
    if value is None:
        return None
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    message = f"fixture {field} at line {line} is dynamic; static census cannot state its effective value"
    raise FixtureCensusError(message)


def _literal_bool(value: ast.expr | None, *, field: str, line: int, default: bool) -> bool:
    """Return a static boolean or fail rather than silently applying a default."""
    if value is None:
        return default
    if isinstance(value, ast.Constant) and isinstance(value.value, bool):
        return value.value
    message = f"fixture {field} at line {line} is dynamic; static census cannot state its effective value"
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
        self.fixtures: list[_FixtureDraft] = []
        self.functions: list[_FunctionFact] = []
        self.dynamic_fixture_requests: list[DynamicFixtureRequest] = []
        self._qualname: list[str] = []
        self._class_depth = 0

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._qualname.append(node.name)
        self._class_depth += 1
        self.generic_visit(node)
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
        usefixtures = _usefixtures(node.decorator_list)
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
            explicit_name = _literal_string(keywords.get("name"), field="name", line=node.lineno)
            scope = _literal_string(keywords.get("scope"), field="scope", line=node.lineno) or _DEFAULT_SCOPE
            autouse = _literal_bool(keywords.get("autouse"), field="autouse", line=node.lineno, default=False)
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
            normalized_body = ast.dump(
                ast.Module(body=node.body, type_ignores=[]),
                annotate_fields=True,
                include_attributes=False,
            )
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
        self.generic_visit(node)
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
            if imported.provider_name != "*" and draft.record.effective_name != imported.provider_name:
                continue
            identity = (draft.record.path, draft.record.line, draft.record.column)
            bindings.setdefault(identity, []).append(
                FixtureImport(
                    path=imported.path,
                    line=imported.line,
                    provider_module=imported.provider_module,
                    provider_name=draft.record.effective_name,
                    bound_name=(draft.record.effective_name if imported.provider_name == "*" else imported.bound_name),
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
        f"dynamic requests={len(result.dynamic_fixture_requests)}",
    )
    for record in result.fixtures:
        print(
            f"{record.path}:{record.line}:{record.column}  {record.effective_name}  "
            f"({record.decorator.callee}, {record.decorator.scope}, autouse={record.decorator.autouse})  "
            f"deps={','.join(record.dependencies) or '-'}  direct-consumers={len(record.consumers)}  "
            f"imports={len(record.imported_bindings)}  autouse-reach={len(record.autouse_reach)}  "
            f"body={record.normalized_body_sha256}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
