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

The census is intentionally descriptive, exactly as fixture_census.py's own
census is: a matching normalized body digest is candidate evidence for a
later review, never a conclusion that two sites are substitutable.  Grouping
is disambiguated by what each body's imported names actually resolve to
(``body_symbol_origins_sha256``), so two same-shaped bodies calling different
underlying functions do not collapse into one false-positive behaviour.

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
        """Return every helper body reached through more than one site."""
        by_body: dict[tuple[str, str, tuple[str, ...]], list[HelperRecord]] = {}
        for record in self.helpers:
            if record.body_performs_no_work:
                continue
            key = (record.normalized_body_sha256, record.body_symbol_origins_sha256, record.decorators)
            by_body.setdefault(key, []).append(record)
        return tuple(
            AliasedHelperBehaviour(
                body_sha256=body,
                function_names=tuple(sorted({record.function_name for record in group})),
                sites=tuple(sorted(f"{record.path}:{record.line}:{record.qualname}" for record in group)),
            )
            for (body, _origins, _decorators), group in sorted(by_body.items())
            if len({(record.path, record.qualname) for record in group}) > 1
        )

    @property
    def aliased_behaviour_count(self) -> int:
        """Return how many distinct helper behaviours are reached through several sites."""
        return len(self.aliased_behaviours)


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
        *,
        module_is_private: bool,
    ) -> None:
        self.path = path
        self.symbol_origins = symbol_origins
        self.pytest_modules = pytest_modules
        self.fixture_aliases = fixture_aliases
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
                        if (
                            name := _dotted_name(decorator.func if isinstance(decorator, ast.Call) else decorator)
                        )
                        is not None
                    )
                )
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
                    ),
                )
        self._qualname.append(node.name)
        self.generic_visit(node)
        self._qualname.pop()


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
        visitor = _HelperVisitor(
            relative,
            symbol_origins,
            pytest_modules,
            fixture_aliases,
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
        "aliased_behaviours": [
            {"body_sha256": b.body_sha256, "function_names": list(b.function_names), "sites": list(b.sites)}
            for b in result.aliased_behaviours
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
    print(f"aliased behaviours (body reached through >1 site): {result.aliased_behaviour_count}")
    for behaviour in result.aliased_behaviours:
        print(
            f"  one body under {len(behaviour.function_names)} names "
            f"({', '.join(behaviour.function_names)}): {', '.join(behaviour.sites)}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
