"""A declared location nothing touches is a decision nobody has taken.

Four categories in this taxonomy have no production consumer whatsoever. They
were found by audit, late, and only because someone went looking; nothing in
the suite could have said so, because a declaration is satisfied by being
written down. This gate makes the condition loud at the point of declaration
instead of discoverable at the point of audit.

**Declare, then verify.** Each member states either a ``consumer_module`` or a
``dormant_reason``, the model refuses a member that states both or neither, and
this gate checks the claim structurally against the named module's AST. The
declaration alone never satisfies the gate -- "it has a consumer because it says
it has one" is exactly the shape being rejected.

Why not whole-program write-reachability: tracing statically from an attribute
load to a filesystem write produces a false negative on every indirection, and
a gate that blocks legitimate changes is one somebody switches off the first
time it is inconvenient. Consumption is weaker in theory and far stronger in
practice, because a location no module touches cannot be written to.

What counts as evidence
------------------------
A claim is satisfied by an ``ast.Attribute`` load of the category member whose
receiver resolves to a name bound to ``StorageCategory``. Nothing else counts:
there is no per-member settings field or environment variable to name any more,
and nothing in this codebase resolves a ``StorageCategory`` member dynamically
by name.

The receiver qualification matters. A bare attribute name is not unique to
``StorageCategory``: this gate once accepted 14 references to an unrelated enum
member that happened to share a storage member name as proof that the storage
category was consumed. The receiver has to resolve to a name bound to
``StorageCategory`` (see :func:`_storage_category_binding_names`).

A mention in a docstring or a string is not a consumption either. A docstring
is an ``ast.Constant``, which an attribute walk cannot see, so a module that
names a member only to record that it is independent of it cannot satisfy a
claim. Four independent passes once agreed on a dormancy verdict while sharing
one weak method; a mention is not a consumption, and this is where that lesson
is encoded.
"""

from __future__ import annotations

import ast
import unicodedata
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from types import MappingProxyType

import pytest

from ...tests.inventory import releases_parsed_sources
from ..directory_scan import scan_directory
from ..storage_taxonomy import StorageLocation
from ..storage_taxonomy_locations import STORAGE_TAXONOMY

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

SRC_CADRUMO = Path(__file__).resolve().parents[2]


