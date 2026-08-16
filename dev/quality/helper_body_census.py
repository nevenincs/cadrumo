"""AST census of private, non-fixture test-helper functions, keyed on body.

``fixture_census.py`` walks the same source universe but only sees functions
carrying a ``@pytest.fixture`` decorator.  The
``2026-08-14-test-harness-sanity-semantic-test-corpus-drift-audit`` found that
this left the larger population invisible: "the campaign's own census sees
only decorated fixture definitions.  Plain helper functions, assertion
helpers, builders and value constructors are outside its reach entirely, and
that is where most of the drift turned out to live."  A name-keyed search for
one such helper returns a single site and reads as unique even when the same
body has been hand-copied under a dozen other names; a census keyed on the
NAME cannot see the alias, only one keyed on the BODY can.

This module owns the disjoint population fixture_census.py does not: private
(leading-underscore) module- or class-level functions in test-owned files
that are NOT registered as pytest fixtures and are not themselves tests.  It
reuses fixture_census's own source universe, docstring-stripping, and
symbol-origin disambiguation (:func:`_module_symbol_origins`) rather than
re-implementing them, so the two censuses share one normalization axis and
cannot silently drift apart on what "the same body" means.

Honesty about reach, stated plainly rather than implied: this is a BODY
census.  It finds a helper hand-copied under a new name -- the aliasing class
this campaign's own drift audit documents -- because the AST shape survives
the rename.  It CANNOT find a semantic mirror: the same behaviour written in
genuinely different code (a different library, a different algorithm, a
different call shape).  ``2026-08-14-test-harness-sanity-semantic-test-corpus-
drift-audit`` and the parallel rag-discovery sweeps in this campaign found
several of those (a pdfium-based PDF builder mirroring seven reportlab-based
sites; a `_bound_repo_with_engine` mirroring `_ephemeral_secure_repo`) and no
AST census, this one included, will ever reach them.  Closing that axis is
`vaultspec-rag` discovery by MEANING before any consolidation, not this gate.

A second, narrower blind spot, named here as documentation rather than
detection: this module scores FUNCTIONS only, exactly as fixture_census.py
does.  Module-level DATA constants duplicated verbatim across files --
`_CASILLA_FRAGMENT`, `_REVISION_ID` and `_LEGAL_REF` are byte-identical
across four files in this tree today -- carry no function body for either
census to walk, so neither reports them.  This module does not attempt to
detect that population; it only says plainly that it would not catch it if
it tried.

The census is intentionally descriptive, exactly as fixture_census.py's own
census is: a matching normalized body digest is candidate evidence for a
later review, never a conclusion that two sites are substitutable.  Grouping
is disambiguated by what each body's imported names actually resolve to
(``body_symbol_origins_sha256``), so two same-shaped bodies calling different
underlying functions do not collapse into one false-positive behaviour.

A flagged group may still be CONSTANT-DEPENDENT: its body is identical
because it closes over a module-level constant of the same NAME in every
file, but that constant's VALUE can differ per file.  The 2026-08-15 B16/
B18/B24/B25 burndown found this concretely twice -- one site's
``_READY_PROFILE_FACTS`` carried a different taxpayer surname than another's;
one site's ``_WORKFLOW`` pointed at a different CI YAML file than another's
-- both cases where the function SHAPE was a real duplicate but a naive
merge would have silently unified different test data.  Every
``AliasedHelperBehaviour`` reports which such names its group's bodies
reference (``closed_over_constants``); a non-empty tuple is the signal to
PARAMETERISE the constant into the consolidated helper's signature, never to
delete the duplicate outright without checking each site's value first. This
detector deliberately does NOT compare the constants' values across sites --
guessing divergent-vs-identical from source text would produce exactly the
confident-but-wrong output this campaign spent the session correcting; a
human reads the referenced constants before consolidating.

A body-identical, constant-dependent group can ALSO be the correct end
state already: a thin per-file wrapper that does nothing but forward its
own closed-over constant into one call on a shared implementation is not
debt, it is composition. ``2026-08-15``'s W09.P30.S141 verification found
exactly that shape live in the tree (``_write_modelo``/``_load_revision``
in `domain/calculations/registry/tests/`, each delegating in full to
`_loader_directory_mode_support.py`) reported as duplication -- the census
was flagging the solution as the problem. A record whose body is exactly
one ``return``/expression statement wrapping a call to a name resolved
through an import (:func:`_delegating_wrapper_target`) is excluded from
`aliased_behaviours` entirely and surfaced instead as `delegating_wrappers`.
Deliberately conservative: a call reached through attribute access
(`_RUNNER.invoke(...)`) or an unresolved callee is left in the duplicate
bucket rather than guessed at, per the same no-guessing discipline as the
constant detector above.

**Duplication matters when it can diverge.** That is the standing test for
whether a body-identical group belongs on a burndown list at all. A copy
that can be fixed in one place and silently survive unfixed in another is
the failure this census exists to catch. A delegating wrapper cannot do
that -- every site routes through the one canonical callee, so a fix to the
canonical reaches all of them, and there is no second implementation to
drift. What remains at that point is a naming preference, not a divergence
risk.

`_invoke` in `src/cadrumo/entrypoints/cli/tests/` is the operator ruling
this principle produced (2026-08-15, S141 follow-up): 51 sites, each a
signature-preserving, value-free passthrough to the one canonical
`cadrumo.tests.cli_runner.invoke_cached_cli` -- unlike `_write_modelo`
above, none of them inject a per-file argument the canonical lacks. Read as
real but low-value debt and DELIBERATELY LEFT UNSWEPT: every site already
routes through the single implementation, so there is nothing to diverge,
while a 51-file sweep on a tree three teams are actively committing to
carries real collision risk for a purely cosmetic gain. Recorded here so
the next reader does not mistake "on this census" for "on the burndown
list" and does not rediscover the question assuming it was simply missed.
If this pattern is worth preventing going forward, the right tool is a lint
rule blocking NEW value-free wrappers over an already-canonical callee, not
a retrospective sweep of the existing ones -- this census does not attempt
that rule; it only records why one was not derived from its own output.

Usage::

    python -m dev.quality.helper_body_census
    python -m dev.quality.helper_body_census --json
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8
from dev.quality.fixture_census import (
    FixtureCensusError,
    _dotted_name,
    _executable_body,
    _fixture_callee,
    _module_symbol_origins,
    _performs_no_work,
    _pytest_bindings,
    _read_trees,
    _relative_path,
    iter_source_files,
)

_UTF_8: Final[str] = UTF_8

#: A private helper lives in a test-owned file: either it sits inside a
#: ``tests`` package directory, or its own filename is a pytest collection
#: target.  Production ``_private`` helpers outside that population are a
#: different concern (the import-hygiene ownership rules already govern
#: them) and are deliberately excluded here.
_TEST_OWNED_FILENAME_PREFIX: Final[str] = "test_"
_TEST_OWNED_DIRECTORY: Final[str] = "tests"


@dataclass(frozen=True, slots=True)
class HelperRecord:
    """The static identity of one private, non-fixture helper definition."""

    path: str
    line: int
    column: int
    qualname: str
    function_name: str
    normalized_body_sha256: str
    body_symbol_origins_sha256: str
    body_performs_no_work: bool
    #: Sorted dotted decorator names other than a pytest fixture (already
    #: excluded from candidacy entirely).  Included in the aliasing key: a
    #: ``@contextmanager``-wrapped body and a bare function sharing the same
    #: statements run differently, so they must not collapse into one
    #: behaviour just because the raw AST dump of the body matches.
    decorators: tuple[str, ...]
    #: Names this body references that are free (not a parameter, not locally
    #: bound, not an import) AND are assigned at module scope somewhere in
    #: this same module -- i.e. a closed-over module-level constant.  NOT
    #: part of the aliasing key: two sites naming a same-shaped constant
    #: differently (``_YEAR`` vs ``_FILING_YEAR``) still share one behaviour.
    #: Values are never compared -- see the module docstring.
    closed_over_constants: tuple[str, ...] = ()
    #: ``<module>.<name>`` this body delegates to in full, or ``None``.  Set
    #: only when the body's SOLE executable statement is a ``return`` or bare
    #: expression wrapping exactly one call to a name resolved through an
    #: import in this module -- see :func:`_delegating_wrapper_target`.  A
    #: non-``None`` value means this site is NOT counted as a duplicate: it
    #: already routes through the single shared implementation the name
    #: names, and a per-file closed-over constant supplying that call's
    #: arguments is the correct end state, not debt.
    delegates_to: str | None = None


@dataclass(frozen=True, slots=True)
class AliasedHelperBehaviour:
    """One helper body reached through more than one (path, function) site.

    See :class:`fixture_census.AliasedBehaviour` for the full rationale; this
    is the same evidence over the disjoint plain-helper population.  Reported,
    never refused -- two sites sharing a body may still be a legitimate,
    independently-owned duplicate (a per-surface safety proof, a
    standalone-runnable gate's own fixture) and adjudicating that is a human
    review, not this gate.
    """

    body_sha256: str
    function_names: tuple[str, ...]
    sites: tuple[str, ...]
    #: Union of every group member's :attr:`HelperRecord.closed_over_constants`.
    #: Non-empty means this is the CONSTANT-DEPENDENT class the 2026-08-15
    #: burndown found: the shape is a real duplicate, but before deleting any
    #: site, read what each one's named constant(s) actually hold -- the fix
    #: shape is to PARAMETERISE the constant into the consolidated helper's
    #: signature, not to pick one site's value and discard the rest.
    closed_over_constants: tuple[str, ...] = ()

    @property
    def is_constant_dependent(self) -> bool:
        """Return whether this behaviour's bodies close over a module constant."""
        return bool(self.closed_over_constants)


@dataclass(frozen=True, slots=True)
class HelperCensus:
    """A reproducible population of private test-helper functions."""

    root: str
    sources: tuple[str, ...]
    helpers: tuple[HelperRecord, ...]

    @property
    def helper_count(self) -> int:
        """Return the number of helper definitions in the complete census."""
        return len(self.helpers)

    @property
    def aliased_behaviours(self) -> tuple[AliasedHelperBehaviour, ...]:
        """Return every helper body reached through more than one site.

        A record whose sole executable statement delegates to a resolved
        import (:attr:`HelperRecord.delegates_to` is set) is excluded from
        this population entirely, not merely annotated -- it already routes
        through one shared implementation, so counting it as a duplicate
        reports the solution as the problem. See
        :attr:`delegating_wrappers` for that population, surfaced rather than
        silently discarded.
        """
        by_body: dict[tuple[str, str, tuple[str, ...]], list[HelperRecord]] = {}
        for record in self.helpers:
            if record.body_performs_no_work or record.delegates_to is not None:
                continue
            key = (record.normalized_body_sha256, record.body_symbol_origins_sha256, record.decorators)
            by_body.setdefault(key, []).append(record)
        return tuple(
            AliasedHelperBehaviour(
                body_sha256=body,
                function_names=tuple(sorted({record.function_name for record in group})),
                sites=tuple(sorted(f"{record.path}:{record.line}:{record.qualname}" for record in group)),
                closed_over_constants=tuple(
                    sorted({name for record in group for name in record.closed_over_constants}),
                ),
            )
            for (body, _origins, _decorators), group in sorted(by_body.items())
            if len({(record.path, record.qualname) for record in group}) > 1
        )

    @property
    def aliased_behaviour_count(self) -> int:
        """Return how many distinct helper behaviours are reached through several sites."""
        return len(self.aliased_behaviours)

    @property
    def delegating_wrappers(self) -> tuple[HelperRecord, ...]:
        """Return every record excluded from :attr:`aliased_behaviours` as a delegating wrapper.

        Counted and listed rather than silently dropped, exactly as
        `fixture_census.py`'s own `behaviourless_fixtures` surfaces its own
        excluded population: a reader comparing this figure across runs needs
        to see what the detector declined to consider, and why.
        """
        return tuple(record for record in self.helpers if record.delegates_to is not None)

    @property
    def delegating_wrapper_count(self) -> int:
        """Return how many records were excluded from aliasing as delegating wrappers."""
        return len(self.delegating_wrappers)


def _is_test_owned(relative: str) -> bool:
    """Return whether ``relative`` is a file this census inspects.

    Matches the population `dev/packaging/tests/test_hashing.py`'s own
    precedent gate scans: files under a ``tests`` directory, or files whose
    own name is a pytest collection target.
    """
    path = Path(relative)
    return _TEST_OWNED_DIRECTORY in path.parts or path.name.startswith(_TEST_OWNED_FILENAME_PREFIX)


def _is_candidate_name(name: str, *, module_is_private: bool) -> bool:
    """Return whether ``name`` is a test-support identifier this census owns.

    A private (leading-underscore) name is always a candidate wherever it is
    defined.  A module whose OWN filename starts with ``_`` (this repo's
    established support-module convention -- ``_secure_objects_support.py``,
    ``_risk_table_support.py``, ``_smoke_common.py``) is itself the private
    surface, so a promoted, non-underscore export from it (``declared_live_
    write``, ``sha256_path``) is candidate too: restricting to underscored
    NAMES only would miss exactly the alias this census exists to catch --
    B18's canonical ``declared_live_write`` next to a copy still spelled
    ``_declared_live_write`` in a file the project cannot import it from.
    """
    if name.startswith("__") or name.startswith("test"):
        return False
    return name.startswith("_") or module_is_private


class _HelperVisitor(ast.NodeVisitor):
    """Collect private, non-fixture function definitions from one module."""

    def __init__(
        self,
        path: str,
        symbol_origins: dict[str, str],
        pytest_modules: frozenset[str],
        fixture_aliases: frozenset[str],
        module_constants: frozenset[str],
        *,
        module_is_private: bool,
    ) -> None:
        self.path = path
        self.symbol_origins = symbol_origins
        self.pytest_modules = pytest_modules
        self.fixture_aliases = fixture_aliases
        self.module_constants = module_constants
        self.module_is_private = module_is_private
        self.records: list[HelperRecord] = []
        self._qualname: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._qualname.append(node.name)
        self.generic_visit(node)
        self._qualname.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        is_fixture = any(
            _fixture_callee(decorator, pytest_modules=self.pytest_modules, fixture_aliases=self.fixture_aliases)
            is not None
            for decorator in node.decorator_list
        )
        if _is_candidate_name(node.name, module_is_private=self.module_is_private) and not is_fixture:
            executable_body = _executable_body(node.body)
            if executable_body:
                normalized_body = ast.dump(
                    ast.Module(body=executable_body, type_ignores=[]),
                    annotate_fields=True,
                    include_attributes=False,
                )
                decorators = tuple(
                    sorted(
                        name
                        for decorator in node.decorator_list
                        if (name := _dotted_name(decorator.func if isinstance(decorator, ast.Call) else decorator))
                        is not None
                    )
                )
                parameters = frozenset(
                    argument.arg for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
                ) | {argument.arg for argument in (node.args.vararg, node.args.kwarg) if argument is not None}
                self.records.append(
                    HelperRecord(
                        path=self.path,
                        line=node.lineno,
                        column=node.col_offset,
                        qualname=".".join((*self._qualname, node.name)),
                        function_name=node.name,
                        normalized_body_sha256=hashlib.sha256(normalized_body.encode(_UTF_8)).hexdigest(),
                        body_symbol_origins_sha256=_body_symbol_origins_sha256(executable_body, self.symbol_origins),
                        body_performs_no_work=_performs_no_work(executable_body),
                        decorators=decorators,
                        closed_over_constants=_closed_over_module_constants(
                            executable_body,
                            parameters=parameters,
                            symbol_origins=self.symbol_origins,
                            module_constants=self.module_constants,
                        ),
                        delegates_to=_delegating_wrapper_target(executable_body, self.symbol_origins),
                    ),
                )
        self._qualname.append(node.name)
        self.generic_visit(node)
        self._qualname.pop()


def _module_level_constant_names(tree: ast.Module) -> frozenset[str]:
    """Return every name a top-level ``Assign``/``AnnAssign`` binds in this module.

    Deliberately shallow -- only ``tree.body`` (module top level), not
    ``ast.walk``, so a same-named local inside some unrelated function is
    never mistaken for a module constant.
    """
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return frozenset(names)


def _bound_names(body: list[ast.stmt]) -> frozenset[str]:
    """Return every name this body assigns, binds, or declares as a parameter.

    An approximation, not a scope-correct resolver: nested-function and
    lambda parameters are folded into the same flat set as the outer body's
    locals. Good enough for a diagnostic "is this name free" check -- a
    coincidental name collision only makes the detector under-report a
    closed-over constant, never fabricate one that is not there.
    """

    def _targets(expr: ast.expr) -> set[str]:
        if isinstance(expr, ast.Name):
            return {expr.id}
        if isinstance(expr, ast.Starred):
            return _targets(expr.value)
        if isinstance(expr, ast.Tuple | ast.List):
            return {name for element in expr.elts for name in _targets(element)}
        return set()

    def _arg_names(arguments: ast.arguments) -> set[str]:
        names = {argument.arg for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)}
        if arguments.vararg is not None:
            names.add(arguments.vararg.arg)
        if arguments.kwarg is not None:
            names.add(arguments.kwarg.arg)
        return names

    bound: set[str] = set()
    for statement in body:
        for node in ast.walk(statement):
            match node:
                case ast.Assign(targets=targets):
                    bound.update(name for target in targets for name in _targets(target))
                case ast.AnnAssign(target=target) | ast.AugAssign(target=target) | ast.NamedExpr(target=target):
                    bound.update(_targets(target))
                case ast.For(target=target) | ast.AsyncFor(target=target):
                    bound.update(_targets(target))
                case ast.comprehension(target=target):
                    bound.update(_targets(target))
                case ast.With(items=items) | ast.AsyncWith(items=items):
                    bound.update(
                        name
                        for item in items
                        if item.optional_vars is not None
                        for name in _targets(item.optional_vars)
                    )
                case ast.ExceptHandler(name=str() as name):
                    bound.add(name)
                case ast.Lambda(args=arguments):
                    bound.update(_arg_names(arguments))
                case ast.FunctionDef(name=name, args=arguments) | ast.AsyncFunctionDef(name=name, args=arguments):
                    bound.add(name)
                    bound.update(_arg_names(arguments))
                case ast.ClassDef(name=name):
                    bound.add(name)
    return frozenset(bound)


