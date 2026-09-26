"""Literal vocabulary: an operator-data location must resolve through the taxonomy.

A sibling property to :mod:`~tests.test_storage_provenance_gate`, and neither
gate subsumes the other. The provenance gate matches the *join*: it fires
whenever ``cadrumo_local_storage_root`` is joined onto by ``/``, ``joinpath``,
``glob``, ``rglob``, ``iterdir``, or a ``Path(...)`` wrapper, and it cannot see
a location spelled out as a literal with no root in sight. This gate matches
the *literal*: a shipped module or a test hand-typing the taxonomy's own
vocabulary -- ``"buckets"``, ``"db"``, ``"cadrumo.db"``, ``"cache/llm-cache"``,
and so on -- to build a path, rather than resolving it through
:func:`~core.storage_taxonomy_locations.storage_path` or
:func:`~core.storage_taxonomy_locations.bucket_scoped_storage_path`. A literal
scan cannot see a path built by joining, and the provenance gate cannot see a
name spelled out in full; together they cover both shapes.

Two independent detectors, because the two defect shapes need different nets
and a net wide enough to catch one is wrong for the other:

Shape 1 -- a single literal, embedded slash and all
----------------------------------------------------
``Path("var/cadrumo/filed-declarations")``: one string constant, typed once,
that already contains the whole relative shape. This is how a handful of
CLI options once defaulted to an ungoverned location -- no settings field, so
no storage-root override could ever reach them. Scoped to **production**
modules only: measured across the test corpus, this shape matches only
repository-relative navigation helpers (``Path("src/cadrumo")``) and
synthetic domain-placeholder values (a ``Path``-typed field given a
plausible-looking sample value in an identity/round-trip test) -- coincidence
on the word, not a location a test resolves or writes to. A single embedded
segment is also too weak a signal on its own: matching on any occurrence of
one vocabulary word would flag ordinary prose and unrelated short names
(``"cache"``, ``"data"``, ``"db"``, ``"live"`` are all common outside this
taxonomy). Requiring the *slash* -- the author explicitly typing a multi
segment relative path in one literal -- is what keeps this shape's positive
rate high enough to enforce.

Shape 2 -- two or more taxonomy segments joined in one chain
--------------------------------------------------------------
``tmp_path / "buckets" / bucket_id / "db" / "cadrumo.db"``: no single string
carries the shape, but the *chain* does, because each hop is still governed
vocabulary. This is the shape a test actually reaches for -- proven by
measurement, not assumed: scoped to the whole package (production and tests
alike), a chain carrying **two or more** distinct governed segments has, at
every site found, been a real hand-typed layout; the loosening to a single
segment per chain reintroduces exactly the ordinary-word noise Shape 1's
slash requirement exists to avoid (a Playwright browser build cache rooted at
``tmp_path / "cache"`` is not a claim about this taxonomy's ``cache/`` prefix).
Two-or-more is not a magic number so much as the point where "coincidentally
shares one common word" stops explaining what is on the page.

Declared pins
-------------
A chain that hand-types the taxonomy's own vocabulary is not always debt.
Some tests exist specifically to prove what the resolver *should* produce,
independent of the resolver -- re-expressing the expected side through the
same accessor the code under test calls would make the assertion compare the
taxonomy against itself, which asserts nothing. :data:`PERMITTED_PIN_MODULES`
and :data:`PERMITTED_PIN_SITES` name those oracles, each with the reason
recorded in the pinning module's own docstring or in the comment beside its
entry here. Every other site is debt, and stays failing until it re-expresses
the location through :func:`~core.storage_taxonomy_locations.storage_path`,
:func:`~core.storage_taxonomy_locations.bucket_scoped_storage_path`, or
``storage_location(category).relative_path()`` for the bucket-relative case
neither accessor covers without a root to resolve against.
"""

from __future__ import annotations

import ast
import re
from functools import cache
from pathlib import Path
from typing import Final, NamedTuple

import pytest

from ...tests.inventory import aeat_relative, ast_for_path, package_python_files, production_python_files
from ..storage_taxonomy_locations import STORAGE_TAXONOMY

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MODULE_SCOPE: Final[str] = "<module>"


