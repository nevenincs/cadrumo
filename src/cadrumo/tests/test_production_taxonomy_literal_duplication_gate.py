"""Two production modules must not independently declare the same taxonomy segment.

The sibling of :mod:`.test_pinned_taxonomy_literal_conformance`. That gate
polices *tests* deliberately opting in to hand-typing a taxonomy segment as an
independent oracle. This one polices *production*: a production module has no
legitimate reason to hand-type a taxonomy segment at all -- it should read the
declaration (``storage_location(StorageCategory.X).subpath``, an existing
``*_DIRNAME``/``*_FILENAME`` re-export, or import a sibling module's own named
constant) rather than mint a second copy that happens to agree today, per
``aeat-registry-authority-flow``.

Real bugs, already fixed while measuring this gate's precision (not by this
change): ``secret_store/_secret_store.py`` independently hand-typed
``_INDEX_FILE_NAME = "index.json"`` alongside
``adapters/persistence/storage/_storage_path_definitions.py``'s own
``SECRET_INDEX_FILENAME = "index.json"``, and
``core/observability/_context.py`` independently re-declared
``_EVENTS_FILENAME = "events.jsonl"`` instead of importing the declaration
already living in ``core/observability/_store.py`` (now the public
``EVENTS_FILENAME``, promoted by a later, related fix -- see the scope
section below). Both are gone -- scanning the current tree confirms the fix
rather than assuming it (see the precision section below).

Why "a segment bound to a constant" needed a scanner distinct from every
join-position instrument in this tree (the test-side gate above, the storage
provenance gate, treegates' census): none of them can see it. A ``/``-join
detector looks for a literal immediately following a division operator or a
``joinpath``/``Path(...)`` call; ``_EVENTS_FILENAME = "events.jsonl"`` is a
bare assignment, and the literal only ever enters a join chain *after* being
bound to a name, several call frames away from its declaration. This gate's
shape is therefore deliberately different from all of them: it matches the
*binding*, not the *use*.

Why pairwise, not vocabulary-membership alone
-----------------------------------------------
A first design flagged any non-authority production constant whose value
matched the taxonomy vocabulary, at all. Running it against the tree as it
stood when this gate was written found ``SECRET_INDEX_FILENAME = "index.json"``
in ``_storage_path_definitions.py`` and ``_TRACE_FILENAME`` /
``_EVENTS_FILENAME`` / ``_ENVELOPE_FILENAME`` in ``core/observability/_store.py``
-- all four **sole, legitimate, already-canonical declaring sites** for a
finer-grained (filename-level, not directory-level) piece of vocabulary the
core taxonomy does not itself model, wrongly flagged as if they duplicated
something. (The three ``_store.py`` names have since been promoted to public
-- ``TRACE_FILENAME`` / ``EVENTS_FILENAME`` / ``ENVELOPE_FILENAME`` -- and read
by ``_storage_path_definitions.py``'s own grammar, a related but separate fix;
see the scope section below. Kept here as the worked example that falsified
the membership-only design, not as a claim about the tree today.) A constant
is only evidence of duplication when a SECOND independent site declares the
identical value; a single declaration, however it got there, is simply where a
name currently lives. So the gate requires **two or more** non-authority
production sites sharing one value before it calls it a duplicate --
vocabulary membership is used only as a relevance filter (confirms the shared
value is a real on-disk segment, not an unrelated coincidence), never as the
sole trigger.

This also matches how the two real bugs actually looked before their fix:
each was *exactly* two independent sites agreeing on one string. The pairwise
requirement does not weaken the gate against that class -- it is the same
shape the bugs had.

Scope, stated exactly (read before trusting a clean run)
----------------------------------------------------------
Matched: a plain assignment or annotated assignment, at MODULE level or at the
immediate body level of a class (so an enum member or a dataclass/pydantic
field with a literal default is caught the same way a bare module constant
is), whose target is a single name and whose value is a string constant.
Function-local constants are NOT scanned -- the class this gate targets is a
NAMED constant meant to be imported, and by convention in this codebase that
lives at module or class level, not inside a function body. NOT reachable at
all, as a matter of the AST shape rather than the current tree's content: a
literal embedded inside an f-string template. Several
``StoragePathDefinition.grammar`` entries in ``_storage_path_definitions.py``
used to hardcode a leaf filename this way instead of interpolating a named
constant the way ``{RUNS_DIRNAME}`` already was -- ``run_trace`` / ``run_events``
/ ``run_envelope`` were the found instance, fixed
(``relocation:core.observability.TRACE_FILENAME,EVENTS_FILENAME,ENVELOPE_FILENAME``)
once this gate's own docstring surfaced it as found-not-fixed. The blind spot
itself is not: the literal never appears as a bare ``ast.Constant``, only as
one segment of an ``ast.JoinedStr``, so a future f-string-embedded duplicate
of this same shape would again be invisible here. Vocabulary is the union of
every
:data:`~cadrumo.core.STORAGE_TAXONOMY` subpath segment (the core, directory-
level authority) and every non-templated ``/``-segment of every
:data:`~cadrumo.adapters.persistence.storage.STORAGE_PATH_DEFINITIONS`
grammar (the adapter-layer, filename-level registry) -- both are genuinely
"a declaration the taxonomy already owns", at two different granularities.

Precision, measured rather than assumed
-----------------------------------------
On the current product tree, ``"financial"`` is the one verified homonym:
``SensitivityClass.FINANCIAL``, a data
classification, versus ``SpendingCategory.FINANCIAL``, an IRPF deduction
category) -- two unrelated closed axes each independently choosing the same
English word, not an unmigrated storage-path duplicate. Zero genuine
duplicates remain at this scope beyond the fixes already made. That is a small
enough exception surface, on a real found bug class, to be worth gating on.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from functools import cache
from pathlib import PurePosixPath
from typing import Final, cast

import pytest

from ..adapters.persistence.storage import STORAGE_PATH_DEFINITIONS
from ..core import STORAGE_TAXONOMY
from ._inventory import aeat_relative, ast_for_path, production_python_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_MAX_TOKEN_LEN: Final[int] = 48
"""Generous ceiling above the longest real taxonomy token (under 32 chars);
see the sibling test-side gate for the identical reasoning."""

AUTHORITY_MODULES: Final[frozenset[str]] = frozenset(
    {
        "core/_storage_taxonomy.py",
        "core/_storage_taxonomy_locations.py",
    },
)
"""The two modules excluded from the scan entirely -- not just from being reported.