def _delegating_wrapper_target(body: list[ast.stmt], symbol_origins: dict[str, str]) -> str | None:
    """Return the ``<module>.<name>`` this body delegates to in full, or ``None``.

    A delegating wrapper's body is exactly ONE executable statement -- a
    ``return`` or a bare expression -- wrapping exactly one ``Call`` to a
    plain name (never an attribute access: ``_RUNNER.invoke(...)`` is not
    recognised, since the callee there is not itself an imported symbol)
    resolved through an import in this module.  Extra positional or keyword
    arguments to that call, however many, do not disqualify it -- the
    wrapper commonly supplies its own per-file constant as one of them, and
    that is the whole point of the wrapper existing.

    Deliberately conservative: two statements, an unresolved callee, or a
    call reached through attribute access all return ``None`` rather than a
    guess.  A false negative here leaves a genuine wrapper in the duplicate
    bucket for a human to notice and clear by hand; a false positive would
    silently hide a real duplicate from the count, which is the worse
    failure.
    """
    if len(body) != 1:
        return None
    match body[0]:
        case ast.Return(value=ast.Call() as candidate) | ast.Expr(value=ast.Call() as candidate):
            pass
        case _:
            return None
    if not isinstance(candidate.func, ast.Name):
        return None
    return symbol_origins.get(candidate.func.id)