@cache
def _taxonomy_vocabulary() -> frozenset[str]:
    """Every path segment the taxonomy declares, plus the two retired literals.

    Read from the live declaration rather than a parallel word list, so a
    newly declared member's leaf name is protected the moment it is declared.
    ``var`` and ``cadrumo`` are not themselves taxonomy members -- they are the
    retired ``<repo>/var/cadrumo/...`` product-directory convention a couple of
    the oracle tests below still assert against, deliberately, as a boundary
    that must never come back.
    """
    return frozenset(
        {segment for location in STORAGE_TAXONOMY.values() for segment in location.subpath.split("/")}
        | {"var", "cadrumo"},
    )


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Return the ``id()`` of every string constant serving as a docstring.

    A module naming a vocabulary word inside its own docstring -- to explain
    why a location is or is not governed, as this very module does -- must not
    read as a hand-typed location. Collected structurally, the same way the
    provenance and liveness gates do it, rather than by an allowlist entry.
    """
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            found.add(id(body[0].value))
    return found


def _function_spans(tree: ast.AST) -> list[tuple[int, int, str]]:
    """Return ``(start, end, dotted name)`` for every function, nested ones included."""
    spans: list[tuple[int, int, str]] = []

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                name = f"{prefix}{child.name}"
                if not isinstance(child, ast.ClassDef):
                    spans.append((child.lineno, child.end_lineno or child.lineno, name))
                walk(child, f"{name}.")
            else:
                walk(child, prefix)

    walk(tree, "")
    return spans


def _enclosing_scope(lineno: int, spans: list[tuple[int, int, str]]) -> str:
    """Return the innermost function containing ``lineno``, or the module scope."""
    enclosing = [(start, name) for start, end, name in spans if start <= lineno <= end]
    return max(enclosing)[1] if enclosing else _MODULE_SCOPE


# --------------------------------------------------------------------- #
# Shape 1: a single literal already containing the whole relative shape #
# --------------------------------------------------------------------- #

_EMBEDDED_SLASH_LITERAL: Final = re.compile(r'Path\(\s*"([^"]*/[^"]*)"')

#: Modules that declare the taxonomy itself, or derive settings defaults from
#: it. These carry the vocabulary on purpose -- they are what everything else
#: resolves through -- so they are excluded from the production literal scan
#: rather than made to route their own declarations through themselves.
_TAXONOMY_DECLARATION_MODULES: Final[frozenset[str]] = frozenset(
    {
        "core/storage_taxonomy.py",
        "core/storage_taxonomy_locations.py",
        "core/config.py",
        "core/config_llm_fields.py",
        "core/config_integration_fields.py",
        "core/config_state_root.py",
    },
)


class LiteralSite(NamedTuple):
    """One production module naming an operator-data location by a bare literal."""

    module: str
    lineno: int
    literal: str


def embedded_slash_literal_sites(module: str, source: str) -> tuple[LiteralSite, ...]:
    """Return every ``Path("a/b")``-shaped literal in ``source`` naming taxonomy vocabulary.

    A pure function over a display name and the module's text, so the
    discrimination tests can hand it synthetic source and prove the shape
    fires or does not, without touching the filesystem.
    """
    vocabulary = _taxonomy_vocabulary()
    sites: list[LiteralSite] = []
    for match in _EMBEDDED_SLASH_LITERAL.finditer(source):
        literal = match.group(1)
        segments = {segment for segment in literal.split("/") if segment}
        if segments & vocabulary:
            lineno = source.count("\n", 0, match.start()) + 1
            sites.append(LiteralSite(module=module, lineno=lineno, literal=literal))
    return tuple(sites)


@cache
def _production_literal_sites() -> tuple[LiteralSite, ...]:
    sites: list[LiteralSite] = []
    for path in production_python_files():
        rel = aeat_relative(path)
        if rel in _TAXONOMY_DECLARATION_MODULES:
            continue
        sites.extend(embedded_slash_literal_sites(rel, path.read_text(encoding="utf-8")))
    return tuple(sites)


# --------------------------------------------------------------------- #
# Shape 2: two or more governed segments joined into one chain          #
# --------------------------------------------------------------------- #

_JOIN_METHODS: Final[frozenset[str]] = frozenset({"joinpath"})


class ChainSite(NamedTuple):
    """One place two or more taxonomy segments are chained into a literal path."""

    module: str
    function: str
    lineno: int
    segments: tuple[str, ...]

    @property
    def key(self) -> tuple[str, str]:
        """The declaration key: module and enclosing function."""
        return (self.module, self.function)


def _flatten_div_chain(node: ast.expr) -> list[ast.expr]:
    """Return a left-associative ``/`` chain's operands, left to right."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return [*_flatten_div_chain(node.left), node.right]
    return [node]


