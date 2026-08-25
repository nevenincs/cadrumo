"""An assimilation chain that closes into a ring must be refused at load.

Assimilation is stored as a POINTER, and the resolver answers for a carved-out
territory by re-asking itself for the parent. That is the right shape -- LIVA
art. 3.Tres fixes what a territory is treated AS and never what the parent
establishes -- but it makes termination a property of the DATA, so the loader
owns it.

The two checks that were there excluded a self-pointer and a parent no
catalogue names. Neither excludes a ring of two or more, and the table
deliberately admits the parent kind that can form one: a carve-out code is a
resolvable parent, because one territory being assimilated to another is
representable. So an ordinary registry edit -- exactly the maintenance this
table invites -- reached an unhandled ``RecursionError`` at RESOLVE time, on the
confirm path, while every sibling malformation in the same loader raises
``IvaCatalogueError`` at LOAD.

Real production validator throughout, driven against a synthetic table. Nothing
is patched and the bundled corpus is never written to: the file read and the
judgement of what the file says are separate functions, so a table that does not
exist on disk can still be judged by exactly the code the bundled one is.
"""

from __future__ import annotations

import pytest

from ..errors import IvaCatalogueError
from .._establishment import _carve_out_rows_from_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The provision the bundled assimilation rows themselves cite. Real, because
#: the loader verifies grounding after the chain checks, so a placeholder would
#: make the terminating-chain control fail for the wrong reason.
_REFS = ["ley-37-1992:art-3.tres"]


def _table(*assimilations: tuple[str, str]) -> dict[str, object]:
    """Return a parsed-table payload assimilating each code to its parent."""
    return {
        "carve_out": [
            {"code": code, "assimilated_to": parent, "legal_refs": list(_REFS)} for code, parent in assimilations
        ]
    }


def test_a_two_row_ring_is_refused_at_load() -> None:
    """The gap: neither prior check excludes it, and the resolver cannot terminate on it."""
    with pytest.raises(IvaCatalogueError) as caught:
        _carve_out_rows_from_payload("synthetic", _table(("MC", "IM"), ("IM", "MC")))

    assert "closes into a cycle" in str(caught.value)


def test_a_longer_ring_is_refused_at_load() -> None:
    """Two rows are the shortest ring past the self-pointer, not the only one.

    A check that walked one hop rather than the whole chain would pass this
    while still admitting a non-terminating table.
    """
    with pytest.raises(IvaCatalogueError) as caught:
        _carve_out_rows_from_payload("synthetic", _table(("MC", "IM"), ("IM", "JE"), ("JE", "MC")))

    assert "closes into a cycle" in str(caught.value)


def test_the_self_pointer_keeps_its_own_message() -> None:
    """The length-one case still earns the diagnostic that names it directly.

    The cycle walk would catch it too, so the risk is the specific refusal
    being quietly replaced by the general one -- the commonest mistake losing
    the message that tells the author what they did.
    """
    with pytest.raises(IvaCatalogueError) as caught:
        _carve_out_rows_from_payload("synthetic", _table(("MC", "MC")))

    assert "assimilated to itself" in str(caught.value)


def test_a_chain_that_terminates_still_loads() -> None:
    """The positive control the refusals are worthless without.

    A check that refused every assimilation would pass all three tests above
    and would take the real table down with it. This asserts the shape the
    bundled table actually uses -- a carve-out pointing at a non-carve-out
    parent -- survives, and that a legitimate multi-hop chain does too.
    """
    rows = _carve_out_rows_from_payload("synthetic", _table(("MC", "FR"), ("IM", "MC")))

    assert rows["MC"].assimilated_to == "FR"
    assert rows["IM"].assimilated_to == "MC"


def test_the_bundled_table_is_free_of_rings() -> None:
    """The check must bite on synthetic input AND pass on the shipped corpus.

    An anti-tautology proof over a synthetic table cannot catch a check that is
    correct on synthetic input while refusing the real one, and the real table
    is the only one that ships.
    """
    from .._establishment import _territory_carve_outs

    assert _territory_carve_outs()["MC"].assimilated_to == "FR"