Excluded by FILE PATH, never by listing the names declared inside them. Two
reasons, both structural: the declaring module is not a duplicate of itself,
and the taxonomy legitimately re-uses the same on-disk name at different
SCOPES on purpose (``"blobs"``/``"audit"`` each name both a root-level
category and a per-bucket subdirectory --
:func:`~.test_storage_taxonomy.test_the_duplicated_names_resolve_to_distinct_members`
asserts exactly this) -- so counting the authority's own internal
scope-pairs as a "duplicate" would flag deliberate, tested design. A third
module that starts declaring taxonomy subpaths as its own job belongs here
too, added deliberately -- not discovered by this gate reddening on it.
"""


HOMONYM_EXCEPTIONS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("core/classification/__init__.py", "financial"),
        ("domain/categories/_spending_category.py", "financial"),
        # SensitivityClass.FINANCIAL (StrEnum) -- a data-classification axis
        # (how a record must be encrypted/redacted). SpendingCategory.FINANCIAL
        # (StrEnum) -- an IRPF economic-activity deduction category ("gastos
        # financieros"). Neither is a directory; the module-level docstring
        # history of ``core/classification`` already warns this exact word
        # produced a false-green liveness gate once by being keyed on the
        # bare string instead of the enum type.
    },
)
"""Verified coincidental collisions with the taxonomy vocabulary: read, and confirmed not a duplicate.