def _outermost_div_nodes(tree: ast.AST) -> list[ast.BinOp]:
    """Return each ``/`` chain's outermost node, so a chain is counted once.

    A nested ``BinOp`` chain visits every sub-expression under ``ast.walk``;
    without this, a five-hop chain would be inspected five times, once per
    intermediate node, each time seeing a different, truncated slice of it.
    """
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    tops: list[ast.BinOp] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        parent = parents.get(node)
        if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Div) and parent.left is node:
            continue
        tops.append(node)
    return tops


def chain_sites(module: str, tree: ast.AST) -> tuple[ChainSite, ...]:
    """Return every ``/``-join or ``.joinpath()`` chain naming 2+ taxonomy segments.

    A pure function over a display name and a parsed tree, so the
    discrimination tests can hand it synthetic source and prove each shape
    fires or does not.
    """
    vocabulary = _taxonomy_vocabulary()
    docstrings = _docstring_nodes(tree)
    spans = _function_spans(tree)
    sites: list[ChainSite] = []

    def _literal_segments(operands: list[ast.expr]) -> tuple[str, ...]:
        found: list[str] = []
        for operand in operands:
            if (
                isinstance(operand, ast.Constant)
                and isinstance(operand.value, str)
                and id(operand) not in docstrings
                and operand.value in vocabulary
            ):
                found.append(operand.value)
        return tuple(found)

    for top in _outermost_div_nodes(tree):
        operands = _flatten_div_chain(top)
        segments = _literal_segments(operands)
        if len(segments) >= 2:
            scope = _enclosing_scope(top.lineno, spans)
            sites.append(ChainSite(module=module, function=scope, lineno=top.lineno, segments=segments))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _JOIN_METHODS:
            segments = _literal_segments(list(node.args))
            if len(segments) >= 2:
                scope = _enclosing_scope(node.lineno, spans)
                sites.append(ChainSite(module=module, function=scope, lineno=node.lineno, segments=segments))

    return tuple(sites)


#: Whole modules whose hand-typed segments are the independent oracle for
#: what the resolver under test should produce. Each names its own reason in
#: its module docstring; re-expressing any of these through the accessor
#: would make the assertion compare the taxonomy against itself.
PERMITTED_PIN_MODULES: Final[frozenset[str]] = frozenset(
    {
        # storage_overrides()/relocated_storage_path() ARE the accessors under
        # test; the multi-segment expectation is the independent oracle their
        # own docstrings describe.
        "tests/test_storage_scope.py",
        # "The directory names asserted below are deliberate literals... the
        # expectation must come from outside the declaration."
        "core/tests/test_ensure_storage_tree.py",
        # "The oracle is the filesystem, walked after the fact, compared
        # against an expectation derived from STORAGE_TAXONOMY... calling the
        # same iteration the materialiser calls would assert nothing at all."
        "core/tests/test_storage_materialisation_parity.py",
        # classify_storage_route()'s own real on-disk shape is the subject
        # under test; re-deriving the expected side from the accessor would
        # let a Settings/classifier defect drift both sides in lockstep. Its
        # own module docstring justifies each pinned literal by name.
        "core/tests/test_storage_route_classification.py",
        # "...each is the independent oracle for what its settings field
        # defaults to when unoverridden, not scaffolding."
        "core/tests/test_storage_substrate_state_root.py",
        # "This module owns the on-disk-name oracle, and owning it is the
        # point... Deriving the expectation from the taxonomy would turn
        # every assertion below into the taxonomy compared with itself."
        "core/tests/test_output_dir_state_root.py",
    },
)