def _storage_category_binding_names(tree: ast.AST) -> set[str]:
    """Return every local name bound to the ``StorageCategory`` enum in ``tree``.

    Mirrors the discriminator this project already uses for ``Modelo`` member
    references (``test_generic_module_modelo_carveouts.py``): a bare attribute
    name is not evidence of a reference to a SPECIFIC enum, only its receiver
    resolving to that enum's own bound name is. A module may import the enum
    under an alias, so the alias set -- not the literal string
    ``"StorageCategory"`` alone -- is what a reference must resolve against.
    """
    names = {"StorageCategory"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(
                alias.asname
                for alias in node.names
                if alias.name == "StorageCategory" and (alias.asname is not None and alias.asname)
            )
    return names


def consumes_member(tree: ast.AST, *, category_member: str) -> bool:
    """Whether the module genuinely references ``StorageCategory.<category_member>``.

    A pure function over a parsed tree, so the discrimination tests can hand it
    synthetic source and prove each shape counts or does not.

    ``category_member`` is a bare enum-member name shared with other closed-value
    enums in this codebase. An attribute load only counts when its receiver
    resolves to a name bound to ``StorageCategory`` (see
    :func:`_storage_category_binding_names`); a bare ``.AUDIT`` on anything else
    is not evidence. A string constant naming the member is never evidence.

    Args:
        tree: The consuming module's parsed AST.
        category_member: The category member's bare enum-member name.
    """
    category_owners = _storage_category_binding_names(tree)
    return any(
        isinstance(node, ast.Attribute)
        and node.attr == category_member
        and isinstance(node.value, ast.Name)
        and node.value.id in category_owners
        for node in ast.walk(tree)
    )


_CONSUMER_ROOTS = (SRC_CADRUMO, SRC_CADRUMO.parent)


@releases_parsed_sources
@cache
def _tree_for(module: str) -> ast.AST | None:
    for root in _CONSUMER_ROOTS:
        path = root / module
        if path.is_file():
            return ast.parse(path.read_text(encoding="utf-8"))
    return None


def _members_claiming_a_consumer() -> tuple[StorageLocation, ...]:
    return tuple(location for location in STORAGE_TAXONOMY.values() if location.consumer_module is not None)


def test_the_taxonomy_declares_a_liveness_claim_for_every_member() -> None:
    """Totality, enforced on the model so a new member cannot skip the question."""
    unclaimed = sorted(
        category.value
        for category, location in STORAGE_TAXONOMY.items()
        if location.consumer_module is None and location.dormant_reason is None
    )
    assert not unclaimed, (
        f"storage taxonomy member(s) {unclaimed} declare neither a consumer_module nor a "
        "dormant_reason. Name the production module that consumes the location, or state why "
        "nothing does -- a member that answers neither is a location the application creates and "
        "may never use"
    )

    # Totality over an empty taxonomy is vacuous, and a collapsed member set
    # would also make every consumer claim below trivially satisfied -- the
    # gate would report a fully live tree while inspecting nothing. Bounds,
    # not counts, so the floor survives an ordinary new member.
    assert len(STORAGE_TAXONOMY) >= 30, (
        f"the taxonomy declares only {len(STORAGE_TAXONOMY)} member(s); it governs dozens of "
        "locations, so this means the declaration collapsed and every assertion here holds "
        "vacuously"
    )
    claiming = _members_claiming_a_consumer()
    assert len(claiming) >= 20, (
        f"only {len(claiming)} member(s) claim a consumer. Most declared locations are live, so a "
        "number this low means either the claims were stripped or nearly everything was marked "
        "dormant -- and 'everything is dormant' passes this gate while meaning nothing"
    )


def test_every_named_consumer_module_exists() -> None:
    """A claim pointing at a module that is gone is not a claim."""
    missing = sorted(
        f"{location.category.value} -> {location.consumer_module}"
        for location in _members_claiming_a_consumer()
        if _tree_for(location.consumer_module or "") is None
    )
    assert not missing, (
        f"consumer_module claim(s) naming a module that does not exist: {missing}. Re-point the "
        "claim in the same change that moves or deletes the module"
    )


def test_every_consumer_claim_is_backed_by_a_real_reference() -> None:
    """The verification half. A mention in prose satisfies nothing."""
    unbacked: list[str] = []
    for location in _members_claiming_a_consumer():
        module = location.consumer_module or ""
        tree = _tree_for(module)
        if tree is None:
            continue
        if not consumes_member(tree, category_member=location.category.name):
            unbacked.append(
                f"{location.category.value} claims {module}, which does not reference "
                f"StorageCategory.{location.category.name}"
            )
    assert not unbacked, (
        f"consumer_module claim(s) the named module does not back: {unbacked}. Either the "
        "consumption moved -- re-point the claim at the module that now reads the location -- or "
        "it was removed, in which case the member is dormant and must say so with a reason. This "
        "is the event no other check catches: the field quietly became dead"
    )


def test_every_dormant_member_states_a_reason_and_really_is_dormant() -> None:
    """A dormant claim is refuted by any module that consumes the member.

    The converse direction, and the one that keeps the dormancy list honest: if
    someone wires a category up, its declaration must stop calling it dormant
    rather than sitting there contradicting the code.
    """
    contradicted: list[str] = []
    for location in STORAGE_TAXONOMY.values():
        if location.dormant_reason is None:
            continue
        assert location.dormant_reason.strip(), f"{location.category.value} declares an empty dormant reason"
        for module in _production_sources():
            # A module that never spells the member's name cannot reference it.
            # The loop is one pass over every production module PER dormant
            # member, so this substring test replaces the great majority of
            # those walks without changing which modules can contribute
            # evidence. It also decides which modules are parsed at all, so a
            # module no dormant member names is never read into a syntax tree.
            if location.category.name not in _searchable_source(module):
                continue
            tree = _production_tree(module)
            if tree is None:
                continue
            if consumes_member(tree, category_member=location.category.name):
                contradicted.append(f"{location.category.value} is declared dormant but {module} references it")
                break
    assert not contradicted, (
        f"dormancy claim(s) the tree refutes: {contradicted}. A member that gained a consumer must "
        "trade its dormant_reason for a consumer_module naming that module"
    )


#: The modules that DECLARE the taxonomy, as opposed to consuming it.
_TAXONOMY_DECLARATION_MODULES = frozenset(
    {"core/storage_taxonomy.py", "core/storage_taxonomy_locations.py"},
)


@releases_parsed_sources
@cache
def _production_sources() -> Mapping[str, str]:
    """Every production module's source text, read once, by relative path.

    Only the text is held. The dormancy sweep is quadratic -- every production
    module, once per dormant member -- and the substring test below retires the
    great majority of those iterations before any tree is needed, so parsing
    every module up front bought nothing but time and a syntax tree per module
    that stayed resident for the rest of the process.

    Test modules are excluded deliberately: a fixture that sets a field proves
    only that the field can be set, not that anything reads it back. Three of
    the four dormant members are set by test fixtures and consumed by nothing,
    which is precisely the shape a test-inclusive sweep would have missed.
    """
    sources: dict[str, str] = {}
    for path in scan_directory(SRC_CADRUMO, pattern="*.py", recursive=True):
        relative = path.relative_to(SRC_CADRUMO).as_posix()
        # Both declaration modules are excluded: a member's own declaration
        # names it by construction, so counting the declaration as consumption
        # refutes every dormancy claim with itself. The locations module was
        # split out of the taxonomy module and inherited that requirement.
        if "/tests/" in f"/{relative}" or relative.startswith("tests/") or relative in _TAXONOMY_DECLARATION_MODULES:
            continue
        sources[relative] = path.read_text(encoding="utf-8")
    return MappingProxyType(sources)


@releases_parsed_sources
@cache
def _searchable_source(module: str) -> str:
    """Return the text a bare-name substring test may be run against.

    Python resolves an identifier through NFKC, so a module can spell a name in
    characters a literal substring test would not find, and the prefilter would
    then hide a real reference from the walks that decide the claim. Normalising
    is skipped for a pure-ASCII module, which is nearly all of them, so the
    prefilter stays one substring test per module and member.
    """
    source = _production_sources()[module]
    return source if source.isascii() else unicodedata.normalize("NFKC", source)


@releases_parsed_sources
@cache
def _production_tree(module: str) -> ast.AST | None:
    """Parse one production module, for the few the prefilter did not retire."""
    try:
        return ast.parse(_production_sources()[module])
    except SyntaxError:  # pragma: no cover - a syntactically broken module fails elsewhere
        return None


# --------------------------------------------------------------------- #
# Discrimination: what counts as evidence, and what must not             #
# --------------------------------------------------------------------- #

_CATEGORY_MEMBER = "INBOX"


def _consumes(source: str) -> bool:
    return consumes_member(ast.parse(source), category_member=_CATEGORY_MEMBER)


def test_a_docstring_mention_is_not_a_consumption() -> None:
    """The single most important assertion in this module.

    A module naming a member in its docstring -- often precisely to record that
    it does *not* use it -- must not satisfy a consumer claim. This is the trap
    four independent passes fell into, encoded so a fifth cannot.
    """
    assert not _consumes('"""This module is deliberately independent of StorageCategory.INBOX."""\n')
    assert not _consumes('def read():\n    """Nothing here touches StorageCategory.INBOX."""\n    return None\n')
    assert not _consumes('class Reader:\n    """Unrelated to INBOX."""\n\n    x = 1\n')


def test_an_unrelated_enum_member_of_the_same_name_is_not_a_consumption() -> None:
    """The namespace-qualification proof: ``Other.INBOX`` is not ``StorageCategory.INBOX``.

    This is the real defect this gate shipped with: references to an unrelated
    same-named enum member satisfied a storage consumer claim. An attribute
    name alone is not enough; the receiver has to resolve
    to a name bound to ``StorageCategory``.
    """
    assert not _consumes("def read():\n    return Other.INBOX\n")
    assert _consumes("def read():\n    return StorageCategory.INBOX\n"), (
        "a genuine StorageCategory.INBOX reference must still count"
    )


def test_an_aliased_import_of_the_enum_still_counts() -> None:
    source = (
        "from taxonomy import StorageCategory as Category\n\ndef read():\n    return storage_path(Category.INBOX)\n"
    )
    assert _consumes(source)


def test_a_bare_category_member_string_is_not_a_consumption() -> None:
    """A category member is not looked up dynamically by name anywhere in this codebase."""
    assert not _consumes('def read():\n    return getattr(taxonomy, "INBOX")\n')


def test_consumption_is_found_below_module_level() -> None:
    """A member consumed inside a method, not at module top level, stays green."""
    source = (
        "class Writer:\n"
        "    def persist(self, settings):\n"
        '        target = storage_path(StorageCategory.INBOX, settings=settings) / "doc.pdf"\n'
        "        return target\n"
    )
    assert _consumes(source)


def test_an_unrelated_module_yields_no_evidence() -> None:
    """The positive control: a detector that fired on everything would be useless."""
    assert not _consumes("def read(settings):\n    return storage_path(StorageCategory.DRAFTS, settings=settings)\n")