Every entry is checked below by :func:`test_every_homonym_exception_is_still_a_live_collision`.
"""


@cache
def _taxonomy_vocabulary() -> frozenset[str]:
    """The union of the core directory-level authority and the adapter filename-level registry.

    :data:`~cadrumo.core.STORAGE_TAXONOMY` supplies every subpath's individual
    path segments -- the same derivation the sibling test-side gate uses, kept
    as an independent copy rather than a shared import for the same reason
    given there: the two gates read different scan surfaces and are meant to
    be individually rerunnable and readable.

    :data:`~cadrumo.adapters.persistence.storage.STORAGE_PATH_DEFINITIONS`
    additionally supplies the finer, filename-level tier the core taxonomy
    does not itself model (``events.jsonl``, ``index.json``, ...) -- read
    from each grammar's ``/``-segments, skipping any segment carrying a
    ``<...>`` template placeholder (a real path component is never spelled
    with angle brackets) and any grammar that is not rooted at ``<root>/``
    (the one non-filesystem entry, ``secure_objects_table``, is a
    ``db://...`` logical key, not an on-disk segment at all).
    """
    tokens: set[str] = set()
    for location in STORAGE_TAXONOMY.values():
        tokens.update(PurePosixPath(location.subpath).parts)
    for definition in STORAGE_PATH_DEFINITIONS:
        if not definition.grammar.startswith("<root>/"):
            continue
        for segment in definition.grammar.split("/"):
            if not segment or "<" in segment or ">" in segment:
                continue
            tokens.add(segment)
    return frozenset(tokens)


class _NamedConstant:
    """One module/class-level ``NAME = "literal"`` binding."""

    __slots__ = ("lineno", "module", "name", "value")

    def __init__(self, module: str, name: str, value: str, lineno: int) -> None:
        self.module = module
        self.name = name
        self.value = value
        self.lineno = lineno


def _named_constants(module: str, tree: ast.AST) -> tuple[_NamedConstant, ...]:
    """Return every module-level or immediate-class-body ``NAME = "string"`` binding.

    Deliberately not a full ``ast.walk``: a plain iteration of ``tree.body``
    plus one level into each ``ClassDef``'s own body, so a function-local
    constant (out of scope -- see the module docstring) is never visited at
    all, rather than visited and then filtered.
    """
    found: list[_NamedConstant] = []

    def scan(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                scan(node.body)
                continue
            targets: list[ast.expr]
            value: ast.expr | None
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = [cast("ast.expr", node.target)], node.value
            else:
                continue
            if value is None or not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
                continue
            if "\n" in value.value or len(value.value) > _MAX_TOKEN_LEN:
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    found.append(_NamedConstant(module, target.id, value.value, node.lineno))

    scan(tree.body if isinstance(tree, ast.Module) else [])
    return tuple(found)


@cache
def _scan_production_tree() -> tuple[_NamedConstant, ...]:
    """Walk every non-authority production module once, returning every candidate binding."""
    found: list[_NamedConstant] = []
    for path in production_python_files():
        module = aeat_relative(path)
        if module in AUTHORITY_MODULES:
            continue
        tree = ast_for_path(path)
        if tree is None:
            continue
        found.extend(_named_constants(module, tree))
    return tuple(sorted(found, key=lambda entry: (entry.module, entry.lineno)))


def _pairwise_taxonomy_duplicates() -> tuple[_NamedConstant, ...]:
    """The scanned bindings whose value is a real taxonomy token AND has 2+ declaring sites.

    A single declaration, however it got there, is simply where a name
    currently lives -- see the module docstring's "why pairwise" section.
    """
    vocabulary = _taxonomy_vocabulary()
    by_value: dict[str, list[_NamedConstant]] = defaultdict(list)
    for entry in _scan_production_tree():
        if entry.value in vocabulary:
            by_value[entry.value].append(entry)
    return tuple(entry for entries in by_value.values() if len(entries) >= 2 for entry in entries)


def test_the_scanned_corpus_is_not_degenerate() -> None:
    """The gate must be reading a real production tree, not finding nothing to check.

    A bound, not a count: an exact figure rots on the next ordinary module.
    """
    scanned = _scan_production_tree()
    assert len(scanned) >= 200, (
        f"found only {len(scanned)} module/class-level string constant(s) across the production "
        "tree, expected at least 200. Discovery has likely broken (production_python_files, or the "
        "AnnAssign/Assign walk), not that most modules stopped declaring named constants"
    )


def test_no_two_production_modules_independently_declare_the_same_taxonomy_segment() -> None:
    """The gate: 2+ non-authority sites agreeing on one taxonomy-vocabulary value is a duplicate."""
    exceptions = HOMONYM_EXCEPTIONS
    duplicated = sorted(
        f"{entry.module}:{entry.lineno} {entry.name} = {entry.value!r}"
        for entry in _pairwise_taxonomy_duplicates()
        if (entry.module, entry.value) not in exceptions
    )
    assert not duplicated, (
        f"two or more production modules independently declare the same taxonomy segment: "
        f"{duplicated}. Pick one canonical site (read `storage_location(StorageCategory.<member>)"
        ".subpath`, import an existing *_DIRNAME/*_FILENAME re-export, or import the sibling "
        "module's own named constant) and delete the other copy -- or, if this is a verified "
        "coincidental homonym on a different closed axis, add it to HOMONYM_EXCEPTIONS with the "
        "reason, never silently"
    )


def test_every_homonym_exception_is_still_a_live_collision() -> None:
    """A homonym exception that stopped colliding is dead weight -- or hiding that the module moved on.

    Mirrors the sibling test-side gate's reconciliation test: an entry whose
    named module no longer contains the literal, at the 2+-site threshold, at
    all, has drifted and must be struck, not left describing code that
    changed.
    """
    still_present = {(entry.module, entry.value) for entry in _pairwise_taxonomy_duplicates()}
    drifted = sorted(pair for pair in HOMONYM_EXCEPTIONS if pair not in still_present)
    assert not drifted, (
        f"HOMONYM_EXCEPTIONS names a collision no longer found in the tree at the 2+-site "
        f"threshold: {drifted}. Strike the stale entries -- either the constant was removed/renamed, "
        "or its sibling collision site was fixed so only one site remains (which is itself good news, "
        "not a gate to silence)"
    )


def test_no_authority_module_is_also_a_homonym_exception() -> None:
    """An authority module cannot also be exempted as a coincidental collision -- it IS the declaration."""
    overlap = sorted(module for module, _literal in HOMONYM_EXCEPTIONS if module in AUTHORITY_MODULES)
    assert not overlap, f"{overlap} appear in both AUTHORITY_MODULES and HOMONYM_EXCEPTIONS"


def test_the_authority_modules_still_declare_the_vocabulary_they_are_excused_for() -> None:
    """An authority exclusion for a module that no longer declares anything is excusing nothing.

    Guards the structural exclusion itself: if either authority module were
    refactored away from declaring taxonomy segments, the path-based
    exclusion would keep silently exempting a module no longer playing that
    role, with nothing here to notice.
    """
    vocabulary = _taxonomy_vocabulary()
    by_module: dict[str, list[str]] = {}
    for path in production_python_files():
        module = aeat_relative(path)
        if module not in AUTHORITY_MODULES:
            continue
        tree = ast_for_path(path)
        if tree is None:
            continue
        by_module[module] = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in vocabulary
        ]
    missing = sorted(module for module in AUTHORITY_MODULES if not by_module.get(module))
    assert not missing, (
        f"{missing} declare(s) no taxonomy-vocabulary literal anywhere -- confirm this module is "
        "still the declaring authority before trusting its structural exclusion from the gate above"
    )


# --------------------------------------------------------------------- #
# Discrimination: the comparison fires on seeded drift, on synthetic     #
# in-memory source only -- no file in the tree is ever mutated to prove  #
# this, so there is no mutation window to clean up afterward.            #
# --------------------------------------------------------------------- #


def _constants_in(module: str, source: str) -> tuple[_NamedConstant, ...]:
    return _named_constants(module, ast.parse(source))


def _pairwise_among(*module_sources: tuple[str, str]) -> tuple[_NamedConstant, ...]:
    """Reimplements the pairwise-grouping step over a synthetic module set, for the discrimination tests."""
    vocabulary = _taxonomy_vocabulary()
    all_entries: list[_NamedConstant] = []
    for module, source in module_sources:
        all_entries.extend(_constants_in(module, source))
    by_value: dict[str, list[_NamedConstant]] = defaultdict(list)
    for entry in all_entries:
        if entry.value in vocabulary:
            by_value[entry.value].append(entry)
    return tuple(entry for entries in by_value.values() if len(entries) >= 2 for entry in entries)


def test_the_detector_fires_on_two_independent_module_level_declarations() -> None:
    """The dominant real shape: two bare module constants, neither reading the other."""
    duplicates = _pairwise_among(
        ("a.py", '_EVENTS_FILENAME = "events.jsonl"\n'),
        ("b.py", '_EVENTS_FILENAME = "events.jsonl"\n'),
    )
    assert {entry.module for entry in duplicates} == {"a.py", "b.py"}


def test_the_detector_fires_across_a_module_declaration_and_an_enum_member() -> None:
    """The second real shape: one site is a bare constant, the other is a class-body enum member."""
    duplicates = _pairwise_among(
        ("a.py", '_FILENAME = "buckets"\n'),
        ("b.py", 'from enum import StrEnum\n\nclass Foo(StrEnum):\n    BUCKETS = "buckets"\n'),
    )
    assert {entry.module for entry in duplicates} == {"a.py", "b.py"}


def test_the_detector_stays_silent_on_a_sole_declaring_site() -> None:
    """A single module declaring a taxonomy segment, with nothing else agreeing, is not a duplicate.

    The exact shape ``SECRET_INDEX_FILENAME`` and ``_TRACE_FILENAME`` turned
    out to be: the sole, legitimate, current declaration of a piece of
    vocabulary -- see the module docstring's "why pairwise" section for why
    an earlier, vocabulary-membership-only design wrongly flagged both.
    """
    duplicates = _pairwise_among(("a.py", 'SECRET_INDEX_FILENAME = "index.json"\n'))
    assert duplicates == ()


def test_the_detector_stays_silent_on_a_function_local_constant() -> None:
    """Out of scope by design -- see the module docstring's stated scope."""
    entries = _constants_in(
        "synthetic.py",
        'def build():\n    _filename = "events.jsonl"\n    return _filename\n',
    )
    assert entries == ()


def test_the_detector_stays_silent_on_a_docstring() -> None:
    """A prose mention is not a binding."""
    entries = _constants_in(
        "synthetic.py",
        '"""This module writes buckets to disk somewhere."""\n',
    )
    assert entries == ()


def test_an_authority_module_is_excluded_from_the_gate_by_path() -> None:
    """The structural exclusion: same literal, same shape, excused only because of which file it is in."""
    entry = _constants_in("core/_storage_taxonomy.py", 'BUCKETS_SUBPATH = "buckets"\n')[0]
    assert (entry.module, entry.value) not in HOMONYM_EXCEPTIONS  # not excused via the homonym route
    assert entry.module in AUTHORITY_MODULES  # excused via the structural route instead


def test_the_detector_stays_silent_on_a_non_string_constant() -> None:
    """An integer or other non-string constant is never a taxonomy segment.

    ``SECRET_INDEX_SCHEMA_VERSION = 1``-shaped duplication (a schema-version
    constant independently re-declared) is a real bug class found and fixed
    alongside the two this gate covers, but it targets taxonomy *segments*,
    which are strings by definition -- that property belongs to a separate
    instrument, not this one.
    """
    entries = _constants_in("synthetic.py", "SECRET_INDEX_SCHEMA_VERSION = 1\n")
    assert entries == ()