#: Narrower (module, function) pins for a single oracle assertion sitting in
#: an otherwise ordinary test module.
PERMITTED_PIN_SITES: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        # Pins cadrumo_database_url's pre-migration on-disk shape directly,
        # independent of the accessor either step under test consumes -- see
        # the function's own docstring.
        (
            "core/tests/test_storage_taxonomy_name_unification.py",
            "test_the_database_url_resolves_to_its_pre_migration_shape",
        ),
        # An arbitrary operator-supplied override value for a relative-path
        # env var, asserting anchor computation -- not the taxonomy's own
        # declared subpath for INVOICES/ATTACHMENTS. The segments overlap
        # with real category names by coincidence of a plausible-looking
        # probe value, not because this asserts what those categories
        # resolve to by default.
        (
            "core/tests/test_config.py",
            "TestRepoRelativePathNormalisationCoverage.test_relative_audit_flagged_paths_resolve_under_project_root",
        ),
    },
)


@cache
def _package_chain_sites() -> tuple[ChainSite, ...]:
    sites: list[ChainSite] = []
    for path in package_python_files():
        rel = aeat_relative(path)
        tree = ast_for_path(path)
        if tree is not None:
            sites.extend(chain_sites(rel, tree))
    return tuple(sites)


# --------------------------------------------------------------------- #
# The gate                                                               #
# --------------------------------------------------------------------- #


def test_the_scanned_corpus_and_the_taxonomy_vocabulary_are_both_non_degenerate() -> None:
    """The gate must be looking at the real tree with a real vocabulary, not nothing."""
    corpus = package_python_files()
    assert len(corpus) >= 500, (
        f"the literal scan walked only {len(corpus)} module(s), far fewer than the package holds; "
        "discovery has collapsed and every assertion below would report a clean tree it never read"
    )
    vocabulary = _taxonomy_vocabulary()
    assert len(vocabulary) >= 40, (
        f"the taxonomy vocabulary has only {len(vocabulary)} word(s); it governs dozens of "
        "declared members, so this means the vocabulary source collapsed"
    )
    assert {"buckets", "cache", "financial"} <= vocabulary, "the vocabulary must contain what it protects"


def test_no_production_module_names_an_operator_data_location_by_a_bare_literal() -> None:
    """Shape 1: a single literal already spelling the whole relative path."""
    offenders = sorted(f"{site.module}:{site.lineno}: Path({site.literal!r})" for site in _production_literal_sites())
    assert not offenders, (
        f"shipped module(s) naming an operator-data location by a bare literal instead of "
        f"resolving it through the storage taxonomy: {offenders}. Declare the member's "
        "StorageCategory and resolve it with storage_path/bucket_scoped_storage_path"
    )


def test_no_undeclared_module_chains_two_or_more_taxonomy_segments_into_a_literal_path() -> None:
    """Shape 2: production and test code alike, outside a declared pin."""
    declared_modules = PERMITTED_PIN_MODULES
    declared_sites = PERMITTED_PIN_SITES
    offenders = sorted(
        f"{site.module}:{site.lineno} in {site.function}: {'/'.join(site.segments)}"
        for site in _package_chain_sites()
        if site.module not in declared_modules and site.key not in declared_sites
    )
    assert not offenders, (
        f"module(s) hand-typing 2+ taxonomy-governed path segments into one literal chain instead "
        f"of resolving them through the storage taxonomy: {offenders}. Re-express the location "
        "through storage_path(category), bucket_scoped_storage_path(category, bucket_id), or "
        "storage_location(category).relative_path() when only the bucket-relative shape is needed. "
        "If the literal is a deliberate independent oracle for what the resolver should produce, "
        "declare it in PERMITTED_PIN_MODULES or PERMITTED_PIN_SITES with the reason"
    )


def test_every_permitted_pin_module_still_carries_a_qualifying_chain() -> None:
    """A pinned module that stopped chaining taxonomy segments is a stale permission."""
    carrying = {site.module for site in _package_chain_sites()}
    stale = sorted(PERMITTED_PIN_MODULES - carrying)
    assert not stale, (
        f"PERMITTED_PIN_MODULES names {stale}, which no longer chains 2+ taxonomy segments into a "
        "literal path; strike the entry in the same change that removed the literal, so the "
        "permission cannot outlive the assertion it was granted for"
    )