def _closed_over_module_constants(
    body: list[ast.stmt],
    *,
    parameters: frozenset[str],
    symbol_origins: dict[str, str],
    module_constants: frozenset[str],
) -> tuple[str, ...]:
    """Return every module-level constant this body references but does not bind.

    A name counts only if it is genuinely free: not a parameter, not
    assigned or bound anywhere within the body, and not an imported name
    (imports are already covered by ``body_symbol_origins_sha256``).
    """
    bound = _bound_names(body) | parameters
    referenced = {
        node.id
        for statement in body
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    free = referenced - bound - symbol_origins.keys()
    return tuple(sorted(free & module_constants))


def _body_symbol_origins_sha256(body: list[ast.stmt], origins: dict[str, str]) -> str:
    """Digest what this body's imported names actually resolve to."""
    referenced = {name.id for statement in body for name in ast.walk(statement) if isinstance(name, ast.Name)}
    resolved = sorted((name, origins[name]) for name in referenced if name in origins)
    return hashlib.sha256(json.dumps(resolved, sort_keys=True).encode(_UTF_8)).hexdigest()


def census(repo_root: Path = REPO_ROOT) -> HelperCensus:
    """Walk the fixture-census source universe and report every private helper.

    Raises :class:`FixtureCensusError` (fixture_census's own error type, since
    this census is fail-closed on the same terms: unreadable or unparseable
    included Python refuses the whole run rather than silently narrowing it).
    """
    root = repo_root.resolve()
    sources = iter_source_files(root)
    trees = _read_trees(sources, root)
    records: list[HelperRecord] = []
    for path, tree in trees.items():
        relative = _relative_path(path, root)
        if not _is_test_owned(relative):
            continue
        pytest_modules, fixture_aliases = _pytest_bindings(tree)
        symbol_origins = _module_symbol_origins(tree, path, root)
        module_constants = _module_level_constant_names(tree)
        visitor = _HelperVisitor(
            relative,
            symbol_origins,
            pytest_modules,
            fixture_aliases,
            module_constants,
            module_is_private=path.name.startswith("_"),
        )
        visitor.visit(tree)
        records.extend(visitor.records)
    return HelperCensus(
        root=str(root),
        sources=tuple(_relative_path(path, root) for path in sources),
        helpers=tuple(sorted(records, key=lambda record: (record.path, record.line, record.column))),
    )


def _json_payload(result: HelperCensus) -> dict[str, object]:
    return {
        "root": result.root,
        "source_count": len(result.sources),
        "helper_count": result.helper_count,
        "aliased_behaviour_count": result.aliased_behaviour_count,
        "delegating_wrapper_count": result.delegating_wrapper_count,
        "aliased_behaviours": [
            {
                "body_sha256": b.body_sha256,
                "function_names": list(b.function_names),
                "sites": list(b.sites),
                "is_constant_dependent": b.is_constant_dependent,
                "closed_over_constants": list(b.closed_over_constants),
            }
            for b in result.aliased_behaviours
        ],
        "delegating_wrappers": [
            {"path": r.path, "line": r.line, "qualname": r.qualname, "delegates_to": r.delegates_to}
            for r in result.delegating_wrappers
        ],
    }


def main(argv: list[str] | None = None) -> int:
    """Print the census or a machine-readable record population."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = census(args.root)
    except FixtureCensusError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(_json_payload(result), indent=2, sort_keys=True))
        return 0

    print(f"helper census: {result.helper_count} private test-helper definitions across {len(result.sources)} files")
    print(
        f"delegating wrappers (excluded from duplication -- already routed to one shared "
        f"implementation): {result.delegating_wrapper_count}",
    )
    print(f"aliased behaviours (body reached through >1 site): {result.aliased_behaviour_count}")
    for behaviour in result.aliased_behaviours:
        label = (
            f"CONSTANT-DEPENDENT (closes over {', '.join(behaviour.closed_over_constants)} -- "
            "read each site's value before consolidating; parameterise, do not delete)"
            if behaviour.is_constant_dependent
            else "duplicate"
        )
        print(
            f"  one body under {len(behaviour.function_names)} names "
            f"({', '.join(behaviour.function_names)}), {label}: {', '.join(behaviour.sites)}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
