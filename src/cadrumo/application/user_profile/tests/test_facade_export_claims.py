"""One symbol, one claimed home, on the package facade's re-export table.

``_LAZY_EXPORTS`` is built as a dict comprehension over ``(module, names)``
pairs, so a name listed under two modules does not collide -- the later pair
silently overwrites the earlier one and the survivor is decided by source
order. That is invisible at runtime by construction: the built dict holds one
entry per name whichever pair won, so nothing an importing test could observe
distinguishes a deliberate home from an accidental one. The claim table has to
be read from the SOURCE to see the losing claim at all, which is why this gate
parses the module rather than importing it and inspecting the result.

The failure that shape produces is not a wrong import path but a dead one. A
name misfiled under a module that does not define it resolves correctly only
while its true owner sorts later; reordering the pairs -- a formatting pass, an
alphabetisation, a merge -- moves resolution to the module that does not define
it, and ``__getattr__`` raises :exc:`AttributeError` at the import site. The
name that carried the defect this gate was written for was
``reject_invalid_profile_facts``, the profile write door's own refusal, whose
import site is the one door every profile fact passes through.

The same truth is stated three times in that file -- the ``TYPE_CHECKING``
import block, the ``_LAZY_EXPORTS`` pairs, and ``__all__`` -- and the three are
hand-synchronised. Divergence between them is the general form of the same
slip, so all three are compared here rather than only the table that resolves
attributes.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
from typing import Final

import pytest

from ... import user_profile as facade

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FACADE_SOURCE: Final[Path] = Path(str(facade.__file__))

_LAZY_TABLE_NAME: Final[str] = "_LAZY_EXPORTS"

_MINIMUM_EXPECTED_CLAIMS: Final[int] = 100
"""A floor under the parse, not a pinned tally.

Every assertion below is satisfied vacuously by an empty claim list, so a
parser that silently stopped matching the table -- the table renamed, the
comprehension restructured -- would turn this whole module green while checking
nothing. The floor is deliberately far below the real count so that it bounds
the parse without becoming a number anyone has to maintain.
"""


def _claimed_names(node: ast.expr) -> tuple[str, ...]:
    """Read one pair's name collection: a literal tuple, or ``tuple(CONSTANT)``.

    Two pairs name a module-level frozenset instead of listing their members
    inline. Those are resolved against the imported module's real object rather
    than re-listed here, so this reader stays a reader: a gate carrying its own
    copy of the data it checks would pass while the file said something else.
    """
    if isinstance(node, ast.Tuple):
        return tuple(element.value for element in node.elts if isinstance(element, ast.Constant))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tuple":
        referenced = node.args[0]
        assert isinstance(referenced, ast.Name), f"unreadable name collection: {ast.unparse(node)}"
        resolved = getattr(facade, referenced.id)
        return tuple(sorted(resolved))
    raise AssertionError(f"unreadable name collection: {ast.unparse(node)}")


def _lazy_claims() -> list[tuple[str, str]]:
    """Every ``(name, module)`` claim the lazy table's source makes, duplicates kept."""
    tree = ast.parse(_FACADE_SOURCE.read_text(encoding="utf-8"))
    claims: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != _LAZY_TABLE_NAME:
            continue
        comprehension = node.value
        assert isinstance(comprehension, ast.DictComp), f"{_LAZY_TABLE_NAME} is no longer a dict comprehension"
        pairs = comprehension.generators[0].iter
        assert isinstance(pairs, ast.Tuple), f"{_LAZY_TABLE_NAME} no longer iterates a literal pair tuple"
        for pair in pairs.elts:
            assert isinstance(pair, ast.Tuple), f"unreadable pair: {ast.unparse(pair)}"
            module_node = pair.elts[0]
            assert isinstance(module_node, ast.Constant), f"unreadable module: {ast.unparse(module_node)}"
            claims.extend((name, module_node.value) for name in _claimed_names(pair.elts[1]))
    return claims


def _type_checking_claims() -> list[tuple[str, str]]:
    """Every ``(name, module)`` the ``TYPE_CHECKING`` block imports."""
    tree = ast.parse(_FACADE_SOURCE.read_text(encoding="utf-8"))
    claims: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or ast.unparse(node.test) != "TYPE_CHECKING":
            continue
        for statement in node.body:
            if not isinstance(statement, ast.ImportFrom):
                continue
            module = "." * statement.level + (statement.module or "")
            claims.extend((alias.name, module) for alias in statement.names)
    return claims


def test_the_claim_table_was_actually_read() -> None:
    """Anti-vacuity: every assertion below passes on an empty parse."""
    assert len(_lazy_claims()) >= _MINIMUM_EXPECTED_CLAIMS
    assert len(_type_checking_claims()) >= _MINIMUM_EXPECTED_CLAIMS


def test_no_name_is_claimed_by_two_modules() -> None:
    """The defect this module exists for: two homes, resolved by source order.

    Reported with both claimants named, because the survivor is the one the
    reader would find by importing and the loser is the one that has to be
    deleted -- a report naming only the name leaves the author to work out
    which of the two the file actually meant.
    """
    owners: dict[str, set[str]] = {}
    for name, module in _lazy_claims():
        owners.setdefault(name, set()).add(module)
    conflicts = {name: sorted(modules) for name, modules in owners.items() if len(modules) > 1}
    assert conflicts == {}, f"names claimed by more than one module in {_LAZY_TABLE_NAME}: {conflicts}"


def test_no_module_claims_the_same_name_twice() -> None:
    """The harmless half of the same slip, caught for the same reason.

    A name listed twice under ONE module resolves correctly today, so it costs
    nothing until the duplicate is the one that gets edited. It is the same
    hand-synchronisation failure and it is free to catch here.
    """
    repeated = sorted(claim for claim, count in Counter(_lazy_claims()).items() if count > 1)
    assert repeated == [], f"names listed more than once under the same module in {_LAZY_TABLE_NAME}: {repeated}"


def test_the_type_checking_block_and_the_lazy_table_agree() -> None:
    """The two hand-kept copies of the same ownership truth must match.

    The ``TYPE_CHECKING`` block is what a type checker and a reader resolve
    against; ``_LAZY_EXPORTS`` is what the interpreter resolves against.
    Divergence means the two answer differently, and only one of them is
    checked at runtime -- so the reader's copy is the one that rots silently.
    """
    assert sorted(set(_type_checking_claims())) == sorted(set(_lazy_claims()))


def test_every_lazily_claimed_name_is_public_and_every_public_name_is_bound() -> None:
    """The claim must be true of the module, not merely self-consistent.

    Two directions, and the second is what makes the ownership claim
    non-vacuous. Every lazily claimed name is exported, so the table cannot
    accumulate rows nothing may import. And every exported name resolves --
    through the lazy table or as an eager module-level binding -- so a module
    named as a home that does not define the symbol fails HERE rather than at
    the first import site to ask for it.
    """
    lazy_names = {name for name, _ in _lazy_claims()}
    exported = set(facade.__all__)
    assert lazy_names - exported == set(), f"claimed but not exported: {sorted(lazy_names - exported)}"
    unresolved = sorted(name for name in exported if not hasattr(facade, name))
    assert unresolved == [], f"exported but unresolvable through the facade: {unresolved}"