def test_every_permitted_pin_site_still_carries_a_qualifying_chain() -> None:
    """A pinned (module, function) that stopped chaining is a stale permission."""
    carrying = {site.key for site in _package_chain_sites()}
    stale = sorted(f"{module}::{function}" for module, function in PERMITTED_PIN_SITES - carrying)
    assert not stale, (
        f"PERMITTED_PIN_SITES names {stale}, which no longer chains 2+ taxonomy segments into a "
        "literal path; strike the entry in the same change, so the permission cannot outlive the "
        "assertion it was granted for"
    )


# --------------------------------------------------------------------- #
# Discrimination: each shape fires, and each control does not           #
# --------------------------------------------------------------------- #


def _chain_sites_in(source: str) -> tuple[ChainSite, ...]:
    return chain_sites("synthetic.py", ast.parse(source))


def test_the_chain_detector_fires_on_a_binop_join_of_two_segments() -> None:
    source = 'def make(tmp_path):\n    return tmp_path / "buckets" / "primary" / "db" / "cadrumo.db"\n'
    (site,) = _chain_sites_in(source)
    assert site.segments == ("buckets", "db", "cadrumo.db")
    assert site.function == "make"


def test_the_chain_detector_fires_on_a_joinpath_call() -> None:
    source = 'def make(tmp_path):\n    return tmp_path.joinpath("cache", "llm-cache")\n'
    (site,) = _chain_sites_in(source)
    assert site.segments == ("cache", "llm-cache")


def test_the_chain_detector_stays_silent_on_a_single_taxonomy_segment() -> None:
    """One common word alone (``"cache"``, ``"data"``, ``"db"``...) is not enough signal."""
    source = 'def make(tmp_path):\n    return tmp_path / "cache"\n'
    assert _chain_sites_in(source) == ()


def test_the_chain_detector_stays_silent_on_a_docstring_mention() -> None:
    source = '"""References buckets and db together, but never joins them."""\n'
    assert _chain_sites_in(source) == ()


def test_the_chain_detector_counts_a_five_hop_chain_once() -> None:
    """A long chain is one site, not one per intermediate BinOp node."""
    source = 'def make(tmp_path):\n    return tmp_path / "buckets" / "id" / "custody" / "envelope.v1.json"\n'
    assert len(_chain_sites_in(source)) == 1


def test_the_chain_detector_attributes_a_site_to_its_innermost_function() -> None:
    source = 'def outer(tmp_path):\n    def inner():\n        return tmp_path / "buckets" / "db"\n    return inner\n'
    (site,) = _chain_sites_in(source)
    assert site.function == "outer.inner"


def test_the_embedded_slash_literal_detector_fires_on_the_historical_defect_shape() -> None:
    sites = embedded_slash_literal_sites("synthetic.py", 'Path("var/cadrumo/filed-declarations")')
    assert len(sites) == 1
    assert sites[0].literal == "var/cadrumo/filed-declarations"


def test_the_embedded_slash_literal_detector_stays_silent_on_a_slash_free_literal() -> None:
    assert embedded_slash_literal_sites("synthetic.py", 'Path("buckets")') == ()


def test_the_embedded_slash_literal_detector_stays_silent_on_no_vocabulary_overlap() -> None:
    assert embedded_slash_literal_sites("synthetic.py", 'Path("unrelated/segment")') == ()


# --------------------------------------------------------------------- #
# Teeth: an isolated fixture, not the live tree, proves the pipeline    #
# --------------------------------------------------------------------- #


def test_the_gate_detects_a_representative_defect_in_an_isolated_fixture(tmp_path: Path) -> None:
    """End to end: a module planted outside the live tree is still caught.

    Proves the detection function itself, not merely that today's tree is
    clean -- a gate that only ever ran against an already-fixed corpus could
    have stopped detecting anything and no assertion here would notice.
    """
    offending = tmp_path / "planted_offender.py"
    offending.write_text(
        'def build(tmp_path):\n    return tmp_path / "buckets" / "primary" / "db" / "cadrumo.db"\n',
        encoding="utf-8",
    )
    tree = ast.parse(offending.read_text(encoding="utf-8"))

    found = chain_sites("planted_offender.py", tree)

    assert len(found) == 1
    assert found[0].segments == ("buckets", "db", "cadrumo.db")
    assert ("planted_offender.py", "build") not in PERMITTED_PIN_SITES
    assert "planted_offender.py" not in PERMITTED_PIN_MODULES
